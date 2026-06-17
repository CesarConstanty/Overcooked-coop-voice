import os
from pathlib import Path
from socket import socket

# Import and patch the production eventlet server if necessary
# Test push commit

import eventlet

eventlet.monkey_patch()


# All other imports must come after patch to ensure eventlet compatibility
import time
import random
import pickle
import queue
import atexit
from socketio.exceptions import TimeoutError as SocketIOTimeOutError
import json
import glob
import logging
from logging.handlers import RotatingFileHandler
from time import gmtime, asctime
from threading import Lock
from copy import deepcopy
from utils import ThreadSafeSet, ThreadSafeDict, questionnaire_to_surveyjs
from flask import Flask, redirect, render_template, jsonify, request, session, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_session import Session
# Système d'authentification supprimé
# from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON
from game import OvercookedGame, OvercookedTutorial, Game, OvercookedPsiturk, PlanningGame
import game
from page_tracker import PageTracker

# Thoughts -- where I'll log potential issues/ideas as they come up
# Should make game driver code more error robust -- if overcooked randomlly errors we should catch it and report it to user
# Right now, if one user 'join's before other user's 'join' finishes, they won't end up in same game
# Could use a monitor on a conditional to block all global ops during calls to _ensure_consistent_state for debugging
# Could cap number of sinlge- and multi-player games separately since the latter has much higher RAM and CPU usage

###########
# Globals #
###########
# Read in global config
CONF_PATH = os.getenv('CONF_PATH', 'config.json')
TRIALS_PATH = os.getenv('CONF_PATH', 'trials.json')
with open(CONF_PATH, 'r') as f:
    CONFIG = json.load(f)

# Available layout names
LAYOUTS = CONFIG['layouts']

# Values that are standard across layouts
LAYOUT_GLOBALS = CONFIG['layout_globals']

# Maximum allowable game length (in seconds)
MAX_GAME_LENGTH = CONFIG['MAX_GAME_LENGTH']

# Path to where pre-trained agents will be stored on server
AGENT_DIR = CONFIG['AGENT_DIR']

# Maximum number of games that can run concurrently. Contrained by available memory and CPU
MAX_GAMES = CONFIG['MAX_GAMES']

# Frames per second cap for serving to client
MAX_FPS = CONFIG['MAX_FPS']

# Default configuration for planning experiment design
PLANNING_DESIGN_CONFIG = CONFIG['planning_design']

# Default configuration for tutorial
TUTORIAL_CONFIG = json.dumps(CONFIG['tutorial'])

# Global queue of available IDs. This is how we synch game creation and keep track of how many games are in memory
#FREE_IDS = queue.Queue(maxsize=MAX_GAMES)

# Bitmap that indicates whether ID is currently in use. Game with ID=i is "freed" by setting FREE_MAP[i] = True
#FREE_MAP = ThreadSafeDict()

# Initialize our ID tracking data
#for i in range(MAX_GAMES):
 #   FREE_IDS.put(i)
  #  FREE_MAP[i] = True

# Mapping of game-id to game objects
GAMES = ThreadSafeDict()

# Set of games IDs that are currently being played
ACTIVE_GAMES = ThreadSafeSet()

# Global dictionary to store PageTracker instances per user
PAGE_TRACKERS = ThreadSafeDict()

# Queue of games IDs that are waiting for additional players to join. Note that some of these IDs might
# be stale (i.e. if FREE_MAP[id] = True)
#WAITING_GAMES = queue.Queue()

# Mapping of users to locks associated with the ID. Enforces user-level serialization
USERS = ThreadSafeDict()


# Mapping of user id's to the current game (room) they are in
USER_ROOMS = ThreadSafeDict()

# Mapping of string game names to corresponding classes
GAME_NAME_TO_CLS = {
    "overcooked": OvercookedGame,
    "tutorial": OvercookedTutorial,
    "psiturk": OvercookedPsiturk,
    "planning": PlanningGame 
    # C'est grâce à la classe PlanningGame que sont calculé les différents paramètres nécessaires au déroulement de la partie
    # Ils sont ensuite renvoyés dans la variable data qui est à son tour exploitée tout au long du code
    # cette classe permet nottement de définir les essais et blocs courant de l'expérimentation
}

game._configure(MAX_GAME_LENGTH, AGENT_DIR)
#######################
# Random #
#######################

#random.seed(114101072025)

#######################
# Flask Configuration #
#######################
# Create and configure flask app
app = Flask(__name__, template_folder=os.path.join('static', 'templates'))
app.config['DEBUG'] = os.getenv('FLASK_ENV', 'production') == 'development'
app.config['SECRET_KEY'] = 'c-\x9f^\x80\xd8\xd0j\xed\xc1\x15\xf7\xc9\x97J{\x97\x165Iq#\x87\x88'
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
# Désactivé pour permettre HTTP : app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#app.config.update(SECRET_KEY='osd(99092=36&462134kjKDhuIS_d23', ENV='development')
socketio = SocketIO(app, cors_allowed_origins="*", logger=app.config['DEBUG'], ping_interval=60, ping_timeout=60)
# Système d'authentification désactivé - utilisation de sessions simples
# login_manager = LoginManager()
# login_manager.init_app(app)
db = SQLAlchemy()
db.init_app(app)


#####################
# Logging (journal) #
#####################
def setup_logging():
    """
    Configure le logger applicatif 'overcooked' : console + fichier rotatif horodaté.

    - eventlet-safe : les handlers utilisent un verrou (monkey-patché par eventlet),
      et les écritures restent ponctuelles (pas dans la boucle de jeu par frame).
    - idempotent : ne réinstalle pas les handlers si déjà configurés (reload).
    - les modules sans accès à `app` (ex. game.py) utilisent un logger enfant
      'overcooked.xxx' qui hérite de ces handlers.

    NB sécurité : ne jamais journaliser de mot de passe (cf. authenticate_participant).
    """
    log = logging.getLogger("overcooked")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG)
    log.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    log.addHandler(console)

    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/server.log", maxBytes=10 * 1024 * 1024, backupCount=50, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        log.addHandler(file_handler)
    except OSError:
        # Si le dossier logs n'est pas accessible, on garde au moins la console.
        log.warning("Impossible de créer logs/server.log ; journalisation console seule.")

    return log


logger = setup_logging()

# Pré-chauffage des caches MDP/mlam/agents au démarrage : déplace le coût de
# construction (sinon payé au 1er essai) vers le boot, pour que le premier
# participant démarre sans latence. Désactivable via config.json ("warmup_caches": false).
if CONFIG.get("warmup_caches", True):
    try:
        game.warmup_caches(CONFIG)
    except Exception:
        logger.exception("[WARMUP] échec inattendu du préchauffage des caches (démarrage poursuivi)")


def safe_json_write(file_path, data, user_id=None):
    """
    Écriture JSON atomique et idempotente.

    - Idempotence : n'écrase JAMAIS un fichier déjà présent (retourne False).
    - Atomicité : écrit dans un fichier temporaire puis os.replace() -> aucun
      fichier tronqué visible, même si l'écriture est interrompue.
    - Plus d'erreur silencieuse : tout échec réel est journalisé (logger.exception).

    Returns:
        bool: True si le fichier a été écrit, False sinon (déjà présent ou échec).
              NB : un appelant qui doit distinguer "déjà présent" de "échec" devra
              tester os.path.exists ; les appelants actuels n'utilisent pas le retour.
    """
    tmp_path = None
    try:
        if os.path.exists(file_path):
            logger.debug("[SAVE_SKIP] déjà présent: %s (uid=%s)", file_path, user_id)
            return False
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        tmp_path = "%s.%s.tmp" % (file_path, os.getpid())
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
        return True
    except Exception:
        logger.exception("[SAVE_FAILED] écriture impossible: %s (uid=%s)", file_path, user_id)
        if tmp_path:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
        return False


# =====================================================
# MODÈLE DE BASE DE DONNÉES
# =====================================================
class User(db.Model):
    """Modèle utilisateur pour stocker l'état de progression dans l'expérience."""
    uid = db.Column(db.String, primary_key=True)
    config = db.Column(JSON)
    step = db.Column(db.Integer) # Le bloc en cours
    trial = db.Column(db.Integer) # L'essaie en cours (correspondant au layout)

    def get_id(self):
        return str(self.uid)


with app.app_context():
    db.create_all()

#################
# MODIFICATIONS #	
#################

is_test = CONFIG.get('mode')
#is_test = "pas_test"
print("ceci est un : ",is_test)

#######################
# Session Management  #
#######################

def get_current_user():
    """
    Remplace current_user - récupère l'utilisateur actuel depuis la session
    """
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

def login_user_session(user):
    """
    Remplace login_user - connecte un utilisateur en stockant son ID en session
    """
    session['user_id'] = user.uid
    session['uid'] = user.uid
    session['config_id'] = user.config.get('config_id')
    session.permanent = True


def authenticate_participant(username, password, config_id=None):
    """
    [ÉCHAFAUDAGE] Identification du participant en mode `log_password = true`.

    Ce point d'entrée prépare le futur système d'inscription/connexion : pour
    l'instant, l'identifiant saisi sert directement d'`uid` de passation et le
    mot de passe N'EST PAS vérifié. L'intégration réelle (création de comptes,
    hachage et vérification du mot de passe, gestion inscription/connexion) sera
    réalisée plus tard.

    TODO(inscription):
      - stocker les comptes (table dédiée ou colonnes `username`/`password_hash`
        sur User), avec werkzeug.security.generate_password_hash / check_password_hash ;
      - distinguer inscription (création) et connexion (vérification) ;
      - renvoyer l'uid du compte authentifié, ou None si échec.

    SÉCURITÉ : ne jamais journaliser `password`.

    Returns:
        str | None : l'uid à utiliser pour la passation, ou None si identifiant vide.
    """
    username = (username or "").strip()
    if not username:
        return None
    # On journalise l'identifiant (jamais le mot de passe).
    logger.info("[LOGIN] mode=log_password username=%s config=%s", username, config_id)
    return username

def logout_user_session():
    """
    Remplace logout_user - déconnecte l'utilisateur
    """
    session.pop('user_id', None)

