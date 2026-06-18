"""
Système de suivi temporel optimisé pour la plateforme expérimentale Overcooked.

Version optimisée pour usage multi-joueurs avec surveillance périodique
et calcul automatique des durées d'activités.

Suivi de navigation (v3.0)
--------------------------
En plus de l'ordre des pages et du temps passé sur chacune, le tracker
classe chaque chargement de page réelle selon le type de navigation du
participant :

    - "entry"    : toute première page de la session ;
    - "forward"  : progression vers une page (nouvelle page, ou bouton
                   « suivant » du navigateur) ;
    - "back"     : retour arrière vers la page précédente de l'historique ;
    - "reload"   : rechargement de la page courante (même page consécutive).

La classification serveur est calculée en simulant la pile d'historique du
navigateur (back/forward stack avec un curseur), à partir du seul ordre des
pages réelles dans `page_history`. Elle est déterministe et survit à un
redémarrage du serveur. Les marqueurs internes [ACTIVITÉ] (détection de
fichiers) et [START_GAME] (événement intra-page) ne sont pas des navigations
et sont étiquetés respectivement "activity" et "event".

Mesure EXACTE côté client (v4.0)
--------------------------------
Le temps passé sur une page et son type de navigation sont désormais MESURÉS
dans le navigateur (et non plus seulement déduits du moment où Flask rend la
route). Le script static/js/page-tracker.js, injecté dans chaque page du
parcours, transmet par `navigator.sendBeacon` des relevés horodatés à
l'horloge monotone `performance.now()` :

    - wall_ms   : temps « mur » réel sur la page (de l'affichage à la sortie) ;
    - active_ms : temps « actif » (document visible uniquement, API Page
                  Visibility) — exclut l'onglet masqué / la veille machine ;
    - perf_nav_type / persisted : type de navigation vérité-terrain
                  (navigate / reload / back_forward, + restauration bfcache).

Le serveur relie chaque relevé à la page rendue via un `view_token` (jeton de
vue généré au rendu et injecté dans la page). Lorsqu'un relevé client est
disponible, `duration_sec` et `end_time` deviennent les valeurs CLIENT exactes
(`timing_source = "client"`) ; sinon on retombe sur la mesure serveur
(`timing_source = "server"`) — aucune perte de données (cf. mémoire
« trial-data-must-always-be-saved »). Les relevés sont idempotents et
cumulatifs (le serveur conserve le maximum) : une fermeture brutale, un
heartbeat ou un passage en arrière-plan suffisent à finaliser la dernière
page, même hors de la route /goodbye.

Le modèle de timing est CLIENT-AUTORITAIRE avec filet serveur. Tous les détails
client bruts sont conservés sous la clé `client` de chaque entrée de page.

Auteur: AI Assistant
Date: Septembre 2025 — màj juin 2026
Version: 4.0 - Mesure client-autoritaire (temps exact + navigation vérité-terrain)
"""

import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging


class PageTracker:
    """
    Gestionnaire de suivi temporel optimisé pour multi-joueurs.
    
    Fonctionnalités:
    - Surveillance périodique des fichiers (2 fois/seconde)
    - Calcul automatique des durées d'activités
    - Thread-safe pour usage concurrent
    - Évite les doublons
    """
    
    def __init__(self, participant_id: str, config_name: str, logger=None):
        """
        Initialise le tracker pour un participant donné.
        
        Args:
            participant_id: Identifiant unique du participant
            config_name: Nom de la configuration expérimentale
            logger: Instance de logger (utilise app.logger si fourni)
        """
        self.participant_id = participant_id
        self.config_name = config_name
        self.current_page = None
        self.current_start_time = None
        self.page_history: List[Dict] = []

        # Logger (utilise app.logger ou logger par défaut)
        self.logger = logger or logging.getLogger(__name__)

        # Configuration des chemins
        self.trajectory_dir = Path(f"trajectories/{config_name}/{participant_id}")
        self.trajectory_dir.mkdir(parents=True, exist_ok=True)
        self.json_file = self.trajectory_dir / f"{participant_id}_suivis_passation.json"

        # Système de surveillance optimisé
        self.processed_files = set()
        self._monitoring_active = False
        self._monitoring_thread = None
        self._thread_lock = threading.Lock()

        # Verrou de données : sérialise toute mutation de page_history et toute
        # sauvegarde. Indispensable car les relevés client (/track/page) arrivent
        # dans des threads de requête Flask concurrents au thread de surveillance
        # des fichiers. Réentrant (une méthode verrouillée peut en appeler une autre).
        self._data_lock = threading.RLock()

        # Compteur monotone pour fabriquer des view_token uniques (jeton de vue
        # reliant un rendu serveur aux relevés client correspondants).
        self._view_counter = 0
        
        self.logger.info(f"[PAGE_TRACKER_INIT] uid={participant_id} | config={config_name} | json_file={self.json_file}")
        
        # Charger les données existantes
        self._load_existing_data()
        self._scan_existing_files()
    
    def _scan_existing_files(self):
        """Scanne les fichiers existants au démarrage et les traite."""
        try:
            all_files = list(self.trajectory_dir.rglob("*.json"))
            self.logger.info(f"[PAGE_TRACKER_SCAN] uid={self.participant_id} | found={len(all_files)} files")
            
            for file_path in all_files:
                if file_path.name.endswith("_suivis_passation.json"):
                    continue
                
                file_path_str = str(file_path)
                # Au lieu de simplement marquer comme traité, traiter le fichier
                if file_path_str not in self.processed_files:
                    self._process_new_file(file_path_str)
                    self.processed_files.add(file_path_str)
                    self.logger.debug(f"[PAGE_TRACKER_FILE_PROCESSED] uid={self.participant_id} | file={file_path.name}")
                    
        except Exception as e:
            self.logger.error(f"[PAGE_TRACKER_SCAN_ERROR] uid={self.participant_id} | error={str(e)}")
            self.processed_files = set()
    
    def _classify_file_step_type(self, file_path: str) -> str:
        """Classification optimisée des types de fichiers."""
        filename = os.path.basename(file_path)
        
        # Correspondances rapides par mots-clés
        if "CONSENT.json" in filename:
            return "Consentement"
        elif "tutorial0.json" in filename:
            return "Premier Tutorial"
        elif "tutorial1.json" in filename:
            return "Deuxième Tutorial"
        elif "tutorial2.json" in filename:
            return "Troisième Tutorial"
        elif "_QVG.json" in filename:
            return "Questionnaire Jeux Vidéo"
        elif "_PTTA.json" in filename:
            return "Questionnaire PTTA"
        elif "GAbstractionP_fr.json" in filename:
            return "Questionnaire GAbstractionP (FR)"
        elif "preference.json" in filename:
            return "Questionnaire Préférence"
        elif "_QPT.json" in filename:
            return self._parse_qpt_filename(filename)
        elif "AAT_L.json" in filename:
            return self._parse_attl_filename(filename)
        elif "HOFFMAN.json" in filename:
            return self._parse_hoffman_filename(filename)
        elif "GAbstractionP.json" in filename:
            return self._parse_gabstractionp_filename(filename)
        elif self._is_game_session(filename):
            return self._parse_game_filename(filename)
        
        return "Activité"
    
    def _parse_qpt_filename(self, filename: str) -> str:
        """Parse les fichiers QPT pour extraire bloc/trial."""
        try:
            parts = filename.replace('_QPT.json', '').split('_')
            if len(parts) >= 3:
                bloc, trial = int(parts[-2]), int(parts[-1])
                return f"Questionnaire Agency - Bloc {bloc+1}, Essai {trial+1}"
        except (ValueError, IndexError):
            pass
        return "Questionnaire Agency"
    
    def _parse_attl_filename(self, filename: str) -> str:
        """Parse les fichiers ATTL pour extraire le bloc."""
        try:
            parts = filename.replace('AAT_L.json', '').split('_')
            if len(parts) >= 2:
                bloc = int(parts[-1])
                return f"Questionnaire ATTL - Bloc {bloc+1}"
        except (ValueError, IndexError):
            pass
        return "Questionnaire ATTL"
    
    def _parse_hoffman_filename(self, filename: str) -> str:
        """Parse les fichiers Hoffman pour extraire le bloc."""
        try:
            parts = filename.replace('HOFFMAN.json', '').split('_')
            if len(parts) >= 2:
                bloc = int(parts[-1])
                return f"Questionnaire Hoffman - Bloc {bloc+1}"
        except (ValueError, IndexError):
            pass
        return "Questionnaire Hoffman"
    
    def _parse_gabstractionp_filename(self, filename: str) -> str:
        """Parse les fichiers GAbstractionP pour extraire le bloc (si présent)."""
        try:
            parts = [p for p in filename.replace('GAbstractionP.json', '').split('_') if p]
            if parts:
                bloc = int(parts[-1])
                return f"Questionnaire GAbstractionP - Bloc {bloc+1}"
        except (ValueError, IndexError):
            pass
        return "Questionnaire GAbstractionP"

    def _parse_game_filename(self, filename: str) -> str:
        """Parse les fichiers de jeu pour extraire bloc/trial."""
        try:
            parts = filename.replace('.json', '').split('_')
            if len(parts) >= 3:
                bloc, trial = int(parts[-2]), int(parts[-1])
                return f"Jeu - Bloc {bloc+1}, Essai {trial+1}"
        except (ValueError, IndexError):
            pass
        return "Jeu"
    
    def _is_game_session(self, filename: str) -> bool:
        """Vérifie si c'est un fichier de session de jeu."""
        if not filename.endswith('.json'):
            return False
        
        base = filename.replace('.json', '')
        parts = base.split('_')
        
        return (len(parts) >= 3 and 
                parts[-2].isdigit() and 
                parts[-1].isdigit() and
                not any(keyword in filename for keyword in
                       ['QPT', 'AAT_L', 'HOFFMAN', 'GAbstractionP', 'preference', 'QVG', 'PTTA', 'tutorial']))
    
    def _infer_step_type_from_page(self, page_name: str) -> str:
        """Infère le type d'étape depuis le nom de la page."""
        page_lower = page_name.lower()
        
        # Détection des événements START_GAME
        if page_name.startswith('[START_GAME]'):
            return "Début partie effective"
        
        # Mapping optimisé
        page_mappings = {
            'index.html': "Page d'accueil",
            'instructions_recipe.html': "Instructions - Recettes",
            'tutorial.html': "Tutorial - Introduction",
            'planning.html': "Interface de jeu",
            'experience_video_games_en.html': "Page questionnaire Jeux Vidéo",
            'preference order_en.html': "Page questionnaire Préférence"
        }
        
        if page_name in page_mappings:
            return page_mappings[page_name]
        
        # Détection par mots-clés
        if 'tutorial_' in page_lower:
            condition = page_name.split('_')[1].split('.')[0].upper()
            return f"Tutorial - Condition {condition}"
        elif 'ptt_a' in page_lower:
            return "Page questionnaire PTTA"
        elif 'goodbye' in page_lower:
            return "Page de fin"
        
        return "Navigation"
    
    def _calculate_activity_duration(self, activity_entry: Dict) -> Optional[float]:
        """
        Calcule la durée d'une activité selon les règles du déroulement expérimental.
        
        Les durées [time needed] correspondent au temps passé selon les règles spécifiques :
        - Questionnaires : depuis leur page parente
        - Tutorials : enchaînement séquentiel
        - Jeux : depuis planning.html ou retour après QPT
        - QPT : depuis le début du jeu correspondant
        - ATTL : depuis le dernier QPT du bloc
        - Hoffman : depuis ATTL correspondant
        
        Returns:
            Durée en secondes ou None si pas applicable
        """
        page_name = activity_entry.get('page', '')
        filename = page_name.replace('[ACTIVITÉ] ', '')
        activity_time = datetime.fromisoformat(activity_entry['start_time'])
        
        # Skip CONSENT.json - pas de durée calculée
        if 'CONSENT.json' in filename:
            return None
        
        try:
            # Utiliser la logique spécifique pour chaque type d'activité
            duration = self._calculate_activity_duration_specific(activity_entry)
            if duration is not None:
                return max(0, duration)  # Éviter les durées négatives
            
            # Fallback : utiliser la page parente si applicable
            parent_page = self._get_parent_page_for_activity(filename)
            if parent_page:
                ref_entry = self._find_reference_page(parent_page)
                if ref_entry:
                    ref_time = datetime.fromisoformat(ref_entry['start_time'])
                    duration = (activity_time - ref_time).total_seconds()
                    return max(0, duration)
            
            return None
            
        except Exception as e:
            print(f"[{self.participant_id}] Erreur calcul durée pour {filename}: {e}")
            return None
    
    def _get_parent_page_for_activity(self, filename: str) -> Optional[str]:
        """
        Détermine la page parente d'une activité selon le déroulement expérimental.
        
        Args:
            filename: Nom du fichier d'activité (sans préfixe [ACTIVITÉ])
            
        Returns:
            Nom de la page parente ou None pour utiliser une référence spécifique
        """
        # Questionnaires avec pages dédiées
        if '_QVG.json' in filename:
            return 'experience_video_games_en.html'
        elif '_PTTA.json' in filename:
            return 'PTT_A_en.html'
        elif 'preference.json' in filename:
            return 'preference order_en.html'
        
        # Tutorials - enchaînement séquentiel depuis tutorial.html
        elif 'tutorial0.json' in filename:
            return 'tutorial.html'
        
        # Pour les autres activités dans les blocs, on utilise une logique spécifique
        return None
    
    def _calculate_activity_duration_specific(self, activity_entry: Dict) -> Optional[float]:
        """
        Calcule la durée spécifique d'une activité selon les règles [time needed].
        
        Chaque [time needed] représente le temps réel passé sur cette activité spécifique,
        calculé généralement depuis l'activité précédente dans la séquence.
        
        Returns:
            Durée en secondes ou None si pas applicable
        """
        page_name = activity_entry.get('page', '')
        filename = page_name.replace('[ACTIVITÉ] ', '')
        activity_time = datetime.fromisoformat(activity_entry['start_time'])
        
        try:
            # Cas spéciaux pour les enchaînements dans les tutorials
            if 'tutorial1.json' in filename:
                # [time needed] depuis tutorial0.json
                ref_start = self._find_activity_start_time('[ACTIVITÉ] tutorial0.json')
                if ref_start:
                    ref_time = datetime.fromisoformat(ref_start)
                    return (activity_time - ref_time).total_seconds()
                    
            elif 'tutorial2.json' in filename:
                # [time needed] depuis tutorial1.json
                ref_start = self._find_activity_start_time('[ACTIVITÉ] tutorial1.json')
                if ref_start:
                    ref_time = datetime.fromisoformat(ref_start)
                    return (activity_time - ref_time).total_seconds()
            
            # Activités dans les blocs de jeu - calcul séquentiel depuis l'activité précédente
            elif self._is_game_session(filename):
                # Chercher d'abord le START_GAME correspondant à ce jeu
                parts = filename.replace('.json', '').split('_')
                if len(parts) >= 3:
                    bloc = parts[-2]
                    trial = parts[-1]
                    start_game_event = f'[START_GAME] Bloc {bloc}, Essai {trial}'
                    ref_start = self._find_activity_start_time(start_game_event, use_prefix=True)
                    
                    if ref_start:
                        # Si START_GAME existe, la durée du jeu commence à partir de là
                        ref_time = datetime.fromisoformat(ref_start)
                        return (activity_time - ref_time).total_seconds()
                
                # Fallback sur l'ancienne logique si pas de START_GAME
                if self._is_first_trial_of_block(filename):
                    # Premier essai du bloc [time needed] : depuis planning.html
                    ref_entry = self._find_reference_page('planning.html')
                    if ref_entry:
                        ref_time = datetime.fromisoformat(ref_entry['start_time'])
                        return (activity_time - ref_time).total_seconds()
                else:
                    # Essais suivants [time needed] : depuis le retour à planning.html après le QPT précédent
                    return self._calculate_sequential_game_duration(filename, activity_time)
            
            elif '_QPT.json' in filename:
                # QPT [time needed] : depuis le début du jeu correspondant
                # Priorité : chercher le START_GAME correspondant, sinon le fichier de jeu
                parts = filename.replace('_QPT.json', '').split('_')
                if len(parts) >= 3:
                    bloc = parts[-2]
                    trial = parts[-1]
                    start_game_event = f'[START_GAME] Bloc {bloc}, Essai {trial}'
                    ref_start = self._find_activity_start_time(start_game_event, use_prefix=True)
                    
                    # Fallback sur le fichier de jeu si pas de START_GAME
                    if not ref_start:
                        game_filename = filename.replace('_QPT.json', '.json')
                        ref_start = self._find_activity_start_time(f'[ACTIVITÉ] {game_filename}')
                    
                    if ref_start:
                        ref_time = datetime.fromisoformat(ref_start)
                        return (activity_time - ref_time).total_seconds()
            
            elif 'AAT_L.json' in filename:
                # ATTL [time needed] : depuis le dernier QPT du bloc
                last_qpt_start = self._find_last_qpt_start_for_bloc(filename)
                if last_qpt_start:
                    ref_time = datetime.fromisoformat(last_qpt_start)
                    return (activity_time - ref_time).total_seconds()
            
            elif 'HOFFMAN.json' in filename:
                # Hoffman [time needed] : depuis ATTL correspondant
                attl_filename = filename.replace('HOFFMAN.json', 'AAT_L.json')
                ref_start = self._find_activity_start_time(f'[ACTIVITÉ] {attl_filename}')
                if ref_start:
                    ref_time = datetime.fromisoformat(ref_start)
                    return (activity_time - ref_time).total_seconds()

            elif 'GAbstractionP.json' in filename:
                # GAbstractionP [time needed] : depuis Hoffman correspondant
                hoffman_filename = filename.replace('GAbstractionP.json', 'HOFFMAN.json')
                ref_start = self._find_activity_start_time(f'[ACTIVITÉ] {hoffman_filename}')
                if ref_start:
                    ref_time = datetime.fromisoformat(ref_start)
                    return (activity_time - ref_time).total_seconds()

            return None
            
        except Exception as e:
            print(f"[{self.participant_id}] Erreur calcul durée spécifique pour {filename}: {e}")
            return None
    
    def _calculate_sequential_game_duration(self, filename: str, activity_time: datetime) -> Optional[float]:
        """
        Calcule la durée d'un essai de jeu depuis l'événement précédent approprié.
        """
        try:
            parts = filename.replace('.json', '').split('_')
            if len(parts) >= 3:
                participant, bloc, trial = parts[0], parts[1], int(parts[2])
                
                if trial > 0:
                    # Pour les essais après le premier, trouver le dernier planning.html avant ce jeu
                    planning_before_this_game = None
                    for entry in reversed(self.page_history):
                        entry_time = datetime.fromisoformat(entry['start_time'])
                        if entry_time < activity_time and entry['page'] == 'planning.html':
                            planning_before_this_game = entry
                            break
                    
                    if planning_before_this_game:
                        ref_time = datetime.fromisoformat(planning_before_this_game['start_time'])
                        return (activity_time - ref_time).total_seconds()
            
            return None
        except Exception as e:
            print(f"[{self.participant_id}] Erreur calcul durée jeu séquentiel: {e}")
            return None
    
    def _is_first_trial_of_block(self, filename: str) -> bool:
        """Vérifie si c'est le premier essai d'un bloc (trial 0)."""
        try:
            if self._is_game_session(filename):
                parts = filename.replace('.json', '').split('_')
                if len(parts) >= 3:
                    trial = int(parts[-1])
                    return trial == 0
        except:
            pass
        return False
    
    def _find_last_qpt_start_for_bloc(self, attl_filename: str) -> Optional[str]:
        """Trouve le start_time du dernier QPT d'un bloc pour calculer la durée ATTL."""
        try:
            # Extraire participant_bloc du nom ATTL
            parts = attl_filename.replace('AAT_L.json', '').split('_')
            if len(parts) >= 2:
                participant, bloc = parts[0], parts[1]
                
                # Chercher le dernier QPT de ce bloc dans l'historique
                # (cherche en ordre inverse pour trouver le plus récent)
                for entry in reversed(self.page_history):
                    page = entry.get('page', '')
                    if f'{participant}_{bloc}_' in page and '_QPT.json' in page:
                        return entry.get('start_time')
            
            return None
        except Exception as e:
            print(f"[{self.participant_id}] Erreur recherche QPT start pour {attl_filename}: {e}")
            return None
    
    def _new_view_token(self) -> str:
        """Fabrique un jeton de vue unique pour relier un rendu serveur aux
        relevés client correspondants (cf. ingest_client_event)."""
        self._view_counter += 1
        # Horodatage + compteur : unique au sein d'un même participant, lisible.
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        return f"pv_{self._view_counter}_{stamp}"

    def start_page(self, page_name: str) -> Optional[str]:
        """Enregistre le début d'une nouvelle page (rendu serveur).

        Pour une vraie page du parcours, génère et renvoie un `view_token` : le
        serveur l'injecte dans la page (window.PAGE_TRACK.token) pour que les
        relevés client `sendBeacon` se rattachent EXACTEMENT à cette vue. Les
        marqueurs internes ([START_GAME]) ne reçoivent pas de jeton et renvoient
        None.

        Returns:
            Le view_token de la page, ou None pour un marqueur interne.
        """
        with self._data_lock:
            current_time = datetime.now().isoformat()

            # Terminer la page précédente (mesure serveur, repli si pas de client).
            previous_page = self.current_page
            if self.current_page and self.current_start_time:
                self._end_current_page(current_time)

            is_marker = page_name.startswith('[')
            view_token = None if is_marker else self._new_view_token()

            # Commencer la nouvelle page
            self.current_page = page_name
            self.current_start_time = current_time

            step_type = self._infer_step_type_from_page(page_name)

            page_entry = {
                "page": page_name,
                "step_type": step_type,
                "start_time": current_time,
                "end_time": None,
                "duration_sec": None,
                # Provenance du timing : "server" tant qu'aucun relevé client
                # n'est arrivé ; bascule à "client" dans _apply_client_event.
                "timing_source": None if is_marker else "server",
                # Jeton de vue (clé de rattachement des beacons client).
                "view_token": view_token,
                # Mesure serveur conservée à part (diagnostic / repli).
                "server_start_time": current_time,
                "server_end_time": None,
                "server_duration_sec": None,
            }
            self.page_history.append(page_entry)

            # Classifier la navigation (avant / arrière / reload) pour cette page.
            self._compute_navigation()

            # Log la transition de page (avec le type de navigation détecté).
            self.logger.info(
                f"[PAGE_TRACKER_PAGE_START] uid={self.participant_id} | page={page_name} | "
                f"step_type={step_type} | nav={page_entry.get('navigation_type')} | "
                f"detail={page_entry.get('navigation_detail')} | "
                f"visit_index={page_entry.get('visit_index')} | "
                f"view_token={view_token} | previous_page={previous_page}")

            # Démarrer la surveillance si pas déjà active
            self.start_monitoring()

            self._save_to_json()
            return view_token
    
    def _end_current_page(self, end_time: str):
        """Termine la page courante côté SERVEUR (repli).

        Calcule la durée « serveur » (rendu de la page suivante moins rendu de
        la page courante) et l'écrit dans les champs diagnostic server_*. Ne
        remplace `end_time`/`duration_sec` publics QUE si aucun relevé client
        exact n'a déjà finalisé cette vue (timing_source != "client"). Ainsi la
        mesure client reste autoritaire (cf. ingest_client_event).
        """
        if not self.page_history:
            return

        # Cibler la dernière occurrence de la page courante (revisites possibles),
        # qu'elle ait déjà été finalisée par le client ou non.
        last_page_entry = None
        for entry in reversed(self.page_history):
            if entry.get('page', '').startswith('[ACTIVITÉ]'):
                continue
            if entry.get('page') == self.current_page:
                last_page_entry = entry
                break

        if not last_page_entry:
            return

        # Durée serveur (toujours renseignée, à titre diagnostic).
        try:
            start_dt = datetime.fromisoformat(last_page_entry['server_start_time']
                                              if last_page_entry.get('server_start_time')
                                              else last_page_entry['start_time'])
            end_dt = datetime.fromisoformat(end_time)
            server_duration = round(max(0, (end_dt - start_dt).total_seconds()), 2)
        except (ValueError, KeyError) as e:
            self.logger.error(
                f"[PAGE_TRACKER_PAGE_DURATION_ERROR] uid={self.participant_id} | "
                f"page={self.current_page} | error={str(e)}")
            server_duration = 0

        last_page_entry['server_end_time'] = end_time
        last_page_entry['server_duration_sec'] = server_duration

        # Valeurs publiques : ne pas écraser une finalisation client exacte.
        if last_page_entry.get('timing_source') == 'client':
            self.logger.info(
                f"[PAGE_TRACKER_PAGE_END] uid={self.participant_id} | page={self.current_page} | "
                f"server_duration={server_duration:.2f}s (client autoritaire conservé: "
                f"{last_page_entry.get('duration_sec')}s)")
        else:
            last_page_entry['end_time'] = end_time
            last_page_entry['duration_sec'] = server_duration
            self.logger.info(
                f"[PAGE_TRACKER_PAGE_END] uid={self.participant_id} | page={self.current_page} | "
                f"duration={server_duration:.2f}s (server)")
    
    def _find_activity_start_time(self, activity_name: str, use_prefix: bool = False) -> Optional[str]:
        """Retourne le start_time d'une activité spécifique.
        
        Args:
            activity_name: Nom exact ou préfixe de l'activité
            use_prefix: Si True, cherche par préfixe (pour START_GAME avec trigger variable)
        """
        for entry in self.page_history:
            page = entry.get('page', '')
            if use_prefix:
                if page.startswith(activity_name):
                    return entry.get('start_time')
            else:
                if page == activity_name:
                    return entry.get('start_time')
        return None
    
    def _find_reference_page(self, page_name: str) -> Optional[Dict]:
        """Trouve une page de référence dans l'historique."""
        for entry in reversed(self.page_history):
            if entry.get('page') == page_name:
                return entry
        return None
    
    def _periodic_file_monitoring(self):
        """Thread de surveillance périodique des fichiers."""
        while self._monitoring_active:
            try:
                # Surveiller les nouveaux fichiers en permanence
                self._check_for_new_files()
                
                time.sleep(0.5)  # 2 fois par seconde
            except Exception as e:
                print(f"[{self.participant_id}] Erreur monitoring: {e}")
                time.sleep(1)
    
    def _check_for_new_files(self):
        """Vérifie les nouveaux fichiers et les traite."""
        try:
            all_files = list(self.trajectory_dir.rglob("*.json"))
            
            for file_path in all_files:
                if file_path.name.endswith("_suivis_passation.json"):
                    continue
                
                file_path_str = str(file_path)
                
                if file_path_str not in self.processed_files:
                    self._process_new_file(file_path_str)
                    self.processed_files.add(file_path_str)
                    
        except Exception as e:
            print(f"[{self.participant_id}] Erreur vérification fichiers: {e}")
    
    def _process_new_file(self, file_path_str: str):
        """Traite un nouveau fichier détecté.

        Verrouillé : la détection de fichiers tourne dans un thread dédié,
        concurrent aux relevés client (/track/page) qui mutent aussi page_history.
        """
        with self._data_lock:
            try:
                file_timestamp = os.path.getmtime(file_path_str)
                activity_time = datetime.fromtimestamp(file_timestamp).isoformat()
                step_type = self._classify_file_step_type(file_path_str)
                filename = os.path.basename(file_path_str)

                # Idempotence : ne pas réinsérer une activité déjà enregistrée
                # (ex. après rechargement de l'historique au redémarrage du serveur).
                activity_page = f"[ACTIVITÉ] {filename}"
                if any(e.get('page') == activity_page for e in self.page_history):
                    return

                # Déterminer la page parente de cette activité
                parent_page = self._determine_parent_page_for_file(filename)

                # Si on n'est pas sur la bonne page parente, ne pas terminer la page courante
                # (l'activité sera associée à sa vraie page parente dans l'organisation finale)

                # Créer l'entrée d'activité
                activity_entry = {
                    "page": f"[ACTIVITÉ] {filename}",
                    "step_type": step_type,
                    "start_time": activity_time,
                    "end_time": activity_time,
                    "duration_sec": 0,
                    "parent_page": parent_page  # Info pour l'organisation
                }

                # Calculer la durée si applicable (hors CONSENT)
                if 'CONSENT.json' not in file_path_str:
                    duration = self._calculate_activity_duration(activity_entry)
                    if duration is not None:
                        activity_entry["duration_sec"] = round(duration, 2)

                # Insérer chronologiquement
                self._insert_activity_chronologically(activity_entry)

                # Sauvegarder immédiatement
                self._save_to_json()

                print(f"[{self.participant_id}] Activité détectée: {step_type} (page: {parent_page})")

            except Exception as e:
                print(f"[{self.participant_id}] Erreur traitement fichier: {e}")
    
    def _determine_parent_page_for_file(self, filename: str) -> Optional[str]:
        """
        Détermine la page parente d'un fichier d'activité.
        
        Args:
            filename: Nom du fichier d'activité
            
        Returns:
            Nom de la page parente ou None
        """
        # Questionnaires avec pages dédiées
        if '_QVG.json' in filename:
            return 'experience_video_games_en.html'
        elif '_PTTA.json' in filename:
            return 'PTT_A_en.html'
        elif 'preference.json' in filename:
            return 'preference order_en.html'
        elif 'CONSENT.json' in filename:
            return 'index.html'
        
        # Tutorials
        elif 'tutorial' in filename:
            return 'tutorial.html'
        
        # Activités de jeu et questionnaires
        elif self._is_game_session(filename) or '_QPT.json' in filename or 'AAT_L.json' in filename or 'HOFFMAN.json' in filename or 'GAbstractionP.json' in filename:
            return 'planning.html'
        
        return self.current_page  # Fallback sur la page courante
    
    def _insert_activity_chronologically(self, activity_entry: Dict):
        """Insère une activité à la bonne position chronologique."""
        activity_time = datetime.fromisoformat(activity_entry["start_time"])
        
        # Trouver la position d'insertion
        insert_index = len(self.page_history)
        for i, entry in enumerate(self.page_history):
            entry_time = datetime.fromisoformat(entry["start_time"])
            if activity_time < entry_time:
                insert_index = i
                break
        
        self.page_history.insert(insert_index, activity_entry)
    
    def _load_existing_data(self):
        """Charge les données existantes depuis le fichier JSON.

        Gère deux formats :
            - le format enrichi (dict avec `_raw_history`) écrit par cette
              version : on restaure l'historique brut tel quel ;
            - le format hérité (liste organisée par pages) : on reconstruit
              l'historique brut au mieux pour ne pas perdre les durées.

        On reprend ensuite la dernière page si elle n'était pas terminée, et on
        amorce `processed_files` avec les activités déjà connues pour éviter de
        les réenregistrer en double lors du scan de fichiers.
        """
        if not self.json_file.exists():
            return

        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                # Format enrichi : l'historique brut est la source de vérité.
                self.page_history = data.get('_raw_history') or []
            elif isinstance(data, list):
                # Format hérité (liste organisée par pages) : reconstruction.
                self.page_history = self._raw_from_organized(data)
            else:
                self.page_history = []

            # Recalculer la navigation sur l'historique restauré.
            self._compute_navigation()

            # Éviter de retraiter (et donc dupliquer) les activités déjà connues.
            self._prime_processed_files_from_history()

            # Reprendre la dernière vraie page si elle n'est pas terminée.
            if self.page_history:
                last_entry = self.page_history[-1]
                page = last_entry.get('page', '')
                if (not last_entry.get('end_time')
                        and not page.startswith('[ACTIVITÉ]')
                        and not page.startswith('[START_GAME]')):
                    self.current_page = page
                    self.current_start_time = last_entry.get('start_time')

        except Exception as e:
            self.logger.error(f"[PAGE_TRACKER_LOAD_ERROR] uid={self.participant_id} | error={str(e)}")
            self.page_history = []

    def _raw_from_organized(self, organized: List[Dict]) -> List[Dict]:
        """Reconstruit un historique brut à partir du format organisé (hérité).

        Permet de continuer à fonctionner si un ancien fichier de suivi (liste
        de pages avec activités imbriquées) est rencontré.
        """
        raw: List[Dict] = []
        for page_data in organized:
            if not isinstance(page_data, dict):
                continue
            info = page_data.get('page_info', {})
            raw.append({
                'page': page_data.get('page'),
                'step_type': info.get('step_type'),
                'start_time': info.get('start_time'),
                'end_time': info.get('end_time'),
                'duration_sec': info.get('duration_sec'),
            })
            for act in page_data.get('activities', []):
                ts = act.get('start_time')
                raw.append({
                    'page': f"[ACTIVITÉ] {act.get('file')}",
                    'step_type': act.get('step_type'),
                    'start_time': ts,
                    'end_time': ts,
                    'duration_sec': act.get('duration_sec', 0),
                })
        # Réordonner chronologiquement (les activités étaient imbriquées).
        raw.sort(key=lambda e: e.get('start_time') or '')
        return raw

    def _prime_processed_files_from_history(self):
        """Marque comme déjà traités les fichiers d'activité présents dans
        l'historique chargé, pour que le scan ne les réinsère pas en double."""
        try:
            known = {
                entry['page'].replace('[ACTIVITÉ] ', '')
                for entry in self.page_history
                if entry.get('page', '').startswith('[ACTIVITÉ]')
            }
            if not known:
                return
            for file_path in self.trajectory_dir.rglob("*.json"):
                if file_path.name in known:
                    self.processed_files.add(str(file_path))
        except Exception as e:
            self.logger.debug(f"[PAGE_TRACKER_PRIME_ERROR] uid={self.participant_id} | error={str(e)}")
    
    def start_monitoring(self):
        """Démarre la surveillance périodique."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitoring_thread = threading.Thread(
                target=self._periodic_file_monitoring,
                daemon=True,
                name=f"FileMonitor-{self.participant_id}"
            )
            self._monitoring_thread.start()
    
    def stop_monitoring(self):
        """Arrête la surveillance périodique."""
        if self._monitoring_active:
            self._monitoring_active = False
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=1.0)
    
    def end_session(self):
        """Termine la session de suivi.

        Note : avec le timing client-autoritaire, la dernière page est en général
        déjà finalisée par le beacon de sortie (pagehide/hidden), même sans passer
        par /goodbye. Cette finalisation serveur reste un filet de sécurité.
        """
        # Arrêter la surveillance hors du verrou (join du thread).
        self.stop_monitoring()

        with self._data_lock:
            current_time = datetime.now().isoformat()

            # Terminer la page actuelle (repli serveur si pas de relevé client).
            if self.current_page and self.current_start_time:
                self._end_current_page(current_time)

            # Scan final pour les fichiers non détectés
            self._final_scan()

            self._save_to_json()
            print(f"[{self.participant_id}] Session terminée")
    
    def _final_scan(self):
        """Scan final pour fichiers non détectés."""
        try:
            all_files = list(self.trajectory_dir.rglob("*.json"))
            print(f"[{self.participant_id}] Scan final : {len(all_files)} fichiers trouvés")
            
            for file_path in all_files:
                if file_path.name.endswith("_suivis_passation.json"):
                    continue
                
                file_path_str = str(file_path)
                print(f"[{self.participant_id}] Examen fichier : {file_path.name}")
                print(f"[{self.participant_id}] Déjà traité ? {file_path_str in self.processed_files}")
                
                if file_path_str not in self.processed_files:
                    print(f"[{self.participant_id}] Traitement nouveau fichier : {file_path.name}")
                    self._process_new_file(file_path_str)
                    self.processed_files.add(file_path_str)
                    
        except Exception as e:
            print(f"[{self.participant_id}] Erreur scan final: {e}")
    
    # =====================================================================
    # Ingestion des relevés CLIENT (mesure exacte du temps et de la navigation)
    # =====================================================================
    # Méthode de timing inscrite dans le fichier résultat (champ documentaire).
    TIMING_METHOD = "client_authoritative_v4"

    @staticmethod
    def _to_float(v) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(v) -> Optional[int]:
        try:
            if v is None:
                return None
            return int(v)
        except (TypeError, ValueError):
            return None

    def _same_logical_page(self, a: str, b: str) -> bool:
        """Égalité « souple » de pages : compare le dernier segment d'URL, sans
        query string, insensible à la casse (repli si le view_token manque)."""
        if not a or not b:
            return False
        na = a.split('?')[0].rstrip('/').split('/')[-1].lower()
        nb = b.split('?')[0].rstrip('/').split('/')[-1].lower()
        return na == nb

    def ingest_client_event(self, event: Dict) -> bool:
        """Intègre un relevé client (enter / heartbeat / exit) émis par
        static/js/page-tracker.js via /track/page.

        Idempotent et cumulatif : les durées (wall_ms / active_ms) ne font que
        croître (le serveur conserve le maximum), si bien qu'un heartbeat ou un
        passage en arrière-plan suffit à finaliser une vue, même en cas de
        fermeture brutale. Le relevé est rattaché à la vue serveur par son
        view_token ; à défaut, par nom de page ; en dernier recours une entrée
        est SYNTHÉTISÉE pour ne jamais perdre la donnée.

        Returns:
            True si le relevé a été intégré, False sinon.
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

                # _save_to_json recalcule la navigation (reconstruction) PUIS
                # ré-applique la surcouche client : la mesure navigateur fait foi.
                self._save_to_json()

                c = entry.get('client') or {}
                self.logger.info(
                    f"[PAGE_TRACKER_CLIENT_EVENT] uid={self.participant_id} | "
                    f"type={event.get('type')} | page={entry.get('page')} | "
                    f"token={event.get('token')} | wall_ms={c.get('wall_ms')} | "
                    f"active_ms={c.get('active_ms')} | nav={entry.get('navigation_type')} | "
                    f"perf={c.get('perf_nav_type')} | persisted={c.get('persisted')}"
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
        # Repli : dernière vraie page de même nom (priorité à celle sans relevé).
        page = event.get('page')
        fallback = None
        for e in reversed(self.page_history):
            p = e.get('page', '')
            if p.startswith('['):
                continue
            if page and (p == page or self._same_logical_page(p, page)):
                if e.get('client') is None:
                    return e
                if fallback is None:
                    fallback = e
        return fallback

    def _synthesize_client_entry(self, event: Dict) -> Dict:
        """Crée une entrée de page à partir d'un relevé client orphelin (jeton
        introuvable). Garantit qu'aucune donnée de suivi n'est perdue."""
        page = event.get('page') or 'UNKNOWN'
        start = event.get('enter_ts') or datetime.now().isoformat()
        self.logger.warning(
            f"[PAGE_TRACKER_CLIENT_ORPHAN] uid={self.participant_id} | page={page} | "
            f"token={event.get('token')} : entrée synthétisée (vue serveur introuvable)")
        return {
            "page": page,
            "step_type": self._infer_step_type_from_page(page),
            "start_time": start,
            "end_time": None,
            "duration_sec": None,
            "timing_source": "server",
            "view_token": event.get('token'),
            "server_start_time": start,
            "server_end_time": None,
            "server_duration_sec": None,
            "synthesized_from_client": True,
        }

    def _apply_client_event(self, entry: Dict, event: Dict):
        """Fusionne un relevé client dans une entrée de page (cumulatif, idempotent)
        et promeut la mesure client en valeurs autoritaires."""
        c = entry.setdefault('client', {})
        wall_increased = False

        # Durées cumulatives : on conserve le maximum reçu.
        for k in ('wall_ms', 'active_ms', 'hidden_ms'):
            v = self._to_float(event.get(k))
            if v is None:
                continue
            prev = c.get(k)
            if prev is None or v >= prev:
                if k == 'wall_ms' and (prev is None or v > prev):
                    wall_increased = True
                c[k] = round(v, 2)

        # Métadonnées (dernier signal non vide gagne).
        c['view_id'] = event.get('view_id') or c.get('view_id')
        if event.get('prev_view_id'):
            c['prev_view_id'] = event.get('prev_view_id')
        if event.get('perf_nav_type'):
            c['perf_nav_type'] = event.get('perf_nav_type')
        if event.get('redirect_count') is not None:
            c['redirect_count'] = self._to_int(event.get('redirect_count'))
        c['persisted'] = bool(event.get('persisted')) or c.get('persisted', False)
        c['guard_redirect'] = bool(event.get('guard_redirect')) or c.get('guard_redirect', False)
        if event.get('guard_dir'):
            c['guard_dir'] = event.get('guard_dir')
        c['enter_ts'] = c.get('enter_ts') or event.get('enter_ts')
        if 'referrer' in event:
            c['referrer'] = event.get('referrer')
        if event.get('history_length') is not None:
            c['history_length'] = self._to_int(event.get('history_length'))
        c['visibility_changes'] = max(c.get('visibility_changes', 0),
                                      self._to_int(event.get('visibility_changes')) or 0)
        c['heartbeats'] = max(c.get('heartbeats', 0),
                              self._to_int(event.get('heartbeats')) or 0)
        if event.get('exit_reason'):
            c['exit_reason'] = event.get('exit_reason')
        c['last_event_type'] = event.get('type')
        c['received_at'] = datetime.now().isoformat()

        # Horodatage de sortie : instant du dernier beacon qui fait progresser la
        # durée, ou de tout beacon « exit ».
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
                entry['end_time'] = c.get('exit_ts')

    def _apply_client_navigation(self, entry: Dict):
        """Surcouche navigation : la vérité-terrain navigateur (perf_nav_type +
        persisted + sens de la garde) corrige la reconstruction serveur.

        Appelée APRÈS _compute_navigation (qui pose visit_index/is_revisit et la
        distinction back/forward), pour ne pas être écrasée par celle-ci.
        """
        c = entry.get('client')
        if not c:
            return
        nt = c.get('perf_nav_type')
        if not nt:
            return
        entry['navigation_source'] = 'client'
        # La première page de la session reste "entry" (déterminé par la pile).
        if entry.get('navigation_type') == 'entry':
            return

        if nt == 'reload':
            entry['navigation_type'] = 'reload'
            entry['navigation_detail'] = 'reload'
        elif nt == 'back_forward':
            # L'API ne distingue pas back/forward ; le sens de la garde fait foi,
            # sinon on conserve la reconstruction si elle a déjà tranché.
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

    def _harmonize_all_navigation(self):
        """Ré-applique la surcouche client à toutes les entrées (après une passe
        de reconstruction). Idempotent."""
        for entry in self.page_history:
            page = entry.get('page', '')
            if page.startswith('['):
                continue
            self._apply_client_navigation(entry)

    # Types de navigation considérés comme de vraies navigations de page
    # (par opposition aux marqueurs internes "activity" / "event").
    PAGE_NAV_TYPES = ("entry", "forward", "back", "reload")

    def _compute_navigation(self):
        """Calcule, pour chaque entrée de page réelle, le type de navigation.

        On simule la pile d'historique du navigateur (back/forward stack) avec
        un curseur, en ne considérant QUE les vraies pages : les marqueurs
        [ACTIVITÉ] (détection de fichiers) et [START_GAME] (événement
        intra-page) ne sont pas des navigations.

        Pour chaque vraie page on détermine, par comparaison avec la pile :
            - "reload"  : la page demandée est identique à la page courante ;
            - "back"    : elle correspond à la page située juste avant le
                          curseur (bouton « précédent ») ;
            - "forward" : elle correspond à la page juste après le curseur
                          (bouton « suivant » du navigateur) OU il s'agit
                          d'une nouvelle progression (la page est alors
                          empilée et les éventuelles pages « en avant » sont
                          tronquées, comme dans un vrai navigateur) ;
            - "entry"   : toute première page de la session.

        Les champs suivants sont écrits (en place) sur chaque entrée :
            navigation_type, navigation_detail, visit_index, is_revisit.

        La méthode est déterministe et idempotente : elle peut être rappelée
        à chaque sauvegarde sans effet de bord.
        """
        nav_stack = []        # pages réelles formant la pile du navigateur
        cursor = -1           # index de la page courante dans nav_stack
        visit_counts = {}     # page -> nombre cumulé d'ouvertures

        for entry in self.page_history:
            page = entry.get('page', '')

            # Marqueurs internes : pas des navigations.
            if page.startswith('[ACTIVITÉ]'):
                entry['navigation_type'] = 'activity'
                entry['navigation_detail'] = 'file_event'
                continue
            if page.startswith('[START_GAME]'):
                entry['navigation_type'] = 'event'
                entry['navigation_detail'] = 'in_page_event'
                continue

            # Vraie page : classification selon la pile d'historique.
            if cursor < 0:
                nav_type, detail = 'entry', 'session_start'
                nav_stack = [page]
                cursor = 0
            elif nav_stack[cursor] == page:
                nav_type, detail = 'reload', 'reload'
                # Pile et curseur inchangés.
            elif cursor > 0 and nav_stack[cursor - 1] == page:
                nav_type, detail = 'back', 'browser_back'
                cursor -= 1
            elif cursor < len(nav_stack) - 1 and nav_stack[cursor + 1] == page:
                nav_type, detail = 'forward', 'browser_forward'
                cursor += 1
            else:
                # Nouvelle progression : on tronque l'avant de la pile et on
                # empile la nouvelle page (comportement d'un vrai navigateur).
                already_seen = page in visit_counts
                nav_type = 'forward'
                detail = 'revisit' if already_seen else 'new_page'
                nav_stack = nav_stack[:cursor + 1] + [page]
                cursor = len(nav_stack) - 1

            visit_counts[page] = visit_counts.get(page, 0) + 1
            entry['navigation_type'] = nav_type
            entry['navigation_detail'] = detail
            entry['visit_index'] = visit_counts[page]
            entry['is_revisit'] = visit_counts[page] > 1
            # Source par défaut : reconstruction serveur (peut être corrigée par
            # la surcouche client ci-dessous si un relevé navigateur existe).
            entry['navigation_source'] = 'reconstructed'

        # Surcouche CLIENT : la vérité-terrain navigateur (reload / back_forward /
        # restauration bfcache) corrige la reconstruction là où elle existe.
        self._harmonize_all_navigation()

    def _build_navigation_summary(self):
        """Agrège les métadonnées de navigation par page et au global.

        Doit être appelée après `_compute_navigation`.

        Returns:
            (summary, totals) où
              - summary : dict {page: {visit_count, entry_count, forward_count,
                back_count, reload_count, total_duration_sec, first_seen,
                last_seen}} ;
              - totals  : dict des compteurs globaux (pages, entry, forward,
                back, reload, distinct_pages, total_page_time_sec).
        """
        summary: Dict[str, Dict] = {}
        totals = {
            "pages": 0, "entry": 0, "forward": 0, "back": 0, "reload": 0,
            "distinct_pages": 0, "total_page_time_sec": 0.0,
        }

        for entry in self.page_history:
            nav = entry.get('navigation_type')
            if nav not in self.PAGE_NAV_TYPES:
                continue  # ignorer activités et événements intra-page

            page = entry.get('page')
            start_time = entry.get('start_time')
            duration = entry.get('duration_sec') or 0

            page_stats = summary.setdefault(page, {
                "visit_count": 0, "entry_count": 0, "forward_count": 0,
                "back_count": 0, "reload_count": 0,
                "total_duration_sec": 0.0,
                "first_seen": start_time, "last_seen": start_time,
            })
            page_stats["visit_count"] += 1
            page_stats[f"{nav}_count"] += 1
            page_stats["total_duration_sec"] = round(
                page_stats["total_duration_sec"] + duration, 2)
            page_stats["last_seen"] = start_time

            totals["pages"] += 1
            totals[nav] += 1
            totals["total_page_time_sec"] = round(
                totals["total_page_time_sec"] + duration, 2)

        totals["distinct_pages"] = len(summary)
        return summary, totals

    def get_navigation_report(self) -> Dict:
        """Retourne le rapport de navigation complet (sans toucher au disque).

        Structure identique à celle écrite dans le fichier de suivi, hors
        `_raw_history`.
        """
        self._compute_navigation()
        summary, totals = self._build_navigation_summary()
        return {
            "participant_id": self.participant_id,
            "config_name": self.config_name,
            "navigation_totals": totals,
            "navigation_summary": summary,
            "pages": self._organize_data_by_pages(),
        }

    def _save_to_json(self):
        """Sauvegarde thread-safe des données avec structure organisée par pages.

        Le fichier contient :
            - participant_id / config_name : métadonnées ;
            - navigation_totals : compteurs globaux (avant/arrière/reload) ;
            - navigation_summary : agrégats par page (temps total, nb visites,
              nb reloads, nb retours...) ;
            - pages : déroulé chronologique des pages et de leurs activités,
              chaque page portant son type de navigation ;
            - _raw_history : historique brut (sert au rechargement fidèle de
              l'état après un redémarrage du serveur).
        """
        with self._data_lock:
            try:
                # 1) (Re)calculer la classification de navigation (+ surcouche client).
                self._compute_navigation()

                # 2) Construire les vues dérivées.
                organized_data = self._organize_data_by_pages()
                navigation_summary, navigation_totals = self._build_navigation_summary()
                timing_coverage = self._build_timing_coverage()

                output = {
                    "participant_id": self.participant_id,
                    "config_name": self.config_name,
                    # Méthode de mesure : timing CLIENT-autoritaire avec filet serveur.
                    "timing_method": self.TIMING_METHOD,
                    "timing_coverage": timing_coverage,
                    "navigation_totals": navigation_totals,
                    "navigation_summary": navigation_summary,
                    "pages": organized_data,
                    "_raw_history": self.page_history,
                }

                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)

                # Vérifier et logger la taille du fichier sauvegardé
                file_size = os.path.getsize(self.json_file)
                self.logger.info(
                    f"[PAGE_TRACKER_SAVE] uid={self.participant_id} | file={self.json_file.name} | "
                    f"size_bytes={file_size} | pages={len(organized_data)} | "
                    f"client_timed={timing_coverage['client']}/{timing_coverage['total_pages']} | "
                    f"nav(fwd/back/reload)={navigation_totals['forward']}/"
                    f"{navigation_totals['back']}/{navigation_totals['reload']}")

            except Exception as e:
                self.logger.error(f"[PAGE_TRACKER_SAVE_ERROR] uid={self.participant_id} | file={self.json_file.name} | error={str(e)}", exc_info=True)

    def _build_timing_coverage(self) -> Dict:
        """Compte la part des pages dont la durée provient d'une mesure client
        EXACTE vs d'un repli serveur (contrôle qualité rapide en tête de fichier)."""
        total = client = server = pending = 0
        for entry in self.page_history:
            if entry.get('page', '').startswith('['):
                continue  # marqueurs internes : pas des pages
            total += 1
            src = entry.get('timing_source')
            if src == 'client':
                client += 1
            elif entry.get('duration_sec') is not None:
                server += 1
            else:
                pending += 1
        return {
            "total_pages": total,
            "client": client,        # durée mesurée exactement dans le navigateur
            "server": server,        # repli serveur (relevé client absent)
            "pending": pending,      # page encore ouverte / non finalisée
        }
    
    def _organize_data_by_pages(self) -> List[Dict]:
        """
        Organise les données par pages dans l'ordre chronologique avec leurs activités associées.
        Permet les multiples occurrences de la même page pour suivre le déroulement complet.
        
        Returns:
            Liste ordonnée de dictionnaires représentant chaque page avec ses activités
        """
        organized_data = []
        current_page_data = None
        
        for entry in self.page_history:
            page_name = entry['page']
            
            if not page_name.startswith('[ACTIVITÉ]'):
                # C'est une nouvelle page - créer une nouvelle entrée
                current_page_data = {
                    "page": page_name,
                    "page_info": {
                        "step_type": entry['step_type'],
                        "start_time": entry['start_time'],
                        "end_time": entry.get('end_time'),
                        # Durée AUTORITAIRE (client exact si dispo, sinon serveur).
                        "duration_sec": entry.get('duration_sec'),
                        "active_duration_sec": entry.get('active_duration_sec'),
                        "timing_source": entry.get('timing_source'),
                        # Classification de navigation (reconstruction + surcouche client)
                        "navigation_type": entry.get('navigation_type'),
                        "navigation_detail": entry.get('navigation_detail'),
                        "navigation_source": entry.get('navigation_source'),
                        "visit_index": entry.get('visit_index'),
                        "is_revisit": entry.get('is_revisit'),
                        # Mesure serveur conservée (diagnostic / repli).
                        "server_duration_sec": entry.get('server_duration_sec'),
                        # Détail brut des relevés navigateur (None si aucun reçu).
                        "client": entry.get('client'),
                        "view_token": entry.get('view_token'),
                    },
                    "activities": []
                }
                organized_data.append(current_page_data)
            else:
                # C'est une activité - l'associer à la page courante ou à sa page logique
                filename = page_name.replace('[ACTIVITÉ] ', '')
                logical_parent = self._determine_parent_page_for_file(filename)
                
                activity_data = {
                    "file": filename,
                    "step_type": entry['step_type'],
                    "start_time": entry['start_time'],
                    "duration_sec": entry.get('duration_sec', 0)
                }
                
                # Essayer d'associer à la page logique la plus récente
                target_page_data = self._find_most_recent_page_occurrence(organized_data, logical_parent)
                
                if target_page_data:
                    target_page_data["activities"].append(activity_data)
                else:
                    # Fallback : associer à la page courante
                    if current_page_data:
                        current_page_data["activities"].append(activity_data)
                    else:
                        # Créer une page orpheline pour cette activité
                        orphan_page = {
                            "page": f"ORPHELINE_{filename}",
                            "page_info": {
                                "step_type": "Activité sans page parente",
                                "start_time": entry['start_time'],
                                "end_time": entry['start_time'],
                                "duration_sec": 0
                            },
                            "activities": [activity_data]
                        }
                        organized_data.append(orphan_page)
        
        return organized_data
    
    def _find_most_recent_page_occurrence(self, organized_data: List[Dict], page_name: str) -> Optional[Dict]:
        """
        Trouve la dernière occurrence d'une page dans les données organisées.
        
        Args:
            organized_data: Liste des pages organisées
            page_name: Nom de la page à rechercher
            
        Returns:
            Dictionnaire de la page trouvée ou None
        """
        if not page_name:
            return None
            
        # Chercher en ordre inverse pour trouver la dernière occurrence
        for page_data in reversed(organized_data):
            if page_data["page"] == page_name:
                return page_data
        
        return None
    
    def _find_closest_page_before_activity(self, activity_entry: Dict) -> Optional[str]:
        """Trouve la page la plus proche chronologiquement avant une activité."""
        activity_time = datetime.fromisoformat(activity_entry['start_time'])
        
        closest_page = None
        for entry in reversed(self.page_history):
            if not entry['page'].startswith('[ACTIVITÉ]'):
                entry_time = datetime.fromisoformat(entry['start_time'])
                if entry_time <= activity_time:
                    closest_page = entry['page']
                    break
        
        return closest_page
    
    def get_activities(self) -> List[Dict]:
        """
        Retourne les activités organisées par pages dans l'ordre chronologique.
        
        Returns:
            Liste ordonnée de pages avec leurs activités associées
        """
        return self._organize_data_by_pages()
    
    def get_raw_history(self) -> List[Dict]:
        """
        Retourne l'historique brut des pages et activités (ancien format).
        
        Returns:
            Liste chronologique des entrées (pour compatibilité)
        """
        return self.page_history.copy()
    
    def calculate_durations(self) -> Dict[str, float]:
        """
        Calcule les durées pour toutes les activités.
        
        Returns:
            Dictionnaire {type_activité: durée_en_secondes}
        """
        durations = {}
        
        for activity in self.page_history:
            duration = self._calculate_activity_duration(activity)
            if duration is not None:
                activity_type = activity.get('step_type', 'Unknown')
                durations[activity_type] = duration
                
        return durations
    
    def force_scan(self):
        """
        Force un scan immédiat du répertoire pour détecter de nouveaux fichiers.
        Utile pour les tests ou le débogage.
        """
        print(f"[{self.participant_id}] Début scan forcé...")
        print(f"[{self.participant_id}] Fichiers déjà traités : {len(self.processed_files)}")
        self._final_scan()
        print(f"[{self.participant_id}] Activités après scan : {len(self.page_history)}")