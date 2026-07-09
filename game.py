from abc import ABC, abstractmethod
from email.policy import default
from threading import Lock, Thread
from queue import Queue, LifoQueue, Empty, Full
from time import time
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld, Recipe
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.mdp.actions import Action, Direction
from overcooked_ai_py.planning.planners import MediumLevelActionManager, MotionPlanner, NO_COUNTERS_PARAMS, COUNTERS_MLG_PARAMS
from overcooked_ai_py.agents.agent import GreedyAgent, LazyAgent, RationalAgent, RandomAgent, PlanningAgent
import random
import os
import pickle
import json
import logging
from copy import deepcopy, copy
from overcooked_ai_py.static import LAYOUTS_DIR
from time import gmtime, asctime
from utils import ThreadSafeDict

# Logger enfant : hérite des handlers du logger 'overcooked' configuré dans app.py.
logger = logging.getLogger("overcooked.game")

# Relative path to where all static pre-trained agents are stored on server
AGENT_DIR = None

# Maximum allowable game time (in seconds)
MAX_GAME_TIME = 1000

# ---------------------------------------------------------------------------
# Caches mémoïsés (perf) : un MDP et son MediumLevelActionManager (mlam) sont
# coûteux à construire et sont recréés à chaque essai dans le code historique.
# On les mémoïse par clé déterministe (layout + paramètres MDP effectifs).
#   - MDP_CACHE  : OvercookedGridworld "template" PARTAGÉ en lecture seule. Ne JAMAIS
#                  le muter : la couche jeu en prend une copie superficielle pour y
#                  poser les attributs runtime (human_player_indices/forced_cutting).
#   - MLAM_CACHE : MediumLevelActionManager partagé (get_plan/min_cost_* sont en
#                  lecture seule -> partage concurrent sûr entre passations).
# Voir get_cached_mdp / get_cached_mlam.
# ---------------------------------------------------------------------------
MDP_CACHE = ThreadSafeDict()
MLAM_CACHE = ThreadSafeDict()
# NB : on ne met PAS en cache les agents. Dans PlanningGame, l'agent (Greedy/Rational/…)
# est construit en code (PlanningGame.get_policy) et décide EN DIRECT à chaque état
# (policy.action(state)) : son comportement s'adapte à l'environnement et ne peut donc
# pas être préchargé. Seul l'ENVIRONNEMENT est mémoïsé (MDP = règles du layout, mlam =
# géométrie/plus-courts-chemins), ce que l'agent utilise pour planifier ses décisions.


def _mdp_cache_key(layout, layouts_dir, mdp_params):
    """Clé hashable, stable et déterministe pour un MDP (sort_keys ; default=str
    pour les valeurs non sérialisables type set)."""
    return json.dumps(
        {"layout": layout, "dir": layouts_dir, "params": mdp_params},
        sort_keys=True, default=str,
    )


def get_cached_mdp(layout, layouts_dir, mdp_params):
    """
    Retourne (mdp_template, key). Le template est construit une seule fois par clé
    via OvercookedGridworld.from_layout_name puis PARTAGÉ. NE PAS muter le template :
    en prendre une copie (copy.copy) pour les attributs runtime.
    """
    key = _mdp_cache_key(layout, layouts_dir, mdp_params)
    mdp = MDP_CACHE.get(key, None)
    if mdp is None:
        mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir, **mdp_params)
        MDP_CACHE[key] = mdp
    return mdp, key


def get_cached_mlam(mdp_template, key):
    """
    Retourne le MediumLevelActionManager associé au MDP template (mémoïsé par `key`).
    Réplique la logique de PlanningAgent.set_mdp (counter params) afin d'obtenir un
    mlam strictement équivalent à celui calculé historiquement, mais une seule fois.
    """
    mlam = MLAM_CACHE.get(key, None)
    if mlam is None:
        # dict(...) : ne pas muter le COUNTERS_MLG_PARAMS global (réf. partagée).
        counter_params = dict(COUNTERS_MLG_PARAMS)
        if mdp_template.counter_goals:
            counter_params["counter_goals"] = mdp_template.counter_goals
            counter_params["counter_drop"] = mdp_template.counter_goals
            counter_params["counter_pickup"] = mdp_template.counter_goals
        mlam = MediumLevelActionManager.from_pickle_or_compute(
            mdp_template, counter_params, force_compute=False)
        MLAM_CACHE[key] = mlam
    return mlam


def warmup_caches(configs):
    """
    Pré-chauffe les caches d'ENVIRONNEMENT au démarrage pour que le PREMIER participant
    ne paie pas le coût de construction du MDP + mlam (géométrie du layout).

    On ne précharge AUCUN agent : dans PlanningGame, l'agent est construit en code et
    décide en direct (comportement adaptatif, non préchargeable).

    Best-effort : reproduit fidèlement les clés du chemin runtime (mdp_params de base
    vides pour PlanningGame + mdp_overrides_from_config(config) ; layouts_dir résolu
    comme dans OvercookedGame.__init__). Toute erreur est journalisée sans interrompre
    le démarrage du serveur.

    Args:
        configs (dict): le CONFIG global ; seules les entrées d'expérience (dict avec
                        une clé "blocs") sont traitées, les autres sont ignorées.
    """
    n_mdp = n_mlam = 0
    for config_id, config in (configs or {}).items():
        if not isinstance(config, dict) or "blocs" not in config:
            continue
        try:
            overrides = OvercookedGridworld.mdp_overrides_from_config(config)
        except Exception:
            logger.exception("[WARMUP] mdp_overrides_from_config a échoué (config=%s)", config_id)
            continue
        mdp_params = dict(overrides)  # base self.mdp_params == {} pour PlanningGame
        layouts_dir = config.get("layouts_dir", LAYOUTS_DIR)
        layouts = set()
        for trials in config.get("blocs", {}).values():
            if isinstance(trials, list):
                layouts.update(trials)
        for layout in layouts:
            try:
                mdp_template, key = get_cached_mdp(layout, layouts_dir, mdp_params)
                n_mdp += 1
                get_cached_mlam(mdp_template, key)
                n_mlam += 1
            except Exception:
                logger.exception("[WARMUP] échec MDP/mlam (layout=%s config=%s)", layout, config_id)
    logger.info("[WARMUP] caches d'environnement préchauffés : mdp=%d mlam=%d", n_mdp, n_mlam)


def _configure(max_game_time, agent_dir):
    global AGENT_DIR, MAX_GAME_TIME
    MAX_GAME_TIME = max_game_time
    AGENT_DIR = agent_dir


class Game(ABC):
    """
    Class representing a game object. Coordinates the simultaneous actions of arbitrary
    number of players. Override this base class in order to use. 

    Players can post actions to a `pending_actions` queue, and driver code can call `tick` to apply these actions.


    It should be noted that most operations in this class are not on their own thread safe. Thus, client code should
    acquire `self.lock` before making any modifications to the instance. 

    One important exception to the above rule is `enqueue_actions` which is thread safe out of the box
    """

    # Possible TODO: create a static list of IDs used by the class so far to verify id uniqueness
    # This would need to be serialized, however, which might cause too great a performance hit to
    # be worth it

    EMPTY = 'EMPTY'

    class Status:
        DONE = 'done'
        ACTIVE = 'active'
        RESET = 'reset'
        INACTIVE = 'inactive'
        ERROR = 'error'
        QPT = 'qpt'

    def __init__(self, *args, **kwargs):
        """
        players (list): List of IDs of players currently in the game
        spectators (set): Collection of IDs of players that are not allowed to enqueue actions but are currently watching the game
        id (int):   Unique identifier for this game
        pending_actions List[(Queue)]: Buffer of (player_id, action) pairs have submitted that haven't been commited yet
        lock (Lock):    Used to serialize updates to the game state
        is_active(bool): Whether the game is currently being played or not
        """
        self.players = []
        self.spectators = set()
        self.pending_actions = []
        self.id = kwargs.get('id', id(self))
        self.id = id(self)
        self.lock = Lock()
        self._is_active = False

    @abstractmethod
    def is_full(self):
        """
        Returns whether there is room for additional players to join or not
        """
        pass

    @abstractmethod
    def apply_action(self, player_idx, action):
        """
        Updates the game state by applying a single (player_idx, action) tuple. Subclasses should try to override this method
        if possible
        """
        pass

    @abstractmethod
    def is_finished(self):
        """
        Returns whether the game has concluded or not
        """
        pass

    def is_ready(self):
        """
        Returns whether the game can be started. Defaults to having enough players
        """
        return self.is_full()

    @property
    def is_active(self):
        """
        Whether the game is currently being played
        """
        return self._is_active

    @property
    def reset_timeout(self):
        """
        Number of milliseconds to pause game on reset
        """
        return 3000

    def apply_actions(self):
        """
        Updates the game state by applying each of the pending actions in the buffer. Is called by the tick method. Subclasses
        should override this method if joint actions are necessary. If actions can be serialized, overriding `apply_action` is 
        preferred
        """
        for i in range(len(self.players)):
            try:
                while True:
                    action = self.pending_actions[i].get(block=False)
                    self.apply_action(i, action)
            except Empty:
                pass

    def activate(self):
        """
        Activates the game to let server know real-time updates should start. Provides little functionality but useful as
        a check for debugging
        """
        self._is_active = True

    def deactivate(self):
        """
        Deactives the game such that subsequent calls to `tick` will be no-ops. Used to handle case where game ends but 
        there is still a buffer of client pings to handle
        """
        self._is_active = False

    def reset(self):
        """
        Restarts the game while keeping all active players by resetting game stats and temporarily disabling `tick`
        """
        if not self.is_active:
            raise ValueError("Inactive Games cannot be reset")
        if self.is_finished():
            return self.Status.DONE
        self.deactivate()
        self.activate()
        return self.Status.RESET

    def needs_reset(self):
        """
        Returns whether the game should be reset on the next call to `tick`
        """
        return False
