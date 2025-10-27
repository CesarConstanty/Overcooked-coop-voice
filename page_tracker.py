"""
Système de suivi temporel optimisé pour la plateforme expérimentale Overcooked.

Version optimisée pour usage multi-joueurs avec surveillance périodique
et calcul automatique des durées d'activités.

Auteur: AI Assistant
Date: Septembre 2025
Version: 2.0 - Intégration avec app.logger
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
        elif "preference.json" in filename:
            return "Questionnaire Préférence"
        elif "_QPT.json" in filename:
            return self._parse_qpt_filename(filename)
        elif "AAT_L.json" in filename:
            return self._parse_attl_filename(filename)
        elif "HOFFMAN.json" in filename:
            return self._parse_hoffman_filename(filename)
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
                       ['QPT', 'AAT_L', 'HOFFMAN', 'preference', 'QVG', 'PTTA', 'tutorial']))
    
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
    
    def start_page(self, page_name: str):
        """Enregistre le début d'une nouvelle page."""
        current_time = datetime.now().isoformat()
        
        # Terminer la page précédente
        previous_page = self.current_page
        if self.current_page and self.current_start_time:
            self._end_current_page(current_time)
        
        # Commencer la nouvelle page
        self.current_page = page_name
        self.current_start_time = current_time
        
        step_type = self._infer_step_type_from_page(page_name)
        
        page_entry = {
            "page": page_name,
            "step_type": step_type,
            "start_time": current_time,
            "end_time": None,
            "duration_sec": None
        }
        self.page_history.append(page_entry)
        
        # Log la transition de page
        self.logger.info(f"[PAGE_TRACKER_PAGE_START] uid={self.participant_id} | page={page_name} | step_type={step_type} | previous_page={previous_page}")
        
        # Démarrer la surveillance si pas déjà active
        self.start_monitoring()
        
        self._save_to_json()
    
    def _end_current_page(self, end_time: str):
        """Termine la page actuelle."""
        if not self.page_history:
            return
            
        # Trouver la dernière page (non activité) ouverte
        last_page_entry = None
        for entry in reversed(self.page_history):
            if not entry['page'].startswith('[ACTIVITÉ]') and not entry.get('end_time'):
                last_page_entry = entry
                break
        
        if last_page_entry and last_page_entry['page'] == self.current_page:
            last_page_entry['end_time'] = end_time
            
            try:
                start_dt = datetime.fromisoformat(last_page_entry['start_time'])
                end_dt = datetime.fromisoformat(end_time)
                duration = (end_dt - start_dt).total_seconds()
                # Éviter les durées négatives dues à des problèmes de synchronisation
                last_page_entry['duration_sec'] = round(max(0, duration), 2)
                
                self.logger.info(f"[PAGE_TRACKER_PAGE_END] uid={self.participant_id} | page={self.current_page} | duration={duration:.2f}s")
            except ValueError as e:
                self.logger.error(f"[PAGE_TRACKER_PAGE_DURATION_ERROR] uid={self.participant_id} | page={self.current_page} | error={str(e)}")
                last_page_entry['duration_sec'] = 0
    
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
        """Traite un nouveau fichier détecté."""
        try:
            file_timestamp = os.path.getmtime(file_path_str)
            activity_time = datetime.fromtimestamp(file_timestamp).isoformat()
            step_type = self._classify_file_step_type(file_path_str)
            filename = os.path.basename(file_path_str)
            
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
        elif self._is_game_session(filename) or '_QPT.json' in filename or 'AAT_L.json' in filename or 'HOFFMAN.json' in filename:
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
        """Charge les données existantes depuis le fichier JSON."""
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    self.page_history = json.load(f)
                    
                # Récupérer la dernière page si elle n'est pas terminée
                if self.page_history and not self.page_history[-1].get('end_time'):
                    last_entry = self.page_history[-1]
                    self.current_page = last_entry['page']
                    self.current_start_time = last_entry['start_time']
                    
            except Exception as e:
                self.logger.error(f"[PAGE_TRACKER_LOAD_ERROR] uid={self.participant_id} | error={str(e)}")
                self.page_history = []
    
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
        """Termine la session de suivi."""
        current_time = datetime.now().isoformat()
        
        # Terminer la page actuelle
        if self.current_page and self.current_start_time:
            self._end_current_page(current_time)
        
        # Arrêter la surveillance
        self.stop_monitoring()
        
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
    
    def _save_to_json(self):
        """Sauvegarde thread-safe des données avec structure organisée par pages."""
        try:
            # Organiser les données par pages avec leurs activités associées
            organized_data = self._organize_data_by_pages()
            
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(organized_data, f, ensure_ascii=False, indent=2)
            
            # Vérifier et logger la taille du fichier sauvegardé
            file_size = os.path.getsize(self.json_file)
            self.logger.info(f"[PAGE_TRACKER_SAVE] uid={self.participant_id} | file={self.json_file.name} | size_bytes={file_size} | entries={len(organized_data)}")
            
        except Exception as e:
            self.logger.error(f"[PAGE_TRACKER_SAVE_ERROR] uid={self.participant_id} | file={self.json_file.name} | error={str(e)}", exc_info=True)
    
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
                        "duration_sec": entry.get('duration_sec')
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