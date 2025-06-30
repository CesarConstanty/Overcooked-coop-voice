console.log("executing survey_manager");

class CallBackTrigger {
    constructor(callback, trial_id) {
        this.callback = callback;
        this.trial_id = trial_id;
    }
    trigger() {
        this.callback("qpt")
    }
}

var timeout;
var timeleft;
var callbacktrigger;
var qpt_timeout_bool = false;
var qpt_model
var qpt_elements

socket.on("connect", function () {
    console.log("connect survey")
    Survey.StylesManager.applyTheme("defaultV2");
    var qpt_raw = $('#qpt_elements').text();
    if (qpt_raw && qpt_raw.trim() !== "None" && qpt_raw.trim() !== "") {
        qpt_elements = JSON.parse(qpt_raw);
        qpt_model = new Survey.Model(qpt_elements);

        qpt_model.onComplete.add(function (sender) {
            callbacktrigger.trigger()
            clearTimeout(timeout);
            clearInterval(timeleft);
            $('#overcooked').show();
            $('#qpt').hide();
            console.log(sender.data);
            socket.emit("post_qpt", { "survey_data": sender.data, "trial_id": callbacktrigger.trial_id, "timeout_bool": qpt_timeout_bool });
            qpt_timeout_bool = false;
        });
        $("#QptDisplay").Survey({ model: qpt_model });
    }
    
    // -- qpb 
    var qpb_elements = JSON.parse($('#qpb_elements').text());
    var qpb_model = new Survey.Model(qpb_elements);
    qpb_model.onComplete.add(function (sender) {
        socket.emit("post_qpb", { "survey_data": sender.data });
    });
    $("#QpbDisplay").Survey({
        model: qpb_model
    });

    // -- hoffman
    var hoffman_elements = JSON.parse($('#hoffman_elements').text());
    var hoffman_model = new Survey.Model(hoffman_elements);
    hoffman_model.onComplete.add(function (sender) {
        socket.emit("post_hoffman", { "survey_data": sender.data });
        console.log('debug', sender.data);
    });
    $("#HoffmanDisplay").Survey({
        model: hoffman_model
    });

})

socket.on('qpt', function (data, callback) {
    console.log("qpt event received", data);
    $('#overcooked').hide();
    $("#qpt").show();
    window.qptCallback = callback;

    // Met à jour dynamiquement le score dans la question 3
    if (typeof data.score !== "undefined") {
        $("#agency_score_placeholder").text(data.score);
    }

    // Timer et autres logiques...
    let timer = data.qpt_length || 30;
    let interval = setInterval(function() {
        timer -= 1;
        $("#qpt_timer").text(timer + " seconds left");
        if (timer <= 0) {
            clearInterval(interval);
            if ($("#qpt").is(":visible")) {
                $("#qptForm").submit();
            }
        }
    }, 1000);

    // Initialisation des sliders
    $('#qptForm input[type=range]').attr('data-touched', 'false');
    checkQptFormComplete();
});

socket.on('qpb', function () {
    $('#overcooked').hide();
    $("#qpb").show();
})

socket.on('hoffman', function () {
    $('#overcooked').hide();
    $("#qpb").hide();
    $("#hoffman").show();
})

socket.on('next_step', function () {
    location.reload();
})

$(document).on('submit', '#qptForm', function(e) {
    e.preventDefault();
    const data = {};
    $('#qptForm input[type=range]').each(function() {
        let val = $(this).val();
        data[$(this).attr('name')] = (val === "" || val === undefined || val === null) ? "nan" : val;
    });
    socket.emit("post_qpt", { "survey_data": data, "timeout_bool": false, "trial_id": window.curr_trial_id || 0 });
    $("#qpt").hide();
    if (window.qptCallback) window.qptCallback();
});

function checkQptFormComplete() {
    let complete = true;
    $('#qptForm input[type=range]').each(function() {
        // On considère qu'une réponse est donnée si le slider a été touché
        if ($(this).attr('data-touched') !== "true") {
            complete = false;
        }
    });
    $("#qptForm button[type=submit]").prop("disabled", !complete);
}

// Met à jour à chaque changement de slider
$(document).on('input change', '#qptForm input[type=range]', function() {
    checkQptFormComplete();
});

// Vérifie à l'ouverture du questionnaire
socket.on('qpt', function (data, callback) {
    console.log("qpt event received", data);
    $('#overcooked').hide();
    $("#qpt").show();
    window.qptCallback = callback;

    // Timer
    let timer = data.qpt_length || 30;
    let interval = setInterval(function() {
        timer -= 1;
        $("#qpt_timer").text(timer + " seconds left");
        if (timer <= 0) {
            clearInterval(interval);
            // Auto-submit le questionnaire si non soumis
            if ($("#qpt").is(":visible")) {
                $("#qptForm").submit();
            }
        }
    }, 1000);

    checkQptFormComplete(); // Vérifie au démarrage
});

// Ajoute l'attribut data-touched à chaque slider au chargement du questionnaire
socket.on('qpt', function (data, callback) {
    $('#qptForm input[type=range]').attr('data-touched', 'false');
    checkQptFormComplete(); // Vérifie au démarrage
});

// Marque le slider comme touché à la première interaction
$(document).on('input change', '#qptForm input[type=range]', function() {
    $(this).attr('data-touched', 'true');
    checkQptFormComplete();
});

// Modifie la collecte des données à la soumission
$(document).on('submit', '#qptForm', function(e) {
    e.preventDefault();
    const data = {};
    $('#qptForm input[type=range]').each(function() {
        let touched = $(this).attr('data-touched');
        let val = $(this).val();
        data[$(this).attr('name')] = (touched !== "true") ? "nan" : val;
    });
    socket.emit("post_qpt", { "survey_data": data, "timeout_bool": false, "trial_id": window.curr_trial_id || 0 });
    $("#qpt").hide();
    if (window.qptCallback) window.qptCallback();
});

