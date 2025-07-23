#!/usr/bin/env python3
"""
test_behavioral_characterization.py

Script de test pour la caractérisation comportementale des layouts Overcooked.
Teste les nouvelles méthodes d'analyse des patterns de mouvement et d'interaction.
"""

import json
import numpy as np
from layout_characterizer import LayoutCharacterizer

def create_test_layout_data():
    """Crée des données de test pour valider la caractérisation comportementale."""
    
    test_data = {
        'layouts': {
            'test_layout_1': {
                'layout_info': {
                    'dimensions': {'width': 10, 'height': 8},
                    'total_cells': 80,
                    'elements': {
                        'tomato_dispensers': 2,
                        'onion_dispensers': 2,
                        'pots': 3,
                        'serving_areas': 2
                    }
                },
                'behavioral_modes': {
                    'coop_mode': {
                        'success_rate': 0.8,
                        'performance_metrics': {
                            'avg_completion_steps': 250,
                            'completion_efficiency': 0.75,
                            'resource_utilization': 0.6,
                            'waste_minimization': 0.8,
                            'overall_efficiency': 0.7
                        },
                        'behavioral_patterns': {
                            'agent_specialization': {
                                'avg_specialization_score': 0.7,
                                'specialization_consistency': 0.8,
                                'agent_0_dominant_roles': {
                                    'ingredient_gatherer': 0.8,
                                    'pot_manager': 0.3
                                },
                                'agent_1_dominant_roles': {
                                    'delivery_specialist': 0.9,
                                    'support_agent': 0.2
                                }
                            },
                            'coordination_events': [
                                'ingredient_exchange', 'spatial_coordination', 
                                'support_action', 'timing_sync', 'role_switch'
                            ]
                        }
                    },
                    'solo_mode': {
                        'success_rate': 0.4,
                        'performance_metrics': {
                            'avg_completion_steps': 450,
                            'completion_efficiency': 0.4,
                            'resource_utilization': 0.3,
                            'waste_minimization': 0.5,
                            'overall_efficiency': 0.4
                        },
                        'behavioral_patterns': {
                            'agent_specialization': {
                                'avg_specialization_score': 0.3,
                                'specialization_consistency': 0.6,
                                'agent_0_dominant_roles': {
                                    'versatile_agent': 0.7,
                                    'ingredient_gatherer': 0.5,
                                    'delivery_specialist': 0.4
                                },
                                'agent_1_dominant_roles': {
                                    'idle_agent': 1.0
                                }
                            },
                            'coordination_events': []
                        }
                    }
                },
                'coordination_analysis': {
                    'coordination_necessity': 'beneficial',
                    'solo_vs_team_effectiveness': {
                        'team_advantage': 0.4,
                        'relative_effectiveness': 2.0
                    }
                }
            },
            
            'test_layout_2': {
                'layout_info': {
                    'dimensions': {'width': 6, 'height': 6},
                    'total_cells': 36,
                    'elements': {
                        'tomato_dispensers': 1,
                        'onion_dispensers': 1,
                        'pots': 1,
                        'serving_areas': 1
                    }
                },
                'behavioral_modes': {
                    'coop_mode': {
                        'success_rate': 0.9,
                        'performance_metrics': {
                            'avg_completion_steps': 180,
                            'completion_efficiency': 0.9,
                            'resource_utilization': 0.8,
                            'waste_minimization': 0.9,
                            'overall_efficiency': 0.85
                        },
                        'behavioral_patterns': {
                            'agent_specialization': {
                                'avg_specialization_score': 0.5,
                                'specialization_consistency': 0.9,
                                'agent_0_dominant_roles': {
                                    'ingredient_gatherer': 0.6,
                                    'pot_manager': 0.7
                                },
                                'agent_1_dominant_roles': {
                                    'pot_manager': 0.6,
                                    'delivery_specialist': 0.8
                                }
                            },
                            'coordination_events': [
                                'timing_sync', 'spatial_coordination'
                            ]
                        }
                    }
                },
                'coordination_analysis': {
                    'coordination_necessity': 'essential',
                    'solo_vs_team_effectiveness': {
                        'team_advantage': 0.6,
                        'relative_effectiveness': 3.0
                    }
                }
            }
        }
    }
    
    return test_data

