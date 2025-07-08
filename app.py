import os
from pathlib import Path
from socket import socket

# Import and patch the production eventlet server if necessary

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
from utils import ThreadSafeSet, ThreadSafeDict, questionnaire_to_surveyjs
from flask import Flask, redirect, render_template, jsonify, request, session, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_session import Session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
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

random.seed(114101072025)

#######################
# Flask Configuration #
#######################
# Create and configure flask app
app = Flask(__name__, template_folder=os.path.join('static', 'templates'))
app.config['DEBUG'] = os.getenv('FLASK_ENV', 'production') == 'development'
app.config['SECRET_KEY'] = 'c-\x9f^\x80\xd8\xd0j\xed\xc1\x15\xf7\xc9\x97J{\x97\x165Iq#\x87\x88'
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#app.config.update(SECRET_KEY='osd(99092=36&462134kjKDhuIS_d23', ENV='development')
socketio = SocketIO(app, cors_allowed_origins="*", logger=app.config['DEBUG'], ping_interval=5, ping_timeout=5)
login_manager = LoginManager()
login_manager.init_app(app)
db = SQLAlchemy()
db.init_app(app)
# Attach handler for logging errors to file
handler = logging.FileHandler(LOGFILE)
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)


class User(UserMixin, db.Model):

    __tablename__ = 'user'
    uid = db.Column(db.String, primary_key=True)
    config = db.Column(JSON)
    step = db.Column(db.Integer) # Le bloc en cours
    trial = db.Column(db.Integer) # L'essaie en cours (correspondant au layout)

    def get_id(self):
        return str(self.uid)


with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

#################
# MODIFICATIONS #	
#################

is_test = CONFIG.get('mode')
#is_test = "pas_test"
print("ceci est un : ",is_test)

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
    del USER_ROOMS[user_id]


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
    - id \in FREE_IDS => FREE_MAP[id]
    - id \in ACTIVE_GAMES => Game in active state
    - id \in WAITING_GAMES => Game in inactive state
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
            

    except KeyError:
        return render_template('UID_error.html')

    if uid:
        session["type"] = "PROLIFIC"
    else:
        uid = request.args.get('TEST_UID', default=None)
        #uid = int(time.time())
        session["type"] = "TEST"
    if uid:
        user = User.query.filter_by(uid=uid).first()
        #user = False
        if user:
            login_user(user)
        else:
            new_user = User(uid=uid, config=config, step=0, trial=0)
            # gère la randomisation des blocs
            if new_user.config.get("shuffle_blocs", False):
                bloc_keys = list(new_user.config["blocs"].keys())
                random.shuffle(bloc_keys)
                print ("ordre des essais :" , bloc_keys)
                new_user.config["bloc_order"] = bloc_keys
                bloc_key = new_user.config["bloc_order"][new_user.step]
                print("premier bloc :", bloc_key)
                print ("liste des essais : ",new_user.config["blocs"][bloc_key] )
            else:
                new_user.config["bloc_order"] = list(new_user.config["blocs"].keys())
            if new_user.config.get("shuffle_trials", False) == True: # gère la randomisation des essais
                for key, value in new_user.config["blocs"].items():
                    random.shuffle(value)
            # Chargement des questionnaires post trial et post bloc
            ## -- qpt
            try:
                if os.path.exists("./questionnaires/post_trial/" + new_user.config["questionnaire_post_trial"]):
                    with open("./questionnaires/post_trial/" + new_user.config["questionnaire_post_trial"], 'r', encoding='utf-8') as f:
                        qpt = json.load(f)
                    f.close()
                    new_user.config["qpt"] = qpt
            except KeyError:
                new_user.config["qpt"] = {}
            
            ## -- qpb
            try:
                if os.path.exists("./questionnaires/post_bloc/" + new_user.config["questionnaire_post_bloc"]):
                    with open("./questionnaires/post_bloc/" + new_user.config["questionnaire_post_bloc"], 'r', encoding='utf-8') as f:
                        qpb = json.load(f)
                    f.close()
                    new_user.config["qpb"] = qpb
            except KeyError:
                new_user.config["qpb"] = {}
            ## -- hoffman
            try:
                if os.path.exists("./questionnaires/hoffman/" + new_user.config["questionnaire_hoffman"]):
                    with open("./questionnaires/hoffman/" + new_user.config["questionnaire_hoffman"], 'r', encoding='utf-8') as f:
                        hoffman = json.load(f)
                    f.close()
                    new_user.config["hoffman"] = hoffman
                    #print("hada",hoffman)
            except KeyError:
                new_user.config["hoffman"] = {}
                #print("erhada",hoffman)


            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
        return render_template('index.html', uid=uid, layout_conf=LAYOUT_GLOBALS) #--- uncomment
        #return redirect(url_for('planning'))
    else:
        return render_template('UID_error.html')


