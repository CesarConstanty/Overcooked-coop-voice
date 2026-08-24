"""agent_coop.py — GreedyCoopAgent : agent greedy COOPÉRATIF pour le jeu (humain + IA).

Réutilise la politique `CoopExchangePolicy` de `simulation_exchange.py` (relais coopératif
décidé par ESTIMATION du gain en pas, sur layout CONNEXE doté de zones d'échange 'Y').
Face à un partenaire HUMAIN, l'IA OBSERVE le joueur et prend le rôle COMPLÉMENTAIRE
(cook si le joueur prépare, prep s'il cuisine) via `CoopExchangePolicy.solo_action` — le
même code que le mode `--mode manual` de `simulation_exchange.py`.

SÉLECTION EN CONFIG : mettre `"agent": "GreedyCoop"` (au lieu de `"Greedy"`) dans le bloc
de config. Le reste du pipeline de jeu (`PlanningGame`) est INCHANGÉ : `GreedyCoopAgent`
EST un `GreedyAgent`, il expose donc `intentions` / `chosen_goal` / `motion_goal` /
`stuck_frames` / `hl_objective_switch` / `forced_recipe` / `forced_subtask` comme attendu
par `game.py` (visuel des intentions, ralentissements, journalisation).

REPLI (jamais de crash) : sur un layout NON coop-exploitable (pas de zones + découpe +
assiette + marmite, ou régions séparées), l'agent se comporte EXACTEMENT comme un
`GreedyAgent` classique (`super().action`) — le greedy natif gère déjà le relais des
layouts séparés (cf. `overcooked_ai_py/agents/agent.py`). Toute erreur d'initialisation
ou d'exécution de la couche coopérative retombe silencieusement sur le greedy.

Import PARESSEUX de `simulation_exchange` (dans `_build_coop`) : évite l'import circulaire
`game -> agent_coop -> simulation_exchange -> game` au chargement, et ne déclenche le
neutralisant de `JointMotionPlanner._populate_all_plans` (effet de bord de module de
`simulation_exchange`, sans incidence : le jeu n'utilise jamais les plans joints) que
lorsqu'un `GreedyCoop` est effectivement joué.
"""
import logging

import numpy as np

from overcooked_ai_py.agents.agent import GreedyAgent
from overcooked_ai_py.mdp.actions import Action, Direction

logger = logging.getLogger("overcooked.agent_coop")


