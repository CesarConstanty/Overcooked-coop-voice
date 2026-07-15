#!/usr/bin/env python3
"""simulation_exchange.py — Deux GreedyAgent qui EXPLOITENT les zones d'échange (Y).

Contexte (vérifié dans le code) : un GreedyAgent ne dépose JAMAIS spontanément sur un
comptoir pour aider le partenaire — il ne pose sur un `X`/`Y` que pour *jeter* un objet
inutile ou en repli quand sa cible est inatteignable (overcooked_ai_py/agents/agent.py).
Sur un layout CONNEXE (tout lui est accessible) il ignore donc les passes et fait le tour.

Pour qu'on VOIE les deux greedy exploiter les passes, ce script ajoute DEUX politiques de
relais, choisies selon la STRUCTURE du layout (cf. `_make_policy`) :

1. `ExchangePolicy` — layout SÉPARÉ : les deux agents démarrent dans DEUX COMPOSANTES
   praticables distinctes reliées seulement par des passes Y (ex. test_exchange_forced).
   Rôles ÉMERGENTS : CUISINE = agent de la composante contenant la marmite (vrai
   GreedyAgent : recette / remplissage / cuisson / dressage / service) ; PREP = l'autre
   (processeur : découpe ce qui lui arrive, fournit des assiettes, relaie le reste). Routage
   par appartenance à une composante : un objet dont la station est « de l'autre côté » est
   DÉPOSÉ sur la passe pont, le partenaire l'y reprend — brut->planche(C), coupé->marmite(P),
   assiette->marmite(P), soupe->service(S). Anti-churn : on ne reprend jamais ce qu'on vient
   de poster.

2. `CoopExchangePolicy` — layout CONNEXE (les deux agents atteignent TOUT ; les passes ne
   sont que des RACCOURCIS). Là, ExchangePolicy dégénère (pas de composantes séparées) et
   les deux greedy feraient le tour complet. On rétablit un pipeline dont l'usage des zones
   est décidé — COMME DEMANDÉ — par ESTIMATION du gain en pas, l'agent OBSERVANT la position
   de son partenaire : il ne dépose sur une zone que s'il estime y gagner des pas vs livrer
   lui-même (le partenaire, mieux placé, termine). Voir la docstring de la classe.

Objectif mesuré : NOMBRE DE STEPS pour livrer TOUTES les commandes, AVEC zones (relais)
vs SANS zones (deux greedy libres, passes = murs). « Steps minimum avec usage OPTIMAL des
zones » = min(AVEC, SANS) : utiliser les zones quand elles aident, s'en passer sinon.

NB (résultats) : les zones font GAGNER (ou rendent RÉALISABLE) le niveau quand la topologie
FORCE la coopération : régions séparées reliées uniquement par les passes (test_exchange_
forced : 7/7 AVEC, infaisable SANS) ou couloir/cul-de-sac où deux greedy libres s'inter-
bloquent (test_exchange_benefit2 : 7/7 AVEC, infaisable SANS). Sur un layout CONNEXE OUVERT
(boucle), deux greedy libres parallélisent déjà mieux et le relais est plus LENT
(test_exchange_benefit) — résultat mesuré et rapporté tel quel.

Perf : le MediumLevelActionManager complet précalcule un JointMotionPlanner en O(P^4)
(30-40 min ici). Le GreedyAgent n'utilise QUE le MotionPlanner mono-agent : on neutralise
donc `_populate_all_plans` -> mlam construit instantanément, comportement inchangé.

Exemples :
  python simulation_exchange.py --mode compare
  python simulation_exchange.py --mode visual                 # relais général (utilise les Y)
  python simulation_exchange.py --mode visual --no-relay      # greedy libre (ignore les Y)
  python simulation_exchange.py --mode manual                 # JOUER soi-même avec un greedy
  python simulation_exchange.py --mode manual --layout test_exchange_forced --human-index 1
"""
import argparse
import json
import logging
import os
from collections import deque
from copy import copy

import numpy as np
import random

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.actions import Action
from overcooked_ai_py.planning import planners as _PL
from overcooked_ai_py.planning.planners import MediumLevelActionManager, COUNTERS_MLG_PARAMS
from overcooked_ai_py.agents.agent import GreedyAgent
import game
import simulation  # build_neighbors, coop_deconflict, _import_state_visualizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("overcooked.simulation_exchange")

# --- Neutralise le JointMotionPlanner (O(P^4)) : un greedy ne consulte jamais les plans
#     joints, seulement joint_motion_planner.motion_planner (mono-agent). -------------
_PL.JointMotionPlanner._populate_all_plans = lambda self: {}

DEFAULT_LAYOUT = "test_exchange_forced"   # variante FORCÉE : montre le gain des zones
DEFAULT_LAYOUTS_DIR = "overcooked_ai_py/data/layouts/generation_cesar_2"
DEFAULT_CONFIG_BLOCK = "config_test_visual"

INF = float("inf")


def chopped(o):
    return bool(getattr(o, "chopped", False))


# ---------------------------------------------------------------------------
# Environnement (mlam allégé : plans joints neutralisés)
# ---------------------------------------------------------------------------
def build_env(layout, layouts_dir, config, exchange=True):
    """(mdp, mlam, counter_goals). `exchange`=True -> passes Y utilisables ; False ->
    counter_goals vidé (les Y redeviennent de simples murs : baseline « sans zone »)."""
    mdp_params = dict(OvercookedGridworld.mdp_overrides_from_config(config))
    mdp_t, _ = game.get_cached_mdp(layout, layouts_dir, mdp_params)
    mdp = copy(mdp_t)
    cp = dict(COUNTERS_MLG_PARAMS)
    goals = list(mdp.counter_goals) if (exchange and mdp.counter_goals) else []
    cp["counter_goals"] = cp["counter_drop"] = cp["counter_pickup"] = goals
    mlam = MediumLevelActionManager(mdp, cp)
    return mdp, mlam, goals


def make_greedy(mdp, mlam, idx, ai_see_asset=True, auto_unstuck=False):
    # auto_unstuck=False par défaut : dans compare/visual la couche coop_deconflict gère les
    # collisions. En jeu MANUEL (partenaire humain, pas de coop_deconflict) on passe True pour
    # que l'IA se dégage seule si elle reste coincée contre le joueur.
    a = GreedyAgent(auto_unstuck=auto_unstuck, ai_see_asset=ai_see_asset)
    a.reset()
    a.set_agent_index(idx)
    a.mdp = mdp
    a.mlam = mlam
    return a


def stand_tiles(mdp, feat_pos):
    x, y = feat_pos
    valid = set(mdp.get_valid_player_positions())
    return [n for n in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)] if n in valid]


