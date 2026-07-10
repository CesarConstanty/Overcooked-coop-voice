from copy import deepcopy
import itertools
import math
import numpy as np
from operator import attrgetter
from collections import defaultdict, Counter
from overcooked_ai_py.mdp.actions import Action
from overcooked_ai_py.planning.planners import MediumLevelActionManager, MotionPlanner, NO_COUNTERS_PARAMS, COUNTERS_MLG_PARAMS
from overcooked_ai_py.mdp.overcooked_mdp import Recipe

class Agent(object):

    def __init__(self):
        self.motion_goal = None
        self.chosen_goal = None
        self.hl_objective_switch = 0
        self.stuck_frames = 0
        self.reset()

    def action(self, state):
        """
        Should return an action, and an action info dictionary.
        If collectingaction trajectories of the agent with OvercookedEnv, the action
        info data will be included in the trajectory data under `ep_infos`.

        This allows agents to optionally store useful information about them
        in the trajectory for further analysis.
        """
        return NotImplementedError()

    def actions(self, states, agent_indices):
        """
        A multi-state version of the action method. This enables for parallized
        implementations that can potentially give speedups in action prediction. 

        Args:
            states (list): list of OvercookedStates for which we want actions for
            agent_indices (list): list to inform which agent we are requesting the action for in each state

        Returns:
            [(action, action_info), (action, action_info), ...]: the actions and action infos for each state-agent_index pair
        """
        return NotImplementedError()

    @staticmethod
    def a_probs_from_action(action):
        action_idx = Action.ACTION_TO_INDEX[action]
        return np.eye(Action.NUM_ACTIONS)[action_idx]

    @staticmethod
    def check_action_probs(action_probs, tolerance=1e-4):
        """Check that action probabilities sum to ≈ 1.0"""
        probs_sum = sum(action_probs)
        assert math.isclose(probs_sum, 1.0, rel_tol=tolerance), "Action probabilities {} should sum up to approximately 1 but sum up to {}".format(
            list(action_probs), probs_sum)

    def set_agent_index(self, agent_index):
        self.agent_index = agent_index

    def set_mdp(self, mdp):
        self.mdp = mdp

    def reset(self):
        """
        One should always reset agents in between trajectory rollouts, as resetting
        usually clears history or other trajectory-specific attributes.
        """
        self.agent_index = None
        self.mdp = None


class AgentGroup(object):
    """
    AgentGroup is a group of N agents used to sample 
    joint actions in the context of an OvercookedEnv instance.
    """

    def __init__(self, *agents, allow_duplicate_agents=False):
        self.agents = agents
        self.n = len(self.agents)
        self.reset()

        if not all(a0 is not a1 for a0, a1 in itertools.combinations(agents, 2)):
            assert allow_duplicate_agents, "All agents should be separate instances, unless allow_duplicate_agents is set to true"

    def joint_action(self, state):
        actions_and_probs_n = tuple(a.action(state) for a in self.agents)
        return actions_and_probs_n

    def set_mdp(self, mdp):
        for a in self.agents:
            a.set_mdp(mdp)

    def reset(self):
        """
        When resetting an agent group, we know that the agent indices will remain the same,
        but we have no guarantee about the mdp, that must be set again separately.
        """
        for i, agent in enumerate(self.agents):
            agent.reset()
            agent.set_agent_index(i)


class AgentPair(AgentGroup):
    """
    AgentPair is the N=2 case of AgentGroup. Unlike AgentGroup,
    it supports having both agents being the same instance of Agent.

    NOTE: Allowing duplicate agents (using the same instance of an agent
    for both fields can lead to problems if the agents have state / history)
    """

    def __init__(self, *agents, allow_duplicate_agents=False):
        super().__init__(*agents, allow_duplicate_agents=allow_duplicate_agents)
        assert self.n == 2
        self.a0, self.a1 = self.agents

    def joint_action(self, state):
        if self.a0 is self.a1:
            # When using the same instance of an agent for self-play,
            # reset agent index at each turn to prevent overwriting it
            self.a0.set_agent_index(0)
            action_and_infos_0 = self.a0.action(state)
            self.a1.set_agent_index(1)
            action_and_infos_1 = self.a1.action(state)
            joint_action_and_infos = (action_and_infos_0, action_and_infos_1)
            return joint_action_and_infos
        else:
            return super().joint_action(state)


class NNPolicy(object):
    """
    This is a common format for NN-based policies. Once one has wrangled the intended trained neural net
    to this format, one can then easily create an Agent with the AgentFromPolicy class.
    """

    def __init__(self):
        pass

    def multi_state_policy(self, states, agent_indices):
        """
        A function that takes in multiple OvercookedState instances and their respective agent indices and returns action probabilities.
        """
        raise NotImplementedError()

    def multi_obs_policy(self, states):
        """
        A function that takes in multiple preprocessed OvercookedState instatences and returns action probabilities.
        """
        raise NotImplementedError()


class AgentFromPolicy(Agent):
    """
    This is a useful Agent class backbone from which to subclass from NN-based agents.
    """

    def __init__(self, policy):
        """
        Takes as input an NN Policy instance
        """
        self.policy = policy
        self.reset()

    def action(self, state):
        return self.actions([state], [self.agent_index])[0]

    def actions(self, states, agent_indices):
        action_probs_n = self.policy.multi_state_policy(states, agent_indices)
        actions_and_infos_n = []
        for action_probs in action_probs_n:
            action = Action.sample(action_probs)
            actions_and_infos_n.append(
                (action, {"action_probs": action_probs}))
        return actions_and_infos_n

    def set_mdp(self, mdp):
        super().set_mdp(mdp)
        self.policy.mdp = mdp

    def reset(self):
        super(AgentFromPolicy, self).reset()
        self.policy.mdp = None


class RandomAgent(Agent):
    """
    An agent that randomly picks motion actions.
    NOTE: Does not perform interact actions, unless specified
    """

    def __init__(self, sim_threads=None, all_actions=False, custom_wait_prob=None):
        self.sim_threads = sim_threads
        self.all_actions = all_actions
        self.custom_wait_prob = custom_wait_prob
        self.motion_goal = None
        self.stuck_frames = None
        self.hl_objective_switch = None
        self.intentions = None

    def action(self, state):
        action_probs = np.zeros(Action.NUM_ACTIONS)
        legal_actions = list(Action.MOTION_ACTIONS)
        if self.all_actions:
            legal_actions = Action.ALL_ACTIONS
        legal_actions_indices = np.array(
            [Action.ACTION_TO_INDEX[motion_a] for motion_a in legal_actions])
        action_probs[legal_actions_indices] = 1 / len(legal_actions_indices)

        if self.custom_wait_prob is not None:
            stay = Action.STAY
            if np.random.random() < self.custom_wait_prob:
                return stay, {"action_probs": Agent.a_probs_from_action(stay)}
            else:
                action_probs = Action.remove_indices_and_renormalize(
                    action_probs, [Action.ACTION_TO_INDEX[stay]])

        return Action.sample(action_probs), {"action_probs": action_probs}

    def actions(self, states, agent_indices):
        return [self.action(state) for state in states]

    def direct_action(self, obs):
        return [np.random.randint(4) for _ in range(self.sim_threads)]


class StayAgent(Agent):

    def __init__(self, sim_threads=None):
        self.sim_threads = sim_threads

    def action(self, state):
        a = Action.STAY
        return a, {}

    def direct_action(self, obs):
        return [Action.ACTION_TO_INDEX[Action.STAY]] * self.sim_threads


class FixedPlanAgent(Agent):
    """
    An Agent with a fixed plan. Returns Stay actions once pre-defined plan has terminated.
    # NOTE: Assumes that calls to action are sequential (agent has history)
    """

    def __init__(self, plan):
        self.plan = plan
        self.i = 0

    def action(self, state):
        if self.i >= len(self.plan):
            return Action.STAY, {}
        curr_action = self.plan[self.i]
        self.i += 1
        return curr_action, {}

    def reset(self):
        super().reset()
        self.i = 0


