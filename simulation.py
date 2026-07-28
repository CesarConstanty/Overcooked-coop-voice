#!/usr/bin/env python3
"""simulation.py — Évaluation de layouts par deux agents Greedy (hors Flask).

Fait jouer DEUX GreedyAgent coopératifs sur les layouts d'un bloc de config
(ex. ``config_test_visual``) et mesure le nombre de ticks + la durée nécessaires
pour compléter le niveau (= toutes les commandes livrées).

Deux modes :
  * ``--mode visual``  : rejoue UN layout dans une fenêtre pygame, en temps réel,
                         pour observer ce qu'il se passe en jeu.
  * ``--mode headless``: simule PLUSIEURS layouts sans affichage, aussi vite que
                         le CPU le permet (Pool multi-process), puis reconvertit
                         les ticks en secondes via le fps de la config
                         (duration_s = ticks / fps). Résultats -> CSV + tableau.

Navigation coopérative (activée par défaut, --no-coop pour désactiver) :
  Deux GreedyAgent planifient chacun leur trajet SEUL et se bloquent mutuellement
  dans les couloirs étroits (le MDP fige les 2 joueurs à toute collision) -> les
  paires greedy « fidèle prod » ne complètent que ~2/36 layouts. La couche coop
  (cf. coop_deconflict) ne touche PAS la sélection de tâche greedy ; elle ne
  déconflicte que le déplacement (priorité + BFS d'évitement + recul en couloir),
  ce qui fait passer les complétions à ~21/36. `--no-coop` reproduit le greedy exact.

Modèle de temps (vérifié dans le code du serveur) :
  1 tick == 1 transition du MDP == 1/fps seconde réelle.
  En production le greedy n'agit qu'un tick sur ``ai_base_speed`` (=4) et STAY
  entre-temps (le MDP, lui, avance à chaque tick : cuisson, découpe, livraisons).
  On reproduit fidèlement ce bridage : chaque agent décide tous les
  ``ticks_per_ai_action`` ticks, STAY sinon. La durée rapportée reflète donc ce
  qu'un participant verrait réellement. ``--unthrottled`` (agit à chaque tick)
  donne le plancher théorique, ~4x plus rapide.

IMPORTANT : lancer depuis la RACINE du dépôt — ``layouts_dir`` de la config est
un chemin relatif (``./overcooked_ai_py/data/layouts/generation_cesar_2``).

Exemples :
  python simulation.py config_test_visual --mode visual --layout test01
  python simulation.py config_test_visual                       # blocs, headless
  python simulation.py config_test_visual --layouts all --jobs 8 --out res.csv
  python simulation.py config_test_visual --unthrottled --max-ticks 5000
"""
import argparse
import csv
import json
import logging
import os
import random
import sys
from collections import deque
from copy import copy
from multiprocessing import Pool

import numpy as np

# NB : PAS de `import app` (il fait eventlet.monkey_patch au chargement) et PAS de
# Recipe.configure manuel (la construction du MDP configure déjà le Recipe global).
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.actions import Action, Direction
from overcooked_ai_py.agents.agent import GreedyAgent
from overcooked_ai_py.static import LAYOUTS_DIR

# On réutilise la couche de cache d'ENVIRONNEMENT du runtime (game.py est
# indépendant de Flask) : mêmes clés que PlanningGame -> les pickles mlam
# précalculés (data/planners/<layout>_am.pkl) sont chargés sans recompute.
import game

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)
logger = logging.getLogger("overcooked.simulation")


# ---------------------------------------------------------------------------
# Chargement config + énumération des layouts
# ---------------------------------------------------------------------------
def load_config(block_name, path="config.json"):
    """Charge config.json et renvoie (CONFIG_global, bloc_selectionne).

    Le bloc d'expérience (config_test / config_test_visual / ...) est TOUJOURS
    choisi par l'appelant — il n'existe pas de clé « bloc actif » dans le JSON
    (au runtime c'est request.args['CONFIG'], cf. app.py)."""
    with open(path, "r") as f:
        CONFIG = json.load(f)
    if block_name not in CONFIG:
        raise SystemExit(
            f"Bloc '{block_name}' introuvable dans {path}. "
            f"Blocs disponibles : {[k for k, v in CONFIG.items() if isinstance(v, dict) and 'blocs' in v]}"
        )
    return CONFIG, CONFIG[block_name]


def _all_layouts_in_dir(layouts_dir):
    """Essais = tous les *.layout d'un dossier (triés)."""
    if not os.path.isdir(layouts_dir):
        raise SystemExit(f"Dossier de layouts introuvable : {layouts_dir} (lancer depuis la racine du dépôt)")
    names = sorted(f[:-len(".layout")] for f in os.listdir(layouts_dir) if f.endswith(".layout"))
    if not names:
        raise SystemExit(f"Aucun fichier *.layout dans {layouts_dir}")
    return [{"step": None, "layout": n, "condition": None} for n in names]