def test_movement_characterization():
    """Teste la caractérisation des patterns de mouvement."""
    print("🤖 TEST: Caractérisation des patterns de mouvement")
    print("=" * 60)
    
    characterizer = LayoutCharacterizer()
    test_data = create_test_layout_data()
    
    for layout_name, layout_data in test_data['layouts'].items():
        print(f"\n📊 Analyse du layout: {layout_name}")
        
        # Tester la caractérisation comportementale
        behavioral_patterns = characterizer.characterize_behavioral_patterns(layout_name, layout_data)
        
        print(f"   🔍 Patterns de mouvement détectés:")
        for mode_name, mode_patterns in behavioral_patterns['movement_patterns'].items():
            print(f"      Mode {mode_name}:")
            
            # Distance totale
            total_dist = mode_patterns.get('total_distance', {})
            print(f"         Distance totale: Agent0={total_dist.get('agent_0', 0):.1f}, "
                  f"Agent1={total_dist.get('agent_1', 0):.1f}, "
                  f"Balance={total_dist.get('balance', 0):.2f}")
            
            # Efficacité de mouvement
            movement_eff = mode_patterns.get('movement_efficiency', {})
            print(f"         Efficacité mouvement: Agent0={movement_eff.get('agent_0', 0):.2f}, "
                  f"Agent1={movement_eff.get('agent_1', 0):.2f}, "
                  f"Global={movement_eff.get('overall', 0):.2f}")
            
            # Distribution spatiale
            spatial_dist = mode_patterns.get('spatial_distribution', {})
            print(f"         Distribution spatiale: Couverture A0={spatial_dist.get('agent_0_coverage', 0):.2f}, "
                  f"A1={spatial_dist.get('agent_1_coverage', 0):.2f}, "
                  f"Chevauchement={spatial_dist.get('overlap_ratio', 0):.2f}")
            
            # Zones d'activité
            activity_zones = mode_patterns.get('activity_zones', {})
            print(f"         Zones d'activité: {activity_zones.get('hot_zones_count', 0)} zones chaudes, "
                  f"Transitions=[{activity_zones.get('zone_transitions_per_agent', [0,0])[0]}, "
                  f"{activity_zones.get('zone_transitions_per_agent', [0,0])[1]}]")
            
            # Exploration vs Exploitation
            exploration = mode_patterns.get('exploration_analysis', {})
            print(f"         Exploration/Exploitation: Exploration={exploration.get('exploration_score', 0):.2f}, "
                  f"Exploitation={exploration.get('exploitation_score', 0):.2f}, "
                  f"Équilibre={exploration.get('balance_score', 0):.2f}")
            
            # Scores de qualité
            quality = mode_patterns.get('movement_quality_scores', {})
            print(f"         Qualité globale: {quality.get('composite_quality_score', 0):.2f}")

def test_interaction_characterization():
    """Teste la caractérisation des patterns d'interaction."""
    print("\n\n🤝 TEST: Caractérisation des patterns d'interaction")
    print("=" * 60)
    
    characterizer = LayoutCharacterizer()
    test_data = create_test_layout_data()
    
    for layout_name, layout_data in test_data['layouts'].items():
        print(f"\n📊 Analyse du layout: {layout_name}")
        
        # Tester la caractérisation comportementale
        behavioral_patterns = characterizer.characterize_behavioral_patterns(layout_name, layout_data)
        
        print(f"   🔍 Patterns d'interaction détectés:")
        for mode_name, mode_patterns in behavioral_patterns['interaction_patterns'].items():
            print(f"      Mode {mode_name}:")
            
            # Fréquence d'interaction
            freq = mode_patterns.get('interaction_frequency', {})
            print(f"         Fréquence: {freq.get('total_interactions', 0)} interactions, "
                  f"{freq.get('interactions_per_minute', 0):.1f}/min, "
                  f"Densité={freq.get('interaction_density', 0):.3f}")
            
            # Types d'interactions
            types = mode_patterns.get('interaction_types', {})
            print(f"         Types: {types.get('exchange_events', 0)} échanges, "
                  f"{types.get('support_events', 0)} supports, "
                  f"{types.get('conflict_events', 0)} conflits")
            
            # Qualité de coordination
            coord_quality = mode_patterns.get('coordination_quality', {})
            print(f"         Qualité coordination: Sync={coord_quality.get('synchronization_score', 0):.2f}, "
                  f"Complémentarité={coord_quality.get('complementarity_score', 0):.2f}, "
                  f"Efficacité={coord_quality.get('efficiency_score', 0):.2f}")
            
            # Patterns temporels
            temporal = mode_patterns.get('temporal_patterns', {})
            print(f"         Temporel: Rythme={temporal.get('interaction_rhythm', 'unknown')}, "
                  f"Consistance={temporal.get('coordination_consistency', 0):.2f}")
            
            # Communication émergente
            comm = mode_patterns.get('communication_emergence', {})
            print(f"         Communication: Détectée={comm.get('implicit_communication_detected', False)}, "
                  f"Efficacité={comm.get('communication_efficiency', 0):.2f}, "
                  f"Qualité transfert={comm.get('information_transfer_quality', 0):.2f}")
            
            # Scores de qualité
            quality = mode_patterns.get('interaction_quality_scores', {})
            print(f"         Qualité globale: {quality.get('composite_interaction_score', 0):.2f}")

