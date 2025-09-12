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
import logging
import glob
from time import gmtime, asctime, sleep, time
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

# Where errors will be logged
LOGFILE = CONFIG['logfile']

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
socketio = SocketIO(app, cors_allowed_origins="*", logger=app.config['DEBUG'], ping_interval=5, ping_timeout=5)
# Système d'authentification désactivé - utilisation de sessions simples
# login_manager = LoginManager()
# login_manager.init_app(app)
db = SQLAlchemy()
db.init_app(app)
# Attach handler for logging errors to file
handler = logging.FileHandler(LOGFILE)
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)


class User(db.Model):

    __tablename__ = 'user'
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
# Global Coordination Functions #
#################################

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
        config = CONFIG[config_id]
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
            "recipe_hud" : True,
            "asset_hud" : True,
            "motion_goal" : False,
            "asset_sound" : True,
            "recipe_sound" : True
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
            "visual_intention_next_duration": config.get("visual_intention_next_duration", 1000)
            }

    except KeyError:
        return render_template('UID_error.html')

    if uid:
        session["type"] = "PROLIFIC"
    else:
        uid = request.args.get('TEST_UID', default=None)
        session["type"] = "TEST"
    if uid:
        user = User.query.filter_by(uid=uid).first()
        if user:
            login_user_session(user)
        else:
            new_user = User(uid=uid, config=config, step=0, trial=0)
            
            # Gestion des questionnaires post-trial (depuis old_app.py)
            try:
                if os.path.exists("./questionnaires/post_trial/" + new_user.config["questionnaire_post_trial"]):
                    with open("./questionnaires/post_trial/" + new_user.config["questionnaire_post_trial"], 'r', encoding='utf-8') as f:
                        qpt = json.load(f)
                    f.close()
                    new_user.config["qpt"] = qpt
            except KeyError:
                new_user.config["qpt"] = {}
                
            # Gestion des questionnaires post-bloc (depuis old_app.py)
            try:
                if os.path.exists("./questionnaires/post_bloc/" + new_user.config["questionnaire_post_bloc"]):
                    with open("./questionnaires/post_bloc/" + new_user.config["questionnaire_post_bloc"], 'r', encoding='utf-8') as f:
                        qpb = json.load(f)
                    f.close()
                    new_user.config["qpb"] = qpb
            except KeyError:
                new_user.config["qpb"] = {}
                
            # Gestion questionnaire hoffman
            try:
                if os.path.exists("./questionnaires/hoffman/" + new_user.config["questionnaire_hoffman"]):
                    with open("./questionnaires/hoffman/" + new_user.config["questionnaire_hoffman"], 'r', encoding='utf-8') as f:
                        hoffman = json.load(f)
                    f.close()
                    new_user.config["hoffman"] = hoffman
            except KeyError:
                new_user.config["hoffman"] = {}
            
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
                accountability_labels = ["Entièrement dû à moi", "Entièrement dû à l'IA"]
                new_user.config["accountability_label_order"] = accountability_labels
                print(f"📋 RANDOMIZE_ACCOUNTABILITY_LABELS=FALSE - Ordre standard: {accountability_labels}")
            
            db.session.add(new_user)
            db.session.commit()
            login_user_session(new_user)
        return render_template('index.html', uid=uid, layout_conf=LAYOUT_GLOBALS)
    else:
        return render_template('UID_error.html')


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
            try:
                with open('trajectories/' + config_id + "/" +uid + '/CONSENT.json', 'w', encoding='utf-8') as f:
                    json.dump(form, f, ensure_ascii=False, indent=4)
                    f.close()
            except KeyError:
                pass
            if condition:
                if mechanic_type == "recipe":
                    # Récupérer les valeurs depuis la config ou les defaults
                    onion_time = config.get("onion_time", LAYOUT_GLOBALS.get("onion_time", 15))
                    tomato_time = config.get("tomato_time", LAYOUT_GLOBALS.get("tomato_time", 7))
                    onion_value = config.get("onion_value", LAYOUT_GLOBALS.get("onion_value", 21))
                    tomato_value = config.get("tomato_value", LAYOUT_GLOBALS.get("tomato_value", 13))
                    

                    return render_template('instructions_recipe.html', 
                                            is_explained=is_explained,
                                            onion_time=onion_time,
                                            tomato_time=tomato_time,
                                            onion_value=onion_value,
                                            tomato_value=tomato_value,
                                            config=config,
                                            timer_max=config.get('explications_generales_max', 600),
                                            timer_min=config.get('explications_generales_min', 120))
                #return redirect(url_for('qvg_survey'))

            else:
                return render_template('condition_error.html')

        else:
            Path("trajectories/" + uid).mkdir(parents=True, exist_ok=True)
            try:
                with open('trajectories/' + uid + '/NOT_CONSENT.json', 'w', encoding='utf-8') as f:
                    json.dump(form, f, ensure_ascii=False, indent=4)
                    f.close()
            except KeyError:
                pass
            return render_template('leave.html', uid=uid, complete=False)
    
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
                          order_bonus=config.get("order_bonus", LAYOUT_GLOBALS.get("order_bonus", 2)))