def _resolve_layout_dir(spec, default_dir):
    """Résout `spec` en dossier de layouts, ou None si ce n'en est pas un.

    Accepte : un chemin (absolu/relatif), le basename du layouts_dir de la config,
    ou un nom de dossier sous les racines usuelles de layouts."""
    roots = [
        os.path.dirname(os.path.normpath(default_dir)),          # parent du layouts_dir config
        LAYOUTS_DIR,                                              # racine du package
        os.path.join("overcooked_ai_py", "data", "layouts"),     # racine repo
    ]
    candidates = [spec]                                          # chemin tel quel (cwd/absolu)
    if os.path.basename(os.path.normpath(default_dir)) == spec:  # basename du dir config
        candidates.append(default_dir)
    candidates += [os.path.join(r, spec) for r in roots]         # sous une racine
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
    return None


def resolve_layout_source(config, spec):
    """Renvoie (trials, layouts_dir) où trials = [{'step','layout','condition'}].

    spec :
      * None / 'blocs' : les layouts de config['blocs'] (défaut), avec contexte
        (step de bloc + condition). Un même layout dans plusieurs blocs -> plusieurs
        lignes (conditions différentes). Utilise le layouts_dir de la config.
      * 'all'          : tous les *.layout du layouts_dir de la config.
      * un DOSSIER     : nom ou chemin d'un dossier de layouts (ex. 'generation_cesar_2',
        'generation_cesar_2 copy', './un/chemin') -> tous ses *.layout, construits
        DEPUIS ce dossier.
      * 'a,b,c'        : liste explicite de noms de layouts (dans le layouts_dir config).
    """
    default_dir = config.get("layouts_dir", LAYOUTS_DIR)
    conditions = config.get("conditions", {})

    if spec is None or spec == "blocs":
        trials = []
        for step, layouts in config.get("blocs", {}).items():
            for layout in layouts:
                trials.append({"step": step, "layout": layout, "condition": conditions.get(step)})
        if not trials:
            raise SystemExit("Aucun layout dans config['blocs'].")
        return trials, default_dir

    if spec == "all":
        return _all_layouts_in_dir(default_dir), default_dir

    layout_dir = _resolve_layout_dir(spec, default_dir)
    if layout_dir is not None:
        return _all_layouts_in_dir(layout_dir), layout_dir

    # Liste explicite "test01,test05" (dans le layouts_dir de la config)
    trials = [
        {"step": None, "layout": n.strip(), "condition": None}
        for n in spec.split(",") if n.strip()
    ]
    return trials, default_dir


# ---------------------------------------------------------------------------
# Construction MDP + mlam + agents (miroir fidèle de PlanningGame)
# ---------------------------------------------------------------------------
def build_env(layout, config, layouts_dir=None):
    """Reconstruit (mdp, mlam) EXACTEMENT comme PlanningGame, via les caches.

    Les params pilotés par la config (valeurs/temps ingrédients, découpe, ...)
    sont extraits par mdp_overrides_from_config, donc les mêmes clés de cache
    qu'au runtime -> réutilisation des pickles. On COPIE le template partagé
    avant tout usage (ne jamais muter le cache lecture seule).

    layouts_dir : dossier des .layout (défaut = celui de la config)."""
    mdp_params = dict(OvercookedGridworld.mdp_overrides_from_config(config))
    layouts_dir = layouts_dir or config.get("layouts_dir", LAYOUTS_DIR)
    mdp_template, key = game.get_cached_mdp(layout, layouts_dir, mdp_params)
    mlam = game.get_cached_mlam(mdp_template, key)
    return copy(mdp_template), mlam


def make_agents(mdp, mlam, auto_unstuck=True):
    """Deux GreedyAgent coopératifs (indices 0 et 1), comme game.py:get_policy.

    On INJECTE directement le mlam partagé (a.mdp / a.mlam) au lieu d'appeler
    set_mdp() qui recalculerait un mlam par agent et muterait un dict global.
    Défauts identiques à la production : GreedyAgent() => auto_unstuck=True,
    ai_see_asset=True (chaque agent ignore l'ingrédient que le partenaire porte
    déjà -> vraie coopération)."""
    agents = []
    for idx in (0, 1):
        a = GreedyAgent(auto_unstuck=auto_unstuck, ai_see_asset=True)
        a.reset()                 # purge prev_state / hl_goal (garde index/mdp/mlam)
        a.set_agent_index(idx)    # OBLIGATOIRE et DISTINCT : 0 puis 1
        a.mdp = mdp
        a.mlam = mlam
        agents.append(a)
    return agents


