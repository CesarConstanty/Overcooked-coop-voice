"""
Système de suivi temporel des pages pour la plateforme expérimentale Overcooked.

Ce module implémente un tracker qui enregistre :
- L'horodatage d'affichage de chaque page HTML
- La durée passée sur chaque page
- La persistance des données au format JSON

Auteur: AI Assistant
Date: Septembre 2025
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class PageTracker:
    """
    Gestionnaire de suivi temporel des pages visitées durant l'expérience.
    
    Cette classe enregistre les horodatages d'affichage de chaque page et calcule
    automatiquement les durées de consultation. Les données sont sauvegardées
    dans un fichier JSON spécifique au participant.
    """
    
    def __init__(self, participant_id: str, config_name: str):
        """
        Initialise le tracker pour un participant donné.
        
        Args:
            participant_id: Identifiant unique du participant
            config_name: Nom de la configuration expérimentale
        """
        self.participant_id = participant_id
        self.config_name = config_name
        self.current_page = None
        self.current_start_time = None
        self.page_history: List[Dict] = []
        
        # Chemin du fichier de sauvegarde
        self.trajectory_dir = Path(f"trajectories/{config_name}/{participant_id}")
        self.trajectory_dir.mkdir(parents=True, exist_ok=True)
        self.json_file = self.trajectory_dir / f"{participant_id}_suivis_passation.json"
        
        # Charger les données existantes si le fichier existe
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Charge les données existantes depuis le fichier JSON s'il existe."""
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    self.page_history = json.load(f)
                    
                # Récupérer la dernière page si elle existe et n'a pas de end_time
                if self.page_history and not self.page_history[-1].get('end_time'):
                    last_entry = self.page_history[-1]
                    self.current_page = last_entry['page']
                    self.current_start_time = last_entry['start_time']
                    
            except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                print(f"Erreur lors du chargement des données de suivi pour {self.participant_id}: {e}")
                self.page_history = []
    
    def start_page(self, page_name: str):
        """
        Enregistre le début de consultation d'une nouvelle page.
        
        Args:
            page_name: Nom de la page HTML affichée (ex: 'instructions.html')
        """
        current_time = datetime.now().isoformat()
        
        # Terminer la page précédente si elle existe
        if self.current_page and self.current_start_time:
            self._end_current_page(current_time)
        
        # Commencer la nouvelle page
        self.current_page = page_name
        self.current_start_time = current_time
        
        # Ajouter l'entrée à l'historique (sans end_time pour l'instant)
        page_entry = {
            "page": page_name,
            "start_time": current_time,
            "end_time": None,
            "duration_sec": None
        }
        self.page_history.append(page_entry)
        
        # Sauvegarder immédiatement
        self._save_to_json()
    
    def _end_current_page(self, end_time: str):
        """
        Termine la page actuelle en calculant sa durée.
        
        Args:
            end_time: Horodatage de fin au format ISO
        """
        if not self.page_history:
            return
            
        # Mettre à jour la dernière entrée
        last_entry = self.page_history[-1]
        if last_entry['page'] == self.current_page and not last_entry.get('end_time'):
            last_entry['end_time'] = end_time
            
            # Calculer la durée en secondes
            try:
                start_dt = datetime.fromisoformat(self.current_start_time)
                end_dt = datetime.fromisoformat(end_time)
                duration = (end_dt - start_dt).total_seconds()
                last_entry['duration_sec'] = round(duration, 2)
            except ValueError as e:
                print(f"Erreur calcul durée pour {self.participant_id}: {e}")
                last_entry['duration_sec'] = 0
    
    def end_session(self):
        """Termine la session en clôturant la page actuelle."""
        if self.current_page and self.current_start_time:
            current_time = datetime.now().isoformat()
            self._end_current_page(current_time)
            self._save_to_json()
            
        # Réinitialiser l'état
        self.current_page = None
        self.current_start_time = None
    
    def _save_to_json(self):
        """Sauvegarde les données dans le fichier JSON."""
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.page_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erreur sauvegarde suivi temporel pour {self.participant_id}: {e}")
    
    def get_current_session_duration(self) -> float:
        """
        Retourne la durée totale de la session en cours (en secondes).
        
        Returns:
            Durée totale en secondes
        """
        if not self.page_history:
            return 0.0
            
        total_duration = 0.0
        for entry in self.page_history:
            if entry.get('duration_sec'):
                total_duration += entry['duration_sec']
                
        # Ajouter le temps de la page actuelle si elle n'est pas terminée
        if self.current_page and self.current_start_time:
            try:
                start_dt = datetime.fromisoformat(self.current_start_time)
                current_dt = datetime.now()
                current_page_duration = (current_dt - start_dt).total_seconds()
                total_duration += current_page_duration
            except ValueError:
                pass
                
        return round(total_duration, 2)
    
    def get_page_summary(self) -> Dict:
        """
        Retourne un résumé des pages visitées.
        
        Returns:
            Dictionnaire avec les statistiques de navigation
        """
        if not self.page_history:
            return {"total_pages": 0, "total_duration": 0.0}
            
        return {
            "total_pages": len(self.page_history),
            "total_duration": self.get_current_session_duration(),
            "current_page": self.current_page,
            "pages_visited": [entry['page'] for entry in self.page_history]
        }