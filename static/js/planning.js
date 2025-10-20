console.log("executing planning")
// Persistent network connection that will be used to transmit real-time data
var socket = io();

/* * * * * * * * * * * * * * * * 
 * Button click event handlers *
 * * * * * * * * * * * * * * * */

var experimentParams = {
    layouts : ["cramped_room", "counter_circuit"],
    gameTime : 10,
    playerZero : "DummyAI"
};

let step = 0;
var curr_trial = 0;
var condition = "U";

let startCountdownId = null;
let startCountdownRemaining = 0;
let startTriggered = false;



function getConfigParams() {
    let paramsText = $('#config').text();
    let params = {};
    if (paramsText) {
        try {
            params = JSON.parse(paramsText);
        } catch (error) {
            console.error('Unable to parse config params', error);
        }
    }
    return params;
}

function showStartOverlay(message) {
    if (message) {
        $('#start-instructions').text(message);
    }
    startTriggered = false;
    $('#start-game').prop('disabled', false);
    $('#start-overlay').show();
    // Countdown automatique supprimé - L'utilisateur doit cliquer manuellement
    // beginStartCountdown();
}

function hideStartOverlay() {
    clearStartCountdown();
    $('#start-overlay').hide();
}

function clearStartCountdown() {
    if (startCountdownId !== null) {
        clearInterval(startCountdownId);
        startCountdownId = null;
    }
    $('#start-countdown').hide();
}

function beginStartCountdown() {
    const $countdownContainer = $('#start-countdown');
    const $countdownValue = $('#countdown-value');
    if ($countdownContainer.length === 0 || $countdownValue.length === 0) {
        return;
    }

    clearStartCountdown();
    startCountdownRemaining = 5;
    $countdownValue.text(startCountdownRemaining);
    $countdownContainer.show();

    startCountdownId = setInterval(function () {
        startCountdownRemaining -= 1;

        if (startCountdownRemaining <= 0) {
            clearStartCountdown();
            triggerGameStart('auto');
        } else {
            $countdownValue.text(startCountdownRemaining);
        }
    }, 1000);
}

function triggerGameStart(source) {
    if (startTriggered) {
        return;
    }

    startTriggered = true;
    clearStartCountdown();

    const $startButton = $('#start-game');
    const $startInstructions = $('#start-instructions');

    $startButton.prop('disabled', true);
    if (source === 'auto') {
        $startInstructions.text('Launching automatically, please wait...');
    } else {
        $startInstructions.text('Preparing game, please wait...');
    }

    const params = getConfigParams();
    const uid = $('#uid').text();
    const blocValue = $('#bloc').text();
    const stepValue = $('#step').text();
    const conditionValue = $('#condition').text();

    if (uid) {
        params.player_uid = uid;
    }
    if (blocValue) {
        params.bloc = blocValue;
    }
    if (conditionValue) {
        params.condition = conditionValue;
        condition = conditionValue;
    }

    // Émettre l'événement de tracking pour le début de la partie
    socket.emit('start_button_clicked', {
        step: stepValue || '0',
        trial: blocValue || '0',
        triggered_by: source === 'auto' ? 'countdown' : 'click'
    });

    const data = {
        params: params,
        game_name: "planning",
        create_if_not_found: false
    };

    socket.emit("create", data);
    $('#waiting').show();
    $('#lobby').hide();
    hideStartOverlay();
}

$(function() { // le $ signifie que la fonction attend que le document html soit chargé
    const $startButton = $('#start-game');
    const $startInstructions = $('#start-instructions');

    $startButton.on('click', function (event) {
        event.preventDefault();
        triggerGameStart('manual');
    });
});

$(function() {
    $('#leave').click(function() {
        socket.emit('leave', {});
        $('#leave').attr("disabled", true);
    });
});

$(function() {
    $('#answer').click(function() {
        let uid = $('#uid').text();
        let step = $('#step').text();
        $('answer').attr("disable", true);
        window.location.href = "./question";
    });
});

$(function() {
    $('#start').click(function() {;
        $('start').attr("disable", true);
        $.ajax({
            type: "POST",
            url: "/planning", 
            data: {"achieved_step" : $('#step').text()},
            success: function(){
                location.reload();
            }
        })
    });
});