@app.route('/instructions_explained')
def instructions_explained():
    uid = request.args.get('UID')
    #agent_names = get_agent_names()
    return render_template('instructions_explained.html', uid=uid, layout_conf=LAYOUT_GLOBALS)


@app.route('/planning', methods=['GET', 'POST'])
def planning():
    current_user = get_current_user()
    uid = current_user.uid
    bloc_order = current_user.config.get("bloc_order", [])
    
    if current_user.step >= len(bloc_order):
        print(f"Utilisateur {uid} terminé tous les blocs (step {current_user.step}), redirection vers qex_ranking")
        return redirect(url_for('qex_ranking'))
    
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

    post_trial = current_user.config.get("questionnaire_post_trial", "")
    if post_trial.endswith(".html"):
        qpt = ""
    else:
        qpt = questionnaire_to_surveyjs(
            current_user.config["qpt"],
            current_user.config["bloc_order"][current_user.step],
            current_user.config.get("pagify_qpt", False)
        )

    qpb_elements = []
    for key, value in current_user.config["qpb"].items():
        if isinstance(value, dict):
            qpb_elements.append(value)
    qpb = {"elements": qpb_elements}

    hoffman_elements = []
    for key, value in current_user.config["hoffman"].items():
        if isinstance(value, dict):
            # Correction : inclure aussi l'avant-dernier bloc (step 5 pour un total de 7 blocs)
            steps = value.get("steps", [])
            total_blocs = len(current_user.config["bloc_order"])
            # Afficher Hoffman si on est dans les steps OU si on est à l'avant-dernier bloc
            #if current_user.step in steps or (current_user.step == total_blocs - 2 and (total_blocs - 2) not in steps):
            hoffman_elements.append(value)
    hoffman = {"elements": hoffman_elements}

    # --- RENDU TEMPLATE ---
    # On ne retourne JAMAIS qex_ranking ici, même si on est au dernier bloc.
    # Le JS s'occupe de rediriger après le dernier questionnaire.
    
    # Préparer les variables qui étaient dans current_user
    total_blocs = len(current_user.config["bloc_order"])
    bloc_key = current_user.config["bloc_order"][current_user.step]
    current_condition = current_user.config["conditions"][bloc_key]
    current_trials = current_user.config["blocs"][bloc_key]
    
    return render_template(
        "planning.html",
        qpb=json.dumps(qpb),
        qpt=qpt if qpt else "",
        hoffman=json.dumps(hoffman),
        uid=current_user.uid,
        step=current_user.step,
        condition=current_condition,
        config=json.dumps(current_user.config),
        trials=json.dumps(current_trials),
        total_blocs=total_blocs,
        qpb_length=current_user.config.get("qpb_length", 300),
        hoffman_length=current_user.config.get("hoffman_length", 300),
        accountability_labels=current_user.config.get("accountability_label_order", ["Entièrement dû à moi", "Entièrement dû à l'IA"])
    )
@app.route('/transition', methods=['GET', 'POST'])
def transition():
    current_user = get_current_user()
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
    try:
        with open('trajectories/' + uid + "/" + uid + "_"  + str(step) + 'QPB.json', 'w', encoding='utf-8') as f:
            json.dump(form, f, ensure_ascii=False, indent=4)
            f.close()
    except KeyError:
        pass
    step += 1
    return render_template('goodbye.html', uid=uid, step=step, completion_link=current_user.config["completion_link"])
    # else :
    #   return render_template('bloc_transition.html', uid = uid, step = step)