def components(neighbors):
    """comp_of[case] = id de la composante connexe praticable (BFS)."""
    comp_of, cid = {}, 0
    for s in neighbors:
        if s in comp_of:
            continue
        q = deque([s]); comp_of[s] = cid
        while q:
            u = q.popleft()
            for v in neighbors[u].values():
                if v not in comp_of:
                    comp_of[v] = cid; q.append(v)
        cid += 1
    return comp_of


def all_pairs_dist(neighbors):
    """dist[a][b] = nb de pas praticables a->b (inf si b hors de la composante de a)."""
    dist = {}
    for src in neighbors:
        d = {src: 0}; q = deque([src])
        while q:
            u = q.popleft()
            for v in neighbors[u].values():
                if v not in d:
                    d[v] = d[u] + 1; q.append(v)
        dist[src] = d
    return dist


def feature_comps(mdp, comp_of, feat_locs):
    """Ensemble des composantes qui BORDENT au moins une feature de la liste."""
    return {comp_of[s] for f in feat_locs for s in stand_tiles(mdp, f) if s in comp_of}


# ---------------------------------------------------------------------------
# Politiques : greedy libre (baseline) et relais à rôles (utilise les passes)
# ---------------------------------------------------------------------------
class GreedyPair:
    """Baseline : deux GreedyAgent libres (référence « sans zones »)."""

    def __init__(self, mdp, mlam):
        self.ags = [make_greedy(mdp, mlam, i) for i in (0, 1)]

    def joint(self, state, t):
        return tuple(a.action(state)[0] for a in self.ags)


class _Shim:
    """Expose .chosen_goal pour coop_deconflict quand un rôle n'est pas un GreedyAgent."""
    def __init__(self):
        self.chosen_goal = ((0, 0), (0, 0))


class ExchangePolicy:
    """Relais GÉNÉRAL, sans hypothèse de géométrie (ni coupe y, ni rôles fixes).

    Les deux agents démarrent dans deux COMPOSANTES praticables distinctes reliées par
    des passes Y. Rôles et flux ÉMERGENT de l'emplacement des features :
      * CUISINE  = agent dont la composante contient la marmite -> vrai GreedyAgent
        (gère recette / remplissage / cuisson / dressage / service) ;
      * PREP     = l'autre agent -> processeur explicite (découpe ce qui lui arrive,
        fournit des assiettes si son distributeur est de son côté, relaie le reste).
    Règle unique de routage : un agent tenant un objet dont la station de DESTINATION
    n'est PAS dans sa composante le DÉPOSE sur la passe libre la plus proche pontant vers
    la composante qui a cette station ; le partenaire l'y récupère (son greedy voit les
    objets posés) et poursuit. Destinations : brut->planche(C), coupé->marmite(P),
    assiette->marmite(P, dressage), soupe->service(S). Fonctionne quel que soit le sens
    (haut/bas, gauche/droite…) et le nombre de passes (>=1)."""

    def __init__(self, mdp, mlam, counter_goals):
        self.mdp, self.mlam, self.mp = mdp, mlam, mlam.motion_planner
        self.neighbors = simulation.build_neighbors(mdp)
        self.comp_of = components(self.neighbors)
        self.dist = all_pairs_dist(self.neighbors)
        self.cutting = bool(getattr(mdp, "cutting_enabled", False))
        self.boards = mdp.get_cutting_board_locations()
        self.dishes = mdp.get_dish_dispenser_locations()
        self.feat_locs = {"C": self.boards, "P": mdp.get_pot_locations(), "S": mdp.get_serving_locations()}
        self.feat_comps = {ft: feature_comps(mdp, self.comp_of, locs)
                           for ft, locs in self.feat_locs.items()}
        # passes « pont » : counter_goal touchant >=2 composantes ; 1 case d'accès / composante
        self.bridges = {}
        for c in counter_goals:
            m = {}
            for s in stand_tiles(mdp, c):
                m.setdefault(self.comp_of[s], s)
            if len(m) >= 2:
                self.bridges[c] = m
        starts = mdp.start_player_positions
        self.comp = [self.comp_of[starts[0]], self.comp_of[starts[1]]]
        # CUISINE = composante contenant la marmite ; PREP = l'autre
        self.cook_i = 0 if self.comp[0] in self.feat_comps["P"] else 1
        self.prep_i = 1 - self.cook_i
        self.cook_comp, self.prep_comp = self.comp[self.cook_i], self.comp[self.prep_i]
        self.boards_prep = [b for b in self.boards
                            if self.prep_comp in feature_comps(mdp, self.comp_of, [b])]
        self.dishes_prep = [d for d in self.dishes
                            if self.prep_comp in feature_comps(mdp, self.comp_of, [d])]
        self.cook = make_greedy(mdp, mlam, self.cook_i, ai_see_asset=False)
        # cases (côté cuisine) des passes -> pont, pour l'anti-churn
        self.cook_bridge_stands = {m[self.cook_comp]: c for c, m in self.bridges.items()
                                   if self.cook_comp in m}
        self._prep_shim = _Shim()
        self._shims = [None, None]
        self._shims[self.cook_i] = self.cook
        self._shims[self.prep_i] = self._prep_shim
        self._shims = tuple(self._shims)

    # ------- utilitaires -------
    def _dest(self, held):
        """Type de station de destination de l'objet tenu (C/P/S), ou None."""
        if held.name in ("onion", "tomato"):
            return "C" if (self.cutting and not chopped(held)) else "P"
        if held.name == "dish":
            return "P"
        if held.name == "soup":
            return "S"
        return None

    def _other(self, comp):
        return self.prep_comp if comp == self.cook_comp else self.cook_comp

    def _nav(self, player, cells):
        """Vers la station la plus proche parmi `cells` (INTERACT à l'arrivée)."""
        goals = []
        for c in cells:
            goals += self.mlam._get_ml_actions_for_positions([c])
        goals = [g for g in goals if self.mp.is_valid_motion_start_goal_pair(player.pos_and_or, g)]
        if not goals:
            return None
        best, bc = None, 1e9
        for g in goals:
            plan, _, c = self.mp.get_plan(player.pos_and_or, g)
            if c < bc:
                bc, best = c, (plan[0] if plan else Action.STAY)
        return best

    def _go_counter(self, player, c, near):
        goals = [g for g in self.mlam._get_ml_actions_for_positions([c]) if g[0] == near]
        if not goals or not self.mp.is_valid_motion_start_goal_pair(player.pos_and_or, goals[0]):
            return None
        plan, _, _ = self.mp.get_plan(player.pos_and_or, goals[0])
        return plan[0] if plan else None

    def _relay(self, player, from_comp, to_comp, state):
        """Déposer l'objet tenu sur la passe LIBRE la plus proche pontant from->to.
        None si aucune passe libre (l'appelant fait STAY)."""
        dp = self.dist.get(player.position, {})
        cands = []
        for c, m in self.bridges.items():
            if from_comp in m and to_comp in m and not state.has_object(c):
                cands.append((dp.get(m[from_comp], 1e9), c, m[from_comp]))
        if not cands:
            return None
        cands.sort()
        return self._go_counter(player, cands[0][1], cands[0][2])

    def _dish_needed(self, state):
        ps = self.mdp.get_pot_states(state)
        return bool(ps.get("ready") or ps.get("cooking")
                    or self.mdp.get_partially_full_pots(ps)
                    or ps.get("2_items") or ps.get("3_items"))

    # ------- rôle CUISINE : greedy + relais de tout objet destiné à l'autre zone -------
    def cook_action(self, state):
        p = state.players[self.cook_i]
        held = p.get_object() if p.has_object() else None
        act, _ = self.cook.action(state)      # calcule d'abord (met à jour chosen_goal)
        if held is not None:
            ft = self._dest(held)
            if ft is not None and self.cook_comp not in self.feat_comps.get(ft, set()):
                r = self._relay(p, self.cook_comp, self._other(self.cook_comp), state)
                return r if r is not None else Action.STAY
            return act
        # ANTI-CHURN / DIRECTIONNEL : ne pas REPRENDRE sur une passe un objet EN TRANSIT vers
        # l'autre zone (celui qu'on vient d'y poster). Recalcul de la décision sans cet objet.
        cg = self.cook.chosen_goal
        if cg is not None and cg[0] in self.cook_bridge_stands:
            c = self.cook_bridge_stands[cg[0]]
            if state.has_object(c):
                it = state.get_object(c); ft = self._dest(it)
                if ft is not None and self.cook_comp not in self.feat_comps.get(ft, set()):
                    s2 = state.deepcopy(); s2.remove_object(c)
                    act, _ = self.cook.action(s2)
        return act

    # ------- rôle PREP : processeur explicite (découpe / assiettes / relais) -------
    def prep_action(self, state):
        p = state.players[self.prep_i]
        held = p.get_object() if p.has_object() else None
        if held is not None:
            ft = self._dest(held)
            if ft == "C" and self.boards_prep:
                empty = [b for b in self.boards_prep if not state.has_object(b)]
                return self._nav(p, empty) or Action.STAY               # poser le brut sur une planche
            if ft is not None and self.prep_comp in self.feat_comps.get(ft, set()):
                return self._nav(p, self.feat_locs[ft]) or Action.STAY   # station locale (rare)
            r = self._relay(p, self.prep_comp, self._other(self.prep_comp), state)
            return r if r is not None else Action.STAY
        # mains vides : finir / récupérer sur une planche locale
        for b in self.boards_prep:
            if state.has_object(b):
                return self._nav(p, [b]) or Action.STAY                 # découper / récupérer le coupé
        # prendre un brut posté sur une passe (pour le découper)
        if self.boards_prep:
            dp = self.dist.get(p.position, {}); best, bd = None, 1e9
            for c, m in self.bridges.items():
                if self.prep_comp in m and state.has_object(c):
                    it = state.get_object(c)
                    if it.name in ("onion", "tomato") and not chopped(it):
                        d = dp.get(m[self.prep_comp], 1e9)
                        if d < bd:
                            bd, best = d, (c, m[self.prep_comp])
            if best is not None:
                a = self._go_counter(p, best[0], best[1])
                if a is not None:
                    return a
        # fournir une assiette (si distributeur de mon côté et la cuisine en a besoin)
        if (self.dishes_prep and self._dish_needed(state)
                and not any(state.has_object(c) and state.get_object(c).name == "dish"
                            for c in self.bridges)):
            return self._nav(p, self.dishes_prep) or Action.STAY
        return Action.STAY

    def joint(self, state, t):
        self._prep_shim.chosen_goal = state.players[self.prep_i].pos_and_or
        out = [None, None]
        out[self.cook_i] = self.cook_action(state)
        out[self.prep_i] = self.prep_action(state)
        return tuple(out)