# méthode appelée périodiquement pour mettre à jour l'état du jeu
# elle applique les actions en attente
# Elle met nottament à jour la classe PlanningGame lorsque tick
# est appelée périodiquement pas la boucle de jeu asynchrone play_game

    def tick(self):
        """
        Updates the game state by applying each of the pending actions. This is done so that players cannot directly modify
        the game state, offering an additional level of safety and thread security. 

        One can think of "enqueue_action" like calling "git add" and "tick" like calling "git commit"

        Subclasses should try to override `apply_actions` if possible. Only override this method if necessary
        """
        if not self.is_active:
            return self.Status.INACTIVE
        if self.needs_reset():
            self.reset()
            return self.Status.RESET

        self.apply_actions()
        return self.Status.DONE if self.is_finished() else self.Status.ACTIVE

    def enqueue_action(self, player_id, action):
        """
        Add (player_id, action) pair to the pending action queue, without modifying underlying game state

        Note: This function IS thread safe
        """
        if not self.is_active:
            # Could run into issues with is_active not being thread safe
            return
        if player_id not in self.players:
            # Only players actively in game are allowed to enqueue actions
            return
        try:
            player_idx = self.players.index(player_id)
            self.pending_actions[player_idx].put(action)
        except Full:
            pass

    def get_state(self):
        """
        Return a JSON compatible serialized state of the game. Note that this should be as minimalistic as possible
        as the size of the game state will be the most important factor in game performance. This is sent to the client
        every frame update.
        """
        return {"players": self.players}

    def to_json(self):
        """
        Return a JSON compatible serialized state of the game. Contains all information about the game, does not need to
        be minimalistic. This is sent to the client only once, upon game creation
        """
        return self.get_state()

    def is_empty(self):
        """
        Return whether it is safe to garbage collect this game instance
        """
        return not self.num_players

    def add_player(self, player_id, idx=None, buff_size=-1):
        """
        Add player_id to the game
        """
        if self.is_full():
            raise ValueError("Cannot add players to full game")
        if self.is_active:
            raise ValueError("Cannot add players to active games")
        if not idx and self.EMPTY in self.players:
            idx = self.players.index(self.EMPTY)
        elif not idx:
            idx = len(self.players)

        padding = max(0, idx - len(self.players) + 1)
        for _ in range(padding):
            self.players.append(self.EMPTY)
            self.pending_actions.append(self.EMPTY)

        self.players[idx] = player_id
        self.pending_actions[idx] = Queue(maxsize=buff_size)

    def add_spectator(self, spectator_id):
        """
        Add spectator_id to list of spectators for this game
        """
        if spectator_id in self.players:
            raise ValueError("Cannot spectate and play at same time")
        self.spectators.add(spectator_id)

    def remove_player(self, player_id):
        """
        Remove player_id from the game
        """
        try:
            idx = self.players.index(player_id)
            self.players[idx] = self.EMPTY
            self.pending_actions[idx] = self.EMPTY
        except ValueError:
            return False
        else:
            return True

    def remove_spectator(self, spectator_id):
        """
        Removes spectator_id if they are in list of spectators. Returns True if spectator successfully removed, False otherwise
        """
        try:
            self.spectators.remove(spectator_id)
        except ValueError:
            return False
        else:
            return True

    def clear_pending_actions(self):
        """
        Remove all queued actions for all players
        """
        for i, player in enumerate(self.players):
            if player != self.EMPTY:
                queue = self.pending_actions[i]
                queue.queue.clear()

    @property
    def num_players(self):
        return len([player for player in self.players if player != self.EMPTY])

    def get_data(self):
        """
        Return any game metadata to server driver. Really only relevant for Psiturk code
        """
        return {}


class DummyGame(Game):
    """
    Standin class used to test basic server logic
    """

    def __init__(self, **kwargs):
        super(DummyGame, self).__init__(**kwargs)
        self.counter = 0

    def is_full(self):
        return self.num_players == 2

    def apply_action(self, idx, action):
        pass

    def apply_actions(self):
        self.counter += 1

    def is_finished(self):
        return self.counter >= 100

    def get_state(self):
        state = super(DummyGame, self).get_state()
        state['count'] = self.counter
        return state


class DummyInteractiveGame(Game):
    """
    Standing class used to test interactive components of the server logic
    """

    def __init__(self, **kwargs):
        super(DummyInteractiveGame, self).__init__(**kwargs)
        self.max_players = int(kwargs.get('playerZero', 'human') == 'human') + int(
            kwargs.get('playerOne', 'human') == 'human')
        self.max_count = kwargs.get('max_count', 30)
        self.counter = 0
        self.counts = [0] * self.max_players

    def is_full(self):
        return self.num_players == self.max_players

    def is_finished(self):
        return max(self.counts) >= self.max_count

    def apply_action(self, player_idx, action):
        if action.upper() == Direction.NORTH:
            self.counts[player_idx] += 1
        if action.upper() == Direction.SOUTH:
            self.counts[player_idx] -= 1

    def apply_actions(self):
        super(DummyInteractiveGame, self).apply_actions()
        self.counter += 1

    def get_state(self):
        state = super(DummyInteractiveGame, self).get_state()
        state['count'] = self.counter
        for i in range(self.num_players):
            state['player_{}_count'.format(i)] = self.counts[i]
        return state