# ---------------------------------------------------------------------------
# Couche de navigation coopérative (déblocage des paires greedy)
# ---------------------------------------------------------------------------
# PROBLÈME : chaque GreedyAgent planifie sa trajectoire SEUL (motion planner mono-
# agent, ignore le partenaire). Quand les deux chemins se croisent, la résolution
# de collision du MDP (_handle_collisions) IMMOBILISE les DEUX joueurs, et chacun
# rejoue le même coup en conflit -> deadlock permanent (paires greedy bloquées sur
# la plupart des layouts à couloirs étroits).
#
# SOLUTION (prioritized space-time avoidance, légère et déterministe) : on NE touche
# PAS à la sélection de tâche greedy (recette, planche, pot, service restent choisies
# par l'agent). On ne déconflicte que le DÉPLACEMENT, et seulement quand les deux
# actions désirées entreraient en collision :
#   * priorité : un agent qui TRAVAILLE (INTERACT) n'est jamais dérangé ; sinon
#     l'index 0 est prioritaire ;
#   * le prioritaire garde son coup ; le céderont recalcule son coup par un BFS vers
#     SON PROPRE but en traitant les cases {courante, suivante} du prioritaire comme
#     obstacles temporaires (il attend si aucun détour) ;
#   * garde-fou anti-blocage-croisé : si le céderont ne peut pas progresser ET occupe
#     la case visée par le prioritaire (couloir à croisement), il RECULE d'une case
#     libre pour dégager le passage.
# Empiriquement : fait passer les complétions greedy×greedy de ~2/36 à ~21/36 sur
# generation_cesar_2. Désactivable via --no-coop (greedy « fidèle prod » exact).

def build_neighbors(mdp):
    """Adjacence des cases jouables : {pos: {direction: pos_voisine}} (valides only).
    Les clés du dict = l'ensemble des positions valides (sert aussi de test d'appart.)."""
    valid = set(mdp.get_valid_player_positions())
    return {
        pos: {d: Action.move_in_direction(pos, d)
              for d in Direction.ALL_DIRECTIONS
              if Action.move_in_direction(pos, d) in valid}
        for pos in valid
    }


def _next_pos(neighbors, pos, action):
    """Case atteinte après `action` (STAY/INTERACT ou mur -> reste sur place)."""
    if action in Direction.ALL_DIRECTIONS and action in neighbors.get(pos, {}):
        return neighbors[pos][action]
    return pos


def _bfs_first_dir(neighbors, start, goal, blocked):
    """Direction du 1er pas d'un plus court chemin start->goal évitant `blocked`.
    None si start==goal, but injoignable, ou pas de chemin."""
    if start == goal or goal not in neighbors:
        return None
    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        for d, nxt in neighbors[cur].items():
            if nxt in blocked or nxt in prev:
                continue
            prev[nxt] = (cur, d)
            queue.append(nxt)
    if goal not in prev:
        return None
    node = goal
    while prev[node] is not None:
        parent, d = prev[node]
        if parent == start:
            return d
        node = parent
    return None


def coop_deconflict(mdp, state, agents, acts, neighbors):
    """Renvoie un couple d'actions sans collision à partir des actions greedy `acts`."""
    p0, p1 = state.players
    n0 = _next_pos(neighbors, p0.position, acts[0])
    n1 = _next_pos(neighbors, p1.position, acts[1])
    if not mdp.is_transition_collision((p0.position, p1.position), (n0, n1)):
        return (acts[0], acts[1])

    # Qui cède ? Ordre de priorité :
    #   1. un travailleur (INTERACT) n'est JAMAIS dérangé ;
    #   2. un agent qui ATTEND (STAY, p.ex. tenant une assiette le temps que la soupe
    #      cuise) n'a pas de destination à protéger : il cède à celui qui se DÉPLACE,
    #      quel que soit son index — c'est lui qui s'écarte du passage (garde-fou
    #      « recul d'une case » ci-dessous). Sans quoi un agent en attente prioritaire
    #      (index 0) fige un couloir devant le partenaire venu déposer/cuire ;
    #   3. à défaut (deux déplacements), l'index 0 reste prioritaire.
    i0_work, i1_work = acts[0] == Action.INTERACT, acts[1] == Action.INTERACT
    i0_stay, i1_stay = acts[0] == Action.STAY, acts[1] == Action.STAY
    if i0_work and not i1_work:
        yielder = 1
    elif i1_work and not i0_work:
        yielder = 0
    elif i0_stay and not i1_stay:
        yielder = 0
    elif i1_stay and not i0_stay:
        yielder = 1
    else:
        yielder = 1
    high = 1 - yielder

    pos_high = state.players[high].position
    next_high = _next_pos(neighbors, pos_high, acts[high])
    blocked = {pos_high, next_high}
    pos_y = state.players[yielder].position
    goal_y = agents[yielder].chosen_goal[0]

    d = _bfs_first_dir(neighbors, pos_y, goal_y, blocked)
    if d is None and pos_y == next_high:
        # Couloir à croisement : reculer d'une case libre pour dégager le prioritaire.
        for cand_d, cand_pos in neighbors[pos_y].items():
            if cand_pos not in blocked:
                d = cand_d
                break

    if d is None and next_high == pos_y:
        # [CUL-DE-SAC] Le cédant est PIÉGÉ dans un cul-de-sac dont l'UNIQUE sortie est la
        # case du prioritaire, et le prioritaire veut justement entrer dans ce cul-de-sac
        # (p.ex. accès unique à la marmite qui est aussi un cul-de-sac — layout benefit3).
        # Ni l'un ni l'autre ne peut céder « normalement » -> interblocage permanent.
        # Solution : le PRIORITAIRE s'écarte (libère sa case, de préférence vers une case
        # NON cul-de-sac) pour laisser SORTIR le piégé ; il reviendra au tick suivant.
        asides = [(hd, hpos) for hd, hpos in neighbors[pos_high].items() if hpos != pos_y]
        asides.sort(key=lambda hp: len(neighbors.get(hp[1], {})), reverse=True)
        if asides:
            out = [None, None]
            out[high] = asides[0][0]
            out[yielder] = Action.STAY
            return tuple(out)

    out = [None, None]
    out[high] = acts[high]
    out[yielder] = d if d is not None else Action.STAY
    return tuple(out)