class CoopExchangePolicy(ExchangePolicy):
    """Relais coopératif pour layout CONNEXE (les deux agents atteignent TOUT, mais les
    zones d'échange 'Y' sont des RACCOURCIS géométriques).

    Sur un tel layout, ExchangePolicy dégénère en greedy libre : n'ayant PAS deux
    composantes séparées, aucune de ses conditions de relais (fondées sur l'appartenance
    à une composante) ne se déclenche, et les deux greedy font le TOUR COMPLET de la
    boucle pour chaque étape de recette (oignon→planche→pot→…). C'est pourquoi
    `simulation_exchange` retombait sur `GreedyPair` (0 usage des Y ; AVEC == SANS).

    Ici on rétablit un pipeline coopératif dont l'usage des zones est décidé — comme
    demandé — par ESTIMATION du gain en pas, l'agent OBSERVANT la position de son
    partenaire :

      * rôles ÉMERGENTS par proximité : CUISINE (`cook`, vrai GreedyAgent) = agent le plus
        proche du bloc marmite/service/dispensers ; PREP = l'autre (proche planche/assiette,
        processeur explicite) ;
      * chaque agent, lorsqu'il tient un objet dont la station de DESTINATION est du côté du
        partenaire, estime le gain en pas de « déposer sur une zone d'échange (le partenaire
        termine) » vs « livrer soi-même », et n'utilise la zone QUE si le gain estimé est
        positif (`_relay_gain`) ; sinon il livre lui-même (repli greedy). Sont ainsi échangés
        tous les objets ET les PLATS : brut->planche(prep), coupé/assiette->marmite(cook),
        et la SOUPE->service(prep) quand le service est du côté prep (cf. test_exchange_
        benefit2, où le cook passe le plat au prep au lieu de traverser jusqu'au service).

    NB — l'estimation est PAR OBJET (locale). Sur un layout connexe OUVERT (boucle) où deux
    greedy libres équilibrent déjà la charge, spécialiser les rôles peut rester GLOBALEMENT
    plus lent que le greedy libre malgré des gains par objet positifs (planche/marmite unique
    déjà sérialisée + charge cook/prep déséquilibrée) : c'est mesuré et rapporté honnêtement
    par le mode `compare` (cf. test_exchange_benefit -> l'optimum reste le greedy libre). Le
    relais est en revanche INDISPENSABLE là où le greedy libre échoue — régions séparées
    (test_exchange_forced) ou interblocage de cul-de-sac (test_exchange_benefit2). « Steps
    minimum avec usage optimal des zones » = min(relais, greedy libre), les deux étant joués.

    Estimation du gain (OBSERVE le partenaire), objet tenu par i, stations de destination D :
        solo   = min_cost_to_feature(pos_i, D)              # i livre lui-même à D
        drop(y)= min_cost_to_feature(pos_i, [y])            # i va déposer sur la zone y
        fin(y) = min_cost_to_feature(pos_j, [y]) + min_cost_between_features([y], D)
                                                            # j (position OBSERVÉE) prend en y puis livre à D
    Relais via la zone libre y de dépôt le moins cher telle que
        drop(y) + MARGE < solo   ET   fin(y) <= solo
    (i économise le trajet vers D en restant LOCAL ; j, déjà mieux placé, termine sans
    retarder l'objet). `_relay_gain` renvoie (y, solo − drop) = gain estimé, ou None.
    """

    def __init__(self, mdp, mlam, counter_goals):
        self.mdp, self.mlam, self.mp = mdp, mlam, mlam.motion_planner
        self.neighbors = simulation.build_neighbors(mdp)
        self.dist = all_pairs_dist(self.neighbors)
        self.cutting = bool(getattr(mdp, "cutting_enabled", False))
        self.boards = mdp.get_cutting_board_locations()
        self.dishes = mdp.get_dish_dispenser_locations()
        self.feat_locs = {"C": self.boards,
                          "P": mdp.get_pot_locations(),
                          "S": mdp.get_serving_locations()}
        # zones d'échange praticables (au moins une case pour s'y tenir)
        self.exchange = [c for c in counter_goals if stand_tiles(mdp, c)]
        # rôles par proximité : cook = agent relativement le plus proche du bloc CUISINE
        cook_feats = (mdp.get_pot_locations() + mdp.get_serving_locations()
                      + mdp.get_onion_dispenser_locations() + mdp.get_tomato_dispenser_locations())
        prep_feats = self.boards + self.dishes
        # « maison » de chaque rôle = sa station de travail CŒUR (ancrage STABLE du gain :
        # livrer un objet ailleurs oblige à REVENIR faire tourner sa boucle — cook->marmite
        # pour cuire la suivante, prep->planche pour découper la suivante). N'inclure QUE le
        # cœur : ainsi une station de service/assiette située du CÔTÉ du partenaire est bien
        # comptée comme un détour (retour vers la marmite), donc RELAYÉE — c'est ce qui
        # permet d'échanger aussi les PLATS (soupes) quand le service est côté prep.
        self.cook_home = mdp.get_pot_locations()
        self.prep_home = self.boards
        starts = mdp.start_player_positions
        score = [self._reg_dist(starts[i], prep_feats) - self._reg_dist(starts[i], cook_feats)
                 for i in (0, 1)]                     # ↑ = plus loin du prep, plus près du cook
        self.cook_i = 0 if score[0] >= score[1] else 1
        self.prep_i = 1 - self.cook_i
        self.cook_comp, self.prep_comp = 0, 1         # côtés virtuels (réutilise _dest/_other)
        self.cook = make_greedy(mdp, mlam, self.cook_i, ai_see_asset=False)
        self._prep_shim = _Shim()
        self._shims = [None, None]
        self._shims[self.cook_i] = self.cook
        self._shims[self.prep_i] = self._prep_shim
        self._shims = tuple(self._shims)
        self.MARGIN = 1                               # gain minimal (pas) pour daigner relayer
        self.DEPTH = 2                                 # profondeur max du pipeline (throttle)
        logger.info("CoopExchange : cook=idx%d, prep=idx%d | %d zone(s) d'échange | "
                    "planches=%s pot=%s assiette=%s", self.cook_i, self.prep_i,
                    len(self.exchange), self.boards, self.feat_locs["P"], self.dishes)

    # ------- utilitaires géométriques -------
    def _reg_dist(self, pos, feat_locs):
        """Plus court trajet praticable de `pos` à une case bordant l'une des features."""
        d = self.dist.get(pos, {})
        best = INF
        for f in feat_locs:
            for s in stand_tiles(self.mdp, f):
                if d.get(s, INF) < best:
                    best = d[s]
        return best

    def _relay_gain(self, holder_i, held, state):
        """Estime le gain en pas de « relayer l'objet tenu via une zone d'échange (le
        partenaire termine) » plutôt que « le livrer soi-même ». OBSERVE la position du
        partenaire. Renvoie (y, gain) pour la meilleure zone libre y (dépôt le moins cher
        satisfaisant la double condition), ou None si aucun relais n'est estimé profitable.

        Deux garde-fous :
        1. CÔTÉ : ne relayer que si la station de destination D est du côté du PARTENAIRE
           (plus proche de SA maison-cœur que de la mienne) — sinon le relais tire le
           partenaire hors de sa zone (ex. lui faire traverser la carte pour servir un plat
           dont le service est en fait de MON côté). Un objet dont D est de mon côté (coupé/
           assiette -> marmite pour le cook) n'est donc jamais relayé (et ne peut pas churner).
        2. COÛT ANCRÉ (stable) : livrer soi-même à D côté partenaire, c'est faire l'aller PUIS
           REVENIR dans sa propre zone (`home`) — sinon le critère est myope (le coût vers D
           fond à mesure qu'on s'en approche, et l'agent finit par le faire lui-même après
           avoir déjà traversé).

            not_use = min_cost_to_feature(pos_i, D) + min_cost_between_features(D, home_i)
            use(y)  = min_cost_to_feature(pos_i, [y])                    # je reste LOCAL
            fin(y)  = min_cost_to_feature(pos_j, [y]) + min_cost_between_features([y], D)
        Relais ssi  D côté partenaire  ET  use(y) + MARGE < not_use  ET  fin(y) <= not_use."""
        ft = self._dest(held)
        if ft is None:
            return None
        dloc = self.feat_locs.get(ft, [])
        if not dloc:
            return None
        me = state.players[holder_i]
        other = state.players[1 - holder_i]
        home = self.cook_home if holder_i == self.cook_i else self.prep_home
        partner_home = self.prep_home if holder_i == self.cook_i else self.cook_home
        d_mine = self.mp.min_cost_between_features(dloc, home)
        # [CÔTÉ] destination plus proche de MA maison que de celle du partenaire -> je livre.
        if self.mp.min_cost_between_features(dloc, partner_home) >= d_mine:
            return None
        not_use = self.mp.min_cost_to_feature(me.pos_and_or, dloc) + d_mine
        best_y, best_drop = None, INF
        for y in self.exchange:
            if state.has_object(y):                   # zone déjà occupée : indisponible
                continue
            drop = self.mp.min_cost_to_feature(me.pos_and_or, [y])
            if drop >= best_drop:
                continue
            fin = (self.mp.min_cost_to_feature(other.pos_and_or, [y])
                   + self.mp.min_cost_between_features([y], dloc))
            if drop + self.MARGIN < not_use and fin <= not_use:
                best_y, best_drop = y, drop
        if best_y is None:
            return None
        return best_y, not_use - best_drop

    # ------- rôle CUISINE : greedy + relais des BRUTS à découper (côté prep) -------
    def _mask_raw_on_exchange(self, state):
        """État où les BRUTS (destination planche) posés sur une zone d'échange sont
        masqués : ils sont du ressort du PREP (qui découpe). Empêche le cook de les
        reprendre — séparation des rôles + anti-churn (ne pas reprendre ce qu'on vient de
        poster). Les COUPÉS et ASSIETTES sur zone restent visibles (entrées du cook)."""
        raws = [y for y in self.exchange
                if state.has_object(y) and self._dest(state.get_object(y)) == "C"]
        if not raws:
            return state
        s = state.deepcopy()
        for y in raws:
            s.remove_object(y)
        return s

    def _in_flight_of(self, state, ingredient):
        """Nb d'exemplaires de `ingredient` EN TRANSIT hors marmite : posés sur une zone
        d'échange, sur une planche, ou tenus par un joueur. (Ceux déjà dans une marmite ne
        comptent pas — ils sont « arrivés ».)"""
        placed = set(self.exchange) | set(self.boards)
        n = sum(1 for pos, obj in state.objects.items()
                if obj.name == ingredient and pos in placed)
        n += sum(1 for pl in state.players
                 if pl.has_object() and pl.get_object().name == ingredient)
        return n

    def _oversupplied(self, state, ingredient):
        """Throttle anti-SURPRODUCTION, PAR TYPE : ne PAS aller chercher un exemplaire de
        plus de `ingredient` au dispenser tant qu'il en circule déjà assez pour ce que la
        marmite en cours en attend ENCORE (`need`, borné par `DEPTH` pour le pipeline).

        Sur layout CONNEXE le throttle natif de agent.py est neutralisé (tout est
        atteignable) ; sans borne le cook injecte plus d'exemplaires que la marmite n'en
        accepte. Le contrôle est PAR TYPE : un oignon en trop (temporairement en transit)
        ne doit PAS bloquer l'apport d'une tomate manquante (et inversement) — sinon
        interblocage. Un éventuel surplus finit consommé par une commande ne demandant que
        cet ingrédient, ou reste inerte sans jamais bloquer la complétion."""
        try:
            missing = self.cook.next_order_info["missing_ingredients_in_MA_pot"]
        except (TypeError, KeyError, AttributeError):
            missing = []
        need = list(missing).count(ingredient)
        if need <= 0:
            return True                                # la marmite n'attend pas ce type
        return self._in_flight_of(state, ingredient) >= min(need, self.DEPTH)

    def _fetch_ingredient(self, pos_and_or):
        """Si le but greedy courant est d'aller PUISER un ingrédient à un dispenser oignon/
        tomate, renvoie son nom (pour le throttle) ; sinon None (ramassage sur zone, pot…)."""
        faced = Action.move_in_direction(pos_and_or[0], pos_and_or[1])
        if faced in set(self.mdp.get_onion_dispenser_locations()):
            return "onion"
        if faced in set(self.mdp.get_tomato_dispenser_locations()):
            return "tomato"
        return None

    def cook_action(self, state):
        p = state.players[self.cook_i]
        held = p.get_object() if p.has_object() else None
        act, _ = self.cook.action(self._mask_raw_on_exchange(state))   # met à jour chosen_goal
        if held is not None:
            # Relayer un objet dont la station suivante est du CÔTÉ du prep : un brut à
            # découper (planche), ou le PLAT (soupe) si le service est côté prep. Le gate
            # applique lui-même le garde-fou de CÔTÉ -> un coupé/assiette (destination
            # marmite = cœur du cook) n'est jamais relayé (pas de churn) et une destination
            # côté cook fait livrer le cook lui-même.
            g = self._relay_gain(self.cook_i, held, state)
            if g is not None:
                return self._nav(p, [g[0]]) or Action.STAY
            return act                                 # sinon : livrer soi-même (pot/service/dressage)
        # mains vides : ne pas sur-approvisionner au dispenser si le type circule déjà assez
        cg = self.cook.chosen_goal
        if cg is not None:
            ingredient = self._fetch_ingredient(cg)
            if ingredient is not None and self._oversupplied(state, ingredient):
                return Action.STAY
        return act

    # ------- rôle PREP : processeur explicite (découpe / assiettes / relais des coupés) -------
    def _dish_in_transit(self, state):
        """Une assiette est-elle déjà en route vers le cook (sur une zone, ou tenue par lui) ?"""
        if any(state.has_object(y) and state.get_object(y).name == "dish" for y in self.exchange):
            return True
        cook_p = state.players[self.cook_i]
        return cook_p.has_object() and cook_p.get_object().name == "dish"

    def prep_action(self, state):
        p = state.players[self.prep_i]
        held = p.get_object() if p.has_object() else None
        if held is not None:
            ft = self._dest(held)
            if ft == "C":                              # brut : le découper sur une planche (côté PREP)
                empty = [b for b in self.boards if not state.has_object(b)]
                return self._nav(p, empty) or Action.STAY
            g = self._relay_gain(self.prep_i, held, state)   # coupé / assiette -> côté cook
            if g is not None:
                return self._nav(p, [g[0]]) or Action.STAY
            return self._nav(p, self.feat_locs.get(ft, [])) or Action.STAY   # sinon livrer soi-même
        # mains vides :
        soup_ys = [y for y in self.exchange            # 0) SERVIR un plat (soupe) relayé par le cook
                   if state.has_object(y) and state.get_object(y).name == "soup"]
        if soup_ys:                                    #    (fin de pipeline = priorité : ça marque la commande)
            return self._nav(p, soup_ys) or Action.STAY
        for b in self.boards:                          # 1) travailler une planche (couper / récupérer le coupé)
            if state.has_object(b):
                return self._nav(p, [b]) or Action.STAY
        raw_ys = [y for y in self.exchange             # 2) prendre un brut relayé (pour le découper)
                  if state.has_object(y) and self._dest(state.get_object(y)) == "C"]
        if raw_ys:
            return self._nav(p, raw_ys) or Action.STAY
        if (self.dishes and self._dish_needed(state)   # 3) fournir une assiette au cook (soupe en cours)
                and not self._dish_in_transit(state)):
            return self._nav(p, self.dishes) or Action.STAY
        return Action.STAY                             # 4) rien à traiter -> attendre (yielder)


