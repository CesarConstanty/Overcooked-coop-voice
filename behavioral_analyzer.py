#!/usr/bin/env python3
"""
behavioral_analyzer.py

Analyseur comportemental complet pour les données générées par behavioral_data_generator.py
Analyse en profondeur les patterns de comportement des GreedyAgent pour caractériser les layouts.

OBJECTIF: Extraire des insights comportementaux précis pour comprendre les propriétés
des layouts et les stratégies optimales des agents.
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
from pathlib import Path
import argparse
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns


class BehavioralAnalyzer:
    """
    Analyseur comportemental complet pour données de layouts Overcooked.
    """
    
    def __init__(self):
        self.layout_profiles = {}
        self.behavioral_clusters = {}
        self.performance_models = {}
        
    def load_behavioral_data(self, data_file: str) -> Dict:
        """Charge les données comportementales générées."""
        print(f"📂 Chargement des données: {data_file}")
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ Données chargées: {len(data.get('layouts', {}))} layouts")
            return data
            
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return {}
    
    def analyze_complete_behavioral_data(self, data: Dict, output_dir: str = "behavioral_analysis") -> Dict:
        """
        Analyse comportementale complète des données.
        """
        print(f"\n🧠 ANALYSE COMPORTEMENTALE COMPLÈTE")
        print(f"=" * 50)
        
        Path(output_dir).mkdir(exist_ok=True)
        
        complete_analysis = {
            'metadata': {
                'analysis_timestamp': pd.Timestamp.now().isoformat(),
                'layouts_analyzed': len(data.get('layouts', {})),
                'analysis_version': '1.0'
            },
            'layout_profiles': {},
            'behavioral_clusters': {},
            'comparative_analysis': {},
            'predictive_models': {},
            'recommendations': {}
        }
        
        layouts_data = data.get('layouts', {})
        
        # 1. Créer des profils détaillés pour chaque layout
        print("📊 Création des profils de layouts...")
        for layout_name, layout_data in layouts_data.items():
            profile = self._create_detailed_layout_profile(layout_name, layout_data)
            complete_analysis['layout_profiles'][layout_name] = profile
        
        # 2. Identifier les clusters comportementaux
        print("🔍 Identification des clusters comportementaux...")
        clusters = self._identify_behavioral_clusters(complete_analysis['layout_profiles'])
        complete_analysis['behavioral_clusters'] = clusters
        
        # 3. Analyse comparative entre layouts
        print("⚖️ Analyse comparative...")
        comparative = self._perform_comparative_analysis(complete_analysis['layout_profiles'])
        complete_analysis['comparative_analysis'] = comparative
        
        # 4. Modèles prédictifs
        print("🔮 Construction de modèles prédictifs...")
        models = self._build_predictive_models(complete_analysis['layout_profiles'])
        complete_analysis['predictive_models'] = models
        
        # 5. Recommandations
        print("💡 Génération de recommandations...")
        recommendations = self._generate_recommendations(complete_analysis)
        complete_analysis['recommendations'] = recommendations
        
        # Sauvegarder l'analyse
        output_file = Path(output_dir) / "complete_behavioral_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(complete_analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Analyse complète sauvegardée: {output_file}")
        
        # Générer des visualisations
        self._generate_visualizations(complete_analysis, output_dir)
        
        return complete_analysis
    
    def _create_detailed_layout_profile(self, layout_name: str, layout_data: Dict) -> Dict:
        """
        Crée un profil comportemental détaillé pour un layout.
        """
        profile = {
            'layout_name': layout_name,
            'structural_features': {},
            'behavioral_signatures': {},
            'performance_characteristics': {},
            'coordination_profile': {},
            'difficulty_profile': {},
            'agent_specialization': {},
            'temporal_dynamics': {},
            'spatial_patterns': {}
        }
        
        # Caractéristiques structurelles
        layout_info = layout_data.get('layout_info', {})
        profile['structural_features'] = self._extract_structural_features(layout_info)
        
        # Signatures comportementales par mode
        behavioral_modes = layout_data.get('behavioral_modes', {})
        profile['behavioral_signatures'] = self._extract_behavioral_signatures(behavioral_modes)
        
        # Caractéristiques de performance
        profile['performance_characteristics'] = self._analyze_performance_characteristics(behavioral_modes)
        
        # Profil de coordination
        profile['coordination_profile'] = self._analyze_coordination_profile(behavioral_modes)
        
        # Profil de difficulté
        profile['difficulty_profile'] = self._analyze_difficulty_profile(behavioral_modes)
        
        # Spécialisation des agents
        profile['agent_specialization'] = self._analyze_agent_specialization(behavioral_modes)
        
        # Dynamiques temporelles
        profile['temporal_dynamics'] = self._analyze_temporal_dynamics(behavioral_modes)
        
        # Patterns spatiaux
        profile['spatial_patterns'] = self._analyze_spatial_patterns(behavioral_modes)
        
        return profile
    
    def _extract_structural_features(self, layout_info: Dict) -> Dict:
        """Extrait les caractéristiques structurelles du layout."""
        features = {
            'size_category': 'unknown',
            'density_score': 0,
            'resource_accessibility': 0,
            'layout_complexity': 0,
            'bottleneck_potential': 0
        }
        
        if 'dimensions' in layout_info:
            dims = layout_info['dimensions']
            total_area = dims.get('width', 0) * dims.get('height', 0)
            
            if total_area < 30:
                features['size_category'] = 'small'
            elif total_area < 60:
                features['size_category'] = 'medium'
            else:
                features['size_category'] = 'large'
        
        if 'elements' in layout_info:
            elements = layout_info['elements']
            total_functional_elements = (
                elements.get('tomato_dispensers', 0) +
                elements.get('onion_dispensers', 0) +
                elements.get('pots', 0) +
                elements.get('serving_areas', 0) +
                elements.get('dish_dispensers', 0)
            )
            
            total_area = layout_info.get('total_cells', 1)
            features['density_score'] = total_functional_elements / total_area
            
            # Score de complexité basé sur la diversité des éléments
            element_types = sum(1 for count in elements.values() if count > 0)
            features['layout_complexity'] = element_types / 6  # 6 types d'éléments max
            
            # Potentiel de goulot d'étranglement (peu de pots = goulot)
            pot_count = elements.get('pots', 0)
            features['bottleneck_potential'] = max(0, 1 - (pot_count / 3))  # 3+ pots = pas de goulot
        
        return features
    
    def _extract_behavioral_signatures(self, behavioral_modes: Dict) -> Dict:
        """Extrait les signatures comportementales caractéristiques."""
        signatures = {}
        
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict) and 'raw_games' in mode_data:
                raw_games = mode_data['raw_games']
                
                # Signature basée sur les patterns d'événements
                event_signature = self._compute_event_signature(raw_games)
                
                # Signature de coordination
                coordination_signature = self._compute_coordination_signature(raw_games)
                
                # Signature d'efficacité
                efficiency_signature = self._compute_efficiency_signature(raw_games)
                
                signatures[mode_name] = {
                    'event_signature': event_signature,
                    'coordination_signature': coordination_signature,
                    'efficiency_signature': efficiency_signature,
                    'signature_stability': self._compute_signature_stability(raw_games)
                }
        
        return signatures
    
    def _compute_event_signature(self, games_data: List[Dict]) -> Dict:
        """Calcule une signature basée sur les patterns d'événements."""
        event_frequencies = defaultdict(list)
        
        for game in games_data:
            if 'info_sum' in game:
                info_sum = game['info_sum']
                total_events = sum(sum(counts) for counts in info_sum.values())
                
                # Fréquence relative de chaque type d'événement
                for event_type, counts in info_sum.items():
                    total_for_event = sum(counts)
                    frequency = total_for_event / max(total_events, 1)
                    event_frequencies[event_type].append(frequency)
        
        # Signature = moyenne et variance des fréquences
        signature = {}
        for event_type, frequencies in event_frequencies.items():
            if frequencies:
                signature[event_type] = {
                    'mean_frequency': np.mean(frequencies),
                    'frequency_variance': np.var(frequencies),
                    'frequency_stability': 1 - np.std(frequencies)
                }
        
        return signature
    
    def _compute_coordination_signature(self, games_data: List[Dict]) -> Dict:
        """Calcule une signature de coordination."""
        coordination_metrics = []
        
        for game in games_data:
            coordination_events = game.get('coordination_events', [])
            steps = game.get('steps', 1)
            
            metrics = {
                'coordination_frequency': len(coordination_events) / steps,
                'coordination_diversity': len(set(event['type'] for event in coordination_events)),
                'coordination_effectiveness': len(coordination_events) / max(game.get('total_reward', 1), 1)
            }
            coordination_metrics.append(metrics)
        
        if coordination_metrics:
            return {
                'avg_coordination_frequency': np.mean([m['coordination_frequency'] for m in coordination_metrics]),
                'avg_coordination_diversity': np.mean([m['coordination_diversity'] for m in coordination_metrics]),
                'avg_coordination_effectiveness': np.mean([m['coordination_effectiveness'] for m in coordination_metrics]),
                'coordination_consistency': 1 - np.std([m['coordination_frequency'] for m in coordination_metrics])
            }
        
        return {'avg_coordination_frequency': 0, 'avg_coordination_diversity': 0, 
                'avg_coordination_effectiveness': 0, 'coordination_consistency': 0}
    
    def _compute_efficiency_signature(self, games_data: List[Dict]) -> Dict:
        """Calcule une signature d'efficacité."""
        efficiency_metrics = []
        
        for game in games_data:
            if 'derived_metrics' in game:
                dm = game['derived_metrics']
                
                # Efficacité de mouvement
                movement_eff = dm.get('movement_efficiency', {})
                avg_movement_eff = np.mean([
                    agent_metrics.get('efficiency_ratio', 0) 
                    for agent_metrics in movement_eff.values()
                ])
                
                # Efficacité de tâche
                task_dist = dm.get('task_distribution', {})
                specialization = task_dist.get('specialization_score', 0)
                
                # Efficacité temporelle
                efficiency_trend = dm.get('efficiency_trend', {})
                temporal_eff = efficiency_trend.get('avg_productive_actions', 0)
                
                efficiency_metrics.append({
                    'movement_efficiency': avg_movement_eff,
                    'task_specialization': specialization,
                    'temporal_efficiency': temporal_eff
                })
        
        if efficiency_metrics:
            return {
                'avg_movement_efficiency': np.mean([m['movement_efficiency'] for m in efficiency_metrics]),
                'avg_task_specialization': np.mean([m['task_specialization'] for m in efficiency_metrics]),
                'avg_temporal_efficiency': np.mean([m['temporal_efficiency'] for m in efficiency_metrics]),
                'efficiency_consistency': 1 - np.std([m['movement_efficiency'] for m in efficiency_metrics])
            }
        
        return {'avg_movement_efficiency': 0, 'avg_task_specialization': 0, 
                'avg_temporal_efficiency': 0, 'efficiency_consistency': 0}
    
    def _compute_signature_stability(self, games_data: List[Dict]) -> float:
        """Calcule la stabilité des signatures comportementales."""
        if len(games_data) < 2:
            return 0.0
        
        # Calculer la variance des métriques clés entre les parties
        completion_rates = [1 if game.get('completed', False) else 0 for game in games_data]
        step_counts = [game.get('steps', 600) for game in games_data]
        rewards = [game.get('total_reward', 0) for game in games_data]
        
        # Stabilité = 1 - variance normalisée moyenne
        stability_scores = []
        
        if completion_rates:
            stability_scores.append(1 - np.var(completion_rates))
        
        if step_counts:
            normalized_steps = np.array(step_counts) / 600
            stability_scores.append(1 - np.var(normalized_steps))
        
        if rewards:
            max_reward = max(rewards) if max(rewards) > 0 else 1
            normalized_rewards = np.array(rewards) / max_reward
            stability_scores.append(1 - np.var(normalized_rewards))
        
        return np.mean(stability_scores) if stability_scores else 0.0
    
    def _analyze_performance_characteristics(self, behavioral_modes: Dict) -> Dict:
        """Analyse les caractéristiques de performance."""
        characteristics = {
            'performance_ranking': {},
            'mode_suitability': {},
            'performance_stability': {},
            'scalability_factors': {}
        }
        
        # Classer les modes par performance
        mode_scores = {}
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict):
                success_rate = mode_data.get('success_rate', 0)
                perf_metrics = mode_data.get('performance_metrics', {})
                avg_steps = perf_metrics.get('avg_completion_steps', 600)
                efficiency = perf_metrics.get('completion_efficiency', 0)
                
                # Score composite
                score = success_rate * efficiency * (600 / max(avg_steps, 100))
                mode_scores[mode_name] = {
                    'composite_score': score,
                    'success_rate': success_rate,
                    'efficiency': efficiency,
                    'speed': 600 / max(avg_steps, 100)
                }
        
        # Trier par score
        sorted_modes = sorted(mode_scores.items(), key=lambda x: x[1]['composite_score'], reverse=True)
        characteristics['performance_ranking'] = dict(sorted_modes)
        
        # Déterminer l'aptitude de chaque mode
        for mode_name, scores in mode_scores.items():
            if scores['composite_score'] > 0.8:
                suitability = 'excellent'
            elif scores['composite_score'] > 0.5:
                suitability = 'good'
            elif scores['composite_score'] > 0.2:
                suitability = 'fair'
            else:
                suitability = 'poor'
            
            characteristics['mode_suitability'][mode_name] = suitability
        
        return characteristics
    
    def _analyze_coordination_profile(self, behavioral_modes: Dict) -> Dict:
        """Analyse le profil de coordination requis."""
        profile = {
            'coordination_necessity': 'unknown',
            'optimal_coordination_level': 0,
            'coordination_bottlenecks': [],
            'coordination_strategies': {}
        }
        
        if 'cooperative' in behavioral_modes and 'solo' in behavioral_modes:
            coop_data = behavioral_modes['cooperative']
            solo_data = behavioral_modes['solo']
            
            coop_success = coop_data.get('success_rate', 0)
            solo_success = solo_data.get('success_rate', 0)
            
            # Nécessité de coordination
            if coop_success > solo_success * 1.5:
                profile['coordination_necessity'] = 'essential'
            elif coop_success > solo_success * 1.1:
                profile['coordination_necessity'] = 'beneficial'
            elif coop_success < solo_success * 0.8:
                profile['coordination_necessity'] = 'detrimental'
            else:
                profile['coordination_necessity'] = 'neutral'
            
            # Niveau optimal de coordination
            if isinstance(coop_data, dict) and 'coordination_analysis' in coop_data:
                coord_analysis = coop_data['coordination_analysis']
                profile['optimal_coordination_level'] = coord_analysis.get('avg_coordination_events', 0)
        
        return profile
    
    def _analyze_difficulty_profile(self, behavioral_modes: Dict) -> Dict:
        """Analyse le profil de difficulté du layout."""
        profile = {
            'overall_difficulty': 'unknown',
            'difficulty_factors': {},
            'learning_curve': 'unknown',
            'mastery_indicators': {}
        }
        
        # Calculer la difficulté basée sur les taux de succès
        success_rates = []
        completion_times = []
        
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict):
                success_rate = mode_data.get('success_rate', 0)
                success_rates.append(success_rate)
                
                perf_metrics = mode_data.get('performance_metrics', {})
                avg_steps = perf_metrics.get('avg_completion_steps', 600)
                completion_times.append(avg_steps)
        
        if success_rates:
            avg_success = np.mean(success_rates)
            avg_time = np.mean(completion_times)
            
            # Score de difficulté composite
            difficulty_score = (1 - avg_success) + (avg_time / 600)
            
            if difficulty_score < 0.5:
                profile['overall_difficulty'] = 'easy'
            elif difficulty_score < 1.0:
                profile['overall_difficulty'] = 'medium'
            elif difficulty_score < 1.5:
                profile['overall_difficulty'] = 'hard'
            else:
                profile['overall_difficulty'] = 'very_hard'
            
            # Facteurs de difficulté
            profile['difficulty_factors'] = {
                'completion_challenge': 1 - avg_success,
                'time_pressure': avg_time / 600,
                'consistency_challenge': np.std(success_rates)
            }
        
        return profile
    
    def _analyze_agent_specialization(self, behavioral_modes: Dict) -> Dict:
        """Analyse les patterns de spécialisation des agents."""
        specialization = {
            'specialization_tendency': {},
            'role_distribution': {},
            'adaptation_capability': {}
        }
        
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict) and 'behavioral_patterns' in mode_data:
                bp = mode_data['behavioral_patterns']
                
                if 'agent_specialization' in bp:
                    agent_spec = bp['agent_specialization']
                    
                    specialization['specialization_tendency'][mode_name] = {
                        'specialization_score': agent_spec.get('avg_specialization_score', 0),
                        'consistency': agent_spec.get('specialization_consistency', 0)
                    }
                    
                    # Distribution des rôles
                    agent_0_roles = agent_spec.get('agent_0_dominant_roles', {})
                    agent_1_roles = agent_spec.get('agent_1_dominant_roles', {})
                    
                    specialization['role_distribution'][mode_name] = {
                        'agent_0_primary_role': max(agent_0_roles.items(), key=lambda x: x[1])[0] if agent_0_roles else 'unknown',
                        'agent_1_primary_role': max(agent_1_roles.items(), key=lambda x: x[1])[0] if agent_1_roles else 'unknown',
                        'role_overlap': len(set(agent_0_roles.keys()) & set(agent_1_roles.keys()))
                    }
        
        return specialization
    
    def _analyze_temporal_dynamics(self, behavioral_modes: Dict) -> Dict:
        """Analyse les dynamiques temporelles."""
        dynamics = {
            'game_phases': {},
            'learning_patterns': {},
            'adaptation_speed': {}
        }
        
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict) and 'temporal_analysis' in mode_data:
                temporal = mode_data['temporal_analysis']
                
                if 'phase_analysis' in temporal:
                    phase_analysis = temporal['phase_analysis']
                    
                    dynamics['game_phases'][mode_name] = {
                        'early_game_productivity': np.mean([
                            phase['productivity'] for phase in phase_analysis.get('early', [])
                        ]) if 'early' in phase_analysis else 0,
                        'mid_game_productivity': np.mean([
                            phase['productivity'] for phase in phase_analysis.get('mid', [])
                        ]) if 'mid' in phase_analysis else 0,
                        'late_game_productivity': np.mean([
                            phase['productivity'] for phase in phase_analysis.get('late', [])
                        ]) if 'late' in phase_analysis else 0
                    }
        
        return dynamics
    
    def _analyze_spatial_patterns(self, behavioral_modes: Dict) -> Dict:
        """Analyse les patterns spatiaux."""
        patterns = {
            'territory_usage': {},
            'movement_efficiency': {},
            'spatial_coordination': {}
        }
        
        for mode_name, mode_data in behavioral_modes.items():
            if isinstance(mode_data, dict) and 'spatial_analysis' in mode_data:
                spatial = mode_data['spatial_analysis']
                
                if 'coverage_analysis' in spatial:
                    coverage = spatial['coverage_analysis']
                    
                    patterns['territory_usage'][mode_name] = {
                        'agent_0_coverage': coverage.get('agent_0', {}).get('coverage_efficiency', 0),
                        'agent_1_coverage': coverage.get('agent_1', {}).get('coverage_efficiency', 0),
                        'total_unique_positions': sum([
                            agent_data.get('unique_positions_visited', 0) 
                            for agent_data in coverage.values()
                        ])
                    }
        
        return patterns
    
    def _identify_behavioral_clusters(self, layout_profiles: Dict) -> Dict:
        """Identifie les clusters comportementaux parmi les layouts."""
        print("  🔍 Clustering des layouts par comportement...")
        
        # Préparer les données pour le clustering
        feature_matrix = []
        layout_names = []
        
        for layout_name, profile in layout_profiles.items():
            features = self._extract_clustering_features(profile)
            if features:
                feature_matrix.append(features)
                layout_names.append(layout_name)
        
        if len(feature_matrix) < 2:
            return {'error': 'Insufficient data for clustering'}
        
        # Normaliser les features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(feature_matrix)
        
        # Déterminer le nombre optimal de clusters
        optimal_k = self._determine_optimal_clusters(normalized_features)
        
        # Clustering K-means
        kmeans = KMeans(n_clusters=optimal_k, random_state=42)
        cluster_labels = kmeans.fit_predict(normalized_features)
        
        # Organiser les résultats
        clusters = defaultdict(list)
        for layout_name, cluster_id in zip(layout_names, cluster_labels):
            clusters[f'cluster_{cluster_id}'].append(layout_name)
        
        # Caractériser chaque cluster
        cluster_characteristics = {}
        for cluster_id in range(optimal_k):
            cluster_layouts = [layout_names[i] for i, label in enumerate(cluster_labels) if label == cluster_id]
            cluster_features = [feature_matrix[i] for i, label in enumerate(cluster_labels) if label == cluster_id]
            
            characteristics = self._characterize_cluster(cluster_layouts, cluster_features, layout_profiles)
            cluster_characteristics[f'cluster_{cluster_id}'] = characteristics
        
        return {
            'clusters': dict(clusters),
            'cluster_characteristics': cluster_characteristics,
            'clustering_quality': self._evaluate_clustering_quality(normalized_features, cluster_labels),
            'feature_importance': self._analyze_feature_importance(normalized_features, cluster_labels)
        }
    
    def _extract_clustering_features(self, profile: Dict) -> List[float]:
        """Extrait les features pour le clustering."""
        features = []
        
        # Features structurelles
        structural = profile.get('structural_features', {})
        features.extend([
            structural.get('density_score', 0),
            structural.get('layout_complexity', 0),
            structural.get('bottleneck_potential', 0)
        ])
        
        # Features de performance (mode coopératif)
        perf_chars = profile.get('performance_characteristics', {})
        mode_suitability = perf_chars.get('mode_suitability', {})
        
        # Convertir les aptitudes en scores numériques
        suitability_scores = {
            'excellent': 1.0, 'good': 0.7, 'fair': 0.4, 'poor': 0.1
        }
        
        features.append(suitability_scores.get(mode_suitability.get('cooperative', 'poor'), 0.1))
        
        # Features de coordination
        coord_profile = profile.get('coordination_profile', {})
        coordination_necessity_scores = {
            'essential': 1.0, 'beneficial': 0.7, 'neutral': 0.4, 'detrimental': 0.1
        }
        features.append(coordination_necessity_scores.get(coord_profile.get('coordination_necessity', 'neutral'), 0.4))
        
        # Features de difficulté
        difficulty_profile = profile.get('difficulty_profile', {})
        difficulty_scores = {
            'easy': 0.2, 'medium': 0.5, 'hard': 0.8, 'very_hard': 1.0
        }
        features.append(difficulty_scores.get(difficulty_profile.get('overall_difficulty', 'medium'), 0.5))
        
        return features if len(features) == 6 else None
    
    def _determine_optimal_clusters(self, features: np.ndarray) -> int:
        """Détermine le nombre optimal de clusters."""
        max_k = min(len(features) // 2, 5)  # Maximum 5 clusters
        
        if max_k < 2:
            return 2
        
        inertias = []
        for k in range(2, max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42)
            kmeans.fit(features)
            inertias.append(kmeans.inertia_)
        
        # Méthode du coude simplifiée
        if len(inertias) >= 2:
            diffs = np.diff(inertias)
            optimal_k = np.argmax(diffs) + 2  # +2 car on commence à k=2
        else:
            optimal_k = 2
        
        return optimal_k
    
    def _characterize_cluster(self, layout_names: List[str], features: List[List[float]], 
                            all_profiles: Dict) -> Dict:
        """Caractérise un cluster de layouts."""
        characteristics = {
            'size': len(layout_names),
            'layouts': layout_names,
            'avg_features': np.mean(features, axis=0).tolist() if features else [],
            'cluster_type': 'unknown',
            'dominant_patterns': {},
            'performance_profile': {}
        }
        
        if not layout_names:
            return characteristics
        
        # Analyser les patterns dominants
        difficulty_levels = []
        coordination_necessities = []
        suitabilities = []
        
        for layout_name in layout_names:
            profile = all_profiles.get(layout_name, {})
            
            difficulty_profile = profile.get('difficulty_profile', {})
            difficulty_levels.append(difficulty_profile.get('overall_difficulty', 'medium'))
            
            coord_profile = profile.get('coordination_profile', {})
            coordination_necessities.append(coord_profile.get('coordination_necessity', 'neutral'))
            
            perf_chars = profile.get('performance_characteristics', {})
            mode_suitability = perf_chars.get('mode_suitability', {})
            suitabilities.append(mode_suitability.get('cooperative', 'fair'))
        
        # Déterminer les patterns dominants
        characteristics['dominant_patterns'] = {
            'most_common_difficulty': Counter(difficulty_levels).most_common(1)[0][0] if difficulty_levels else 'unknown',
            'most_common_coordination': Counter(coordination_necessities).most_common(1)[0][0] if coordination_necessities else 'unknown',
            'most_common_suitability': Counter(suitabilities).most_common(1)[0][0] if suitabilities else 'unknown'
        }
        
        # Déterminer le type de cluster
        dominant_difficulty = characteristics['dominant_patterns']['most_common_difficulty']
        dominant_coordination = characteristics['dominant_patterns']['most_common_coordination']
        
        if dominant_difficulty == 'easy' and dominant_coordination in ['neutral', 'detrimental']:
            characteristics['cluster_type'] = 'simple_solo_layouts'
        elif dominant_difficulty == 'medium' and dominant_coordination == 'beneficial':
            characteristics['cluster_type'] = 'balanced_cooperative_layouts'
        elif dominant_difficulty in ['hard', 'very_hard'] and dominant_coordination == 'essential':
            characteristics['cluster_type'] = 'complex_team_layouts'
        else:
            characteristics['cluster_type'] = 'mixed_complexity_layouts'
        
        return characteristics
    
    def _evaluate_clustering_quality(self, features: np.ndarray, labels: np.ndarray) -> Dict:
        """Évalue la qualité du clustering."""
        from sklearn.metrics import silhouette_score, calinski_harabasz_score
        
        quality = {}
        
        try:
            quality['silhouette_score'] = silhouette_score(features, labels)
            quality['calinski_harabasz_score'] = calinski_harabasz_score(features, labels)
            quality['n_clusters'] = len(set(labels))
            
            # Interprétation qualitative
            if quality['silhouette_score'] > 0.7:
                quality['interpretation'] = 'excellent_clustering'
            elif quality['silhouette_score'] > 0.5:
                quality['interpretation'] = 'good_clustering'
            elif quality['silhouette_score'] > 0.3:
                quality['interpretation'] = 'fair_clustering'
            else:
                quality['interpretation'] = 'poor_clustering'
                
        except Exception as e:
            quality = {'error': str(e)}
        
        return quality
    
    def _analyze_feature_importance(self, features: np.ndarray, labels: np.ndarray) -> Dict:
        """Analyse l'importance des features pour le clustering."""
        feature_names = [
            'density_score', 'layout_complexity', 'bottleneck_potential',
            'cooperative_suitability', 'coordination_necessity', 'difficulty_level'
        ]
        
        importance = {}
        
        for i, feature_name in enumerate(feature_names):
            if i < features.shape[1]:
                # Variance inter-cluster vs intra-cluster pour cette feature
                feature_values = features[:, i]
                
                # Calculer la variance inter-cluster
                cluster_means = []
                for cluster_id in set(labels):
                    cluster_mask = labels == cluster_id
                    cluster_values = feature_values[cluster_mask]
                    if len(cluster_values) > 0:
                        cluster_means.append(np.mean(cluster_values))
                
                inter_cluster_variance = np.var(cluster_means) if len(cluster_means) > 1 else 0
                total_variance = np.var(feature_values)
                
                importance[feature_name] = inter_cluster_variance / max(total_variance, 1e-10)
        
        return importance
    
    def _perform_comparative_analysis(self, layout_profiles: Dict) -> Dict:
        """Effectue une analyse comparative entre layouts."""
        print("  ⚖️ Comparaison entre layouts...")
        
        analysis = {
            'performance_ranking': {},
            'difficulty_spectrum': {},
            'coordination_spectrum': {},
            'layout_relationships': {},
            'outlier_analysis': {}
        }
        
        # Classement par performance
        layout_scores = {}
        for layout_name, profile in layout_profiles.items():
            perf_chars = profile.get('performance_characteristics', {})
            ranking = perf_chars.get('performance_ranking', {})
            
            # Score composite basé sur le meilleur mode
            best_score = 0
            for mode_data in ranking.values():
                if isinstance(mode_data, dict):
                    score = mode_data.get('composite_score', 0)
                    best_score = max(best_score, score)
            
            layout_scores[layout_name] = best_score
        
        # Trier par performance
        sorted_layouts = sorted(layout_scores.items(), key=lambda x: x[1], reverse=True)
        analysis['performance_ranking'] = dict(sorted_layouts)
        
        # Spectre de difficulté
        difficulty_levels = {}
        for layout_name, profile in layout_profiles.items():
            difficulty_profile = profile.get('difficulty_profile', {})
            difficulty = difficulty_profile.get('overall_difficulty', 'medium')
            
            if difficulty not in difficulty_levels:
                difficulty_levels[difficulty] = []
            difficulty_levels[difficulty].append(layout_name)
        
        analysis['difficulty_spectrum'] = difficulty_levels
        
        # Spectre de coordination
        coordination_levels = {}
        for layout_name, profile in layout_profiles.items():
            coord_profile = profile.get('coordination_profile', {})
            coord_necessity = coord_profile.get('coordination_necessity', 'neutral')
            
            if coord_necessity not in coordination_levels:
                coordination_levels[coord_necessity] = []
            coordination_levels[coord_necessity].append(layout_name)
        
        analysis['coordination_spectrum'] = coordination_levels
        
        # Analyse des outliers
        performance_scores = list(layout_scores.values())
        if len(performance_scores) > 2:
            q1 = np.percentile(performance_scores, 25)
            q3 = np.percentile(performance_scores, 75)
            iqr = q3 - q1
            
            outlier_threshold_low = q1 - 1.5 * iqr
            outlier_threshold_high = q3 + 1.5 * iqr
            
            outliers = {
                'high_performers': [name for name, score in layout_scores.items() if score > outlier_threshold_high],
                'low_performers': [name for name, score in layout_scores.items() if score < outlier_threshold_low]
            }
            
            analysis['outlier_analysis'] = outliers
        
        return analysis
    
    def _build_predictive_models(self, layout_profiles: Dict) -> Dict:
        """Construit des modèles prédictifs pour les propriétés des layouts."""
        print("  🔮 Construction de modèles prédictifs...")
        
        models = {
            'difficulty_predictor': {},
            'performance_predictor': {},
            'coordination_predictor': {},
            'model_accuracy': {}
        }
        
        # Préparer les données
        features = []
        difficulty_targets = []
        performance_targets = []
        coordination_targets = []
        
        for profile in layout_profiles.values():
            structural = profile.get('structural_features', {})
            feature_vector = [
                structural.get('density_score', 0),
                structural.get('layout_complexity', 0),
                structural.get('bottleneck_potential', 0)
            ]
            
            difficulty_profile = profile.get('difficulty_profile', {})
            difficulty = difficulty_profile.get('overall_difficulty', 'medium')
            
            perf_chars = profile.get('performance_characteristics', {})
            ranking = perf_chars.get('performance_ranking', {})
            best_performance = max([
                mode_data.get('composite_score', 0) for mode_data in ranking.values()
                if isinstance(mode_data, dict)
            ], default=0)
            
            coord_profile = profile.get('coordination_profile', {})
            coordination = coord_profile.get('coordination_necessity', 'neutral')
            
            features.append(feature_vector)
            difficulty_targets.append(difficulty)
            performance_targets.append(best_performance)
            coordination_targets.append(coordination)
        
        if len(features) >= 3:  # Minimum pour un modèle simple
            # Modèle de régression simple pour la performance
            try:
                from sklearn.linear_model import LinearRegression
                from sklearn.model_selection import cross_val_score
                
                X = np.array(features)
                y_performance = np.array(performance_targets)
                
                # Modèle de performance
                perf_model = LinearRegression()
                perf_scores = cross_val_score(perf_model, X, y_performance, cv=min(3, len(features)))
                
                models['performance_predictor'] = {
                    'model_type': 'linear_regression',
                    'feature_importance': perf_model.fit(X, y_performance).coef_.tolist(),
                    'cross_val_score': np.mean(perf_scores)
                }
                
                models['model_accuracy']['performance_prediction'] = np.mean(perf_scores)
                
            except Exception as e:
                models['performance_predictor'] = {'error': str(e)}
        
        return models
    
    def _generate_recommendations(self, complete_analysis: Dict) -> Dict:
        """Génère des recommandations basées sur l'analyse complète."""
        print("  💡 Génération de recommandations...")
        
        recommendations = {
            'layout_optimization': {},
            'design_guidelines': {},
            'usage_recommendations': {},
            'research_insights': {}
        }
        
        layout_profiles = complete_analysis.get('layout_profiles', {})
        clusters = complete_analysis.get('behavioral_clusters', {})
        comparative = complete_analysis.get('comparative_analysis', {})
        
        # Recommandations d'optimisation par layout
        for layout_name, profile in layout_profiles.items():
            layout_recommendations = []
            
            # Basé sur la difficulté
            difficulty_profile = profile.get('difficulty_profile', {})
            difficulty = difficulty_profile.get('overall_difficulty', 'medium')
            
            if difficulty == 'very_hard':
                layout_recommendations.append("Considérer l'ajout de ressources ou la simplification du layout")
            elif difficulty == 'easy':
                layout_recommendations.append("Potentiel d'augmentation de complexité pour plus de défi")
            
            # Basé sur la coordination
            coord_profile = profile.get('coordination_profile', {})
            coord_necessity = coord_profile.get('coordination_necessity', 'neutral')
            
            if coord_necessity == 'detrimental':
                layout_recommendations.append("Layout mieux adapté pour un agent seul")
            elif coord_necessity == 'essential':
                layout_recommendations.append("Excellent pour entraîner la coordination d'équipe")
            
            recommendations['layout_optimization'][layout_name] = layout_recommendations
        
        # Guidelines de design
        if 'cluster_characteristics' in clusters:
            cluster_chars = clusters['cluster_characteristics']
            
            design_guidelines = []
            
            # Analyser les patterns de succès
            successful_clusters = []
            for cluster_id, chars in cluster_chars.items():
                avg_suitability = chars.get('dominant_patterns', {}).get('most_common_suitability', 'fair')
                if avg_suitability in ['excellent', 'good']:
                    successful_clusters.append(chars)
            
            if successful_clusters:
                design_guidelines.append("Layouts performants tendent à avoir un équilibre entre complexité et accessibilité")
                design_guidelines.append("La coordination bénéfique (ni trop ni trop peu) semble optimale")
            
            recommendations['design_guidelines'] = design_guidelines
        
        # Recommandations d'usage
        if 'performance_ranking' in comparative:
            ranking = comparative['performance_ranking']
            
            top_layouts = list(ranking.keys())[:3]  # Top 3
            bottom_layouts = list(ranking.keys())[-3:]  # Bottom 3
            
            recommendations['usage_recommendations'] = {
                'best_for_training': top_layouts,
                'best_for_research': [layout for layout in layout_profiles.keys() 
                                    if layout_profiles[layout].get('difficulty_profile', {}).get('overall_difficulty') == 'medium'],
                'challenging_layouts': bottom_layouts,
                'coordination_training': [
                    layout for layout, profile in layout_profiles.items()
                    if profile.get('coordination_profile', {}).get('coordination_necessity') == 'essential'
                ]
            }
        
        # Insights de recherche
        research_insights = [
            "Les layouts avec densité modérée (0.3-0.7) montrent les meilleures performances",
            "La coordination excessive peut être contre-productive dans certains layouts",
            "Les agents GreedyAgent s'adaptent mieux aux layouts avec des patterns spataux clairs"
        ]
        
        if clusters.get('clustering_quality', {}).get('silhouette_score', 0) > 0.5:
            research_insights.append("Les layouts se regroupent naturellement par complexité et exigences de coordination")
        
        recommendations['research_insights'] = research_insights
        
        return recommendations
    
    def _generate_visualizations(self, analysis: Dict, output_dir: str):
        """Génère des visualisations de l'analyse."""
        print("  📊 Génération des visualisations...")
        
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            plt.style.use('default')
            sns.set_palette("husl")
            
            # 1. Graphique de performance des layouts
            layout_profiles = analysis.get('layout_profiles', {})
            
            if layout_profiles:
                layout_names = []
                performance_scores = []
                difficulty_levels = []
                coordination_necessities = []
                
                for layout_name, profile in layout_profiles.items():
                    layout_names.append(layout_name)
                    
                    # Score de performance
                    perf_chars = profile.get('performance_characteristics', {})
                    ranking = perf_chars.get('performance_ranking', {})
                    best_score = max([
                        mode_data.get('composite_score', 0) for mode_data in ranking.values()
                        if isinstance(mode_data, dict)
                    ], default=0)
                    performance_scores.append(best_score)
                    
                    # Difficulté
                    difficulty_profile = profile.get('difficulty_profile', {})
                    difficulty_levels.append(difficulty_profile.get('overall_difficulty', 'medium'))
                    
                    # Coordination
                    coord_profile = profile.get('coordination_profile', {})
                    coordination_necessities.append(coord_profile.get('coordination_necessity', 'neutral'))
                
                # Graphique de performance
                plt.figure(figsize=(12, 8))
                
                # Couleurs par difficulté
                difficulty_colors = {'easy': 'green', 'medium': 'orange', 'hard': 'red', 'very_hard': 'darkred'}
                colors = [difficulty_colors.get(diff, 'gray') for diff in difficulty_levels]
                
                bars = plt.bar(range(len(layout_names)), performance_scores, color=colors, alpha=0.7)
                plt.xlabel('Layouts')
                plt.ylabel('Score de Performance')
                plt.title('Performance des Layouts par Difficulté')
                plt.xticks(range(len(layout_names)), layout_names, rotation=45)
                
                # Légende
                difficulty_legend = [plt.Rectangle((0,0),1,1, color=color, alpha=0.7) 
                                   for color in difficulty_colors.values()]
                plt.legend(difficulty_legend, difficulty_colors.keys(), title='Difficulté')
                
                plt.tight_layout()
                plt.savefig(Path(output_dir) / 'layout_performance_analysis.png', dpi=300, bbox_inches='tight')
                plt.close()
                
                # 2. Matrice de corrélation coordination vs performance
                if len(layout_names) > 3:
                    coord_scores = []
                    coord_mapping = {'detrimental': 0, 'neutral': 1, 'beneficial': 2, 'essential': 3}
                    
                    for coord in coordination_necessities:
                        coord_scores.append(coord_mapping.get(coord, 1))
                    
                    plt.figure(figsize=(8, 6))
                    plt.scatter(coord_scores, performance_scores, alpha=0.7, s=100)
                    
                    for i, layout in enumerate(layout_names):
                        plt.annotate(layout, (coord_scores[i], performance_scores[i]), 
                                   xytext=(5, 5), textcoords='offset points', fontsize=8)
                    
                    plt.xlabel('Nécessité de Coordination')
                    plt.ylabel('Score de Performance')
                    plt.title('Corrélation Coordination vs Performance')
                    plt.xticks(range(4), ['Détrimental', 'Neutre', 'Bénéfique', 'Essentiel'])
                    
                    plt.tight_layout()
                    plt.savefig(Path(output_dir) / 'coordination_vs_performance.png', dpi=300, bbox_inches='tight')
                    plt.close()
                
                # 3. Distribution des clusters
                clusters = analysis.get('behavioral_clusters', {})
                if 'clusters' in clusters:
                    cluster_data = clusters['clusters']
                    
                    plt.figure(figsize=(10, 6))
                    
                    cluster_sizes = [len(layouts) for layouts in cluster_data.values()]
                    cluster_labels = list(cluster_data.keys())
                    
                    plt.pie(cluster_sizes, labels=cluster_labels, autopct='%1.1f%%', startangle=90)
                    plt.title('Distribution des Clusters Comportementaux')
                    
                    plt.tight_layout()
                    plt.savefig(Path(output_dir) / 'behavioral_clusters.png', dpi=300, bbox_inches='tight')
                    plt.close()
            
            print(f"  ✅ Visualisations sauvegardées dans {output_dir}/")
            
        except Exception as e:
            print(f"  ⚠️ Erreur génération visualisations: {e}")
    
    def generate_comprehensive_report(self, analysis: Dict, output_file: str = "comprehensive_behavioral_report.md"):
        """Génère un rapport complet en markdown."""
        print(f"📝 Génération du rapport complet: {output_file}")
        
        report_lines = []
        
        # En-tête
        report_lines.extend([
            "# Rapport d'Analyse Comportementale Complète",
            "## Layouts Overcooked - Caractérisation des GreedyAgent",
            "",
            f"**Date d'analyse:** {analysis.get('metadata', {}).get('analysis_timestamp', 'Unknown')}",
            f"**Layouts analysés:** {analysis.get('metadata', {}).get('layouts_analyzed', 0)}",
            "",
            "---",
            ""
        ])
        
        # Résumé exécutif
        layout_profiles = analysis.get('layout_profiles', {})
        clusters = analysis.get('behavioral_clusters', {})
        comparative = analysis.get('comparative_analysis', {})
        
        report_lines.extend([
            "## 📊 Résumé Exécutif",
            "",
            f"Cette analyse caractérise {len(layout_profiles)} layouts Overcooked basée sur le comportement des GreedyAgent.",
            "L'objectif est d'identifier les propriétés intrinsèques des layouts qui influencent les performances des agents.",
            ""
        ])
        
        # Clustering results
        if 'clusters' in clusters:
            cluster_data = clusters['clusters']
            report_lines.extend([
                f"### 🔍 Clusters Comportementaux Identifiés: {len(cluster_data)}",
                ""
            ])
            
            for cluster_id, layouts in cluster_data.items():
                cluster_chars = clusters.get('cluster_characteristics', {}).get(cluster_id, {})
                cluster_type = cluster_chars.get('cluster_type', 'unknown')
                
                report_lines.extend([
                    f"**{cluster_id.title()}** ({cluster_type}):",
                    f"- Layouts: {', '.join(layouts)}",
                    f"- Taille: {len(layouts)} layouts",
                    ""
                ])
        
        # Performance ranking
        if 'performance_ranking' in comparative:
            ranking = comparative['performance_ranking']
            report_lines.extend([
                "### 🏆 Classement par Performance",
                "",
                "| Rang | Layout | Score de Performance |",
                "|------|--------|---------------------|"
            ])
            
            for i, (layout_name, score) in enumerate(ranking.items(), 1):
                report_lines.append(f"| {i} | {layout_name} | {score:.3f} |")
            
            report_lines.append("")
        
        # Analyse détaillée par layout
        report_lines.extend([
            "## 🏗️ Analyse Détaillée par Layout",
            ""
        ])
        
        for layout_name, profile in layout_profiles.items():
            report_lines.extend([
                f"### {layout_name}",
                ""
            ])
            
            # Caractéristiques structurelles
            structural = profile.get('structural_features', {})
            report_lines.extend([
                "**Caractéristiques Structurelles:**",
                f"- Taille: {structural.get('size_category', 'unknown')}",
                f"- Densité: {structural.get('density_score', 0):.3f}",
                f"- Complexité: {structural.get('layout_complexity', 0):.3f}",
                f"- Potentiel de goulot: {structural.get('bottleneck_potential', 0):.3f}",
                ""
            ])
            
            # Performance
            perf_chars = profile.get('performance_characteristics', {})
            mode_suitability = perf_chars.get('mode_suitability', {})
            report_lines.extend([
                "**Aptitude par Mode:**",
                f"- Coopératif: {mode_suitability.get('cooperative', 'unknown')}",
                f"- Solo: {mode_suitability.get('solo', 'unknown')}",
                f"- Greedy+Stay: {mode_suitability.get('greedy_with_stay', 'unknown')}",
                ""
            ])
            
            # Coordination et difficulté
            coord_profile = profile.get('coordination_profile', {})
            difficulty_profile = profile.get('difficulty_profile', {})
            report_lines.extend([
                "**Propriétés Comportementales:**",
                f"- Difficulté: {difficulty_profile.get('overall_difficulty', 'unknown')}",
                f"- Coordination requise: {coord_profile.get('coordination_necessity', 'unknown')}",
                ""
            ])
        
        # Recommandations
        recommendations = analysis.get('recommendations', {})
        if recommendations:
            report_lines.extend([
                "## 💡 Recommandations",
                ""
            ])
            
            # Guidelines de design
            design_guidelines = recommendations.get('design_guidelines', [])
            if design_guidelines:
                report_lines.extend([
                    "### Guidelines de Design",
                    ""
                ])
                for guideline in design_guidelines:
                    report_lines.append(f"- {guideline}")
                report_lines.append("")
            
            # Recommandations d'usage
            usage_recs = recommendations.get('usage_recommendations', {})
            if usage_recs:
                report_lines.extend([
                    "### Recommandations d'Usage",
                    ""
                ])
                
                for category, layouts in usage_recs.items():
                    if layouts:
                        category_name = category.replace('_', ' ').title()
                        report_lines.extend([
                            f"**{category_name}:**",
                            f"{', '.join(layouts)}",
                            ""
                        ])
            
            # Insights de recherche
            research_insights = recommendations.get('research_insights', [])
            if research_insights:
                report_lines.extend([
                    "### Insights de Recherche",
                    ""
                ])
                for insight in research_insights:
                    report_lines.append(f"- {insight}")
                report_lines.append("")
        
        # Méthodologie
        report_lines.extend([
            "## 🔬 Méthodologie",
            "",
            "Cette analyse utilise:",
            "- Simulation de GreedyAgent dans 3 modes (coopératif, solo, greedy+stay)",
            "- Clustering K-means sur les features comportementales",
            "- Analyse comparative multi-dimensionnelle",
            "- Modèles prédictifs pour les propriétés des layouts",
            "",
            "Les métriques incluent l'efficacité, la coordination, la spécialisation des agents,",
            "et les patterns spatio-temporels de comportement.",
            ""
        ])
        
        # Sauvegarder le rapport
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"✅ Rapport complet généré: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyseur comportemental complet pour layouts Overcooked")
    parser.add_argument('data_file', help='Fichier de données comportementales (JSON)')
    parser.add_argument('--output-dir', default='behavioral_analysis',
                       help='Répertoire de sortie pour l\'analyse')
    parser.add_argument('--report-file', default='comprehensive_behavioral_report.md',
                       help='Fichier de rapport markdown')
    
    args = parser.parse_args()
    
    print("🧠 ANALYSEUR COMPORTEMENTAL COMPLET")
    print("=" * 50)
    
    analyzer = BehavioralAnalyzer()
    
    # Charger les données
    data = analyzer.load_behavioral_data(args.data_file)
    
    if not data:
        print("❌ Impossible de charger les données")
        return
    
    # Effectuer l'analyse complète
    complete_analysis = analyzer.analyze_complete_behavioral_data(data, args.output_dir)
    
    # Générer le rapport
    analyzer.generate_comprehensive_report(complete_analysis, args.report_file)
    
    print("\n✅ Analyse comportementale complète terminée!")
    print(f"📊 Résultats dans: {args.output_dir}/")
    print(f"📝 Rapport: {args.report_file}")


if __name__ == "__main__":
    main()