def login_required_session(f):
    """
    Remplace @login_required - décorateur pour vérifier l'authentification
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if current_user is None:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

#################################
# Page Tracking Functions      #
#################################

def get_page_tracker(user_id: str, config_id: str) -> PageTracker:
    """
    Récupère ou crée un PageTracker pour un utilisateur donné.
    
    Args:
        user_id: Identifiant de l'utilisateur
        config_id: Identifiant de la configuration expérimentale
        
    Returns:
        Instance PageTracker pour cet utilisateur
    """
    if user_id not in PAGE_TRACKERS:
        PAGE_TRACKERS[user_id] = PageTracker(user_id, config_id, logger=logger)
    return PAGE_TRACKERS[user_id]

def track_page_view(page_name: str, user_id: str = None, config_id: str = None):
    """
    Enregistre la visite d'une page pour l'utilisateur actuel.
    
    Args:
        page_name: Nom de la page visitée (ex: 'instructions.html')
        user_id: ID utilisateur (optionnel, récupéré depuis session si absent)
        config_id: ID config (optionnel, récupéré depuis session si absent)
    """
    try:
        # Récupérer les IDs depuis session si non fournis
        if not user_id:
            user_id = session.get('uid')
        if not config_id:
            config_id = session.get('config_id', 'default')
            
        if user_id:
            tracker = get_page_tracker(user_id, config_id)
            tracker.start_page(page_name)
    except Exception:
        pass

def end_user_session(user_id: str):
    """
    Termine la session de suivi pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
    """
    try:
        if user_id in PAGE_TRACKERS:
            PAGE_TRACKERS[user_id].end_session()
    except Exception:
        pass

#################################
# Global Coordination Functions #
#################################

def count_active_games():
    """Nombre de parties réellement occupées (au moins un joueur présent).

    On ignore les parties vides qui peuvent subsister dans GAMES après une
    déconnexion (un jeu actif devenu vide est désactivé mais pas toujours
    retiré de GAMES via cleanup_game), afin de ne pas gonfler artificiellement
    le compte et bloquer de nouveaux participants à tort.
    """
    n = 0
    for game in GAMES.values():
        try:
            if not game.is_empty():
                n += 1
        except Exception:
            # En cas de doute on compte la partie (prudence côté capacité).
            n += 1
    return n


def server_at_capacity():
    """True si le nombre de parties actives a atteint la limite MAX_GAMES."""
    return count_active_games() >= MAX_GAMES


def try_create_game(game_name, **kwargs):
    """
    Tries to create a brand new Game object based on parameters in `kwargs`

    Returns (Game, Error) that represent a pointer to a game object, and error that occured
    during creation, if any. In case of error, `Game` returned in None. In case of sucess,
    `Error` returned is None

    Possible Errors:
        - Runtime error if server is at max game capacity
        - Propogate any error that occured in game __init__ function
    """
    try:
        #curr_id = FREE_IDS.get(block=False)
        #assert FREE_MAP[curr_id], "Current id is already in use"
        game_cls = GAME_NAME_TO_CLS.get(game_name, OvercookedGame)
        if game_cls == OvercookedTutorial:
            kwargs["config"]["layouts_dir"] = "overcooked_ai_py/data/layouts"
        game = game_cls(**kwargs)
    #except queue.Empty:
    #    err = RuntimeError("Server at max capacity")
    #    return None, err
    except Exception as e:
        return None, e
    else:
        GAMES[game.id] = game
        #FREE_MAP[game.id] = False
        return game, None


def cleanup_game(game):
    #if FREE_MAP[game.id]:
     #   raise ValueError("Double free on a game")

    # User tracking
    for user_id in game.players:
        leave_curr_room(user_id)

    # Socketio tracking
    socketio.close_room(game.id)

    # Game tracking
    #FREE_MAP[game.id] = True
    #FREE_IDS.put(game.id)
    del GAMES[game.id]

    if game.id in ACTIVE_GAMES:
        ACTIVE_GAMES.remove(game.id)


def get_game(game_id):
    return GAMES.get(game_id, None)


def get_curr_game(user_id):
    return get_game(get_curr_room(user_id))


def get_curr_room(user_id):
    return USER_ROOMS.get(user_id, None)


def set_curr_room(user_id, room_id):
    USER_ROOMS[user_id] = room_id


def leave_curr_room(user_id):
    USER_ROOMS.pop(user_id, None)


# def get_waiting_game():
#     """
#     Return a pointer to a waiting game, if one exists

#     Note: The use of a queue ensures that no two threads will ever receive the same pointer, unless
#     the waiting game's ID is re-added to the WAITING_GAMES queue
#     """
#     try:
#         waiting_id = WAITING_GAMES.get(block=False)
#         while FREE_MAP[waiting_id]:
#             waiting_id = WAITING_GAMES.get(block=False)
#     except queue.Empty:
#         return None
#     else:
#         return get_game(waiting_id)


##########################
# Socket Handler Helpers #
##########################

def _leave_game(user_id):
    """
    Removes `user_id` from it's current game, if it exists. Rebroadcast updated game state to all
    other users in the relevant game.

    Leaving an active game force-ends the game for all other users, if they exist

    Leaving a waiting game causes the garbage collection of game memory, if no other users are in the
    game after `user_id` is removed
    """
    # Get pointer to current game if it exists
    game = get_curr_game(user_id)

    if not game:
        # Cannot leave a game if not currently in one
        return False

    # Acquire this game's lock to ensure all global state updates are atomic
    with game.lock:
        # Update socket state maintained by socketio
        leave_room(game.id)

        # Update user data maintained by this app
        leave_curr_room(user_id)

        # Update game state maintained by game object
        if user_id in game.players:
            game.remove_player(user_id)
        else:
            game.remove_spectator(user_id)

        # Whether the game was active before the user left
        was_active = game.id in ACTIVE_GAMES

        # Rebroadcast data and handle cleanup based on the transition caused by leaving
        if was_active and game.is_empty():
            # Active -> Empty
            game.deactivate()
        elif game.is_empty():
            # Waiting -> Empty
            cleanup_game(game)
        elif not was_active:
            # Waiting -> Waiting
            emit('waiting', {"in_game": True}, room=game.id)
        elif was_active and game.is_ready():
            # Active -> Active
            pass
        elif was_active and not game.is_empty():
            # Active -> Waiting
            game.deactivate()

    return was_active

# fonction permettant la création d'un nouveau jeu, 
# déclenche également un évènement socketIO pour lancer la partie
# cet évènement est capté par le fichier planning.js
def _create_game(user_id, game_name, params={}):
    current_user = get_current_user()
    existing_game = GAMES.get(game_name, None)
    if existing_game:
        cleanup_game(existing_game)
    game, err = try_create_game(game_name, **params)
    if not game:
        emit("creation_failed", {"error": err.__repr__()}, to=current_user.uid)
        print("error:" + (err.__repr__()))
        return
    spectating = True
    with game.lock:
        if not game.is_full():
            spectating = False
            game.add_player(user_id)
        else:
            spectating = True
            game.add_spectator(user_id)
        socketio.close_room(game.id) # ensure the same client is not in the same room with two sids after connect/disconnect . Will need to be changed in case of multiplayer games
        join_room(game.id)
        set_curr_room(user_id, game.id)
        game.activate() 
        ACTIVE_GAMES.add(game.id)
# Déclenche l'évènement pour lancer la partie qui est écouté par planning.js
# va également déclencher play_game qui permet de mettre à jour la partie
        emit('start_game', {"spectating": spectating,
                "start_info": game.to_json(), "trial": current_user.trial, "step": current_user.step, "config": game.config}, room=game.id)
        socketio.start_background_task(play_game, game, fps=current_user.config.get("fps",MAX_FPS))
        # else:
        #     WAITING_GAMES.put(game.id)
        #     emit('waiting', {"in_game": True}, room=game.id)


#####################
# Debugging Helpers #
#####################

def _ensure_consistent_state():
    """
    Simple sanity checks of invariants on global state data

    Let ACTIVE be the set of all active game IDs, GAMES be the set of all existing
    game IDs, and WAITING be the set of all waiting (non-stale) game IDs. Note that
    a game could be in the WAITING_GAMES queue but no longer exist (indicated by
    the FREE_MAP)

    - Intersection of WAITING and ACTIVE games must be empty set
    - Union of WAITING and ACTIVE must be equal to GAMES
    - id \\in FREE_IDS => FREE_MAP[id]
    - id \\in ACTIVE_GAMES => Game in active state
    - id \\in WAITING_GAMES => Game in inactive state
    """
    #waiting_games = set()
    active_games = set()
    all_games = set(GAMES)

    # for game_id in list(FREE_IDS.queue):
    #     assert FREE_MAP[game_id], "Freemap in inconsistent state"

    # for game_id in list(WAITING_GAMES.queue):
    #     if not FREE_MAP[game_id]:
    #         waiting_games.add(game_id)

    for game_id in ACTIVE_GAMES:
        active_games.add(game_id)

    # assert waiting_games.union(
    #     active_games) == all_games, "WAITING union ACTIVE != ALL"

    # assert not waiting_games.intersection(
    #     active_games), "WAITING intersect ACTIVE != EMPTY"

    assert all([get_game(g_id)._is_active for g_id in active_games]
               ), "Active ID in waiting state"
    # assert all([not get_game(g_id)._id_active for g_id in waiting_games]
    #            ), "Waiting ID in active state"


def get_agent_names():
    return [d for d in os.listdir(AGENT_DIR) if os.path.isdir(os.path.join(AGENT_DIR, d))]

######################
# Application routes #
######################

# Hitting each of these endpoints creates a brand new socket that is closed
# at after the server response is received. Standard HTTP protocol

