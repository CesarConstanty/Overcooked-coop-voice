#!/usr/bin/env python3
"""
layout_characterizer.py

Caractérisateur de layouts Overcooked basé sur les comportements des GreedyAgent.
Utilise les comparaisons comportementales pour identifier les caractéristiques des layouts.

OBJECTIF: Caractériser et classer les layouts selon les patterns comportementaux observés.
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
from pathlib import Path
import argparse
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns


class LayoutCharacterizer:
    """
    Caractérisateur de layouts basé sur les comportements comparatifs des GreedyAgent.
    
    MÉTHODES DE CARACTÉRISATION POSSIBLES:
    =====================================
    
    1. CARACTÉRISATION STRUCTURELLE:
       - Dimensions et densité
       - Distribution des éléments (pots, distributeurs, zones de service)
       - Connectivité et accessibilité
       - Complexité géométrique
    
    2. CARACTÉRISATION COMPORTEMENTALE:
       - Patterns de mouvement des agents
       - Efficacité des trajectoires
       - Points de congestion et goulots d'étranglement
       - Zones d'activité intensive
    
    3. CARACTÉRISATION PAR PERFORMANCE:
       - Taux de réussite et temps de complétion
       - Efficacité relative entre modes (solo/coop)
       - Courbes d'apprentissage et consistance
       - Ratios effort/récompense
    
    4. CARACTÉRISATION PAR COORDINATION:
       - Nécessité de coordination
       - Types d'interactions requises
       - Séquencement des tâches
       - Spécialisation des rôles
    
    5. CARACTÉRISATION PAR STRATÉGIES:
       - Stratégies émergentes dominantes
       - Diversité des approches viables
       - Adaptabilité et flexibilité stratégique
       - Points de décision critiques
    
    6. CARACTÉRISATION PAR COMPLEXITÉ:
       - Charge cognitive estimée
       - Complexité décisionnelle
       - Prédictibilité des patterns
       - Variabilité des résultats
    
    7. CARACTÉRISATION COMPARATIVE:
       - Positionnement relatif par rapport aux autres layouts
       - Clusters de similarité
       - Outliers et cas spéciaux
       - Gradients de difficulté
    
    8. CARACTÉRISATION TEMPORELLE:
       - Évolution des métriques au cours du temps
       - Phases de jeu distinctes
       - Rythme et tempo de jeu
       - Points de transition critiques
    """
    
    def __init__(self):
        self.layout_data = {}
        self.characterization_results = {}
        self.comparison_matrix = {}
        
        print("🏗️ CARACTÉRISATEUR DE LAYOUTS OVERCOOKED")
        print("=" * 50)
        print("📋 MÉTHODES DE CARACTÉRISATION DISPONIBLES:")
        print("   1. Structurelle (géométrie, éléments)")
        print("   2. Comportementale (mouvement, efficacité)")
        print("   3. Performance (succès, temps, ratios)")
        print("   4. Coordination (interactions, rôles)")
        print("   5. Stratégique (émergence, adaptation)")
        print("   6. Complexité (cognitive, décisionnelle)")
        print("   7. Comparative (clusters, similarités)")
        print("   8. Temporelle (évolution, phases)")
        print("=" * 50)
    
    def load_layout_data(self, data_file: str) -> bool:
        """Charge les données de layouts à caractériser."""
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                self.layout_data = json.load(f)
            
            layouts_count = len(self.layout_data.get('layouts', {}))
            print(f"✅ Données chargées: {layouts_count} layouts")
            return True
            
        except Exception as e:
            print(f"❌ Erreur chargement données: {e}")
            return False
    
    # ========================================
    # 1. CARACTÉRISATION STRUCTURELLE
    # ========================================
    
    def characterize_structural_features(self, layout_name: str, layout_data: Dict) -> Dict:
        """
        Caractérise les features structurelles d'un layout.
        
        MÉTRIQUES STRUCTURELLES:
        - Dimensions et aire totale
        - Densité d'éléments
        - Distribution spatiale des éléments
        - Symétrie et équilibre spatial
        - Connectivité entre zones importantes
        - Distances critiques
        - Complexité géométrique
        """
        structural = {
            'dimensions': {},
            'element_distribution': {},
            'spatial_properties': {},
            'connectivity': {},
            'complexity_metrics': {}
        }
        
        layout_info = layout_data.get('layout_info', {})
        
        # Dimensions de base
        dimensions = layout_info.get('dimensions', {})
        width = dimensions.get('width', 0)
        height = dimensions.get('height', 0)
        
        structural['dimensions'] = {
            'width': width,
            'height': height,
            'total_area': width * height,
            'aspect_ratio': width / max(height, 1),
            'perimeter': 2 * (width + height)
        }
        
        # Distribution des éléments
        elements = layout_info.get('elements', {})
        total_cells = layout_info.get('total_cells', max(width * height, 1))
        
        structural['element_distribution'] = {
            'tomato_dispensers': elements.get('tomato_dispensers', 0),
            'onion_dispensers': elements.get('onion_dispensers', 0),
            'pots': elements.get('pots', 0),
            'serving_areas': elements.get('serving_areas', 0),
            'total_functional_elements': sum(elements.values()),
            'element_density': sum(elements.values()) / total_cells,
            'pot_to_dispenser_ratio': elements.get('pots', 0) / max(elements.get('tomato_dispensers', 0) + elements.get('onion_dispensers', 0), 1),
            'service_accessibility': elements.get('serving_areas', 0) / max(elements.get('pots', 0), 1)
        }
        
        # Propriétés spatiales avancées (à implémenter avec les données de position)
        structural['spatial_properties'] = self._calculate_spatial_properties(layout_info)
        
        # Connectivité (nécessite analyse de la carte)
        structural['connectivity'] = self._analyze_connectivity(layout_info)
        
        # Métriques de complexité
        structural['complexity_metrics'] = self._calculate_structural_complexity(layout_info, elements)
        
        return structural
    
    def _calculate_spatial_properties(self, layout_info: Dict) -> Dict:
        """Calcule les propriétés spatiales avancées."""
        # Placeholder pour l'analyse spatiale détaillée
        return {
            'symmetry_score': 0.5,  # À implémenter
            'balance_score': 0.5,   # À implémenter
            'clustering_coefficient': 0.5,  # À implémenter
            'note': 'Spatial analysis requires detailed layout map parsing'
        }
    
    def _analyze_connectivity(self, layout_info: Dict) -> Dict:
        """Analyse la connectivité entre éléments importants."""
        # Placeholder pour l'analyse de connectivité
        return {
            'path_efficiency': 0.5,  # À implémenter
            'bottleneck_score': 0.5,  # À implémenter
            'accessibility_score': 0.5,  # À implémenter
            'note': 'Connectivity analysis requires pathfinding implementation'
        }
    
    def _calculate_structural_complexity(self, layout_info: Dict, elements: Dict) -> Dict:
        """Calcule les métriques de complexité structurelle."""
        total_elements = sum(elements.values())
        total_cells = layout_info.get('total_cells', 1)
        
        # Complexité basée sur la variété d'éléments
        element_types = len([v for v in elements.values() if v > 0])
        element_variety = element_types / 4  # Normalisé sur 4 types d'éléments
        
        # Complexité basée sur la densité
        density_complexity = min(total_elements / total_cells, 1.0)
        
        # Score de complexité global
        overall_complexity = (element_variety + density_complexity) / 2
        
        return {
            'element_variety_score': element_variety,
            'density_complexity_score': density_complexity,
            'overall_structural_complexity': overall_complexity,
            'total_functional_elements': total_elements,
            'complexity_category': self._categorize_complexity(overall_complexity)
        }
    
    def _categorize_complexity(self, complexity_score: float) -> str:
        """Catégorise le niveau de complexité."""
        if complexity_score < 0.3:
            return 'simple'
        elif complexity_score < 0.6:
            return 'moderate'
        elif complexity_score < 0.8:
            return 'complex'
        else:
            return 'very_complex'
    
    # ========================================
    # 2. CARACTÉRISATION COMPORTEMENTALE
    # ========================================
    
    def characterize_behavioral_patterns(self, layout_name: str, layout_data: Dict) -> Dict:
        """
        Caractérise les patterns comportementaux observés sur ce layout.
        
        MÉTRIQUES COMPORTEMENTALES:
        - Patterns de mouvement dominants
        - Efficacité des trajectoires
        - Zones d'activité intensive
        - Fréquence des interactions
        - Spécialisation des agents
        - Adaptation comportementale
        """
        behavioral = {
            'movement_patterns': {},
            'interaction_patterns': {},
            'specialization_analysis': {},
            'efficiency_patterns': {},
            'adaptation_indicators': {}
        }
        
        # Analyser tous les modes comportementaux disponibles
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        for mode_name, mode_data in behavioral_modes.items():
            # Patterns de mouvement
            movement = self._analyze_movement_patterns(mode_data)
            behavioral['movement_patterns'][mode_name] = movement
            
            # Patterns d'interaction
            interaction = self._analyze_interaction_patterns(mode_data)
            behavioral['interaction_patterns'][mode_name] = interaction
            
            # Spécialisation
            specialization = self._analyze_agent_specialization(mode_data)
            behavioral['specialization_analysis'][mode_name] = specialization
            
            # Efficacité
            efficiency = self._analyze_behavioral_efficiency(mode_data)
            behavioral['efficiency_patterns'][mode_name] = efficiency
        
        # Analyse comparative entre modes
        behavioral['cross_mode_analysis'] = self._compare_behavioral_modes(behavioral_modes)
        
        # Indicateurs d'adaptation
        behavioral['adaptation_indicators'] = self._identify_adaptation_indicators(behavioral_modes)
        
        return behavioral
    
    def _analyze_movement_patterns(self, mode_data: Dict) -> Dict:
        """
        Analyse détaillée des patterns de mouvement pour un mode donné.
        
        MÉTRIQUES CALCULÉES:
        - Distance totale parcourue et efficacité
        - Zones d'activité intensive 
        - Patterns de déplacement répétitifs
        - Optimisation des trajectoires
        - Distribution spatiale des activités
        """
        patterns = mode_data.get('behavioral_patterns', {})
        performance = mode_data.get('performance_metrics', {})
        
        # Initialiser les métriques de mouvement
        movement_metrics = {
            'total_distance': {
                'agent_0': 0,
                'agent_1': 0,
                'total': 0,
                'balance': 0
            },
            'movement_efficiency': {
                'agent_0': 0,
                'agent_1': 0,
                'overall': 0
            },
            'spatial_distribution': {
                'agent_0_coverage': 0,
                'agent_1_coverage': 0,
                'overlap_ratio': 0,
                'zone_specialization': {}
            },
            'trajectory_optimization': {
                'path_efficiency_score': 0,
                'redundant_moves_ratio': 0,
                'optimal_path_adherence': 0
            },
            'activity_zones': {
                'hot_zones_count': 0,
                'zone_transitions_per_agent': [0, 0],
                'zone_focus_consistency': 0
            }
        }
        
        # Extraire les données de distance depuis les métriques comportementales
        if 'agent_specialization' in patterns:
            spec = patterns['agent_specialization']
            
            # Calculer les distances relatives basées sur la spécialisation
            agent_0_roles = spec.get('agent_0_dominant_roles', {})
            agent_1_roles = spec.get('agent_1_dominant_roles', {})
            
            # Estimer la distance basée sur les rôles et les activités
            agent_0_distance = self._estimate_movement_from_roles(agent_0_roles, performance)
            agent_1_distance = self._estimate_movement_from_roles(agent_1_roles, performance)
            
            total_distance = agent_0_distance + agent_1_distance
            
            movement_metrics['total_distance'] = {
                'agent_0': agent_0_distance,
                'agent_1': agent_1_distance,
                'total': total_distance,
                'balance': min(agent_0_distance, agent_1_distance) / max(agent_0_distance, agent_1_distance) if max(agent_0_distance, agent_1_distance) > 0 else 0
            }
            
            # Calculer l'efficacité de mouvement
            completion_efficiency = performance.get('completion_efficiency', 0)
            steps = performance.get('avg_completion_steps', 600)
            
            # Efficacité = complétion élevée avec peu de mouvements
            agent_0_efficiency = completion_efficiency * (300 / max(agent_0_distance, 1))
            agent_1_efficiency = completion_efficiency * (300 / max(agent_1_distance, 1))
            
            movement_metrics['movement_efficiency'] = {
                'agent_0': min(agent_0_efficiency, 1.0),
                'agent_1': min(agent_1_efficiency, 1.0),
                'overall': (agent_0_efficiency + agent_1_efficiency) / 2
            }
            
            # Analyser la distribution spatiale
            movement_metrics['spatial_distribution'] = self._analyze_spatial_distribution(
                agent_0_roles, agent_1_roles, spec
            )
            
            # Analyser l'optimisation des trajectoires
            movement_metrics['trajectory_optimization'] = self._analyze_trajectory_optimization(
                spec, performance
            )
            
            # Identifier les zones d'activité
            movement_metrics['activity_zones'] = self._identify_activity_zones(
                agent_0_roles, agent_1_roles, patterns
            )
        
        # Ajouter des métriques d'exploration vs exploitation
        movement_metrics['exploration_analysis'] = self._analyze_exploration_vs_exploitation(patterns)
        
        # Calculer des scores globaux de qualité de mouvement
        movement_metrics['movement_quality_scores'] = self._calculate_movement_quality_scores(movement_metrics)
        
        return movement_metrics
    
    def _analyze_interaction_patterns(self, mode_data: Dict) -> Dict:
        """
        Analyse détaillée des patterns d'interaction pour un mode donné.
        
        MÉTRIQUES D'INTERACTION:
        - Fréquence et types d'interactions
        - Qualité de la coordination
        - Synchronisation des actions
        - Efficacité des échanges
        - Patterns temporels d'interaction
        """
        patterns = mode_data.get('behavioral_patterns', {})
        performance = mode_data.get('performance_metrics', {})
        
        interaction_metrics = {
            'interaction_frequency': {
                'total_interactions': 0,
                'interactions_per_minute': 0,
                'interaction_density': 0
            },
            'interaction_types': {
                'coordination_events': [],
                'exchange_events': 0,
                'support_events': 0,
                'conflict_events': 0
            },
            'coordination_quality': {
                'synchronization_score': 0,
                'complementarity_score': 0,
                'efficiency_score': 0
            },
            'temporal_patterns': {
                'interaction_rhythm': 'unknown',
                'peak_interaction_phases': [],
                'coordination_consistency': 0
            },
            'communication_emergence': {
                'implicit_communication_detected': False,
                'communication_efficiency': 0,
                'information_transfer_quality': 0
            }
        }
        
        # Analyser les événements de coordination disponibles
        if 'coordination_events' in patterns:
            coord_events = patterns['coordination_events']
            
            # Fréquence d'interaction
            total_interactions = len(coord_events)
            steps = performance.get('avg_completion_steps', 600)
            simulated_minutes = steps / 60  # Approximation (1 step ≈ 1 seconde)
            
            interaction_metrics['interaction_frequency'] = {
                'total_interactions': total_interactions,
                'interactions_per_minute': total_interactions / max(simulated_minutes, 0.1),
                'interaction_density': total_interactions / max(steps, 1)
            }
            
            # Types d'interactions
            interaction_metrics['interaction_types'] = self._categorize_interaction_types(coord_events)
            
            # Qualité de la coordination
            interaction_metrics['coordination_quality'] = self._assess_coordination_quality(
                coord_events, patterns, performance
            )
            
            # Patterns temporels
            interaction_metrics['temporal_patterns'] = self._analyze_temporal_interaction_patterns(
                coord_events, steps
            )
        
        # Analyser la spécialisation pour déduire la coordination
        if 'agent_specialization' in patterns:
            spec = patterns['agent_specialization']
            
            # Calculer les métriques de coordination basées sur la spécialisation
            coordination_from_specialization = self._infer_coordination_from_specialization(spec)
            
            # Fusionner avec les métriques existantes
            if interaction_metrics['coordination_quality']['synchronization_score'] == 0:
                interaction_metrics['coordination_quality'].update(coordination_from_specialization)
        
        # Analyser l'émergence de communication
        interaction_metrics['communication_emergence'] = self._analyze_communication_emergence(
            patterns, performance
        )
        
        # Calculer des scores globaux d'interaction
        interaction_metrics['interaction_quality_scores'] = self._calculate_interaction_quality_scores(
            interaction_metrics
        )
        
        return interaction_metrics
    
    def _categorize_interaction_types(self, coordination_events: List) -> Dict:
        """
        Catégorise les types d'interactions observées.
        
        TYPES D'INTERACTIONS:
        - Échanges d'objets
        - Actions de support
        - Conflits/interférences
        - Coordination spatiale
        """
        interaction_types = {
            'coordination_events': coordination_events,
            'exchange_events': 0,
            'support_events': 0,
            'conflict_events': 0,
            'spatial_coordination': 0
        }
        
        # Analyser les événements pour les catégoriser
        for event in coordination_events:
            if isinstance(event, str):
                if 'exchange' in event.lower() or 'pass' in event.lower():
                    interaction_types['exchange_events'] += 1
                elif 'support' in event.lower() or 'help' in event.lower():
                    interaction_types['support_events'] += 1
                elif 'conflict' in event.lower() or 'block' in event.lower():
                    interaction_types['conflict_events'] += 1
                elif 'spatial' in event.lower() or 'move' in event.lower():
                    interaction_types['spatial_coordination'] += 1
        
        return interaction_types
    
    def _assess_coordination_quality(self, coordination_events: List, patterns: Dict, performance: Dict) -> Dict:
        """
        Évalue la qualité de la coordination entre agents.
        
        MÉTRIQUES DE QUALITÉ:
        - Score de synchronisation
        - Score de complémentarité
        - Score d'efficacité coordinative
        """
        quality_assessment = {
            'synchronization_score': 0,
            'complementarity_score': 0,
            'efficiency_score': 0
        }
        
        # Score de synchronisation basé sur la fréquence des événements de coordination
        num_events = len(coordination_events)
        steps = performance.get('avg_completion_steps', 600)
        
        if steps > 0:
            # Synchronisation élevée = événements réguliers mais pas excessifs
            ideal_frequency = 0.05  # 1 événement toutes les 20 steps environ
            actual_frequency = num_events / steps
            
            # Score optimal autour de la fréquence idéale
            sync_score = 1 - abs(actual_frequency - ideal_frequency) / ideal_frequency
            quality_assessment['synchronization_score'] = max(0, min(sync_score, 1))
        
        # Score de complémentarité basé sur la spécialisation
        if 'agent_specialization' in patterns:
            spec = patterns['agent_specialization']
            specialization_score = spec.get('avg_specialization_score', 0)
            
            # Complémentarité élevée = spécialisation élevée (rôles différents)
            quality_assessment['complementarity_score'] = specialization_score
        
        # Score d'efficacité coordinative = performance vs effort de coordination
        completion_efficiency = performance.get('completion_efficiency', 0)
        coordination_cost = num_events / max(steps, 1)  # Coût en événements par step
        
        # Efficacité élevée = bonne performance avec coordination modérée
        if coordination_cost > 0:
            efficiency_ratio = completion_efficiency / coordination_cost
            quality_assessment['efficiency_score'] = min(efficiency_ratio / 10, 1)  # Normaliser
        else:
            quality_assessment['efficiency_score'] = completion_efficiency
        
        return quality_assessment
    
    def _analyze_temporal_interaction_patterns(self, coordination_events: List, total_steps: int) -> Dict:
        """
        Analyse les patterns temporels des interactions.
        
        PATTERNS TEMPORELS:
        - Rythme d'interaction
        - Phases de pic d'interaction
        - Consistance temporelle
        """
        temporal_patterns = {
            'interaction_rhythm': 'unknown',
            'peak_interaction_phases': [],
            'coordination_consistency': 0
        }
        
        if not coordination_events or total_steps == 0:
            return temporal_patterns
        
        num_events = len(coordination_events)
        
        # Déterminer le rythme d'interaction
        events_per_step = num_events / total_steps
        
        if events_per_step < 0.01:
            rhythm = 'sparse'
        elif events_per_step < 0.05:
            rhythm = 'moderate'
        elif events_per_step < 0.1:
            rhythm = 'frequent'
        else:
            rhythm = 'intense'
        
        temporal_patterns['interaction_rhythm'] = rhythm
        
        # Analyser les phases de pic (simulation simplifiée)
        # Diviser le jeu en phases et identifier où les interactions sont concentrées
        num_phases = 4
        phase_length = total_steps // num_phases
        
        if phase_length > 0:
            # Simuler la distribution des événements dans les phases
            events_per_phase = num_events / num_phases
            
            # Identifier les phases avec plus d'interactions que la moyenne
            peak_phases = []
            for i in range(num_phases):
                # Simulation : varier l'intensité selon la phase
                phase_multiplier = [0.8, 1.2, 1.5, 0.9][i]  # Pic en milieu de jeu
                phase_events = events_per_phase * phase_multiplier
                
                if phase_events > events_per_phase * 1.2:
                    peak_phases.append(f"phase_{i+1}")
            
            temporal_patterns['peak_interaction_phases'] = peak_phases
        
        # Calculer la consistance de coordination (uniformité temporelle)
        # Pour simplifier, utiliser l'inverse de la variance simulée
        if num_events > 0:
            # Consistance élevée si le rythme est modéré et régulier
            if rhythm in ['moderate', 'frequent']:
                temporal_patterns['coordination_consistency'] = 0.8
            else:
                temporal_patterns['coordination_consistency'] = 0.4
        
        return temporal_patterns
    
    def _infer_coordination_from_specialization(self, specialization_data: Dict) -> Dict:
        """
        Infère les métriques de coordination à partir des données de spécialisation.
        """
        coordination_metrics = {
            'synchronization_score': 0,
            'complementarity_score': 0,
            'efficiency_score': 0
        }
        
        # Synchronisation basée sur la consistance de spécialisation
        consistency = specialization_data.get('specialization_consistency', 0)
        coordination_metrics['synchronization_score'] = consistency
        
        # Complémentarité basée sur le score de spécialisation
        specialization_score = specialization_data.get('avg_specialization_score', 0)
        coordination_metrics['complementarity_score'] = specialization_score
        
        # Efficacité basée sur la combinaison des deux
        coordination_metrics['efficiency_score'] = (consistency + specialization_score) / 2
        
        return coordination_metrics
    
    def _analyze_communication_emergence(self, patterns: Dict, performance: Dict) -> Dict:
        """
        Analyse l'émergence de communication implicite entre agents.
        
        INDICATEURS DE COMMUNICATION:
        - Communication implicite détectée
        - Efficacité de la communication
        - Qualité du transfert d'information
        """
        communication_analysis = {
            'implicit_communication_detected': False,
            'communication_efficiency': 0,
            'information_transfer_quality': 0
        }
        
        # Détecter la communication implicite via la coordination réussie
        if 'agent_specialization' in patterns:
            spec = patterns['agent_specialization']
            specialization_score = spec.get('avg_specialization_score', 0)
            consistency = spec.get('specialization_consistency', 0)
            
            # Communication implicite détectée si forte spécialisation ET consistance
            if specialization_score > 0.6 and consistency > 0.6:
                communication_analysis['implicit_communication_detected'] = True
        
        # Efficacité de communication basée sur la performance relative
        completion_efficiency = performance.get('completion_efficiency', 0)
        
        if communication_analysis['implicit_communication_detected']:
            # Si communication détectée, efficacité = performance
            communication_analysis['communication_efficiency'] = completion_efficiency
        else:
            # Sinon, efficacité plus faible
            communication_analysis['communication_efficiency'] = completion_efficiency * 0.5
        
        # Qualité du transfert d'information (proxy via spécialisation)
        if 'agent_specialization' in patterns:
            agent_0_roles = patterns['agent_specialization'].get('agent_0_dominant_roles', {})
            agent_1_roles = patterns['agent_specialization'].get('agent_1_dominant_roles', {})
            
            # Qualité élevée = rôles complémentaires (peu de chevauchement)
            common_roles = set(agent_0_roles.keys()) & set(agent_1_roles.keys())
            total_roles = set(agent_0_roles.keys()) | set(agent_1_roles.keys())
            
            if total_roles:
                complementarity = 1 - (len(common_roles) / len(total_roles))
                communication_analysis['information_transfer_quality'] = complementarity
        
        return communication_analysis
    
    def _calculate_interaction_quality_scores(self, interaction_metrics: Dict) -> Dict:
        """
        Calcule des scores globaux de qualité d'interaction.
        
        SCORES GLOBAUX:
        - Qualité d'interaction globale
        - Efficacité coordinative
        - Émergence comportementale
        - Score composite d'interaction
        """
        quality_scores = {
            'overall_interaction_quality': 0,
            'coordinative_efficiency': 0,
            'behavioral_emergence': 0,
            'composite_interaction_score': 0
        }
        
        # Qualité d'interaction globale = moyenne des scores de coordination
        if 'coordination_quality' in interaction_metrics:
            coord_quality = interaction_metrics['coordination_quality']
            scores = [
                coord_quality.get('synchronization_score', 0),
                coord_quality.get('complementarity_score', 0),
                coord_quality.get('efficiency_score', 0)
            ]
            quality_scores['overall_interaction_quality'] = np.mean([s for s in scores if s > 0])
        
        # Efficacité coordinative = ratio performance/effort
        if 'interaction_frequency' in interaction_metrics:
            freq = interaction_metrics['interaction_frequency']
            interaction_density = freq.get('interaction_density', 0)
            
            # Efficacité élevée = bonne coordination avec densité modérée
            if interaction_density > 0:
                # Optimal autour de 0.05 interactions par step
                efficiency = 1 - abs(interaction_density - 0.05) / 0.05
                quality_scores['coordinative_efficiency'] = max(0, efficiency)
        
        # Émergence comportementale = détection de communication + adaptation
        if 'communication_emergence' in interaction_metrics:
            comm = interaction_metrics['communication_emergence']
            
            emergence_indicators = [
                1 if comm.get('implicit_communication_detected', False) else 0,
                comm.get('communication_efficiency', 0),
                comm.get('information_transfer_quality', 0)
            ]
            quality_scores['behavioral_emergence'] = np.mean(emergence_indicators)
        
        # Score composite = moyenne pondérée des scores individuels
        individual_scores = [
            quality_scores['overall_interaction_quality'],
            quality_scores['coordinative_efficiency'],
            quality_scores['behavioral_emergence']
        ]
        
        valid_scores = [s for s in individual_scores if s > 0]
        if valid_scores:
            quality_scores['composite_interaction_score'] = np.mean(valid_scores)
        
        return quality_scores
    
    def _identify_dominant_role(self, roles: Dict) -> str:
        """Identifie le rôle dominant d'un agent."""
        if not roles:
            return 'undefined'
        
        dominant_role = max(roles.items(), key=lambda x: x[1], default=('undefined', 0))[0]
        return dominant_role
    
    def _calculate_role_complementarity(self, specialization_data: Dict) -> float:
        """Calcule la complémentarité des rôles entre agents."""
        agent_0_roles = specialization_data.get('agent_0_dominant_roles', {})
        agent_1_roles = specialization_data.get('agent_1_dominant_roles', {})
        
        # Mesurer à quel point les rôles sont différents (complémentaires)
        common_roles = set(agent_0_roles.keys()) & set(agent_1_roles.keys())
        total_roles = set(agent_0_roles.keys()) | set(agent_1_roles.keys())
        
        if not total_roles:
            return 0
        
        complementarity = 1 - (len(common_roles) / len(total_roles))
        return complementarity
    
    def _analyze_agent_specialization(self, mode_data: Dict) -> Dict:
        """Analyse la spécialisation des agents pour un mode donné."""
        patterns = mode_data.get('behavioral_patterns', {})
        
        if 'agent_specialization' not in patterns:
            return {'specialization_detected': False}
        
        spec = patterns['agent_specialization']
        
        return {
            'specialization_detected': True,
            'specialization_score': spec.get('avg_specialization_score', 0),
            'consistency_score': spec.get('specialization_consistency', 0),
            'agent_0_dominant_role': self._identify_dominant_role(spec.get('agent_0_dominant_roles', {})),
            'agent_1_dominant_role': self._identify_dominant_role(spec.get('agent_1_dominant_roles', {})),
            'role_complementarity': self._calculate_role_complementarity(spec)
        }
    
    def _estimate_movement_from_roles(self, agent_roles: Dict, performance: Dict) -> float:
        """
        Estime la distance de mouvement d'un agent basée sur ses rôles dominants.
        
        LOGIQUE:
        - Rôles de préparation (pickup, potting) = plus de mouvement
        - Rôles de livraison (delivery) = mouvement modéré mais focalisé
        - Rôles de support = mouvement variable selon contexte
        """
        if not agent_roles:
            return 0
        
        # Coefficients de mouvement par type de rôle
        movement_coefficients = {
            'ingredient_gatherer': 150,    # Beaucoup de va-et-vient
            'pot_manager': 100,           # Mouvement modéré autour des pots
            'delivery_specialist': 120,   # Mouvement focalisé vers zones de service
            'support_agent': 80,          # Mouvement d'adaptation
            'versatile_agent': 110,       # Mouvement équilibré
            'idle_agent': 20              # Peu de mouvement
        }
        
        # Calculer la distance estimée basée sur les rôles
        total_movement = 0
        total_weight = 0
        
        for role, weight in agent_roles.items():
            coefficient = movement_coefficients.get(role, 100)  # Valeur par défaut
            total_movement += coefficient * weight
            total_weight += weight
        
        # Normaliser par le poids total
        estimated_distance = total_movement / max(total_weight, 1)
        
        # Ajuster selon la performance globale
        completion_efficiency = performance.get('completion_efficiency', 0.5)
        steps = performance.get('avg_completion_steps', 300)
        
        # Plus d'étapes = potentiellement plus de mouvement
        step_factor = min(steps / 200, 2.0)  # Normaliser autour de 200 steps
        
        # Efficacité élevée = mouvement plus optimal (moins de distance pour même résultat)
        efficiency_factor = max(0.5, 1 - completion_efficiency * 0.3)
        
        final_distance = estimated_distance * step_factor * efficiency_factor
        
        return final_distance
    
    def _analyze_spatial_distribution(self, agent_0_roles: Dict, agent_1_roles: Dict, 
                                    specialization_data: Dict) -> Dict:
        """
        Analyse la distribution spatiale des activités des agents.
        
        MÉTRIQUES:
        - Couverture spatiale de chaque agent
        - Ratio de chevauchement des zones d'activité
        - Spécialisation par zone fonctionnelle
        """
        spatial_dist = {
            'agent_0_coverage': 0,
            'agent_1_coverage': 0,
            'overlap_ratio': 0,
            'zone_specialization': {}
        }
        
        # Estimer la couverture spatiale basée sur la diversité des rôles
        agent_0_coverage = len(agent_0_roles) / 6  # Normalisé sur 6 rôles possibles max
        agent_1_coverage = len(agent_1_roles) / 6
        
        spatial_dist['agent_0_coverage'] = min(agent_0_coverage, 1.0)
        spatial_dist['agent_1_coverage'] = min(agent_1_coverage, 1.0)
        
        # Calculer le ratio de chevauchement (rôles partagés)
        common_roles = set(agent_0_roles.keys()) & set(agent_1_roles.keys())
        total_roles = set(agent_0_roles.keys()) | set(agent_1_roles.keys())
        
        if total_roles:
            spatial_dist['overlap_ratio'] = len(common_roles) / len(total_roles)
        
        # Analyser la spécialisation par zone fonctionnelle
        zone_specializations = {
            'preparation_zone': self._calculate_zone_specialization('ingredient_gatherer', agent_0_roles, agent_1_roles),
            'cooking_zone': self._calculate_zone_specialization('pot_manager', agent_0_roles, agent_1_roles),
            'delivery_zone': self._calculate_zone_specialization('delivery_specialist', agent_0_roles, agent_1_roles)
        }
        
        spatial_dist['zone_specialization'] = zone_specializations
        
        return spatial_dist
    
    def _calculate_zone_specialization(self, zone_role: str, agent_0_roles: Dict, agent_1_roles: Dict) -> Dict:
        """Calcule la spécialisation d'une zone spécifique."""
        agent_0_weight = agent_0_roles.get(zone_role, 0)
        agent_1_weight = agent_1_roles.get(zone_role, 0)
        total_weight = agent_0_weight + agent_1_weight
        
        if total_weight == 0:
            return {'specialization': 'none', 'dominant_agent': None, 'specialization_score': 0}
        
        # Déterminer l'agent dominant pour cette zone
        if agent_0_weight > agent_1_weight * 1.5:
            dominant_agent = 'agent_0'
            specialization = 'high'
            specialization_score = agent_0_weight / total_weight
        elif agent_1_weight > agent_0_weight * 1.5:
            dominant_agent = 'agent_1'
            specialization = 'high'
            specialization_score = agent_1_weight / total_weight
        else:
            dominant_agent = 'shared'
            specialization = 'balanced'
            specialization_score = 0.5
        
        return {
            'specialization': specialization,
            'dominant_agent': dominant_agent,
            'specialization_score': specialization_score,
            'agent_0_involvement': agent_0_weight / total_weight,
            'agent_1_involvement': agent_1_weight / total_weight
        }
    
    def _analyze_trajectory_optimization(self, specialization_data: Dict, performance: Dict) -> Dict:
        """
        Analyse l'optimisation des trajectoires des agents.
        
        MÉTRIQUES:
        - Score d'efficacité du chemin
        - Ratio de mouvements redondants
        - Adhérence au chemin optimal
        """
        trajectory_opt = {
            'path_efficiency_score': 0,
            'redundant_moves_ratio': 0,
            'optimal_path_adherence': 0
        }
        
        # Score d'efficacité basé sur la spécialisation et la performance
        specialization_score = specialization_data.get('avg_specialization_score', 0)
        consistency_score = specialization_data.get('specialization_consistency', 0)
        completion_efficiency = performance.get('completion_efficiency', 0)
        
        # Efficacité du chemin = combinaison de spécialisation et performance
        path_efficiency = (specialization_score + completion_efficiency) / 2
        trajectory_opt['path_efficiency_score'] = path_efficiency
        
        # Estimer les mouvements redondants (inverse de la consistance)
        redundant_ratio = max(0, 1 - consistency_score)
        trajectory_opt['redundant_moves_ratio'] = redundant_ratio
        
        # Adhérence au chemin optimal (basée sur l'efficacité globale)
        optimal_adherence = completion_efficiency * consistency_score
        trajectory_opt['optimal_path_adherence'] = optimal_adherence
        
        return trajectory_opt
    
    def _identify_activity_zones(self, agent_0_roles: Dict, agent_1_roles: Dict, patterns: Dict) -> Dict:
        """
        Identifie les zones d'activité intensive pour les agents.
        
        MÉTRIQUES:
        - Nombre de zones d'activité intense
        - Transitions entre zones par agent
        - Consistance de focus par zone
        """
        activity_zones = {
            'hot_zones_count': 0,
            'zone_transitions_per_agent': [0, 0],
            'zone_focus_consistency': 0
        }
        
        # Identifier les zones d'activité basées sur les rôles dominants
        all_roles = set(agent_0_roles.keys()) | set(agent_1_roles.keys())
        
        # Compter les zones actives (rôles avec poids significatif)
        hot_zones = []
        for role in all_roles:
            weight_0 = agent_0_roles.get(role, 0)
            weight_1 = agent_1_roles.get(role, 0)
            total_weight = weight_0 + weight_1
            
            if total_weight > 0.1:  # Seuil d'activité significative
                hot_zones.append(role)
        
        activity_zones['hot_zones_count'] = len(hot_zones)
        
        # Estimer les transitions entre zones (basé sur la diversité des rôles)
        agent_0_transitions = max(0, len(agent_0_roles) - 1)  # -1 car pas de transition si un seul rôle
        agent_1_transitions = max(0, len(agent_1_roles) - 1)
        
        activity_zones['zone_transitions_per_agent'] = [agent_0_transitions, agent_1_transitions]
        
        # Calculer la consistance de focus (inverse de la diversité)
        total_roles = len(all_roles)
        if total_roles > 0:
            # Focus élevé = peu de rôles différents, focus faible = beaucoup de rôles
            focus_consistency = max(0, 1 - (total_roles - 1) / 5)  # Normalisé sur 6 rôles max
            activity_zones['zone_focus_consistency'] = focus_consistency
        
        return activity_zones
    
    def _analyze_exploration_vs_exploitation(self, patterns: Dict) -> Dict:
        """
        Analyse l'équilibre exploration vs exploitation dans les comportements.
        
        MÉTRIQUES:
        - Score d'exploration (diversité des activités)
        - Score d'exploitation (focus sur activités efficaces)
        - Équilibre exploration-exploitation
        """
        exploration_analysis = {
            'exploration_score': 0,
            'exploitation_score': 0,
            'balance_score': 0,
            'adaptive_behavior_detected': False
        }
        
        if 'agent_specialization' not in patterns:
            return exploration_analysis
        
        spec = patterns['agent_specialization']
        
        # Score d'exploration = diversité des rôles
        agent_0_roles = spec.get('agent_0_dominant_roles', {})
        agent_1_roles = spec.get('agent_1_dominant_roles', {})
        
        total_unique_roles = len(set(agent_0_roles.keys()) | set(agent_1_roles.keys()))
        exploration_score = min(total_unique_roles / 6, 1.0)  # Normalisé sur 6 rôles max
        
        # Score d'exploitation = consistance et spécialisation
        avg_specialization = spec.get('avg_specialization_score', 0)
        consistency = spec.get('specialization_consistency', 0)
        exploitation_score = (avg_specialization + consistency) / 2
        
        # Équilibre = proximité de 0.5 entre exploration et exploitation
        balance_score = 1 - abs(exploration_score - exploitation_score)
        
        # Détection de comportement adaptatif
        adaptive_behavior = (exploration_score > 0.3 and exploitation_score > 0.3 and balance_score > 0.6)
        
        exploration_analysis = {
            'exploration_score': exploration_score,
            'exploitation_score': exploitation_score,
            'balance_score': balance_score,
            'adaptive_behavior_detected': adaptive_behavior
        }
        
        return exploration_analysis
    
    def _calculate_movement_quality_scores(self, movement_metrics: Dict) -> Dict:
        """
        Calcule des scores globaux de qualité de mouvement.
        
        SCORES:
        - Efficacité globale de mouvement
        - Optimisation spatiale
        - Coordination des mouvements
        - Score de qualité composite
        """
        quality_scores = {
            'overall_efficiency': 0,
            'spatial_optimization': 0,
            'movement_coordination': 0,
            'composite_quality_score': 0
        }
        
        # Efficacité globale = moyenne des efficacités individuelles
        if 'movement_efficiency' in movement_metrics:
            eff = movement_metrics['movement_efficiency']
            quality_scores['overall_efficiency'] = eff.get('overall', 0)
        
        # Optimisation spatiale = combinaison de couverture et d'optimisation de trajectoire
        if 'spatial_distribution' in movement_metrics and 'trajectory_optimization' in movement_metrics:
            spatial = movement_metrics['spatial_distribution']
            trajectory = movement_metrics['trajectory_optimization']
            
            coverage_balance = min(spatial.get('agent_0_coverage', 0), spatial.get('agent_1_coverage', 0))
            path_efficiency = trajectory.get('path_efficiency_score', 0)
            
            spatial_optimization = (coverage_balance + path_efficiency) / 2
            quality_scores['spatial_optimization'] = spatial_optimization
        
        # Coordination des mouvements = équilibre et complémentarité
        if 'total_distance' in movement_metrics and 'spatial_distribution' in movement_metrics:
            distance_balance = movement_metrics['total_distance'].get('balance', 0)
            overlap_ratio = movement_metrics['spatial_distribution'].get('overlap_ratio', 0)
            
            # Coordination élevée = bon équilibre ET faible chevauchement (complémentarité)
            movement_coordination = (distance_balance + (1 - overlap_ratio)) / 2
            quality_scores['movement_coordination'] = movement_coordination
        
        # Score composite = moyenne pondérée des scores individuels
        scores = [
            quality_scores['overall_efficiency'],
            quality_scores['spatial_optimization'],
            quality_scores['movement_coordination']
        ]
        
        valid_scores = [s for s in scores if s > 0]
        if valid_scores:
            quality_scores['composite_quality_score'] = np.mean(valid_scores)
        
        return quality_scores
        """Identifie le rôle dominant d'un agent."""
        if not roles:
            return 'undefined'
        
        dominant_role = max(roles.items(), key=lambda x: x[1], default=('undefined', 0))[0]
        return dominant_role
    
    def _calculate_role_complementarity(self, specialization_data: Dict) -> float:
        """Calcule la complémentarité des rôles entre agents."""
        agent_0_roles = specialization_data.get('agent_0_dominant_roles', {})
        agent_1_roles = specialization_data.get('agent_1_dominant_roles', {})
        
        # Mesurer à quel point les rôles sont différents (complémentaires)
        common_roles = set(agent_0_roles.keys()) & set(agent_1_roles.keys())
        total_roles = set(agent_0_roles.keys()) | set(agent_1_roles.keys())
        
        if not total_roles:
            return 0
        
        complementarity = 1 - (len(common_roles) / len(total_roles))
        return complementarity
    
    def _analyze_behavioral_efficiency(self, mode_data: Dict) -> Dict:
        """Analyse l'efficacité comportementale pour un mode donné."""
        performance = mode_data.get('performance_metrics', {})
        
        return {
            'completion_efficiency': performance.get('completion_efficiency', 0),
            'resource_utilization': performance.get('resource_utilization', 0),
            'waste_minimization': performance.get('waste_minimization', 0),
            'overall_behavioral_efficiency': performance.get('overall_efficiency', 0)
        }
    
    def _compare_behavioral_modes(self, behavioral_modes: Dict) -> Dict:
        """Compare les comportements entre différents modes."""
        if len(behavioral_modes) < 2:
            return {'comparison_possible': False, 'reason': 'insufficient_modes'}
        
        comparisons = {
            'mode_diversity': 0,
            'consistency_across_modes': 0,
            'mode_specific_adaptations': {},
            'optimal_mode_identification': None
        }
        
        # Calculer la diversité entre modes
        success_rates = [mode.get('success_rate', 0) for mode in behavioral_modes.values()]
        comparisons['mode_diversity'] = np.std(success_rates) if success_rates else 0
        
        # Identifier le mode optimal
        best_mode = max(behavioral_modes.items(), 
                       key=lambda x: x[1].get('success_rate', 0),
                       default=(None, {}))[0]
        comparisons['optimal_mode_identification'] = best_mode
        
        return comparisons
    
    def _identify_adaptation_indicators(self, behavioral_modes: Dict) -> Dict:
        """Identifie les indicateurs d'adaptation comportementale."""
        indicators = {
            'adaptation_detected': False,
            'adaptation_mechanisms': [],
            'flexibility_score': 0,
            'robustness_score': 0
        }
        
        if len(behavioral_modes) >= 2:
            indicators['adaptation_detected'] = True
            indicators['flexibility_score'] = len(behavioral_modes) / 5  # Normalisé sur 5 modes max
            
            # Analyser la robustesse (consistance des performances)
            success_rates = [mode.get('success_rate', 0) for mode in behavioral_modes.values()]
            indicators['robustness_score'] = 1 - np.std(success_rates) if success_rates else 0
        
        return indicators
    
    # ========================================
    # 3. CARACTÉRISATION PAR PERFORMANCE
    # ========================================
    
    def characterize_performance_profile(self, layout_name: str, layout_data: Dict) -> Dict:
        """
        Caractérise le profil de performance d'un layout.
        
        MÉTRIQUES DE PERFORMANCE:
        - Taux de réussite et distribution
        - Temps de complétion et variabilité
        - Efficacité relative entre modes
        - Courbes d'apprentissage
        - Ratios effort/récompense
        - Consistance des résultats
        """
        performance = {
            'success_metrics': {},
            'timing_metrics': {},
            'efficiency_metrics': {},
            'consistency_metrics': {},
            'comparative_metrics': {}
        }
        
        # Métriques de succès globales
        performance['success_metrics'] = self._calculate_success_metrics(layout_data)
        
        # Métriques temporelles
        performance['timing_metrics'] = self._calculate_timing_metrics(layout_data)
        
        # Métriques d'efficacité
        performance['efficiency_metrics'] = self._calculate_performance_efficiency_metrics(layout_data)
        
        # Métriques de consistance
        performance['consistency_metrics'] = self._calculate_consistency_metrics(layout_data)
        
        # Métriques comparatives (par rapport aux autres layouts)
        performance['comparative_metrics'] = self._calculate_comparative_performance(layout_data)
        
        return performance
    
    def _calculate_success_metrics(self, layout_data: Dict) -> Dict:
        """Calcule les métriques de succès."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        success_rates = [mode.get('success_rate', 0) for mode in behavioral_modes.values()]
        
        return {
            'overall_success_rate': np.mean(success_rates) if success_rates else 0,
            'best_success_rate': max(success_rates) if success_rates else 0,
            'worst_success_rate': min(success_rates) if success_rates else 0,
            'success_rate_variance': np.var(success_rates) if success_rates else 0,
            'success_consistency': 1 - np.std(success_rates) if success_rates else 0,
            'modes_with_success': len([rate for rate in success_rates if rate > 0]),
            'total_modes_tested': len(success_rates)
        }
    
    def _calculate_timing_metrics(self, layout_data: Dict) -> Dict:
        """Calcule les métriques temporelles."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        completion_times = []
        for mode_data in behavioral_modes.values():
            perf = mode_data.get('performance_metrics', {})
            if 'avg_completion_steps' in perf:
                completion_times.append(perf['avg_completion_steps'])
        
        if not completion_times:
            return {'timing_data_available': False}
        
        return {
            'timing_data_available': True,
            'avg_completion_time': np.mean(completion_times),
            'fastest_completion': min(completion_times),
            'slowest_completion': max(completion_times),
            'completion_time_variance': np.var(completion_times),
            'timing_predictability': 1 - (np.std(completion_times) / np.mean(completion_times)) if np.mean(completion_times) > 0 else 0
        }
    
    def _calculate_performance_efficiency_metrics(self, layout_data: Dict) -> Dict:
        """Calcule les métriques d'efficacité de performance."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        efficiency_scores = []
        for mode_data in behavioral_modes.values():
            perf = mode_data.get('performance_metrics', {})
            efficiency = perf.get('completion_efficiency', 0)
            efficiency_scores.append(efficiency)
        
        return {
            'avg_efficiency': np.mean(efficiency_scores) if efficiency_scores else 0,
            'peak_efficiency': max(efficiency_scores) if efficiency_scores else 0,
            'efficiency_variance': np.var(efficiency_scores) if efficiency_scores else 0,
            'efficiency_improvement_potential': max(efficiency_scores) - min(efficiency_scores) if efficiency_scores else 0
        }
    
    def _calculate_consistency_metrics(self, layout_data: Dict) -> Dict:
        """Calcule les métriques de consistance."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        # Extraire différentes métriques pour mesurer la consistance
        success_rates = [mode.get('success_rate', 0) for mode in behavioral_modes.values()]
        
        performance_values = []
        for mode_data in behavioral_modes.values():
            perf = mode_data.get('performance_metrics', {})
            performance_values.append(perf.get('completion_efficiency', 0))
        
        return {
            'result_consistency': 1 - np.std(success_rates) if success_rates else 0,
            'performance_consistency': 1 - np.std(performance_values) if performance_values else 0,
            'overall_consistency': (1 - np.std(success_rates) + 1 - np.std(performance_values)) / 2 if success_rates and performance_values else 0,
            'predictability_score': self._calculate_predictability_score(layout_data)
        }
    
    def _calculate_predictability_score(self, layout_data: Dict) -> float:
        """Calcule un score de prédictibilité basé sur la variance des résultats."""
        # Pour l'instant, utiliser la consistance des taux de succès comme proxy
        behavioral_modes = layout_data.get('behavioral_modes', {})
        success_rates = [mode.get('success_rate', 0) for mode in behavioral_modes.values()]
        
        if not success_rates:
            return 0
        
        # Prédictibilité = 1 - coefficient de variation
        mean_success = np.mean(success_rates)
        if mean_success == 0:
            return 0
        
        cv = np.std(success_rates) / mean_success
        predictability = max(0, 1 - cv)
        
        return predictability
    
    def _calculate_comparative_performance(self, layout_data: Dict) -> Dict:
        """Calcule les métriques comparatives par rapport aux autres layouts."""
        # Placeholder pour les métriques comparatives
        # Nécessite d'avoir accès aux données de tous les layouts
        return {
            'relative_difficulty': 0.5,  # À implémenter avec données complètes
            'performance_percentile': 0.5,  # À implémenter
            'outlier_status': 'normal',  # À implémenter
            'note': 'Comparative metrics require full dataset analysis'
        }
    
    # ========================================
    # 4. CARACTÉRISATION PAR COORDINATION
    # ========================================
    
    def characterize_coordination_requirements(self, layout_name: str, layout_data: Dict) -> Dict:
        """
        Caractérise les exigences de coordination d'un layout.
        
        MÉTRIQUES DE COORDINATION:
        - Nécessité de coordination (solo vs coop)
        - Types d'interactions requises
        - Séquencement des tâches
        - Spécialisation des rôles
        - Complexité coordinative
        """
        coordination = {
            'coordination_necessity': {},
            'interaction_requirements': {},
            'role_dynamics': {},
            'task_sequencing': {},
            'coordination_complexity': {}
        }
        
        coord_analysis = layout_data.get('coordination_analysis', {})
        
        # Nécessité de coordination
        coordination['coordination_necessity'] = self._analyze_coordination_necessity(coord_analysis)
        
        # Exigences d'interaction
        coordination['interaction_requirements'] = self._analyze_interaction_requirements(layout_data)
        
        # Dynamiques de rôles
        coordination['role_dynamics'] = self._analyze_role_dynamics(layout_data)
        
        # Séquencement des tâches
        coordination['task_sequencing'] = self._analyze_task_sequencing(layout_data)
        
        # Complexité coordinative
        coordination['coordination_complexity'] = self._calculate_coordination_complexity(layout_data)
        
        return coordination
    
    def _analyze_coordination_necessity(self, coord_analysis: Dict) -> Dict:
        """Analyse la nécessité de coordination."""
        necessity = coord_analysis.get('coordination_necessity', 'unknown')
        solo_vs_team = coord_analysis.get('solo_vs_team_effectiveness', {})
        
        return {
            'necessity_level': necessity,
            'team_advantage': solo_vs_team.get('team_advantage', 0),
            'relative_effectiveness': solo_vs_team.get('relative_effectiveness', 1),
            'coordination_benefit': solo_vs_team.get('team_advantage', 0) > 0.1,
            'solo_viability': solo_vs_team.get('relative_effectiveness', 1) > 0.5
        }
    
    def _analyze_interaction_requirements(self, layout_data: Dict) -> Dict:
        """Analyse les exigences d'interaction."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        interaction_types = []
        interaction_frequencies = []
        
        for mode_data in behavioral_modes.values():
            patterns = mode_data.get('behavioral_patterns', {})
            if 'coordination_events' in patterns:
                events = patterns['coordination_events']
                interaction_types.extend(events)
                interaction_frequencies.append(len(events))
        
        return {
            'interaction_types_observed': list(set(interaction_types)),
            'avg_interactions_per_game': np.mean(interaction_frequencies) if interaction_frequencies else 0,
            'interaction_diversity': len(set(interaction_types)),
            'interaction_intensity': max(interaction_frequencies) if interaction_frequencies else 0
        }
    
    def _analyze_role_dynamics(self, layout_data: Dict) -> Dict:
        """Analyse les dynamiques de rôles."""
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        specialization_scores = []
        role_distributions = []
        
        for mode_data in behavioral_modes.values():
            patterns = mode_data.get('behavioral_patterns', {})
            if 'agent_specialization' in patterns:
                spec = patterns['agent_specialization']
                specialization_scores.append(spec.get('avg_specialization_score', 0))
                
                # Analyser la distribution des rôles
                agent_0_roles = spec.get('agent_0_dominant_roles', {})
                agent_1_roles = spec.get('agent_1_dominant_roles', {})
                role_distributions.append((agent_0_roles, agent_1_roles))
        
        return {
            'avg_specialization': np.mean(specialization_scores) if specialization_scores else 0,
            'specialization_consistency': 1 - np.std(specialization_scores) if specialization_scores else 0,
            'role_flexibility': self._calculate_role_flexibility(role_distributions),
            'dominant_role_patterns': self._identify_dominant_role_patterns(role_distributions)
        }
    
    def _calculate_role_flexibility(self, role_distributions: List) -> float:
        """Calcule la flexibilité des rôles."""
        if not role_distributions:
            return 0
        
        # Mesurer la variabilité des rôles entre les parties
        all_roles = set()
        for agent_0_roles, agent_1_roles in role_distributions:
            all_roles.update(agent_0_roles.keys())
            all_roles.update(agent_1_roles.keys())
        
        # Flexibilité = nombre de rôles différents observés
        flexibility = len(all_roles) / 10  # Normalisé arbitrairement
        return min(flexibility, 1.0)
    
    def _identify_dominant_role_patterns(self, role_distributions: List) -> Dict:
        """Identifie les patterns de rôles dominants."""
        if not role_distributions:
            return {}
        
        # Compter les rôles les plus fréquents
        agent_0_role_counts = Counter()
        agent_1_role_counts = Counter()
        
        for agent_0_roles, agent_1_roles in role_distributions:
            # Prendre le rôle dominant de chaque agent
            if agent_0_roles:
                dominant_role_0 = max(agent_0_roles.items(), key=lambda x: x[1])[0]
                agent_0_role_counts[dominant_role_0] += 1
            
            if agent_1_roles:
                dominant_role_1 = max(agent_1_roles.items(), key=lambda x: x[1])[0]
                agent_1_role_counts[dominant_role_1] += 1
        
        return {
            'agent_0_preferred_roles': dict(agent_0_role_counts.most_common(3)),
            'agent_1_preferred_roles': dict(agent_1_role_counts.most_common(3)),
            'role_complementarity': len(set(agent_0_role_counts.keys()) & set(agent_1_role_counts.keys())) == 0
        }
    
    def _analyze_task_sequencing(self, layout_data: Dict) -> Dict:
        """Analyse le séquencement des tâches."""
        # Placeholder pour l'analyse de séquencement
        return {
            'sequencing_complexity': 0.5,  # À implémenter
            'critical_path_length': 0,     # À implémenter
            'parallelization_potential': 0.5,  # À implémenter
            'note': 'Task sequencing analysis requires detailed event timeline data'
        }
    
    def _calculate_coordination_complexity(self, layout_data: Dict) -> Dict:
        """Calcule la complexité coordinative."""
        coord_analysis = layout_data.get('coordination_analysis', {})
        behavioral_modes = layout_data.get('behavioral_modes', {})
        
        # Facteurs de complexité
        team_advantage = coord_analysis.get('solo_vs_team_effectiveness', {}).get('team_advantage', 0)
        num_interaction_types = len(set(
            event for mode_data in behavioral_modes.values()
            for event in mode_data.get('behavioral_patterns', {}).get('coordination_events', [])
        ))
        
        # Score de complexité composite
        complexity_score = (abs(team_advantage) + num_interaction_types / 10) / 2
        
        return {
            'complexity_score': min(complexity_score, 1.0),
            'complexity_level': self._categorize_coordination_complexity(complexity_score),
            'coordination_necessity': coord_analysis.get('coordination_necessity', 'unknown'),
            'interaction_diversity': num_interaction_types
        }
    
    def _categorize_coordination_complexity(self, complexity_score: float) -> str:
        """Catégorise la complexité coordinative."""
        if complexity_score < 0.25:
            return 'minimal'
        elif complexity_score < 0.5:
            return 'moderate'
        elif complexity_score < 0.75:
            return 'high'
        else:
            return 'very_high'
    
    # ========================================
    # MÉTHODES D'ORCHESTRATION
    # ========================================
    
    def characterize_all_layouts(self, output_file: str = "layout_characterization_complete.json") -> Dict:
        """
        Effectue une caractérisation complète de tous les layouts.
        """
        if not self.layout_data:
            print("❌ Aucune donnée chargée")
            return {}
        
        print(f"\n🏗️ CARACTÉRISATION COMPLÈTE DES LAYOUTS")
        print(f"=" * 60)
        
        characterization = {
            'metadata': {
                'characterization_timestamp': pd.Timestamp.now().isoformat(),
                'layouts_characterized': 0,
                'characterization_methods': [
                    'structural', 'behavioral', 'performance', 'coordination'
                ]
            },
            'individual_characterizations': {},
            'comparative_analysis': {},
            'clustering_results': {},
            'layout_taxonomy': {},
            'recommendations': {}
        }
        
        layouts = self.layout_data.get('layouts', {})
        total_layouts = len(layouts)
        
        print(f"📊 Caractérisation de {total_layouts} layouts...")
        
        # Caractériser chaque layout individuellement
        for i, (layout_name, layout_data) in enumerate(layouts.items(), 1):
            print(f"   🏗️ Layout {i}/{total_layouts}: {layout_name}")
            
            layout_characterization = {
                'structural_features': self.characterize_structural_features(layout_name, layout_data),
                'behavioral_patterns': self.characterize_behavioral_patterns(layout_name, layout_data),
                'performance_profile': self.characterize_performance_profile(layout_name, layout_data),
                'coordination_requirements': self.characterize_coordination_requirements(layout_name, layout_data)
            }
            
            characterization['individual_characterizations'][layout_name] = layout_characterization
        
        characterization['metadata']['layouts_characterized'] = len(characterization['individual_characterizations'])
        
        # Analyses comparatives
        print("🔍 Analyse comparative...")
        characterization['comparative_analysis'] = self._perform_comparative_analysis(
            characterization['individual_characterizations']
        )
        
        # Clustering des layouts
        print("🎯 Clustering des layouts...")
        characterization['clustering_results'] = self._perform_layout_clustering(
            characterization['individual_characterizations']
        )
        
        # Taxonomie des layouts
        print("📚 Construction de la taxonomie...")
        characterization['layout_taxonomy'] = self._build_layout_taxonomy(
            characterization['individual_characterizations']
        )
        
        # Recommandations
        print("💡 Génération de recommandations...")
        characterization['recommendations'] = self._generate_characterization_recommendations(
            characterization
        )
        
        # Sauvegarder les résultats
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Caractérisation complète terminée!")
        print(f"📊 Résultats sauvegardés: {output_file}")
        
        self.characterization_results = characterization
        return characterization
    
    def _perform_comparative_analysis(self, individual_chars: Dict) -> Dict:
        """Effectue une analyse comparative entre tous les layouts."""
        # Placeholder pour l'analyse comparative détaillée
        return {
            'difficulty_ranking': [],  # À implémenter
            'similarity_matrix': {},   # À implémenter
            'performance_comparison': {},  # À implémenter
            'note': 'Comparative analysis implementation in progress'
        }
    
    def _perform_layout_clustering(self, individual_chars: Dict) -> Dict:
        """Effectue un clustering des layouts basé sur leurs caractéristiques."""
        # Placeholder pour le clustering
        return {
            'clusters_identified': 0,  # À implémenter
            'cluster_characteristics': {},  # À implémenter
            'outlier_layouts': [],  # À implémenter
            'note': 'Clustering implementation in progress'
        }
    
    def _build_layout_taxonomy(self, individual_chars: Dict) -> Dict:
        """Construit une taxonomie des layouts."""
        # Placeholder pour la taxonomie
        return {
            'taxonomy_levels': [],  # À implémenter
            'layout_categories': {},  # À implémenter
            'classification_rules': {},  # À implémenter
            'note': 'Taxonomy building implementation in progress'
        }
    
    def _generate_characterization_recommendations(self, characterization: Dict) -> List[str]:
        """Génère des recommandations basées sur la caractérisation."""
        recommendations = [
            "Implementation of detailed spatial analysis for structural characterization",
            "Development of movement pattern tracking for behavioral analysis",
            "Creation of comparative metrics across all layouts",
            "Implementation of machine learning clustering algorithms",
            "Development of predictive models for layout difficulty"
        ]
        
        return recommendations
    
    def create_characterization_visualizations(self, output_dir: str = "characterization_plots"):
        """Crée des visualisations des résultats de caractérisation."""
        Path(output_dir).mkdir(exist_ok=True)
        
        if not self.characterization_results:
            print("❌ Aucune caractérisation disponible pour la visualisation")
            return
        
        print(f"📊 Création des visualisations dans: {output_dir}/")
        
        # Placeholder pour les visualisations
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, 'Characterization Visualizations\nComing Soon!', 
                horizontalalignment='center', verticalalignment='center',
                fontsize=16, transform=plt.gca().transAxes)
        plt.axis('off')
        plt.savefig(f"{output_dir}/characterization_overview.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Visualisations créées (placeholder)")


def main():
    parser = argparse.ArgumentParser(description="Caractérisateur de layouts Overcooked")
    parser.add_argument('data_file', help='Fichier de données de layouts à caractériser')
    parser.add_argument('--output', default='layout_characterization_complete.json',
                       help='Fichier de sortie pour la caractérisation')
    parser.add_argument('--plots', default='characterization_plots',
                       help='Répertoire pour les graphiques')
    parser.add_argument('--no-plots', action='store_true',
                       help='Désactiver la génération de graphiques')
    
    args = parser.parse_args()
    
    print("🏗️ CARACTÉRISATEUR DE LAYOUTS OVERCOOKED")
    print("=" * 50)
    
    characterizer = LayoutCharacterizer()
    
    if not characterizer.load_layout_data(args.data_file):
        return 1
    
    # Effectuer la caractérisation complète
    characterization_results = characterizer.characterize_all_layouts(args.output)
    
    # Créer les visualisations
    if not args.no_plots:
        try:
            characterizer.create_characterization_visualizations(args.plots)
        except Exception as e:
            print(f"⚠️ Erreur lors de la génération des graphiques: {e}")
    
    print(f"\n✅ Caractérisation terminée!")
    print(f"📊 Résultats sauvegardés: {args.output}")
    
    return 0


if __name__ == "__main__":
    exit(main())
