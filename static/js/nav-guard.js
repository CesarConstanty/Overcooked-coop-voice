/* nav-guard.js — contrôle de navigation du parcours expérimental.
 *
 * Politique (alignée avec le filet serveur dans app.py) :
 *   1) Rechargement (F5/Ctrl+R) : autorisé, on reste sur la page courante
 *      (permet au participant de pallier un éventuel bug).
 *   2) Retour en arrière (bouton Précédent) : renvoie à la première page
 *      de l'expérience.
 *   3) Retour en avant (bouton Suivant) : renvoie à la dernière page visitée
 *      (la plus avancée du parcours).
 *   4) Toute autre navigation hors de l'ordre prévu est neutralisée.
 *
 * Dépendance : window.NAV_GUARD.firstUrl (URL d'entrée, injectée par le serveur).
 *
 * Détection : chaque entrée d'historique porte history.state.ng_pos ; sessionStorage
 * conserve la position courante (curPos), la position maximale atteinte (maxPos) et
 * l'URL la plus avancée (lastUrl). Tout est évalué SYNCHRONEMENT au chargement de la
 * page : on n'attend pas l'évènement popstate (peu fiable entre documents). Le pire
 * comportement possible est une redirection vers la première / dernière page — jamais
 * une perte de données.
 */
(function () {
  "use strict";

  var CFG = window.NAV_GUARD || {};
  var FIRST_URL = CFG.firstUrl || "/";
  var here = location.pathname + location.search;

  var K = {
    max: "ng.maxPos",
    cur: "ng.curPos",
    last: "ng.lastUrl",
    toFirst: "ng.gotoFirst",
    toLast: "ng.gotoLast"
  };

  function num(v, d) {
    var n = parseInt(v, 10);
    return isNaN(n) ? d : n;
  }

  function store() {
    try {
      return window.sessionStorage;
    } catch (e) {
      return null;
    }
  }

  function setPos(pos) {
    try {
      history.replaceState({ ng_pos: pos }, "", here);
    } catch (e) {
      /* environnements sans History API : on ne casse rien */
    }
  }

  function decide() {
    var s = store();
    if (!s) {
      return; // sessionStorage indisponible : ne rien neutraliser.
    }

    var maxPos = num(s.getItem(K.max), -1);
    var curPos = num(s.getItem(K.cur), -1);
    var lastUrl = s.getItem(K.last) || here;

    // (A) Atterrissage suite à une redirection que NOUS avons déclenchée.
    //     location.replace() efface history.state : on le reconstruit ici.
    if (s.getItem(K.toFirst) === "1") {
      s.removeItem(K.toFirst);
      setPos(0);
      s.setItem(K.cur, "0");          // page courante = première page
      return;                          // maxPos / lastUrl conservés (mémoire de l'avancée)
    }
    if (s.getItem(K.toLast) === "1") {
      s.removeItem(K.toLast);
      setPos(maxPos);
      s.setItem(K.cur, String(maxPos));
      s.setItem(K.last, here);
      return;
    }

    var st = history.state || {};
    var pos = (typeof st.ng_pos === "number") ? st.ng_pos : null;

    // (B) Navigation « vers l'avant » normale (clic bouton / redirection serveur)
    //     ou URL saisie à la main : pas de ng_pos → nouvelle page la plus avancée.
    if (pos === null) {
      var np = maxPos + 1;
      setPos(np);
      s.setItem(K.max, String(np));
      s.setItem(K.cur, String(np));
      s.setItem(K.last, here);
      return;
    }

    // (C) Rechargement de la page courante → autorisé (point 1).
    if (pos === curPos) {
      return;
    }

    // (D) Retour en arrière (entrée plus ancienne) → première page (point 2).
    if (pos < curPos) {
      s.setItem(K.cur, String(pos)); // anti-boucle
      if (here !== FIRST_URL) {
        s.setItem(K.toFirst, "1");
        location.replace(FIRST_URL);
      }
      return;
    }

    // (E) Retour en avant (entrée plus récente) → dernière page visitée (point 3).
    s.setItem(K.cur, String(pos));
    if (here !== lastUrl) {
      s.setItem(K.toLast, "1");
      location.replace(lastUrl);
    }
  }

  decide();

  // Restauration depuis le bfcache : history.state est rétabli mais le script
  // de tête n'est pas forcément ré-exécuté → on réévalue.
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) {
      decide();
    }
  });
})();
