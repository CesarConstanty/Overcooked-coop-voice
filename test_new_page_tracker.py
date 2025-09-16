#!/usr/bin/env python3
"""
Script de test pour la nouvelle logique du PageTracker.
Recalcule les durées selon les nouvelles règles [time needed].
"""

import json
import os
import shutil
from pathlib import Path
from page_tracker import PageTracker

def test_participant_tracking(participant_id: str, config_name: str = "config_test"):
    """
    Teste la nouvelle logique du PageTracker sur un participant existant.
    """
    print(f"\n=== Test PageTracker pour participant {participant_id} ===")
    
    # Sauvegarder l'ancien fichier
    trajectory_dir = Path(f"trajectories/{config_name}/{participant_id}")
    old_file = trajectory_dir / f"{participant_id}_suivis_passation.json"
    backup_file = trajectory_dir / f"{participant_id}_suivis_passation_backup.json"
    
    if old_file.exists():
        shutil.copy2(old_file, backup_file)
        print(f"Sauvegarde créée: {backup_file}")
    
    # Initialiser le tracker
    tracker = PageTracker(participant_id, config_name)
    
    # Charger les données existantes pour analyser
    if old_file.exists():
        with open(old_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            
        print(f"Données existantes: {len(old_data)} entrées")
        
        # Analyser les pages et activités
        pages = [entry for entry in old_data if not entry['page'].startswith('[ACTIVITÉ]')]
        activities = [entry for entry in old_data if entry['page'].startswith('[ACTIVITÉ]')]
        
        print(f"Pages: {len(pages)}, Activités: {len(activities)}")
        
        # Simuler les pages visitées
        tracker.page_history = []  # Reset
        for entry in old_data:
            if not entry['page'].startswith('[ACTIVITÉ]'):
                # Reproduire la visite de page
                page_entry = {
                    "page": entry['page'],
                    "step_type": entry['step_type'],
                    "start_time": entry['start_time'],
                    "end_time": entry.get('end_time'),
                    "duration_sec": entry.get('duration_sec')
                }
                tracker.page_history.append(page_entry)
        
        # Réanalyser les activités avec la nouvelle logique
        print("\nRecalcul des durées avec la nouvelle logique...")
        new_activities = []
        
        for entry in activities:
            filename = entry['page'].replace('[ACTIVITÉ] ', '')
            
            # Créer une nouvelle entrée d'activité
            new_activity = {
                "page": entry['page'],
                "step_type": entry['step_type'],
                "start_time": entry['start_time'],
                "end_time": entry['end_time'],
                "duration_sec": 0
            }
            
            # Calculer la nouvelle durée
            if 'CONSENT.json' not in filename:
                duration = tracker._calculate_activity_duration(new_activity)
                if duration is not None:
                    new_activity["duration_sec"] = round(duration, 2)
                    print(f"  {filename}: {duration:.2f}s")
                else:
                    print(f"  {filename}: pas de durée calculée")
            
            new_activities.append(new_activity)
        
        # Fusionner pages et activités, trier par timestamp
        all_entries = pages + new_activities
        all_entries.sort(key=lambda x: x['start_time'])
        
        # Sauvegarder le nouveau fichier
        with open(old_file, 'w', encoding='utf-8') as f:
            json.dump(all_entries, f, ensure_ascii=False, indent=2)
        
        print(f"\nNouveau fichier sauvegardé: {old_file}")
        print(f"Ancien fichier sauvegardé: {backup_file}")
        
        # Afficher un résumé des changements
        print("\n=== Résumé des changements ===")
        for old_act, new_act in zip(activities, new_activities):
            old_dur = old_act.get('duration_sec', 0)
            new_dur = new_act.get('duration_sec', 0)
            if abs(old_dur - new_dur) > 0.1:  # Différence significative
                filename = old_act['page'].replace('[ACTIVITÉ] ', '')
                print(f"{filename}: {old_dur:.2f}s → {new_dur:.2f}s")

def main():
    """Teste les participants 5 et 7."""
    participants = ['5', '7']
    
    for participant_id in participants:
        test_participant_tracking(participant_id)
        
    print("\n=== Test terminé ===")
    print("Les anciens fichiers sont sauvegardés avec le suffixe '_backup'")

if __name__ == "__main__":
    main()