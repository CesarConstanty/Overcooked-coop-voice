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

    // Affiche juste le timer informatif
    let timer = data.qpt_length || 30;
    let interval = setInterval(function() {
        timer -= 1;
        $("#qpt_timer").text(timer + " seconds left");
        if (timer <= 0) {
            clearInterval(interval);
            // Auto-submit le questionnaire si non soumis
            if ($("#qpt").is(":visible")) {
                // Option 1 : soumission automatique du formulaire (si tu veux forcer la collecte des valeurs actuelles)
                $("#qptForm").submit();
                // Option 2 : si tu veux juste passer à la suite sans soumettre :
                // $("#qpt").hide();
                // if (window.qptCallback) window.qptCallback();
            }
        }
    }, 1000);

    // Laisse le bouton actif
    $("#qptForm button[type=submit]").prop("disabled", false);
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
        data[$(this).attr('name')] = $(this).val();
    });
    socket.emit("post_qpt", { "survey_data": data, "timeout_bool": false, "trial_id": window.curr_trial_id || 0 });
    $("#qpt").hide();
    if (window.qptCallback) window.qptCallback();
});