@app.route('/qex_ranking', methods=['GET'])
def qex_ranking():
    current_user = get_current_user()
    uid = current_user.uid
    step = current_user.step
    config_id = current_user.config["config_id"]
    file_name = f"trajectories/{config_id}/{uid}/Post_experiment/{uid}_{step}_preference.json"
    if os.path.exists(file_name):
        return render_template('goodbye.html', completion_link=current_user.config["completion_link"])
    
    preference_length = current_user.config.get("preference_length", 60)
    num_blocs = len(current_user.config.get("bloc_order", []))
    return render_template('preference order_en.html', preference_length=preference_length, num_blocs=num_blocs)

@app.route('/submit_qex_ranking', methods=['POST'])
def submit_qex_ranking():
    current_user = get_current_user()
    uid = current_user.uid
    step = current_user.step 
    config_id = current_user.config["config_id"]
    file_name = f"trajectories/{config_id}/{uid}/Post_experiment/{uid}_{step}_preference.json"
    if os.path.exists(file_name):
        return render_template('goodbye.html', completion_link=current_user.config["completion_link"])

    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    try:
        bloc_key = current_user.config["bloc_order"][current_user.step]
        condition = current_user.config["conditions"][bloc_key]
    except (KeyError, IndexError):
        form_data["condition"] = "N/A" 

    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])

    # --- QEX specific data extraction ---
    ranking_json_string = request.form.get('ranking_data')
    timeout_bool = request.form.get('timeout_bool', 'false') == 'true'

    if not ranking_json_string:
        print("Error: No 'ranking_data' received for QEX submission.")
        
        return redirect(url_for('planning')) # Or a specific error page

    try:
        # Parse the JSON string back into a Python list
        ranking_list = json.loads(ranking_json_string)
        form_data["ranking_response"] = ranking_list # Store the QEX ranking here
        form_data["timeout_bool"] = timeout_bool # Store whether submission was by timeout

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON received for QEX 'ranking_data': {ranking_json_string}")
        return "Error: Invalid ranking data format for QEX", 400

    # --- Save the QEX data to a JSON file ---
    # saving preference scale in prolific ID folder
    config_id = current_user.config["config_id"]
    Path(f"trajectories/{config_id}/{uid}/Post_experiment").mkdir(parents=True, exist_ok=True)
    file_name = f"trajectories/{config_id}/{uid}/Post_experiment/{uid}_{step}_preference.json"
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(form_data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved QEX data for user {uid} at step {step} to {file_name}")
    except Exception as e: 
        print(f"Error saving QEX data for user {uid} at step {step}: {e}")
        
        return "Error saving QEX data", 500

    
    current_user.step += 1
    #current_user.save() # Make sure User model has a save method to persist changes?

    
    return render_template('goodbye.html', completion_link=current_user.config["completion_link"])
    

# --qvg


@app.route('/experience_video_games_survey', methods=['GET'])
def qvg_survey():
    """
    Renders the video game questionnaire (QVG) HTML page.
    """
    current_user = get_current_user()
    # Récupère la durée du timer depuis la config utilisateur
    qvg_length = current_user.config.get("qvg_length", 60)  # 60s par défaut si absent
    return render_template('experience_video_games_en.html', qvg_length=qvg_length)

@app.route('/submit_qvg_survey', methods=['POST'])
def submit_qvg_survey():
    """
    Handles the POST submission of the video game questionnaire (QVG).
    Extracts data, saves it to a JSON file, and progresses the user's step.
    """
    current_user = get_current_user()
    uid = current_user.uid
    step = current_user.step

    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    try:
        # Get condition if applicable for this step, similar to other forms
        bloc_key = current_user.config["bloc_order"][current_user.step]
        condition = current_user.config["conditions"][bloc_key]
    except (KeyError, IndexError):
        form_data["condition"] = "N/A" # Default if condition not found for step

    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])

    # --- QVG specific data extraction ---
    # Get the JSON string from the hidden input field
    qvg_json_string = request.form.get('qvg_data')

    if not qvg_json_string:
        print(f"Error: No 'qvg_data' received for QVG submission for user {uid} at step {step}.")
        # Decide how to handle this: render an error page, redirect, etc.
        # Redirect to planning if data is missing, similar to QEX
        return redirect(url_for('planning'))

    try:
        # Parse the JSON string back into a Python dictionary
        qvg_response_data = json.loads(qvg_json_string)
        form_data["qvg_response"] = qvg_response_data # Store the QVG responses here

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON received for QVG 'qvg_data': {qvg_json_string} for user {uid} at step {step}.")
        return "Error: Invalid QVG data format", 400

    # --- Save the QVG data to a JSON file ---
    # saving demographic and video game scale in prolific ID folder
    Path("trajectories/" + current_user.config["config_id"] + "/"+ uid + "/" + "Pre_experiment").mkdir(parents=True, exist_ok=True)
    file_name = 'trajectories/' + current_user.config["config_id"] + "/" + uid + "/" + "Pre_experiment" + "/" + uid + "_" + str(current_user.step) + '_QVG.json'
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(form_data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved QVG data for user {uid} at step {step} to {file_name}")
    except Exception as e:
        print(f"Error saving QVG data for user {uid} at step {step}: {e}")
        return "Error saving QVG data", 500

    
    # Determine the next page based on the new step value, similar to the /transition route
    
    return redirect(url_for('ptta_survey')) #TODO: put tuttorial ?




# -- ptta

@app.route('/ptta_survey', methods=['GET'])
def ptta_survey():
    current_user = get_current_user()
    ptta_length = current_user.config.get("ptta_length", 60)
    return render_template('PTT_A_en.html',ptta_length=ptta_length)

@app.route('/submit_ptta_survey', methods=['POST'])
def submit_ptta_survey():
    """
    Handles the POST submission of the PTT-A survey.
    Extracts data, saves it to a JSON file, and progresses the user's step.
    """
    current_user = get_current_user()
    uid = current_user.uid
    step = current_user.step

    form_data = {}
    form_data["step"] = step
    form_data["user_agent"] = request.headers.get('User-Agent')
    # Pour ajouter condition premier bloc au fichier resultat
    #    #try:
    #    bloc_key = current_user.config["bloc_order"][current_user.step]
    #    form_data["condition"] = current_user.config["conditions"][bloc_key]
    #except (KeyError, IndexError):
    #    form_data["condition"] = "N/A"

    form_data["uid"] = uid
    form_data["timestamp"] = gmtime()
    form_data["date"] = asctime(form_data["timestamp"])

    # --- PTT-A specific data extraction ---
    # Get the JSON string from the hidden input field named 'ptta_data'
    ptta_json_string = request.form.get('ptta_data')

    if not ptta_json_string:
        print(f"Error: No 'ptta_data' received for PTT-A submission for user {uid} at step {step}.")
        
        return redirect(url_for('planning')) # Or an error page

    try:
        # Parse the JSON string back into a Python dictionary
        ptta_response_data = json.loads(ptta_json_string)
        form_data["ptta_response"] = ptta_response_data # Store the PTT-A responses here

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON received for PTT-A 'ptta_data': {ptta_json_string} for user {uid} at step {step}.")
        return "Error: Invalid PTT-A data format", 400

    # --- Save the PTT-A data to a JSON file ---
    # path to save PTT-A scale in an prolific ID folder
    Path(f"trajectories/{current_user.config['config_id']}/{uid}/Pre_experiment").mkdir(parents=True, exist_ok=True)
    # Using a clear naming convention: _PTTA.json
    file_name = f"trajectories/{current_user.config['config_id']}/{uid}/Pre_experiment/{uid}_{current_user.step}_PTTA.json"
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(form_data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved PTT-A data for user {uid} at step {step} to {file_name}")
    except Exception as e:
        print(f"Error saving PTT-A data for user {uid} at step {step}: {e}")
        return "Error saving PTT-A data", 500


    return redirect(url_for('tutorial'))




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
    return render_template('planning_design.html', uid="design", agent_names=["Lazy", "Greedy", "Rational", "Random"], layouts=layouts)


@app.route('/goodbye')
def goodbye():
    """
    Route pour la page de fin avec lien de completion.
    Utilisée notamment lors du timeout des timers de page.
    """
    current_user = get_current_user()
    if current_user and current_user.config.get("completion_link"):
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
        return render_template('tutorial.html', uid=uid, seq_id=step, config=TUTORIAL_CONFIG, timer_max=timer_max)
    else :
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
    if data.get("planning_design", None):
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
    # Déclenche la création du jeu avec les données fournies
    _create_game(
        user_id, game_name, {
            "id": current_user.uid,
            "player_uid": current_user.uid,
            "step": int(current_user.step),
            "curr_trial_in_game": int(current_user.trial) - 1,  # trial doit être 0 ici pour commencer au premier essai
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
        current_user.step), "curr_trial_in_game" : int(current_user.trial)-1, "room" : current_user.uid,"config": current_user.config})
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


@socketio.on('connect') # est déclenché à chaque fois qu'un client se connect au serveur via Socket.IO
def on_connect():       # utilise le user_id pour gérer ces connexions
    current_user = get_current_user()
    user_id = current_user.uid
    if user_id in USERS:
        return

    USERS[user_id] = Lock()



@socketio.on('disconnect')
def on_disconnect():
    # Ensure game data is properly cleaned-up in case of unexpected disconnect
    current_user = get_current_user()
    user_id = current_user.uid
    if user_id not in USERS:
        return
    with USERS[user_id]:
        _leave_game(user_id)

    del USERS[user_id]

@socketio.on("new_trial")
def on_new_trial():
    current_user = get_current_user()
    user_id = current_user.uid
    game = get_curr_game(user_id)
    if not game:
        return
    current_user.trial = game.curr_trial_in_game
    db.session.commit()
    

@socketio.on("post_qpt")
def post_qpt(data):
    current_user = get_current_user()
    sid = request.sid
    uid = current_user.uid
    bloc_key = current_user.config["bloc_order"][current_user.step]
    trial = current_user.trial

    form = {}
    mapping = {"q1": "control_used", "q2": "control_felt", "q3": "accountability"}
    form["answer"] = {mapping.get(k, k): v for k, v in data["survey_data"].items()}
    
    condition = current_user.config["conditions"][bloc_key]
    form["timeout_bool"] = data["timeout_bool"]
    form["step"] = current_user.step
    form["trial"] = trial
    form["trial_id"] = f"{uid}_{bloc_key}_{trial}_QPT"
    form["layout"] = current_user.config["blocs"][bloc_key][trial]
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = condition
    form["uid"] = uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])

    Path(f"trajectories/{current_user.config['config_id']}/{uid}/QPT").mkdir(parents=True, exist_ok=True)
    file_name = f"trajectories/{current_user.config['config_id']}/{uid}/QPT/{uid}_{current_user.step}_{trial}_QPT.json"
    # Vérifie si le fichier existe déjà pour éviter un double enregistrement
    if not os.path.exists(file_name):
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(form, f, ensure_ascii=False, indent=4)
        except KeyError:
            pass

        total_trial = len(current_user.config["blocs"][bloc_key])
        if trial < total_trial-1:
            current_user.trial += 1
            db.session.commit()
            socketio.emit("next_step", to=sid)
    else:
        print(f"QPT déjà enregistré pour {file_name}, pas de double incrémentation.")


