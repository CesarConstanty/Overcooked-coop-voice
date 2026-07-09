// Persistent network connection that will be used to transmit real-time data
var socket = io();



var config;

var tutorial_instructions = () => [
    `
    <p>How it works: <b>Recipes &amp; Ingredients</b></p>
    <p>Your goal is to cook and deliver a soup that matches one of the orders shown in <b>All Orders</b>. Only recipes in <b>All Orders</b> earn points.</p>
    <p>Grab your ingredients from the <b>onion</b> and <b>tomato dispensers</b> on the walls. Put your ingredient(s) in the <b>pot</b>, wait for the soup to cook, pick up a <b>plate</b> from the dish dispenser, collect the soup and deliver it to the <b>serving window</b>.</p>
    <p>Good luck!</p>
    <br></br>
    `,
    `
    <p>How it works: <b>The Cutting Board</b></p>
    <p>From now on, every ingredient must be <b>chopped</b> before it can go into the pot &mdash; you will not be able to drop a raw ingredient into the pot.</p>
    <p>Grab an ingredient from a <b>dispenser</b>, drop it on the <b>cutting board</b>, then press <b>spacebar</b> several times to chop it. When it's done, pick it up and put it in the pot.</p>
    <p>Cook, plate and deliver a chopped soup to advance.</p>
    <p>Good luck!</p>
    <br></br>
    `,
    `
    <p>How it works: <b>Cooking together</b></p>
    <p>This kitchen has <b>onion</b> and <b>tomato dispensers</b>, a <b>cutting board</b>, a <b>bin</b> and the serving window &mdash; and this time an <b>AI teammate</b> (the blue cook) prepares soups alongside you.</p>
    <p>Work together to complete <b>all three orders</b> shown in <b>All Orders</b>: gather ingredients, <b>chop</b> them, cook, plate and deliver each one. The tutorial ends once the three orders are done.</p>
    <br></br>
    `
];

var tutorial_hints = () => [
    `
    <p>
        You move up, down, left and right with the <b>arrow keys</b>,
        and interact (grab, drop, use a tile) with the <b>spacebar</b>.
        Face a tile, then press spacebar to use it.
      </p>
    `,
    `
    <p>You must <b>chop before potting</b>: drop the ingredient on the cutting board, press <b>spacebar</b> repeatedly until it is fully cut, then pick it up and add it to the pot.</p>
    `
    ,
    `
    <p>Remember: every ingredient must be <b>chopped</b> on the cutting board before it goes into the pot. Split the work with your <b>AI teammate</b> and deliver all three orders to finish.</p>
    `
]

var curr_tutorial_phase;

// Read in game config provided by server
$(function() {
    config = JSON.parse($('#config').text());
    tutorial_instructions = tutorial_instructions();
    tutorial_hints = tutorial_hints();
    $('#quit').show();
});

/* * * * * * * * * * * * * * * * 
 * Button click event handlers *
 * * * * * * * * * * * * * * * */

$(function() {
    $('#try-again').click(function () {
        params = config['tutorialParams']
        let uid = $('#uid').text();
        params.player_uid = uid;
        data = {
            "params" : params,
            "game_name" : "tutorial"
        };
        socket.emit("join", data);
        $('try-again').attr("disable", true);
    });
});

$(function() {
    $('#show-hint').click(function() {
        let text = $(this).text();
        let new_text = text === "Show Hint" ? "Hide Hint" : "Show Hint";
        $('#hint-wrapper').toggle();
        $(this).text(new_text);
    });
});

$(function() {
    $('#quit').click(function() {
        socket.emit("leave", {});
        $('quit').attr("disable", true);
        window.location.href = "./";
    });
});

$(function() {
    $('#finish').click(function() {
        $('finish').attr("disable", true);
        window.location.href = "./";
    });
});

$(function() {
    $('#startExperiment').click(function() {
        $('startTraining').attr("disable", true);
        window.location.href = "./planning";
    });
});



/* * * * * * * * * * * * * 
 * Socket event handlers *
 * * * * * * * * * * * * */

socket.on('creation_failed', function(data) {
    // Tell user what went wrong
    let err = data['error']
    $("#overcooked").empty();
    $('#overcooked').append(`<h4>Sorry, tutorial creation code failed with error: ${JSON.stringify(err)}</>`);
    $('#try-again').show();
    $('#try-again').attr("disabled", false);
});