@app.route('/instructions', methods=['GET', 'POST'])
@login_required
def instructions():
    uid = current_user.uid
    condition = current_user.config["conditions"]
    is_explained = False

    all_conditions = [item for sublist in [list(bloc.values()) for bloc in condition.values()] for item in sublist] #test wheter at least 1 intention is given at some point
    if any(all_conditions):
        is_explained = True
    mechanic_type =  current_user.config["mechanic"]
    isAgency =  current_user.config.get("agency", False)
    form = request.form.to_dict()
    form["timestamp"] = gmtime()
    form["date"] = asctime(form["timestamp"])
    form["useragent"] = request.headers.get('User-Agent')
    #form["IPadress"] = request.remote_addr
    #
    if form["consentRadio"] == "accept":
        Path("trajectories/" + current_user.config["config_id"] + "/"+ uid).mkdir(parents=True, exist_ok=True)
        try:
            with open('trajectories/' + current_user.config["config_id"] + "/" +uid + '/CONSENT.json', 'w', encoding='utf-8') as f:
                json.dump(form, f, ensure_ascii=False, indent=4)
                f.close()
        except KeyError:
            pass
        if condition:
            if mechanic_type == "recipe":
                if isAgency:
                    return render_template('instructions_recipe_Agency.html', is_explained=is_explained)
                else :
                    return render_template('instructions_recipe.html', is_explained=is_explained)
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


@app.route('/instructions_explained')
def instructions_explained():
    uid = request.args.get('UID')
    #agent_names = get_agent_names()
    return render_template('instructions_explained.html', uid=uid, layout_conf=LAYOUT_GLOBALS)


@app.route('/planning', methods=['GET', 'POST'])
@login_required
def planning():
    uid = current_user.uid
    bloc_order = current_user.config["bloc_order"]
    if current_user.step >= len(bloc_order):
        return redirect(url_for('qex_ranking'))
    try:
        bloc_key = current_user.config["bloc_order"][current_user.step]
        condition = current_user.config["conditions"][bloc_key]
        print ("CONDITION random bloc : ", condition)
    except KeyError:
        condition = request.args.get('CONDITION')
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

    # --- MODIFICATION ICI ---
    # On ne retourne JAMAIS qex_ranking ici, même si on est au dernier bloc.
    # Le JS s'occupe de rediriger après le dernier questionnaire.
    return render_template(
        "planning.html",
        qpb=json.dumps(qpb),
        qpt=qpt if qpt else "",
        hoffman=json.dumps(hoffman)
    )
@app.route('/transition', methods=['GET', 'POST'])
def transition():
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
@login_required
def qex_ranking():
    uid = current_user.uid
    step = current_user.step
    config_id = current_user.config["config_id"]
    file_name = f"trajectories/{config_id}/{uid}/Post_experiment/{uid}_{step}_preference.json"
    if os.path.exists(file_name):
        return render_template('goodbye.html', completion_link=current_user.config["completion_link"])
    return render_template('preference order_en.html')