@app.route('/')
def index():
    uid = request.args.get('PROLIFIC_PID', default=None)
    user_sid = "None"
    
    try:
        config_id = request.args.get('CONFIG', default=None)
        config = deepcopy(CONFIG[config_id])
        config["config_id"] = config_id
        
        # NOUVEAU: Préserver les labels de condition originaux pour les tutoriels
        config["condition_labels"] = dict(config["conditions"])  # Copie des labels originaux
        
        for bloc, value in config["conditions"].items():
            if value == "U":
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : False
            }
            elif value =="EV":
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : True,
            "asset_hud" : True,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : False
            }
            elif value =="EVa":
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : True,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : False
            }
            elif value =="EVr":
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : True,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : False
            }
            elif value =="EA" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : True,
            "recipe_sound" : True
            }
            elif value =="EAa" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : True,
            "recipe_sound" : False
            }
            elif value =="EAr" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : True
            }
            elif value =="E" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : True,
            "recipe_sound" : True,
            "visual_bubbles" : True,
            "visual_intention_recipe_duration": config.get("visual_intention_recipe_duration", 2000),
            "visual_intention_asset_duration": config.get("visual_intention_asset_duration", 1500),
            "visual_intention_next_duration": config.get("visual_intention_next_duration", 1000),
            "visual_intention_show_recipe": config.get("visual_intention_show_recipe", True),
            "visual_intention_show_asset": config.get("visual_intention_show_asset", True)
            }
            elif value =="Ea" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : False,
            "asset_hud" : True,
            "motion_goal" : False,
            "asset_sound" : True,
            "recipe_sound" : False
            }
            elif value =="Er" :
                config["conditions"][bloc]={
            "recipe_head": False,
            "recipe_hud" : True,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : True
            }
            elif value =="EVH" :
                config["conditions"][bloc]={
            "recipe_head": True,
            "recipe_hud" : False,
            "asset_hud" : False,
            "motion_goal" : False,
            "asset_sound" : False,
            "recipe_sound" : False,
            "visual_bubbles" : True,
            "visual_intention_recipe_duration": config.get("visual_intention_recipe_duration", 2000),
            "visual_intention_asset_duration": config.get("visual_intention_asset_duration", 1500),
            "visual_intention_next_duration": config.get("visual_intention_next_duration", 1000),
            "visual_intention_show_recipe": config.get("visual_intention_show_recipe", True),
            "visual_intention_show_asset": config.get("visual_intention_show_asset", True)
            }

    except KeyError:
        return render_template('UID_error.html')

    # ------------------------------------------------------------------
    # Mode d'identification du participant (par expérience : config["log_password"]).
    #   - log_password=False (historique) : identification par l'id du premier lien
    #     cliqué (PROLIFIC_PID), avec repli sur TEST_UID.
    #   - log_password=True : identifiant + mot de passe via le formulaire /login
    #     (ÉCHAFAUDAGE : cf. authenticate_participant ; inscription réelle à venir).
    # ------------------------------------------------------------------
    if config.get("log_password", False):
        uid = session.get('auth_uid')
        if not uid:
            # Pas encore authentifié : présenter le formulaire d'identification.
            return render_template('login.html', config_id=config_id)
        session["type"] = session.get("auth_type", "ACCOUNT")
    elif uid:
        session["type"] = "PROLIFIC"
    else:
        uid = request.args.get('TEST_UID', default=None)
        session["type"] = "TEST"
    if uid:
        user = User.query.filter_by(uid=uid).first()
        if user:
            login_user_session(user)
        else:
            # Capacité serveur : un NOUVEAU participant ne peut commencer
            # l'expérience que si le nombre de parties simultanées n'a pas
            # atteint MAX_GAMES. Les participants déjà enregistrés (branche
            # `if user`) ne sont jamais bloqués et peuvent toujours reprendre.
            if server_at_capacity():
                logger.info(
                    "[CAPACITY] Inscription refusée pour uid=%s : %d/%d parties actives",
                    uid, count_active_games(), MAX_GAMES)
                return render_template('full.html', max_games=MAX_GAMES)
            new_user = User(uid=uid, config=config, step=0, trial=0)

            # Questionnaires : normalisation/validation du bloc config unifié
            # "questionnaires" (synthèse rétro-compatible depuis les anciennes
            # clés si absent). Les questionnaires sont désormais des pages HTML
            # autonomes (plus de chargement JSON/SurveyJS ici).
            normalize_questionnaire_config(new_user.config)

            # Shuffle des trials si nécessaire (depuis old_app.py)
            if new_user.config.get("shuffle_trials", False) == True:
                for key, value in new_user.config["blocs"].items():
                    random.shuffle(value)
            
            # gère la randomisation des blocs
            if new_user.config.get("shuffle_blocs", False):
                # SHUFFLE_BLOCS = TRUE : Ordre aléatoire
                bloc_keys = list(new_user.config["blocs"].keys())
                random.shuffle(bloc_keys)
                new_user.config["bloc_order"] = bloc_keys
                print(f"🎲 SHUFFLE_BLOCS=TRUE - Ordre randomisé: {bloc_keys}")
                bloc_key = new_user.config["bloc_order"][new_user.step]
                print(f"🎲 Premier bloc sélectionné: {bloc_key}")
                print(f"🎲 Liste des essais du premier bloc: {new_user.config['blocs'][bloc_key]}")
            else:
                # SHUFFLE_BLOCS = FALSE : Ordre croissant strict (0, 1, 2, ...)
                bloc_keys = sorted(new_user.config["blocs"].keys(), key=lambda x: int(x))
                new_user.config["bloc_order"] = bloc_keys
                print(f"📋 SHUFFLE_BLOCS=FALSE - Ordre croissant: {bloc_keys}")
                if bloc_keys:
                    premier_bloc = bloc_keys[0]
                    print(f"📋 Premier bloc sélectionné (step 0): {premier_bloc}")
            
            # Gère la randomisation des labels d'attribution de responsabilité
            if new_user.config.get("randomize_accountability_labels", False):
                # RANDOMIZE_ACCOUNTABILITY_LABELS = TRUE : Ordre aléatoire des labels
                accountability_labels = ["Me", "The artificial agent"]
                random.shuffle(accountability_labels)
                new_user.config["accountability_label_order"] = accountability_labels
                print(f"🎲 RANDOMIZE_ACCOUNTABILITY_LABELS=TRUE - Ordre randomisé: {accountability_labels}")
            else:
                # RANDOMIZE_ACCOUNTABILITY_LABELS = FALSE : Ordre standard (moi, IA)
                accountability_labels = ["Me", "The artificial agent"]
                new_user.config["accountability_label_order"] = accountability_labels
                print(f"📋 RANDOMIZE_ACCOUNTABILITY_LABELS=FALSE - Ordre standard: {accountability_labels}")
            
            db.session.add(new_user)
            db.session.commit()
            login_user_session(new_user)
        
        # Suivi temporel : enregistrer la visite de la page index
        track_page_view('index.html', uid, config_id)
        
        return render_template('index.html', uid=uid, layout_conf=LAYOUT_GLOBALS)
    else:
        return render_template('UID_error.html')


@app.route('/login', methods=['POST'])
def login():
    """
    [ÉCHAFAUDAGE] Point d'entrée du mode d'identification `log_password = true`.

    Reçoit l'identifiant + mot de passe du formulaire login.html, délègue à
    authenticate_participant (vérification réelle à implémenter plus tard), puis
    redirige vers la route index qui poursuit le flux normal de passation.
    """
    config_id = request.form.get('CONFIG') or request.args.get('CONFIG')
    username = request.form.get('username', '')
    password = request.form.get('password', '')

    uid = authenticate_participant(username, password, config_id)
    if not uid:
        return render_template('login.html', config_id=config_id,
                               error="Veuillez renseigner un identifiant.")

    # Authentification (échafaudée) réussie : on mémorise l'uid pour la session.
    session['auth_uid'] = uid
    session['auth_type'] = "ACCOUNT"
    return redirect(url_for('index', CONFIG=config_id))