/* * * * * * * * * * * * * 
 * Socket event handlers *
 * * * * * * * * * * * * */

window.intervalID = -1;
window.spectating = true;

socket.on("connect", function () {
    $('#waiting').hide();
    $('#lobby').hide();
    $('#leave').hide();
    $('#leave').attr("disabled", true);
    const conditionValue = $('#condition').text();
    if (conditionValue) {
        condition = conditionValue;
    }
    showStartOverlay('Click the button below when you are ready to start the experiment.');
});

socket.on('waiting', function (data) {
    // Show game lobby
    $('#error-exit').hide();
    $('#waiting').hide();
    $('#game-over').hide();
    $('#instructions').hide();
    $('#tutorial').hide();
    $("#overcooked").empty();
    $('#lobby').show();
    $('#join').hide();
    $('#join').attr("disabled", true)
    $('#create').hide();
    $('#create').attr("disabled", true)
    $('#leave').show();
    $('#leave').attr("disabled", false);
    if (!data.in_game) {
        // Begin pinging to join if not currently in a game
        if (window.intervalID === -1) {
            window.intervalID = setInterval(function () {
                socket.emit('join', {});
            }, 1000);
        }
    }
});

socket.on('creation_failed', function(data) {
    // Tell user what went wrong
    let err = data['error']
    $("#overcooked").empty();
    $('#lobby').hide();
    $("#instructions").show();
    $('#tutorial').show();
    $('#waiting').hide();
    $('#start-instructions').text('Game creation failed, please try again.');
    showStartOverlay();
    console.log("creation")
    $('#overcooked').append(`<h4>Sorry, game creation code failed with error: ${JSON.stringify(err)}</>`);
});
// déclenché suite à une requette de app.py
socket.on('start_game', function(data) {
    // Hide game-over and lobby, show game title header
    if (window.intervalID !== -1) {
        clearInterval(window.intervalID);
        window.intervalID = -1;
    }
    graphics_config = {
        container_id : "overcooked",
        start_info : data.start_info,
        condition : data.config.conditions[data.config.bloc_order[data.step]],
        mechanic : data.config.mechanic,
        Game_Trial_Timer : data.config.Game_Trial_Timer,
        show_counter_drop : data.config.show_counter_drop,
    };
    window.spectating = data.spectating;
    $('#error-exit').hide();
    $("#overcooked").empty();
    $('#game-over').hide();
    $('#lobby').hide();
    $('#waiting').hide();
    $('#join').hide();
    $('#join').attr("disabled", true);
    $('#create').hide();
    $('#create').attr("disabled", true)
    $("#instructions").hide();
    $('#tutorial').hide();
    $('#leave').show();
    $('#leave').attr("disabled", false)
    hideStartOverlay();
    curr_trial = data.trial +1;

    let bloc_key = data.config.bloc_order[data.step];
    $('#game-title').text(`Experiment in Progress, Block ${data.step + 1}/${Object.keys(data.config.blocs).length}, Trial ${curr_trial}/${Object.keys(data.config.blocs[bloc_key]).length}`);
    $('#game-title').show(); 
    
    if (!window.spectating) {
        enable_key_listener();
    }
    graphics_start(graphics_config);
});


// Lorsque le serveur émet l'évènement reset_game (via play_game dans app.py)
// alors le jeu met à jour son affichage graphique pour passer à l'essai suivant
socket.on('reset_game', function(data) {   
    //console.log(`[RESET_GAME] Received reset_game event for trial ${data.trial + 1} in block ${data.step + 1}`);
    //console.log(`[RESET_GAME] State:`, data.state);
    step = $('#step')
    //graphics_end();
    //game_config.scene.endLevel(); // Il semble que endlevel n'existe pas ce qui engendre un chargement du layout du premier essai en boucle lorsque complété
    if (!window.spectating) {       // problème observé en utilisant la config test_layout(bug__enlevel), simplement le commmenter semble suffir
        disable_key_listener();
    }
    curr_trial = data.trial + 1;
    $('#game-title').text(`Experiment in Progress, Block ${data.step+1}/${Object.keys(data.config.blocs).length}, Trial ${curr_trial}/${Object.keys(data.config.blocs[data.step]).length}`);
    $("#reset-game").show();
    setTimeout(function() {
        //console.log(`[RESET_GAME] Resetting graphics for trial ${curr_trial} in block ${data.step + 1}`);
        $("reset-game").hide();
        graphics_config = {
            container_id : "overcooked",
            start_info : data.state, 
            condition : data.condition,
            Game_Trial_Timer : data.config.Game_Trial_Timer
        };
        if (!window.spectating) {
            enable_key_listener();
        }
        graphics_reset(graphics_config);
        //console.log(`[RESET_GAME] Graphics reset complete for trial ${curr_trial} in block ${data.step + 1}`);

    }, data.timeout);
    socket.emit("new_trial");     
    //console.log(`[RESET_GAME] Emitted new_trial event for trial ${curr_trial} in block ${data.step + 1}`);
});