socket.on('start_game', function(data) {
    curr_tutorial_phase = 0;
    graphics_config = {
        container_id : "overcooked",
        start_info : data.start_info,
        mechanic : data.config.mechanic,
        show_score : true,
        player_colors : {0: 'green', 1: 'blue'}
    };
    $("#overcooked").empty();
    $('#game-over').hide();
    $('#try-again').hide();
    $('#try-again').attr('disabled', true)
    $('#hint-wrapper').hide();
    $('#show-hint').text('Show Hint');
    $('#game-title').text(`Tutorial in Progress, Phase ${curr_tutorial_phase + 1}/${tutorial_instructions.length}`);
    $('#game-title').show();
    $('#tutorial-instructions').append(tutorial_instructions[curr_tutorial_phase]);
    $('#instructions-wrapper').show();
    $('#hint').append(tutorial_hints[curr_tutorial_phase]);
    enable_key_listener();
    graphics_start(graphics_config);
});

socket.on('reset_game', function(data) {
    curr_tutorial_phase++;
    // À la fin de la dernière phase, le serveur émet un dernier reset_game (curr_phase passe à 3)
    // juste avant end_game. Cet index dépasse alors le nombre d'instructions : on l'ignore pour
    // éviter d'afficher "undefined" / "Phase 4/3" le temps que end_game prenne le relais.
    if (curr_tutorial_phase >= tutorial_instructions.length) {
        return;
    }
    graphics_end();
    disable_key_listener();
    $("#overcooked").empty();
    $('#tutorial-instructions').empty();
    $('#hint').empty();
    $("#tutorial-instructions").append(tutorial_instructions[curr_tutorial_phase]);
    $("#hint").append(tutorial_hints[curr_tutorial_phase]);
    $('#game-title').text(`Tutorial in Progress, Phase ${curr_tutorial_phase + 1}/${tutorial_instructions.length}`);
    
    let button_pressed = $('#show-hint').text() === 'Hide Hint';
    if (button_pressed) {
        $('#show-hint').click();
    }
    graphics_config = {
        container_id : "overcooked",
        start_info : data.state,
        show_score : true,
        player_colors : {0: 'green', 1: 'blue'}
    };
    graphics_start(graphics_config);
    enable_key_listener();
});

socket.on('state_pong', function(data) {
    // Draw state update
    drawState(data['state']);
});

socket.on('end_game', function(data) {
    // Hide game data and display game-over html
    graphics_end();
    disable_key_listener();
    $('#game-title').hide();
    $('#instructions-wrapper').hide();
    $('#hint-wrapper').hide();
    $('#show-hint').hide();
    $('#game-over').show();
    $('#quit').hide();
    
    if (data.status === 'inactive') {
        // Game ended unexpectedly
        $('#error-exit').show();
        // Propogate game stats to parent window with psiturk code
        window.top.postMessage({ name : "error" }, "*");
    } else {
        // Propogate game stats to parent window with psiturk code
        window.top.postMessage({ name : "tutorial-done" }, "*");
    }

    //$('#finish').show();
    $('#startExperiment').show();
});


/* * * * * * * * * * * * * * 
 * Game Key Event Listener *
 * * * * * * * * * * * * * */

function enable_key_listener() {
    $(document).on('keydown', function(e) {
        // Ignore les répétitions automatiques du clavier quand une touche reste
        // enfoncée : un appui prolongé doit produire une seule action, exactement
        // comme un appui unique. (jQuery 1.10 ne normalise pas `repeat` -> originalEvent)
        if (e.repeat || (e.originalEvent && e.originalEvent.repeat)) {
            e.preventDefault();
            return;
        }
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
        socket.emit('action', { 'action' : action });
    });
};

function disable_key_listener() {
    $(document).off('keydown');
};

/* * * * * * * * * * * * 
 * Game Initialization *
 * * * * * * * * * * * */

socket.on("connect", function() {
    // Config for this specific game
    params = $('#user_config').text();
    let data = {
        "params" : params,
        "game_name" : "tutorial",
        
    };

    // create (or join if it exists) new game
    socket.emit("join", data);
});


/* * * * * * * * * * *
 * Utility Functions *
 * * * * * * * * * * */

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