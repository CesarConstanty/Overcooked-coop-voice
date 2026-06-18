/* page-tracker.js — mesure EXACTE du temps passé sur chaque page et de la
 * navigation, côté client, pour la plateforme expérimentale Overcooked.
 *
 * Pourquoi côté client ?
 * ----------------------
 * Le suivi historique était purement serveur : l'horodatage d'une page était
 * pris au moment où Flask rendait la route, et sa durée n'était calculée qu'au
 * chargement de la page SUIVANTE. Ce modèle est inexact pour une expérience de
 * sciences cognitives :
 *   - les retours/avancées via le bfcache ne touchent pas le serveur ;
 *   - la durée incluait la latence réseau + le temps serveur de la requête
 *     suivante, et restait nulle si aucune page suivante n'arrivait (abandon) ;
 *   - le temps « onglet masqué / machine en veille » était compté comme du
 *     temps de lecture ;
 *   - le type de navigation (avant/arrière/reload) était RECONSTRUIT (heuristique)
 *     et non mesuré.
 *
 * Ce module mesure la vérité terrain dans le navigateur et la transmet au
 * serveur, qui l'inscrit telle quelle dans le fichier résultat :
 *   - horloge MONOTONE performance.now() (immunisée contre les sauts d'horloge
 *     système / NTP / DST) pour toutes les durées ;
 *   - type de navigation lu sur l'API Navigation Timing
 *     (performance.getEntriesByType('navigation')[0].type) + pageshow.persisted
 *     pour distinguer une restauration bfcache ;
 *   - deux compteurs : temps « mur » (page affichée) et temps « actif »
 *     (document visible uniquement, via l'API Page Visibility) ;
 *   - remontée fiable même en cas de fermeture brutale : navigator.sendBeacon()
 *     sur visibilitychange→hidden ET pagehide, plus un heartbeat périodique
 *     (borne basse en cas de crash) ;
 *   - chaque VUE de page reçoit un view_id unique (reload et restauration
 *     bfcache = nouvelles vues) pour distinguer les revisites d'une même URL.
 *
 * Coexistence avec nav-guard.js (impératif) :
 *   - injecté APRÈS nav-guard dans le <head> : on observe l'état post-décision ;
 *   - n'utilise QUE des clés sessionStorage préfixées « pt. » (jamais ng.*) ;
 *   - ne touche jamais history.state (ng_pos) ni l'URL servie ;
 *   - n'enregistre AUCUN beforeunload/unload (qui casseraient le bfcache et la
 *     ré-entrée pageshow de la garde) ; uniquement pagehide / visibilitychange ;
 *   - tout est encapsulé dans try/catch : une erreur ici ne doit jamais empêcher
 *     nav-guard.js (script séparé) de s'exécuter, ni bloquer un location.replace.
 *
 * Le serveur fournit, via window.PAGE_TRACK (injecté dans le <head>) :
 *   { token, page, beaconUrl, heartbeatMs }
 *   - token : jeton de vue généré par le serveur au rendu (relie la vue serveur
 *     aux beacons client) ;
 *   - page  : nom canonique de la page (ex. "planning.html") ;
 *   - beaconUrl : endpoint POST (ex. "/track/page") ;
 *   - heartbeatMs : période du heartbeat (0 = désactivé).
 */
