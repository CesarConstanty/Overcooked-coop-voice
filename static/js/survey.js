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
var qpt_model;
var qpt_elements;
var qptStartTime = null;
var qptSubmitted = false;
var qptTimerInterval = null;

// SurveyJS only for QPB and Hoffman
socket.on("connect", function () {
    console.log("connect survey")
    Survey.StylesManager.applyTheme("defaultV2");

    // -- QPB (SurveyJS)
    let qpb_elements_raw = $('#qpb_elements').text();
    let qpb_elements = null;
    if (qpb_elements_raw && qpb_elements_raw.trim().length > 0 && qpb_elements_raw.trim() !== "None" && qpb_elements_raw.trim() !== "null") {
        try {
            qpb_elements = JSON.parse(qpb_elements_raw);
        } catch (e) {
            console.error("Erreur de parsing qpb_elements:", e);
        }
    }
    if (qpb_elements && qpb_elements.elements && qpb_elements.elements.length > 0) {
        var qpb_model = new Survey.Model(qpb_elements);
        qpb_model.onComplete.add(function (sender) {
            socket.emit("post_qpb", { "survey_data": sender.data });
        });
        $("#QpbDisplay").Survey({
            model: qpb_model
        });
    }

    // -- Hoffman (SurveyJS)
    let hoffman_elements_raw = $('#hoffman_elements').text();
    let hoffman_elements = null;
    if (hoffman_elements_raw && hoffman_elements_raw.trim().length > 0 && hoffman_elements_raw.trim() !== "None" && hoffman_elements_raw.trim() !== "null") {
        try {
            hoffman_elements = JSON.parse(hoffman_elements_raw);
        } catch (e) {
            console.error("Erreur de parsing hoffman_elements:", e);
        }
    }
    if (hoffman_elements && hoffman_elements.elements && hoffman_elements.elements.length > 0) {
        var hoffman_model = new Survey.Model(hoffman_elements);
        hoffman_model.onComplete.add(function (sender) {
            socket.emit("post_hoffman", { "survey_data": sender.data });
            console.log('debug', sender.data);
        });
        $("#HoffmanDisplay").Survey({
            model: hoffman_model
        });
    }
});

// Handler pour le QPT natif (agency)
socket.on('qpt', function (data, callback) {
    // Affiche le formulaire natif
    $('#overcooked').hide();
    $("#qpt").show();

    // Affichage conditionnel du score ou du temps
    if (typeof data.score !== "undefined") {
        $("#agency_score_placeholder").text(data.score);
    }

    // Réinitialise les sliders et data-touched
    $('#qptForm input[type=range]').each(function() {
        $(this).val(50);
        $(this).attr('data-touched', 'false');
    });
    checkQptFormComplete();

    qptStartTime = Date.now();
    qptSubmitted = false;
    window.qptCallback = callback;
    window.curr_trial_id = data.trial;

    // Timer
    let timer = data.qpt_length || 30;
    $("#qpt_timer").text(timer + " seconds left");
    if (qptTimerInterval) {
        clearInterval(qptTimerInterval);
        qptTimerInterval = null;
    }
    qptTimerInterval = setInterval(function() {
        timer -= 1;
        $("#qpt_timer").text(timer + " seconds left");
        if (timer <= 0) {
            clearInterval(qptTimerInterval);
            qptTimerInterval = null;
            if ($("#qpt").is(":visible") && !qptSubmitted) {
                sendQptForm(true); // timeout_bool = true
            }
        }
    }, 1000);
});

// Gestion du bouton submit QPT natif
function sendQptForm(timeout_bool = false) {
    if (qptSubmitted) return;
    qptSubmitted = true;
    if (qptTimerInterval) {
        clearInterval(qptTimerInterval);
        qptTimerInterval = null;
    }
    $("#qptForm button[type=submit]").prop("disabled", true);
    const data = {};
    $('#qptForm input[type=range]').each(function() {
        let touched = $(this).attr('data-touched');
        let val = $(this).val();
        data[$(this).attr('name')] = (touched !== "true") ? "nan" : val;
    });
    // Ajoute le temps écoulé en secondes
    let elapsed = qptStartTime ? ((Date.now() - qptStartTime) / 1000) : null;
    socket.emit("post_qpt", { "survey_data": data, "timeout_bool": timeout_bool, "trial_id": window.curr_trial_id || 0, "time": elapsed });
    $("#qpt").hide();
    if (window.qptCallback) window.qptCallback();
}

$(document).on('submit', '#qptForm', function(e) {
    e.preventDefault();
    sendQptForm(false);
});

// Vérifie si tous les sliders ont été touchés pour activer le bouton submit
function checkQptFormComplete() {
    let complete = true;
    $('#qptForm input[type=range]').each(function() {
        if ($(this).attr('data-touched') !== "true") {
            complete = false;
        }
    });
    $("#qptForm button[type=submit]").prop("disabled", !complete);
}

// Marque le slider comme touché à la première interaction et vérifie le formulaire
$(document).on('input change', '#qptForm input[type=range]', function() {
    $(this).attr('data-touched', 'true');
    checkQptFormComplete();
});

socket.on('next_step', function () {
    location.reload();
});

socket.on('qpb', function () {
    $("#qpt").hide();
    $("#QpbDisplay").show();
    $("#qpb").show();
});

socket.on('hoffman', function () {
    $("#qpb").hide();
    $("#HoffmanDisplay").show();
    $("#hoffman").show();
});