# ---------------------------------------------------------------------------
# Rollout
# ---------------------------------------------------------------------------
def rollout(mdp, policy, counter_goals, *, horizon=3000, tpaa=1, seed=0, fps=10, on_tick=None):
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)
    neighbors = simulation.build_neighbors(mdp)
    coop_agents = policy._shims if isinstance(policy, ExchangePolicy) else policy.ags
    cg = set(counter_goals)
    state = mdp.get_standard_start_state()
    tot = len(mdp.start_all_orders)
    t = decisions = y_drop = y_pick = 0
    prev_pass = {c: state.has_object(c) for c in cg}

    if on_tick is not None:
        on_tick(state, tot - len(state.all_orders), t)

    while len(state.all_orders) > 0 and t < horizon:
        if t % tpaa == 0:
            joint = policy.joint(state, t)
            joint = simulation.coop_deconflict(mdp, state, tuple(coop_agents), tuple(joint), neighbors)
            decisions += 1
        else:
            joint = (Action.STAY, Action.STAY)
        state, _ = mdp.get_state_transition(state, joint)
        for c in cg:
            now = state.has_object(c)
            y_drop += now and not prev_pass[c]
            y_pick += (not now) and prev_pass[c]
            prev_pass[c] = now
        t += 1
        if on_tick is not None:
            on_tick(state, tot - len(state.all_orders), t)

    return dict(done=len(state.all_orders) == 0, steps=t, decisions=decisions,
                delivered=tot - len(state.all_orders), orders_total=tot,
                duration_s=round(t / fps, 1), y_drop=int(y_drop), y_pick=int(y_pick))


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def _bridge_passes(mdp, counter_goals, comp_of=None):
    """Passes « pont » : counter_goals dont les cases d'accès couvrent >=2 composantes
    praticables (donc reliant deux zones que les agents ne peuvent traverser à pied)."""
    if comp_of is None:
        comp_of = components(simulation.build_neighbors(mdp))
    return [c for c in counter_goals
            if len({comp_of[s] for s in stand_tiles(mdp, c) if s in comp_of}) >= 2]


