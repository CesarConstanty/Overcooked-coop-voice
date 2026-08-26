// Persistent network connection that will be used to transmit real-time data
var socket = io();

var config;

var tutorial_instructions = () => [
    `
    <p>How it works: <b>The Cutting Board</b></p>
    <p>Every ingredient must be <b>chopped</b> before it can go into the pot &mdash; you will not be able to drop a raw ingredient into the pot.</p>
    <p>Grab an ingredient from a <b>dispenser</b>, drop it on the <b>cutting board</b>, then press <b>spacebar</b> several times to chop it. When it's done, pick it up and put it in the pot.</p>
    <p>Cook, plate and deliver a chopped soup to advance.</p>
    <p>Good luck!</p>
    <br></br>
    `,
    `
    <p>How it works: <b>Cooking with an AI teammate</b></p>
    <p>An <b>AI teammate</b> (the blue cook) now prepares recipes alongside you.</p>
    <p>Work together to complete every order shown in <b>All Orders</b>: gather and chop the ingredients, cook the soups, plate them and deliver them.</p>
    <p>This step ends once all the displayed orders have been delivered.</p>
    <br></br>
    `,
    `
    <p>How it works: <b>Cooking together</b></p>
    <p>Some kitchens are quite small, making it difficul to cook together.</br>
    <p>Fortunately, you can continiously walk into your partner to push them back and clear your way</br>
    <br></br>
    `,
    `
    <p>How it works: <b>Exchange zones</b></p>
    <p>This kitchen is divided into two separate work areas. The shared counters in the middle are <b>exchange zones</b>: neither cook can cross the barrier, but both can use these counters.</p>
    <p>Your AI teammate has access to the ingredient dispensers, the pot and the serving window. You have access to the <b>cutting board</b> and the <b>plate dispenser</b>.</p>
    <p>Pick up the raw onion placed by the AI on an exchange counter, chop it, then place the chopped onion back on an exchange counter. Also pass a plate to the AI when it is needed. Complete the onion soup to finish the tutorial.</p>
    <br></br>
    `
];

var tutorial_hints = () => [
    `
    <p>You must <b>chop before potting</b>: drop the ingredient on the cutting board, press <b>spacebar</b> repeatedly until it is fully cut, then pick it up and add it to the pot.</p>
    `,
    `
    <p>Share the work with the blue cook and complete every order displayed in <b>All Orders</b>.</p>
    `,
    `
    <p>Remember: every ingredient must be <b>chopped</b> on the cutting board before it goes into the pot. Split the work with your <b>AI teammate</b> and deliver all three orders to finish.</p>
    `,
    `
    <p>Face an <b>empty exchange counter</b> and press <b>spacebar</b> to leave the object there. Your teammate can pick it up from the other side. Keep at least one exchange counter free for the next transfer.</p>
    `
];

var curr_tutorial_phase;

// Read in game config provided by server
$(function() {
    config = JSON.parse($('#config').text());

    const tutorialStepCount = config.tutorialParams.layouts.length;

    tutorial_instructions = tutorial_instructions().slice(
        0,
        tutorialStepCount
    );

    tutorial_hints = tutorial_hints().slice(
        0,
        tutorialStepCount
    );

    $('#quit').show();
});

/* * * * * * * * * * * * * * * *
 * Button click event handlers
 * * * * * * * * * * * * * * * */