@socketio.on("post_qpb") # Semble gérer la transition entre les différents blocs et remettre à 0 l'essai en cours
def post_qpb(data):
    current_user = get_current_user()
    sid = request.sid
    uid = current_user.uid
    bloc_key = current_user.config["bloc_order"][current_user.step]
    form = {}
    form["answer"] = {value["name"] : None for key,value in current_user.config["qpb"].items() if current_user.step in value["steps"]}
    for key, value in data["survey_data"].items():
        form["answer"][key] = value
    form["step"] = current_user.step
    form["trial_id"] = f"{uid}_{bloc_key}_QPB"
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = current_user.config["conditions"][bloc_key]
    form["uid"] = current_user.uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])

    Path("trajectories/" + current_user.config["config_id"] +"/"+ uid + "/" + "QPB").mkdir(parents=True, exist_ok=True)
    try:
        with open('trajectories/' + current_user.config["config_id"] + "/" + uid + "/" + "QPB" + "/" + uid + "_" + str(current_user.step) + 'AAT_L.json', 'w', encoding='utf-8') as f:
            json.dump(form, f, ensure_ascii=False, indent=4)
            f.close()
    except KeyError:
        pass
    #current_user.step += 1 # Permet de passer au bloc suivant
    current_user.trial = 0 # Attribut la valeur 0 à l'essai actuel
    db.session.commit()
    #socketio.emit("next_step", to=sid)
    socketio.emit("hoffman", to=sid)