def _make_policy(mdp, mlam, cg, relay):
    """Choix de la politique de relais selon la STRUCTURE du layout :
      * deux composantes praticables distinctes reliées par >=1 passe pont, marmite d'un
        côté  -> ExchangePolicy (relais à rôles émergents ; cf. test_exchange_forced) ;
      * une SEULE composante (layout CONNEXE : les deux agents atteignent tout) MAIS avec
        des zones d'échange et un pipeline découpe -> CoopExchangePolicy (relais coopératif
        décidé par estimation du gain en pas ; cf. test_exchange_benefit) ;
      * sinon -> greedy libre (GreedyPair).
    Repli AUTOMATIQUE (jamais de crash)."""
    if relay:
        comp_of = components(simulation.build_neighbors(mdp))
        s0, s1 = mdp.start_player_positions
        c0, c1 = comp_of.get(s0), comp_of.get(s1)
        bridges = [c for c in _bridge_passes(mdp, cg, comp_of)
                   if {c0, c1} <= {comp_of[s] for s in stand_tiles(mdp, c) if s in comp_of}]
        pot_comps = feature_comps(mdp, comp_of, mdp.get_pot_locations())
        if c0 is not None and c0 != c1 and bridges and (c0 in pot_comps or c1 in pot_comps):
            return ExchangePolicy(mdp, mlam, cg)
        # [CONNEXE] Un seul composant, mais des zones d'échange + pipeline découpe
        # (planche/assiette/marmite) : relais coopératif à gain estimé. Le gate se
        # neutralise (== greedy) si le layout n'offre aucun raccourci profitable.
        if c0 is not None and c0 == c1 and _connected_exploitable(mdp, cg):
            return CoopExchangePolicy(mdp, mlam, cg)
        logger.warning("Layout '%s' : structure à zones non exploitable (agents dans %s ; "
                       "%d passe(s) pont entre eux ; marmite atteignable=%s) -> greedy libre. "
                       "Pour le relais : deux régions séparées reliées SEULEMENT par des passes "
                       "'Y' (cf. test_exchange_forced), OU un layout connexe avec zones + découpe "
                       "(cf. test_exchange_benefit).",
                       mdp.layout_name, "2 composantes" if c0 != c1 else "1 seule composante",
                       len(bridges), bool((c0 in pot_comps) or (c1 in pot_comps)))
    return GreedyPair(mdp, mlam)