# ---------------------------------------------------------------------------
# Cœur : une simulation (utilisée par les deux modes)
# ---------------------------------------------------------------------------
def rollout(mdp, mlam, *, fps, ticks_per_ai_action, horizon,
            seed=0, auto_unstuck=True, coop=True, on_tick=None):
    """Joue un layout jusqu'à complétion (all_orders vide) ou horizon (ticks).

    Boucle une transition MDP par tick ; les agents ne DÉCIDENT qu'un tick sur
    ``ticks_per_ai_action`` (STAY sinon). ``on_tick(state, score, tick)`` permet
    au mode visuel de rendre chaque frame.

    ``coop`` (défaut True) active la couche de navigation coopérative qui débloque
    les paires greedy (cf. coop_deconflict). Avec coop, l'anti-blocage aléatoire
    des agents est désactivé (déterministe) car la couche le remplace.

    Complétion = len(state.all_orders) == 0 (mdp.is_terminal est TOUJOURS False).
    """
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)  # graine aussi le random module (start state / anti-blocage)

    a0, a1 = make_agents(mdp, mlam, auto_unstuck=(auto_unstuck and not coop))
    neighbors = build_neighbors(mdp) if coop else None
    state = mdp.get_standard_start_state()
    orders_total = len(mdp.start_all_orders)

    sparse = 0.0
    decisions = 0
    t = 0

    if on_tick is not None:
        on_tick(state, sparse, t)   # rendu de l'état initial

    while len(state.all_orders) > 0 and t < horizon:
        if t % ticks_per_ai_action == 0:
            act0, _ = a0.action(state)
            act1, _ = a1.action(state)
            joint_action = (act0, act1)   # ordre = indices agents (0, 1)
            if coop:
                joint_action = coop_deconflict(mdp, state, (a0, a1), joint_action, neighbors)
            decisions += 1
        else:
            joint_action = (Action.STAY, Action.STAY)

        state, info = mdp.get_state_transition(state, joint_action)
        sparse += sum(info["sparse_reward_by_agent"])
        t += 1

        if on_tick is not None:
            on_tick(state, sparse, t)

    completed = len(state.all_orders) == 0
    return {
        "ticks": t,
        "decisions": decisions,
        "duration_s": round(t / fps, 3),
        "completed": completed,
        "orders_total": orders_total,
        "orders_delivered": orders_total - len(state.all_orders),
        "sparse_reward": float(sparse),
        "horizon_hit": (not completed) and t >= horizon,
    }


def compute_horizon(config, fps, max_ticks_override, max_game_length):
    """Plafond en ticks pour MESURER le temps de complétion. Défaut = MAX_GAME_LENGTH
    (secondes, le plafond DUR de la config) converti en ticks — généreux, pour que la
    complétion soit réellement observée (les paires greedy prennent ~1000 ticks). La
    colonne `fits_gametime` indique séparément si ça tient dans gameTime (fenêtre
    d'essai de l'expé). ``--max-ticks`` force une autre valeur."""
    if max_ticks_override:
        return int(max_ticks_override)
    return int(float(max_game_length) * fps)