def test_specialization_analysis():
    """Teste l'analyse de spécialisation des agents."""
    print("\n\n⚡ TEST: Analyse de spécialisation des agents")
    print("=" * 60)
    
    characterizer = LayoutCharacterizer()
    test_data = create_test_layout_data()
    
    for layout_name, layout_data in test_data['layouts'].items():
        print(f"\n📊 Analyse du layout: {layout_name}")
        
        # Tester la caractérisation comportementale
        behavioral_patterns = characterizer.characterize_behavioral_patterns(layout_name, layout_data)
        
        print(f"   🔍 Spécialisation détectée:")
        for mode_name, mode_patterns in behavioral_patterns['specialization_analysis'].items():
            print(f"      Mode {mode_name}:")
            
            if mode_patterns.get('specialization_detected', False):
                print(f"         Spécialisation: Score={mode_patterns.get('specialization_score', 0):.2f}, "
                      f"Consistance={mode_patterns.get('consistency_score', 0):.2f}")
                print(f"         Rôles dominants: Agent0={mode_patterns.get('agent_0_dominant_role', 'unknown')}, "
                      f"Agent1={mode_patterns.get('agent_1_dominant_role', 'unknown')}")
                print(f"         Complémentarité: {mode_patterns.get('role_complementarity', 0):.2f}")
            else:
                print("         Aucune spécialisation détectée")

def test_behavioral_comparison():
    """Teste la comparaison comportementale entre modes."""
    print("\n\n🔄 TEST: Comparaison comportementale entre modes")
    print("=" * 60)
    
    characterizer = LayoutCharacterizer()
    test_data = create_test_layout_data()
    
    layout_name = 'test_layout_1'  # Layout avec plusieurs modes
    layout_data = test_data['layouts'][layout_name]
    
    print(f"📊 Comparaison pour: {layout_name}")
    
    # Tester la caractérisation comportementale
    behavioral_patterns = characterizer.characterize_behavioral_patterns(layout_name, layout_data)
    
    # Analyse comparative
    cross_mode = behavioral_patterns.get('cross_mode_analysis', {})
    print(f"   🔍 Analyse comparative:")
    print(f"      Diversité entre modes: {cross_mode.get('mode_diversity', 0):.2f}")
    print(f"      Mode optimal identifié: {cross_mode.get('optimal_mode_identification', 'unknown')}")
    print(f"      Comparaison possible: {cross_mode.get('comparison_possible', False)}")
    
    # Indicateurs d'adaptation
    adaptation = behavioral_patterns.get('adaptation_indicators', {})
    print(f"   🎯 Adaptation comportementale:")
    print(f"      Adaptation détectée: {adaptation.get('adaptation_detected', False)}")
    print(f"      Score de flexibilité: {adaptation.get('flexibility_score', 0):.2f}")
    print(f"      Score de robustesse: {adaptation.get('robustness_score', 0):.2f}")

def main():
    """Fonction principale du test."""
    print("🧪 TESTS DE CARACTÉRISATION COMPORTEMENTALE")
    print("=" * 80)
    print("Validation des nouvelles méthodes d'analyse des patterns de mouvement et d'interaction")
    print("=" * 80)
    
    try:
        # Tests des différents aspects de la caractérisation comportementale
        test_movement_characterization()
        test_interaction_characterization()
        test_specialization_analysis()
        test_behavioral_comparison()
        
        print("\n\n✅ TOUS LES TESTS COMPORTEMENTAUX TERMINÉS AVEC SUCCÈS!")
        print("🎯 Les méthodes de caractérisation comportementale sont opérationnelles")
        
    except Exception as e:
        print(f"\n❌ ERREUR PENDANT LES TESTS: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