def _connected_exploitable(mdp, cg):
    """True si un layout CONNEXE a la signature d'un pipeline relayable : des zones
    d'échange, une marmite, la découpe activée avec au moins une planche et une assiette
    (les deux stations « côté prep » sur lesquelles repose le relais). Le bénéfice réel
    est ensuite jugé au cas par cas par le gate `_relay_gain` (repli greedy si nul)."""
    return bool(cg) and bool(mdp.get_pot_locations()) \
        and bool(getattr(mdp, "cutting_enabled", False)) \
        and bool(mdp.get_cutting_board_locations()) and bool(mdp.get_dish_dispenser_locations())


def run_compare(args, config):
    print(f"\n  AVEC vs SANS zones d'échange — layout={args.layout} (tpaa={args.tpaa}, horizon={args.max_ticks})")
    print("  " + "-" * 74)
    print(f"  {'variante':<30}{'livré':>8}{'steps':>8}{'décis.':>8}{'Ydrop':>7}{'Ypick':>7}")
    print("  " + "-" * 74)
    res = {}
    avec_policy = None
    for label, exchange, relay in [("AVEC zones (relais)", True, True),
                                   ("SANS zones (greedy libre)", False, False)]:
        mdp, mlam, cg = build_env(args.layout, args.layouts_dir, config, exchange=exchange)
        policy = _make_policy(mdp, mlam, cg, relay)
        if relay:
            avec_policy = policy
        r = rollout(mdp, policy, cg, horizon=args.max_ticks, tpaa=args.tpaa, seed=args.seed)
        res[label] = r
        done = "OK" if r["done"] else "TMO"
        print(f"  {label:<30}{r['delivered']:>4}/{r['orders_total']} {done:<3}{r['steps']:>6}"
              f"{r['decisions']:>8}{r['y_drop']:>7}{r['y_pick']:>7}")
    print("  " + "-" * 74)
    a, b = res["AVEC zones (relais)"], res["SANS zones (greedy libre)"]
    separated = isinstance(avec_policy, ExchangePolicy) and not isinstance(avec_policy, CoopExchangePolicy)
    connected_relay = isinstance(avec_policy, CoopExchangePolicy)
    if a["done"] and b["done"]:
        d = a["steps"] - b["steps"]
        best = min(a["steps"], b["steps"])
        print(f"  -> {a['orders_total']} commandes livrées dans les DEUX cas : {a['steps']} steps AVEC vs "
              f"{b['steps']} SANS = {d:+d} ({100*d/b['steps']:+.1f}%).")
        print(f"     Minimum réalisable ~ {best} steps.")
        if d > 0:
            # AVEC plus lent : le layout ne FORCE pas la coopération (greedy libre déjà
            # optimal). L'utilisation OPTIMALE des zones = ne pas s'y astreindre -> le
            # minimum est celui du greedy libre.
            print("     Utilisation OPTIMALE des zones ici = NE PAS relayer : sur ce layout\n"
                  "     connexe OUVERT, deux greedy libres parallélisent mieux que le relais\n"
                  "     (la planche/marmite unique sérialise déjà ; spécialiser les rôles\n"
                  "     DÉSÉQUILIBRE la charge). Les zones ne gagnent que si la topologie\n"
                  "     FORCE la traversée (cf. test_exchange_forced) ou bloque le greedy\n"
                  "     libre (cf. test_exchange_benefit2).")
        elif d < 0:
            print("     Le relais coopératif via les zones fait GAGNER des steps : les agents\n"
                  "     restent locaux et se passent les objets au lieu de faire le tour.")
    elif a["done"] and not b["done"]:
        why = ("régions cloisonnées, reliées UNIQUEMENT par les zones d'échange"
               if separated else
               "le greedy libre s'interbloque (topologie contraignante : cul-de-sac/couloir),\n"
               "     là où le relais coopératif garde chaque agent local et débloque le pipeline")
        print(f"  -> ZONES INDISPENSABLES : {a['orders_total']} commandes en {a['steps']} steps AVEC les"
              f" zones, INFAISABLE sans (0/{b['orders_total']} :\n     {why}). Gain total : réalisable vs jamais.")
    else:
        print("  -> au moins une variante n'a pas tout livré dans l'horizon"
              + (" (relais coopératif connexe)" if connected_relay else ""))
    print()
    return res