# ---------------------------------------------------------------------------
# Mode headless (batch, parallèle)
# ---------------------------------------------------------------------------
def _run_one(task):
    """Worker Pool (top-level, picklable) : (re)charge config, simule, renvoie 1 ligne."""
    _, config = load_config(task["block_name"], task["config_path"])
    mdp, mlam = build_env(task["layout"], config, task["layouts_dir"])
    row = rollout(
        mdp, mlam,
        fps=task["fps"],
        ticks_per_ai_action=task["tpaa"],
        horizon=task["horizon"],
        seed=task["seed"],
        auto_unstuck=task["auto_unstuck"],
        coop=task["coop"],
    )
    row.update(
        layout=task["layout"],
        step=task["step"],
        condition=task["condition"],
        repeat=task["repeat"],
        fps=task["fps"],
        ticks_per_ai_action=task["tpaa"],
        seed=task["seed"],
        coop=task["coop"],
        # Complète-t-il dans la fenêtre d'essai gameTime (secondes) ?
        fits_gametime=bool(row["completed"] and row["duration_s"] <= float(config.get("gameTime", 50))),
    )
    return row


CSV_FIELDS = [
    "layout", "step", "condition", "repeat",
    "completed", "ticks", "duration_s", "fits_gametime", "decisions",
    "orders_delivered", "orders_total", "sparse_reward", "horizon_hit",
    "ticks_per_ai_action", "coop", "fps", "seed",
]


def run_headless(block_name, config, args):
    fps = args.fps or float(config.get("fps", 10))
    tpaa = 1 if args.unthrottled else args.ticks_per_ai_action
    horizon = compute_horizon(config, fps, args.max_ticks, args.max_game_length)

    trials, layouts_dir = resolve_layout_source(config, args.layouts)
    tasks = [
        {
            "config_path": args.config_path, "block_name": block_name, "layouts_dir": layouts_dir,
            "layout": tr["layout"], "step": tr["step"], "condition": tr["condition"],
            "repeat": r, "fps": fps, "tpaa": tpaa, "horizon": horizon,
            "seed": args.seed + r, "auto_unstuck": not args.deterministic,
            "coop": not args.no_coop,
        }
        for tr in trials for r in range(args.repeats)
    ]

    logger.info(
        "Headless : %d layout(s) [%s] x %d repeat(s) = %d run(s) | fps=%g tpaa=%d horizon=%d ticks | coop=%s | jobs=%d",
        len(trials), layouts_dir, args.repeats, len(tasks), fps, tpaa, horizon, not args.no_coop, args.jobs,
    )

    try:
        from tqdm import tqdm
    except ImportError:  # tqdm optionnel
        def tqdm(it, **k): return it

    if args.jobs == 1:
        rows = [_run_one(t) for t in tqdm(tasks, desc="sim")]
    else:
        with Pool(args.jobs) as pool:
            rows = list(tqdm(pool.imap_unordered(_run_one, tasks), total=len(tasks), desc="sim"))

    rows.sort(key=lambda r: (str(r["step"]), r["layout"], r["repeat"]))

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("Résultats écrits dans %s", args.out)

    _print_summary(rows, tpaa, fps)
    return rows


def _print_summary(rows, tpaa, fps):
    coop_on = bool(rows and rows[0].get("coop", True))
    print()
    print(f"  Résumé  (ticks_per_ai_action={tpaa}, fps={fps:g}, 1 tick = {1/fps:.3f}s, "
          f"nav={'coop' if coop_on else 'greedy brut'})")
    print("  " + "-" * 84)
    print(f"  {'layout':<16}{'cond':<6}{'done':<6}{'ticks':>7}{'durée(s)':>10}{'≤gT':>5}{'décis.':>8}{'cmd':>8}{'score':>8}")
    print("  " + "-" * 84)
    n_done = n_fit = 0
    for r in rows:
        done = "OK" if r["completed"] else ("TMO" if r["horizon_hit"] else "—")
        n_done += bool(r["completed"])
        fit = bool(r.get("fits_gametime"))
        n_fit += fit
        cond = str(r["condition"] or "")
        cmd = f"{r['orders_delivered']}/{r['orders_total']}"
        print(
            f"  {r['layout']:<16}{cond:<6}{done:<6}{r['ticks']:>7}"
            f"{r['duration_s']:>10.1f}{('✓' if fit else ''):>5}{r['decisions']:>8}{cmd:>8}{r['sparse_reward']:>8.0f}"
        )
    print("  " + "-" * 84)
    durs = [r["duration_s"] for r in rows if r["completed"]]
    if durs:
        print(f"  Complétés : {n_done}/{len(rows)} (dont {n_fit} ≤ gameTime) | "
              f"durée moy. {np.mean(durs):.1f}s (min {min(durs):.1f} / max {max(durs):.1f})")
    else:
        print(f"  Complétés : {n_done}/{len(rows)}")
    print()