@app.route('/instructions', methods=['GET', 'POST'])
def instructions():
    # Récupérer l'UID et la CONFIG depuis les paramètres URL ou session
    uid = request.args.get('PROLIFIC_PID') or request.args.get('TEST_UID') or session.get('uid')
    config_id = request.args.get('CONFIG') or session.get('config_id')
    
    if not uid or not config_id:
        return render_template('UID_error.html')
    
    # Récupérer la configuration depuis le fichier global
    try:
        config = CONFIG[config_id]
        config["config_id"] = config_id
    except KeyError:
        return render_template('UID_error.html')
    
    # Vérifier s'il y a des explications dans les conditions
    condition = config.get("conditions", {})
    is_explained = False
    
    # Tester si au moins une intention est donnée à un moment donné
    all_conditions = list(condition.values()) if condition else []
    if any(all_conditions):
        is_explained = True
    
    mechanic_type = config.get("mechanic", "recipe")
    isAgency = config.get("agency", False)
    
    if request.method == 'POST':
        form = request.form.to_dict()
        form["timestamp"] = gmtime()
        form["date"] = asctime(form["timestamp"])
        form["useragent"] = request.headers.get('User-Agent')
        #form["IPadress"] = request.remote_addr
        #
        if form.get("consentRadio") == "accept":
            Path("trajectories/" + config_id + "/"+ uid).mkdir(parents=True, exist_ok=True)
            
            file_name = 'trajectories/' + config_id + "/" + uid + '/CONSENT.json'
            success = safe_json_write(file_name, form, uid)
            
            if condition:
                if mechanic_type == "recipe":
                    # Récupérer les valeurs depuis la config ou les defaults
                    onion_time = config.get("onion_time", LAYOUT_GLOBALS.get("onion_time", 15))
                    tomato_time = config.get("tomato_time", LAYOUT_GLOBALS.get("tomato_time", 7))
                    onion_value = config.get("onion_value", LAYOUT_GLOBALS.get("onion_value", 21))
                    tomato_value = config.get("tomato_value", LAYOUT_GLOBALS.get("tomato_value", 13))
                    # [CUTTING BOARD] Paramètres de découpe pour les instructions
                    cutting_enabled = config.get("cutting_enabled", LAYOUT_GLOBALS.get("cutting_enabled", False))
                    chop_time = config.get("chop_time", LAYOUT_GLOBALS.get("chop_time", {}))
                    recipes_requiring_chopping = config.get("recipes_requiring_chopping", LAYOUT_GLOBALS.get("recipes_requiring_chopping", []))


                    # Suivi temporel : enregistrer la visite de la page instructions_recipe
                    track_page_view('instructions_recipe.html', uid, config.get("config_id"))

                    return render_template('instructions_recipe.html',
                                            is_explained=is_explained,
                                            onion_time=onion_time,
                                            tomato_time=tomato_time,
                                            onion_value=onion_value,
                                            tomato_value=tomato_value,
                                            cutting_enabled=cutting_enabled,
                                            chop_time=chop_time,
                                            recipes_requiring_chopping=recipes_requiring_chopping,
                                            config=config,
                                            timer_max=config.get('explications_generales_max', 600),
                                            timer_min=config.get('explications_generales_min', 120))
                #return redirect(url_for('qvg_survey'))

            else:
                return render_template('condition_error.html')

        else:
            Path("trajectories/" + uid).mkdir(parents=True, exist_ok=True)
            
            file_name = 'trajectories/' + uid + '/NOT_CONSENT.json'
            safe_json_write(file_name, form, uid)
            
            return render_template('leave.html', uid=uid, complete=False)
    
    # Suivi temporel : enregistrer la visite de la page instructions (GET)
    track_page_view('instructions.html', uid, config.get("config_id"))
    
    # Affichage initial de la page d'instructions (GET)
    return render_template('instructions.html', 
                          uid=uid, 
                          config=config,
                          researcher=config.get("researcher", {}),
                          supervisor=config.get("supervisor", {}),
                          onion_time=config.get("onion_time", LAYOUT_GLOBALS.get("onion_time", 15)),
                          tomato_time=config.get("tomato_time", LAYOUT_GLOBALS.get("tomato_time", 7)),
                          onion_value=config.get("onion_value", LAYOUT_GLOBALS.get("onion_value", 21)),
                          tomato_value=config.get("tomato_value", LAYOUT_GLOBALS.get("tomato_value", 13)),
                          max_num_ingredients=config.get("max_num_ingredients", LAYOUT_GLOBALS.get("max_num_ingredients", 3)),
                          order_bonus=config.get("order_bonus", LAYOUT_GLOBALS.get("order_bonus", 2)),
                          cutting_enabled=config.get("cutting_enabled", LAYOUT_GLOBALS.get("cutting_enabled", False)),
                          chop_time=config.get("chop_time", LAYOUT_GLOBALS.get("chop_time", {})),
                          recipes_requiring_chopping=config.get("recipes_requiring_chopping", LAYOUT_GLOBALS.get("recipes_requiring_chopping", [])))


@app.route('/instructions_explained')
def instructions_explained():
    uid = request.args.get('UID')
    # Suivi temporel : enregistrer la visite de la page instructions expliquées
    track_page_view('instructions_explained.html', uid)
    #agent_names = get_agent_names()
    return render_template('instructions_explained.html', uid=uid, layout_conf=LAYOUT_GLOBALS)


@app.route('/planning', methods=['GET', 'POST'])
def planning():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    uid = current_user.uid
    
    bloc_order = current_user.config.get("bloc_order", [])
    
    if current_user.step >= len(bloc_order):
        print(f"Utilisateur {uid} terminé tous les blocs (step {current_user.step}), redirection vers les questionnaires de fin")
        return redirect(url_for('questionnaire', slot='end'))
    
    # --- GESTION DES TUTORIELS DE CONDITION ---
    # Vérifier si l'utilisateur doit voir le tutoriel de condition avant de commencer le bloc
    from_tutorial = request.args.get('from_condition_tutorial', False)
    should_show_tutorial = (
        current_user.trial == 0 and  # Début d'un nouveau bloc
        not from_tutorial and  # Pas déjà venu du tutoriel
        current_user.config.get("condition_tutorials")  # Tutoriels configurés
    )
    
    # Debug des informations de bloc
    bloc_order = current_user.config.get("bloc_order", [])
    print(f"🎯 SÉLECTION BLOC - Utilisateur {uid}:")
    print(f"   Step actuel: {current_user.step}")
    print(f"   Ordre des blocs: {bloc_order}")
    if current_user.step < len(bloc_order):
        bloc_actuel = bloc_order[current_user.step]
        condition_actuelle = current_user.config.get("conditions", {}).get(bloc_actuel, "Non définie")
        print(f"   Bloc actuel (step {current_user.step}): {bloc_actuel}")
        print(f"   Condition actuelle: {condition_actuelle}")
    else:
        print(f"   ⚠️  Step {current_user.step} dépasse la longueur des blocs ({len(bloc_order)})")
    
    print(f"DEBUG TUTORIEL - Utilisateur {uid}: trial={current_user.trial}, from_tutorial={from_tutorial}, condition_tutorials présent={bool(current_user.config.get('condition_tutorials'))}")
    print(f"DEBUG TUTORIEL - should_show_tutorial={should_show_tutorial}")
    
    if should_show_tutorial:
        try:
            bloc_key = current_user.config["bloc_order"][current_user.step]
            
            # Récupérer le label de condition depuis condition_labels (préservé depuis /index)
            condition_label = current_user.config.get("condition_labels", {}).get(bloc_key)
            
            # Si condition_labels n'existe pas, est vide, ou contient un dict, déduire depuis la configuration
            if not condition_label or isinstance(condition_label, dict):
                condition_config = current_user.config["conditions"][bloc_key]
                if isinstance(condition_config, dict):
                    # Logique inverse : déterminer le label depuis la configuration
                    # Vérifier d'abord EVH (nouvelle condition avec visual_bubbles)
                    if (condition_config.get("visual_bubbles") == True and 
                        condition_config.get("recipe_head") == True):
                        condition_label = "EVH"
                    elif (condition_config.get("recipe_hud") == False and 
                        condition_config.get("asset_hud") == False and
                        condition_config.get("asset_sound") == False and
                        condition_config.get("recipe_sound") == False and
                        condition_config.get("visual_bubbles") != True):
                        condition_label = "U"
                    elif (condition_config.get("recipe_hud") == True and 
                          condition_config.get("asset_hud") == True and
                          condition_config.get("asset_sound") == False):
                        condition_label = "EV"
                    elif (condition_config.get("asset_sound") == True and 
                          condition_config.get("recipe_sound") == True):
                        condition_label = "EA"
                    else:
                        condition_label = None
                        print(f"ERREUR: Configuration inconnue pour bloc {bloc_key}: {condition_config}")
                else:
                    condition_label = condition_config
            
            print(f"DEBUG TUTORIEL - bloc_key={bloc_key}, condition_label={condition_label} (type: {type(condition_label)})")
            
            condition_tutorials = current_user.config.get("condition_tutorials", {})
            print(f"DEBUG TUTORIEL - condition_tutorials={condition_tutorials}")
            
            # Si un tutoriel existe pour cette condition, y rediriger
            if condition_label and isinstance(condition_label, str) and condition_label in condition_tutorials:
                print(f"Redirection vers tutoriel de condition {condition_label} pour bloc {bloc_key} (step {current_user.step})")
                return redirect(url_for('condition_tutorial'))
            else:
                print(f"Aucun tutoriel configuré pour condition {condition_label} ou type incorrect: {type(condition_label)}")
        except (KeyError, IndexError) as e:
            print(f"Erreur lors de la vérification tutoriel pour utilisateur {uid}: {e}")
            # Continuer vers planning normal en cas d'erreur
    
    # --- LOGIQUE PLANNING NORMALE ---
    try:
        bloc_key = current_user.config["bloc_order"][current_user.step]
        # Pour l'affichage, utiliser les conditions transformées (dictionnaires)
        condition = current_user.config["conditions"][bloc_key]
        # Pour le logging, utiliser le label simple
        condition_label = current_user.config.get("condition_labels", {}).get(bloc_key, "inconnu")
        print(f"Planning - Utilisateur {uid}, bloc {bloc_key}, condition {condition_label}, trial {current_user.trial}")
    except (KeyError, IndexError) as e:
        print(f"Erreur configuration bloc pour utilisateur {uid}: {e}")
        condition = request.args.get('CONDITION', 'U')  # Fallback
    
    agent_names = get_agent_names()

    # Garde reprise/retour : si l'essai courant a déjà été joué (trajectoire
    # présente) mais qu'on revient sur /planning, ne pas le rejouer : pousser
    # vers le questionnaire post-essai.
    if current_trial_played(current_user):
        return redirect(url_for('questionnaire', slot='post_trial'))

    # --- RENDU TEMPLATE ---
    # Les questionnaires (post-essai/post-bloc) ne sont plus rendus ici : ce
    # sont des pages HTML autonomes servies par /questionnaire/<slot>.
    total_blocs = len(current_user.config["bloc_order"])
    bloc_key = current_user.config["bloc_order"][current_user.step]
    current_condition = current_user.config["conditions"][bloc_key]
    current_trials = current_user.config["blocs"][bloc_key]

    # Suivi temporel : enregistrer la visite de la page planning
    track_page_view('planning.html', current_user.uid, current_user.config.get("config_id"))

    return render_template(
        "planning.html",
        uid=current_user.uid,
        step=current_user.step,
        condition=current_condition,
        bloc=bloc_key,
        config=json.dumps(current_user.config),
        trials=json.dumps(current_trials),
        total_blocs=total_blocs,
        dev_mode=current_user.config.get("dev", False)
    )
@app.route('/transition', methods=['GET', 'POST'])
def transition():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    uid = current_user.uid
    step = current_user.step
    bloc_key = current_user.config["bloc_order"][current_user.step]
    condition = current_user.config["conditions"][bloc_key]
    form = {}
    form["answer"] = request.form.to_dict()
    form["step"] = step
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = condition
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])

    Path("trajectories/" + uid).mkdir(parents=True, exist_ok=True)
    file_name = f"trajectories/{uid}/{uid}_{step}QPB.json"
    
    # Ne pas écraser si le fichier existe déjà : conserver la première soumission
    if os.path.exists(file_name):
        pass
    else:
        safe_json_write(file_name, form, uid)
    
    step += 1
    return render_template('goodbye.html', uid=uid, step=step, completion_link=current_user.config["completion_link"])
    # else :
    #   return render_template('bloc_transition.html', uid = uid, step = step)

