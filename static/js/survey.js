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
var qpbTimerInterval = null;
var qpbSubmitted = false;
var hoffmanTimerInterval = null;
var hoffmanSubmitted = false;

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
            qpbSubmitted = true;
            if (qpbTimerInterval) {
                clearInterval(qpbTimerInterval);
                qpbTimerInterval = null;
            }
            socket.emit("post_qpb", { "survey_data": sender.data });
        });
        $("#QpbDisplay").Survey({
            model: qpb_model
        });

        // Timer QPB sera démarré seulement quand le questionnaire s'affiche
        window.qpb_model = qpb_model; // Rendre accessible globalement pour l'événement qpb
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
            hoffmanSubmitted = true;
            if (hoffmanTimerInterval) {
                clearInterval(hoffmanTimerInterval);
                hoffmanTimerInterval = null;
            }
            socket.emit("post_hoffman", { "survey_data": sender.data });
            console.log('debug', sender.data);
        });
        $("#HoffmanDisplay").Survey({
            model: hoffman_model
        });

        // Timer Hoffman sera démarré seulement quand le questionnaire s'affiche
        window.hoffman_model = hoffman_model; // Rendre accessible globalement pour l'événement hoffman
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
    // Récupère le numéro du bloc courant et le nombre total de blocs
    var step = parseInt($('#step').text());
    var total_blocs = parseInt($('#total_blocs').text());
    // Si on vient de finir le dernier bloc, on redirige vers le ranking
    if (step + 1 > total_blocs) {
        window.location.href = "/qex_ranking";
    } else {
        // MODIFICATION: Rediriger vers /planning au lieu de recharger la page
        // Cela déclenchera la logique de vérification des tutoriels de condition
        window.location.href = "/planning";
    }
});

socket.on('qpb', function () {
    $("#qpt").hide();
    $("#QpbDisplay").show();
    $("#qpb").show();
    
    // Démarre le timer QPB maintenant que le questionnaire est affiché
    if (window.qpb_model) {
        qpbSubmitted = false;
        let qpb_timer_val = parseInt($("#qpb_timer_value").text()) || 30;
        let timer = qpb_timer_val;
        
        // Ajoute un affichage du timer si besoin
        if ($("#QpbDisplay").find("#qpb_timer_display").length === 0) {
            $("#QpbDisplay").prepend('<div id="qpb_timer_display" style="text-align:center; font-size:1.1em; color:#3a7bd5; margin-bottom:1em;"></div>');
        }
        $("#qpb_timer_display").text(timer + " seconds left");

        if (qpbTimerInterval) {
            clearInterval(qpbTimerInterval);
            qpbTimerInterval = null;
        }
        qpbTimerInterval = setInterval(function () {
            timer -= 1;
            $("#qpb_timer_display").text(timer + " seconds left");
            if (timer <= 0) {
                clearInterval(qpbTimerInterval);
                qpbTimerInterval = null;
                if (!qpbSubmitted) {
                    // Remplit les questions non répondues avec "nan"
                    let data = window.qpb_model.data;
                    let qpb_elements_raw = $('#qpb_elements').text();
                    let qpb_elements = JSON.parse(qpb_elements_raw);
                    qpb_elements.elements.forEach(function (q) {
                        if (q && q.name && (data[q.name] === undefined || data[q.name] === null || data[q.name] === "")) {
                            data[q.name] = "nan";
                        }
                    });
                    qpbSubmitted = true;
                    window.qpb_model.onComplete.clear(); // Empêche double envoi
                    socket.emit("post_qpb", { "survey_data": data });
                }
            }
        }, 1000);
    }
});

socket.on('hoffman', function () {
    var step = parseInt($('#step').text());
    var total_blocs = parseInt($('#total_blocs').text());
    console.log("Signal hoffman reçu : ", hoffman_elements, " STEP : ", step );
    $("#qpb").hide();
    $("#HoffmanDisplay").show();
    $("#hoffman").show();
    
    // Démarre le timer Hoffman maintenant que le questionnaire est affiché
    if (window.hoffman_model) {
        hoffmanSubmitted = false;
        let hoffman_timer_val = parseInt($("#hoffman_timer_value").text()) || 30;
        let timer = hoffman_timer_val;
        
        // Ajoute un affichage du timer si besoin
        if ($("#HoffmanDisplay").find("#hoffman_timer_display").length === 0) {
            $("#HoffmanDisplay").prepend('<div id="hoffman_timer_display" style="text-align:center; font-size:1.1em; color:#3a7bd5; margin-bottom:1em;"></div>');
        }
        $("#hoffman_timer_display").text(timer + " seconds left");

        if (hoffmanTimerInterval) {
            clearInterval(hoffmanTimerInterval);
            hoffmanTimerInterval = null;
        }
        hoffmanTimerInterval = setInterval(function () {
            timer -= 1;
            $("#hoffman_timer_display").text(timer + " seconds left");
            if (timer <= 0) {
                clearInterval(hoffmanTimerInterval);
                hoffmanTimerInterval = null;
                if (!hoffmanSubmitted) {
                    // Remplit les questions non répondues avec "nan"
                    let data = window.hoffman_model.data;
                    let hoffman_elements_raw = $('#hoffman_elements').text();
                    let hoffman_elements = JSON.parse(hoffman_elements_raw);
                    hoffman_elements.elements.forEach(function (q) {
                        if (q && q.name && (data[q.name] === undefined || data[q.name] === null || data[q.name] === "")) {
                            data[q.name] = "nan";
                        }
                    });
                    hoffmanSubmitted = true;
                    window.hoffman_model.onComplete.clear(); // Empêche double envoi
                    socket.emit("post_hoffman", { "survey_data": data });
                }
            }
        }, 1000);
    }
});

