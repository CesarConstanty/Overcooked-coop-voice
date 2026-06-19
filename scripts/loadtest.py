#!/usr/bin/env python3
"""Load-test du serveur Overcooked : N participants simulés jouant EN PARALLÈLE.

But : mesurer empiriquement le plafond de charge d'un process eventlet mono-worker
AVANT le lancement, pour fixer MAX_GAMES. On simule K participants qui rejoignent une
partie (binôme avec l'IA) et on mesure la cadence des frames serveur (intervalle entre
deux `state_pong`, cible ~1/fps = 100 ms) et les déconnexions.

Chaque client :
  1) ouvre une session HTTP `/?TEST_UID=<id>&CONFIG=<config>` (crée + connecte l'User) ;
  2) ouvre une WebSocket Socket.IO en partageant le cookie de session ;
  3) émet `join`, écoute `state_pong` (chronométrage), et `end_game` -> re-`join`.

Méthode recommandée : lancer K = 2, 4, 8, 12, 16 SUR LE CPU DE PROD et sur la plus
grande layout. Plafond sûr = plus grand K où p95(intervalle) < ~150 ms sans déconnexion,
puis retirer ~30 % de marge -> MAX_GAMES.

NB : à lancer contre un serveur dont les layouts du bloc existent. Si `frames mesurées`
reste à 0 (aucune partie ne démarre), c'est que le `join` minimal ne suffit pas à assigner
le layout d'essai (le flux réel passe par consentement -> instructions -> planning) ou que
le fichier .layout est absent : compléter alors la séquence HTTP de préchauffe ci-dessous
pour parcourir ces pages avant le `join`.

Dépendances :  pip install "python-socketio[client]" requests websocket-client

Exemples :
  python scripts/loadtest.py --base-url http://127.0.0.1:5000 --clients 8 --duration 90
  python scripts/loadtest.py --base-url https://overcooked.exemple.fr --clients 12 --duration 120
"""
import argparse
import statistics
import sys
import threading
import time

try:
    import requests
    import socketio
except ImportError:
    sys.exit('Dépendances manquantes : pip install "python-socketio[client]" requests websocket-client')


def _cookie_header(session):
    return "; ".join("%s=%s" % (c.name, c.value) for c in session.cookies)


class Client(threading.Thread):
    def __init__(self, idx, base_url, config_id, stop_evt):
        super().__init__(daemon=True)
        self.idx = idx
        self.base_url = base_url.rstrip("/")
        self.config_id = config_id
        self.stop_evt = stop_evt
        self.uid = "loadtest_%03d" % idx
        self.intervals = []        # secondes entre deux state_pong
        self._last_pong = None
        self.disconnects = 0
        self.games_done = 0
        self.errors = []
        self.sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)

    def _wire(self):
        sio = self.sio

        @sio.on("state_pong")
        def _on_pong(_data):
            now = time.monotonic()
            if self._last_pong is not None:
                self.intervals.append(now - self._last_pong)
            self._last_pong = now

        @sio.on("end_game")
        def _on_end(_data):
            self.games_done += 1
            self._last_pong = None
            if not self.stop_evt.is_set():
                # Laisser le serveur nettoyer la partie avant de re-rejoindre.
                time.sleep(0.5)
                self._join()

        @sio.on("creation_failed")
        def _on_fail(data):
            self.errors.append("creation_failed: %s" % (data or {}).get("error"))

        @sio.event
        def disconnect():
            self.disconnects += 1

    def _join(self):
        try:
            self.sio.emit("join", {"create_if_not_found": True,
                                   "game_name": "overcooked", "params": {}})
        except Exception as e:  # noqa: BLE001
            self.errors.append("join: %r" % e)

    def run(self):
        s = requests.Session()
        try:
            r = s.get("%s/?TEST_UID=%s&CONFIG=%s" % (self.base_url, self.uid, self.config_id),
                      timeout=30)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            self.errors.append("http warmup: %r" % e)
            return
        self._wire()
        try:
            self.sio.connect(self.base_url, headers={"Cookie": _cookie_header(s)},
                             transports=["websocket"], wait_timeout=20)
        except Exception as e:  # noqa: BLE001
            self.errors.append("connect: %r" % e)
            return
        self._join()
        while not self.stop_evt.is_set():
            time.sleep(0.2)
        try:
            self.sio.disconnect()
        except Exception:  # noqa: BLE001
            pass


def _pct(values, p):
    if not values:
        return float("nan")
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return values[k]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--clients", type=int, default=4)
    ap.add_argument("--duration", type=int, default=90, help="durée de mesure (s)")
    ap.add_argument("--config", default="config_test", help="valeur du paramètre CONFIG")
    ap.add_argument("--ramp", type=float, default=0.3, help="délai entre connexions (s)")
    args = ap.parse_args()

    stop_evt = threading.Event()
    clients = [Client(i, args.base_url, args.config, stop_evt) for i in range(args.clients)]

    print("[LOADTEST] %d clients -> %s (config=%s) pendant %ds"
          % (args.clients, args.base_url, args.config, args.duration))
    for c in clients:
        c.start()
        time.sleep(args.ramp)

    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < args.duration:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    stop_evt.set()
    for c in clients:
        c.join(timeout=10)

    all_intervals = [x for c in clients for x in c.intervals]
    total_disc = sum(c.disconnects for c in clients)
    total_done = sum(c.games_done for c in clients)
    errs = [(c.uid, e) for c in clients for e in c.errors]

    print("\n==================== RÉSULTATS ====================")
    print("clients              : %d" % args.clients)
    print("frames mesurées      : %d" % len(all_intervals))
    print("parties terminées    : %d" % total_done)
    print("déconnexions         : %d" % total_disc)
    if all_intervals:
        print("intervalle state_pong (ms) : "
              "p50=%.0f  p95=%.0f  p99=%.0f  max=%.0f  (cible ~100)"
              % (_pct(all_intervals, 50) * 1000, _pct(all_intervals, 95) * 1000,
                 _pct(all_intervals, 99) * 1000, max(all_intervals) * 1000))
        print("intervalle moyen (ms): %.0f" % (statistics.fmean(all_intervals) * 1000))
    verdict_ok = all_intervals and _pct(all_intervals, 95) * 1000 < 150 and total_disc == 0
    print("verdict @%d clients   : %s" % (args.clients, "OK" if verdict_ok else "SATURÉ / instable"))
    if errs:
        print("\nerreurs (%d) :" % len(errs))
        for uid, e in errs[:20]:
            print("  %s : %s" % (uid, e))
    print("===================================================")
    sys.exit(0 if verdict_ok else 1)


if __name__ == "__main__":
    main()