class GreedyCoopAgent(GreedyAgent):
    """GreedyAgent enrichi d'une couche de coopération adaptative (CoopExchangePolicy).

    Construit la politique coopérative PARESSEUSEMENT au 1er `action()`, une fois `mdp` et
    `mlam` injectés par `PlanningGame.activate()`. Reflète ensuite sur SOI (le wrapper) les
    intentions / buts du cerveau greedy interne quand l'IA joue le rôle COOK, et une
    intention dérivée (best-effort) quand elle joue le rôle PREP, afin que le système
    d'intentions du jeu (visuel + ralentissements) reste cohérent."""

    def __init__(self, *args, ai_see_asset=True, **kwargs):
        super().__init__(*args, ai_see_asset=ai_see_asset, **kwargs)
        self.intentions["agent_name"] = "greedy_coop"
        self._coop = None
        self._t = 0                    # compteur de décisions (hystérésis de bascule de rôle)
        self._coop_crash_logged = False
        self._shared_recipe = None     # recette cible partagée (stable entre les bascules de rôle)
        self._chopped = None           # helper simulation_exchange.chopped (stocké à la construction)
        self._stuck_frames = 0
        self._prev_block_pos = None

    def reset(self):
        super().reset()
        self._coop = None
        self._t = 0
        self._coop_crash_logged = False
        self._shared_recipe = None
        self._stuck_frames = 0
        self._prev_block_pos = None

    def _build_coop(self):
        """Construit `CoopExchangePolicy` si le layout s'y prête (CONNEXE + exploitable),
        sinon marque le repli greedy (`_coop = False`). Réplique la décision de
        `simulation_exchange.run_manual` (partenaire IA adaptatif vs greedy simple)."""
        import simulation
        from simulation_exchange import (
            CoopExchangePolicy, components, _connected_exploitable, chopped,
        )
        self._chopped = chopped
        mdp, mlam = self.mdp, self.mlam
        cg = list(mdp.counter_goals or [])
        comp_of = components(simulation.build_neighbors(mdp))
        s0, s1 = mdp.start_player_positions
        connected = comp_of.get(s0) is not None and comp_of.get(s0) == comp_of.get(s1)
        if connected and _connected_exploitable(mdp, cg):
            self._coop = CoopExchangePolicy(mdp, mlam, cg)
            logger.info("GreedyCoop(idx%d) : couche coopérative ACTIVE (layout '%s' connexe "
                        "exploitable, %d zone(s) d'échange)", self.agent_index,
                        getattr(mdp, "layout_name", "?"), len(self._coop.exchange))
        else:
            self._coop = False
            logger.info("GreedyCoop(idx%d) : layout '%s' non coop-exploitable -> repli greedy "
                        "classique", self.agent_index, getattr(mdp, "layout_name", "?"))

    # ------------------------------------------------------------------
    # Décision
    # ------------------------------------------------------------------
    def action(self, state):
        if self._coop is None:
            try:
                self._build_coop()
            except Exception:
                logger.exception("GreedyCoop : échec de construction de la couche coopérative "
                                 "-> repli greedy définitif pour cet essai")
                self._coop = False
        if self._coop:
            try:
                # `t` démarre à 0 puis s'incrémente (comme `run_manual` de simulation_exchange) :
                # il ne sert qu'à l'hystérésis de bascule de rôle (ROLE_DWELL) dans solo_action.
                act = self._coop.solo_action(state, self.agent_index, self._t)
                self._t += 1
                if act is None:
                    act = Action.STAY
                act = self._anti_block(state, act)
                self._mirror_intentions(state)
                return act, {"action_probs": self.a_probs_from_action(act)}
            except Exception:
                # Une erreur de la couche coopérative ne doit JAMAIS figer le jeu : on retombe
                # sur le greedy natif (comportement dégradé mais fonctionnel) et on loggue une fois.
                if not self._coop_crash_logged:
                    logger.exception("GreedyCoop : solo_action a échoué -> repli greedy pour ce tick")
                    self._coop_crash_logged = True
        return super().action(state)

    # ------------------------------------------------------------------
    # Anti-blocage ROLE-AGNOSTIQUE (face à un humain) + comptage de stuck_frames
    # ------------------------------------------------------------------
    def _anti_block(self, state, act):
        """Débloque l'IA et compte `stuck_frames`, QUEL QUE SOIT le rôle (cook OU prep).

        Pourquoi ici et pas dans le cerveau greedy : l'`auto_unstuck` natif ne tourne QUE quand
        l'IA joue COOK (le PREP se déplace via `prep_action`/`_nav`, sans ce mécanisme) et son
        compteur n'avance que par intermittence -> une IA-prep coincée par le joueur dans un
        couloir 1-large PIÉTINAIT sans jamais être débloquée NI comptée (d'où `agent_stuck_loop=0`
        trompeur dans les traces). Le wrapper, lui, voit CHAQUE décision.

        Règle : blocage = l'IA VEUT avancer vers une case FRANCHISSABLE mais le PARTENAIRE
        l'occupe (vrai deadlock de couloir 1-large). Après 2 frames bloquées, on choisit un pas
        latéral vers une case LIBRE pour briser la symétrie (partenaire supposé immobile). Un
        « pas » vers un mur/comptoir n'est PAS un blocage : c'est une RÉORIENTATION pour interagir
        (déposer/découper) — sinon on ferait dériver l'IA en pleine découpe. Les STAY / INTERACT
        volontaires (throttle, park, attente) ne sont pas comptés non plus."""
        me = self.agent_index
        cur = state.players[me].position
        partner_pos = state.players[1 - me].position
        orient = state.players[me].orientation
        wants_move = act not in (Action.STAY, Action.INTERACT)
        blocked = wants_move and self._steps_onto(cur, orient, act) == partner_pos
        if blocked:
            self._stuck_frames = self._stuck_frames + 1 if cur == self._prev_block_pos else 1
            self._prev_block_pos = cur
            if self._stuck_frames >= 2:
                alt = self._pick_unblock(cur, orient, partner_pos)
                if alt is not None:
                    act = alt
        else:
            self._stuck_frames = 0
            self._prev_block_pos = None
        self.stuck_frames = self._stuck_frames         # reflété pour la journalisation (agent_stuck_loop)
        return act

    def _steps_onto(self, cur, orient, act):
        """Case où l'IA IRAIT avec `act` (terrain seul) ; == `cur` si c'est un mur/comptoir."""
        return self.mdp._move_if_direction(cur, orient, act)[0]

    def _pick_unblock(self, cur, orient, partner_pos):
        """Un pas (parmi N/S/E/O) menant vers une case LIBRE (ni mur/comptoir, ni le partenaire),
        tiré au hasard pour ne pas rejouer indéfiniment la direction bloquée ; None si encaissée."""
        cands = [d for d in Direction.ALL_DIRECTIONS
                 if self._steps_onto(cur, orient, d) not in (cur, partner_pos)]
        if not cands:
            return None
        return cands[np.random.randint(len(cands))]

    # ------------------------------------------------------------------
    # Miroir des intentions (pour le visuel / les ralentissements du jeu)
    # ------------------------------------------------------------------
    def _mirror_intentions(self, state):
        """Refléter sur le wrapper (lu par `game.py`) l'état du cerveau greedy interne quand
        l'IA joue COOK ; sinon dériver une intention best-effort du rôle PREP. La recette
        cible est maintenue STABLE entre les bascules de rôle pour ne pas faire flapper le
        déclencheur de ralentissement « changement de recette »."""
        pol = self._coop
        cook = pol.cook
        # Champs journalisés / cumulatifs : toujours refléter le cerveau cook. NB : `stuck_frames`
        # n'est PLUS pris ici (le cerveau cook ne tourne qu'en rôle COOK et compterait faux) : il
        # est tenu par `_anti_block`, role-agnostique et calé sur la cadence réelle des décisions.
        self.hl_objective_switch = cook.hl_objective_switch
        self.next_order_info = cook.next_order_info
        cook_recipe = cook.intentions.get("recipe")
        if cook_recipe is not None:
            self._shared_recipe = cook_recipe
        if pol.cook_i == self.agent_index:
            # L'IA joue COOK : intentions/buts exacts du greedy interne.
            self.intentions = {**cook.intentions, "recipe": self._shared_recipe,
                               "agent_name": "greedy_coop"}
            self.chosen_goal = cook.chosen_goal
            self.motion_goal = cook.motion_goal
        else:
            # L'IA joue PREP : intention dérivée (planche/assiette/relais).
            self.intentions = {"recipe": self._shared_recipe,
                               "goal": self._prep_goal_code(state),
                               "agent_name": "greedy_coop"}
            # Pas de but de mouvement distinct exposé pour le prep (le greedy interne n'a pas
            # tourné) : le jeu n'affiche alors pas de cible fantôme.
            self.chosen_goal = state.players[self.agent_index].pos_and_or
            self.motion_goal = None

    def _prep_goal_code(self, state):
        """Code d'asset ('C'/'P'/'D'/'S'/'X') approximant l'objectif du prep, pour le visuel
        d'intentions et les ralentissements — dérivé sans planificateur de l'objet tenu et de
        l'état des planches/assiettes (cf. codes de `agent.py`)."""
        p = state.players[self.agent_index]
        if p.has_object():
            o = p.get_object()
            if o.name in ("onion", "tomato"):
                return "C" if not self._chopped(o) else "P"   # brut -> planche ; coupé -> (relayé vers) marmite
            if o.name == "dish":
                return "D"
            if o.name == "soup":
                return "S"
            return "X"
        # mains vides : une planche à travailler (découper / récupérer le coupé) ?
        for b in self._coop.boards:
            if state.has_object(b):
                return "C"
        # sinon fournir une assiette au cook si une soupe est en cours ?
        if self._coop.dishes and self._coop._dish_needed(state):
            return "D"
        return "X"