@socketio.on("post_hoffman")
def post_hoffman(data):
    current_user = get_current_user()
    sid = request.sid
    uid = current_user.uid
    bloc_key = current_user.config["bloc_order"][current_user.step]
    form = {}
    form["answer"] = {value["name"] : None for key,value in current_user.config["hoffman"].items() if current_user.step in value["steps"]}
    for key, value in data["survey_data"].items():
        form["answer"][key] = value
    form["step"] = current_user.step
    form["trial_id"] = f"{uid}_{bloc_key}_HOFFMAN"
    form["user_agent"] = request.headers.get('User-Agent')
    form["condition"] = current_user.config["conditions"][bloc_key]
    form["uid"] = current_user.uid
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])

    Path("trajectories/" + current_user.config["config_id"] +"/"+ uid + "/"+ "QPB").mkdir(parents=True, exist_ok=True)
    try:
        with open('trajectories/' + current_user.config["config_id"] + "/" + uid + "/" + "QPB" + "/" + uid + "_" + str(current_user.step) + 'HOFFMAN.json', 'w', encoding='utf-8') as f:
            json.dump(form, f, ensure_ascii=False, indent=4)
            f.close()
    except KeyError:
        pass
    if current_user.step <= 6 :
        current_user.step += 1 # Permet de passer au bloc suivant
        current_user.trial = 0 # Attribut la valeur 0 à l'essai actuel
    db.session.commit()
    socketio.emit("next_step", to=sid)


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
    try:
        Path("trajectories/" + data["config"].get("config_id")+ "/" + data["uid"]
                            ).mkdir(parents=True, exist_ok=True)
    except TypeError:
        return
    try:
        # Créer une copie des données pour modification
        data_copy = deepcopy(data)
        
        # Modifier la configuration pour :
        # 1. Afficher les données de configuration utilisées pour l'essai sous le "bloc_order"
        # 2. Supprimer les informations relatives au "qpb" et "hoffman"
        if "config" in data_copy:
            config = data_copy["config"]
            
            # Supprimer les sections qpb et hoffman
            if "qpb" in config:
                del config["qpb"]
            if "hoffman" in config:
                del config["hoffman"]
            
            # Ajouter les données de configuration pour l'essai actuel sous bloc_order
            if "bloc_order" in config and "step" in data_copy:
                step = data_copy["step"]
                bloc_order = config["bloc_order"]
                
                # Ajouter les informations de configuration pour l'essai actuel
                if step < len(bloc_order):
                    current_bloc_key = bloc_order[step]
                    
                    # Créer une structure pour afficher les données de configuration utilisées
                    config_for_trial = {
                        "current_bloc": current_bloc_key,
                        "current_step": step,
                        "total_blocs": len(bloc_order)
                    }
                    
                    # Ajouter la condition actuelle si elle existe
                    if "conditions" in config and current_bloc_key in config["conditions"]:
                        config_for_trial["current_condition"] = config["conditions"][current_bloc_key]
                    
                    # Ajouter les trials du bloc actuel si ils existent
                    if "blocs" in config and current_bloc_key in config["blocs"]:
                        config_for_trial["current_bloc_trials"] = config["blocs"][current_bloc_key]
                    
                    # Placer ces informations juste après bloc_order
                    config["trial_config_data"] = config_for_trial
        
        with open('trajectories/'+ data["config"].get("config_id") + "/" + data["uid"] + "/" + data['trial_id']+'.json', 'w', encoding='utf-8') as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=4)
        f.close()
    except KeyError:
        pass

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
            with game.lock:
                data = game.data
            try:
                trial_save_routine(data)
                # Affiche le questionnaire agency à chaque fin de trial SAUF pour le tutoriel
                if not isinstance(game, OvercookedTutorial):
                    socketio.call("qpt", {
                        "qpt_length": game.config.get("qpt_length", 30),
                        "trial": data.get("curr_trial_in_game", 0),
                        "show_time": game.config.get("show_trial_time", False),
                        "time_elapsed": data.get("time_elapsed", 0),
                        "score": data.get("score", 0),
                        "infinite_all_order": game.config.get("infinite_all_order", False)
                    }, room=game.id)
            except SocketIOTimeOutError:
                print("Player " + str(game.id) + " is not on")
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
        trial_save_routine(data)
        if status == Game.Status.DONE:
            try:
                # Affiche TOUJOURS le questionnaire agency à la fin du dernier essai SAUF pour le tutoriel
                if not isinstance(game, OvercookedTutorial):
                    socketio.call("qpt", {
                        "qpt_length": game.config.get("qpt_length", 30),
                        "trial": data.get("curr_trial_in_game", 0),
                        "show_time": game.config.get("show_trial_time", False),
                        "time_elapsed": data.get("time_elapsed", 0),
                        "score": data.get("score", 0),
                        "infinite_all_order": game.config.get("infinite_all_order", False)
                    }, room=game.id)
                    socketio.emit("qpb", room=game.id)
            except SocketIOTimeOutError:
                print("Player " + str(game.id) + " is not on")
                if not isinstance(game, OvercookedTutorial):
                    socketio.emit("qpb", room=game.id)
            socketio.emit('end_game', {"status": status, "data": data}, room=game.id)
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