#!/usr/bin/env python3
"""
Test rapide du mode coopératif avec 2 GreedyAgents.
"""

import sys
import os
sys.path.append('.')

from layout_evaluator_final import LayoutEvaluator

def test_coop_mode():
    """Test rapide du mode coopératif (2 GreedyAgents)."""
    print("🎮 TEST RAPIDE - MODE COOPÉRATIF (2x GreedyAgent)")
    print("=" * 60)
    
    # Configuration pour test rapide
    evaluator = LayoutEvaluator(
        layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/",
        horizon=200,  # Horizon plus court pour test rapide
        num_games_per_layout=2,  # Moins de parties
        target_fps=20.0,  # FPS plus rapide
        max_stuck_frames=30,
        single_agent=False,  # Mode coopératif
        greedy_with_stay=False
    )
    
    # Évaluer un seul layout
    layout_names = evaluator.discover_layouts()
    if layout_names:
        test_layout = layout_names[0]
        print(f"\n🧪 Test du layout: {test_layout}")
        
        result = evaluator.evaluate_single_layout(test_layout)
        
        print(f"\n📊 RÉSULTATS DU TEST:")
        print(f"   Layout: {result['layout_name']}")
        print(f"   Viable: {result['viable']}")
        print(f"   Parties jouées: {result.get('games_played', 0)}")
        print(f"   Taux de complétion: {result.get('completion_rate', 0):.1%}")
        
        # Vérifier les métriques comportementales
        if 'behavioral_analysis' in result:
            ba = result['behavioral_analysis']
            print(f"   Soupes livrées (total): {sum(ba['aggregated_events'].get('soup_delivery', [0, 0]))}")
            print(f"   Collaborations: {ba.get('total_collaboration_events', 0)}")
            
            if 'efficiency_analysis' in ba:
                eff = ba['efficiency_analysis']
                print(f"   Efficacité pickup A0: {eff['agent_0']['pickup_efficiency']:.1%}")
                print(f"   Efficacité pickup A1: {eff['agent_1']['pickup_efficiency']:.1%}")
        
        # Sauvegarder le résultat de test
        evaluator.results[test_layout] = result
        evaluator.save_results("test_coop_quick.json", include_individual_games=False)
        
        print(f"\n✅ Test terminé avec succès!")
        return True
    else:
        print("❌ Aucun layout trouvé pour le test")
        return False

if __name__ == "__main__":
    test_coop_mode()
