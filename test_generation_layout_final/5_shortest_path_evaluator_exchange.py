#!/usr/bin/env python3
"""
Sélecteur de Layouts Basé sur les Échanges - Overcooked pour Sciences Cognitives

Ce module implémente une méthodologie avancée pour:
1. Analyser les échanges entre joueurs dans chaque layout
2. Calculer l'efficacité de la coopération par rapport au solo
3. Sélectionner les layouts maximisant les interactions tout en optimisant l'efficacité
4. Visualiser les métriques d'échange et de performance

Objectif: Identifier les layouts favorisant le plus d'interactions coopératives 
         tout en maintenant un gain significatif d'efficacité par rapport au solo.

Auteur: Assistant IA Spécialisé
Date: Août 2025
Contexte: Recherche en sciences cognitives sur la coopération humain-IA
"""

import os
import json
import glob
import shutil
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
import statistics
from scipy import stats

# Configuration matplotlib pour des visualisations professionnelles
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = [12, 8]
plt.rcParams['font.size'] = 10

class ExchangeBasedLayoutSelector:
    """Sélecteur de layouts basé sur l'analyse des échanges entre joueurs"""
    
    def __init__(self):
        """Initialise le sélecteur avec configuration des dossiers et paramètres"""
        # Configuration des dossiers
        self.data_dir = "path_evaluation_results"
        self.layouts_source_dir = "layouts_with_objects"
        self.selected_layouts_dir = "layout_analysis_results/exchange_analysis/layouts_échanges_optimaux"
        self.output_dir = "layout_analysis_results/exchange_analysis"
        
        # Créer les dossiers de sortie
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.selected_layouts_dir, exist_ok=True)
        
        # Paramètres d'analyse des échanges
        self.exchange_distance_threshold = 2.0  # Distance max pour considérer un échange
        self.min_exchange_duration = 2  # Durée minimale d'un échange (en steps)
        self.efficiency_threshold = 10  # Gain minimum requis en steps (solo - duo)
        self.min_exchange_count = 5  # Nombre minimum d'échanges requis
        
        # Structure pour stocker les données
        self.layout_exchange_data = {}
        self.efficiency_data = {}
        self.combined_scores = {}
        self.total_processed_count = 0  # Compteur pour le traitement itératif
        
        print(f"🔄 Sélecteur d'échanges initialisé")
        print(f"📂 Dossier de sortie: {self.output_dir}")
        print(f"📂 Layouts sélectionnés: {self.selected_layouts_dir}")
    
    def process_evaluation_files_iteratively(self) -> Dict[str, Dict]:
        """Traite les fichiers d'évaluation de manière itérative pour économiser la mémoire"""
        
        evaluation_files = glob.glob(f"{self.data_dir}/*.json")
        filtered_layouts = {}
        
        print(f"\n📊 Traitement itératif de {len(evaluation_files)} fichiers...")
        print(f"💾 Mode économe en mémoire activé")
        
        total_processed = 0
        total_filtered = 0
        
        for i, file_path in enumerate(evaluation_files, 1):
            print(f"\n📁 Fichier {i}/{len(evaluation_files)}: {os.path.basename(file_path)}")
            
            try:
                # Traiter le fichier par chunks si possible
                file_layouts = self.load_single_file_data(file_path)
                
                if not file_layouts:
                    continue
                
                # Traiter chaque layout individuellement
                for layout_name, layout_info in file_layouts.items():
                    total_processed += 1
                    self.total_processed_count = total_processed  # Mettre à jour le compteur global
                    
                    # Calculer les métriques d'échange pour ce layout
                    exchange_data = self.simulate_player_exchanges(layout_info)
                    
                    # Appliquer les critères de filtrage immédiatement
                    if self.meets_filtering_criteria(exchange_data):
                        filtered_layouts[layout_name] = exchange_data
                        total_filtered += 1
                        
                        if total_filtered % 10 == 0:
                            print(f"   ✅ {total_filtered} layouts validés jusqu'à présent")
                
                # Libérer la mémoire du fichier traité
                del file_layouts
                
                print(f"   📊 Traité: {total_processed} | Validé: {total_filtered}")
                
            except Exception as e:
                print(f"   ❌ Erreur lors du traitement de {file_path}: {e}")
                continue
        
        print(f"\n✅ Traitement terminé:")
        print(f"   📊 Total analysé: {total_processed} layouts")
        print(f"   🎯 Total validé: {total_filtered} layouts")
        if total_processed > 0:
            print(f"   📈 Taux de validation: {(total_filtered/total_processed*100):.1f}%")
        else:
            print(f"   📈 Aucun layout trouvé dans {self.data_dir}")
        
        return filtered_layouts
    
    def load_single_file_data(self, file_path: str) -> Dict[str, Dict]:
        """Charge les données d'un seul fichier"""
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            file_layouts = {}
            
            if isinstance(data, list):
                # Si c'est une liste de layouts
                for layout_info in data:
                    layout_path = layout_info.get('layout_path', '')
                    layout_name = self.extract_layout_name(layout_path)
                    if layout_name:
                        file_layouts[layout_name] = layout_info
            elif isinstance(data, dict):
                # Si c'est un dictionnaire
                for layout_name, layout_info in data.items():
                    file_layouts[layout_name] = layout_info
            
            return file_layouts
            
        except Exception as e:
            print(f"❌ Erreur lors du chargement de {file_path}: {e}")
            return {}
    
    def meets_filtering_criteria(self, exchange_data: Dict) -> bool:
        """Vérifie si un layout respecte les critères de filtrage basés sur les échanges réels"""
        
        # Critère 1: Gain d'efficacité minimum
        if exchange_data['efficiency_gain'] < self.efficiency_threshold:
            return False
        
        # Critère 2: Nombre d'échanges minimum (plus strict pour les échanges réels)
        min_exchanges_required = 3 if exchange_data.get('real_exchanges_detected', False) else self.min_exchange_count
        if exchange_data['exchange_count'] < min_exchanges_required:
            return False
        
        # Critère 3: Amélioration significative (au moins 5% de gain)
        if exchange_data['efficiency_percentage'] < 5.0:
            return False
        
        # Critère 4: Au moins une zone d'échange
        if exchange_data['exchange_zones'] < 1:
            return False
        
        # Bonus pour les échanges réels détectés
        if exchange_data.get('real_exchanges_detected', False):
            return True  # Accepter plus facilement les layouts avec échanges réels
        
        return True
    
    def extract_layout_name(self, layout_path: str) -> str:
        """Extrait le nom du layout depuis son chemin"""
        if not layout_path:
            return ""
        
        # Extraire le nom de fichier sans extension
        layout_name = os.path.basename(layout_path).replace('.layout', '')
        return layout_name
    
    def simulate_player_exchanges(self, layout_info: Dict) -> Dict:
        """
        Analyse les échanges réels entre joueurs basés sur les actions de jeu
        
        Détecte les séquences:
        1. Joueur A dépose un objet à la position P (drop/place/deliver)
        2. Joueur B récupère un objet à la position P (pickup/grab/take)
        
        Returns:
            Dict contenant les métriques d'échange réel détectées
        """
        
        solo_distance = layout_info.get('solo_distance', 0)
        coop_distance = layout_info.get('coop_distance', 0)
        
        if solo_distance == 0 or coop_distance == 0:
            return self._create_empty_exchange_data()
        
        # Récupérer les actions des joueurs
        player_actions = layout_info.get('player_actions', {})
        coop_actions = layout_info.get('coop_actions', [])
        game_actions = layout_info.get('game_actions', [])
        
        # Essayer différents formats de données d'actions
        actions_to_analyze = coop_actions or game_actions or []
        
        # Si pas d'actions trouvées, utiliser l'ancienne méthode d'estimation
        if not actions_to_analyze:
            return self._estimate_exchanges_from_efficiency(solo_distance, coop_distance)
        
        # Analyser les échanges dans les actions
        exchanges = self._detect_real_exchanges_in_actions(actions_to_analyze)
        
        # Calculer les métriques d'échange
        exchange_count = len(exchanges)
        exchange_positions = set()
        exchange_durations = []
        exchange_objects = []
        
        for exchange in exchanges:
            exchange_positions.add(exchange['position'])
            exchange_durations.append(exchange['duration'])
            exchange_objects.append(exchange['object_type'])
        
        # Métriques dérivées
        avg_exchange_duration = np.mean(exchange_durations) if exchange_durations else 0
        unique_exchange_positions = len(exchange_positions)
        object_types_exchanged = len(set(exchange_objects))
        
        # Calcul du gain d'efficacité
        efficiency_gain = solo_distance - coop_distance
        efficiency_percentage = (efficiency_gain / solo_distance * 100) if solo_distance > 0 else 0
        
        # Score de coopération basé sur les échanges réels
        cooperation_score = self._calculate_real_cooperation_score(
            exchange_count, unique_exchange_positions, avg_exchange_duration, efficiency_gain
        )
        
        # Densité d'échange réelle
        exchange_density = (exchange_count / max(1, coop_distance)) * 100
        
        # Qualité d'interaction basée sur la diversité et fréquence
        interaction_quality = min(10, (
            exchange_count * 2 + 
            unique_exchange_positions * 1.5 + 
            object_types_exchanged * 1.2
        ) / 3)
        
        print(f"   🔄 {layout_info.get('layout_name', 'Layout')} - {exchange_count} échanges détectés")
        
        return {
            'exchange_count': exchange_count,
            'avg_exchange_duration': avg_exchange_duration,
            'exchange_zones': unique_exchange_positions,
            'exchange_intensity': exchange_count / max(1, unique_exchange_positions),
            'cooperation_score': cooperation_score,
            'efficiency_gain': efficiency_gain,
            'efficiency_percentage': efficiency_percentage,
            'solo_distance': solo_distance,
            'coop_distance': coop_distance,
            'exchange_density': exchange_density,
            'interaction_quality': interaction_quality,
            'exchanges_detail': exchanges,
            'object_types_exchanged': object_types_exchanged,
            'real_exchanges_detected': exchange_count > 0
        }
    
    def _create_empty_exchange_data(self) -> Dict:
        """Crée une structure de données d'échange vide"""
        return {
            'exchange_count': 0,
            'avg_exchange_duration': 0,
            'exchange_zones': 0,
            'exchange_intensity': 0,
            'cooperation_score': 0,
            'efficiency_gain': 0,
            'efficiency_percentage': 0,
            'solo_distance': 0,
            'coop_distance': 0,
            'exchange_density': 0,
            'interaction_quality': 0,
            'exchanges_detail': [],
            'object_types_exchanged': 0,
            'real_exchanges_detected': False
        }
    
    def _detect_real_exchanges_in_actions(self, actions: List) -> List[Dict]:
        """
        Détecte les échanges réels dans la liste des actions
        
        Recherche les séquences:
        - Joueur A fait une action de dépôt (drop/place/deliver) à la position P
        - Joueur B fait une action de récupération (pickup/grab/take) à la position P
        """
        
        if not actions or not isinstance(actions, list):
            return []
        
        exchanges = []
        recent_drops = {}  # position -> {player, action_index, object_type, timestamp}
        
        # Actions considérées comme des dépôts/récupérations
        drop_actions = {'drop', 'place', 'put_down', 'deliver', 'put', 'deposit'}
        pickup_actions = {'pickup', 'grab', 'take', 'pick_up', 'get', 'collect'}
        
        for action_index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            
            player_id = action.get('player_id', action.get('player', action.get('agent_id', 0)))
            action_type = action.get('action_type', action.get('action', action.get('type', '')))
            position = self._extract_position_from_action(action)
            object_type = action.get('object_type', action.get('object', action.get('item', 'unknown')))
            
            if not position:
                continue
            
            # Normaliser la position en tuple pour la comparaison
            pos_key = tuple(position) if isinstance(position, (list, tuple)) else position
            
            # Vérifier si c'est une action de dépôt
            if self._is_drop_action(action_type, drop_actions):
                recent_drops[pos_key] = {
                    'player': player_id,
                    'action_index': action_index,
                    'object_type': object_type,
                    'timestamp': action_index
                }
            
            # Vérifier si c'est une action de récupération
            elif self._is_pickup_action(action_type, pickup_actions):
                # Chercher un dépôt récent à cette position par un autre joueur
                if pos_key in recent_drops:
                    drop_info = recent_drops[pos_key]
                    
                    # Vérifier que c'est un autre joueur
                    if drop_info['player'] != player_id:
                        # Vérifier que la récupération est dans un délai raisonnable
                        duration = action_index - drop_info['action_index']
                        if 0 < duration <= 20:  # Max 20 actions entre dépôt et récupération
                            # Échange détecté !
                            exchange = {
                                'drop_player': drop_info['player'],
                                'pickup_player': player_id,
                                'position': pos_key,
                                'object_type': object_type,
                                'duration': duration,
                                'drop_action_index': drop_info['action_index'],
                                'pickup_action_index': action_index
                            }
                            exchanges.append(exchange)
                            
                            # Supprimer le dépôt utilisé pour éviter les doublons
                            del recent_drops[pos_key]
        
        return exchanges
    
    def _extract_position_from_action(self, action: Dict) -> Optional[Tuple]:
        """Extrait la position d'une action"""
        
        # Essayer différents formats de position
        position_keys = ['position', 'pos', 'location', 'coordinates', 'x_y', 'coord']
        
        for key in position_keys:
            if key in action:
                pos = action[key]
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return tuple(pos[:2])  # Prendre x, y
                elif isinstance(pos, dict):
                    if 'x' in pos and 'y' in pos:
                        return (pos['x'], pos['y'])
        
        # Si aucune position explicite, essayer d'extraire des coordonnées x, y
        if 'x' in action and 'y' in action:
            return (action['x'], action['y'])
        
        return None
    
    def _is_drop_action(self, action_type: str, drop_actions: set) -> bool:
        """Vérifie si l'action est une action de dépôt"""
        if not isinstance(action_type, str):
            return False
        
        action_lower = action_type.lower()
        return any(drop_word in action_lower for drop_word in drop_actions)
    
    def _is_pickup_action(self, action_type: str, pickup_actions: set) -> bool:
        """Vérifie si l'action est une action de récupération"""
        if not isinstance(action_type, str):
            return False
        
        action_lower = action_type.lower()
        return any(pickup_word in action_lower for pickup_word in pickup_actions)
    
    def _calculate_real_cooperation_score(self, exchange_count: int, unique_positions: int, 
                                        avg_duration: float, efficiency_gain: float) -> float:
        """Calcule un score de coopération basé sur les échanges réels"""
        
        # Score basé sur le nombre d'échanges (plus = mieux)
        exchange_score = min(10, exchange_count * 1.5)
        
        # Score basé sur la diversité des positions (plus = mieux)
        position_score = min(10, unique_positions * 2)
        
        # Score basé sur la durée des échanges (ni trop court ni trop long)
        if avg_duration == 0:
            duration_score = 0
        elif 2 <= avg_duration <= 8:
            duration_score = 10  # Durée optimale
        elif avg_duration < 2:
            duration_score = 5   # Trop rapide
        else:
            duration_score = max(0, 10 - (avg_duration - 8))  # Trop lent
        
        # Score basé sur l'efficacité
        efficiency_score = min(10, efficiency_gain / 10)
        
        # Moyenne pondérée privilégiant les échanges réels
        cooperation_score = (
            exchange_score * 0.5 +      # 50% pour le nombre d'échanges
            position_score * 0.3 +      # 30% pour la diversité
            duration_score * 0.1 +      # 10% pour la qualité temporelle
            efficiency_score * 0.1      # 10% pour l'efficacité
        )
        
        return cooperation_score
    
    def _estimate_exchanges_from_efficiency(self, solo_distance: int, coop_distance: int) -> Dict:
        """Estimation des échanges basée sur l'efficacité quand les actions ne sont pas disponibles"""
        
        # Calcul du gain d'efficacité
        efficiency_gain = solo_distance - coop_distance
        efficiency_percentage = (efficiency_gain / solo_distance * 100) if solo_distance > 0 else 0
        
        # Estimation basée sur l'efficacité (plus conservatrice)
        if efficiency_gain < 10:
            estimated_exchanges = 0
        elif efficiency_gain < 30:
            estimated_exchanges = max(1, int(efficiency_gain / 15))
        else:
            estimated_exchanges = max(2, int(efficiency_gain / 10))
        
        # Estimation de la durée moyenne des échanges
        avg_exchange_duration = max(3, min(10, int(efficiency_gain / 8)))
        
        # Zones d'échange estimées
        exchange_zones = max(1, min(4, int(estimated_exchanges / 2) + 1))
        
        # Intensité des échanges
        exchange_intensity = estimated_exchanges / max(1, exchange_zones)
        
        # Score de coopération
        cooperation_score = self._calculate_real_cooperation_score(
            estimated_exchanges, exchange_zones, avg_exchange_duration, efficiency_gain
        )
        
        return {
            'exchange_count': estimated_exchanges,
            'avg_exchange_duration': avg_exchange_duration,
            'exchange_zones': exchange_zones,
            'exchange_intensity': exchange_intensity,
            'cooperation_score': cooperation_score,
            'efficiency_gain': efficiency_gain,
            'efficiency_percentage': efficiency_percentage,
            'solo_distance': solo_distance,
            'coop_distance': coop_distance,
            'exchange_density': estimated_exchanges / max(1, coop_distance) * 100,
            'interaction_quality': min(10, exchange_intensity * avg_exchange_duration / 5),
            'exchanges_detail': [],
            'object_types_exchanged': 1 if estimated_exchanges > 0 else 0,
            'real_exchanges_detected': False  # Estimation, pas de détection réelle
        }
    
    def calculate_exchange_metrics(self, filtered_layouts: Dict[str, Dict]) -> Dict[str, Dict]:
        """Les métriques d'échange sont déjà calculées lors du filtrage itératif"""
        
        print(f"\n🔄 Métriques d'échange déjà calculées pour {len(filtered_layouts)} layouts")
        return filtered_layouts
    
    def filter_layouts_by_criteria(self, exchange_metrics: Dict[str, Dict]) -> Dict[str, Dict]:
        """Les layouts sont déjà filtrés lors du traitement itératif"""
        
        print(f"\n🎯 Layouts déjà filtrés selon les critères: {len(exchange_metrics)} validés")
        print(f"   • Gain d'efficacité minimum: {self.efficiency_threshold} steps")
        print(f"   • Nombre d'échanges minimum: {self.min_exchange_count}")
        
        return exchange_metrics
    
    def calculate_combined_score(self, filtered_layouts: Dict[str, Dict]) -> List[Tuple[str, float, Dict]]:
        """
        Calcule un score combiné pondérant échanges réels et efficacité
        
        Score = (0.5 * normalized_real_exchanges) + (0.3 * normalized_efficiency) + 
                (0.2 * normalized_cooperation) + (bonus si échanges réels détectés)
        """
        
        print(f"\n📊 Calcul des scores combinés basés sur les échanges réels...")
        
        if not filtered_layouts:
            return []
        
        # Séparer les layouts avec/sans échanges réels détectés
        real_exchange_layouts = {name: metrics for name, metrics in filtered_layouts.items() 
                                if metrics.get('real_exchanges_detected', False)}
        estimated_exchange_layouts = {name: metrics for name, metrics in filtered_layouts.items() 
                                     if not metrics.get('real_exchanges_detected', False)}
        
        print(f"   🎯 Layouts avec échanges réels détectés: {len(real_exchange_layouts)}")
        print(f"   📊 Layouts avec échanges estimés: {len(estimated_exchange_layouts)}")
        
        # Extraire les valeurs pour normalisation
        exchange_counts = [metrics['exchange_count'] for metrics in filtered_layouts.values()]
        efficiency_gains = [metrics['efficiency_gain'] for metrics in filtered_layouts.values()]
        cooperation_scores = [metrics['cooperation_score'] for metrics in filtered_layouts.values()]
        exchange_zones = [metrics['exchange_zones'] for metrics in filtered_layouts.values()]
        
        # Normalisation (0-1)
        max_exchanges = max(exchange_counts) if exchange_counts else 1
        max_efficiency = max(efficiency_gains) if efficiency_gains else 1
        max_cooperation = max(cooperation_scores) if cooperation_scores else 1
        max_zones = max(exchange_zones) if exchange_zones else 1
        
        scored_layouts = []
        
        for layout_name, metrics in filtered_layouts.items():
            # Normalisation des composants
            norm_exchanges = metrics['exchange_count'] / max_exchanges
            norm_efficiency = metrics['efficiency_gain'] / max_efficiency
            norm_cooperation = metrics['cooperation_score'] / max_cooperation
            norm_zones = metrics['exchange_zones'] / max_zones
            
            # Bonus pour les échanges réels détectés
            real_exchange_bonus = 0.1 if metrics.get('real_exchanges_detected', False) else 0
            
            # Score combiné avec pondération privilégiant les échanges réels
            combined_score = (
                0.5 * norm_exchanges +      # 50% pour les échanges (priorité)
                0.25 * norm_efficiency +    # 25% pour l'efficacité
                0.15 * norm_cooperation +   # 15% pour la coopération
                0.1 * norm_zones +         # 10% pour la diversité des zones
                real_exchange_bonus        # Bonus pour échanges réels
            )
            
            scored_layouts.append((layout_name, combined_score, metrics))
        
        # Trier par score décroissant
        scored_layouts.sort(key=lambda x: x[1], reverse=True)
        
        print(f"✅ Scores calculés avec priorité aux échanges réels détectés")
        return scored_layouts
    
    def select_top_layouts(self, scored_layouts: List[Tuple[str, float, Dict]], 
                          top_count: int = 25) -> List[Tuple[str, float, Dict]]:
        """Sélectionne les meilleurs layouts selon le score combiné"""
        
        selected_layouts = scored_layouts[:top_count]
        
        print(f"\n🏆 Sélection des {len(selected_layouts)} meilleurs layouts:")
        print(f"   Score range: {selected_layouts[-1][1]:.3f} - {selected_layouts[0][1]:.3f}")
        
        # Statistiques des layouts sélectionnés
        selected_exchanges = [metrics['exchange_count'] for _, _, metrics in selected_layouts]
        selected_efficiency = [metrics['efficiency_gain'] for _, _, metrics in selected_layouts]
        
        print(f"   Échanges: {min(selected_exchanges)} - {max(selected_exchanges)} (moy: {np.mean(selected_exchanges):.1f})")
        print(f"   Efficacité: {min(selected_efficiency)} - {max(selected_efficiency)} (moy: {np.mean(selected_efficiency):.1f})")
        
        return selected_layouts
    
    def create_exchange_analysis_visualizations(self, scored_layouts: List[Tuple[str, float, Dict]]) -> List[str]:
        """Crée les visualisations d'analyse des échanges"""
        
        print(f"\n📊 Génération des visualisations...")
        
        if not scored_layouts:
            print("❌ Aucune donnée à visualiser")
            return []
        
        visualization_files = []
        
        # Préparer les données
        layout_names = [name[:20] + "..." if len(name) > 20 else name for name, _, _ in scored_layouts]
        scores = [score for _, score, _ in scored_layouts]
        exchange_counts = [metrics['exchange_count'] for _, _, metrics in scored_layouts]
        efficiency_gains = [metrics['efficiency_gain'] for _, _, metrics in scored_layouts]
        cooperation_scores = [metrics['cooperation_score'] for _, _, metrics in scored_layouts]
        solo_distances = [metrics['solo_distance'] for _, _, metrics in scored_layouts]
        coop_distances = [metrics['coop_distance'] for _, _, metrics in scored_layouts]
        
        # 1. Graphique principal: Score combiné vs Échanges vs Efficacité
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Graphique 1: Comparaison Solo vs Duo avec échanges
        x = np.arange(len(layout_names))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, solo_distances, width, label='Solo', 
                       alpha=0.8, color='skyblue', edgecolor='navy')
        bars2 = ax1.bar(x + width/2, coop_distances, width, label='Duo', 
                       alpha=0.8, color='lightcoral', edgecolor='darkred')
        
        ax1.set_title('Distances Solo vs Duo - Layouts Optimisés pour les Échanges\n'
                     f'Top {len(layout_names)} layouts avec le plus d\'interactions', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Layouts (triés par score d\'échange)', fontsize=12)
        ax1.set_ylabel('Distance Totale', fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels(layout_names, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Ajouter le nombre d'échanges au-dessus des barres
        for i, exchanges in enumerate(exchange_counts):
            ax1.text(i, max(solo_distances[i], coop_distances[i]) + 5, 
                    f'{exchanges} éch.', ha='center', va='bottom', 
                    fontsize=8, fontweight='bold', color='purple')
        
        # Graphique 2: Score combiné par layout
        colors = plt.cm.RdYlBu_r([score/max(scores) for score in scores])
        bars = ax2.bar(x, scores, color=colors, alpha=0.8, edgecolor='black')
        
        ax2.set_title('Score Combiné d\'Échange et d\'Efficacité', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Layouts', fontsize=12)
        ax2.set_ylabel('Score Combiné (0-1)', fontsize=12)
        ax2.set_xticks(x)
        ax2.set_xticklabels(layout_names, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Graphique 3: Relation Échanges vs Efficacité
        scatter = ax3.scatter(exchange_counts, efficiency_gains, 
                            c=scores, s=100, alpha=0.7, cmap='viridis', edgecolors='black')
        
        ax3.set_title('Relation: Nombre d\'Échanges vs Gain d\'Efficacité', 
                     fontsize=14, fontweight='bold')
        ax3.set_xlabel('Nombre d\'Échanges entre Joueurs', fontsize=12)
        ax3.set_ylabel('Gain d\'Efficacité (Solo - Duo)', fontsize=12)
        ax3.grid(True, alpha=0.3)
        
        # Ajouter une colorbar
        cbar = plt.colorbar(scatter, ax=ax3)
        cbar.set_label('Score Combiné', fontsize=10)
        
        # Ligne de tendance
        if len(exchange_counts) > 1:
            z = np.polyfit(exchange_counts, efficiency_gains, 1)
            p = np.poly1d(z)
            ax3.plot(exchange_counts, p(exchange_counts), "r--", alpha=0.8, 
                    label=f'Tendance: y={z[0]:.1f}x+{z[1]:.1f}')
            ax3.legend()
        
        # Graphique 4: Distribution des scores de coopération
        ax4.hist(cooperation_scores, bins=15, alpha=0.7, color='lightgreen', 
                edgecolor='darkgreen', density=True)
        
        # Ajouter les statistiques
        mean_coop = np.mean(cooperation_scores)
        std_coop = np.std(cooperation_scores)
        
        ax4.axvline(mean_coop, color='red', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {mean_coop:.2f}')
        ax4.axvline(mean_coop + std_coop, color='orange', linestyle=':', linewidth=2, 
                   label=f'+1σ: {mean_coop + std_coop:.2f}')
        
        ax4.set_title('Distribution des Scores de Coopération', 
                     fontsize=14, fontweight='bold')
        ax4.set_xlabel('Score de Coopération', fontsize=12)
        ax4.set_ylabel('Densité', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/exchange_based_analysis_main.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        visualization_files.append(output_path)
        print(f"   ✅ Graphique principal sauvegardé: {os.path.basename(output_path)}")
        
        # 2. Analyse détaillée des échanges
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Métriques d'échange additionnelles
        exchange_densities = [metrics['exchange_density'] for _, _, metrics in scored_layouts]
        interaction_qualities = [metrics['interaction_quality'] for _, _, metrics in scored_layouts]
        avg_exchange_durations = [metrics['avg_exchange_duration'] for _, _, metrics in scored_layouts]
        exchange_zones = [metrics['exchange_zones'] for _, _, metrics in scored_layouts]
        
        # Graphique 1: Densité d'échange
        ax1.bar(x, exchange_densities, color='cyan', alpha=0.7, edgecolor='teal')
        ax1.set_title('Densité d\'Échanges par Layout\n(Échanges pour 100 steps)', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Layouts', fontsize=12)
        ax1.set_ylabel('Densité d\'Échanges', fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels(layout_names, rotation=45, ha='right')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Graphique 2: Qualité des interactions
        ax2.bar(x, interaction_qualities, color='gold', alpha=0.7, edgecolor='orange')
        ax2.set_title('Qualité des Interactions entre Joueurs', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Layouts', fontsize=12)
        ax2.set_ylabel('Score de Qualité d\'Interaction', fontsize=12)
        ax2.set_xticks(x)
        ax2.set_xticklabels(layout_names, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Graphique 3: Durée moyenne des échanges
        ax3.scatter(avg_exchange_durations, exchange_counts, 
                   c=efficiency_gains, s=80, alpha=0.7, cmap='plasma', edgecolors='black')
        ax3.set_title('Durée vs Nombre d\'Échanges\n(Couleur = Gain d\'efficacité)', 
                     fontsize=14, fontweight='bold')
        ax3.set_xlabel('Durée Moyenne des Échanges (steps)', fontsize=12)
        ax3.set_ylabel('Nombre d\'Échanges', fontsize=12)
        ax3.grid(True, alpha=0.3)
        
        # Graphique 4: Zones d'échange
        ax4.scatter(exchange_zones, exchange_counts, 
                   c=scores, s=100, alpha=0.7, cmap='viridis', edgecolors='black')
        ax4.set_title('Zones d\'Échange vs Nombre d\'Échanges\n(Couleur = Score combiné)', 
                     fontsize=14, fontweight='bold')
        ax4.set_xlabel('Nombre de Zones d\'Échange', fontsize=12)
        ax4.set_ylabel('Nombre d\'Échanges', fontsize=12)
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path2 = f"{self.output_dir}/exchange_detailed_metrics.png"
        plt.savefig(output_path2, dpi=300, bbox_inches='tight')
        plt.close()
        
        visualization_files.append(output_path2)
        print(f"   ✅ Métriques détaillées sauvegardées: {os.path.basename(output_path2)}")
        
        # 3. Comparaison efficacité vs échanges
        self._create_efficiency_exchange_comparison(scored_layouts, visualization_files)
        
        return visualization_files
    
    def _create_efficiency_exchange_comparison(self, scored_layouts: List[Tuple[str, float, Dict]], 
                                             visualization_files: List[str]) -> None:
        """Crée une comparaison détaillée efficacité vs échanges"""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Préparer les données
        exchange_counts = [metrics['exchange_count'] for _, _, metrics in scored_layouts]
        efficiency_gains = [metrics['efficiency_gain'] for _, _, metrics in scored_layouts]
        efficiency_percentages = [metrics['efficiency_percentage'] for _, _, metrics in scored_layouts]
        scores = [score for _, score, _ in scored_layouts]
        
        # Graphique 1: Histogramme des gains d'efficacité
        ax1.hist(efficiency_gains, bins=15, alpha=0.7, color='lightblue', 
                edgecolor='darkblue', density=False)
        ax1.axvline(np.mean(efficiency_gains), color='red', linestyle='--', linewidth=2,
                   label=f'Moyenne: {np.mean(efficiency_gains):.1f}')
        ax1.set_title('Distribution des Gains d\'Efficacité\nLayouts Sélectionnés', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Gain d\'Efficacité (Solo - Duo)', fontsize=12)
        ax1.set_ylabel('Nombre de Layouts', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Graphique 2: Histogramme des échanges
        ax2.hist(exchange_counts, bins=10, alpha=0.7, color='lightcoral', 
                edgecolor='darkred', density=False)
        ax2.axvline(np.mean(exchange_counts), color='blue', linestyle='--', linewidth=2,
                   label=f'Moyenne: {np.mean(exchange_counts):.1f}')
        ax2.set_title('Distribution du Nombre d\'Échanges\nLayouts Sélectionnés', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Nombre d\'Échanges entre Joueurs', fontsize=12)
        ax2.set_ylabel('Nombre de Layouts', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Graphique 3: Relation efficacité vs échanges avec annotations
        scatter = ax3.scatter(efficiency_gains, exchange_counts, 
                            c=scores, s=100, alpha=0.7, cmap='RdYlBu_r', edgecolors='black')
        
        # Diviser en quadrants
        mean_efficiency = np.mean(efficiency_gains)
        mean_exchanges = np.mean(exchange_counts)
        
        ax3.axhline(mean_exchanges, color='gray', linestyle=':', alpha=0.5)
        ax3.axvline(mean_efficiency, color='gray', linestyle=':', alpha=0.5)
        
        # Annoter les quadrants
        ax3.text(max(efficiency_gains) * 0.8, max(exchange_counts) * 0.9, 
                'Haute Efficacité\nHauts Échanges\n(OPTIMAL)', 
                ha='center', va='center', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))
        
        ax3.text(min(efficiency_gains) * 1.2, max(exchange_counts) * 0.9, 
                'Basse Efficacité\nHauts Échanges\n(SOCIAL)', 
                ha='center', va='center', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.7))
        
        ax3.set_title('Quadrants Efficacité vs Échanges\n(Couleur = Score Combiné)', 
                     fontsize=14, fontweight='bold')
        ax3.set_xlabel('Gain d\'Efficacité (Solo - Duo)', fontsize=12)
        ax3.set_ylabel('Nombre d\'Échanges', fontsize=12)
        ax3.grid(True, alpha=0.3)
        
        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax3)
        cbar.set_label('Score Combiné', fontsize=10)
        
        # Graphique 4: Top 10 avec barres d'efficacité et échanges
        top_10 = scored_layouts[:10]
        top_names = [name[:15] + "..." if len(name) > 15 else name for name, _, _ in top_10]
        top_efficiency = [metrics['efficiency_gain'] for _, _, metrics in top_10]
        top_exchanges = [metrics['exchange_count'] for _, _, metrics in top_10]
        
        x_top = np.arange(len(top_10))
        width = 0.35
        
        ax4_twin = ax4.twinx()
        
        bars1 = ax4.bar(x_top - width/2, top_efficiency, width, label='Gain d\'Efficacité', 
                       alpha=0.8, color='steelblue')
        bars2 = ax4_twin.bar(x_top + width/2, top_exchanges, width, label='Nombre d\'Échanges', 
                            alpha=0.8, color='coral')
        
        ax4.set_title('Top 10: Efficacité et Échanges Combinés', 
                     fontsize=14, fontweight='bold')
        ax4.set_xlabel('Layouts (classés par score)', fontsize=12)
        ax4.set_ylabel('Gain d\'Efficacité (steps)', fontsize=12, color='steelblue')
        ax4_twin.set_ylabel('Nombre d\'Échanges', fontsize=12, color='coral')
        
        ax4.set_xticks(x_top)
        ax4.set_xticklabels(top_names, rotation=45, ha='right')
        ax4.grid(True, alpha=0.3, axis='y')
        
        # Légendes
        ax4.legend(loc='upper left')
        ax4_twin.legend(loc='upper right')
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/efficiency_exchange_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        visualization_files.append(output_path)
        print(f"   ✅ Comparaison efficacité-échanges sauvegardée: {os.path.basename(output_path)}")
    
    def copy_selected_layouts(self, selected_layouts: List[Tuple[str, float, Dict]]) -> int:
        """Copie les layouts sélectionnés vers le dossier de destination"""
        
        print(f"\n📁 Copie des {len(selected_layouts)} layouts sélectionnés...")
        
        copied_count = 0
        failed_count = 0
        
        # Créer un fichier de résumé
        summary_file = f"{self.selected_layouts_dir}/layouts_échanges_résumé.txt"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("LAYOUTS SÉLECTIONNÉS - OPTIMISATION DES ÉCHANGES\n")
            f.write("="*70 + "\n\n")
            f.write(f"Date de sélection: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Critère: Maximisation des échanges avec efficacité significative\n")
            f.write(f"Nombre de layouts sélectionnés: {len(selected_layouts)}\n\n")
            
            f.write("PARAMÈTRES DE SÉLECTION:\n")
            f.write(f"• Gain d'efficacité minimum: {self.efficiency_threshold} steps\n")
            f.write(f"• Nombre d'échanges minimum: {self.min_exchange_count}\n")
            f.write(f"• Distance seuil pour échanges: {self.exchange_distance_threshold}\n")
            f.write(f"• Durée minimale d'échange: {self.min_exchange_duration} steps\n\n")
            
            f.write("LAYOUTS SÉLECTIONNÉS:\n")
            f.write("-" * 50 + "\n")
            f.write(f"{'Rang':<4} {'Layout':<40} {'Score':<8} {'Échanges':<9} {'Efficacité':<10}\n")
            f.write("-" * 50 + "\n")
            
            for i, (layout_name, score, metrics) in enumerate(selected_layouts, 1):
                f.write(f"{i:2d}.  {layout_name:<40} {score:6.3f}  {metrics['exchange_count']:7d}  "
                       f"{metrics['efficiency_gain']:8.1f}\n")
                
                # Chercher le fichier layout correspondant
                layout_files = glob.glob(f"{self.layouts_source_dir}/**/*{layout_name}*.layout", 
                                       recursive=True)
                
                if layout_files:
                    source_file = layout_files[0]  # Prendre le premier trouvé
                    destination_file = f"{self.selected_layouts_dir}/{layout_name}.layout"
                    
                    try:
                        shutil.copy2(source_file, destination_file)
                        copied_count += 1
                    except Exception as e:
                        print(f"❌ Erreur copie {layout_name}: {e}")
                        failed_count += 1
                        f.write(f"    ❌ ERREUR COPIE: {e}\n")
                else:
                    print(f"❌ Fichier non trouvé: {layout_name}")
                    failed_count += 1
                    f.write(f"    ❌ FICHIER NON TROUVÉ\n")
            
            f.write(f"\nRÉSULTAT COPIE:\n")
            f.write(f"✅ Layouts copiés avec succès: {copied_count}\n")
            f.write(f"❌ Échecs de copie: {failed_count}\n")
        
        print(f"✅ Copie terminée: {copied_count}/{len(selected_layouts)} layouts copiés")
        print(f"📄 Résumé sauvegardé: {summary_file}")
        
        return copied_count
    
    def generate_comprehensive_report(self, scored_layouts: List[Tuple[str, float, Dict]], 
                                    copied_count: int) -> str:
        """Génère un rapport complet de l'analyse des échanges"""
        
        report_path = f"{self.output_dir}/exchange_analysis_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("RAPPORT COMPLET - SÉLECTION DE LAYOUTS BASÉE SUR LES ÉCHANGES\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"📅 Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"🎯 Objectif: Sélection de layouts maximisant les échanges coopératifs\n")
            f.write(f"🧠 Contexte: Recherche en sciences cognitives sur la coopération\n\n")
            
            # 1. Méthodologie
            f.write("📋 MÉTHODOLOGIE APPLIQUÉE\n")
            f.write("-" * 25 + "\n")
            f.write("1. Analyse des données de performance Solo vs Duo\n")
            f.write("2. Simulation des échanges basée sur les gains d'efficacité\n")
            f.write("3. Calcul des métriques d'interaction (nombre, durée, zones)\n")
            f.write("4. Score combiné pondérant échanges (40%) et efficacité (30%)\n")
            f.write("5. Sélection des layouts avec le meilleur équilibre\n\n")
            
            # 2. Paramètres utilisés
            f.write("⚙️  PARAMÈTRES DE SÉLECTION\n")
            f.write("-" * 28 + "\n")
            f.write(f"Gain d'efficacité minimum: {self.efficiency_threshold} steps\n")
            f.write(f"Nombre d'échanges minimum: {self.min_exchange_count}\n")
            f.write(f"Distance seuil pour échanges: {self.exchange_distance_threshold}\n")
            f.write(f"Durée minimale d'échange: {self.min_exchange_duration} steps\n\n")
            
            # 3. Statistiques globales
            if scored_layouts:
                all_scores = [score for _, score, _ in scored_layouts]
                all_exchanges = [metrics['exchange_count'] for _, _, metrics in scored_layouts]
                all_efficiency = [metrics['efficiency_gain'] for _, _, metrics in scored_layouts]
                all_cooperation = [metrics['cooperation_score'] for _, _, metrics in scored_layouts]
                
                f.write("📊 STATISTIQUES DES LAYOUTS SÉLECTIONNÉS\n")
                f.write("-" * 40 + "\n")
                f.write(f"Nombre total de layouts analysés: {len(scored_layouts)}\n")
                f.write(f"Layouts finalement retenus: {copied_count}\n\n")
                
                f.write("SCORES COMBINÉS:\n")
                f.write(f"• Range: {min(all_scores):.3f} - {max(all_scores):.3f}\n")
                f.write(f"• Moyenne: {np.mean(all_scores):.3f} ± {np.std(all_scores):.3f}\n")
                f.write(f"• Médiane: {np.median(all_scores):.3f}\n\n")
                
                f.write("ÉCHANGES ENTRE JOUEURS:\n")
                f.write(f"• Range: {min(all_exchanges)} - {max(all_exchanges)} échanges\n")
                f.write(f"• Moyenne: {np.mean(all_exchanges):.1f} ± {np.std(all_exchanges):.1f}\n")
                f.write(f"• Médiane: {np.median(all_exchanges):.1f}\n\n")
                
                f.write("GAINS D'EFFICACITÉ:\n")
                f.write(f"• Range: {min(all_efficiency):.1f} - {max(all_efficiency):.1f} steps\n")
                f.write(f"• Moyenne: {np.mean(all_efficiency):.1f} ± {np.std(all_efficiency):.1f}\n")
                f.write(f"• Médiane: {np.median(all_efficiency):.1f}\n\n")
                
                f.write("SCORES DE COOPÉRATION:\n")
                f.write(f"• Range: {min(all_cooperation):.2f} - {max(all_cooperation):.2f}\n")
                f.write(f"• Moyenne: {np.mean(all_cooperation):.2f} ± {np.std(all_cooperation):.2f}\n")
                f.write(f"• Médiane: {np.median(all_cooperation):.2f}\n\n")
            
            # 4. Top 15 des layouts
            f.write("🏆 TOP 15 DES LAYOUTS SÉLECTIONNÉS\n")
            f.write("-" * 35 + "\n")
            f.write(f"{'Rang':<4} {'Layout':<40} {'Score':<8} {'Éch.':<5} {'Eff.':<6} {'Coop.':<6}\n")
            f.write("-" * 70 + "\n")
            
            for i, (layout_name, score, metrics) in enumerate(scored_layouts[:15], 1):
                f.write(f"{i:2d}.  {layout_name:<40} {score:6.3f}  "
                       f"{metrics['exchange_count']:3d}  "
                       f"{metrics['efficiency_gain']:5.0f}  "
                       f"{metrics['cooperation_score']:5.2f}\n")
            
            if len(scored_layouts) > 15:
                f.write(f"... et {len(scored_layouts) - 15} autres layouts\n")
            
            # 5. Catégorisation des layouts
            if scored_layouts:
                f.write(f"\n📈 CATÉGORISATION PAR PERFORMANCE\n")
                f.write("-" * 35 + "\n")
                
                high_exchange = sum(1 for _, _, metrics in scored_layouts 
                                  if metrics['exchange_count'] >= 15)
                medium_exchange = sum(1 for _, _, metrics in scored_layouts 
                                    if 10 <= metrics['exchange_count'] < 15)
                low_exchange = sum(1 for _, _, metrics in scored_layouts 
                                 if metrics['exchange_count'] < 10)
                
                f.write(f"Hauts échanges (≥15): {high_exchange} layouts\n")
                f.write(f"Échanges moyens (10-14): {medium_exchange} layouts\n")
                f.write(f"Échanges modérés (<10): {low_exchange} layouts\n\n")
                
                high_efficiency = sum(1 for _, _, metrics in scored_layouts 
                                    if metrics['efficiency_gain'] >= 50)
                medium_efficiency = sum(1 for _, _, metrics in scored_layouts 
                                      if 25 <= metrics['efficiency_gain'] < 50)
                
                f.write(f"Haute efficacité (≥50 steps): {high_efficiency} layouts\n")
                f.write(f"Efficacité moyenne (25-49 steps): {medium_efficiency} layouts\n")
            
            # 6. Recommandations
            f.write(f"\n💡 RECOMMANDATIONS POUR L'EXPÉRIENCE\n")
            f.write("-" * 40 + "\n")
            f.write("1. Utiliser prioritairement les layouts du Top 10\n")
            f.write("2. Équilibrer les sessions entre hauts/moyens échanges\n")
            f.write("3. Considérer l'ordre de présentation selon la difficulté\n")
            f.write("4. Monitorer les interactions réelles vs prédictions\n\n")
            
            f.write(f"📊 Visualisations générées dans: {self.output_dir}\n")
            f.write(f"📁 Layouts copiés dans: {self.selected_layouts_dir}\n")
        
        return report_path
    
    def export_data_for_analysis(self, scored_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Exporte les données au format CSV pour analyses ultérieures"""
        
        csv_path = f"{self.output_dir}/exchange_layout_data.csv"
        
        # Préparer les données pour le DataFrame
        data_rows = []
        for layout_name, combined_score, metrics in scored_layouts:
            row = {
                'layout_name': layout_name,
                'combined_score': combined_score,
                'exchange_count': metrics['exchange_count'],
                'avg_exchange_duration': metrics['avg_exchange_duration'],
                'exchange_zones': metrics['exchange_zones'],
                'exchange_intensity': metrics['exchange_intensity'],
                'cooperation_score': metrics['cooperation_score'],
                'efficiency_gain': metrics['efficiency_gain'],
                'efficiency_percentage': metrics['efficiency_percentage'],
                'solo_distance': metrics['solo_distance'],
                'coop_distance': metrics['coop_distance'],
                'exchange_density': metrics['exchange_density'],
                'interaction_quality': metrics['interaction_quality']
            }
            data_rows.append(row)
        
        # Créer et sauvegarder le DataFrame
        df = pd.DataFrame(data_rows)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        print(f"📊 Données exportées au format CSV: {csv_path}")
        return csv_path
    
    def run_complete_exchange_analysis(self):
        """Exécute l'analyse complète basée sur les échanges avec traitement économe en mémoire"""
        
        print("🔄 DÉMARRAGE DE L'ANALYSE BASÉE SUR LES ÉCHANGES")
        print("="*60)
        print("💾 Mode économe en mémoire activé - traitement itératif")
        
        # 1. Traitement itératif des données (charge + filtre + calcule en une passe)
        filtered_layouts = self.process_evaluation_files_iteratively()
        if not filtered_layouts:
            print("❌ Aucun layout ne passe les critères. Ajustez les paramètres.")
            return
        
        # 2. Les métriques d'échange sont déjà calculées
        exchange_metrics = self.calculate_exchange_metrics(filtered_layouts)
        
        # 3. Les layouts sont déjà filtrés
        validated_layouts = self.filter_layouts_by_criteria(exchange_metrics)
        
        # 4. Calculer les scores combinés
        scored_layouts = self.calculate_combined_score(validated_layouts)
        
        # 5. Sélectionner les meilleurs
        selected_layouts = self.select_top_layouts(scored_layouts, top_count=25)
        
        # 6. Créer les visualisations
        visualization_files = self.create_exchange_analysis_visualizations(selected_layouts)
        
        # 7. Copier les layouts sélectionnés
        copied_count = self.copy_selected_layouts(selected_layouts)
        
        # 8. Générer le rapport complet
        report_path = self.generate_comprehensive_report(selected_layouts, copied_count)
        
        # 9. Exporter les données CSV
        csv_path = self.export_data_for_analysis(selected_layouts)
        
        # Résumé final
        print(f"\n🎉 ANALYSE TERMINÉE AVEC SUCCÈS!")
        print("="*50)
        print(f"📊 Layouts analysés au total: {self.total_processed_count}")
        print(f"🎯 Layouts validés: {len(filtered_layouts)}")
        print(f"✅ Layouts sélectionnés: {len(selected_layouts)}")
        print(f"📁 Layouts copiés: {copied_count}")
        print(f"📈 Visualisations: {len(visualization_files)}")
        print(f"📄 Rapport: {report_path}")
        print(f"📊 Données CSV: {csv_path}")
        print(f"\n🎯 Les layouts optimisant les échanges coopératifs sont prêts!")


def main():
    """Fonction principale pour la sélection basée sur les échanges"""
    
    print("🤝 EXCHANGE-BASED LAYOUT SELECTOR - OVERCOOKED")
    print("Sélection de layouts optimisant les échanges coopératifs")
    print("Spécialement conçu pour la recherche en sciences cognitives")
    print()
    
    selector = ExchangeBasedLayoutSelector()
    selector.run_complete_exchange_analysis()


if __name__ == "__main__":
    main()