@app.route('/qex_ranking', methods=['GET'])
def qex_ranking():
    # Route legacy : redirige vers le séquenceur unifié (slot 'end').
    if not get_current_user():
        return redirect(url_for('index'))
    return redirect(url_for('questionnaire', slot='end'))


# ============================================================================
# Système unifié de questionnaires (pages HTML autonomes, pilotées par config)
# ----------------------------------------------------------------------------
# Tous les questionnaires sont servis comme des pages HTML autonomes via un
# séquenceur générique. Le placement est paramétrable dans config.json :
#     "questionnaires": {
#         "begin": ["QVG", "PTTA"], "post_trial": ["agency"],
#         "post_bloc": ["AAT_L", "hoffman"], "end": ["preference"]
#     }
# La logique de nommage des fichiers de résultats est STRICTEMENT préservée.
# ============================================================================

QUESTIONNAIRE_SLOTS = ("begin", "post_trial", "post_bloc", "end")


# --- Constructeurs de chemins ----------------------------------------------
# Les questionnaires historiques conservent leur nommage de sauvegarde FIGÉ
# (rétro-compat des données déjà collectées). Les questionnaires génériques
# (Likert fournis comme simples templates) passent par _path_generic :
# l'emplacement de sauvegarde découle du slot où on les place, ce qui permet de
# poser le même questionnaire à n'importe quel endroit de l'expérience.
_SLOT_DIRS = {
    "begin": "Pre_experiment",
    "post_trial": "QPT",
    "post_bloc": "QPB",
    "end": "Post_experiment",
}

def _path_generic(uid, step, trial, cid, slot=None, name=None):
    sub = _SLOT_DIRS.get(slot, "Questionnaires")
    if slot == "post_trial":
        return f"trajectories/{cid}/{uid}/{sub}/{uid}_{step}_{trial}_{name}.json"
    return f"trajectories/{cid}/{uid}/{sub}/{uid}_{step}_{name}.json"

# Instruments historiques : nommage FIGÉ dans leur slot natif (rétro-compat des
# données déjà collectées) ; nommage générique slot-aware si on les place ailleurs.
def _path_qvg(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "begin"):
        return f"trajectories/{cid}/{uid}/Pre_experiment/{uid}_{step}_QVG.json"
    return _path_generic(uid, step, trial, cid, slot, name or "QVG")

def _path_ptta(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "begin"):
        return f"trajectories/{cid}/{uid}/Pre_experiment/{uid}_{step}_PTTA.json"
    return _path_generic(uid, step, trial, cid, slot, name or "PTTA")

def _path_agency(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "post_trial"):
        return f"trajectories/{cid}/{uid}/QPT/{uid}_{step}_{trial}_QPT.json"
    return _path_generic(uid, step, trial, cid, slot, name or "agency")

def _path_aat_l(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "post_bloc"):
        return f"trajectories/{cid}/{uid}/QPB/{uid}_{step}AAT_L.json"
    return _path_generic(uid, step, trial, cid, slot, name or "AAT_L")

def _path_hoffman(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "post_bloc"):
        return f"trajectories/{cid}/{uid}/QPB/{uid}_{step}HOFFMAN.json"
    return _path_generic(uid, step, trial, cid, slot, name or "hoffman")

def _path_preference(uid, step, trial, cid, slot=None, name=None):
    if slot in (None, "end"):
        return f"trajectories/{cid}/{uid}/Post_experiment/{uid}_{step}_preference.json"
    return _path_generic(uid, step, trial, cid, slot, name or "preference")


# --- Fonctions de sauvegarde (corps repris verbatim des anciens handlers) --
def save_qvg(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    try:
        bloc_key = config["bloc_order"][step]
        condition = config["conditions"][bloc_key]
    except (KeyError, IndexError):
        form_data["condition"] = "N/A"
    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])
    qvg_json_string = form_req.get('qvg_data')
    try:
        form_data["qvg_response"] = json.loads(qvg_json_string) if qvg_json_string else {}
    except json.JSONDecodeError:
        form_data["qvg_response"] = {}
    file_name = _path_qvg(uid, step, user.trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form_data, uid)


def save_ptta(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])
    ptta_json_string = form_req.get('ptta_data')
    try:
        form_data["ptta_response"] = json.loads(ptta_json_string) if ptta_json_string else {}
    except json.JSONDecodeError:
        form_data["ptta_response"] = {}
    file_name = _path_ptta(uid, step, user.trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form_data, uid)


def save_agency(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    trial = user.trial
    bloc_key = config["bloc_order"][step]
    mapping = {"q1": "control_used", "q2": "control_felt", "q3": "accountability"}
    form = {}
    form["answer"] = {mapping[k]: form_req.get(k) for k in ("q1", "q2", "q3")}
    acc_labels = config.get("accountability_label_order", ["Me", "The artificial agent"])
    if isinstance(acc_labels, list) and len(acc_labels) >= 2:
        form["accountability_order"] = [acc_labels[0], "The team", acc_labels[1]]
    else:
        form["accountability_order"] = ["Me", "The team", "The artificial agent"]
    form["timeout_bool"] = (form_req.get("timeout_bool", "false") == "true")
    form["step"] = step
    form["trial"] = trial
    form["trial_id"] = f"{uid}_{bloc_key}_{trial}_QPT"
    form["layout"] = config["blocs"][bloc_key][trial]
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = config["conditions"][bloc_key]
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])
    file_name = _path_agency(uid, step, trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form, uid)


def save_aat_l(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    bloc_key = config["bloc_order"][step]
    form = {}
    form["answer"] = {k: v for k, v in form_req.items() if k.startswith("Q")}
    form["step"] = step
    form["trial_id"] = f"{uid}_{bloc_key}_QPB"
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = config["conditions"][bloc_key]
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])
    file_name = _path_aat_l(uid, step, user.trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form, uid)


def save_hoffman(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    bloc_key = config["bloc_order"][step]
    form = {}
    form["answer"] = {k: v for k, v in form_req.items() if k.startswith("Q")}
    form["step"] = step
    form["trial_id"] = f"{uid}_{bloc_key}_HOFFMAN"
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = config["conditions"][bloc_key]
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])
    file_name = _path_hoffman(uid, step, user.trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form, uid)


def save_generic_likert(user, form_req, slot=None, name=None):
    """Sauvegarde générique d'un questionnaire Likert (champs Q*).

    L'emplacement et les métadonnées découlent du slot où le questionnaire est
    placé : on peut donc poser le même template à n'importe quel endroit de
    l'expérience et en récupérer les réponses. Pas de dépendance dure au bloc
    (condition défensive) pour rester valable au slot "begin" comme ailleurs."""
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    trial = user.trial
    form = {}
    form["answer"] = {k: v for k, v in form_req.items() if k.startswith("Q")}
    form["slot"] = slot
    form["step"] = step
    if slot == "post_trial":
        form["trial"] = trial
    form["user_agent"] = request.headers.get('User-Agent')
    try:
        bloc_key = config["bloc_order"][step]
        form["condition"] = config["conditions"][bloc_key]
        if slot == "post_trial":
            form["trial_id"] = f"{uid}_{bloc_key}_{trial}_{name}"
        else:
            form["trial_id"] = f"{uid}_{bloc_key}_{name}"
    except (KeyError, IndexError):
        form["condition"] = "N/A"
        form["trial_id"] = f"{uid}_{name}"
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])
    sub = _SLOT_DIRS.get(slot, "Questionnaires")
    Path(f"trajectories/{config_id}/{uid}/{sub}").mkdir(parents=True, exist_ok=True)
    file_name = _path_generic(uid, step, trial, config_id, slot, name)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form, uid)


def save_preference(user, form_req, slot=None, name=None):
    uid = user.uid
    config = user.config
    config_id = config["config_id"]
    step = user.step
    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    try:
        bloc_key = config["bloc_order"][step]
        condition = config["conditions"][bloc_key]
    except (KeyError, IndexError):
        form_data["condition"] = "N/A"
    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])
    ranking_json_string = form_req.get('ranking_data')
    try:
        form_data["ranking_response"] = json.loads(ranking_json_string) if ranking_json_string else []
    except json.JSONDecodeError:
        form_data["ranking_response"] = []
    form_data["timeout_bool"] = form_req.get('timeout_bool', 'false') == 'true'
    form_data["explanation_text"] = form_req.get('explanation_text', '')
    file_name = _path_preference(uid, step, user.trial, config_id, slot, name)
    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(file_name):
        safe_json_write(file_name, form_data, uid)


# --- Fonctions de contexte de rendu (variables passées au template) --------
def _ctx_default(user, slot=None):
    return {}

def _ctx_agency(user, slot=None):
    return {
        "accountability_labels": user.config.get(
            "accountability_label_order", ["Me", "The artificial agent"]),
        "score": request.args.get("score", ""),
    }

def _ctx_post_bloc(user, slot=None):
    return {"step": user.step}

def _ctx_preference(user, slot=None):
    return {"num_blocs": len(user.config.get("bloc_order", []))}


