"""
Suivi de navigation SIMPLIFIÉ pour la plateforme expérimentale Overcooked.

Ce module enregistre, pour chaque participant, UNIQUEMENT :
  - les pages visitées (dans l'ordre chronologique) ;
  - le nombre de visites de chaque page ;
  - la durée de chaque visite ;
  - le type de navigation : entrée / avant / arrière / rechargement ;
  - un résumé agrégé des navigations (par page et au global).

Mesure de la durée — CLIENT-AUTORITAIRE avec repli serveur
----------------------------------------------------------
La durée d'une visite est MESURÉE dans le navigateur (static/js/page-tracker.js)
et transmise par navigator.sendBeacon à la route /track/page, puis intégrée par
`ingest_client_event`. Chaque rendu de page reçoit un `view_token` qui relie la
vue serveur aux relevés client. Tant qu'aucun relevé client n'est arrivé, la
durée est estimée côté serveur (écart entre deux rendus) : aucune donnée n'est
jamais perdue. Les relevés client sont cumulatifs et idempotents (le serveur
conserve le maximum), si bien qu'un heartbeat, un passage en arrière-plan ou une
fermeture brutale suffisent à finaliser la dernière page.

Classification de la navigation
-------------------------------
Le type avant/arrière/rechargement est RECONSTRUIT côté serveur en simulant la
pile d'historique du navigateur à partir du seul ordre des pages rendues, puis
CORRIGÉ par la vérité-terrain navigateur quand elle est disponible
(performance navigation type + restauration bfcache + sens de la garde).

Interface publique (appelée depuis app.py) :
    - start_page(page_name)      -> view_token (None pour un marqueur interne)
    - ingest_client_event(event) -> bool
    - end_session()

Version: 5.0 - Suivi minimal (pages / visites / durée / navigation)
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging


class PageTracker:
    """Suivi minimal des pages visitées, de leur durée et de la navigation.

    Thread-safe : les relevés client (/track/page) arrivent dans des threads de
    requête Flask concurrents. Un unique RLock sérialise toute mutation de
    l'historique et toute sauvegarde.
    """

    # Méthode de mesure inscrite dans le fichier résultat (champ documentaire).
    TIMING_METHOD = "client_authoritative_v5_simplified"
    # Types considérés comme de vraies navigations de page.
    PAGE_NAV_TYPES = ("entry", "forward", "back", "reload")

    def __init__(self, participant_id: str, config_name: str, logger=None):
        self.participant_id = participant_id
        self.config_name = config_name
        self.logger = logger or logging.getLogger(__name__)

        self.current_page: Optional[str] = None
        self.current_start_time: Optional[str] = None
        self.page_history: List[Dict] = []

        self._data_lock = threading.RLock()
        self._view_counter = 0  # fabrique des view_token uniques

        self.trajectory_dir = Path(f"trajectories/{config_name}/{participant_id}")
        self.trajectory_dir.mkdir(parents=True, exist_ok=True)
        self.json_file = self.trajectory_dir / f"{participant_id}_suivis_passation.json"

        self.logger.info(
            f"[PAGE_TRACKER_INIT] uid={participant_id} | config={config_name} | "
            f"json_file={self.json_file}")

        self._load_existing_data()

    # ------------------------------------------------------------------ #
    # Enregistrement d'une nouvelle page (rendu serveur)
    # ------------------------------------------------------------------ #
    def _new_view_token(self) -> str:
        """Jeton de vue unique reliant un rendu serveur à ses relevés client."""
        self._view_counter += 1
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        return f"pv_{self._view_counter}_{stamp}"

    def start_page(self, page_name: str) -> Optional[str]:
        """Enregistre le début d'une nouvelle page et renvoie son `view_token`.

        Les marqueurs internes (ex. "[START_GAME] ...") ne sont PAS des pages :
        ils sont ignorés et renvoient None (aucun jeton, aucune entrée créée).
        """
        if not page_name or page_name.startswith('['):
            return None

        with self._data_lock:
            now = datetime.now().isoformat()

            # Finaliser la page précédente (repli serveur si pas de relevé client).
            if self.current_page and self.current_start_time:
                self._end_current_page(now)

            view_token = self._new_view_token()
            self.current_page = page_name
            self.current_start_time = now

            self.page_history.append({
                "page": page_name,
                "start_time": now,
                "end_time": None,
                # Durée AUTORITAIRE (client exact si dispo, sinon repli serveur).
                "duration_sec": None,
                "active_duration_sec": None,
                "timing_source": "server",
                "view_token": view_token,
                # Mesure serveur brute (diagnostic / repli).
                "server_start_time": now,
                "server_end_time": None,
                "server_duration_sec": None,
                # Détail des relevés navigateur (None tant qu'aucun reçu).
                "client": None,
            })

            self._compute_navigation()

            last = self.page_history[-1]
            self.logger.info(
                f"[PAGE_TRACKER_PAGE_START] uid={self.participant_id} | page={page_name} | "
                f"nav={last.get('navigation_type')} | visit_index={last.get('visit_index')} | "
                f"view_token={view_token}")

            self._save_to_json()
            return view_token

    def _end_current_page(self, end_time: str):
        """Finalise la page courante côté SERVEUR (repli).

        Écrit toujours la durée serveur (diagnostic), mais ne remplace la durée
        publique QUE si aucun relevé client exact n'a déjà finalisé la vue
        (timing_source != "client") : la mesure navigateur reste autoritaire.
        """
        entry = None
        for e in reversed(self.page_history):
            if e.get('page') == self.current_page:
                entry = e
                break
        if entry is None:
            return

        try:
            start_dt = datetime.fromisoformat(
                entry.get('server_start_time') or entry['start_time'])
            server_duration = round(
                max(0.0, (datetime.fromisoformat(end_time) - start_dt).total_seconds()), 2)
        except (ValueError, KeyError):
            server_duration = 0.0

        entry['server_end_time'] = end_time
        entry['server_duration_sec'] = server_duration

        if entry.get('timing_source') != 'client':
            entry['end_time'] = end_time
            entry['duration_sec'] = server_duration
            self.logger.info(
                f"[PAGE_TRACKER_PAGE_END] uid={self.participant_id} | "
                f"page={self.current_page} | duration={server_duration:.2f}s (server)")

    # ------------------------------------------------------------------ #
    # Classification de la navigation (entrée / avant / arrière / rechargement)
    # ------------------------------------------------------------------ #
    def _compute_navigation(self):
        """Classe chaque visite en entry / forward / back / reload.

        Reconstruit la pile d'historique du navigateur (back/forward stack avec
        curseur) à partir du seul ordre des pages, puis corrige avec la vérité-
        terrain client quand elle existe. Déterministe et idempotent (peut être
        rappelée à chaque sauvegarde sans effet de bord).

        Champs écrits sur chaque entrée : navigation_type, navigation_detail,
        visit_index, is_revisit, navigation_source.
        """
        nav_stack: List[str] = []   # pages formant la pile du navigateur
        cursor = -1                 # index de la page courante dans nav_stack
        visit_counts: Dict[str, int] = {}

        for entry in self.page_history:
            page = entry.get('page', '')

            if cursor < 0:
                nav_type, detail = 'entry', 'session_start'
                nav_stack = [page]
                cursor = 0
            elif nav_stack[cursor] == page:
                nav_type, detail = 'reload', 'reload'
            elif cursor > 0 and nav_stack[cursor - 1] == page:
                nav_type, detail = 'back', 'browser_back'
                cursor -= 1
            elif cursor < len(nav_stack) - 1 and nav_stack[cursor + 1] == page:
                nav_type, detail = 'forward', 'browser_forward'
                cursor += 1
            else:
                # Nouvelle progression : tronquer l'avant de la pile et empiler
                # (comportement d'un vrai navigateur).
                nav_type = 'forward'
                detail = 'revisit' if page in visit_counts else 'new_page'
                nav_stack = nav_stack[:cursor + 1] + [page]
                cursor = len(nav_stack) - 1

            visit_counts[page] = visit_counts.get(page, 0) + 1
            entry['navigation_type'] = nav_type
            entry['navigation_detail'] = detail
            entry['visit_index'] = visit_counts[page]
            entry['is_revisit'] = visit_counts[page] > 1
            entry['navigation_source'] = 'reconstructed'

            # Surcouche CLIENT : la vérité-terrain navigateur corrige la
            # reconstruction là où un relevé existe.
            self._apply_client_navigation(entry)

    def _apply_client_navigation(self, entry: Dict):
        """Corrige la reconstruction avec la vérité-terrain navigateur
        (perf_nav_type + restauration bfcache + sens de la garde)."""
        c = entry.get('client')
        nt = c.get('perf_nav_type') if c else None
        if not nt or entry.get('navigation_type') == 'entry':
            return  # 1re page de session : rester "entry"

        entry['navigation_source'] = 'client'
        if nt == 'reload':
            entry['navigation_type'] = 'reload'
            entry['navigation_detail'] = 'reload'
        elif nt == 'back_forward':
            # L'API ne distingue pas back/forward ; le sens de la garde fait foi.
            gd = c.get('guard_dir')
            if gd in ('back', 'forward'):
                entry['navigation_type'] = gd
            elif entry.get('navigation_type') not in ('back', 'forward'):
                entry['navigation_type'] = 'back'
            entry['navigation_detail'] = 'browser_back_forward'
        elif nt == 'navigate':
            if entry.get('navigation_type') not in ('back', 'forward'):
                entry['navigation_type'] = 'forward'
            if entry.get('navigation_detail') in (None, 'reload'):
                entry['navigation_detail'] = 'new_page'

        if c.get('guard_redirect'):
            detail = entry.get('navigation_detail') or ''
            if 'guard_redirect' not in detail:
                entry['navigation_detail'] = (detail + '+guard_redirect') if detail else 'guard_redirect'

    def _build_navigation_summary(self):
        """Agrège les navigations par page et au global (le « résumé »).

        Returns:
            (summary, totals) où
              - summary : {page: {visit_count, entry_count, forward_count,
                back_count, reload_count, total_duration_sec, first_seen,
                last_seen}} ;
              - totals  : compteurs globaux (pages, entry, forward, back, reload,
                distinct_pages, total_page_time_sec).
        """
        summary: Dict[str, Dict] = {}
        totals = {
            "pages": 0, "entry": 0, "forward": 0, "back": 0, "reload": 0,
            "distinct_pages": 0, "total_page_time_sec": 0.0,
        }

        for entry in self.page_history:
            nav = entry.get('navigation_type')
            if nav not in self.PAGE_NAV_TYPES:
                continue

            page = entry.get('page')
            start_time = entry.get('start_time')
            duration = entry.get('duration_sec') or 0

            stats = summary.setdefault(page, {
                "visit_count": 0, "entry_count": 0, "forward_count": 0,
                "back_count": 0, "reload_count": 0, "total_duration_sec": 0.0,
                "first_seen": start_time, "last_seen": start_time,
            })
            stats["visit_count"] += 1
            stats[f"{nav}_count"] += 1
            stats["total_duration_sec"] = round(stats["total_duration_sec"] + duration, 2)
            stats["last_seen"] = start_time

            totals["pages"] += 1
            totals[nav] += 1
            totals["total_page_time_sec"] = round(totals["total_page_time_sec"] + duration, 2)

        totals["distinct_pages"] = len(summary)
        return summary, totals

    # ------------------------------------------------------------------ #
    # Ingestion des relevés CLIENT (durée exacte + navigation vérité-terrain)
    # ------------------------------------------------------------------ #
    def ingest_client_event(self, event: Dict) -> bool:
        """Intègre un relevé client (enter / heartbeat / exit) émis par
        static/js/page-tracker.js via /track/page.

        Rattaché à sa vue serveur par le view_token ; à défaut par nom de page ;
        en dernier recours une entrée est SYNTHÉTISÉE (aucune perte de donnée).
        Cumulatif et idempotent : les durées ne font que croître (max conservé),
        si bien qu'un heartbeat ou une fermeture brutale suffit à finaliser.
        """
        if not isinstance(event, dict):
            return False
        with self._data_lock:
            try:
                entry = self._find_entry_for_client(event)
                synthesized = False
                if entry is None:
                    entry = self._synthesize_client_entry(event)
                    self.page_history.append(entry)
                    synthesized = True

                self._apply_client_event(entry, event)
                self._save_to_json()

                c = entry.get('client') or {}
                self.logger.info(
                    f"[PAGE_TRACKER_CLIENT_EVENT] uid={self.participant_id} | "
                    f"type={event.get('type')} | page={entry.get('page')} | "
                    f"token={event.get('token')} | wall_ms={c.get('wall_ms')} | "
                    f"nav={entry.get('navigation_type')} | perf={c.get('perf_nav_type')}"
                    + (" | SYNTH" if synthesized else ""))
                return True
            except Exception as e:
                self.logger.error(
                    f"[PAGE_TRACKER_CLIENT_EVENT_ERROR] uid={self.participant_id} | "
                    f"error={str(e)}", exc_info=True)
                return False

    def _find_entry_for_client(self, event: Dict) -> Optional[Dict]:
        """Retrouve l'entrée de page à enrichir avec un relevé client."""
        token = event.get('token')
        if token:
            for e in self.page_history:
                if e.get('view_token') == token:
                    return e
        # Repli : dernière page de même nom (priorité à celle sans relevé client).
        page = event.get('page')
        fallback = None
        for e in reversed(self.page_history):
            if page and self._same_logical_page(e.get('page', ''), page):
                if e.get('client') is None:
                    return e
                if fallback is None:
                    fallback = e
        return fallback

    @staticmethod
    def _same_logical_page(a: str, b: str) -> bool:
        """Égalité « souple » de pages : dernier segment d'URL, sans query
        string, insensible à la casse (repli si le view_token manque)."""
        if not a or not b:
            return False
        na = a.split('?')[0].rstrip('/').split('/')[-1].lower()
        nb = b.split('?')[0].rstrip('/').split('/')[-1].lower()
        return na == nb

    def _synthesize_client_entry(self, event: Dict) -> Dict:
        """Crée une entrée depuis un relevé client orphelin (vue serveur
        introuvable), pour ne jamais perdre de donnée de suivi."""
        page = event.get('page') or 'UNKNOWN'
        start = event.get('enter_ts') or datetime.now().isoformat()
        self.logger.warning(
            f"[PAGE_TRACKER_CLIENT_ORPHAN] uid={self.participant_id} | page={page} | "
            f"token={event.get('token')} : entrée synthétisée (vue serveur introuvable)")
        return {
            "page": page,
            "start_time": start,
            "end_time": None,
            "duration_sec": None,
            "active_duration_sec": None,
            "timing_source": "server",
            "view_token": event.get('token'),
            "server_start_time": start,
            "server_end_time": None,
            "server_duration_sec": None,
            "client": None,
            "synthesized_from_client": True,
        }

    def _apply_client_event(self, entry: Dict, event: Dict):
        """Fusionne un relevé client (cumulatif, idempotent) et promeut la mesure
        navigateur en durée autoritaire."""
        c = entry.get('client')
        if c is None:
            c = {}
            entry['client'] = c

        # Durées cumulatives : conserver le maximum reçu.
        wall_increased = False
        for k in ('wall_ms', 'active_ms', 'hidden_ms'):
            v = self._to_float(event.get(k))
            if v is None:
                continue
            prev = c.get(k)
            if prev is None or v >= prev:
                if k == 'wall_ms' and (prev is None or v > prev):
                    wall_increased = True
                c[k] = round(v, 2)

        # Métadonnées utiles à la navigation + diagnostic.
        for k in ('perf_nav_type', 'guard_dir', 'exit_reason'):
            if event.get(k):
                c[k] = event.get(k)
        c['persisted'] = bool(event.get('persisted')) or c.get('persisted', False)
        c['guard_redirect'] = bool(event.get('guard_redirect')) or c.get('guard_redirect', False)
        c['visibility_changes'] = max(c.get('visibility_changes', 0),
                                      self._to_int(event.get('visibility_changes')) or 0)
        c['heartbeats'] = max(c.get('heartbeats', 0),
                              self._to_int(event.get('heartbeats')) or 0)
        c['last_event_type'] = event.get('type')
        c['received_at'] = datetime.now().isoformat()

        # Horodatage de sortie : dernier beacon qui fait progresser la durée, ou
        # tout beacon « exit ».
        client_now = event.get('client_now')
        if client_now and (wall_increased or event.get('type') == 'exit'):
            c['exit_ts'] = client_now

        # Promotion en valeurs publiques autoritaires.
        wall = c.get('wall_ms')
        if wall is not None:
            entry['duration_sec'] = round(wall / 1000.0, 2)
            entry['active_duration_sec'] = round((c.get('active_ms') or 0) / 1000.0, 2)
            entry['timing_source'] = 'client'
            if c.get('exit_ts'):
                entry['end_time'] = c['exit_ts']

    @staticmethod
    def _to_float(v) -> Optional[float]:
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(v) -> Optional[int]:
        try:
            return None if v is None else int(v)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ #
    # Sérialisation
    # ------------------------------------------------------------------ #
    def _visits_view(self) -> List[Dict]:
        """Liste chronologique compacte des visites (lecture humaine)."""
        return [{
            "page": e.get('page'),
            "start_time": e.get('start_time'),
            "end_time": e.get('end_time'),
            "duration_sec": e.get('duration_sec'),
            "active_duration_sec": e.get('active_duration_sec'),
            "timing_source": e.get('timing_source'),
            "navigation_type": e.get('navigation_type'),
            "navigation_detail": e.get('navigation_detail'),
            "navigation_source": e.get('navigation_source'),
            "visit_index": e.get('visit_index'),
            "is_revisit": e.get('is_revisit'),
        } for e in self.page_history]

    def _timing_coverage(self) -> Dict:
        """Part des pages dont la durée provient d'une mesure client EXACTE vs
        d'un repli serveur (contrôle qualité en tête de fichier)."""
        total = client = server = pending = 0
        for e in self.page_history:
            total += 1
            if e.get('timing_source') == 'client':
                client += 1
            elif e.get('duration_sec') is not None:
                server += 1
            else:
                pending += 1
        return {"total_pages": total, "client": client, "server": server, "pending": pending}

    def _save_to_json(self):
        """Sauvegarde thread-safe et ATOMIQUE (tmp + fsync + os.replace).

        Le fichier contient :
            - participant_id / config_name / timing_method : métadonnées ;
            - timing_coverage : part client exact vs repli serveur ;
            - navigation_totals : compteurs globaux (avant/arrière/reload) ;
            - navigation_summary : agrégats par page (nb visites, nb reloads,
              nb retours, temps total...) ;
            - visits : déroulé chronologique de chaque visite ;
            - _raw_history : historique brut (rechargement fidèle après
              redémarrage du serveur).
        """
        with self._data_lock:
            try:
                self._compute_navigation()
                summary, totals = self._build_navigation_summary()
                coverage = self._timing_coverage()

                output = {
                    "participant_id": self.participant_id,
                    "config_name": self.config_name,
                    "timing_method": self.TIMING_METHOD,
                    "timing_coverage": coverage,
                    "navigation_totals": totals,
                    "navigation_summary": summary,
                    "visits": self._visits_view(),
                    "_raw_history": self.page_history,
                }

                tmp_file = self.json_file.parent / (self.json_file.name + f".{os.getpid()}.tmp")
                try:
                    with open(tmp_file, 'w', encoding='utf-8') as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_file, self.json_file)
                except Exception:
                    if tmp_file.exists():
                        try:
                            tmp_file.unlink()
                        except OSError:
                            pass
                    raise

                self.logger.info(
                    f"[PAGE_TRACKER_SAVE] uid={self.participant_id} | "
                    f"visits={len(self.page_history)} | "
                    f"client_timed={coverage['client']}/{coverage['total_pages']} | "
                    f"nav(fwd/back/reload)={totals['forward']}/{totals['back']}/{totals['reload']}")
            except Exception as e:
                self.logger.error(
                    f"[PAGE_TRACKER_SAVE_ERROR] uid={self.participant_id} | "
                    f"file={self.json_file.name} | error={str(e)}", exc_info=True)

    def _load_existing_data(self):
        """Recharge l'historique brut d'un fichier existant (reprise après un
        redémarrage du serveur) et reprend la dernière page non terminée."""
        if not self.json_file.exists():
            return
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Seul le format enrichi (dict avec `_raw_history`) est restauré.
            self.page_history = data.get('_raw_history') or [] if isinstance(data, dict) else []

            self._compute_navigation()

            if self.page_history:
                last = self.page_history[-1]
                if not last.get('end_time') and not last.get('page', '').startswith('['):
                    self.current_page = last.get('page')
                    self.current_start_time = last.get('start_time')
        except Exception as e:
            self.logger.error(
                f"[PAGE_TRACKER_LOAD_ERROR] uid={self.participant_id} | error={str(e)}")
            self.page_history = []

    # ------------------------------------------------------------------ #
    # Fin de session
    # ------------------------------------------------------------------ #
    def end_session(self):
        """Termine la session de suivi.

        Avec le timing client-autoritaire, la dernière page est en général déjà
        finalisée par le beacon de sortie (pagehide/hidden). Ce repli serveur
        garantit une durée même sans relevé client.
        """
        with self._data_lock:
            now = datetime.now().isoformat()
            if self.current_page and self.current_start_time:
                self._end_current_page(now)
            self._save_to_json()
            self.logger.info(
                f"[PAGE_TRACKER_END] uid={self.participant_id} | session terminée")