@app.route('/submit_qex_ranking', methods=['POST'])
@login_required
def submit_qex_ranking():

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

    if not ranking_json_string:
        print("Error: No 'ranking_data' received for QEX submission.")
        
        return redirect(url_for('planning')) # Or a specific error page

    try:
        # Parse the JSON string back into a Python list
        ranking_list = json.loads(ranking_json_string)
        form_data["ranking_response"] = ranking_list # Store the QEX ranking here

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
@login_required
def qvg_survey():
    """
    Renders the video game questionnaire (QVG) HTML page.
    """
    # Récupère la durée du timer depuis la config utilisateur
    qvg_length = current_user.config.get("qvg_length", 60)  # 60s par défaut si absent
    return render_template('experience_video_games_en.html', qvg_length=qvg_length)

@app.route('/submit_qvg_survey', methods=['POST'])
@login_required
def submit_qvg_survey():
    """
    Handles the POST submission of the video game questionnaire (QVG).
    Extracts data, saves it to a JSON file, and progresses the user's step.
    """
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
@login_required
def ptta_survey():
    ptta_length = current_user.config.get("ptta_length", 60)
    return render_template('PTT_A_en.html',ptta_length=ptta_length)

@app.route('/submit_ptta_survey', methods=['POST'])
@login_required
def submit_ptta_survey():
    """
    Handles the POST submission of the PTT-A survey.
    Extracts data, saves it to a JSON file, and progresses the user's step.
    """
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
    login_user(new_user)
    layouts_path = "overcooked_ai_py/data/layouts"
    layouts = [f[:-7] for f in os.listdir(layouts_path)
               if os.path.isfile(os.path.join(layouts_path, f))]
    layouts.sort()
    return render_template('planning_design.html', uid="design", agent_names=["Lazy", "Greedy", "Rational", "Random"], layouts=layouts)


@app.route('/cat')
def cat():
    return render_template('cat.html')  


@app.route('/tutorial')
@login_required
def tutorial():
    uid = current_user.uid
    step = 0
    # Remise à zéro des compteurs d'essai et de bloc pour l'expérience principale
    current_user.trial = 0
    current_user.step = 0
    db.session.commit()
    psiturk = request.args.get('psiturk', False)
    if is_test != "test" :
        return render_template('tutorial.html', uid=uid, seq_id=step, config=TUTORIAL_CONFIG)
    else :
        return render_template('tutorialTest.html', uid=uid, seq_id=step, config=TUTORIAL_CONFIG)


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
    user_id = current_user.uid
    with USERS[user_id]:
        was_active = _leave_game(user_id)

        if was_active:
            emit('end_game', {"status": Game.Status.DONE, "data": {}}, to=current_user.uid)
        else:
            emit('end_lobby', to=current_user.uid)


@socketio.on('action')
def on_action(data):
    user_id = current_user.uid
    action = data['action']

    game = get_curr_game(user_id)
    if not game:
        return

    game.enqueue_action(user_id, action)


@socketio.on('connect') # est déclenché à chaque fois qu'un client se connect au serveur via Socket.IO
def on_connect():       # utilise le user_id pour gérer ces connexions
    user_id = current_user.uid
    if user_id in USERS:
        return

    USERS[user_id] = Lock()



@socketio.on('disconnect')
def on_disconnect():
    # Ensure game data is properly cleaned-up in case of unexpected disconnect
    user_id = current_user.uid
    if user_id not in USERS:
        return
    with USERS[user_id]:
        _leave_game(user_id)

    del USERS[user_id]

@socketio.on("new_trial")
def on_new_trial():
    user_id = current_user.uid
    game = get_curr_game(user_id)
    if not game:
        return
    current_user.trial = game.curr_trial_in_game
    db.session.commit()
    

@socketio.on("post_qpt")
def post_qpt(data):
    sid = request.sid
    uid = current_user.uid
    bloc_key = current_user.config["bloc_order"][current_user.step]
    trial = current_user.trial

    form = {}
    mapping = {"q1": "control_used", "q2": "control_felt", "q3": "accountability"}
    form["answer"] = {mapping.get(k, k): v for k, v in data["survey_data"].items()}
    for key, value in data["survey_data"].items():
        form["answer"][key] = value
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
        with open('trajectories/'+ data["config"].get("config_id") + "/" + data["uid"] + "/" + data['trial_id']+'.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
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