# --- Registre : nom de questionnaire -> métadonnées ------------------------
# "slot" = emplacements autorisés (ici QUESTIONNAIRE_SLOTS pour tous) : n'importe
# quel questionnaire peut être placé n'importe où via la config. Les instruments
# spécifiques gardent leur template, save et nommage de fichier dédiés (figés dans
# leur slot natif, génériques ailleurs) ; les Likert génériques utilisent
# _path_generic / save_generic_likert (réponses Q*).
QUESTIONNAIRE_REGISTRY = {
    "QVG":        {"slot": QUESTIONNAIRE_SLOTS, "template": "experience_video_games_en.html", "path": _path_qvg,        "save": save_qvg,        "context": _ctx_default},
    "PTTA":       {"slot": QUESTIONNAIRE_SLOTS, "template": "PTT_A_en.html",                  "path": _path_ptta,       "save": save_ptta,       "context": _ctx_default},
    "agency":     {"slot": QUESTIONNAIRE_SLOTS, "template": "agency.html",                    "path": _path_agency,     "save": save_agency,     "context": _ctx_agency},
    "AAT_L":      {"slot": QUESTIONNAIRE_SLOTS, "template": "AAT_L.html",                     "path": _path_aat_l,      "save": save_aat_l,      "context": _ctx_post_bloc},
    "hoffman":    {"slot": QUESTIONNAIRE_SLOTS, "template": "hoffman.html",                   "path": _path_hoffman,    "save": save_hoffman,    "context": _ctx_post_bloc},
    "GAbstractionP":    {"slot": QUESTIONNAIRE_SLOTS, "template": "GAbstractionP.html",        "path": _path_generic, "save": save_generic_likert, "context": _ctx_default},
    "GAbstractionP_fr": {"slot": QUESTIONNAIRE_SLOTS, "template": "GAbstractionP_fr.html",     "path": _path_generic, "save": save_generic_likert, "context": _ctx_default},
    "preference": {"slot": QUESTIONNAIRE_SLOTS, "template": "preference order_en.html",       "path": _path_preference, "save": save_preference, "context": _ctx_preference},
}


def _template_exists(template_name):
    """True si Flask peut charger ce template (même dossier que render_template)."""
    try:
        app.jinja_env.loader.get_source(app.jinja_env, template_name)
        return True
    except Exception:
        return False


def resolve_questionnaire(name):
    """Métadonnées du questionnaire référencé en config.

    1) Nom au registre -> son entrée (instruments spécifiques : agency, preference,
       QVG, AAT_L... avec nommage de sauvegarde dédié et figé).
    2) Sinon, si un template ``static/templates/<name>.html`` existe -> questionnaire
       Likert générique posable dans N'IMPORTE QUEL slot ; les réponses ``Q*`` sont
       sauvegardées selon l'emplacement (cf. save_generic_likert). Autrement dit :
       fournir le template et citer le nom en config suffit, sans toucher au code.
    3) Sinon -> None (ignoré, avec un avertissement)."""
    entry = QUESTIONNAIRE_REGISTRY.get(name)
    if entry is not None:
        return entry
    if (isinstance(name, str) and name
            and not any(c in name for c in ('/', '\\', '..'))
            and _template_exists(f"{name}.html")):
        return {
            "slot": QUESTIONNAIRE_SLOTS,
            "template": f"{name}.html",
            "path": _path_generic,
            "save": save_generic_likert,
            "context": _ctx_default,
        }
    return None


def normalize_questionnaire_config(config):
    """Garantit la présence d'un bloc config["questionnaires"] valide.

    Si absent, le synthétise depuis les anciennes clés (rétro-compat). Filtre
    les noms inconnus ou rangés dans le mauvais slot (log + ignore)."""
    q = config.get("questionnaires")
    if not isinstance(q, dict):
        # Synthèse rétro-compatible depuis les clés historiques.
        q = {"begin": [], "post_trial": [], "post_bloc": [], "end": []}
        if config.get("questionnaire_post_trial"):
            q["post_trial"] = ["agency"]
        legacy_pb = []
        if config.get("questionnaire_post_bloc"):
            legacy_pb.append("AAT_L")
        if config.get("questionnaire_hoffman"):
            legacy_pb.append("hoffman")
        q["post_bloc"] = legacy_pb
        q["begin"] = ["QVG", "PTTA"]
        q["end"] = ["preference"]
    # Validation : ne garder que les noms connus et correctement rangés.
    clean = {}
    for slot in QUESTIONNAIRE_SLOTS:
        names = q.get(slot, []) or []
        valid = []
        for name in names:
            entry = resolve_questionnaire(name)
            if entry is None:
                logger.warning("[QUESTIONNAIRES] '%s' inconnu et sans template "
                               "static/templates/%s.html (slot '%s') : ignoré", name, name, slot)
                continue
            # "slot" du registre = emplacement unique (str) ou liste d'emplacements autorisés.
            allowed = entry["slot"]
            allowed = (allowed,) if isinstance(allowed, str) else tuple(allowed)
            if slot in allowed:
                valid.append(name)
            else:
                logger.warning("[QUESTIONNAIRES] '%s' non autorisé dans le slot '%s' (autorisés : %s) : ignoré",
                               name, slot, list(allowed))
        clean[slot] = valid
    config["questionnaires"] = clean
    return clean


# --- Helpers de séquencement ------------------------------------------------
def get_slot_list(user, slot):
    return (user.config.get("questionnaires", {}) or {}).get(slot, []) or []

def questionnaire_result_exists(user, name, slot):
    entry = resolve_questionnaire(name)
    cid = user.config.get("config_id")
    return os.path.exists(entry["path"](user.uid, user.step, user.trial, cid, slot, name))

def current_trial_played(user):
    """True si la trajectoire de l'essai courant (step, trial) a été sauvegardée.
    Sert de garde : on ne propose le questionnaire post-essai que pour un essai
    réellement joué, et on ne rejoue pas un essai déjà joué (cf. /planning)."""
    cid = user.config.get("config_id")
    trial_id = f"{user.uid}_{user.step}_{user.trial}"
    return os.path.exists(f"trajectories/{cid}/{user.uid}/{trial_id}.json")

def next_pending_questionnaire(user, slot):
    for name in get_slot_list(user, slot):
        if resolve_questionnaire(name) is not None and not questionnaire_result_exists(user, name, slot):
            return name
    return None

def advance_after_slot(user, slot):
    """Mute step/trial une fois le slot terminé et renvoie l'URL de la phase suivante.
    Reproduit les incréments historiques (post_qpt/post_qpb/post_hoffman/qex)."""
    if slot == "begin":
        return url_for('tutorial')
    if slot == "post_trial":
        bloc_key = user.config["bloc_order"][user.step]
        total_trial = len(user.config["blocs"][bloc_key])
        if user.trial < total_trial - 1:
            user.trial += 1
            db.session.commit()
            return url_for('planning')
        return url_for('questionnaire', slot='post_bloc')
    if slot == "post_bloc":
        user.trial = 0
        user.step += 1  # incrément historique (ex-post_hoffman)
        db.session.commit()
        if user.step < len(user.config["bloc_order"]):
            return url_for('planning')
        return url_for('questionnaire', slot='end')
    if slot == "end":
        user.step += 1
        db.session.commit()
        return url_for('goodbye')
    return url_for('index')


# --- Routes du séquenceur ---------------------------------------------------
@app.route('/questionnaire/<slot>', methods=['GET'])
def questionnaire(slot):
    """Rend le premier questionnaire non encore complété du slot.
    Si tous sont faits (ou via retour navigateur sur un déjà rempli), avance."""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    if slot not in QUESTIONNAIRE_SLOTS:
        return redirect(url_for('index'))
    # Garde : le questionnaire post-essai ne concerne qu'un essai réellement joué.
    # (empêche d'y répondre via Précédent alors que l'essai courant n'est pas joué)
    if slot == "post_trial" and not current_trial_played(current_user):
        return redirect(url_for('planning'))
    name = next_pending_questionnaire(current_user, slot)
    if name is None:
        return redirect(advance_after_slot(current_user, slot))
    entry = resolve_questionnaire(name)
    ctx = entry.get("context", _ctx_default)(current_user, slot)
    track_page_view(entry["template"], current_user.uid, current_user.config.get("config_id"))
    return render_template(
        entry["template"],
        dev_mode=current_user.config.get("dev", False),
        post_url=url_for('questionnaire_submit', slot=slot, name=name),
        **ctx
    )


@app.route('/questionnaire/<slot>/<name>', methods=['POST'])
def questionnaire_submit(slot, name):
    """Sauvegarde (idempotente) puis avance : questionnaire suivant du slot, ou phase suivante."""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    entry = resolve_questionnaire(name)
    if slot not in QUESTIONNAIRE_SLOTS or entry is None:
        return redirect(url_for('index'))
    # Garde : ne pas enregistrer un questionnaire post-essai pour un essai non joué
    # (cas d'une soumission via une page mise en cache par le navigateur).
    if slot == "post_trial" and not current_trial_played(current_user):
        return redirect(url_for('planning'))
    if not questionnaire_result_exists(current_user, name, slot):
        entry["save"](current_user, request.form, slot, name)
    if next_pending_questionnaire(current_user, slot) is not None:
        return redirect(url_for('questionnaire', slot=slot))
    return redirect(advance_after_slot(current_user, slot))


# -- Questionnaires de début (QVG, PTTA) : routes legacy redirigées vers le séquenceur.

@app.route('/experience_video_games_survey', methods=['GET'])
def qvg_survey():
    if not get_current_user():
        return redirect(url_for('index'))
    return redirect(url_for('questionnaire', slot='begin'))


@app.route('/ptta_survey', methods=['GET'])
def ptta_survey():
    if not get_current_user():
        return redirect(url_for('index'))
    return redirect(url_for('questionnaire', slot='begin'))


@app.route('/planning_design')
def planning_design():
    uid = "design" + str(gmtime())
    new_user = User(uid=uid, config={}, step=0, trial=0)
    db.session.add(new_user)
    db.session.commit()
    login_user_session(new_user)
    layouts_path = "overcooked_ai_py/data/layouts"
    layouts = [f[:-7] for f in os.listdir(layouts_path)
               if os.path.isfile(os.path.join(layouts_path, f))]
    layouts.sort()
    
    # Suivi temporel : enregistrer la visite de planning_design
    track_page_view('planning_design.html', uid, 'design')
    
    return render_template('planning_design.html', uid="design", agent_names=["Lazy", "Greedy", "Rational", "Random"], layouts=layouts)


@app.route('/goodbye')
def goodbye():
    """
    Route pour la page de fin avec lien de completion.
    Utilisée notamment lors du timeout des timers de page.
    """
    current_user = get_current_user()
    if current_user and current_user.config.get("completion_link"):
        # Suivi temporel : enregistrer la visite de la page goodbye
        track_page_view('goodbye.html', current_user.uid, current_user.config.get("config_id"))
        # Terminer la session de suivi
        end_user_session(current_user.uid)
        return render_template('goodbye.html', completion_link=current_user.config["completion_link"])
    else:
        # Fallback si pas d'utilisateur connecté ou pas de completion_link
        return render_template('goodbye.html', completion_link="")