class OvercookedGame(Game):
    """
    Class for bridging the gap between Overcooked_Env and the Game interface

    Instance variable:
        - max_players (int): Maximum number of players that can be in the game at once
        - mdp (OvercookedGridworld): Controls the underlying Overcooked game logic
        - score (int): Current reward acheived by all players
        - max_time (int): Number of seconds the game should last
        - npc_policies (dict): Maps user_id to policy (Agent) for each AI player
        - npc_state_queues (dict): Mapping of NPC user_ids to LIFO queues for the policy to process
        - curr_tick (int): How many times the game server has called this instance's `tick` method
        - ticker_per_ai_action (int): How many frames should pass in between NPC policy forward passes. 
            Note that this is a lower bound; if the policy is computationally expensive the actual frames
            per forward pass can be higher
        - action_to_overcooked_action (dict): Maps action names returned by client to action names used by OvercookedGridworld
            Note that this is an instance variable and not a static variable for efficiency reasons
        - human_players (set(str)): Collection of all player IDs that correspond to humans
        - npc_players (set(str)): Collection of all player IDs that correspond to AI
        - randomized (boolean): Whether the order of the layouts should be randomized

    Methods:
        - npc_policy_consumer: Background process that asynchronously computes NPC policy forward passes. One thread
            spawned for each NPC
        - _curr_game_over: Determines whether the game on the current mdp has ended
    """

    def __init__(self, layouts=["cramped_room"], mdp_params={}, num_players=2, gameTime=30, playerZero='human',
                 playerOne='human', showPotential=False, randomized=False, **kwargs):
        super(OvercookedGame, self).__init__(**kwargs)
        self.show_potential = showPotential
        self.mdp_params = mdp_params
        self.layouts = layouts
        self.curr_trial_in_game = kwargs.get("curr_trial_in_game",-1)
        self.curr_layout = self.layouts[self.curr_trial_in_game]
        self.max_players = int(num_players)
        self.mdp = None
        self.mp = None
        self.score = 0
        self.phi = 0
        self.max_time = min(int(gameTime), MAX_GAME_TIME)
        self.action_to_overcooked_action = {
            "STAY": Action.STAY,
            "UP": Direction.NORTH,
            "DOWN": Direction.SOUTH,
            "LEFT": Direction.WEST,
            "RIGHT": Direction.EAST,
            "SPACE": Action.INTERACT
        }
        self.ticks_per_ai_action = 4
        self.curr_tick = 0
        self.human_players = set()
        self.npc_players = set()
        self.playerZero = playerZero
        self.playerOne = playerOne
        self.npc_policies = {}
        self.npc_state_queues = {}
        try:
            self.layouts_dir = kwargs["config"]['layouts_dir']
        except KeyError:
            self.layouts_dir = LAYOUTS_DIR

        if randomized:
            random.shuffle(self.layouts)

        if self.playerZero != 'human':
            self.planning_agent_id = self.playerZero + '_0'
            player_zero_id = self.playerZero + '_0'
            self.add_player(player_zero_id, idx=0, buff_size=1, is_human=False)
            self.npc_policies[player_zero_id] = self.get_policy(
                self.playerZero, idx=0)
            self.npc_state_queues[player_zero_id] = LifoQueue()

        if self.playerOne != 'human':
            self.planning_agent_id = self.playerOne + '_1'
            player_one_id = self.playerOne + '_1'
            self.add_player(player_one_id, idx=1, buff_size=1, is_human=False)
            self.npc_policies[player_one_id] = self.get_policy(
                self.playerOne, idx=1)
            self.npc_state_queues[player_one_id] = LifoQueue()
       # breakpoint()
        #1

    def needs_player_renew(self):
        '''
        renvoie None, False
        '''
        return None, False

    def _curr_game_over(self): # Vérifie si la durée maximum de l'essaie est dépassée
        return time() - self.start_time >= self.max_time

    def needs_reset(self):
        """
        Override needs_reset to handle the case where all_orders is empty.
        When all orders are completed, the game should reset regardless of whether it's the last trial.
        """
        game_over = self._curr_game_over()
        if not game_over:
            return False
        
        # Si la partie est terminée à cause des commandes vides, on reset même si c'est le dernier essai
        if self.mechanic == "recipe" and len(self.state.all_orders) == 0:
            return True
        
        # Sinon, on utilise la logique normale (reset seulement si pas terminé)
        return not self.is_finished()

    def add_player(self, player_id, idx=None, buff_size=-1, is_human=True):
        super(OvercookedGame, self).add_player(
            player_id, idx=idx, buff_size=buff_size)
        if is_human:
            self.human_players.add(player_id)
        else:
            self.npc_players.add(player_id)

    def remove_player(self, player_id):
        removed = super(OvercookedGame, self).remove_player(player_id)
        if removed:
            if player_id in self.human_players:
                self.human_players.remove(player_id)
            elif player_id in self.npc_players:
                self.npc_players.remove(player_id)
            else:
                raise ValueError("Inconsistent state")

    def npc_policy_consumer(self, policy_id):
        queue = self.npc_state_queues[policy_id]
        policy = self.npc_policies[policy_id]
        crash_logged = False
        while self._is_active:
            state = queue.get()
            try:
                npc_action, _ = policy.action(state)
            except Exception:
                # Une panne de l'agent ne doit JAMAIS tuer silencieusement le thread :
                # sinon plus aucune action NPC n'est produite, l'état n'avance plus et
                # l'écran reste noir sans erreur visible. On loggue la trace complète
                # (1re occurrence seulement, pour éviter le spam) et on continue avec
                # STAY afin que la boucle de jeu reste réactive et affichée.
                if not crash_logged:
                    logger.exception(
                        "[NPC_POLICY_CRASH] policy=%s : exception dans policy.action ; "
                        "repli sur Action.STAY pour ne pas figer le jeu", policy_id)
                    crash_logged = True
                npc_action = Action.STAY
            super(OvercookedGame, self).enqueue_action(policy_id, npc_action)

    def is_full(self):
        return self.num_players >= self.max_players

    def is_finished(self): # Vérifie si le dernier essai réalisé était le dernier 
        val = self.curr_trial_in_game >= len(
            self.layouts) - 1 and self._curr_game_over()
        return val

    def is_empty(self):
        """
        Game is considered safe to scrap if there are no active players or if there are no humans (spectating or playing)
        """
        return super(OvercookedGame, self).is_empty() or not self.spectators and not self.human_players

    def is_ready(self):
        """
        Game is ready to be activated if there are a sufficient number of players and at least one human (spectator or player)
        """
        return super(OvercookedGame, self).is_ready() and not self.is_empty()

    def apply_action(self, player_id, action):
        pass

    def apply_actions(self):
        # Default joint action, as NPC policies and clients probably don't enqueue actions fast
        # enough to produce one at every tick
        joint_action = [Action.STAY] * len(self.players)

        # Synchronize individual player actions into a joint-action as required by overcooked logic
        for i in range(len(self.players)):
            try:
                joint_action[i] = self.pending_actions[i].get(block=False)
            except Empty:
                pass

        # Apply overcooked game logic to get state transition
        prev_state = self.state
        self.state, info = self.mdp.get_state_transition(
            prev_state, joint_action)
        if self.show_potential:
            self.phi = self.mdp.potential_function(
                prev_state, self.mp, gamma=0.99)

        # Send next state to all background consumers if needed
        if self.curr_tick % self.ticks_per_ai_action == 0:
            for npc_id in self.npc_policies:
                self.npc_state_queues[npc_id].put(self.state, block=False)

        # Update score based on soup deliveries that might have occured
        curr_reward = sum(info['sparse_reward_by_agent'])
        self.score += curr_reward

        # Return about the current transition
        return prev_state, joint_action, info

    def enqueue_action(self, player_id, action):
        overcooked_action = self.action_to_overcooked_action[action]
        super(OvercookedGame, self).enqueue_action(
            player_id, overcooked_action)

    def reset(self):
        status = super(OvercookedGame, self).reset()
        if status == self.Status.RESET:
            # Hacky way of making sure game timer doesn't "start" until after reset timeout has passed
            self.start_time += self.reset_timeout / 1000

    def tick(self):
        if self.curr_tick == 0:
            self.start_time = time()
        self.curr_tick += 1
        return super(OvercookedGame, self).tick()

    def activate(self):
        # Passage à l'essai suivant (try/except : le tutoriel n'a pas de self.step).
        try:
            logger.debug("[ACTIVATE] passage à l'essai %s du bloc %s",
                         self.curr_trial_in_game + 2, self.step + 1)
        except Exception:
            logger.debug("[ACTIVATE] tutoriel (pas d'essai/bloc)")
        self.curr_trial_in_game += 1 # permet de passer à l'essai (et donc au layout) suivant
        self.curr_layout = self.layouts[self.curr_trial_in_game] # charge le layout de l'essai actuel
        logger.debug("[ACTIVATE] chargement du layout: %s", self.curr_layout)
        # [CONFIG SOURCE OF TRUTH] La config écrase les valeurs du layout pour les paramètres
        # listés dans OvercookedGridworld.CONFIG_DRIVEN_MDP_PARAMS (valeurs/temps des ingrédients,
        # dispenser_pool, paramètres de découpe, AI_forced_cutting).
        config_overrides = OvercookedGridworld.mdp_overrides_from_config(getattr(self, "config", {}))
        mdp_params = {**self.mdp_params, **config_overrides}
        # [CACHE] MDP template mémoïsé (construit une seule fois par layout+params).
        # On en prend une COPIE superficielle pour y poser les attributs runtime
        # ci-dessous, sans jamais muter le template partagé.
        _t_mdp = time()
        try:
            mdp_template, mdp_key = get_cached_mdp(self.curr_layout, self.layouts_dir, mdp_params)
        except Exception as e:
            logger.error("[ACTIVATE] échec de chargement du layout %s : %s", self.curr_layout, e)
            raise
        self.mdp = copy(mdp_template)
        _mdp_ms = (time() - _t_mdp) * 1000

        # [FORCED CUTTING] Renseigner le MDP sur les joueurs humains. AI_forced_cutting provient
        # désormais de la config (via CONFIG_DRIVEN_MDP_PARAMS) ; Human_forced_cutting est appliqué
        # ci-dessous car il dépend de l'identité runtime des joueurs humains.
        self.mdp.human_player_indices = {
            idx for idx, pid in enumerate(self.players) if pid in self.human_players
        }
        self.mdp.human_forced_cutting = bool(
            getattr(self, "config", {}).get("Human_forced_cutting", False)
        )
        player_to_renew, needs_player_renew = self.needs_player_renew()
        if needs_player_renew: # condition jamais respectée
            self.remove_player(player_to_renew)
            self.npc_policies = {}
            self.npc_state_queues = {}
            if self.playerZero != 'human':
                self.planning_agent_id = self.playerZero + '_0'
                player_zero_id = self.playerZero + '_0'
                self.add_player(player_zero_id, idx=0,
                                buff_size=1, is_human=False)
                self.npc_policies[player_zero_id] = self.get_policy(
                    self.playerZero, idx=0)
                self.npc_state_queues[player_zero_id] = LifoQueue()

            if self.playerOne != 'human':
                self.planning_agent_id = self.playerOne + '_1'
                player_one_id = self.playerOne + '_1'
                self.add_player(player_one_id, idx=1,
                                buff_size=1, is_human=False)
                self.npc_policies[player_one_id] = self.get_policy(
                    self.playerOne, idx=1)
                self.npc_state_queues[player_one_id] = LifoQueue()

        # Sanity check at start of each game
        # vérifier que les joueurs enregistrés soint présents dans la liste des joueurs
        # pas compris pourquoi c'est nécessaire
            # self.npc_players = ensemble contenant les identifiants de tous les joueurs AA
            # self.human_players = ensemble contenant les identifiants de tous les joueurs humains
            # self.players = liste contenant les identifiants de tous les joueurs
        if not self.npc_players.union(self.human_players) == set(self.players): 
            raise ValueError("Inconsistent State")
# Try to remove the unecessary motion planner
        #if self.show_potential: # semble prendre la valeur false à l'initialisation de la classe overcookedGame
        #    self.mp = MotionPlanner.from_pickle_or_compute( # permet de charger un système de planification du mouvement pour l'essai en cours
        #       self.mdp, counter_goals=self.mdp.counter_goals) # Le fichier motionplanner.py gére tous les calculs liés aux déplacements et interactions avec layout
        self.state = self.mdp.get_standard_start_state() # retourne la position, l'orientation du joueur et s'il tient objet
        if self.show_potential:
            self.phi = self.mdp.potential_function( # fonction plus utilisée (gérait un comportement)
                self.state, self.mp, gamma=0.99)
        self.curr_tick = 0
        self.score = 0
        self.threads = []
        super(OvercookedGame, self).activate() # attribut à _is_active la valeur True ce qui active la méthode tick
        # [CACHE] mlam mémoïsé (partagé en lecture seule). Pour les agents
        # planificateurs, on injecte directement le mlam caché et le MDP template
        # (référencé par le mlam), ce qui évite le from_pickle_or_compute coûteux de
        # set_mdp. Les autres agents (Random/Stay) gardent le comportement historique.
        _t_mlam = time()
        mlam = get_cached_mlam(mdp_template, mdp_key)
        _mlam_ms = (time() - _t_mlam) * 1000
        for npc_policy in self.npc_policies:
            agent = self.npc_policies[npc_policy]
            agent.reset()
            if isinstance(agent, PlanningAgent):
                agent.mdp = mdp_template
                agent.mlam = mlam
            else:
                agent.set_mdp(self.mdp)
            self.npc_state_queues[npc_policy] = LifoQueue()
            self.npc_state_queues[npc_policy].put(self.state)

            t = Thread(target=self.npc_policy_consumer, args=(npc_policy,)) # permet processus tourne en boucle, ici au npc d'avoir une prise d'information/décision/execution autonome
            self.threads.append(t)
            t.start()
        self.start_time = time()
        try:
            logger.info("[PROFILE activate] layout=%s bloc=%s essai=%s mdp_ms=%.1f mlam_ms=%.1f",
                        self.curr_layout, getattr(self, "step", "?"),
                        self.curr_trial_in_game, _mdp_ms, _mlam_ms)
        except Exception:
            logger.debug("[ACTIVATE] activé (tutoriel) mdp_ms=%.1f mlam_ms=%.1f", _mdp_ms, _mlam_ms)
    def deactivate(self):
        super(OvercookedGame, self).deactivate()
        # Ensure the background consumers do not hang
        for npc_policy in self.npc_policies:
            self.npc_state_queues[npc_policy].put(self.state)

        # Wait for all background threads to exit
        for t in self.threads:
            t.join()

        # Clear all action queues
        self.clear_pending_actions()

    def get_state(self):
        state_dict = {}
        state_dict['potential'] = self.phi if self.show_potential else None
        state_dict['state'] = self.state.to_dict()
        state_dict['score'] = self.score
        state_dict['time_left'] = max(
            self.max_time - (time() - self.start_time), 0)
        # [ASYMMETRIC DISPENSERS] Le client humain (joueur 0) ne voit que les items des dispensers 'A'
        # TODO: réactiver ce filtre après les tests visuels (supprimer le commentaire ci-dessous)
        # if self.mdp.has_asymmetric_dispensers():
        #     b_positions = {tuple(p) for p in self.mdp.get_player1_dispenser_locations()}
        #     state_dict['state']['dispenser_items'] = [
        #         entry for entry in state_dict['state'].get('dispenser_items', [])
        #         if (entry[0], entry[1]) not in b_positions
        #     ]