# ---------------------------------------------------------------------------
# Mode visuel (temps réel, mono-process)
# ---------------------------------------------------------------------------
def _import_state_visualizer():
    """Importe StateVisualizer en réparant les dettes du fork pour le rendu pygame :

      1. state_visualizer.py importe `overcooked_ai_py.mdp.layout_generator`
         (supprimé du fork ; le client web JS a remplacé le rendu pygame). On
         réinjecte le petit module de constantes de terrain manquant.
      2. Ce fork ajoute des terrains propres — C (planche à découper), E
         (poubelle), Y (dépôt). Le sprite sheet standard (data/graphics/terrain.png)
         n'a PAS de planche. On bascule donc la feuille de terrain sur celle du jeu
         réel (static/assets/terrain_cut.png/json), qui contient `cutting_board.png`
         (mêmes tuiles 15x15 -> géométrie identique), et on mappe C -> cutting_board.
         NB : on NE touche PAS aux feuilles objets/chefs/soupes (leurs noms de frames
         diffèrent dans les sheets _cut, ex. onion_cut.png -> casserait le rendu des
         ingrédients non découpés).
    """
    import sys
    import types

    mod = "overcooked_ai_py.mdp.layout_generator"
    if mod not in sys.modules:
        lg = types.ModuleType(mod)
        for name, sym in {
            "EMPTY": " ", "COUNTER": "X", "ONION_DISPENSER": "O",
            "TOMATO_DISPENSER": "T", "POT": "P", "DISH_DISPENSER": "D",
            "SERVING_LOC": "S",
        }.items():
            setattr(lg, name, sym)
        sys.modules[mod] = lg

    from overcooked_ai_py.visualization.state_visualizer import (
        StateVisualizer, MultiFramePygameImage,
    )
    from overcooked_ai_py.mdp.actions import Direction as _Dir

    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "assets")

    def _load_sheet(name):
        png, js = os.path.join(assets, name + ".png"), os.path.join(assets, name + ".json")
        return MultiFramePygameImage(png, js) if os.path.exists(png) and os.path.exists(js) else None

    # Feuille de terrain du jeu réel (contient la planche à découper).
    terrain_cut = _load_sheet("terrain_cut")
    if terrain_cut is not None:
        StateVisualizer.TERRAINS_IMG = terrain_cut
        cutting_frame = "cutting_board"
    else:
        cutting_frame = "counter"  # repli si les assets sont absents

    StateVisualizer.TILE_TO_FRAME_NAME = {
        **StateVisualizer.TILE_TO_FRAME_NAME,
        "C": cutting_frame,   # planche à découper (sprite dédié du jeu réel)
        "E": "exchange",      # poubelle
        "Y": "counter",       # dépôt / counter_goal (converti en 'X' par le MDP -> mort)
        "A": "onions",        # distributeur asymétrique joueur 0 (best-effort : contenu dynamique)
        "B": "tomatoes",      # distributeur asymétrique joueur 1 (best-effort : contenu dynamique)
    }

    # Feuilles « coupées » : ingrédients découpés (onion_cut/tomato_cut), chefs tenant
    # un ingrédient découpé, et soupes à ingrédients découpés dans la marmite (frames
    # `soup_idle_..._cut`). Chargées une fois, partagées par toutes les instances.
    objects_cut = _load_sheet("objects_cut")
    chefs_cut = _load_sheet("chefs_cut")
    soups_cut = _load_sheet("soups_cut")

    class SimVisualizer(StateVisualizer):
        """StateVisualizer + sprites d'ingrédients DÉCOUPÉS + interpolation du
        déplacement des chefs (pour un rendu fluide, sans « saut »)."""

        OBJECTS_CUT_IMG = objects_cut
        CHEFS_CUT_IMG = chefs_cut
        SOUPS_CUT_IMG = soups_cut

        def __init__(self, **kw):
            super().__init__(**kw)
            # Override d'affichage des positions chefs (x,y fractionnaires) pour le
            # tweening ; None = positions logiques discrètes.
            self._vis_positions = None
            self._warned_tiles = set()

        # ---- ROBUSTESSE : aucune tuile de terrain ne doit faire planter le rendu ----
        # Le MDP accepte plus de symboles que la table sprite standard (ex. A/B,
        # distributeurs asymétriques, ou un symbole inédit d'un nouveau layout). On
        # rend toute tuile inconnue en 'counter' (tuile neutre) et on PRÉVIENT une
        # fois, plutôt que de lever un KeyError.
        def _render_grid(self, surface, grid):
            unknown = set()
            for y, row in enumerate(grid):
                for x, tile in enumerate(row):
                    frame = self.TILE_TO_FRAME_NAME.get(tile)
                    if frame is None or frame not in self.TERRAINS_IMG.frames_rectangles:
                        unknown.add(tile)
                        frame = "counter"
                    self.TERRAINS_IMG.blit_on_surface(
                        surface, self._position_in_unscaled_pixels((x, y)), frame)
            new = unknown - self._warned_tiles
            if new:
                self._warned_tiles |= new
                logger.warning(
                    "Symbole(s) de terrain non mappé(s) rendu(s) en 'counter' : %s "
                    "-> ajouter au mapping si ce sont de vrais éléments de jeu.",
                    sorted(new))

        # ---- BUG 1 : ingrédients découpés rendus avec leur sprite dédié ----------
        def _render_objects(self, surface, objects, grid):
            for obj in objects.values():
                pos = self._position_in_unscaled_pixels(obj.position)
                if obj.name == "soup":
                    (x, y) = obj.position
                    if grid[y][x] == "P":
                        status = "cooked" if obj.is_ready else "idle"
                    else:
                        status = "done"
                    # [BUG 1] Soupe à ingrédients DÉCOUPÉS -> feuille soups_cut (la
                    # marmite affiche les ingrédients coupés). Comme dans graphics.js,
                    # seules les frames "idle" de soups_cut portent le suffixe _cut ;
                    # "cooked"/"done" y existent sans suffixe. On ne bascule que si la
                    # frame voulue existe réellement (repli sécurisé sur SOUPS_IMG).
                    frame = self._soup_frame_name(obj.ingredients, status)
                    chopped = getattr(obj, "all_ingredients_chopped", False)
                    sheet = self.SOUPS_IMG
                    if chopped and self.SOUPS_CUT_IMG is not None:
                        cut_frame = frame + "_cut" if status == "idle" else frame
                        if cut_frame in self.SOUPS_CUT_IMG.frames_rectangles:
                            sheet, frame = self.SOUPS_CUT_IMG, cut_frame
                    sheet.blit_on_surface(surface, pos, frame)
                elif (getattr(obj, "chopped", False) and self.OBJECTS_CUT_IMG
                      and (obj.name + "_cut") in self.OBJECTS_CUT_IMG.frames_rectangles):
                    self.OBJECTS_CUT_IMG.blit_on_surface(surface, pos, obj.name + "_cut")
                else:
                    self.OBJECTS_IMG.blit_on_surface(surface, pos, obj.name)

        # ---- BUG 1 (tenu) + BUG 2 (interpolation) --------------------------------
        def _render_players(self, surface, players):
            for num, player in enumerate(players):
                color = self.player_colors[num]
                dname = _Dir.DIRECTION_TO_NAME[player.orientation]
                held = player.held_object

                if held is None:
                    hname = ""
                elif held.name == "soup":
                    hname = "soup-onion" if "onion" in held.ingredients else "soup-tomato"
                else:
                    hname = held.name

                hat_frame = "%s-%shat" % (dname, color)
                cut_held = (held is not None and held.name in ("onion", "tomato")
                            and getattr(held, "chopped", False))
                cut_body = dname + "-" + (hname + "_cut") if cut_held else None

                if (cut_held and self.CHEFS_CUT_IMG
                        and cut_body in self.CHEFS_CUT_IMG.frames_rectangles):
                    body_sheet, body_frame = self.CHEFS_CUT_IMG, cut_body
                    hat_sheet = (self.CHEFS_CUT_IMG
                                 if hat_frame in self.CHEFS_CUT_IMG.frames_rectangles
                                 else self.CHEFS_IMG)
                else:
                    body_sheet = hat_sheet = self.CHEFS_IMG
                    body_frame = dname + (("-" + hname) if hname else "")

                if self._vis_positions is not None:
                    vx, vy = self._vis_positions[num]
                    pos = (int(round(self.UNSCALED_TILE_SIZE * vx)),
                           int(round(self.UNSCALED_TILE_SIZE * vy)))
                else:
                    pos = self._position_in_unscaled_pixels(player.position)

                body_sheet.blit_on_surface(surface, pos, body_frame)
                hat_sheet.blit_on_surface(surface, pos, hat_frame)

    return SimVisualizer


