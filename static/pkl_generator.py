"""
Pré-génère hors-ligne les pickles d'ENVIRONNEMENT que le serveur charge au runtime,
pour que le pré-chauffage au démarrage (app.py -> game.warmup_caches) soit un simple
CHARGEMENT de fichiers (quelques secondes) au lieu d'un recalcul complet (~30-40 min),
pendant lequel le worker eventlet unique est bloqué et ne répond à AUCUNE requête
(chargement infini côté navigateur puis NS_ERROR_NET_EMPTY_RESPONSE).

CE QUI EST GÉNÉRÉ — et pourquoi
--------------------------------
Le bon artefact est le MediumLevelActionManager : fichiers ``{layout}_am.pkl`` dans
``overcooked_ai_py/data/planners/``. C'est ce que charge le chemin runtime
``game.get_cached_mlam`` -> ``MediumLevelActionManager.from_pickle_or_compute`` ; l'agent
``PlanningAgent`` s'en sert à CHAQUE tick (ml_action / choose_motion_goal).

⚠️ Ne PAS générer de ``{layout}_mp.pkl`` (MotionPlanner) : construire un MLAM reconstruit
son propre MotionPlanner en interne (JointMotionPlanner -> MotionPlanner()), il ne relit
jamais ``*_mp.pkl``. Le seul lecteur de ``*_mp.pkl`` (game.py, self.mp) est commenté et
conditionné à ``show_potential=False`` : ces fichiers sont morts pour les configs actuelles.

POURQUOI C'EST LONG (et pourquoi on parallélise)
------------------------------------------------
~99 % du temps par layout est le JointMotionPlanner, qui pré-calcule le plan optimal pour
CHAQUE paire (état de départ des 2 agents -> état d'arrivée des 2 agents) : ~2,4 M
combinaisons pour 20 cases marchables, en Python pur. Le coût croît en ~P^4 (P = cases).
On ne touche PAS à cet algo (le contenu picklé doit rester identique, sinon l'agent change
de comportement) : on exploite le fait que chaque ``{layout}_am.pkl`` est INDÉPENDANT pour
répartir les layouts sur plusieurs cœurs (multiprocessing). Speedup ~ nombre de cœurs.

FIDÉLITÉ AU RUNTIME
-------------------
On réutilise EXACTEMENT les fonctions runtime (``game.get_cached_mdp`` /
``game.get_cached_mlam``) et la même construction de ``mdp_params``
(``OvercookedGridworld.mdp_overrides_from_config``) que ``game.warmup_caches``. La clé de
cache et le fichier produit sont donc strictement ceux que le serveur charge : pas de
recalcul-au-boot par invalidation (terrain_mtx / params). Le résultat parallèle est
BYTE-pour-byte équivalent au calcul série (aucune dépendance inter-layouts).

IMPORTANT : lancer depuis la RACINE du dépôt (les ``layouts_dir`` sont relatifs) et sur la
MÊME version des .layout + config.json que le serveur, puis livrer les ``*_am.pkl``. Les
layouts changent souvent : regénérer à chaque modification de layout.

Usage :
    python static/pkl_generator.py                 # toutes les configs, tous les cœurs
    PKL_JOBS=4 python static/pkl_generator.py       # limiter à 4 process (RAM)
    PKL_FORCE=1 python static/pkl_generator.py       # forcer le recalcul (ignore l'existant)
    CONF_PATH=config_autre.json python static/pkl_generator.py
"""
import os
import sys
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from time import time

# Racine du dépôt importable + CWD = racine (pour résoudre les layouts_dir relatifs).
# Fait AVANT le fork : les process enfants héritent de sys.path, du CWD et du module `game`
# déjà importé (start method 'fork' sous Linux), donc démarrage quasi instantané.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import game
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.data.planners import PLANNERS_DIR

CONF_PATH = os.getenv("CONF_PATH", "config.json")  # même défaut que app.py
FORCE = os.getenv("PKL_FORCE", "").lower() in ("1", "true", "yes")


def _count_am_pkl():
    try:
        return sum(1 for f in os.listdir(PLANNERS_DIR) if f.endswith("_am.pkl"))
    except OSError:
        return 0


def _generate_one(task):
    """Exécuté dans un PROCESS enfant. Construit + sauve {layout}_am.pkl via le chemin
    runtime exact. Ne renvoie que des métadonnées (le MLAM lui-même est écrit sur disque,
    jamais rapatrié par IPC)."""
    layout, layouts_dir, mdp_params = task
    t0 = time()
    try:
        mdp_template, key = game.get_cached_mdp(layout, layouts_dir, mdp_params)
        game.get_cached_mlam(mdp_template, key)  # from_pickle_or_compute -> save {layout}_am.pkl
        return (layout, time() - t0, None)
    except Exception as e:
        return (layout, time() - t0, repr(e))