(function () {
  "use strict";

  var CFG = window.PAGE_TRACK;
  if (!CFG || !CFG.token) {
    return; // page non suivie (pas de jeton serveur) : ne rien faire.
  }
  // Idempotence : ne pas réarmer si le script est injecté/exécuté deux fois.
  if (window.__PAGE_TRACKER_ACTIVE__) {
    return;
  }
  window.__PAGE_TRACKER_ACTIVE__ = true;

  var BEACON_URL = CFG.beaconUrl || "/track/page";
  var TOKEN = CFG.token;
  var PAGE = CFG.page || (location.pathname + location.search);
  var HEARTBEAT_MS = (typeof CFG.heartbeatMs === "number") ? CFG.heartbeatMs : 15000;

  // ---- Horloges -----------------------------------------------------------
  // performance.now() : monotone, sub-ms, point de départ = navigationStart.
  function perfNow() {
    try {
      if (window.performance && performance.now) return performance.now();
    } catch (e) {}
    return Date.now();
  }
  // Ancre absolue (epoch ms) du début de navigation, pour corréler avec les
  // logs serveur. timeOrigin est l'instant 0 de performance.now().
  var ANCHOR_MS = (function () {
    try {
      if (window.performance && typeof performance.timeOrigin === "number") {
        return performance.timeOrigin;
      }
    } catch (e) {}
    return Date.now();
  })();
  function isoFromPerf(pms) {
    try {
      return new Date(ANCHOR_MS + pms).toISOString();
    } catch (e) {
      try { return new Date().toISOString(); } catch (e2) { return null; }
    }
  }

  // ---- Identité de la vue & type de navigation (vérité terrain) -----------
  function makeViewId() {
    try {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    } catch (e) {}
    return "v-" + ANCHOR_MS.toString(36) + "-" + perfNow().toFixed(0) + "-" +
           Math.floor(Math.random() * 1e9).toString(36);
  }
  var viewId = makeViewId();

  // performance.getEntriesByType('navigation')[0].type :
  //   "navigate" | "reload" | "back_forward" | "prerender"
  var perfNavType = "navigate";
  var redirectCount = 0;
  (function () {
    try {
      var navs = performance.getEntriesByType && performance.getEntriesByType("navigation");
      if (navs && navs.length) {
        perfNavType = navs[0].type || "navigate";
        redirectCount = navs[0].redirectCount || 0;
        return;
      }
    } catch (e) {}
    // Repli sur l'API héritée performance.navigation.
    try {
      if (performance.navigation) {
        var t = performance.navigation.type;
        perfNavType = (t === 1) ? "reload" : (t === 2) ? "back_forward" : "navigate";
        redirectCount = performance.navigation.redirectCount || 0;
      }
    } catch (e) {}
  })();

  // Détection d'une redirection forcée par nav-guard (back→firstUrl /
  // forward→lastUrl) : la garde positionne ng.gotoFirst / ng.gotoLast juste
  // avant son location.replace(). Si ces drapeaux sont présents au chargement,
  // la vue courante est un atterrissage de garde (durée non « lecture réelle »).
  // On LIT sans jamais écrire ces clés (propriété de nav-guard).
  function detectGuardRedirect() {
    try {
      var s = window.sessionStorage;
      if (!s) return { redirect: false, dir: null };
      if (s.getItem("ng.gotoFirst") === "1") return { redirect: true, dir: "back" };
      if (s.getItem("ng.gotoLast") === "1") return { redirect: true, dir: "forward" };
    } catch (e) {}
    return { redirect: false, dir: null };
  }
  var guard = detectGuardRedirect();

  // Chaîne de vues : on conserve la vue précédente (clé pt.* dédiée) pour que le
  // serveur puisse recoudre l'enchaînement si besoin. N'utilise JAMAIS ng.*.
  var prevViewId = null;
  try {
    var st = window.sessionStorage;
    if (st) {
      prevViewId = st.getItem("pt.lastViewId");
      st.setItem("pt.lastViewId", viewId);
    }
  } catch (e) {}

  // ---- Accumulateurs temps mur / temps actif (visible) --------------------
  var startPerf = perfNow();           // début de la vue (mur)
  var activeMs = 0;                     // somme des segments visibles
  var hiddenMs = 0;                     // somme des segments masqués
  var visibleSegStart = null;          // début du segment visible courant
  var hiddenSegStart = null;           // début du segment masqué courant
  var visibilityChanges = 0;
  var heartbeats = 0;
  var enterTs = isoFromPerf(0);         // instant absolu (epoch) du début de page

  (function initSegments() {
    var now = startPerf;
    try {
      if (document.visibilityState === "hidden") {
        hiddenSegStart = now;
      } else {
        visibleSegStart = now;
      }
    } catch (e) {
      visibleSegStart = now; // par défaut : considérer visible
    }
  })();

  function snapshot() {
    var now = perfNow();
    var wall = now - startPerf;
    var active = activeMs + (visibleSegStart !== null ? (now - visibleSegStart) : 0);
    var hidden = hiddenMs + (hiddenSegStart !== null ? (now - hiddenSegStart) : 0);
    return {
      wall_ms: Math.max(0, Math.round(wall * 100) / 100),
      active_ms: Math.max(0, Math.round(active * 100) / 100),
      hidden_ms: Math.max(0, Math.round(hidden * 100) / 100)
    };
  }

  // ---- Transmission -------------------------------------------------------
  function send(type, opts) {
    opts = opts || {};
    try {
      var d = snapshot();
      var payload = {
        type: type,                         // "enter" | "heartbeat" | "exit"
        token: TOKEN,
        view_id: viewId,
        prev_view_id: prevViewId,
        page: PAGE,
        perf_nav_type: perfNavType,         // navigate | reload | back_forward | prerender
        redirect_count: redirectCount,
        persisted: !!opts.persisted,        // restauration bfcache
        guard_redirect: guard.redirect,     // atterrissage forcé par nav-guard
        guard_dir: guard.dir,               // "back" | "forward" | null
        enter_ts: enterTs,                  // début de page (epoch ISO)
        client_now: (function () { try { return new Date().toISOString(); } catch (e) { return null; } })(),
        wall_ms: d.wall_ms,                 // temps mur cumulé (page affichée)
        active_ms: d.active_ms,             // temps actif cumulé (document visible)
        hidden_ms: d.hidden_ms,             // temps masqué cumulé
        visibility_changes: visibilityChanges,
        heartbeats: heartbeats,
        history_length: (function () { try { return history.length; } catch (e) { return null; } })(),
        referrer: (function () { try { return document.referrer || ""; } catch (e) { return ""; } })()
      };
      if (opts.exit_reason) payload.exit_reason = opts.exit_reason;

      var body = JSON.stringify(payload);
      var delivered = false;
      // sendBeacon : survit au teardown de la page (transport privilégié).
      try {
        if (navigator.sendBeacon) {
          var blob = new Blob([body], { type: "application/json" });
          delivered = navigator.sendBeacon(BEACON_URL, blob);
        }
      } catch (e) {
        delivered = false;
      }
      if (!delivered) {
        // Repli : fetch keepalive (ne pas bloquer le teardown).
        try {
          fetch(BEACON_URL, {
            method: "POST",
            body: body,
            headers: { "Content-Type": "application/json" },
            keepalive: true,
            credentials: "same-origin"
          })["catch"](function () {});
        } catch (e) {}
      }
    } catch (e) {
      /* ne jamais laisser une erreur de suivi remonter */
    }
  }

  // ---- Gestion du cycle de vie -------------------------------------------
  function onVisibilityChange() {
    try {
      var now = perfNow();
      visibilityChanges++;
      if (document.visibilityState === "hidden") {
        // Fin d'un segment visible → bascule masqué.
        if (visibleSegStart !== null) { activeMs += now - visibleSegStart; visibleSegStart = null; }
        if (hiddenSegStart === null) hiddenSegStart = now;
        // « hidden » est le point de flush fiable (mobile saute souvent pagehide).
        send("exit", { exit_reason: "hidden" });
      } else {
        // Retour visible → reprise du segment actif.
        if (hiddenSegStart !== null) { hiddenMs += now - hiddenSegStart; hiddenSegStart = null; }
        if (visibleSegStart === null) visibleSegStart = now;
      }
    } catch (e) {}
  }

  function onPageHide(e) {
    try {
      var now = perfNow();
      if (visibleSegStart !== null) { activeMs += now - visibleSegStart; visibleSegStart = null; }
      if (hiddenSegStart !== null) { hiddenMs += now - hiddenSegStart; hiddenSegStart = null; }
      var persisted = !!(e && e.persisted);
      send("exit", { exit_reason: persisted ? "pagehide_bfcache" : "pagehide", persisted: persisted });
    } catch (e2) {}
  }

  function onPageShow(e) {
    // Restauration depuis le bfcache : la closure JS persiste (les compteurs
    // continuent), mais on ré-amorce le segment courant et on signale la reprise.
    try {
      if (e && e.persisted) {
        var now = perfNow();
        if (document.visibilityState === "visible") {
          if (visibleSegStart === null) visibleSegStart = now;
        } else {
          if (hiddenSegStart === null) hiddenSegStart = now;
        }
        send("enter", { persisted: true });
      }
    } catch (e2) {}
  }

  try { document.addEventListener("visibilitychange", onVisibilityChange, true); } catch (e) {}
  try { window.addEventListener("pagehide", onPageHide, true); } catch (e) {}
  try { window.addEventListener("pageshow", onPageShow, true); } catch (e) {}

  // Heartbeat : borne basse de durée même si crash/coupure (ni pagehide ni
  // hidden ne se déclenchent). Émis uniquement quand la page est visible.
  if (HEARTBEAT_MS && HEARTBEAT_MS > 0) {
    try {
      setInterval(function () {
        try {
          if (document.visibilityState === "visible") {
            heartbeats++;
            send("heartbeat");
          }
        } catch (e) {}
      }, HEARTBEAT_MS);
    } catch (e) {}
  }

  // Annonce initiale de la vue (ouverture côté serveur du suivi exact).
  send("enter", {});
})();
