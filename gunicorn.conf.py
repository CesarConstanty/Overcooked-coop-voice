# Configuration gunicorn pour Overcooked-coop-voice.
#
# UN SEUL worker eventlet est IMPÉRATIF : l'application conserve un état global en
# mémoire de processus (GAMES / ACTIVE_GAMES / USERS / USER_ROOMS / PAGE_TRACKERS et
# les caches MDP/MLAM) qui n'est PAS partagé entre workers. Plusieurs workers feraient
# atterrir la requête HTTP et la WebSocket d'un même participant sur des process
# différents -> partie introuvable, perte de données. Pour plus de charge : CPU plus
# rapide (scale vertical), pas plus de workers.
#
# Lancement (via systemd) :
#   gunicorn -c gunicorn.conf.py app:app
#
# IMPORTANT : nécessite gunicorn < 23 (le worker eventlet a été retiré dans
# gunicorn >= 23). requirements.txt épingle déjà `gunicorn<23`.
import os

# --- Réseau ---
bind = os.getenv("BIND", "127.0.0.1:5000")   # derrière nginx ; ne pas exposer publiquement

# --- Modèle de worker ---
worker_class = "eventlet"
workers = 1                 # NE PAS augmenter (état global en mémoire)
worker_connections = 2000   # greenlets eventlet (sockets concurrents) par worker

# --- Délais ---
# Handshake/long-polling SocketIO + boucles de jeu en tâche de fond : timeouts généreux.
timeout = 120               # heartbeat du worker (eventlet est asynchrone)
graceful_timeout = 90       # temps laissé aux boucles play_game pour finir + sauvegarder
keepalive = 75              # >= ping_interval SocketIO (60 s) pour survivre aux keepalives

# --- Journaux (stdout/stderr -> journald via systemd) ---
accesslog = "-"
errorlog = "-"
loglevel = "info"

proc_name = "overcooked"


# --- Arrêt en douceur : rejouer la sauvegarde de secours des essais actifs que le
#     bloc __main__ assurerait normalement (gunicorn ne l'exécute pas). _on_shutdown
#     est idempotent : drain -> flush des essais actifs (_interrupted/) -> notifie.
#     IMPORTANT : on ne flush que depuis le WORKER (où `app` est déjà importé, donc
#     `import app` est instantané). Le master n'importe pas l'app (pas de preload) :
#     un hook master `import app` y déclencherait un warmup complet à l'arrêt. ---
def _flush(label):
    try:
        import app as overcooked_app
        overcooked_app._on_shutdown(label)
    except Exception:
        import traceback
        traceback.print_exc()


def worker_int(worker):
    # SIGINT/SIGQUIT reçu par le worker
    _flush("gunicorn-worker_int")


def worker_exit(server, worker):
    # Le worker se termine (arrêt/reload) : dernier filet de sauvegarde
    _flush("gunicorn-worker_exit")