socket.on('state_pong', function(data) {
    // Draw state update
    drawState(data['state']);
});

socket.on('end_game', function(data) {
    // Hide game data and display game-over html
    graphics_end();
    if (!window.spectating) {
        disable_key_listener();
    }
    let bloc = $('#bloc').text();
    let step = $('#step').text();
    
    // Vérifier si c'est un questionnaire post-trial ou post-bloc
    if (data.show_post_trial_questionnaire && !data.is_last_trial_in_bloc) {
        // Questionnaire post-trial
        console.log(`[POST_TRIAL] Affichage du questionnaire post-trial pour l'essai ${data.curr_trial_in_game + 1}/${data.total_trials_in_bloc}`);
        $('#overcooked-container').append(`<h4>Please answer few questions about the game you just completed (${data.curr_trial_in_game + 1}/${data.total_trials_in_bloc})</h4>`);
    } else if (data.is_last_trial_in_bloc) {
        // Questionnaire post-bloc
        console.log(`[POST_BLOC] Affichage du questionnaire post-bloc après ${data.total_trials_in_bloc} essais`);
        $('#overcooked-container').append(`<h4>For the upcoming questions, consider the whole block of games and how the agent communicated its intentions to you.</h4>`);
    } else {
        // Cas par défaut
        $('#overcooked-container').append(`<h4>For the upcoming questions, consider the whole block of games and how the agent communicated its intentions to you.</h4>`);
    }
    
    $('#game-title').hide();
    $('#game-over').show();
    $('#overcooked').hide();
    $('#answer').attr("disabled", false);
    $("#leave").hide();
    $('#leave').attr("disabled", true)
    
    // Game ended unexpectedly
    if (data.status === 'inactive') {
        $('#error-exit').show();
    }
});

socket.on('end_lobby', function() {
    // Hide lobby
    console.log("end_lobby");
    $('#lobby').hide();
    $('#waiting').hide();
    $('#leave').hide();
    $('#leave').attr("disabled", true);
    $('#instructions').show();
    $('#tutorial').show();

    showStartOverlay('You have left the lobby. Click the button to start a new game.');

    clearInterval(window.intervalID);
    window.intervalID = -1;
})



/* * * * * * * * * * * * * * 
 * Game Key Event Listener *
 * * * * * * * * * * * * * */

function enable_key_listener() {
    $(document).on('keydown', function(e) {
        let action = 'STAY'
        switch (e.which) {
            case 37: // left
                action = 'LEFT';
                break;

            case 38: // up
                action = 'UP';
                break;

            case 39: // right
                action = 'RIGHT';
                break;

            case 40: // down
                action = 'DOWN';
                break;

            case 32: //space
                action = 'SPACE';
                break;

            default: // exit this handler for other keys
                return; 
        }
        e.preventDefault();
        socket.emit('action', { 'action' : action, 'condition' : condition});
    });
};

function disable_key_listener() {
    $(document).off('keydown');
};


/* * * * * * * * * * *
 * Utility Functions *
 * * * * * * * * * * */
// convertit des dictionnaires en json
var arrToJSON = function(arr) {
    let retval = {}
    for (let i = 0; i < arr.length; i++) {
        elem = arr[i];
        key = elem['name'];
        value = elem['value'];
        retval[key] = value;
    }
    return retval;
};