def _setup_visualizer():
    """StateVisualizer du sim, mais avec le mapping terrain FIDÈLE AU VRAI JEU
    (static/js/graphics.js, show_counter_drop=True) :
        Y -> exchange.png (zone d'échange)   [le sim mettait counter.png : FAUX]
        C -> cutting_board.png (planche)
        E -> trash_bin.png (poubelle)        [le sim mettait exchange.png : FAUX]
    trash_bin n'est PAS dans terrain_cut ; on charge terrain.json (qui l'a) pour la poubelle."""
    SV = simulation._import_state_visualizer()   # injecte le stub layout_generator + charge les sprites
    from overcooked_ai_py.visualization.state_visualizer import MultiFramePygameImage
    SV.TILE_TO_FRAME_NAME = {**SV.TILE_TO_FRAME_NAME,
                             "Y": "exchange", "C": "cutting_board", "E": "trash_bin"}
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "assets")
    png, js = os.path.join(assets, "terrain.png"), os.path.join(assets, "terrain.json")
    trash_img = MultiFramePygameImage(png, js) if os.path.exists(png) and os.path.exists(js) else None

    class FixedVisualizer(SV):
        TRASH_IMG = trash_img
        def _render_grid(self, surface, grid):
            for y, row in enumerate(grid):
                for x, tile in enumerate(row):
                    img, frame = self.TERRAINS_IMG, self.TILE_TO_FRAME_NAME.get(tile)
                    # la poubelle 'E' vient de terrain.json (absente de terrain_cut)
                    if tile == "E" and self.TRASH_IMG is not None \
                            and "trash_bin" in self.TRASH_IMG.frames_rectangles:
                        img, frame = self.TRASH_IMG, "trash_bin"
                    elif frame is None or frame not in img.frames_rectangles:
                        frame = "counter"
                    img.blit_on_surface(surface, self._position_in_unscaled_pixels((x, y)), frame)
    return FixedVisualizer


def run_visual(args, config):
    import pygame
    StateVisualizer = _setup_visualizer()
    mdp, mlam, cg = build_env(args.layout, args.layouts_dir, config, exchange=not args.no_relay)
    grid = [list(r) for r in mdp.terrain_mtx]
    for (x, y) in cg:                      # marquer les passes avec le sprite « exchange »
        grid[y][x] = "Y"
    grid = ["".join(r) for r in grid]
    policy = _make_policy(mdp, mlam, cg, relay=not args.no_relay)
    logger.info("Visuel : layout=%s | relais=%s | %d passes", args.layout, not args.no_relay, len(cg))

    pygame.init()
    viz = StateVisualizer()
    clock = pygame.time.Clock()
    win = {"surface": None}
    SUBFRAMES, EASE = 3, 0.35
    vis = {"pos": None}

    def on_tick(state, delivered, t):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                raise KeyboardInterrupt
        targets = [[float(p.position[0]), float(p.position[1])] for p in state.players]
        if vis["pos"] is None:
            vis["pos"] = [list(tp) for tp in targets]
        hud = StateVisualizer.default_hud_data(state, score=delivered,
                                               time_left=round((args.max_ticks - t) / args.fps, 1))
        for _ in range(SUBFRAMES):
            for i, tgt in enumerate(targets):
                vis["pos"][i][0] += EASE * (tgt[0] - vis["pos"][i][0])
                vis["pos"][i][1] += EASE * (tgt[1] - vis["pos"][i][1])
            viz._vis_positions = [tuple(p) for p in vis["pos"]]
            surf = viz.render_state(state, grid, hud_data=hud)
            if win["surface"] is None:
                win["surface"] = pygame.display.set_mode(surf.get_size())
                pygame.display.set_caption(f"Zones d'échange — {args.layout}"
                                           + ("" if not args.no_relay else " (greedy libre)"))
            win["surface"].blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(args.fps * SUBFRAMES)

    try:
        r = rollout(mdp, policy, cg, horizon=args.max_ticks, tpaa=args.tpaa,
                    seed=args.seed, fps=args.fps, on_tick=on_tick)
        logger.info("%s : %d/%d commandes en %d steps | passes: %d dépôts / %d retraits",
                    "TOUT LIVRÉ" if r["done"] else "horizon atteint",
                    r["delivered"], r["orders_total"], r["steps"], r["y_drop"], r["y_pick"])
        print("  (fermer la fenêtre pour quitter)")
        while True:
            for e in pygame.event.get():
                if e.type in (pygame.QUIT, pygame.KEYDOWN):
                    raise KeyboardInterrupt
            clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