@app.route('/cat')
def cat():
    return render_template('cat.html')  


@app.route('/tutorial')
def tutorial():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    uid = current_user.uid
    
    step = 0
    # Remise à zéro des compteurs d'essai et de bloc pour l'expérience principale
    current_user.trial = 0
    current_user.step = 0
    db.session.commit()
    psiturk = request.args.get('psiturk', False)
    
    # Récupérer la valeur du timer depuis la configuration utilisateur
    timer_max = current_user.config.get('timer_tuto_max', 600)  # 600s par défaut si absent
    
    if is_test != "test" :
        # Suivi temporel : enregistrer la visite du tutoriel
        track_page_view('tutorial.html', uid, current_user.config.get("config_id"))
        return render_template('tutorial.html', uid=uid, seq_id=step, config=TUTORIAL_CONFIG, timer_max=timer_max)
    else :
        # Suivi temporel : enregistrer la visite du tutoriel de test
        track_page_view('tutorialTest.html', uid, current_user.config.get("config_id"))
        return render_template('tutorialTest.html', uid=uid, seq_id=step, config=TUTORIAL_CONFIG, timer_max=timer_max)


@app.route('/condition_tutorial')
def condition_tutorial():
    """
    Route pour afficher le tutoriel spécifique à une condition expérimentale.
    Cette route est appelée avant chaque bloc pour présenter le tutoriel correspondant 
    à la condition (EA, U, EV) qui va être jouée.
    
    La logique :
    1. Récupère la condition du bloc courant en fonction de current_user.step
    2. Utilise le mapping condition_tutorials de la config pour trouver le bon template
    3. Affiche le tutoriel correspondant avec les bonnes variables
    """
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('index'))
    uid = current_user.uid
    bloc_order = current_user.config.get("bloc_order", [])
    
    # Vérifier qu'on n'est pas au-delà du nombre de blocs
    if current_user.step >= len(bloc_order):
        print(f"Utilisateur {uid} au step {current_user.step} >= nombre de blocs {len(bloc_order)}, redirection vers qex_ranking")
        return redirect(url_for('qex_ranking'))
    
    # Récupérer la condition du bloc courant
    # TO DO : Modifier pour ajouter les autres conditions si nécessaire
    try:
        bloc_key = current_user.config["bloc_order"][current_user.step]
        # Récupérer le label de condition depuis condition_labels (préservé depuis /index)
        condition_label = current_user.config.get("condition_labels", {}).get(bloc_key)
        
        # Si condition_labels n'existe pas, est vide, ou contient un dict, déduire depuis la configuration
        if not condition_label or isinstance(condition_label, dict):
            condition_config = current_user.config["conditions"][bloc_key]
            if isinstance(condition_config, dict):
                # Logique inverse : déterminer le label depuis la configuration
                # Vérifier d'abord EVH (nouvelle condition avec visual_bubbles)
                if (condition_config.get("visual_bubbles") == True and 
                    condition_config.get("recipe_head") == True):
                    condition_label = "EVH"
                elif (condition_config.get("recipe_hud") == False and 
                    condition_config.get("asset_hud") == False and
                    condition_config.get("asset_sound") == False and
                    condition_config.get("recipe_sound") == False and
                    condition_config.get("visual_bubbles") != True):
                    condition_label = "U"
                elif (condition_config.get("recipe_hud") == True and 
                      condition_config.get("asset_hud") == True and
                      condition_config.get("asset_sound") == False):
                    condition_label = "EV"
                elif (condition_config.get("asset_sound") == True and 
                      condition_config.get("recipe_sound") == True):
                    condition_label = "EA"
                else:
                    condition_label = None
                    print(f"ERREUR: Configuration inconnue pour bloc {bloc_key}: {condition_config}")
            else:
                condition_label = condition_config
        
        print(f"DEBUG CONDITION_TUTORIAL - bloc_key={bloc_key}, condition_label={condition_label} (type: {type(condition_label)})")
        
        # Vérifier que c'est une chaîne
        if not isinstance(condition_label, str):
            print(f"Condition label n'est pas une chaîne: {condition_label} (type: {type(condition_label)})")
            return redirect(url_for('planning'))
            
    except (KeyError, IndexError) as e:
        print(f"Erreur récupération condition pour utilisateur {uid} step {current_user.step}: {e}")
        return redirect(url_for('planning'))
    
    # Récupérer le template de tutoriel correspondant à cette condition
    condition_tutorials = current_user.config.get("condition_tutorials", {})
    tutorial_template = condition_tutorials.get(condition_label)
    
    # Si pas de tutoriel spécifique trouvé, rediriger vers planning
    if not tutorial_template:
        print(f"Aucun tutoriel trouvé pour la condition {condition_label}, redirection vers planning")
        return redirect(url_for('planning'))
    
    # Vérifier que le template existe
    template_path = f"static/templates/{tutorial_template}"
    if not os.path.exists(template_path):
        print(f"Template {template_path} introuvable, redirection vers planning")
        return redirect(url_for('planning'))
    
    print(f"Affichage du tutoriel {tutorial_template} pour la condition {condition_label} (bloc {bloc_key}, step {current_user.step})")
    
    # Suivi temporel : enregistrer la visite du tutoriel de condition
    track_page_view(tutorial_template, uid, current_user.config.get("config_id"))
    
    # Retourner le template correspondant avec les variables nécessaires
    return render_template(
        tutorial_template, 
        uid=uid, 
        condition=condition_label,
        bloc_id=bloc_key,
        step=current_user.step,
        timer_max=current_user.config.get('explications_block_max', 600),
        timer_min=current_user.config.get('explications_block_min', 60)
    )


@app.route('/debug')
def debug():
    resp = {}
    games = []
    active_games = []
    #waiting_games = []
    users = []
    # free_ids = []
    # free_map = {}
    for game_id in ACTIVE_GAMES:
        game = get_game(game_id)
        active_games.append({"id": game_id, "state": game.to_json()})

    # for game_id in list(WAITING_GAMES.queue):
    #     game = get_game(game_id)
    #     game_state = None if FREE_MAP[game_id] else game.to_json()
    #     waiting_games.append({"id": game_id, "state": game_state})

    for game_id in GAMES:
        games.append(game_id)

    for user_id in USER_ROOMS:
        users.append({user_id: get_curr_room(user_id)})

    # for game_id in list(FREE_IDS.queue):
    #     free_ids.append(game_id)

    # for game_id in FREE_MAP:
    #     free_map[game_id] = FREE_MAP[game_id]

    resp['active_games'] = active_games
    #resp['waiting_games'] = waiting_games
    resp['all_games'] = games
    resp['users'] = users
    # resp['free_ids'] = free_ids
    # resp['free_map'] = free_map
    return jsonify(resp)


#########################
# Socket Event Handlers #
#########################

# Asynchronous handling of client-side socket events. Note that the socket persists even after the
# event has been handled. This allows for more rapid data communication, as a handshake only has to
# happen once at the beginning. Thus, socket events are used for all game updates, where more rapid
# communication is needed

@socketio.on('create') # déplenché suite à une requette du fichier planning.js
def on_create(data):
    current_user = get_current_user()
    user_id = current_user.uid
    
    
    #print(data)
    curr_game = get_curr_game(user_id) # Vérifie si un jeu existe déjà pour cet UID
    if curr_game:
        # Cannot create if currently in a game
        return
    is_planning_design = bool(data.get("planning_design", None))
    if is_planning_design:
        #data.pop("planning_design")
        current_user.config["mechanic"] = data["params"]["mechanic"]
        current_user.config["blocs"] = {"0": data['params']['layouts']}
        current_user.config["agent"] = data['params']["playerOne"] if data[
            'params']["playerOne"] != "human" else data['params']["playerZero"]
        current_user.config["gameTime"] = data['params']['gameTime']
        current_user.config["conditions"] = {
            "0": data['params']['condition']}
    params = data.get('params', {})
    game_name = data.get('game_name', 'overcooked')

    # Déclenche la création du jeu avec les données fournies.
    # single_trial : l'expérience joue UN essai par session (puis questionnaires
    # en pages HTML autonomes). L'outil planning_design garde la séquence complète.
    _create_game(
        user_id, game_name, {
            "id": current_user.uid,
            "player_uid": current_user.uid,
            "step": int(current_user.step),
            "curr_trial_in_game": int(current_user.trial) - 1,  # trial doit être 0 ici pour commencer au premier essai
            "single_trial": not is_planning_design,
            "is_first_trial_of_block": int(current_user.trial) == 0,
            "config": current_user.config
        }
    )


@socketio.on('join')
def on_join(data):
    current_user = get_current_user()
    user_id = current_user.uid
    
    
    with USERS[user_id]:
        create_if_not_found = data.get("create_if_not_found", True)

        # Retrieve current game if one exists
        curr_game = get_curr_game(user_id)
        if curr_game:
            # Cannot join if currently in a game
            return

        # Retrieve a currently open game if one exists
        #game = get_waiting_game()

        # No available game was found so create a game
        params = data.get('params', {})
        if user_id != current_user.uid:
            current_user.uid = user_id
            db.session.commit()
        params = data.get('params', {})
        game_name = data.get('game_name', 'overcooked')
        _create_game(user_id, game_name, {"player_uid": current_user.uid, "step": int(
        current_user.step), "curr_trial_in_game" : int(current_user.trial)-1, "single_trial": True,
        "is_first_trial_of_block": int(current_user.trial) == 0, "room" : current_user.uid,"config": current_user.config})
        return
            # # Game was found so join it
            # with game.lock:

            #     join_room(game.id)
            #     set_curr_room(user_id, game.id)
            #     game.add_player(user_id)

            #     # Game is ready to begin play
            #     game.activate()
            #     ACTIVE_GAMES.add(game.id)
            #     emit('start_game', {"start_info": game.to_json(
            #     ), "trial": current_user.trial, "step": current_user.step, "config": game.config}, to=current_user.uid)
            #     socketio.start_background_task(play_game, game)
            #     # else:
            #     #     # Still need to keep waiting for players
            #     #     WAITING_GAMES.put(game.id)
            #     #     emit('waiting', {"in_game": True}, current_user.uid)