#        print ("valeur de la variable state_dict['state'] : ", state_dict['state'])
        return state_dict

    def to_json(self):
        obj_dict = {}
        obj_dict['counter_goals'] = self.mdp.counter_goals
        obj_dict['terrain'] = self.mdp.terrain_mtx if self._is_active else None
        obj_dict['state'] = self.get_state() if self._is_active else None
        obj_dict['order_triplets'] = self.mdp.order_triplets
        return obj_dict

    def get_policy(self, npc_id, idx=0):
        # if npc_id.lower().startswith("rllib"):
        #     try:
        #         # Loading rllib agents requires additional helpers
        #         fpath = os.path.join(AGENT_DIR, npc_id, 'agent', 'agent')
        #         agent = load_agent(fpath, agent_index=idx)
        #         return agent
        #     except Exception as e:
        #         raise IOError(
        #             "Error loading Rllib Agent\n{}".format(e.__repr__()))
        #     finally:
        #         # Always kill ray after loading agent, otherwise, ray will crash once process exits
        #         if ray.is_initialized():
        #             ray.shutdown()
        #else:
        try:
            fpath = os.path.join(AGENT_DIR, npc_id, 'agent.pickle')
            with open(fpath, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            raise IOError("Error loading agent\n{}".format(e.__repr__()))


class PlanningGame(OvercookedGame):
    """

    """

    def __init__(self, mdp_params={}, *args,  **kwargs):
        self.step = kwargs.get("step", -1)
        kwargs.get("config").pop("completion_link", None)
        self.config = kwargs.get("config")
        #print("CONFIG:::::::::::::::::::::",self.config)
        self.shuffle_trials = bool(self.config.get("shuffle_trials", False))
        self.layouts = self.config.get("blocs")[str(self.step)]
        self.curr_condition = self.config.get("conditions")[str(self.step)]
        # Mode "un essai par session" : la session ne joue que l'essai courant
        # puis passe en DONE (les questionnaires post-essai/post-bloc sont des
        # pages HTML autonomes servies hors-jeu). On conserve la liste complète
        # des essais du bloc pour que curr_trial_in_game / trial_id / le total
        # affiché restent corrects ; seul l'enchaînement intra-session change.
        self.single_trial = bool(kwargs.get("single_trial", False))
        self.is_first_trial_of_block = bool(kwargs.get("is_first_trial_of_block", False))
        self.total_trials_in_bloc = len(self.layouts)
        self.participant_uid = kwargs.get('player_uid', '-1')
        self.mechanic = self.config.get('mechanic', 'time')
        self.qpt = self.config.get('qpt', {})
        self.qpt_length = self.config.get('qpt_length', 5)
        self.data = []
        self.mdp_params = mdp_params
        self.trajectory = []
        self.human_action_count = 0
        self.agent_action_count = 0
        self.human_interact_count = 0
        self.agent_interact_count = 0
        self.human_counter_share = 0
        self.infos = []
        
        # Initialize trial_id for compatibility
        self.trial_id = None
        
        # Initialize AI slowdown system for PlanningGame only
        self.base_ticks_per_ai_action = self.config.get("ai_base_speed", 4)
        self.slow_ticks_per_ai_action = self.config.get("ai_slow_speed", 12) 
        self.trial_start_ticks_per_ai_action = self.config.get("ai_trial_start_speed", 20)
        self.asset_slow_ticks_per_ai_action = self.config.get("ai_asset_slow_speed", 30)
        self.slow_duration_ticks = self.config.get("ai_slow_duration", 20)
        self.asset_slow_duration_ticks = self.config.get("ai_asset_slow_duration", 25)
        self.ai_slowdown_enabled = self.config.get("ai_slowdown_enabled", True)
        self.ai_asset_slowdown_enabled = self.config.get("ai_asset_slowdown_enabled", True)
        self.ai_asset_slowdown_intentions = self.config.get("ai_asset_slowdown_intentions", ["O", "T", "D", "S", "P", "X", "C"])
        self.slow_remaining_ticks = 0
        self.trial_start_slow_remaining_ticks = 0
        self.asset_slow_remaining_ticks = 0
        self.last_recipe_intention = None
        self.last_asset_intention = None
        
        kwargs.update(
            {"playerZero": self.config["agent"], "gameTime": self.config["gameTime"]})
        super(PlanningGame, self).__init__(
            mdp_params=mdp_params, layouts=self.layouts, *args, **kwargs)
        
        # Set initial AI speed after parent initialization
        self.ticks_per_ai_action = self.base_ticks_per_ai_action

        # Triplet display system — configuration (constant throughout experiment)
        self.triplet_enabled = bool(self.config.get('triplet', False))
        self.triplet_display_min = float(self.config.get('triplet_display_min', 10))
        self.triplet_display_max = float(self.config.get('triplet_display_max', 30))
        # Runtime triplet state (properly initialised in activate())
        self.order_triplets = None
        self.orders_served = 0
        self.current_triplet_index = 0
        self.triplet_start_time = None
        self.triplet_duration = 0

        # Temporary recipe system — configuration (constante sur l'expérience)
        self.temporary_recipe_enabled = bool(self.config.get('temporary_recipe', False))
        self.random_temporary_recipe = bool(self.config.get('random_temporary_recipe', False))
        self.min_temporary_recipe = float(self.config.get('minimum_time_temporary_recipe', 10))
        self.max_temporary_recipe = float(self.config.get('maximum_time_temporary_recipe', 50))
        self.exact_temporary_recipe = float(self.config.get('exact_time_temporary_recipe', 50))
        # État runtime : {ingredients(tuple): timestamp d'expiration}, réinitialisé par essai
        self.recipe_expiry = {}

        # infinite_all_order — configuration (constante sur l'expérience)
        # Quand actif, l'essai n'épuise jamais ses commandes : on maintient en permanence
        # `number_shown_recipes` recettes affichées, réapprovisionnées (unique) depuis le
        # pool du layout (start_all_orders) après chaque livraison/expiration.
        self.infinite_all_order = bool(self.config.get('infinite_all_order', False))
        self.number_shown_recipes = int(self.config.get('number_shown_recipes', 5))

    def _update_ai_speed(self):
        """Update AI speed based on slowdown state (PlanningGame only)."""
        if not self.ai_slowdown_enabled:
            self.ticks_per_ai_action = self.base_ticks_per_ai_action
            return
        
        old_speed = self.ticks_per_ai_action
        
        # Priority: trial start slowdown > asset change slowdown > recipe change slowdown > normal speed
        if self.trial_start_slow_remaining_ticks > 0:
            self.ticks_per_ai_action = self.trial_start_ticks_per_ai_action
            self.trial_start_slow_remaining_ticks -= 1
            if old_speed != self.ticks_per_ai_action:
                print(f"[AI_SLOWDOWN] Speed changed to TRIAL START SLOW: {self.ticks_per_ai_action} (remaining: {self.trial_start_slow_remaining_ticks})")
        elif self.asset_slow_remaining_ticks > 0:
            self.ticks_per_ai_action = self.asset_slow_ticks_per_ai_action
            self.asset_slow_remaining_ticks -= 1
            if old_speed != self.ticks_per_ai_action:
                print(f"[AI_SLOWDOWN] Speed changed to ASSET CHANGE SLOW: {self.ticks_per_ai_action} (remaining: {self.asset_slow_remaining_ticks})")
        elif self.slow_remaining_ticks > 0:
            self.ticks_per_ai_action = self.slow_ticks_per_ai_action
            self.slow_remaining_ticks -= 1
            if old_speed != self.ticks_per_ai_action:
                print(f"[AI_SLOWDOWN] Speed changed to RECIPE CHANGE SLOW: {self.ticks_per_ai_action} (remaining: {self.slow_remaining_ticks})")
        else:
            self.ticks_per_ai_action = self.base_ticks_per_ai_action
            if old_speed != self.ticks_per_ai_action:
                print(f"[AI_SLOWDOWN] Speed returned to NORMAL: {self.ticks_per_ai_action}")

    def _check_recipe_intention_change(self):
        """Check if AI recipe intention has changed and trigger slowdown (PlanningGame only)."""
        if not self.ai_slowdown_enabled:
            return
            
        if hasattr(self, 'planning_agent_id') and self.planning_agent_id in self.npc_policies:
            intentions = self.get_intentions(self.planning_agent_id)
            if intentions and 'recipe' in intentions:
                current_recipe = intentions['recipe']
                
                # Log current state for debugging
                if self.curr_tick % 30 == 0:  # Log every 30 ticks to avoid spam
                    print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: current_recipe={current_recipe}, last_recipe={self.last_recipe_intention}")
                
                # Si l'intention de recette a changé, déclencher le ralentissement
                if (self.last_recipe_intention is not None and 
                    current_recipe != self.last_recipe_intention and
                    current_recipe is not None):
                    print(f"[AI_SLOWDOWN] Recipe intention changed: {self.last_recipe_intention} -> {current_recipe}")
                    print(f"[AI_SLOWDOWN] Triggering slowdown for {self.slow_duration_ticks} ticks")
                    self.slow_remaining_ticks = self.slow_duration_ticks
                
                self.last_recipe_intention = current_recipe
            else:
                # Log when intentions are not available
                if self.curr_tick % 60 == 0:  # Log every 60 ticks
                    print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: No recipe intentions available - intentions={intentions}")
        else:
            # Log when planning agent is not available
            if self.curr_tick % 60 == 0:  # Log every 60 ticks
                print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: No planning agent available")
  
    def _check_asset_intention_change(self):
        """Check if AI asset/goal intention has changed and trigger slowdown (PlanningGame only)."""
        if not self.ai_slowdown_enabled or not self.ai_asset_slowdown_enabled:
            return
            
        if hasattr(self, 'planning_agent_id') and self.planning_agent_id in self.npc_policies:
            intentions = self.get_intentions(self.planning_agent_id)
            if intentions and 'goal' in intentions:
                current_asset = intentions['goal']
                
                # Log current state for debugging
                if self.curr_tick % 30 == 0:  # Log every 30 ticks to avoid spam
                    print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: current_asset={current_asset}, last_asset={self.last_asset_intention}")
                
                # Si l'intention d'asset a changé, déclencher le ralentissement
                if (self.last_asset_intention is not None and 
                    current_asset != self.last_asset_intention and
                    current_asset is not None and
                    current_asset in self.ai_asset_slowdown_intentions):
                    # Mapping des codes d'asset pour les logs
                    asset_names = {'D': 'Deliver', 'O': 'Onion', 'T': 'Tomato', 'P': 'Pot', 'S': 'Soup', 'X': 'Other', 'C': 'Chop'}
                    last_name = asset_names.get(self.last_asset_intention, self.last_asset_intention)
                    current_name = asset_names.get(current_asset, current_asset)
                    
                    print(f"[AI_SLOWDOWN] Asset intention changed: {last_name} -> {current_name}")
                    print(f"[AI_SLOWDOWN] Triggering asset slowdown for {self.asset_slow_duration_ticks} ticks")
                    self.asset_slow_remaining_ticks = self.asset_slow_duration_ticks
                elif (self.last_asset_intention is not None and 
                      current_asset != self.last_asset_intention and
                      current_asset is not None and
                      current_asset not in self.ai_asset_slowdown_intentions):
                    # Log quand l'intention change mais n'est pas dans la liste autorisée
                    asset_names = {'D': 'Deliver', 'O': 'Onion', 'T': 'Tomato', 'P': 'Pot', 'S': 'Soup', 'X': 'Other', 'C': 'Chop'}
                    last_name = asset_names.get(self.last_asset_intention, self.last_asset_intention)
                    current_name = asset_names.get(current_asset, current_asset)
                    print(f"[AI_SLOWDOWN] Asset intention changed: {last_name} -> {current_name} (no slowdown - not in enabled list)")
                
                self.last_asset_intention = current_asset
            else:
                # Log when intentions are not available
                if self.curr_tick % 60 == 0:  # Log every 60 ticks
                    print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: No asset intentions available - intentions={intentions}")
        else:
            # Log when planning agent is not available
            if self.curr_tick % 60 == 0:  # Log every 60 ticks
                print(f"[AI_SLOWDOWN_DEBUG] Tick {self.curr_tick}: No planning agent available for asset check")
                

    # ------------------------------------------------------------------
    # Triplet helpers
    # ------------------------------------------------------------------

    def _get_current_triplet_orders(self):
        """Fresh orders for the current triplet slot, always from start_all_orders."""
        if not self.order_triplets:
            return []
        idx = self.current_triplet_index % len(self.order_triplets)
        orders = []
        for i in self.order_triplets[idx]:
            if i < len(self.mdp.start_all_orders):
                orders.append(Recipe.from_dict(self.mdp.start_all_orders[i]))
        return orders

    def _advance_triplet(self):
        """Move to the next triplet and pick a new random display duration."""
        self.current_triplet_index += 1
        self.triplet_start_time = time()
        self.triplet_duration = random.uniform(self.triplet_display_min, self.triplet_display_max)
        self.state._all_orders = self._get_current_triplet_orders()

    # ------------------------------------------------------------------
    # Temporary recipe helpers
    # ------------------------------------------------------------------

    def _temporary_recipes_active(self):
        """Mutuellement exclusif avec triplet : le triplet est prioritaire."""
        return self.temporary_recipe_enabled and not self.order_triplets

    def _recipe_lifetime(self):
        """Durée de vie (secondes) d'une recette : aléatoire bornée ou exacte."""
        if self.random_temporary_recipe:
            return random.uniform(self.min_temporary_recipe, self.max_temporary_recipe)
        return self.exact_temporary_recipe

    def _pick_replacement_recipe(self):
        """Recette du pool du layout absente de la liste courante (préserve l'unicité)."""
        present = {r.ingredients for r in self.state._all_orders}
        candidates = [Recipe.from_dict(d) for d in self.mdp.start_all_orders
                      if Recipe.from_dict(d).ingredients not in present]
        return random.choice(candidates) if candidates else None

    def _update_temporary_recipes(self):
        """Expire les recettes en fin de vie et les remplace 1-pour-1."""
        now = time()
        # Purge des entrées de recettes livrées/absentes
        present = {r.ingredients for r in self.state._all_orders}
        self.recipe_expiry = {k: v for k, v in self.recipe_expiry.items() if k in present}
        # Expiration + remplacement 1-pour-1
        expired = [r for r in list(self.state._all_orders)
                   if self.recipe_expiry.get(r.ingredients, float('inf')) <= now]
        for r in expired:
            self.state._all_orders.remove(r)
            self.recipe_expiry.pop(r.ingredients, None)
            replacement = self._pick_replacement_recipe() or r  # cas dégénéré : réarme la même
            self.state._all_orders.append(replacement)
            self.recipe_expiry[replacement.ingredients] = now + self._recipe_lifetime()
        # Affecte une durée de vie aux recettes nouvelles (initial / infinite_all_order)
        for r in self.state._all_orders:
            if r.ingredients not in self.recipe_expiry:
                self.recipe_expiry[r.ingredients] = now + self._recipe_lifetime()

    # ------------------------------------------------------------------
    # infinite_all_order : flux continu de recettes, `number_shown_recipes` affichées
    # ------------------------------------------------------------------

    def _infinite_orders_active(self):
        """infinite_all_order : réapprovisionne en continu l'affichage jusqu'à
        `number_shown_recipes`. Mutuellement exclusif avec le triplet (prioritaire)."""
        return self.infinite_all_order and not self.order_triplets

    def _infinite_recipe_target(self):
        """Nombre de recettes à maintenir affichées, borné par la taille du pool du layout
        (on ne peut pas afficher plus de recettes UNIQUES que n'en contient start_all_orders)."""
        pool_size = len(self.mdp.start_all_orders)
        return max(0, min(self.number_shown_recipes, pool_size))

    def _init_infinite_recipes(self):
        """Démarre l'essai avec exactement `number_shown_recipes` recettes : un
        sous-ensemble aléatoire du pool du layout (start_all_orders)."""
        target = self._infinite_recipe_target()
        pool = [Recipe.from_dict(d) for d in self.mdp.start_all_orders]
        random.shuffle(pool)
        self.state._all_orders = pool[:target]

    def _replenish_infinite_recipes(self):
        """Complète state._all_orders jusqu'à `number_shown_recipes` en piochant (unique)
        dans le pool du layout. Les recettes ajoutées reçoivent une durée de vie si le
        système de recettes temporaires est actif."""
        target = self._infinite_recipe_target()
        pool = [Recipe.from_dict(d) for d in self.mdp.start_all_orders]
        now = time()
        while len(self.state._all_orders) < target:
            present = {r.ingredients for r in self.state._all_orders}
            candidates = [r for r in pool if r.ingredients not in present]
            if not candidates:
                break
            new_r = random.choice(candidates)
            self.state._all_orders.append(new_r)
            if self._temporary_recipes_active():
                self.recipe_expiry[new_r.ingredients] = now + self._recipe_lifetime()

    # ------------------------------------------------------------------

    def _curr_game_over(self): # Vérifie si le all_order est complété ou si la durée maximum de l'essai est dépassée
        if self.mechanic == "recipe":
            if self.order_triplets:
                # With triplets the trial is always time-bounded
                return time() - self.start_time >= self.max_time
            return len(self.state.all_orders) == 0 or time() - self.start_time >= self.max_time
        else:
            return time() - self.start_time >= self.max_time
    
    def needs_reset(self):
        """
        Override needs_reset to handle the case where all_orders is empty.
        When all orders are completed, the game should reset regardless of whether it's the last trial.
        """
        # Mode "un essai par session" : aucun reset intra-session. L'essai
        # courant terminé fait passer le jeu en DONE (cf. is_finished).
        if getattr(self, 'single_trial', False):
            return False

        game_over = self._curr_game_over()
        if not game_over:
            return False

        # Si la partie est terminée à cause des commandes vides, on reset même si c'est le dernier essai
        if self.mechanic == "recipe" and len(self.state.all_orders) == 0:
            return True

        # Si la partie est terminée par le temps ET qu'il reste des essais, on reset
        # Le jeu ne se termine que si c'est le dernier essai ET qu'il est terminé
        return self.curr_trial_in_game < len(self.layouts) - 1

    def is_finished(self):
        # Mode "un essai par session" : la partie se termine dès que l'essai
        # courant est terminé (temps écoulé ou commandes complétées), quel que
        # soit son rang dans le bloc.
        if getattr(self, 'single_trial', False):
            return self._curr_game_over()
        return super().is_finished()

    def is_last_trial_in_bloc(self):
        """
        Détermine si c'est le dernier essai du bloc actuel.
        """
        return self.curr_trial_in_game >= len(self.layouts) - 1
    
    def should_show_post_trial_questionnaire(self):
        """
        Détermine si on doit afficher le questionnaire post-trial.
        Le questionnaire post-trial doit être affiché après chaque essai,
        sauf après le dernier essai d'un bloc (qui déclenche le questionnaire post-bloc).
        """
        return (self._curr_game_over() and 
                not self.is_last_trial_in_bloc() and 
                self.config.get("questionnaire_post_trial", "") != "")
    
    def game_timer(self):
        return time() - self.start_time

    def set_trial_id_error(self):
        self.trial_id = self.participant_uid + '_' + \
            str(self.step) + 'ERROR' + self.curr_layout[-1]

    def activate(self):
        """
        En plus de vérifier le passage à l'essai suivant,
        Cette méthode permet de réinitialiser les différentes métriques des résultats entre chaque essai
        Resets trial ID at start of new "game"
        """
        self.human_action_count = 0
        self.agent_action_count = 0
        self.human_interact_count = 0
        self.agent_interact_count = 0
        self.human_counter_share = 0
        self.infos = []
        
        # Trigger automatic slowdown at trial start if enabled
        # Note: curr_trial_in_game will be incremented by super().activate(), so we check current value
        if self.ai_slowdown_enabled and hasattr(self, 'config'):
            trial_start_slowdown = self.config.get("ai_trial_start_slowdown", False)
            trial_start_duration = self.config.get("ai_trial_start_duration", 50)
            trial_start_first_only = self.config.get("ai_trial_start_first_only", False)
            
            # Check if we should trigger slowdown
            should_slowdown = trial_start_slowdown
            if trial_start_first_only:
                # Premier essai du bloc. En mode single_trial, curr_trial_in_game
                # vaut -1 à chaque session : on s'appuie sur le flag explicite
                # is_first_trial_of_block (sinon comportement historique).
                if getattr(self, 'single_trial', False):
                    is_first = self.is_first_trial_of_block
                else:
                    is_first = (self.curr_trial_in_game == -1)
                should_slowdown = should_slowdown and is_first

            if should_slowdown:
                self.trial_start_slow_remaining_ticks = trial_start_duration
                print(f"[AI_SLOWDOWN] Trial start slowdown triggered for {trial_start_duration} ticks at speed {self.trial_start_ticks_per_ai_action}")
                if trial_start_first_only:
                    print(f"[AI_SLOWDOWN] First trial of block {self.step} - extended orientation time")
        
        super().activate()

        # Reset triplet state for this trial's layout (super().activate() loads new mdp)
        self.order_triplets = getattr(self.mdp, 'order_triplets', None) if self.triplet_enabled else None
        if self.order_triplets:
            self.orders_served = 0
            self.current_triplet_index = 0
            self.triplet_start_time = None
            self.triplet_duration = random.uniform(self.triplet_display_min, self.triplet_display_max)
            # Apply first triplet immediately so to_json() sends the correct subset
            self.state._all_orders = self._get_current_triplet_orders()

        # infinite_all_order : démarre l'essai avec exactement number_shown_recipes recettes
        # (sous-ensemble du pool). À faire AVANT l'affectation des durées de vie ci-dessous.
        if self._infinite_orders_active():
            self._init_infinite_recipes()

        # Réinitialise les durées de vie des recettes temporaires pour ce nouvel essai
        self.recipe_expiry = {}
        if self._temporary_recipes_active():
            now = time()
            for r in self.state._all_orders:
                self.recipe_expiry[r.ingredients] = now + self._recipe_lifetime()

        self.trial_id = self.participant_uid + '_' + \
            str(self.step) + "_" + str(self.curr_trial_in_game)

    def deactivate(self):
        try:
            self.data = self.get_data()
        except IndexError:
            pass
        super(PlanningGame, self).deactivate()

    def apply_actions(self):
        """
        Applies pending actions then logs transition data
        """
        # Check for recipe intention changes and update AI speed (slowdown system)
        self._check_recipe_intention_change()
        self._check_asset_intention_change()
        self._update_ai_speed()

        # Triplet system: restrict state.all_orders to current triplet before each tick
        before_triplet_count = None
        if self.order_triplets:
            if self.triplet_start_time is None:
                self.triplet_start_time = time()
            # Rotate triplet when timer expires
            if time() - self.triplet_start_time >= self.triplet_duration:
                self._advance_triplet()
            # Ensure only current triplet orders are visible / scoreable
            self.state._all_orders = self._get_current_triplet_orders()
            before_triplet_count = len(self.state._all_orders)

        # Apply MDP logic
        prev_state, joint_action, info = super(
            PlanningGame, self).apply_actions()
        self.infos.append(info['event_infos'])

        # Triplet system: if an order was served, advance triplet
        if self.order_triplets and before_triplet_count is not None:
            if len(self.state._all_orders) < before_triplet_count:
                self.orders_served += 1
                self._advance_triplet()

        # Temporary recipe system : expirer/remplacer les recettes en fin de vie
        if self._temporary_recipes_active():
            self._update_temporary_recipes()

        # infinite_all_order : réapprovisionne jusqu'à number_shown_recipes après
        # chaque livraison/expiration, pour que l'affichage ne s'épuise jamais.
        if self._infinite_orders_active():
            self._replenish_infinite_recipes()

        if joint_action[1] != (0, 0):
            self.human_action_count += 1
            if joint_action[1] == 'interact':
                self.human_interact_count += 1
        if joint_action[0] != (0, 0):
            self.agent_action_count += 1
            if joint_action[0] == 'interact':
                self.agent_interact_count += 1

        # Log data to send to psiturk client
        curr_reward = sum(info['sparse_reward_by_agent'])
        if self.order_triplets:
            ach_orders = self.orders_served
        else:
            ach_orders = len(self.mdp.start_all_orders) - len(self.state.all_orders)
        transition = {
            "joint_action": json.dumps(joint_action),
            "reward": curr_reward,
            "time_left": max(self.max_time - (time() - self.start_time), 0),
            "score": self.score,
            "time_elapsed": time() - self.start_time,
            "cur_gameloop": self.curr_tick,
            "layout": json.dumps(self.mdp.terrain_mtx),
            "layout_name": self.curr_layout,
            "trial_id": self.trial_id,
            "participant_uid": self.participant_uid,
            "player_0_id": self.players[0],
            "player_1_id": self.players[1],
            "player_0_is_human": self.players[0] in self.human_players,
            "player_1_is_human": self.players[1] in self.human_players,
            "all_orders": self.state.all_orders,
            "achieved_orders_len": ach_orders,
            "human_action_count": self.human_action_count,
            "agent_action_count": self.agent_action_count,
            "agent_stuck_loop": self.npc_policies[self.planning_agent_id].stuck_frames,
            "hl_switch": self.npc_policies[self.planning_agent_id].hl_objective_switch,

        }
        transition.update(prev_state.to_dict())
        self.trajectory.append(transition)

    def get_policy(self, npc_id,  idx):
        #self.mdp = OvercookedGridworld.from_layout_name(self.layouts[-1], self.layouts_dir, **self.mdp_params)
        if "Lazy" in self.planning_agent_id:
            agent = LazyAgent()
        elif "Greedy" in self.planning_agent_id:
            agent = GreedyAgent()
        elif "Rational" in self.planning_agent_id:
            agent = RationalAgent()
        else:
            agent = RandomAgent()
        agent.set_agent_index(idx)
        return agent

    def get_intentions(self, policy_id):
        #queue = self.npc_state_queues[policy_id]
        policy = self.npc_policies[policy_id]
        return policy.intentions

    def get_motion_goal(self, policy_id):
        policy = self.npc_policies[policy_id]
        if policy.motion_goal:
            return policy.chosen_goal[0]

    def set_player_intention(self, section, value):
        """[COMM JOUEUR→IA] Applique une consigne du joueur humain à l'agent planificateur.

        - section 'distal'   : value = liste d'ingrédients de la recette à viser (ou None pour relâcher)
        - section 'proximal' : value = code de sous-tâche 'ingredient'|'chop'|'pot'|'serve' (ou None)

        L'écriture d'attribut est atomique (GIL) ; l'agent la lit dans son thread de décision
        (npc_policy_consumer) au prochain appel à action()."""
        # La communication bidirectionnelle doit être activée dans la config, sinon on ignore.
        if not (getattr(self, 'config', None) or {}).get('bidirectionnelle'):
            return
        policy = self.npc_policies.get(getattr(self, 'planning_agent_id', None))
        if policy is None:
            return
        if section == 'distal':
            policy.forced_recipe = value if value else None
        elif section == 'proximal':
            policy.forced_subtask = value if value else None

    def get_state(self):
        state_dict = {}
        state_dict['potential'] = self.phi if self.show_potential else None
        state_dict['state'] = self.state.to_dict()
        state_dict['score'] = self.score
        
        # Debug timing calculation
        current_time = time()
        elapsed_time = current_time - self.start_time
        calculated_time_left = self.max_time - elapsed_time
        time_left = max(calculated_time_left, 0)
        
        # Log timing info for debugging
        if hasattr(self, 'debug_timer_count'):
            self.debug_timer_count += 1
        else:
            self.debug_timer_count = 1
            
        if self.debug_timer_count % 60 == 0:  # Log every 60 calls to avoid spam
            print(f"[TIMER_DEBUG] Trial {self.curr_trial_in_game+1}: max_time={self.max_time}, elapsed={elapsed_time:.2f}, time_left={time_left}")
        
        state_dict['time_left'] = time_left
        # Durée écoulée depuis le début de l'essai en cours (option show_time_in_trial)
        state_dict['time_elapsed'] = max(elapsed_time, 0)
        # Triplet timer
        if self.order_triplets and self.triplet_start_time is not None:
            triplet_elapsed = time() - self.triplet_start_time
            state_dict['triplet_time_left'] = max(0, round(self.triplet_duration - triplet_elapsed))
            # Full triplet for display: always 3 recipes from layout, regardless of served status
            idx = self.current_triplet_index % len(self.order_triplets)
            state_dict['triplet_display_orders'] = [
                self.mdp.start_all_orders[i]
                for i in self.order_triplets[idx]
                if i < len(self.mdp.start_all_orders)
            ]
        else:
            state_dict['triplet_time_left'] = None
            state_dict['triplet_display_orders'] = None
        # Temps restant par recette (aligné sur state.all_orders trié)
        if self._temporary_recipes_active():
            now = time()
            state_dict['recipe_time_left'] = [
                max(0, round(self.recipe_expiry.get(r.ingredients, 0) - now))
                for r in self.state.all_orders
            ]
        else:
            state_dict['recipe_time_left'] = None
        state_dict['intentions'] = self.get_intentions(self.planning_agent_id)
        state_dict['state']['players'][int(
            self.planning_agent_id[-1])]['motion_goal'] = self.get_motion_goal(self.planning_agent_id)
        state_dict['state']['players'][int(
            self.planning_agent_id[-1])]['intentions'] = self.get_intentions(self.planning_agent_id)
        # [ASYMMETRIC DISPENSERS] Le client humain (joueur 0) ne voit que les items des dispensers 'A'
        # TODO: réactiver ce filtre après les tests visuels (supprimer le commentaire ci-dessous)
        # if self.mdp.has_asymmetric_dispensers():
        #     b_positions = {tuple(p) for p in self.mdp.get_player1_dispenser_locations()}
        #     state_dict['state']['dispenser_items'] = [
        #         entry for entry in state_dict['state'].get('dispenser_items', [])
        #         if (entry[0], entry[1]) not in b_positions
        #     ]
        state_dict['show_post_trial_questionnaire'] = self.should_show_post_trial_questionnaire()
        state_dict['is_last_trial_in_bloc'] = self.is_last_trial_in_bloc()
        state_dict['curr_trial_in_game'] = self.curr_trial_in_game
        state_dict['total_trials_in_bloc'] = len(self.layouts)
        
#        print ("valeur de la variable state_dict['intentions']['recipe'] : ", state_dict['intentions']['recipe'])
#        print ("valeur de la variable state_dict['intentions']['goal'] : ", state_dict['intentions']['goal'])
#        print ("valeur de la variable state_dict['intentions']['agent_name'] : ", state_dict['intentions']['agent_name'])
#        print ("valeur de la variable state_dict['intentions'] : ", state_dict['intentions'])
        return state_dict

    def get_data(self):
        """
        Returns and then clears the accumulated trajectory
        """
        info_sum = deepcopy(self.infos[-1])
        for key, value in info_sum.items():
            info_sum[key] = [0,0]
        for info in self.infos:
            for key, value in info.items():
                if value[0]:
                    info_sum[key][0] +=1
                if value[1]:
                    info_sum[key][1] +=1
        data = {"uid": self.participant_uid, "trial_id": self.trial_id, "layout": self.curr_layout, "time_elapsed": self.trajectory[-1]["time_elapsed"],
                "mechanic": self.mechanic,
                "timestamp": gmtime(), "date": asctime(gmtime()), "step": self.step,
                "condition": self.curr_condition, 
                "curr_trial_in_game": self.curr_trial_in_game, 
                "score": self.trajectory[-1]["score"],
                "info_sum" : info_sum,
                "human_action_count": self.trajectory[-1]["human_action_count"],
                "agent_action_count": self.trajectory[-1]["agent_action_count"],
                "agent_interact_count": self.agent_interact_count,
                "human_interact_count": self.human_interact_count,
                "agent_stuck_loop": self.trajectory[-1]["agent_stuck_loop"],
                "hl_switch": self.trajectory[-1]["hl_switch"],
                "achieved_orders_len": self.trajectory[-1]["achieved_orders_len"],
                "bloc": self.step,
                "trajectory": self.trajectory,
                "config" : self.config}

        self.trajectory = []
        return data


# class PlanningGame(OvercookedGame):
#
#     def __init__(self, layouts=["cramped_room"], **kwargs):
#         super(PlanningGame, self).__init__(layouts=layouts)
#         super().__init__(layouts, **kwargs)
#         self.mlam = MediumLevelActionManager.from_pickle_or_compute(self.mdp, NO_COUNTERS_PARAMS)
#
#     def get_policy(self, *args, **kwargs):
#         return GreedyHumanModel(self.mlam)


class OvercookedPsiturk(OvercookedGame):
    """
    Wrapper on OvercookedGame that handles additional housekeeping for Psiturk experiments

    Instance Variables:
        - trajectory (list(dict)): list of state-action pairs in current trajectory
        - psiturk_uid (string): Unique id for each psiturk game instance (provided by Psiturk backend)
            Note, this is not the user id -- two users in the same game will have the same psiturk_uid
        - trial_id (string): Unique identifier for each psiturk trial, updated on each call to reset
            Note, one OvercookedPsiturk game handles multiple layouts. This is how we differentiate

    Methods:
        get_data: Returns the accumulated trajectory data and clears the self.trajectory instance variable

    """

    def __init__(self, *args, psiturk_uid='-1', **kwargs):
        super(OvercookedPsiturk, self).__init__(
            *args, showPotential=False, **kwargs)
        self.psiturk_uid = psiturk_uid
        self.trajectory = []

    def activate(self):
        """
        Resets trial ID at start of new "game"
        """
        super(OvercookedPsiturk, self).activate()
        self.trial_id = self.psiturk_uid + str(self.start_time)

    def apply_actions(self):
        """
        Applies pending actions then logs transition data
        """
        # Apply MDP logic
        prev_state, joint_action, info = super(
            OvercookedPsiturk, self).apply_actions()

        # Log data to send to psiturk client
        curr_reward = sum(info['sparse_reward_by_agent'])
        transition = {
            "state": json.dumps(prev_state.to_dict()),
            "joint_action": json.dumps(joint_action),
            "reward": curr_reward,
            "time_left": max(self.max_time - (time() - self.start_time), 0),
            "score": self.score,
            "time_elapsed": time() - self.start_time,
            "cur_gameloop": self.curr_tick,
            "layout": json.dumps(self.mdp.terrain_mtx),
            "layout_name": self.curr_layout,
            "trial_id": self.trial_id,
            "player_0_id": self.players[0],
            "player_1_id": self.players[1],
            "player_0_is_human": self.players[0] in self.human_players,
            "player_1_is_human": self.players[1] in self.human_players
        }

        self.trajectory.append(transition)

    def get_data(self):
        """
        Returns and then clears the accumulated trajectory
        """
        data = {"uid": self.psiturk_uid + "_" +
                str(time()), "trajectory": self.trajectory}
        self.trajectory = []
        return data


class OvercookedTutorial(OvercookedGame):
    """
    Wrapper on OvercookedGame that includes additional data for tutorial mechanics, most notably the introduction of tutorial "phases"

    Instance Variables:
        - curr_phase (int): Indicates what tutorial phase we are currently on
        - phase_two_score (float): The exact sparse reward the user must obtain to advance past phase 2
    """

    def __init__(self, layouts=["tutorial_0", "tutorial_1", "tutorial_2"], mdp_params={}, playerZero='human', playerOne='AI', phaseTwoScore=15,
                 **kwargs):
        super(OvercookedTutorial, self).__init__(layouts=layouts, mdp_params=mdp_params, playerZero=playerZero,
                                                 playerOne=playerOne, showPotential=False, **kwargs)
        self.phase_two_score = phaseTwoScore
        self.phase_two_finished = False
        self.config = kwargs.get("config")
        self.max_time = 0
        self.max_players = 2
        self.ticks_per_ai_action = 5  # Fixed AI speed for tutorial
        self.curr_phase = 0
        # [TUTORIEL] Le layout de chaque phase est choisi via curr_trial_in_game, incrémenté
        # dans OvercookedGame.activate(). Pour rester aligné avec curr_phase (incrémenté dans
        # reset()), curr_trial_in_game DOIT partir de -1 : le 1er activate() le porte à 0 = phase 0.
        # Le handler 'join' transmet curr_trial_in_game = current_user.trial - 1 (utile pour
        # l'expérience, mais dénué de sens ici). Si trial != 0, les deux compteurs se décalent et
        # le reset de fin de phase 2 tente layouts[3] -> IndexError côté serveur (invisible dans la
        # console navigateur), 'reset_game' n'est jamais émis et le tutoriel reste bloqué en phase 2.
        # On force donc -1 : le tutoriel rejoue toujours ses 3 layouts fixes depuis le début.
        self.curr_trial_in_game = -1
        self.curr_layout = self.layouts[0]
        self.participant_uid = kwargs.get('player_uid', '-1')
        self.trial_id = "tutorial" + str(self.curr_phase)
        self.data = []
        self.trajectory = []

    @property
    def reset_timeout(self):
        return 1

    def needs_reset(self):
        reset_needed = False
        if self.curr_phase == 0:
            reset_needed = self.score > 0
        elif self.curr_phase == 1:
            reset_needed = self.score > 0
        elif self.curr_phase == 2:
            # Étape 3 validée uniquement quand les 3 recettes affichées ont été livrées
            # (phase_two_finished, cf. apply_actions). Pas de repli sur score > 0 : une seule
            # livraison ne doit plus terminer l'étape.
            reset_needed = self.phase_two_finished
        
        if reset_needed:
            print(f"[TUTORIAL] Phase {self.curr_phase} completed, needs_reset = True, score = {self.score}, phase_two_finished = {self.phase_two_finished}")
        
        return reset_needed
    
    def is_finished(self):
        """
        Tutorial est terminé quand on a terminé toutes les phases (curr_phase >= 3)
        """
        finished = self.curr_phase >= 3
        if finished:
            print(f"[TUTORIAL] Tutorial is finished! curr_phase = {self.curr_phase}")
        return finished


    def reset(self):
        print(f"[TUTORIAL] Resetting phase {self.curr_phase} -> {self.curr_phase + 1}")
        self.curr_phase += 1
        self.data = self.get_data()
        self.score = 0  # Remettre le score à zéro à chaque phase
        self.phase_two_finished = False  # Réinitialiser la validation de la phase 2
        super(OvercookedTutorial, self).reset()

    def _phase_mdp_config(self, phase, base):
        """[TUTORIEL] Paramètres MDP propres à chaque phase pédagogique.

        Le tutoriel ne peut pas hériter de la config expérimentale (config_test) pour le MDP :
        celle-ci force globalement cutting_enabled / Human_forced_cutting / recipes_requiring_chopping,
        ce qui rendrait la phase 0 (recette simple, SANS découpe) injouable et bloquerait la pose
        en marmite. On reconstruit donc, par phase, uniquement les overrides MDP voulus
        (cf. CONFIG_DRIVEN_MDP_PARAMS) en gardant l'économie (valeurs/temps des ingrédients) identique
        à l'expérience pour la cohérence. Les ingrédients proviennent de distributeurs réguliers
        (oignon 'O', tomate 'T') : il n'y a plus aucun distributeur aléatoire dans le tutoriel.
        """
        base = base or {}
        cfg = {
            "onion_value":  base.get("onion_value", 3),
            "tomato_value": base.get("tomato_value", 2),
            "onion_time":   base.get("onion_time", 9),
            "tomato_time":  base.get("tomato_time", 6),
        }
        if phase == 0:
            # Leçon 1 : découvrir les recettes et les distributeurs oignon/tomate. Pas de découpe
            # (cutting_enabled reste False).
            pass
        else:
            # Leçons 2 et 3 : découpe activée et imposée. À l'étape 3 (phase 2) le partenaire IA
            # cuisine avec le participant : on impose donc la découpe à l'humain ET à l'IA, comme
            # dans l'expérience. La liste couvre les recettes de l'étape 2 ([onion], [tomato]) et
            # de l'étape 3 ([onion], [onion,tomato], [onion,tomato,tomato]).
            cfg["cutting_enabled"] = True
            cfg["chop_time"] = base.get("chop_time", {"onion": 3, "tomato": 2})
            cfg["recipes_requiring_chopping"] = base.get(
                "recipes_requiring_chopping",
                [["onion"], ["tomato"], ["onion", "tomato"],
                 ["onion", "tomato", "tomato"]])
            cfg["Human_forced_cutting"] = True
            cfg["AI_forced_cutting"] = True
        return cfg

    def activate(self):
        self.trial_id = "tutorial" + str(self.curr_phase)
        # [TUTORIEL] Le partenaire IA ne cuisine qu'à l'étape 3 (phase 2) ; il reste immobile
        # pendant l'apprentissage solo (phases 0 et 1). On (dé)active AVANT super().activate() car
        # celui-ci démarre les threads de décision de l'agent.
        for pol in self.npc_policies.values():
            if isinstance(pol, TutorialCoopAI):
                pol.tutorial_active = (self.curr_phase == 2)
        # [TUTORIEL] On permute self.config par les overrides MDP de la phase courante UNIQUEMENT
        # le temps de la construction du MDP dans super().activate() (qui lit self.config en
        # mdp_overrides_from_config + Human_forced_cutting), puis on restaure la vraie config
        # (utilisée par get_data pour le logging).
        real_config = self.config
        self.config = self._phase_mdp_config(self.curr_phase, real_config)
        try:
            super(OvercookedTutorial, self).activate()
        finally:
            self.config = real_config

    def deactivate(self):
        super(OvercookedTutorial, self).deactivate()

    def get_policy(self, npc_id=None, idx=1):
        # [TUTORIEL] Partenaire IA : GreedyAgent réel (comme l'expérience), mais actif seulement
        # à l'étape 3 (phase 2). Le mlam de la phase (géométrie du layout) est injecté par
        # OvercookedGame.activate() car TutorialCoopAI est un PlanningAgent. idx=1 : le partenaire
        # est le joueur 2 ('2' dans les layouts) ; l'humain est le joueur 1 (index 0).
        agent = TutorialCoopAI()
        agent.set_agent_index(idx)
        return agent

    def apply_actions(self):
        """
        Apply regular MDP logic with retroactive score adjustment tutorial purposes
        """
        prev_state, joint_action, info = super(
            OvercookedTutorial, self).apply_actions()

        human_reward, ai_reward = info['sparse_reward_by_agent']

        # We only want to keep track of the human's score in the tutorial
        self.score -= ai_reward

        # [TUTORIEL ÉTAPE 3] La phase 2 n'est validée que lorsque l'équipe (participant + IA) a livré
        # les 3 recettes affichées. Chaque livraison correcte retire la recette de all_orders
        # (mdp.resolve_interacts -> clear_order), donc all_orders vide == les 3 commandes réalisées.
        if self.curr_phase == 2:
            if len(self.state.all_orders) == 0:
                if not self.phase_two_finished:
                    print("[TUTORIAL] Phase 2 completed! All 3 orders delivered, setting phase_two_finished = True")
                self.phase_two_finished = True
        transition = {
            "joint_action": json.dumps(joint_action),
            "time_left": max(self.max_time - (time() - self.start_time), 0),
            "score": self.score,
            "time_elapsed": time() - self.start_time,
            "cur_gameloop": self.curr_tick,
            "layout": json.dumps(self.mdp.terrain_mtx),
            "layout_name": self.curr_layout,
            "trial_id": self.trial_id,
            "participant_uid": self.participant_uid,
            "player_0_id": self.players[0],
            "player_1_id": self.players[1],
            "player_0_is_human": self.players[0] in self.human_players,
            "player_1_is_human": self.players[1] in self.human_players,
            "all_orders": self.state.all_orders
        }
        transition.update(prev_state.to_dict())
        self.trajectory.append(transition)

    def get_data(self):
        """
        Returns and then clears the accumulated trajectory
        """
        data = {"uid": self.participant_uid, "trial_id": self.trial_id,
                "timestamp": gmtime(), "date": asctime(gmtime()),
                "score": self.trajectory[-1]["score"],
                "trajectory": self.trajectory,
                "config" : self.config,
                "show_post_trial_questionnaire": self.should_show_post_trial_questionnaire() if hasattr(self, 'should_show_post_trial_questionnaire') else False,
                "is_last_trial_in_bloc": self.is_last_trial_in_bloc() if hasattr(self, 'is_last_trial_in_bloc') else False,
                "curr_trial_in_game": self.curr_trial_in_game,
                "total_trials_in_bloc": self.total_trials_in_bloc if hasattr(self, 'total_trials_in_bloc') else 1}
        self.trajectory = []
        return data


class DummyOvercookedGame(OvercookedGame):
    """
    Class that hardcodes the AI to be random. Used for debugging
    """

    def __init__(self, layouts=["cramped_room"], **kwargs):
        super(DummyOvercookedGame, self).__init__(layouts, **kwargs)

    def get_policy(self, *args, **kwargs):
        return DummyAI()


class DummyAI():
    """
    Randomly samples actions. Used for debugging
    """

    def action(self, state):
        [action] = random.sample(
            [Action.STAY, Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST, Action.INTERACT], 1)
        return action, None

    def reset(self):
        pass

    def set_mdp(self, mdp):
        pass


class DummyComputeAI(DummyAI):
    """
    Performs simulated compute before randomly sampling actions. Used for debugging
    """

    def __init__(self, compute_unit_iters=1e5):
        """
        compute_unit_iters (int): Number of for loop cycles in one "unit" of compute. Number of 
                                    units performed each time is randomly sampled
        """
        super(DummyComputeAI, self).__init__()
        self.compute_unit_iters = int(compute_unit_iters)

    def action(self, state):
        # Randomly sample amount of time to busy wait
        iters = random.randint(1, 10) * self.compute_unit_iters

        # Actually compute something (can't sleep) to avoid scheduling optimizations
        val = 0
        for i in range(iters):
            # Avoid branch prediction optimizations
            if i % 2 == 0:
                val += 1
            else:
                val += 2

        # Return randomly sampled action
        return super(DummyComputeAI, self).action(state)


class StayAI():
    """
    Always returns "stay" action. Used for debugging
    """

    def action(self, state):
        return Action.STAY, None

    def reset(self):
        pass


class TutorialAI():
    COOK_SOUP_LOOP = [
        # Grab first onion
        Direction.WEST,
        Direction.WEST,
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Grab second onion
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Grab third onion
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Cook soup
        Action.INTERACT,

        # Grab plate
        Direction.EAST,
        Direction.SOUTH,
        Action.INTERACT,
        Direction.WEST,
        Direction.NORTH,

        # Deliver soup
        Action.INTERACT,
        Direction.EAST,
        Direction.EAST,
        Direction.EAST,
        Action.INTERACT,
        Direction.WEST
    ]

    COOK_SOUP_COOP_LOOP = [
        # Grab first onion
        Direction.WEST,
        Direction.WEST,
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.SOUTH,
        Action.INTERACT,

        # Move to start so this loops
        Direction.EAST,
        Direction.EAST,

        # Pause to make cooperation more real time
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY
    ]

    def __init__(self, *args, **kwargs):
        self.curr_phase = -1
        self.curr_tick = -1

    def action(self, state):
        # [TUTORIEL SOLO] Le partenaire reste inactif dans toutes les phases : le participant
        # apprend seul les mécaniques (recette/random dispenser, découpe, poubelle). Les anciennes
        # boucles COOK_SOUP_LOOP / COOK_SOUP_COOP_LOOP étaient codées pour l'ancienne grille 7×5
        # et ne sont plus utilisées avec les nouvelles grilles de tutoriel.
        self.curr_tick += 1
        return Action.STAY, None

    def set_mdp(self, mdp):
        pass

    def reset(self):
        self.curr_tick = -1
        self.curr_phase += 1


class TutorialCoopAI(GreedyAgent):
    """[TUTORIEL] Partenaire IA du tutoriel de familiarisation.

    - Reste immobile (Action.STAY) pendant les étapes d'apprentissage solo (phases 0 et 1) : le
      participant y apprend seul les mécaniques (recette, découpe).
    - À l'étape 3 (phase 2), coopère réellement comme l'agent de l'expérience : c'est un
      GreedyAgent (planificateur) qui va chercher les ingrédients, les découpe, remplit la marmite,
      dresse l'assiette et sert. Le mlam de la phase (géométrie du layout) est injecté par
      OvercookedGame.activate() car TutorialCoopAI est un PlanningAgent.

    L'attribut `tutorial_active` est (dé)positionné par OvercookedTutorial.activate() selon la phase.
    """

    def __init__(self, *args, **kwargs):
        super(TutorialCoopAI, self).__init__(*args, **kwargs)
        # Activé uniquement à l'étape 3 (phase 2) par OvercookedTutorial.activate().
        self.tutorial_active = False

    def action(self, state):
        if not self.tutorial_active:
            return Action.STAY, None
        return super(TutorialCoopAI, self).action(state)