def run_manual(args, config):
    """[JEU MANUEL] Le joueur contrôle UN chef au clavier ; l'autre est un GreedyAgent
    (comme en production : humain + IA greedy). Désactivé par défaut : s'active avec
    `--mode manual`. Commandes : Flèches ou ZQSD = se déplacer / pivoter ; Espace (ou E,
    Entrée) = interagir (maintenir pour découper) ; Échap = quitter."""
    import pygame
    from overcooked_ai_py.mdp.actions import Direction
    StateVisualizer = _setup_visualizer()
    mdp, mlam, cg = build_env(args.layout, args.layouts_dir, config, exchange=not args.no_relay)
    grid = [list(r) for r in mdp.terrain_mtx]
    for (x, y) in cg:                      # marquer les passes avec le sprite « exchange »
        grid[y][x] = "Y"
    grid = ["".join(r) for r in grid]
    human_i = args.human_index if args.human_index in (0, 1) else 1
    ai_i = 1 - human_i
    ai = make_greedy(mdp, mlam, ai_i, auto_unstuck=True)   # partenaire greedy autonome
    logger.info("Jeu MANUEL : tu joues le chef %d ; l'IA (greedy) joue le chef %d | layout=%s | %d zone(s)",
                human_i, ai_i, args.layout, len(cg))
    print("  Commandes : Flèches / ZQSD = se déplacer ou pivoter | Espace (ou E) = interagir "
          "(maintenir pour découper) | Échap = quitter")

    KEY_TO_DIR = {
        pygame.K_UP: Direction.NORTH, pygame.K_z: Direction.NORTH, pygame.K_w: Direction.NORTH,
        pygame.K_DOWN: Direction.SOUTH, pygame.K_s: Direction.SOUTH,
        pygame.K_LEFT: Direction.WEST, pygame.K_q: Direction.WEST, pygame.K_a: Direction.WEST,
        pygame.K_RIGHT: Direction.EAST, pygame.K_d: Direction.EAST,
    }
    INTERACT_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_e)

    pygame.init()
    viz = StateVisualizer()
    clock = pygame.time.Clock()
    state = mdp.get_standard_start_state()
    tot = len(mdp.start_all_orders)
    win = {"surface": None}
    SUBFRAMES, EASE = 3, 0.35
    vis = {"pos": [[float(p.position[0]), float(p.position[1])] for p in state.players]}
    quit_flag = {"v": False}

    def read_human():
        """Action du joueur pour CE tick : une touche fraîchement pressée est prioritaire
        (tap = un pas / un interact) ; sinon on lit les touches MAINTENUES (déplacement
        continu, maintien d'Espace = découpe). Met quit_flag si fermeture demandée."""
        act = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                quit_flag["v"] = True
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    quit_flag["v"] = True
                elif e.key in INTERACT_KEYS:
                    act = Action.INTERACT
                elif e.key in KEY_TO_DIR:
                    act = KEY_TO_DIR[e.key]
        if act is not None:
            return act
        held = pygame.key.get_pressed()
        if any(held[k] for k in INTERACT_KEYS):
            return Action.INTERACT
        for k, d in KEY_TO_DIR.items():
            if held[k]:
                return d
        return Action.STAY

    def render(t):
        delivered = tot - len(state.all_orders)
        targets = [[float(p.position[0]), float(p.position[1])] for p in state.players]
        hud = StateVisualizer.default_hud_data(state, score=delivered,
                                               time_left=round((args.max_ticks - t) / args.fps, 1))
        for _ in range(SUBFRAMES):
            for i, tgt in enumerate(targets):
                vis["pos"][i][0] += EASE * (tgt[0] - vis["pos"][i][0])
                vis["pos"][i][1] += EASE * (tgt[1] - vis["pos"][i][1])
            viz._vis_positions = [tuple(p) for p in vis["pos"]]
            surf = viz.render_state(state, grid, hud_data=hud)
            if win["surface"] is None:
                win["surface"] = pygame.display.set_mode(surf.get_size())
                pygame.display.set_caption(f"JEU MANUEL — chef {human_i} (toi) + greedy — {args.layout}")
            win["surface"].blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(args.fps * SUBFRAMES)

    try:
        render(0)
        t = 0
        while len(state.all_orders) > 0 and t < args.max_ticks and not quit_flag["v"]:
            human_action = read_human()
            if quit_flag["v"]:
                break
            ai_action, _ = ai.action(state)
            joint = [None, None]
            joint[human_i] = human_action
            joint[ai_i] = ai_action
            state, _ = mdp.get_state_transition(state, tuple(joint))
            t += 1
            render(t)
        done = len(state.all_orders) == 0
        logger.info("%s : %d/%d commandes en %d steps",
                    "GAGNÉ (toutes les commandes livrées)" if done else "fin",
                    tot - len(state.all_orders), tot, t)
        if not quit_flag["v"]:
            print("  " + ("BRAVO — tout livré ! " if done else "") + "(Échap ou fermer la fenêtre pour quitter)")
            while not quit_flag["v"]:
                for e in pygame.event.get():
                    if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                        quit_flag["v"] = True
                clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["compare", "visual", "manual"], default="compare")
    ap.add_argument("--layout", default=DEFAULT_LAYOUT)
    ap.add_argument("--layouts-dir", default=DEFAULT_LAYOUTS_DIR)
    ap.add_argument("--config-path", default="config.json")
    ap.add_argument("--config-block", default=DEFAULT_CONFIG_BLOCK)
    ap.add_argument("--no-relay", action="store_true",
                    help="[visuel] greedy libre (ignore les passes) au lieu du relais à rôles")
    ap.add_argument("--human-index", type=int, default=1, choices=[0, 1],
                    help="[manuel] index du chef contrôlé au clavier ; l'IA greedy joue l'autre "
                         "(défaut 1, comme en prod où l'IA est le chef 0)")
    ap.add_argument("--tpaa", type=int, default=1,
                    help="ticks entre 2 décisions (1 = non bridé, mesure pure de steps)")
    ap.add_argument("--max-ticks", type=int, default=3000)
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    config = json.load(open(args.config_path))[args.config_block]
    {"manual": run_manual, "visual": run_visual, "compare": run_compare}[args.mode](args, config)


if __name__ == "__main__":
    main()