def run_visual(block_name, config, args):
    # Imports lourds/optionnels confinés au mode visuel (pygame non déclaré en deps).
    import pygame
    StateVisualizer = _import_state_visualizer()

    fps = args.fps or float(config.get("fps", 10))
    tpaa = 1 if args.unthrottled else args.ticks_per_ai_action
    horizon = compute_horizon(config, fps, args.max_ticks, args.max_game_length)

    trials, layouts_dir = resolve_layout_source(config, args.layouts)
    layout = args.layout or trials[0]["layout"]
    mdp, mlam = build_env(layout, config, layouts_dir)

    logger.info("Visuel : layout=%s | fps=%g tpaa=%d horizon=%d ticks | coop=%s",
                layout, fps, tpaa, horizon, not args.no_coop)

    pygame.init()
    viz = StateVisualizer()
    grid = mdp.terrain_mtx
    clock = pygame.time.Clock()
    win = {"surface": None}

    # [BUG 2] Interpolation : les chefs GLISSENT vers leur case logique au lieu de
    # « sauter » d'une case (le modèle bridé ne bouge qu'un tick sur ai_base_speed).
    # On rend SUBFRAMES sous-images par tick d'environnement, en rapprochant les
    # positions affichées de la cible (ease-out). Cadence réelle préservée
    # (SUBFRAMES x fps*SUBFRAMES = 1/fps par tick).
    SUBFRAMES = 3
    EASE = 0.35
    vis = {"pos": None}

    def on_tick(state, score, t):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                raise KeyboardInterrupt
        targets = [[float(p.position[0]), float(p.position[1])] for p in state.players]
        if vis["pos"] is None:
            vis["pos"] = [list(tp) for tp in targets]   # départ : pas d'animation
        hud = StateVisualizer.default_hud_data(
            state, score=int(score), time_left=round((horizon - t) / fps, 1)
        )
        for _ in range(SUBFRAMES):
            for i, tgt in enumerate(targets):
                vis["pos"][i][0] += EASE * (tgt[0] - vis["pos"][i][0])
                vis["pos"][i][1] += EASE * (tgt[1] - vis["pos"][i][1])
            viz._vis_positions = [tuple(p) for p in vis["pos"]]
            surf = viz.render_state(state, grid, hud_data=hud)
            if win["surface"] is None:
                win["surface"] = pygame.display.set_mode(surf.get_size())
                pygame.display.set_caption(f"Greedy x Greedy — {layout}")
            win["surface"].blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(fps * SUBFRAMES)

    try:
        result = rollout(
            mdp, mlam, fps=fps, ticks_per_ai_action=tpaa, horizon=horizon,
            seed=args.seed, auto_unstuck=not args.deterministic,
            coop=not args.no_coop, on_tick=on_tick,
        )
        result.update(layout=layout)
        status = "COMPLÉTÉ" if result["completed"] else "NON complété (horizon)"
        logger.info(
            "%s en %d ticks = %.1fs | %d décisions | %d/%d commandes | score=%.0f",
            status, result["ticks"], result["duration_s"], result["decisions"],
            result["orders_delivered"], result["orders_total"], result["sparse_reward"],
        )
        # Laisse la dernière frame affichée jusqu'à fermeture de la fenêtre.
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Deux GreedyAgent jouent des layouts ; mesure ticks + durée.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("config", help="nom du bloc de config, ex. config_test_visual")
    ap.add_argument("--config-path", default="config.json", help="chemin du config.json")
    ap.add_argument("--mode", choices=["headless", "visual"], default="headless")
    ap.add_argument("--layouts", default=None,
                    help="'blocs' (défaut), 'all', un DOSSIER (ex. 'generation_cesar_2' "
                         "ou un chemin), ou une liste 'test01,test05'")
    ap.add_argument("--layout", default=None,
                    help="[visuel] layout précis (défaut : 1er des blocs/liste)")
    ap.add_argument("--ticks-per-ai-action", type=int, default=None,
                    help="ticks entre 2 décisions d'un agent (défaut : ai_base_speed de la config)")
    ap.add_argument("--unthrottled", action="store_true",
                    help="agents à chaque tick (plancher théorique) ; ignore ticks-per-ai-action")
    ap.add_argument("--deterministic", action="store_true",
                    help="désactive l'anti-blocage aléatoire (auto_unstuck=False) ; risque de deadlock")
    ap.add_argument("--no-coop", action="store_true",
                    help="désactive la navigation coopérative -> greedy « fidèle prod » exact "
                         "(les paires greedy se bloquent sur la plupart des layouts)")
    ap.add_argument("--repeats", type=int, default=1, help="[headless] runs par layout (graines seed+r)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count(), help="[headless] process parallèles")
    ap.add_argument("--fps", type=float, default=None, help="override du fps de la config")
    ap.add_argument("--max-ticks", type=int, default=None,
                    help="override du plafond de ticks (défaut : MAX_GAME_LENGTH*fps, généreux)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="simulation_results.csv", help="[headless] fichier CSV de sortie")
    args = ap.parse_args(argv)

    CONFIG, config = load_config(args.config, args.config_path)
    # Défaut du bridage IA = ai_base_speed de la config (fidèle à la production).
    if args.ticks_per_ai_action is None:
        args.ticks_per_ai_action = int(config.get("ai_base_speed", 4))
    # MAX_GAME_LENGTH est une clé top-level (secondes) ; plafonne gameTime.
    args.max_game_length = CONFIG.get("MAX_GAME_LENGTH", config.get("gameTime", 50))

    if args.mode == "visual":
        run_visual(args.config, config, args)
    else:
        run_headless(args.config, config, args)


if __name__ == "__main__":
    main()
