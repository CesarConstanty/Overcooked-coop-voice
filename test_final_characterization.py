#!/usr/bin/env python3
"""
test_final_characterization.py

Test final pour démontrer la caractérisation comportementale complète des layouts Overcooked.
"""

import json
from datetime import datetime
from layout_characterizer import LayoutCharacterizer

def create_complete_test_data():
    """Crée des données de test complètes représentant des évaluations réelles."""
    
    test_data = {
        'layouts': {
            'layout_cesar_analyzed': {
                'layout_info': {
                    'dimensions': {'width': 7, 'height': 7},
                    'total_cells': 49,
                    'elements': {
                        'tomato_dispensers': 2,
                        'onion_dispensers': 2,
                        'pots': 3,
                        'serving_areas': 2
                    }
                },
                'behavioral_modes': {
                    'greedy_coop': {
                        'success_rate': 1.0,
                        'performance_metrics': {
                            'avg_completion_steps': 277,
                            'completion_efficiency': 1.0,
                            'resource_utilization': 0.85,
                            'waste_minimization': 0.9,
                            'overall_efficiency': 2.17
                        },
                        'behavioral_patterns': {
                            'agent_specialization': {
                                'avg_specialization_score': 0.6,
                                'specialization_consistency': 0.8,
                                'agent_0_dominant_roles': {
                                    'ingredient_gatherer': 0.7,
                                    'pot_manager': 0.6
                                },
                                'agent_1_dominant_roles': {
                                    'delivery_specialist': 0.8,
                                    'support_agent': 0.5
                                }
                            },
                            'coordination_events': [
                                'ingredient_exchange', 'delivery_coordination', 
                                'cooking_coordination', 'spatial_coordination'
                            ]
                        }
                    },
                    'greedy_solo': {
                        'success_rate': 0.3,
                        'performance_metrics': {
                            'avg_completion_steps': 450,
                            'completion_efficiency': 0.3,
                            'resource_utilization': 0.4,
                            'waste_minimization': 0.5,
                            'overall_efficiency': 0.67
                        },
                        'behavioral_patterns': {
                            'agent_specialization': {
                                'avg_specialization_score': 0.3,
                                'specialization_consistency': 0.6,
                                'agent_0_dominant_roles': {
                                    'versatile_agent': 0.8,
                                    'solo_operator': 0.9
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
                        'team_advantage': 0.7,
                        'relative_effectiveness': 3.24
                    }
                }
            }
        }
    }
    
    return test_data

def demonstrate_full_characterization():
    """Démontre toutes les capacités de caractérisation comportementale."""
    
    print("🎯 DÉMONSTRATION COMPLÈTE DE CARACTÉRISATION COMPORTEMENTALE")
    print("=" * 80)
    print("Analyse détaillée des patterns comportementaux des GreedyAgent")
    print("=" * 80)
    
    # Initialiser le caractérisateur
    characterizer = LayoutCharacterizer()
    
    # Données de test
    test_data = create_complete_test_data()
    layout_name = 'layout_cesar_analyzed'
    layout_data = test_data['layouts'][layout_name]
    
    print(f"\n📊 ANALYSE DU LAYOUT: {layout_name}")
    print("=" * 60)
    
    # 1. CARACTÉRISATION COMPORTEMENTALE
    print("\n🤖 1. CARACTÉRISATION COMPORTEMENTALE")
    print("-" * 40)
    
    behavioral_patterns = characterizer.characterize_behavioral_patterns(layout_name, layout_data)
    
    # Patterns de mouvement
    print("   📍 PATTERNS DE MOUVEMENT:")
    for mode_name, mode_patterns in behavioral_patterns['movement_patterns'].items():
        print(f"      Mode {mode_name}:")
        
        # Distances et efficacité
        total_dist = mode_patterns.get('total_distance', {})
        movement_eff = mode_patterns.get('movement_efficiency', {})
        print(f"         🚶 Distance: A0={total_dist.get('agent_0', 0):.1f}, A1={total_dist.get('agent_1', 0):.1f}")
        print(f"         ⚡ Efficacité: A0={movement_eff.get('agent_0', 0):.2f}, A1={movement_eff.get('agent_1', 0):.2f}")
        
        # Zones d'activité
        activity_zones = mode_patterns.get('activity_zones', {})
        print(f"         🏢 Zones chaudes: {activity_zones.get('hot_zones_count', 0)}")
        print(f"         🔄 Transitions: {activity_zones.get('zone_transitions_per_agent', [0,0])}")
        
        # Qualité globale
        quality = mode_patterns.get('movement_quality_scores', {})
        print(f"         🎯 Qualité: {quality.get('composite_quality_score', 0):.2f}")
    
    # Patterns d'interaction
    print("\n   🤝 PATTERNS D'INTERACTION:")
    for mode_name, mode_patterns in behavioral_patterns['interaction_patterns'].items():
        print(f"      Mode {mode_name}:")
        
        # Fréquence et types
        freq = mode_patterns.get('interaction_frequency', {})
        types = mode_patterns.get('interaction_types', {})
        print(f"         📊 Interactions: {freq.get('total_interactions', 0)} total, {freq.get('interactions_per_minute', 0):.1f}/min")
        print(f"         🔄 Types: {types.get('exchange_events', 0)} échanges, {types.get('support_events', 0)} supports")
        
        # Qualité de coordination
        coord_quality = mode_patterns.get('coordination_quality', {})
        print(f"         🎯 Coordination: Sync={coord_quality.get('synchronization_score', 0):.2f}, Eff={coord_quality.get('efficiency_score', 0):.2f}")
        
        # Communication émergente
        comm = mode_patterns.get('communication_emergence', {})
        print(f"         💬 Communication: Détectée={comm.get('implicit_communication_detected', False)}")
    
    # Spécialisation des agents
    print("\n   ⚡ SPÉCIALISATION DES AGENTS:")
    for mode_name, mode_patterns in behavioral_patterns['specialization_analysis'].items():
        print(f"      Mode {mode_name}:")
        if mode_patterns.get('specialization_detected', False):
            print(f"         📈 Score: {mode_patterns.get('specialization_score', 0):.2f}")
            print(f"         🎭 Rôles: A0={mode_patterns.get('agent_0_dominant_role', 'unknown')}")
            print(f"                   A1={mode_patterns.get('agent_1_dominant_role', 'unknown')}")
            print(f"         🤝 Complémentarité: {mode_patterns.get('role_complementarity', 0):.2f}")
        else:
            print("         ❌ Aucune spécialisation détectée")
    
    # 2. CARACTÉRISATION PERFORMANCE
    print("\n📈 2. CARACTÉRISATION PERFORMANCE")
    print("-" * 40)
    
    performance_profile = characterizer.characterize_performance_profile(layout_name, layout_data)
    
    print("   🎯 MÉTRIQUES DE SUCCÈS:")
    success_metrics = performance_profile.get('success_metrics', {})
    print(f"      Taux de succès global: {success_metrics.get('overall_success_rate', 0):.1%}")
    print(f"      Meilleur taux: {success_metrics.get('best_success_rate', 0):.1%}")
    print(f"      Consistance: {success_metrics.get('success_consistency', 0):.2f}")
    
    print("   ⏱️ MÉTRIQUES TEMPORELLES:")
    timing_metrics = performance_profile.get('timing_metrics', {})
    print(f"      Temps moyen: {timing_metrics.get('avg_completion_time', 0):.0f} steps")
    print(f"      Plus rapide: {timing_metrics.get('fastest_completion', 0):.0f} steps")
    print(f"      Prédictibilité: {timing_metrics.get('timing_predictability', 0):.2f}")
    
    print("   ⚡ MÉTRIQUES D'EFFICACITÉ:")
    efficiency_metrics = performance_profile.get('efficiency_metrics', {})
    print(f"      Efficacité moyenne: {efficiency_metrics.get('avg_efficiency', 0):.2f}")
    print(f"      Efficacité maximale: {efficiency_metrics.get('peak_efficiency', 0):.2f}")
    print(f"      Potentiel d'amélioration: {efficiency_metrics.get('efficiency_improvement_potential', 0):.2f}")
    
    # 3. CARACTÉRISATION COORDINATION
    print("\n🤝 3. CARACTÉRISATION COORDINATION")
    print("-" * 40)
    
    coordination_req = characterizer.characterize_coordination_requirements(layout_name, layout_data)
    
    print(f"   🎯 Nécessité de coordination: {coordination_req.get('coordination_necessity', 'unknown')}")
    print(f"   📊 Complexité coordination: {coordination_req.get('coordination_complexity', 'unknown')}")
    
    role_dynamics = coordination_req.get('role_dynamics', {})
    print(f"   🎭 Dynamiques de rôles:")
    print(f"      Flexibilité: {role_dynamics.get('role_flexibility', 0):.2f}")
    print(f"      Spécialisation optimale: {role_dynamics.get('optimal_specialization', 0):.2f}")
    
    # 4. CARACTÉRISATION STRATÉGIQUE
    print("\n🧠 4. CARACTÉRISATION STRATÉGIQUE")
    print("-" * 40)
    
    strategic_elements = characterizer.characterize_strategic_elements(layout_name, layout_data)
    
    emergence = strategic_elements.get('emergent_strategies', {})
    print(f"   🌟 Stratégies émergentes:")
    print(f"      Émergence détectée: {emergence.get('emergence_detected', False)}")
    print(f"      Complexité stratégique: {emergence.get('strategy_complexity_score', 0):.2f}")
    
    adaptation = strategic_elements.get('adaptation_mechanisms', {})
    print(f"   🔄 Mécanismes d'adaptation:")
    print(f"      Adaptabilité: {adaptation.get('adaptability_score', 0):.2f}")
    print(f"      Flexibilité: {adaptation.get('behavioral_flexibility', 0):.2f}")
    
    # 5. ANALYSE COMPARATIVE ENTRE MODES
    print("\n🔄 5. ANALYSE COMPARATIVE ENTRE MODES")
    print("-" * 40)
    
    cross_mode = behavioral_patterns.get('cross_mode_analysis', {})
    print(f"   📊 Diversité entre modes: {cross_mode.get('mode_diversity', 0):.2f}")
    print(f"   🎯 Mode optimal: {cross_mode.get('optimal_mode_identification', 'unknown')}")
    
    adaptation_indicators = behavioral_patterns.get('adaptation_indicators', {})
    print(f"   🧬 Adaptation comportementale:")
    print(f"      Adaptation détectée: {adaptation_indicators.get('adaptation_detected', False)}")
    print(f"      Score de flexibilité: {adaptation_indicators.get('flexibility_score', 0):.2f}")
    print(f"      Score de robustesse: {adaptation_indicators.get('robustness_score', 0):.2f}")
    
    # 6. GÉNÉRATION DU RAPPORT FINAL
    print("\n📄 6. GÉNÉRATION DU RAPPORT FINAL")
    print("-" * 40)
    
    final_report = {
        'layout_name': layout_name,
        'analysis_timestamp': datetime.now().isoformat(),
        'characterization_results': {
            'behavioral_patterns': behavioral_patterns,
            'performance_profile': performance_profile,
            'coordination_requirements': coordination_req,
            'strategic_elements': strategic_elements
        },
        'summary': {
            'layout_type': 'cooperative_beneficial',
            'optimal_mode': cross_mode.get('optimal_mode_identification', 'greedy_coop'),
            'coordination_level': coordination_req.get('coordination_necessity', 'beneficial'),
            'success_rate': success_metrics.get('overall_success_rate', 0),
            'behavioral_diversity': cross_mode.get('mode_diversity', 0),
            'key_insights': [
                f"Layout favorise la coopération (succès: {success_metrics.get('overall_success_rate', 0):.1%})",
                f"Spécialisation des agents observée (score: {behavioral_patterns['specialization_analysis'].get('greedy_coop', {}).get('specialization_score', 0):.2f})",
                f"Coordination bénéfique (amélioration: {layout_data['coordination_analysis']['solo_vs_team_effectiveness']['team_advantage']:.1%})",
                f"Efficacité élevée en mode coopératif ({layout_data['behavioral_modes']['greedy_coop']['performance_metrics']['overall_efficiency']:.2f})"
            ]
        }
    }
    
    # Sauvegarder le rapport
    import os
    os.makedirs('./reports/', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"./reports/final_characterization_demo_{timestamp}.json"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Rapport sauvegardé: {report_path}")
    
    # Afficher le résumé
    print("\n🎯 RÉSUMÉ EXÉCUTIF:")
    print("=" * 60)
    for i, insight in enumerate(final_report['summary']['key_insights'], 1):
        print(f"   {i}. {insight}")
    
    print(f"\n✅ CARACTÉRISATION COMPORTEMENTALE COMPLÈTE TERMINÉE!")
    print(f"📊 Layout analysé: {layout_name}")
    print(f"🎯 Mode optimal identifié: {final_report['summary']['optimal_mode']}")
    print(f"🤝 Niveau de coordination: {final_report['summary']['coordination_level']}")
    print(f"📈 Taux de succès: {final_report['summary']['success_rate']:.1%}")
    print(f"🔄 Diversité comportementale: {final_report['summary']['behavioral_diversity']:.2f}")

def main():
    """Fonction principale de démonstration."""
    try:
        demonstrate_full_characterization()
        return 0
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