def _build_work(CONFIG):
    """Aplatit toutes les configs d'expérience en une liste de tâches UNIQUES (dédupliquées
    par clé de cache runtime). Retourne (tasks, collisions)."""
    exp_configs = {
        cid: c for cid, c in CONFIG.items()
        if isinstance(c, dict) and "blocs" in c
    }
    tasks = {}            # cache_key -> (layout, layouts_dir, mdp_params)
    seen_params = {}      # layout -> mdp_params (pour détecter les collisions de nom)
    collisions = []
    for cid, config in exp_configs.items():
        try:
            mdp_params = dict(OvercookedGridworld.mdp_overrides_from_config(config))
        except Exception as e:
            print(f"[{cid}] mdp_overrides_from_config a échoué : {e} — config ignorée.")
            continue
        layouts_dir = config.get("layouts_dir", game.LAYOUTS_DIR)
        layouts = {
            l for trials in config.get("blocs", {}).values()
            if isinstance(trials, list) for l in trials
        }
        for layout in layouts:
            # Collision de nom : {layout}_am.pkl n'a pas de hash de params. Si deux configs
            # veulent le même layout avec des params différents, elles se disputent le
            # fichier -> recalcul au boot à chaque bascule. Aujourd'hui config_test et
            # config_testBIS ont des params identiques (pas de collision) ; on avertit sinon.
            prev = seen_params.get(layout)
            if prev is not None and prev != mdp_params:
                collisions.append(layout)
            seen_params.setdefault(layout, mdp_params)
            key = game._mdp_cache_key(layout, layouts_dir, mdp_params)
            tasks.setdefault(key, (layout, layouts_dir, mdp_params))
    return list(tasks.values()), sorted(set(collisions)), list(exp_configs)


def main():
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)

    tasks, collisions, exp_ids = _build_work(CONFIG)
    if not tasks:
        print(f"[pkl_generator] aucune config d'expérience (clé 'blocs') dans {CONF_PATH}.")
        return

    os.makedirs(PLANNERS_DIR, exist_ok=True)
    if FORCE:
        removed = 0
        for layout, _, _ in tasks:
            fp = os.path.join(PLANNERS_DIR, layout + "_am.pkl")
            try:
                os.remove(fp)
                removed += 1
            except OSError:
                pass
        print(f"[pkl_generator] PKL_FORCE : {removed} *_am.pkl supprimés (recalcul complet)")

    # Nombre de process : min(tâches, cœurs) par défaut, surchargé par PKL_JOBS. Chaque
    # process peut consommer quelques centaines de Mo (JointMotionPlanner) -> baisser PKL_JOBS
    # si la RAM est limitée sur la machine de génération.
    cpu = os.cpu_count() or 1
    jobs = int(os.getenv("PKL_JOBS", cpu))
    jobs = max(1, min(jobs, len(tasks)))

    before = _count_am_pkl()
    print(f"[pkl_generator] configs : {', '.join(exp_ids)}")
    print(f"[pkl_generator] {len(tasks)} layouts uniques | {jobs} process | cible {PLANNERS_DIR}")
    print(f"[pkl_generator] {before} *_am.pkl existants avant\n")
    for c in collisions:
        print(f"    ⚠️  COLLISION : '{c}' demandé avec des mdp_params différents selon la "
              f"config -> {c}_am.pkl ne peut en contenir qu'un (recalcul au boot).")

    t_all = time()
    n_ok = n_hit = n_err = 0
    done = 0
    total = len(tasks)

    # 'fork' : les enfants héritent de `game` déjà importé (pas de ré-import coûteux).
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
        futures = {ex.submit(_generate_one, t): t[0] for t in tasks}
        for fut in as_completed(futures):
            layout, dt, err = fut.result()
            done += 1
            if err is not None:
                n_err += 1
                print(f"    [{done:>2}/{total}] ✗ {layout:<16} {dt:6.1f}s  ÉCHEC : {err}")
            elif dt < 3.0:  # rechargé depuis un pickle valide existant
                n_hit += 1
                print(f"    [{done:>2}/{total}] · {layout:<16} {dt:6.1f}s  (chargé)")
            else:
                n_ok += 1
                print(f"    [{done:>2}/{total}] ✓ {layout:<16} {dt:6.1f}s  (calculé + sauvé)")

    after = _count_am_pkl()
    print(f"\n[pkl_generator] terminé en {time() - t_all:.1f}s : "
          f"{n_ok} calculés, {n_hit} chargés, {n_err} échecs sur {total}")
    print(f"[pkl_generator] {after} *_am.pkl dans {PLANNERS_DIR} (+{after - before})")
    if n_err:
        sys.exit(1)


if __name__ == "__main__":
    main()