@socketio.on('leave')
def on_leave(data):
    current_user = get_current_user()
    user_id = current_user.uid
    
    
    with USERS[user_id]:
        was_active = _leave_game(user_id)

        if was_active:
            emit('end_game', {"status": Game.Status.DONE, "data": {}}, to=current_user.uid)
        else:
            emit('end_lobby', to=current_user.uid)


@socketio.on('action')
def on_action(data):
    current_user = get_current_user()
    user_id = current_user.uid
    action = data['action']

    game = get_curr_game(user_id)
    if not game:
        return

    game.enqueue_action(user_id, action)


@socketio.on('player_intention')
def on_player_intention(data):
    """[COMM JOUEUR→IA] Reçoit une consigne d'intention cliquée par le joueur et la transmet
    à l'agent planificateur. data = {'section': 'distal'|'proximal', 'value': <recette|code|None>}."""
    current_user = get_current_user()
    user_id = current_user.uid

    game = get_curr_game(user_id)
    if not isinstance(game, PlanningGame):
        return

    game.set_player_intention(data.get('section'), data.get('value'))


@socketio.on('connect') # est déclenché à chaque fois qu'un client se connect au serveur via Socket.IO
def on_connect():       # utilise le user_id pour gérer ces connexions
    current_user = get_current_user()
    user_id = current_user.uid
    
    
    if user_id in USERS:
        return

    USERS[user_id] = Lock()


@socketio.on('start_button_clicked')
def on_start_button_clicked(data):
    """
    Capte l'événement du clic sur le bouton 'Start Game' ou la fin du countdown.
    Permet de mesurer précisément le début de la partie effective.
    
    Args:
        data: {'step': int, 'trial': int, 'triggered_by': 'click' or 'countdown'}
    """
    current_user = get_current_user()
    if not current_user:
        return
    
    uid = current_user.uid
    config_id = current_user.config.get("config_id")
    
    # Utiliser les valeurs actuelles du serveur (source de vérité)
    # au lieu des valeurs envoyées par le client qui peuvent être obsolètes
    step = current_user.step
    trial = current_user.trial
    trigger = data.get('triggered_by', 'click')  # 'click' ou 'countdown'
    
    # Créer un nom d'événement unique pour tracer ce moment précis
    event_name = f"[START_GAME] Bloc {step}, Essai {trial} ({trigger})"
    
    # Enregistrer cet événement dans le tracker
    track_page_view(event_name, uid, config_id)


@socketio.on('disconnect')
def on_disconnect():
    # Ensure game data is properly cleaned-up in case of unexpected disconnect.
    # NB : en SocketIO, 'disconnect' se déclenche aussi à chaque navigation de page ;
    # on ne termine donc PAS la session de suivi ici (cf. end_user_session, appelé à
    # /goodbye). On se contente de libérer proprement la partie en cours.
    current_user = get_current_user()
    if not current_user:
        return
    user_id = current_user.uid

    if user_id not in USERS:
        return
    logger.debug("[DISCONNECT] uid=%s", user_id)
    with USERS[user_id]:
        _leave_game(user_id)

    del USERS[user_id]

# NB : les anciens handlers socket de questionnaires (new_trial, post_qpt,
# post_qpb, post_hoffman) ont été supprimés. Les questionnaires post-essai et
# post-bloc sont désormais des pages HTML autonomes servies par le séquenceur
# /questionnaire/<slot> (sauvegarde via save_agency/save_aat_l/save_hoffman ;
# incréments step/trial via advance_after_slot).


# Exit handler for server
def on_exit():

    # Force-terminate all games on server termination
    for game_id in GAMES:
        socketio.emit('end_game', {"status": Game.Status.INACTIVE, "data": get_game(
            game_id).get_data()}, room=game_id)

def trial_save_routine(data):
    '''
    Sauvegarder les données relative à un essai dans un fichier json
    dont nom sous la forme id_bloc_essai
    '''
    if not isinstance(data, dict):
        logger.error("[TRIAL_SAVE] données non-dict (%s) reçues : impossible de sauvegarder", type(data).__name__)
        return

    uid = data.get("uid", "UNKNOWN")
    trial_id = data.get("trial_id", "UNKNOWN")
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    config_id = config.get("config_id")

    # Enrichissement best-effort : ne doit JAMAIS empêcher la sauvegarde de l'essai.
    data_copy = deepcopy(data)
    try:
        if isinstance(data_copy.get("config"), dict):
            cfg = data_copy["config"]
            # Supprimer les sections qpb et hoffman (volumineuses, non pertinentes ici)
            cfg.pop("qpb", None)
            cfg.pop("hoffman", None)
            # Ajouter les données de configuration de l'essai courant sous bloc_order
            if "bloc_order" in cfg and "step" in data_copy:
                step = data_copy["step"]
                bloc_order = cfg["bloc_order"]
                if isinstance(step, int) and step < len(bloc_order):
                    current_bloc_key = bloc_order[step]
                    config_for_trial = {
                        "current_bloc": current_bloc_key,
                        "current_step": step,
                        "total_blocs": len(bloc_order),
                    }
                    if current_bloc_key in cfg.get("conditions", {}):
                        config_for_trial["current_condition"] = cfg["conditions"][current_bloc_key]
                    if current_bloc_key in cfg.get("blocs", {}):
                        config_for_trial["current_bloc_trials"] = cfg["blocs"][current_bloc_key]
                    # [CUTTING BOARD] Tracer les paramètres de découpe pour l'analyse
                    config_for_trial["cutting_enabled"] = cfg.get("cutting_enabled", False)
                    config_for_trial["chop_time"] = cfg.get("chop_time", None)
                    config_for_trial["recipes_requiring_chopping"] = cfg.get("recipes_requiring_chopping", [])
                    cfg["trial_config_data"] = config_for_trial
    except Exception:
        logger.exception("[TRIAL_SAVE] enrichissement config échoué (uid=%s trial_id=%s) ; sauvegarde des données brutes",
                         uid, trial_id)

    # 1) Chemin normal trajectories/{config_id}/{uid}/{trial_id}.json
    saved = False
    if config_id and uid and uid != "UNKNOWN":
        file_path = "trajectories/%s/%s/%s.json" % (config_id, uid, trial_id)
        if os.path.exists(file_path):
            # Déjà sauvegardé : idempotent, l'essai n'est pas perdu.
            return
        saved = safe_json_write(file_path, data_copy, uid)
        if not saved:
            logger.error("[TRIAL_SAVE] échec d'écriture du chemin normal %s ; bascule sur la sauvegarde de secours",
                         file_path)

    # 2) Sauvegarde de SECOURS : on ne perd JAMAIS les données d'un essai.
    #    Utilisée si config_id/uid manquent ou si l'écriture normale a échoué.
    if not saved:
        ts = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        backup_path = "trajectories/_backup/%s/%s_%s.json" % (uid, trial_id, ts)
        if safe_json_write(backup_path, data_copy, uid):
            logger.warning("[TRIAL_SAVE_BACKUP] essai sauvegardé en secours: %s (config_id=%r, uid=%r) — à investiguer",
                           backup_path, config_id, uid)
        else:
            logger.critical("[TRIAL_SAVE_LOST] ÉCHEC TOTAL de sauvegarde de l'essai uid=%s trial_id=%s", uid, trial_id)

#############
# Game Loop #
#############

# Déclenche nottement l'évènement state_pong écouté par planning.js 
# qui permet de mettre à jour les informations de la partie
def play_game(game, fps=15):
    status = Game.Status.ACTIVE
    
    print(f"[PLAY_GAME] Starting game loop for game {game.id} with FPS {fps}")
    
    while status != Game.Status.DONE and status != Game.Status.INACTIVE:
        with game.lock:
            status = game.tick()
        if status == Game.Status.RESET:
            # Reset intra-session : seul l'outil planning_design / les tutoriels
            # multi-layouts y passent. En mode single_trial (expérience), ce cas
            # ne se produit jamais (la session ne joue qu'un essai puis -> DONE).
            with game.lock:
                data = game.data
            if not isinstance(data, dict):
                data = {}
            trial_save_routine(data)
            socketio.emit('reset_game', {
                "state": game.to_json(),
                "timeout": game.reset_timeout,
                "trial": game.curr_trial_in_game,
                "step": getattr(game, "step", 0),
                "condition": getattr(game, "curr_condition", None),
                "config": game.config
            }, room=game.id)
            socketio.sleep(game.reset_timeout / 1000)
        else:
            socketio.emit('state_pong', {"state": game.get_state()}, room=game.id)
        socketio.sleep(1 / fps)
    with game.lock:

        if status != Game.Status.INACTIVE:
            game.deactivate()
        data = game.data
        if not isinstance(data, dict):
            data = {}
        trial_save_routine(data)
        if status == Game.Status.DONE:
            # Fin de l'essai courant. En mode single_trial (expérience), le client
            # navigue vers le séquenceur de questionnaires post-essai (pages HTML
            # autonomes). Tutoriel / planning_design : pas de navigation (next=None).
            next_url = "/questionnaire/post_trial" if getattr(game, "single_trial", False) else None
            socketio.emit('end_game', {
                "status": status,
                "data": data,
                "next": next_url,
                "score": data.get("score", 0),
            }, room=game.id)

    print(f"[PLAY_GAME] Game loop ended for game {game.id+1} with status {status}")
    cleanup_game(game)


if __name__ == '__main__':
    # Dynamically parse host and port from environment variables (set by docker build)
    # host = os.getenv('HOST', 'localhost')
    # port = int(os.getenv('PORT', 8080))
    # Attach exit handler to ensure graceful shutdown
    atexit.register(on_exit)
    if os.getenv('FLASK_ENV', 'production') == 'production':
        debug_env=False
    else:
        debug_env=True

    # https://localhost:80 is external facing address regardless of build environment
    socketio.run(app, host='0.0.0.0', port='5000', debug=debug_env)