class PlanningAgent(Agent):
    """
    Agent that at each step selects a medium level action corresponding
    to the most intuitively high-priority thing to do

    NOTE: MIGHT NOT WORK IN ALL ENVIRONMENTS, for example forced_coordination.layout,
    in which an individual agent cannot complete the task on their own.
    Will work only in environments where the only order is 3 onion soup.
    """

    def __init__(self, hl_boltzmann_rational=False, ll_boltzmann_rational=False, hl_temp=1, ll_temp=1,
                 auto_unstuck=True):
        #self.mdp = mdp
        self.intentions = {"recipe": None, "goal": None, "agent_name": None}
        self.motion_goal = None
        self.chosen_goal = None
        self.hl_objective_switch = 0
        self.stuck_frames = 0
        # [CUTTING BOARD] Drapeau d'attente volontaire d'une planche (voir action()).
        self._intentional_wait = False
        Recipe.configure({})
        # None = aucun objectif réel encore choisi. La première affectation d'une vraie
        # recette ne doit pas compter comme un switch (None n'est jamais dans all_recipes).
        self.hl_goal = None
        

        # Bool for perfect rationality vs Boltzmann rationality for high level and low level action selection
        # For choices among high level goals of same type
        self.hl_boltzmann_rational = hl_boltzmann_rational
        # For choices about low level motion
        self.ll_boltzmann_rational = ll_boltzmann_rational

        # Coefficient for Boltzmann rationality for high level action selection
        self.hl_temperature = hl_temp
        self.ll_temperature = ll_temp

        # Whether to automatically take an action to get the agent unstuck if it's in the same
        # state as the previous turn. If false, the agent is history-less, while if true it has history.
        self.auto_unstuck = auto_unstuck
        self.next_order_info = None
        # [COMM JOUEUR→IA] Consignes du joueur (None = aucun forçage).
        self.forced_recipe = None    # section distale : liste d'ingrédients de la recette à viser
        self.forced_subtask = None   # section proximale : 'ingredient'|'chop'|'pot'|'serve'
        self.reset()

    def reset(self):
        self.prev_state = None
        # None = aucun objectif réel encore choisi pour cet essai. Le 1er choix d'un essai
        # ne doit pas compter comme un switch (None n'est jamais dans all_recipes).
        self.hl_goal = None
        # [COMM JOUEUR→IA] Réinitialiser les consignes du joueur à chaque nouvel essai.
        self.forced_recipe = None
        self.forced_subtask = None
        #self.mdp = mdp
        #self.mlam = MediumLevelActionManager.from_pickle_or_compute(self.mdp, NO_COUNTERS_PARAMS)

    def set_mdp(self, mdp):
        super().set_mdp(mdp)
        counter_params = COUNTERS_MLG_PARAMS
        if self.mdp.counter_goals:
            counter_params["counter_goals"] = self.mdp.counter_goals
            counter_params["counter_drop"] = self.mdp.counter_goals
            counter_params["counter_pickup"] = self.mdp.counter_goals
        self.mlam = MediumLevelActionManager.from_pickle_or_compute(
            self.mdp, counter_params, force_compute=False)
        a = 1

    def actions(self, states, agent_indices):
        actions_and_infos_n = []
        for state, agent_idx in zip(states, agent_indices):
            self.set_agent_index(agent_idx)
            self.reset()
            actions_and_infos_n.append(self.action(state))
        return actions_and_infos_n

    def action(self, state):
        # [CUTTING BOARD] Attente volontaire : remis à False à chaque décision, puis mis à
        # True par _chop_or_wait_actions quand l'IA choisit d'ATTENDRE qu'une planche se
        # libère (plutôt que de jeter un ingrédient encore nécessaire). Sert à exempter
        # cette attente du mécanisme anti-blocage (cf. plus bas), comme pour un INTERACT.
        self._intentional_wait = False
        # [COMM JOUEUR→IA] Forçage STRICT d'une sous-tâche demandée par le joueur (section proximale).
        # L'IA ne fait QUE l'étape demandée ; si elle n'est pas réalisable dans l'état courant,
        # elle reste immobile (STAY), sans déclencher la logique auto_unstuck.
        if self.forced_subtask is not None:
            forced_goals = self._forced_motion_goals(state)
            if len(forced_goals) == 0:
                self.chosen_goal = state.players_pos_and_or[self.agent_index]
                self.prev_state = state
                return Action.STAY, {"action_probs": self.a_probs_from_action(Action.STAY)}
            self.motion_goal = forced_goals
        else:
            self.motion_goal = self.ml_action(state)

        # [CUTTING BOARD] Attente volontaire d'une planche occupée : l'IA tient un
        # ingrédient encore nécessaire mais toutes les planches sont prises (partenaire
        # en train de découper). On reste STAY sur place jusqu'à libération, SANS passer
        # par le planner (le goal « sur place » peut ne pas affronter une feature selon
        # l'orientation courante) ni par l'anti-blocage. Miroir du court-circuit du mode
        # forcé ci-dessus. C'est ce qui remplace l'ancien comportement « jeter l'oignon ».
        if self._intentional_wait:
            self.chosen_goal = state.players_pos_and_or[self.agent_index]
            self.prev_state = state
            return Action.STAY, {"action_probs": self.a_probs_from_action(Action.STAY)}

        # Once we have identified the motion goals for the medium
        # level action we want to perform, select the one with lowest cost
        start_pos_and_or = state.players_pos_and_or[self.agent_index]

        chosen_goal, chosen_action, action_probs = self.choose_motion_goal(
            start_pos_and_or, self.motion_goal)
        self.chosen_goal = chosen_goal

        if self.ll_boltzmann_rational and chosen_goal[0] == start_pos_and_or[0]:
            chosen_action, action_probs = self.boltzmann_rational_ll_action(
                start_pos_and_or, chosen_goal)

        if self.auto_unstuck:
            # HACK: if two agents get stuck, select an action at random that would
            # change the player positions if the other player were not to move
            # [CUTTING BOARD] Un INTERACT est une action VOLONTAIRE « sur place » :
            # déposer / découper / récupérer un ingrédient sur une planche demande
            # plusieurs INTERACT consécutifs (chop_time interactions) sans que la
            # position de l'agent change. L'agent travaille, il n'est PAS bloqué : il
            # ne faut donc pas le compter comme "stuck", sinon l'anti-blocage le fait
            # dériver d'une case entre chaque découpe au lieu de simplement couper.
            # NB : l'attente volontaire d'une planche occupée est déjà court-circuitée en
            # STAY plus haut (self._intentional_wait) et n'atteint jamais ce bloc.
            if chosen_action == Action.INTERACT:
                self.stuck_frames = 0
            elif self.prev_state is not None and state.players_pos_and_or == self.prev_state.players_pos_and_or:
                self.stuck_frames += 1
                # Only activate anti-blocking after being stuck for 2 consecutive frames
                if self.stuck_frames >= 2:
                    if self.agent_index == 0:
                        joint_actions = list(itertools.product(
                            Action.ALL_ACTIONS, [Action.STAY]))
                    elif self.agent_index == 1:
                        joint_actions = list(itertools.product(
                            [Action.STAY], Action.ALL_ACTIONS))
                    else:
                        raise ValueError("Player index not recognized")

                    unblocking_joint_actions = []
                    for j_a in joint_actions:
                        new_state, _ = self.mlam.mdp.get_state_transition(
                            state, j_a)
                        if new_state.player_positions != self.prev_state.player_positions:
                            unblocking_joint_actions.append(j_a)
                    # Getting stuck became a possiblity simply because the nature of a layout (having a dip in the middle)
                    if len(unblocking_joint_actions) == 0:
                        unblocking_joint_actions.append([Action.STAY, Action.STAY])
                    chosen_action = unblocking_joint_actions[np.random.choice(len(unblocking_joint_actions))][
                        self.agent_index]
                    action_probs = self.a_probs_from_action(chosen_action)
            else:
                # Reset stuck counter when agent moves
                self.stuck_frames = 0

            # NOTE: Assumes that calls to the action method are sequential
            self.prev_state = state
        return chosen_action, {"action_probs": action_probs}

    def choose_motion_goal(self, start_pos_and_or, motion_goals):
        """
        For each motion goal, consider the optimal motion plan that reaches the desired location.
        Based on the plan's cost, the method chooses a motion goal (either boltzmann rationally
        or rationally), and returns the plan and the corresponding first action on that plan.
        """
        if self.hl_boltzmann_rational:
            possible_plans = [self.mlam.motion_planner.get_plan(
                start_pos_and_or, goal) for goal in motion_goals]
            plan_costs = [plan[2] for plan in possible_plans]
            goal_idx, action_probs = self.get_boltzmann_rational_action_idx(
                plan_costs, self.hl_temperature)
            chosen_goal = motion_goals[goal_idx]
            chosen_goal_action = possible_plans[goal_idx][0][0]
        else:
            chosen_goal, chosen_goal_action = self.get_lowest_cost_action_and_goal(
                start_pos_and_or, motion_goals)
            action_probs = self.a_probs_from_action(chosen_goal_action)
        return chosen_goal, chosen_goal_action, action_probs

    def get_boltzmann_rational_action_idx(self, costs, temperature):
        """Chooses index based on softmax probabilities obtained from cost array"""
        costs = np.array(costs)
        softmax_probs = np.exp(-costs * temperature) / \
            np.sum(np.exp(-costs * temperature))
        action_idx = np.random.choice(len(costs), p=softmax_probs)
        return action_idx, softmax_probs

    def get_lowest_cost_action_and_goal(self, start_pos_and_or, motion_goals):
        """
        Chooses motion goal that has the lowest cost action plan.
        Returns the motion goal itself and the first action on the plan.
        """
        min_cost = np.inf
        best_action, best_goal = None, None
        for goal in motion_goals:
            action_plan, _, plan_cost = self.mlam.motion_planner.get_plan(
                start_pos_and_or, goal)
            if plan_cost < min_cost:
                best_action = action_plan[0]
                min_cost = plan_cost
                best_goal = goal
        return best_goal, best_action

    def boltzmann_rational_ll_action(self, start_pos_and_or, goal, inverted_costs=False):
        """
        Computes the plan cost to reach the goal after taking each possible low level action.
        Selects a low level action boltzmann rationally based on the one-step-ahead plan costs.

        If `inverted_costs` is True, it will make a boltzmann "irrational" choice, exponentially
        favouring high cost plans rather than low cost ones.
        """
        future_costs = []
        for action in Action.ALL_ACTIONS:
            pos, orient = start_pos_and_or
            new_pos_and_or = self.mdp._move_if_direction(pos, orient, action)
            _, _, plan_cost = self.mlam.motion_planner.get_plan(
                new_pos_and_or, goal)
            sign = (-1) ** int(inverted_costs)
            future_costs.append(sign * plan_cost)

        action_idx, action_probs = self.get_boltzmann_rational_action_idx(
            future_costs, self.ll_temperature)
        return Action.ALL_ACTIONS[action_idx], action_probs

    




    def _held_needs_chopping(self, held_obj):
        """[CUTTING BOARD] True si l'ingrédient tenu doit être coupé avant le pot.
        C'est le cas si la recette ciblée l'exige, OU si la découpe est imposée à ce
        joueur via AI_forced_cutting (le MDP interdit alors de déposer du non-coupé)."""
        mdp = self.mlam.mdp
        if not getattr(mdp, 'cutting_enabled', False):
            return False
        if getattr(held_obj, 'chopped', False):
            return False
        # [FORCED CUTTING] Découpe imposée à ce joueur => toujours découper avant le pot.
        if getattr(mdp, 'is_forced_cutting_player', None) and mdp.is_forced_cutting_player(self.agent_index):
            return True
        try:
            recipe = self.next_order_info["recipe"]
        except (TypeError, KeyError):
            return False
        return mdp.recipe_requires_chopping(recipe)

    def _discard_actions(self, state):
        """[POUBELLE] Motion goals pour se débarrasser de l'objet tenu : poubelle en
        priorité si le layout en contient une, sinon dépôt sur comptoir / zone d'échange.
        Retourne (motion_goals, goal_symbol)."""
        am = self.mlam
        if am.mdp.get_trash_bin_locations():
            trash_goals = am.place_obj_in_trash_actions(state)
            if trash_goals:
                return trash_goals, 'E'
        return am.place_obj_on_counter_actions(state), 'X'

    # ==================================================================
    # [ÉCHANGE] Coopération asymétrique par passage d'objets (zone d'échange 'Y')
    # ------------------------------------------------------------------
    # Sur un layout asymétrique (p.ex. test_asym01), certaines ressources d'une
    # recette ne sont accessibles qu'à UN des deux joueurs : oignon/tomate/pot/
    # service d'un côté, planche à découper 'C'/assiette 'D' de l'autre, séparés par
    # un mur de comptoirs d'échange 'Y' (mdp.counter_goals). Aucun joueur ne peut
    # compléter une commande seul. Comportement voulu : chaque agent fait AVANCER
    # l'objet aussi loin que ses ressources accessibles le permettent, puis, s'il ne
    # peut aller plus loin alors que le PARTENAIRE le peut, il DÉPOSE l'objet sur un
    # comptoir d'échange atteignable par les deux (« passer dans l'état le plus avancé
    # possible ») au lieu de le jeter. Symétriquement, il ne RÉCUPÈRE d'un comptoir
    # d'échange qu'un objet qu'il peut lui-même faire avancer (sinon il reprendrait en
    # boucle ce qu'il vient de passer = churn).
    #
    # Toutes ces branches sont conditionnées par « ressource inatteignable par MOI mais
    # atteignable par le PARTENAIRE » : sur un layout auto-suffisant (ressources
    # atteignables des deux côtés + counter_goals vide) elles sont des no-op et le
    # comportement greedy historique est strictement inchangé.

    def _reachable(self, pos_and_or, feature_positions):
        """True si au moins un motion goal vers l'une de ces positions de feature est
        atteignable depuis pos_and_or (même composante connexe + fait face à la feature)."""
        if not feature_positions:
            return False
        mp = self.mlam.motion_planner
        for g in self.mlam._get_ml_actions_for_positions(list(feature_positions)):
            if mp.is_valid_motion_start_goal_pair(pos_and_or, g):
                return True
        return False

    def _partner_reach(self, state, feature_positions):
        return self._reachable(state.players[1 - self.agent_index].pos_and_or, feature_positions)

    def _ingredient_needs_chop(self, state, chopped):
        """True si un ingrédient (déjà coupé=chopped) devrait être découpé avant le pot
        pour CET agent : découpe activée, pas encore coupé, et (découpe imposée à ce
        joueur OU recette courante l'exigeant). Miroir de _held_needs_chopping pour un
        ingrédient hypothétique (posé sur un comptoir)."""
        mdp = self.mlam.mdp
        if not getattr(mdp, 'cutting_enabled', False) or chopped:
            return False
        if getattr(mdp, 'is_forced_cutting_player', None) and mdp.is_forced_cutting_player(self.agent_index):
            return True
        try:
            return mdp.recipe_requires_chopping(self.next_order_info["recipe"])
        except (TypeError, KeyError):
            return False

    def _can_advance_item(self, state, item_name, chopped):
        """True si CET agent peut faire avancer d'au moins une étape un objet donné,
        depuis son état courant, avec les ressources qu'il peut ATTEINDRE. Sert à décider
        s'il faut passer l'objet au partenaire, et à ne récupérer d'un comptoir d'échange
        que ce qu'on peut réellement traiter (anti-churn)."""
        mdp = self.mlam.mdp
        me = state.players[self.agent_index].pos_and_or
        if item_name in ('onion', 'tomato'):
            if self._ingredient_needs_chop(state, chopped):
                return self._reachable(me, mdp.get_cutting_board_locations())
            return self._reachable(me, mdp.get_pot_locations())
        if item_name == 'dish':
            return self._reachable(me, mdp.get_pot_locations())
        if item_name == 'soup':
            return self._reachable(me, mdp.get_serving_locations())
        return True

    def _exchange_handoff_actions(self, state):
        """Motion goals pour DÉPOSER l'objet tenu sur un comptoir d'échange (counter_goals)
        VIDE, atteignable à la fois par MOI et par le PARTENAIRE (pour qu'il puisse le
        reprendre). Retour [] si aucun tel comptoir (l'appelant retombe sur attendre/jeter)."""
        mdp = self.mlam.mdp
        mp = self.mlam.motion_planner
        me = state.players[self.agent_index].pos_and_or
        partner = state.players[1 - self.agent_index].pos_and_or
        goals = []
        for c in mdp.counter_goals:
            if state.has_object(c):
                continue
            if not self._reachable(partner, [c]):
                continue
            for g in self.mlam._get_ml_actions_for_positions([c]):
                if mp.is_valid_motion_start_goal_pair(me, g):
                    goals.append(g)
        return goals

    def _handoff_if_partner_only(self, state, needed_positions):
        """Si la ressource `needed_positions` (nécessaire pour faire avancer l'objet tenu)
        est INATTEIGNABLE par moi mais ATTEIGNABLE par le partenaire, renvoie les motion
        goals pour passer l'objet via un comptoir d'échange. Sinon None (l'appelant
        poursuit sa logique attendre/jeter habituelle)."""
        me = state.players[self.agent_index].pos_and_or
        if self._reachable(me, needed_positions):
            return None
        if not self._partner_reach(state, needed_positions):
            return None
        return self._exchange_handoff_actions(state) or None

    def _in_transit_to_partner(self, state, item_name):
        """True si un exemplaire de `item_name` est déjà « en aval » côté partenaire : tenu
        par lui, posé sur un comptoir d'ÉCHANGE, ou en cours de traitement sur une PLANCHE à
        découper. Throttle fournisseur : n'en fournir un nouveau qu'une fois le précédent
        consommé (mis au pot). Inclure la planche évite la sur-production (sinon on fournit
        un 2e exemplaire pendant que le partenaire découpe le 1er)."""
        mdp = self.mlam.mdp
        partner = state.players[1 - self.agent_index]
        if partner.has_object() and partner.get_object().name == item_name:
            return True
        downstream = set(mdp.counter_goals) | set(mdp.get_cutting_board_locations())
        for pos, obj in state.objects.items():
            if obj.name == item_name and pos in downstream:
                return True
        return False

    def _filter_counter_pickups(self, state, counter_objects):
        """Retire des candidats de ramassage sur comptoir les objets posés sur un comptoir
        d'ÉCHANGE que CET agent ne peut pas faire avancer (ils sont en transit vers le
        partenaire ; les reprendre = churn). No-op si le layout n'a pas de comptoir
        d'échange (counter_goals vide) -> comportement historique préservé."""
        mdp = self.mlam.mdp
        exchange = set(mdp.counter_goals)
        if not exchange:
            return counter_objects
        filtered = defaultdict(list)
        for name, positions in counter_objects.items():
            for pos in positions:
                if pos in exchange:
                    obj = state.get_object(pos) if state.has_object(pos) else None
                    chopped = bool(getattr(obj, 'chopped', False)) if obj is not None else False
                    if not self._can_advance_item(state, name, chopped):
                        continue
                filtered[name].append(pos)
        return filtered

    def _fetch_or_supply(self, state, item, counter_objects):
        """Empty-handed : obtenir `item` (oignon/tomate) pour avancer la recette.

        Priorité RECEVEUR : s'il existe sur un comptoir un exemplaire que je peux faire
        AVANCER moi-même (typiquement un ingrédient DÉJÀ COUPÉ que le partenaire m'a
        renvoyé et que je peux mettre au pot), aller le CONSOMMER — jamais bloqué par le
        throttle. Sinon FOURNISSEUR : aller en chercher un au dispenser ; mais si je ne
        peux pas faire avancer un `item` brut moi-même (je ne fais que le passer) et qu'un
        exemplaire est déjà en aval côté partenaire, ATTENDRE (ne pas sur-approvisionner).
        `counter_objects` est déjà filtré (règle du receveur). Retour (motion_goals, symbole)."""
        am = self.mlam
        mp = am.motion_planner
        mdp = am.mdp
        player = state.players[self.agent_index]
        sym = 'O' if item == 'onion' else 'T'
        pick = am.pickup_onion_actions if item == 'onion' else am.pickup_tomato_actions
        # [NO-OP] Layout auto-suffisant (aucun comptoir d'échange) : la coopération par
        # passage n'a pas lieu d'être -> comportement greedy historique STRICTEMENT
        # inchangé (dispenser + comptoirs combinés, coût le plus faible choisi ensuite).
        if not mdp.counter_goals:
            return pick(counter_objects, state=state, player_idx=self.agent_index), sym
        # 1) RECEVEUR : consommer un exemplaire posé sur comptoir que je peux faire avancer.
        consumable = list(counter_objects.get(item, []))
        cons_goals = [g for g in am._get_ml_actions_for_positions(consumable)
                      if mp.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
        if cons_goals:
            return cons_goals, sym
        # 2) FOURNISSEUR : aller au dispenser.
        disp = (mdp.get_onion_dispenser_locations() if item == 'onion'
                else mdp.get_tomato_dispenser_locations())
        disp += am._get_asymmetric_dispenser_locations_for_item(state, self.agent_index, item)
        disp_goals = [g for g in am._get_ml_actions_for_positions(disp)
                      if mp.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
        if disp_goals:
            if (not self._can_advance_item(state, item, chopped=False)) \
                    and self._in_transit_to_partner(state, item):
                # Pur fournisseur + un exemplaire déjà en aval -> ne pas empiler, attendre.
                self._intentional_wait = True
                return am.wait_actions(player), sym
            return disp_goals, sym
        # 3) Aucune source atteignable : l'ingrédient viendra du partenaire -> attendre.
        self._intentional_wait = True
        return am.wait_actions(player), sym

    def _fetch_dish_or_wait(self, state, player, counter_objects):
        """Empty-handed : aller chercher une assiette (comptoirs filtrés = règle du
        receveur). Throttle fournisseur : si je ne peux pas emporter la soupe moi-même
        (aucune marmite atteignable -> je ne fais que PASSER l'assiette) et qu'une assiette
        est déjà en transit vers le partenaire, j'ATTENDS au lieu de sur-approvisionner."""
        am = self.mlam
        if (not self._can_advance_item(state, 'dish', chopped=False)) \
                and self._in_transit_to_partner(state, 'dish'):
            self._intentional_wait = True
            return am.wait_actions(player)
        return am.pickup_dish_actions(counter_objects, state=state, player_idx=self.agent_index)

    def _can_obtain_ingredient(self, state, item):
        """[ÉCHANGE] True si l'agent peut obtenir `item` MAINTENANT : son dispenser est
        atteignable, OU un exemplaire qu'il peut faire avancer est posé sur un comptoir
        atteignable (passé par le partenaire). Sert à viser en priorité l'ingrédient
        manquant réellement disponible plutôt que de rester bloqué sur un ingrédient
        inaccessible."""
        mdp = self.mlam.mdp
        me = state.players[self.agent_index].pos_and_or
        disp = (mdp.get_onion_dispenser_locations() if item == 'onion'
                else mdp.get_tomato_dispenser_locations())
        disp += self.mlam._get_asymmetric_dispenser_locations_for_item(state, self.agent_index, item)
        if self._reachable(me, disp):
            return True
        for pos, obj in state.objects.items():
            if obj.name == item and mdp.get_terrain_type_at_pos(pos) == 'X' \
                    and self._reachable(me, [pos]) \
                    and self._can_advance_item(state, item, bool(getattr(obj, 'chopped', False))):
                return True
        return False

    def _committed_ingredients(self, state):
        """[ÉCHANGE] Multiensemble (Counter) des ingrédients oignon/tomate actuellement
        ENGAGÉS dans le pipeline de la recette en cours d'assemblage : présents dans une
        marmite PAS ENCORE EN CUISSON, sur une planche à découper, sur un comptoir d'échange,
        ou tenus par un joueur. Exclut les soupes en cuisson/prêtes (recette déjà figée, plus
        rien à assembler) et les dispensers. AGNOSTIQUE au joueur (même valeur pour les deux)
        -> objectifs cohérents entre partenaires.

        Sert à choisir une recette cible STABLE et ACCUMULATIVE (GreedyAgent.hl_action) :
        chaque tomate qui ENTRE dans le pipeline fait grimper l'objectif
        ([O,O,O]->[O,O,T]->[O,T,T]) et celui-ci RESTE stable tant que la tomate y est (tenue /
        planche / échange / marmite en assemblage), au lieu de « redescendre » vers [O,O,O]
        dès qu'elle est repassée. L'objectif ne se relâche qu'une fois la soupe lancée en
        cuisson (pipeline vidé)."""
        mdp = self.mlam.mdp
        c = Counter()
        placed = set(mdp.counter_goals) | set(mdp.get_cutting_board_locations())
        for pot_pos in mdp.get_pot_locations():
            if state.has_object(pot_pos):
                soup = state.get_object(pot_pos)
                if not soup.is_cooking and not soup.is_ready:
                    for ing in soup.ingredients:
                        if ing in ('onion', 'tomato'):
                            c[ing] += 1
        for pos, obj in state.objects.items():
            if obj.name in ('onion', 'tomato') and pos in placed:
                c[obj.name] += 1
        for pl in state.players:
            if pl.has_object() and pl.get_object().name in ('onion', 'tomato'):
                c[pl.get_object().name] += 1
        return c

    def _chop_or_wait_actions(self, state, player):
        """[CUTTING BOARD] Motion goals pour découper l'ingrédient BRUT tenu.

        Cas normal : une planche est LIBRE -> aller l'y déposer.

        Sinon (toutes les planches occupées, p.ex. le partenaire découpe déjà) :
        l'ingrédient tenu reste NÉCESSAIRE à la recette (il sera coupé une fois la
        planche libérée) — on NE le jette PAS. Comportement voulu : l'IA va d'abord se
        placer DEVANT une planche occupée et lui faire face, PUIS attend (STAY) là
        jusqu'à libération.
          - pas encore en place -> renvoyer les motion goals vers la planche occupée
            (déplacement normal : l'IA marche jusqu'à la planche puis se tourne) ;
          - arrivée et face à la planche -> poser self._intentional_wait (action()
            court-circuitera en STAY) plutôt que d'INTERAGIR sur une planche occupée
            (no-op) ou de dériver.
        Repli : aucune position d'attente atteignable (planche accessible seulement du
        côté du partenaire) -> attendre sur place (self._intentional_wait) ; retour []
        uniquement si le layout n'a AUCUNE planche, pour laisser l'appelant gérer ce
        cas dégénéré.

        [ÉCHANGE] Si AUCUNE planche n'est atteignable par moi mais que le PARTENAIRE peut
        en atteindre une, je ne peux pas faire avancer l'ingrédient brut : je le PASSE au
        partenaire via un comptoir d'échange (état le plus avancé possible = brut) au lieu
        de le jeter. L'appelant doit lire self.intentions['goal'] (positionné ici)."""
        am = self.mlam
        mp = am.motion_planner
        board_locs = am.mdp.get_cutting_board_locations()
        # Planches VIDES atteignables par moi : aller y déposer l'ingrédient à couper.
        reachable_empty = [g for g in am.put_ingredient_on_board_actions(state)
                           if mp.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
        if reachable_empty:
            self.intentions['goal'] = 'C'
            return reachable_empty
        if not board_locs:
            self.intentions['goal'] = 'C'
            return []   # layout sans planche : cas dégénéré, repli de l'appelant
        # [ÉCHANGE] Aucune planche atteignable par moi mais le partenaire peut découper.
        handoff = self._handoff_if_partner_only(state, board_locs)
        if handoff is not None:
            self.intentions['goal'] = 'X'
            return handoff
        # Planches atteignables par moi mais toutes occupées (partenaire découpe déjà) :
        # aller se placer DEVANT une planche occupée et attendre sa libération.
        self.intentions['goal'] = 'C'
        occupied = [p for p in board_locs if state.has_object(p)]
        wait_goals = [mg for mg in am._get_ml_actions_for_positions(occupied)
                      if mp.is_valid_motion_start_goal_pair(player.pos_and_or, mg)]
        # Déjà en place et face à une planche, OU aucune position atteignable -> attendre.
        if (not wait_goals) or (player.pos_and_or in wait_goals):
            self._intentional_wait = True
            return am.wait_actions(player)
        return wait_goals   # s'y rendre d'abord (puis on attendra une fois arrivé)

    def _plate_or_wait_actions(self, state, player, pot_states_dict):
        """[ASSIETTE] Motion goals pour une assiette tenue quand AUCUNE marmite n'est
        prête ni en cuisson (``pickup_soup_with_dish_actions(only_nearly_ready=True)``
        a renvoyé []).

        Symétrique de ``_chop_or_wait_actions`` : si une marmite est EN COURS
        d'assemblage (partiellement remplie, ou pleine mais cuisson pas encore lancée),
        la soupe va être cuite et l'assiette servira à l'emporter — on NE la jette PAS.
        On ATTEND sur place (``self._intentional_wait`` -> STAY dans ``action()``) plutôt
        que de la déposer/reprendre en boucle sur un comptoir : ce « churn » est non
        seulement inutile mais promène l'agent et gêne le partenaire venu déposer le
        dernier ingrédient / lancer la cuisson. Dès la cuisson lancée,
        ``only_nearly_ready`` renverra la marmite et l'agent ira l'emporter.

        Repli : aucune marmite en cours d'assemblage -> l'assiette est réellement
        inutile -> jeter (poubelle en priorité, cf. ``_discard_actions``).

        Retourne (motion_goals, goal_symbol)."""
        am = self.mlam
        # [ÉCHANGE] Je tiens une assiette mais ne peux atteindre AUCUNE marmite (pour
        # emporter la soupe) alors que le partenaire le peut : lui passer l'assiette via
        # un comptoir d'échange (c'est lui qui plate/emporte la soupe de son côté).
        handoff = self._handoff_if_partner_only(state, am.mdp.get_pot_locations())
        if handoff is not None:
            return handoff, 'X'
        # Marmites en cours de traitement : en remplissage (partielles) OU pleines pas
        # encore lancées. Dans les DEUX cas on GARDE l'assiette et on attend : elle
        # servira à emporter la soupe une fois cuite. IMPORTANT : même si la marmite
        # pleine forme une recette INVALIDE ([O,O,T]...), l'assiette reste NÉCESSAIRE —
        # c'est en emportant la soupe (invalide) avec l'assiette qu'on VIDE la marmite
        # pour poursuivre le jeu (la soupe, elle, sera jetée par la branche 'soup'). Ne
        # JAMAIS jeter l'assiette dans ce cas.
        pending = (am.mdp.get_partially_full_pots(pot_states_dict)
                   + am.mdp.get_full_but_not_cooking_pots(pot_states_dict))
        if not pending:
            # Aucune soupe à venir : l'assiette ne sert à rien -> jeter.
            return self._discard_actions(state)
        # Une soupe s'assemble / est à cuire : attendre sur place qu'elle cuise, sans
        # encombrer la marmite que le partenaire doit encore atteindre.
        self._intentional_wait = True
        return am.wait_actions(player), 'P'

    def _put_in_pot_or_wait_actions(self, state, player, pot_states_dict, fill_goals):
        """[POT] ``fill_goals`` = ``put_<ingredient>_in_pot_actions(...)`` (marmites
        remplissables : partielles ou vides). Si non vide -> aller remplir.

        Sinon AUCUNE marmite n'est remplissable alors que l'ingrédient tenu reste
        NÉCESSAIRE (branche appelée seulement quand il est requis et déjà découpé si
        besoin). Une marmite occupée (prête / en cuisson / pleine) va se LIBÉRER une
        fois la soupe emportée -> on ATTEND (``self._intentional_wait`` -> STAY) au lieu
        de poser/reprendre l'ingrédient en boucle sur un comptoir. Ce « churn » est,
        comme pour l'assiette, un INTERACT « protégé » par la couche coop : il fige un
        couloir devant le partenaire venu justement emporter la soupe (donc libérer la
        marmite). En STAY, l'agent devient un « yielder » que la couche coop écarte.

        Priorité au déblocage : s'il existe une marmite qui n'attend qu'un INTERACT
        mains vides pour cuire — pleine (même en une recette invalide déposée par le
        partenaire, à cuire puis jeter pour libérer la place) OU partielle formant déjà
        une commande complète maximale — l'ingrédient tenu EMPÊCHE de la lancer : on
        JETTE pour libérer une main, puis (mains vides) on lance sa cuisson au tick
        suivant. Attendre serait un INTERBLOCAGE : une marmite pleine-non-cuisson ne se
        « libère » JAMAIS toute seule (contrairement à une marmite en cuisson/prête).

        Sinon, seule une marmite en cuisson/prête va réellement se libérer en emportant
        sa soupe -> on ATTEND (``self._intentional_wait`` -> STAY) au lieu de poser/
        reprendre l'ingrédient en boucle sur un comptoir. Ce « churn » est un INTERACT
        « protégé » par la couche coop : il fige un couloir devant le partenaire venu
        justement emporter la soupe. En STAY l'agent devient un « yielder » écarté.

        Anti-blocage : si le partenaire tient LUI AUSSI un ingrédient (deux mains
        pleines, personne pour emporter la soupe et libérer la marmite), ne pas attendre
        tous les deux -> jeter pour libérer une main (et pouvoir prendre une assiette).

        Repli : aucune marmite ne se libérera -> jeter.

        [ÉCHANGE] Si aucune marmite n'est ATTEIGNABLE par moi (fill vidé par le filtre de
        reachability) mais que le PARTENAIRE peut en atteindre une, je passe l'ingrédient
        (coupé = état le plus avancé de mon côté) au partenaire via un comptoir d'échange
        au lieu de le jeter. (Si une marmite m'est atteignable mais que fill est vide pour
        cause d'INCOMPATIBILITÉ recette, _handoff_if_partner_only renvoie None -> on garde
        la logique cuire/attendre/jeter.)
        Retourne (motion_goals, goal_symbol)."""
        mp = self.mlam.motion_planner
        # Ne garder que les marmites remplissables réellement ATTEIGNABLES par moi.
        reachable_fill = [g for g in fill_goals
                          if mp.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
        if reachable_fill:
            return reachable_fill, 'P'
        mdp = self.mlam.mdp
        handoff = self._handoff_if_partner_only(state, mdp.get_pot_locations())
        if handoff is not None:
            return handoff, 'X'
        # Marmites qui n'attendent qu'un INTERACT mains vides pour cuire. L'ingrédient
        # tenu bloque leur lancement -> libérer la main (jeter), puis les cuire.
        needs_cook_start = (mdp.get_full_but_not_cooking_pots(pot_states_dict)
                            + self._maximal_complete_pots(state, pot_states_dict))
        if needs_cook_start:
            return self._discard_actions(state)
        # Seules 'ready'/'cooking' se libéreront d'elles-mêmes (soupe emportée). NE PAS
        # inclure les pleines-non-cuisson : rien ne les cuit tant que l'agent attend.
        occupied = pot_states_dict['ready'] + pot_states_dict['cooking']
        partner = state.players[1 - self.agent_index]
        partner_holds_ingredient = (partner.has_object()
                                    and partner.get_object().name in ('onion', 'tomato'))
        if occupied and not partner_holds_ingredient:
            self._intentional_wait = True
            return self.mlam.wait_actions(player), 'P'
        return self._discard_actions(state)

    # ------------------------------------------------------------------
    # [RECETTE VALIDE] Compatibilité marmite <-> commandes (all_orders).
    # ------------------------------------------------------------------
    # Le remplissage « naïf » (put_<ingredient>_in_pot_actions) vise TOUTE marmite
    # partielle ou vide, sans vérifier que le contenu résultant reste une commande
    # possible. D'où le bug : une marmite [oignon, tomate] (commande VALIDE [O,T]) vue
    # comme un [O,O,O] incomplet -> l'IA ajoute un oignon -> [O,O,T], recette ABSENTE
    # de all_orders. Les helpers ci-dessous filtrent sur la compatibilité réelle avec
    # les commandes courantes (multiensembles d'ingrédients).

    def _order_ingredient_counters(self, state):
        """Multiensembles (Counter) des commandes actuellement valides (all_orders)."""
        return [Counter(recipe.ingredients) for recipe in state.all_orders]

    def _pot_can_accept_ingredient(self, pot_contents, ingredient, order_counters):
        """True si ajouter `ingredient` à une marmite contenant `pot_contents` (liste de
        noms) laisse le contenu sous-multiensemble d'AU MOINS une commande — donc encore
        complétable en une vraie recette. False => l'ajout créerait une combinaison
        absente de all_orders (p.ex. [O,T] + oignon = [O,O,T])."""
        resulting = Counter(pot_contents)
        resulting[ingredient] += 1
        return any(all(resulting[name] <= oc.get(name, 0) for name in resulting)
                   for oc in order_counters)

    def _valid_fill_pots(self, state, pot_states_dict, ingredient):
        """Motion goals vers les marmites remplissables (partielles ou vides) où déposer
        `ingredient` reste compatible avec au moins une commande. Remplace le
        put_<ingredient>_in_pot_actions naïf : exclut toute marmite qui deviendrait une
        recette invalide. Retour [] => aucune marmite ne peut légitimement l'accueillir
        (l'appelant décide alors : attendre qu'une marmite se libère, ou jeter)."""
        order_counters = self._order_ingredient_counters(state)
        fillable = (self.mlam.mdp.get_partially_full_pots(pot_states_dict)
                    + pot_states_dict['empty'])
        valid = []
        for pot_pos in fillable:
            contents = list(state.get_object(pot_pos).ingredients) if state.has_object(pot_pos) else []
            if self._pot_can_accept_ingredient(contents, ingredient, order_counters):
                valid.append(pot_pos)
        return self.mlam._get_ml_actions_for_positions(valid)

    def _maximal_complete_pots(self, state, pot_states_dict):
        """Positions des marmites (partielles ou pleines pas encore en cuisson) dont le
        contenu forme une commande complète de all_orders qu'AUCUNE autre commande
        n'étend (sous-multiensemble strict). Une telle marmite ne peut plus rien devenir
        d'autre -> il faut lancer sa cuisson (ni attendre, ni y ajouter).

        Ex. (test01) [O,T] est complète ET maximale (ni [O,O,T] ni [O,T,T] dans les
        commandes) -> à cuire. À l'inverse [O] ou [O,O] (que [O,O,O] peut encore étendre)
        ne sont PAS renvoyées : on les laisse grandir vers une recette plus grosse."""
        order_counters = self._order_ingredient_counters(state)
        mdp = self.mlam.mdp
        candidates = (mdp.get_partially_full_pots(pot_states_dict)
                      + mdp.get_full_but_not_cooking_pots(pot_states_dict))
        result = []
        for pot_pos in candidates:
            if not state.has_object(pot_pos):
                continue
            contents = Counter(state.get_object(pot_pos).ingredients)
            n = sum(contents.values())
            is_complete = any(contents == oc for oc in order_counters)
            if not is_complete:
                continue
            can_grow = any(sum(oc.values()) > n
                           and all(contents[name] <= oc.get(name, 0) for name in contents)
                           for oc in order_counters)
            if not can_grow:
                result.append(pot_pos)
        return result

    def _resolve_hl_action(self, state):
        """[COMM JOUEUR→IA] Sélection de la recette cible haut niveau.

        Si le joueur a forcé une recette (section distale) et qu'elle est réalisable dans
        l'état courant (présente dans hl_info), on la vise EXACTEMENT ; sinon on retombe sur
        l'heuristique propre de l'agent (Rational/Greedy/Lazy)."""
        if self.forced_recipe:
            all_recipes = self.hl_info(state)
            target = sorted(self.forced_recipe)
            for recipe, info in all_recipes.items():
                if sorted(recipe.ingredients) == target:
                    self.hl_goal = recipe
                    return {
                        "recipe": info["recipe"],
                        "most_advanced_pot": info["most_advanced_pot"],
                        "missing_ingredients_in_MA_pot": info["missing_ingredients_in_MA_pot"],
                        "point_time_ratio": info["point_time_ratio"],
                        "min_cost_to_complete": info["min_cost_to_complete"],
                    }
        return self.hl_action(state)

    def _cookable_pots(self, state, pot_states_dict):
        """[COMM JOUEUR→IA] Marmites non vides, ni en cuisson ni prêtes, dont les ingrédients
        forment une commande complète (la recette forcée si définie, sinon n'importe quelle
        commande de state.all_orders). Utilisé pour lancer la cuisson en forçage strict 'pot'."""
        mdp = self.mlam.mdp
        orders = [sorted(r.ingredients) for r in state.all_orders]
        target = sorted(self.forced_recipe) if self.forced_recipe else None
        cookable = []
        for pot_pos in mdp.get_pot_locations():
            if not state.has_object(pot_pos):
                continue
            soup = state.get_object(pot_pos)
            if soup.is_cooking or soup.is_ready or len(soup.ingredients) == 0:
                continue
            ings = sorted(soup.ingredients)
            if (target is not None and ings == target) or (target is None and ings in orders):
                cookable.append(pot_pos)
        return cookable

    def _forced_motion_goals(self, state):
        """[COMM JOUEUR→IA] Forçage STRICT d'une étape du pipeline (section proximale).

        Retourne la liste (filtrée par atteignabilité) des motion goals correspondant
        UNIQUEMENT à l'étape demandée. Réutilise les générateurs du mlam.

        Règle de déblocage (poubelle) : si l'IA tient un objet qui l'empêche de réaliser
        l'étape demandée ET qui n'est PAS pertinent pour cette étape, elle va le jeter
        (poubelle en priorité, comptoir en repli) au lieu de rester bloquée. Un objet
        encore pertinent (mais momentanément inutilisable, ex. ingrédient brut quand on
        veut remplir la marmite) est conservé → l'IA reste alors immobile (retour []).
        """
        am = self.mlam
        mdp = self.mlam.mdp
        player = state.players[self.agent_index]
        counter_objects = mdp.get_counter_objects_dict(state, list(mdp.terrain_pos_dict['X']))
        pot_states_dict = mdp.get_pot_states(state)
        cutting_enabled = getattr(mdp, 'cutting_enabled', False)
        if cutting_enabled:
            board_locs = set(mdp.get_cutting_board_locations())
            board_objs = [o for o in state.objects.values() if o.position in board_locs]
        else:
            board_objs = []
        chopped_on_board = [o for o in board_objs if getattr(o, 'chopped', False)]
        unchopped_on_board = [o for o in board_objs if not getattr(o, 'chopped', False)]

        # Refléter la recette forcée dans les intentions (HUD IA→joueur).
        if self.forced_recipe:
            self.intentions['recipe'] = list(self.forced_recipe)

        held = player.get_object() if player.has_object() else None
        held_name = held.name if held is not None else None
        held_chopped = bool(getattr(held, 'chopped', False)) if held is not None else False
        is_raw_ingredient = held_name in ('onion', 'tomato') and not held_chopped
        is_chopped_ingredient = held_name in ('onion', 'tomato') and held_chopped

        sub = self.forced_subtask
        goals = []
        discard = False   # True => objet tenu non pertinent : aller le jeter à la poubelle

        if sub == 'ingredient':
            # Prendre un ingrédient (oignon/tomate) et l'amener à la planche à découper.
            if held is None:
                info = self._resolve_hl_action(state)
                missing = list(info.get('missing_ingredients_in_MA_pot', [])) if info else []
                if 'onion' in missing:
                    goals = am.pickup_onion_actions(counter_objects, state=state, player_idx=self.agent_index)
                    self.intentions['goal'] = 'O'
                elif 'tomato' in missing:
                    goals = am.pickup_tomato_actions(counter_objects, state=state, player_idx=self.agent_index)
                    self.intentions['goal'] = 'T'
            elif is_raw_ingredient:
                goals = am.put_ingredient_on_board_actions(state)
                self.intentions['goal'] = 'C'
            else:
                discard = True   # assiette / soupe / ingrédient déjà coupé : non pertinent

        elif sub == 'chop':
            # Découper : ne se fait que mains libres, sur un ingrédient non coupé déjà posé.
            if held is None:
                if unchopped_on_board:
                    goals = am.chop_actions(unchopped_on_board)
                    self.intentions['goal'] = 'C'
            elif is_raw_ingredient:
                # Pertinent (ingrédient à découper) : le poser sur la planche d'abord.
                goals = am.put_ingredient_on_board_actions(state)
                self.intentions['goal'] = 'C'
            else:
                discard = True   # assiette / soupe / ingrédient déjà coupé : non pertinent

        elif sub == 'pot':
            # Amener les ingrédients coupés dans la marmite (+ lancer la cuisson quand complète).
            if held is None:
                if chopped_on_board:
                    goals = am.pickup_chopped_actions(chopped_on_board)
                    self.intentions['goal'] = 'C'
                else:
                    goals = am._get_ml_actions_for_positions(self._cookable_pots(state, pot_states_dict))
                    self.intentions['goal'] = 'P'
            elif is_chopped_ingredient or (held_name in ('onion', 'tomato') and not self._held_needs_chopping(held)):
                # [RECETTE VALIDE] Même sur ordre EXPLICITE du joueur, ne jamais créer une
                # recette absente de all_orders : ne viser que les marmites où l'ajout
                # reste compatible (cf. branches autonomes). Si aucune (p.ex. marmite déjà
                # complète [O,T] -> [O,O,T] interdit), ne rien faire (goals=[] -> STAY)
                # plutôt que de gâcher la marmite.
                goals = self._valid_fill_pots(state, pot_states_dict, held_name)
                self.intentions['goal'] = 'P'
            elif is_raw_ingredient:
                pass   # ingrédient brut encore pertinent (à découper) : on le garde → STAY
            else:
                discard = True   # assiette / soupe : non pertinent pour remplir la marmite

        elif sub == 'serve':
            # Récupérer les plats dans la marmite et les servir.
            if held is None:
                if pot_states_dict['ready'] or pot_states_dict['cooking']:
                    goals = am.pickup_dish_actions(counter_objects, state=state, player_idx=self.agent_index)
                    self.intentions['goal'] = 'D'
            elif held_name == 'dish':
                goals = am.pickup_soup_with_dish_actions(pot_states_dict, only_nearly_ready=True)
                self.intentions['goal'] = 'P'
            elif held_name == 'soup':
                goals = am.deliver_soup_actions()
                self.intentions['goal'] = 'S'
            else:
                discard = True   # ingrédient (brut/coupé) : non pertinent pour servir

        # [POUBELLE] Objet tenu non pertinent pour l'étape : aller s'en débarrasser.
        if discard:
            goals, self.intentions['goal'] = self._discard_actions(state)

        # Ne conserver que les goals réellement atteignables depuis la position courante.
        goals = [mg for mg in goals
                 if self.mlam.motion_planner.is_valid_motion_start_goal_pair(player.pos_and_or, mg)]
        return goals

    def ml_action(self, state):
        """
        Selects a medium level action for the current state.
        Motion goals can be thought of instructions of the form:
            [do X] at location [Y]

        In this method, X (e.g. deliver the soup, pick up an onion, etc) is chosen based on
        a simple set of greedy heuristics based on the current state.

        Effectively, will return a list of all possible locations Y in which the selected
        medium level action X can be performed.
        """
        player = state.players[self.agent_index]
        other_player = state.players[1 - self.agent_index]
        am = self.mlam

        counter_objects = self.mlam.mdp.get_counter_objects_dict(
            state, list(self.mlam.mdp.terrain_pos_dict['X']))
        pot_states_dict = self.mlam.mdp.get_pot_states(state)

        # [CUTTING BOARD] Etat des planches à découper (no-op si la feature est désactivée)
        cutting_enabled = getattr(self.mlam.mdp, 'cutting_enabled', False)
        if cutting_enabled:
            board_locs = set(self.mlam.mdp.get_cutting_board_locations())
            board_objs = [o for o in state.objects.values() if o.position in board_locs]
        else:
            board_objs = []

        if not player.has_object():
            ready_soups = pot_states_dict['ready']
            cooking_soups = pot_states_dict['cooking']

            soup_nearly_ready = len(ready_soups) > 0 or len(cooking_soups) > 0
            other_has_dish = other_player.has_object(
            ) and other_player.get_object().name == 'dish'

            # [ÉCHANGE] Candidats de ramassage sur comptoir filtrés (règle du receveur) :
            # ne pas reprendre d'un comptoir d'échange un objet qu'on ne peut pas faire
            # avancer soi-même (anti-churn). No-op sur layout auto-suffisant.
            pickup_counter_objects = self._filter_counter_pickups(state, counter_objects)

            if soup_nearly_ready and not other_has_dish:
                self.intentions['goal'] = 'D'
                motion_goals = self._fetch_dish_or_wait(state, player, pickup_counter_objects)
            else:
                self.next_order_info = self._resolve_hl_action(state)
                self.intentions["recipe"] = self.next_order_info["recipe"].ingredients
                # [RECETTE COMPLÈTE] Priorité : une marmite formant une commande complète
                # « maximale » (aucune commande ne l'étend, p.ex. [O,T]) ne peut plus rien
                # devenir d'autre -> lancer sa cuisson MAINTENANT, quelle que soit la
                # recette « préférée » (de plus haute valeur) ciblée par l'agent. Sans
                # cela, un Greedy visant [O,O,O] laisserait indéfiniment une marmite [O,T]
                # non cuite (et, après le filtrage de remplissage, tournerait en rond :
                # prendre un oignon -> le jeter -> le reprendre...).
                maximal_pots = self._maximal_complete_pots(state, pot_states_dict)
                soups_ready_to_cook_key = '{}_items'.format(
                    len(self.next_order_info["recipe"].ingredients))
                soups_ready_to_cook = pot_states_dict[soups_ready_to_cook_key]
                if maximal_pots:
                    self.intentions['goal'] = 'P'
                    motion_goals = am._get_ml_actions_for_positions(maximal_pots)
                elif soups_ready_to_cook:
                    only_pot_states_ready_to_cook = defaultdict(list)
                    only_pot_states_ready_to_cook[soups_ready_to_cook_key] = soups_ready_to_cook
                    # we want to cook only soups that has same len as order
                    motion_goals = am.start_cooking_actions(
                        only_pot_states_ready_to_cook)

                elif self.next_order_info["most_advanced_pot"]:
                    # Prendre en compte l'objet que tient le joueur partenaire seulement si AI_see_asset est activé
                    missing_ingredients = list(self.next_order_info["missing_ingredients_in_MA_pot"])
                    
                    # Si AI_see_asset est activé ET le partenaire tient un ingrédient, le considérer comme "apporté"
                    if self.ai_see_asset and other_player.has_object():
                        partner_obj = other_player.get_object()
                        if partner_obj.name in missing_ingredients:
                            missing_ingredients.remove(partner_obj.name)
                    
                    # Décider de l'action en fonction des ingrédients restants
                    if len(missing_ingredients) == 0:
                        # Le pot le plus avancé n'a plus d'ingrédient manquant : prendre
                        # une assiette pour emporter la soupe — MAIS seulement si ce pot
                        # contient RÉELLEMENT une soupe à emporter et que le partenaire
                        # n'en tient pas déjà une. Sinon l'information est PÉRIMÉE :
                        # missing==[] alors que le pot est VIDE parce que la dernière
                        # commande est déjà cuite/emportée/livrée par le partenaire (son
                        # recette est filtrée de hl_info -> next_order_info reste figé).
                        # Aller chercher une assiette dans ce cas = va-et-vient inutile
                        # (poser/reprendre) qui, en INTERACT, est « protégé » par la couche
                        # coop et bloque le partenaire venu livrer. On s'abstient donc.
                        ma_pot = self.next_order_info["most_advanced_pot"]
                        ma_has_soup = ma_pot is not None and state.has_object(ma_pot)
                        # [ÉCHANGE] `missing_ingredients` a pu être vidé par ai_see_asset alors
                        # que le pot n'est PAS réellement complet : le partenaire TIENT encore
                        # l'ingrédient (sur un layout d'échange il est loin d'être potté — il doit
                        # d'abord être découpé puis repassé). Aller chercher une assiette
                        # (inatteignable) mènerait, via le repli go_to_closest_feature, à CUIRE le
                        # pot INCOMPLET (ex. [O,O] au lieu de [O,O,T]). On ATTEND que le partenaire
                        # dépose réellement l'ingrédient. Gardé sur counter_goals -> no-op strict
                        # sur layout auto-suffisant (comportement historique inchangé).
                        raw_missing = self.next_order_info["missing_ingredients_in_MA_pot"]
                        if self.mlam.mdp.counter_goals and ma_has_soup and len(raw_missing) > 0:
                            self._intentional_wait = True
                            motion_goals = am.wait_actions(player)
                        elif ma_has_soup and not other_has_dish:
                            self.intentions['goal'] = 'D'
                            motion_goals = self._fetch_dish_or_wait(state, player, pickup_counter_objects)
                        else:
                            # Assiette redondante (le partenaire tient déjà une assiette,
                            # ou la soupe est déjà emportée/livrée -> pot vide) : ne rien
                            # aller chercher. Attendre sur place (STAY) plutôt que d'aller
                            # churner une assiette. En STAY l'agent devient un « yielder »
                            # que la couche coop écarte du passage du partenaire (au lieu
                            # de le figer par un INTERACT « protégé »).
                            self._intentional_wait = True
                            motion_goals = am.wait_actions(player)
                    elif 'onion' in missing_ingredients or 'tomato' in missing_ingredients:
                        # [ÉCHANGE] Viser en priorité l'ingrédient manquant qu'on peut RÉELLEMENT
                        # obtenir maintenant (dispenser atteignable, ou exemplaire avançable passé
                        # sur l'échange) : un découpeur à qui on passe une tomate ne doit pas rester
                        # bloqué à attendre des oignons inaccessibles. Sur layout auto-suffisant
                        # (counter_goals vide) l'ordre historique oignon>tomate est conservé (les
                        # deux obtenables -> tri stable -> bit-identique).
                        cand = [i for i in ('onion', 'tomato') if i in missing_ingredients]
                        if self.mlam.mdp.counter_goals:
                            cand.sort(key=lambda i: 0 if self._can_obtain_ingredient(state, i) else 1)
                        motion_goals, self.intentions['goal'] = self._fetch_or_supply(
                            state, cand[0], pickup_counter_objects)
                    else:
                        motion_goals = am.wait_actions(player)
                        motion_goals
                else:
                    motion_goals = am.go_to_closest_feature_actions(player, state=state, player_idx=self.agent_index)
                    motion_goals

            # [CUTTING BOARD] Priorité: si un ingrédient est en cours de découpe / déjà coupé
            # sur une planche ATTEIGNABLE par moi, finir la découpe ou le récupérer avant
            # toute autre action. [ÉCHANGE] Ne considérer que les planches de MON côté :
            # sinon un agent qui ne peut pas atteindre la planche du partenaire viserait un
            # but inatteignable (-> jeté au repli). Réinitialise aussi _intentional_wait car
            # on a désormais un objectif concret (couper/récupérer), pas une attente.
            if cutting_enabled and board_objs:
                my_board_objs = [o for o in board_objs
                                 if self._reachable(player.pos_and_or, [o.position])]
                if my_board_objs:
                    self._intentional_wait = False
                    chopped_objs = [o for o in my_board_objs if getattr(o, 'chopped', False)]
                    unchopped_objs = [o for o in my_board_objs if not getattr(o, 'chopped', False)]
                    self.intentions['goal'] = 'C'
                    if chopped_objs:
                        motion_goals = am.pickup_chopped_actions(chopped_objs)
                    else:
                        motion_goals = am.chop_actions(unchopped_objs)

        else:
            player_obj = player.get_object()
            all_recipes = self.hl_info(state)
            # [ÉCHANGE] Si l'agent TIENT un ingrédient sur un layout d'échange, ré-évaluer la
            # recette cible pour l'ADAPTER à cet ingrédient (une tomate reçue alors qu'il visait
            # les oignons -> bascule vers la meilleure recette contenant une tomate, incrémente
            # hl_switch, et la traite au lieu de la jeter). Gardé sur counter_goals -> no-op
            # (branche historique) sur layout auto-suffisant.
            if self.mlam.mdp.counter_goals and player_obj.name in ('onion', 'tomato') and all_recipes:
                self.next_order_info = self._resolve_hl_action(state)
            else:
                try :
                    self.next_order_info["missing_ingredients_in_MA_pot"] = all_recipes[self.next_order_info["recipe"]]["missing_ingredients_in_MA_pot"]
                except KeyError:
                    # Recipe triplet changed — the cached recipe is no longer valid; replan.
                    if all_recipes:
                        self.next_order_info = self._resolve_hl_action(state)

            if player_obj.name == 'onion':
                # self.next_order_info["min_cost_to_complete"] == any([10000, 0]):
                if 'onion' not in self.next_order_info["missing_ingredients_in_MA_pot"]:
                    # [POUBELLE] Oignon non requis : jeter (poubelle en priorité)
                    motion_goals, self.intentions['goal'] = self._discard_actions(state)
                # [CUTTING BOARD] découper l'oignon avant de le mettre au pot si la recette l'exige.
                # Si la planche est occupée (partenaire en train de découper), l'oignon reste
                # nécessaire : on attend qu'elle se libère plutôt que de le jeter.
                elif cutting_enabled and self._held_needs_chopping(player_obj):
                    # [ÉCHANGE] découpe / attente / passage au partenaire (intention posée dedans)
                    motion_goals = self._chop_or_wait_actions(state, player)
                else:
                    # [RECETTE VALIDE] Ne viser que les marmites où ajouter l'oignon reste
                    # compatible avec une commande (exclut p.ex. une marmite [O,T] complète
                    # -> éviterait [O,O,T]). Si aucune : attendre/jeter (helper ci-dessous).
                    fill = self._valid_fill_pots(state, pot_states_dict, 'onion')
                    motion_goals, self.intentions['goal'] = self._put_in_pot_or_wait_actions(
                        state, player, pot_states_dict, fill)

            elif player_obj.name == 'tomato':
                # self.next_order.min_cost_to_complete == 10000 or self.next_order.min_cost_to_complete == 0 :
                if 'tomato' not in self.next_order_info["missing_ingredients_in_MA_pot"]:
                    # [POUBELLE] Tomate non requise : jeter (poubelle en priorité)
                    motion_goals, self.intentions['goal'] = self._discard_actions(state)
                # [CUTTING BOARD] découper la tomate avant de la mettre au pot si la recette l'exige.
                # Si la planche est occupée, la tomate reste nécessaire : on attend au lieu de la jeter.
                elif cutting_enabled and self._held_needs_chopping(player_obj):
                    # [ÉCHANGE] découpe / attente / passage au partenaire (intention posée dedans)
                    motion_goals = self._chop_or_wait_actions(state, player)
                else:
                    # [RECETTE VALIDE] cf. branche oignon : ne viser que les marmites où
                    # ajouter la tomate reste compatible avec une commande.
                    fill = self._valid_fill_pots(state, pot_states_dict, 'tomato')
                    motion_goals, self.intentions['goal'] = self._put_in_pot_or_wait_actions(
                        state, player, pot_states_dict, fill)

            elif player_obj.name == 'dish':
                self.intentions['goal'] = 'P'
                motion_goals = am.pickup_soup_with_dish_actions(
                    pot_states_dict, only_nearly_ready=True)
                # [ÉCHANGE] Ne garder que les marmites ATTEIGNABLES : si la seule soupe
                # prête/en cuisson est du côté du partenaire, motion_goals se vide et
                # _plate_or_wait_actions décide (passer l'assiette au partenaire / attendre).
                motion_goals = [mg for mg in motion_goals
                                if self.mlam.motion_planner.is_valid_motion_start_goal_pair(player.pos_and_or, mg)]
                if motion_goals == []:
                   # [ASSIETTE] Aucune soupe prête/en cuisson à emporter. Si une soupe
                   # est en cours d'assemblage, l'assiette reste nécessaire : attendre
                   # (STAY) au lieu de la poser/reprendre en boucle sur un comptoir
                   # (churn qui bloque le partenaire). Ne jeter que si rien n'arrive.
                   motion_goals, self.intentions['goal'] = self._plate_or_wait_actions(
                       state, player, pot_states_dict)

            elif player_obj.name == 'soup':
                if player_obj.recipe not in state.all_orders :
                    # [POUBELLE] Soupe non commandée : jeter (poubelle en priorité)
                    motion_goals, self.intentions['goal'] = self._discard_actions(state)
                else :
                    self.intentions['goal'] = 'S'
                    deliver = am.deliver_soup_actions()
                    reachable = [g for g in deliver
                                 if self.mlam.motion_planner.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
                    if reachable:
                        motion_goals = reachable
                    else:
                        # [ÉCHANGE] Service inatteignable par moi mais le partenaire peut
                        # livrer : lui passer la soupe (état le plus avancé) via l'échange.
                        handoff = self._handoff_if_partner_only(state, self.mlam.mdp.get_serving_locations())
                        if handoff is not None:
                            motion_goals, self.intentions['goal'] = handoff, 'X'
                        else:
                            motion_goals = deliver   # repli : sera filtré -> jeté si vraiment bloqué

            else:
                raise ValueError()

        motion_goals = [mg for mg in motion_goals if self.mlam.motion_planner.is_valid_motion_start_goal_pair(
            player.pos_and_or, mg)]

        if len(motion_goals) == 0:
            if self._intentional_wait:
                # [CUTTING BOARD] Attente volontaire d'une planche : le goal « sur place »
                # a pu être filtré (orientation courante ne faisant pas face à une feature).
                # NE PAS jeter l'ingrédient (il reste nécessaire) et NE PAS écraser
                # l'intention 'C'. Un goal factice suffit : action() court-circuitera en STAY.
                motion_goals = am.wait_actions(player)
            elif player.has_object():
                # [POUBELLE] Repli de rejet : poubelle en priorité, sinon comptoir/zone d'échange
                motion_goals, self.intentions['goal'] = self._discard_actions(state)
            else:
                motion_goals = am.go_to_closest_feature_actions(player)
            motion_goals = [mg for mg in motion_goals if self.mlam.motion_planner.is_valid_motion_start_goal_pair(
                player.pos_and_or, mg)]
            if len(motion_goals) ==0:
                motion_goals = am.go_to_closest_feature_actions(player)
                motion_goals = [mg for mg in motion_goals if self.mlam.motion_planner.is_valid_motion_start_goal_pair(
                player.pos_and_or, mg)]          
            
            assert len(motion_goals) != 0
        #breakpoint()
        return motion_goals

    def hl_info(self, state):

        def missing_ingredients_in_pot(recipe, pos):
            """
            computes the difference between recipe's ingredients and ingredients already present in pot
            """
            missing_ingredients = list(recipe.ingredients)
            if state.all_objects_by_type["soup"]:
                for soup in state.all_objects_by_type["soup"]:
                    if soup.position == pos and not soup.is_cooking and not soup.is_ready:
                        for ingredient in soup.ingredients:
                            if ingredient in missing_ingredients:
                                missing_ingredients.remove(ingredient)
            return missing_ingredients

        def calculate_recipe_cost(recipe, pot_pos):
            costs_dict = deepcopy(self.mlam.motion_planner.costs_dict)
            delivery_locations = self.mdp.get_serving_locations()
            onion_locations = self.mlam.mdp.get_onion_dispenser_locations()
            tomato_locations = self.mlam.mdp.get_tomato_dispenser_locations()
            onion_delivery_cost = self.mlam.motion_planner.min_cost_between_features(onion_locations, delivery_locations, manhattan_if_fail=False)
            tomato_delivery_cost = self.mlam.motion_planner.min_cost_between_features(tomato_locations, delivery_locations, manhattan_if_fail=False)
            cost = 0
            missing_ingredients = missing_ingredients_in_pot(recipe, pot_pos)
            for index, ingredient in enumerate(missing_ingredients) :
                if index ==0 :
                    if ingredient == 'onion' :
                        cost = self.mlam.motion_planner.min_cost_to_feature(state.players[self.agent_index].pos_and_or, onion_locations) + costs_dict['onion-pot'] 
                    else : 
                        cost = self.mlam.motion_planner.min_cost_to_feature(state.players[self.agent_index].pos_and_or, tomato_locations)# + costs_dict['tomato-pot']
                else :
                    if ingredient == 'onion' :
                            cost+= costs_dict['onion-pot'] * 2
                    else :
                            pass
                            #cost+= costs_dict['tomato-pot'] * 2
            # [CUTTING BOARD] coût additionnel de découpe (nb d'interactions) si la recette l'exige
            if getattr(self.mdp, 'cutting_enabled', False) and self.mdp.recipe_requires_chopping(recipe):
                for ingredient in missing_ingredients:
                    cost += self.mdp.get_chop_time(ingredient)
            return cost + costs_dict['pot-delivery'] + min([onion_delivery_cost, tomato_delivery_cost])

        def cost_to_complete(recipe, state):
            pot_locations = self.mlam.mdp.get_pot_locations().copy()
            missing_ingredients_in_pots = {}
            costs = {}
            for pos in pot_locations:
                if pos in state.objects.keys():
                    missing_ingredients_in_pots[pos] = missing_ingredients_in_pot(recipe, pos)

                    if len(missing_ingredients_in_pots[pos]) + len(state.objects[pos].ingredients) > recipe.MAX_NUM_INGREDIENTS : #test wether ingredients already in pot are compatible with order
                        costs[pos] = 10000 #arbitrary value allowing to drop onion on counter.
                    else:
                        costs[pos] = calculate_recipe_cost(recipe, pos)
                else:
                    missing_ingredients_in_pots[pos] = list(recipe.ingredients)
                    costs[pos] = calculate_recipe_cost(recipe, pos)
            min_cost_to_complete = min(costs.values())
            return  costs, min_cost_to_complete, missing_ingredients_in_pots

        def point_time_ratio(recipe, costs):
            pot_locations = self.mlam.mdp.get_pot_locations()
            if costs :
                point_time_ratio = recipe.value*10/(min(costs.values()) + recipe.time)
                most_advanced_pot = min(costs, key=costs.get) #so the min is calculated on value rather than key
            else :
                point_time_ratio = -1
                most_advanced_pot = pot_locations[0]
            return point_time_ratio, most_advanced_pot
        
        
        all_recipes = {}
        costs = {}
        cooking_or_ready_soups = [sorted(soup.ingredients) for soup in filter(lambda soup: soup.is_cooking or soup.is_ready, state.all_objects_by_type['soup'])]
        for index, recipe in enumerate(state.all_orders) :
            try:
                assert recipe.value is not None
            except AssertionError:
                recipe.configure(self.mdp.recipe_config)
            if list(recipe.ingredients) in cooking_or_ready_soups:
                continue            
            costs, min_cost_to_complete, missing_ingredients_in_pots = cost_to_complete(recipe, state)
            ratio, most_advanced_pot = point_time_ratio(recipe, costs)
            all_recipes[recipe] = {
                "recipe" : recipe,
                "costs" : costs,
                "min_cost_to_complete" : min_cost_to_complete,
                "point_time_ratio" : ratio,
                "most_advanced_pot" : most_advanced_pot,
                "value" : recipe.value,
                "missing_ingredients_in_MA_pot" : missing_ingredients_in_pot(recipe, most_advanced_pot)
                }
        # breakpoint()
            
        
        return all_recipes
        
        

class RationalAgent(PlanningAgent):
    def __init__(self, hl_boltzmann_rational=False, ll_boltzmann_rational=False, hl_temp=1, ll_temp=1, auto_unstuck=True):
        super().__init__(hl_boltzmann_rational, ll_boltzmann_rational, hl_temp, ll_temp, auto_unstuck)
        self.intentions["agent_name"] = "rational"
        self.switch_step = 0
        #print(self.intentions)

    def hl_action(self, state):
        all_recipes = self.hl_info(state)
        if len(all_recipes) == 0:
            return self.next_order_info
        cheapest = max(all_recipes, key= lambda key : all_recipes.get(key)["point_time_ratio"])  
        #print(self.hl_goal)
         # the cheapest recipe is the one from the all_recipes dict based on point time ratio of value dict 
        #cheapest = max(filter(lambda recipe : sorted(recipe.ingredients) not in cooking_or_ready_soups, all_recipes), key="point_time_ratio")
        if cheapest != self.hl_goal and self.switch_step % 5 == 0 :
            #cheapest.update_cost_to_complete(state, self.mlam, self.agent_index)
            #cheapest.update_point_time_ratio(self.mlam)
            # On ne compte un switch que si l'ancien objectif est ENCORE réalisable.
            # S'il a disparu de all_recipes (recette complétée / en cours de cuisson),
            # passer à la suivante n'est pas un changement d'avis.
            if self.hl_goal in all_recipes:
                self.hl_objective_switch += 1
            self.hl_goal =cheapest
            # breakpoint()
        self.switch_step += 1
        print("switch", self.switch_step, self.hl_objective_switch)
        cheapest_info = {
            "recipe" : all_recipes[cheapest]["recipe"],
            "most_advanced_pot" : all_recipes[cheapest]["most_advanced_pot"],
            "missing_ingredients_in_MA_pot" : all_recipes[cheapest]["missing_ingredients_in_MA_pot"],
            "point_time_ratio" : all_recipes[cheapest]["point_time_ratio"],
            "min_cost_to_complete" : all_recipes[cheapest]["min_cost_to_complete"]
            }
        print("here:  ",cheapest_info)
        return cheapest_info

class GreedyAgent(PlanningAgent):
    def __init__(self, hl_boltzmann_rational=False, ll_boltzmann_rational=False, hl_temp=1, ll_temp=1, auto_unstuck=True, ai_see_asset=True):
        super().__init__(hl_boltzmann_rational, ll_boltzmann_rational, hl_temp, ll_temp, auto_unstuck)
        self.intentions["agent_name"] = "greedy"
        self.ai_see_asset = ai_see_asset
        
        
    def hl_action(self, state):
        all_recipes = self.hl_info(state)
        if len(all_recipes) == 0:
            return self.next_order_info
        cheapest = max(all_recipes, key= lambda key : all_recipes.get(key)["value"])
        #cheapest = max(filter(lambda recipe : sorted(recipe.ingredients) not in cooking_or_ready_soups, all_recipes), key="point_time_ratio")
        # [ÉCHANGE] Recette cible STABLE et ACCUMULATIVE pilotée par les ingrédients ENGAGÉS
        # dans le pipeline (_committed_ingredients) : la meilleure recette (par valeur) dont le
        # multiensemble engagé reste un SOUS-MULTIENSEMBLE (donc encore complétable). Chaque
        # tomate qui entre fait grimper l'objectif ([O,O,O]->[O,O,T]->[O,T,T]) et l'objectif
        # RESTE stable tant que la tomate est dans le pipeline (au lieu de « redescendre » vers
        # [O,O,O] dès qu'elle est repassée). Équivaut au value-max quand rien n'est imposé
        # (le multiensemble engagé est alors sous-ensemble de la recette de plus haute valeur).
        # No-op hors layout d'échange (counter_goals vide -> value-max historique inchangé).
        forced = False
        if self.mlam.mdp.counter_goals:
            committed = self._committed_ingredients(state)
            compatible = [r for r in all_recipes
                          if all(committed[i] <= Counter(r.ingredients)[i] for i in committed)]
            if compatible:
                cheapest = max(compatible, key=lambda r: all_recipes[r]["value"])
            # [hl_switch] Changement IMPOSÉ = le pipeline engagé n'est PLUS compatible avec
            # l'objectif courant (une tomate reçue le dépasse) -> il FAUT changer sinon la
            # recette visée est incomplétable (aucune action scorante). Les changements
            # VOLONTAIRES ne satisfont pas cette condition et ne comptent pas : re-choix par
            # valeur, recette suivante après livraison, et retour au défaut une fois la soupe
            # en cuisson (pipeline vidé -> committed vide -> compatible avec tout).
            if self.hl_goal is not None and self.hl_goal in all_recipes:
                hg = Counter(self.hl_goal.ingredients)
                forced = any(committed[i] > hg[i] for i in committed)
        if cheapest != self.hl_goal :
            #cheapest.update_cost_to_complete(state, self.mlam, self.agent_index)
            #cheapest.update_point_time_ratio(self.mlam)
            if forced:
                self.hl_objective_switch += 1
            self.hl_goal =cheapest
        cheapest_info = {
            "recipe" : all_recipes[cheapest]["recipe"],
            "most_advanced_pot" : all_recipes[cheapest]["most_advanced_pot"],
            "missing_ingredients_in_MA_pot" : all_recipes[cheapest]["missing_ingredients_in_MA_pot"],
            "point_time_ratio" : all_recipes[cheapest]["point_time_ratio"],
            "min_cost_to_complete" : all_recipes[cheapest]["min_cost_to_complete"]
            }
        #breakpoint()
        return cheapest_info

class LazyAgent(PlanningAgent):
    def __init__(self, hl_boltzmann_rational=False, ll_boltzmann_rational=False, hl_temp=1, ll_temp=1, auto_unstuck=True):
        super().__init__(hl_boltzmann_rational, ll_boltzmann_rational, hl_temp, ll_temp, auto_unstuck)
        self.intentions["agent_name"] = "lazy" 
    def hl_action(self, state):
        cooking_or_ready_soups = [sorted(soup.ingredients) for soup in filter(lambda soup: soup.is_cooking or soup.is_ready, state.all_objects_by_type['soup'])]
        for recipe in state.all_orders :
            recipe.update_cost_to_complete(state, self.mlam, self.agent_index)
            recipe.update_point_time_ratio(self.mlam)

        candidates = [recipe for recipe in state.all_orders if sorted(recipe.ingredients) not in cooking_or_ready_soups]
        shortest = min(candidates, key=attrgetter("min_cost_to_complete"))
        if shortest != self.hl_goal :
            # On ne compte un switch que si l'ancien objectif est ENCORE réalisable.
            # S'il n'est plus candidat (recette complétée / en cours de cuisson),
            # passer à la suivante n'est pas un changement d'avis.
            if self.hl_goal in candidates:
                self.hl_objective_switch += 1
            self.hl_goal = shortest
        return shortest

class SampleAgent(Agent):
    """ Agent that samples action using the average action_probs across multiple agents
    """

    def __init__(self, agents):
        self.agents = agents

    def action(self, state):
        action_probs = np.zeros(Action.NUM_ACTIONS)
        for agent in self.agents:
            action_probs += agent.action(state)[1]["action_probs"]
        action_probs = action_probs/len(self.agents)
        return Action.sample(action_probs), {"action_probs": action_probs}
    """
    """
# Deprecated. Need to fix Heuristic to work with the new MDP to reactivate Planning
# class CoupledPlanningAgent(Agent):
#     """
#     An agent that uses a joint planner (mlp, a MediumLevelPlanner) to find near-optimal
#     plans. At each timestep the agent re-plans under the assumption that the other agent
#     is also a CoupledPlanningAgent, and then takes the first action in the plan.
#     """
#
#     def __init__(self, mlp, delivery_horizon=2, heuristic=None):
#         self.mlp = mlp
#         self.mlp.failures = 0
#         self.heuristic = heuristic if heuristic is not None else Heuristic(mlp.mp).simple_heuristic
#         self.delivery_horizon = delivery_horizon
#
#     def action(self, state):
#         try:
#             joint_action_plan = self.mlp.get_low_level_action_plan(state, self.heuristic, delivery_horizon=self.delivery_horizon, goal_info=True)
#         except TimeoutError:
#             print("COUPLED PLANNING FAILURE")
#             self.mlp.failures += 1
#             return Direction.ALL_DIRECTIONS[np.random.randint(4)]
#         return (joint_action_plan[0][self.agent_index], {}) if len(joint_action_plan) > 0 else (Action.STAY, {})
#
#
# class EmbeddedPlanningAgent(Agent):
#     """
#     An agent that uses A* search to find an optimal action based on a model of the other agent,
#     `other_agent`. This class approximates the other agent as being deterministic even though it
#     might be stochastic in order to perform the search.
#     """
#
#     def __init__(self, other_agent, mlp, env, delivery_horizon=2, logging_level=0):
#         """mlp is a MediumLevelPlanner"""
#         self.other_agent = other_agent
#         self.delivery_horizon = delivery_horizon
#         self.mlp = mlp
#         self.env = env
#         self.h_fn = Heuristic(mlp.mp).simple_heuristic
#         self.logging_level = logging_level
#
#     def action(self, state):
#         start_state = state.deepcopy()
#         order_list = start_state.order_list if start_state.order_list is not None else ["any", "any"]
#         start_state.order_list = order_list[:self.delivery_horizon]
#         other_agent_index = 1 - self.agent_index
#         initial_env_state = self.env.state
#         self.other_agent.env = self.env
#
#         expand_fn = lambda state: self.mlp.get_successor_states_fixed_other(state, self.other_agent, other_agent_index)
#         goal_fn = lambda state: len(state.order_list) == 0
#         heuristic_fn = lambda state: self.h_fn(state)
#
#         search_problem = SearchTree(start_state, goal_fn, expand_fn, heuristic_fn, max_iter_count=50000)
#
#         try:
#             ml_s_a_plan, cost = search_problem.A_star_graph_search(info=True)
#         except TimeoutError:
#             print("A* failed, taking random action")
#             idx = np.random.randint(5)
#             return Action.ALL_ACTIONS[idx]
#
#         # Check estimated cost of the plan equals
#         # the sum of the costs of each medium-level action
#         assert sum([len(item[0]) for item in ml_s_a_plan[1:]]) == cost
#
#         # In this case medium level actions are tuples of low level actions
#         # We just care about the first low level action of the first med level action
#         first_s_a = ml_s_a_plan[1]
#
#         # Print what the agent is expecting to happen
#         if self.logging_level >= 2:
#             self.env.state = start_state
#             for joint_a in first_s_a[0]:
#                 print(self.env)
#                 print(joint_a)
#                 self.env.step(joint_a)
#             print(self.env)
#             print("======The End======")
#
#         self.env.state = initial_env_state
#
#         first_joint_action = first_s_a[0][0]
#         if self.logging_level >= 1:
#             print("expected joint action", first_joint_action)
#         action = first_joint_action[self.agent_index]
#         return action, {}
#

# Deprecated. Due to Heuristic and MLP
# class CoupledPlanningPair(AgentPair):
#     """
#     Pair of identical coupled planning agents. Enables to search for optimal
#     action once rather than repeating computation to find action of second agent
#     """
#
#     def __init__(self, agent):
#         super().__init__(agent, agent, allow_duplicate_agents=True)
#
#     def joint_action(self, state):
#         # Reduce computation by half if both agents are coupled planning agents
#         joint_action_plan = self.a0.mlp.get_low_level_action_plan(state, self.a0.heuristic, delivery_horizon=self.a0.delivery_horizon, goal_info=True)
#
#         if len(joint_action_plan) == 0:
#             return ((Action.STAY, {}), (Action.STAY, {}))
#
#         joint_action_and_infos = [(a, {}) for a in joint_action_plan[0]]
#         return joint_action_and_infos