$(function() {
    $('#try-again').click(function() {
        params = config['tutorialParams'];

        let uid = $('#uid').text();
        params.player_uid = uid;

        data = {
            "params": params,
            "game_name": "tutorial"
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
 * Socket event handlers
 * * * * * * * * * * * * */

socket.on('creation_failed', function(data) {
    // Tell user what went wrong
    let err = data['error'];

    $("#overcooked").empty();

    $('#overcooked').append(
        `<h4>Sorry, tutorial creation code failed with error: ${JSON.stringify(err)}</>`
    );

    $('#try-again').show();
    $('#try-again').attr("disabled", false);
});

socket.on('start_game', function(data) {
    curr_tutorial_phase = 0;

    graphics_config = {
        container_id: "overcooked",
        start_info: data.start_info,
        mechanic: data.config.mechanic,
        show_score: true,
        player_colors: {
            0: 'green',
            1: 'blue'
        }
    };

    $("#overcooked").empty();
    $('#game-over').hide();
    $('#try-again').hide();
    $('#try-again').attr('disabled', true);
    $('#hint-wrapper').hide();
    $('#show-hint').text('Show Hint');

    $('#game-title').text(
        `Tutorial in Progress, Phase ${curr_tutorial_phase + 1}/${tutorial_instructions.length}`
    );

    $('#game-title').show();

    $('#tutorial-instructions').append(
        tutorial_instructions[curr_tutorial_phase]
    );

    $('#instructions-wrapper').show();

    $('#hint').append(
        tutorial_hints[curr_tutorial_phase]
    );

    enable_key_listener();
    graphics_start(graphics_config);
});

socket.on('reset_game', function(data) {
    curr_tutorial_phase++;

    // Le serveur émet un dernier reset_game lorsque la dernière étape configurée
    // est validée. On affiche immédiatement la fin du tutoriel, qu'il comporte
    // 3 ou 4 étapes, sans attendre l'événement end_game.
    if (curr_tutorial_phase >= tutorial_instructions.length) {
        graphics_end();
        disable_key_listener();

        $("#overcooked").empty();
        $('#game-title').hide();
        $('#instructions-wrapper').hide();
        $('#hint-wrapper').hide();
        $('#show-hint').hide();
        $('#game-over').show();
        $('#quit').hide();
        $('#startExperiment').show();

        return;
    }

    graphics_end();
    disable_key_listener();

    $("#overcooked").empty();
    $('#tutorial-instructions').empty();
    $('#hint').empty();

    $("#tutorial-instructions").append(
        tutorial_instructions[curr_tutorial_phase]
    );

    $("#hint").append(
        tutorial_hints[curr_tutorial_phase]
    );

    $('#game-title').text(
        `Tutorial in Progress, Phase ${curr_tutorial_phase + 1}/${tutorial_instructions.length}`
    );

    let button_pressed = $('#show-hint').text() === 'Hide Hint';

    if (button_pressed) {
        $('#show-hint').click();
    }

    graphics_config = {
        container_id: "overcooked",
        start_info: data.state,
        show_score: true,
        player_colors: {
            0: 'green',
            1: 'blue'
        }
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

        window.top.postMessage(
            { name: "error" },
            "*"
        );
    } else {
        window.top.postMessage(
            { name: "tutorial-done" },
            "*"
        );
    }

    $('#startExperiment').show();
});

/* * * * * * * * * * * * * *
 * Game Key Event Listener
 * * * * * * * * * * * * * */

function enable_key_listener() {
    $(document).on('keydown', function(e) {
        // Ignore les répétitions automatiques du clavier
        if (e.repeat || (e.originalEvent && e.originalEvent.repeat)) {
            e.preventDefault();
            return;
        }

        let action = 'STAY';

        switch (e.which) {
            case 37:
                action = 'LEFT';
                break;

            case 38:
                action = 'UP';
                break;

            case 39:
                action = 'RIGHT';
                break;

            case 40:
                action = 'DOWN';
                break;

            case 32:
                action = 'SPACE';
                break;

            default:
                return;
        }

        e.preventDefault();

        socket.emit(
            'action',
            { 'action': action }
        );
    });
}

function disable_key_listener() {
    $(document).off('keydown');
}

/* * * * * * * * * * * *
 * Game Initialization
 * * * * * * * * * * * */

socket.on("connect", function() {
    params = $('#user_config').text();

    let data = {
        "params": params,
        "game_name": "tutorial"
    };

    socket.emit("join", data);
});

/* * * * * * * * * * *
 * Utility Functions
 * * * * * * * * * * */

var arrToJSON = function(arr) {
    let retval = {};

    for (let i = 0; i < arr.length; i++) {
        elem = arr[i];
        key = elem['name'];
        value = elem['value'];
        retval[key] = value;
    }

    return retval;
};