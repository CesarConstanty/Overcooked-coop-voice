#!/usr/bin/env python3
"""
Test rapide du mode solo pour vérifier la correction des pickups de tomates.
"""

import sys
import os
sys.path.append('.')

from layout_evaluator_final import LayoutEvaluator

def test_solo_tomato_fix():
    """Test rapide du mode solo pour vérifier les pickups de tomates."""
    print("🎮 TEST CORRECTION - MODE SOLO (tomato pickup)")
    print("=" * 60)
    
    # Configuration pour test rapide
    evaluator = LayoutEvaluator(
        layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/",
        horizon=300,  # Horizon plus court pour test rapide
        num_games_per_layout=2,  # Moins de parties
        target_fps=20.0,  # FPS plus rapide
        max_stuck_frames=30,
        single_agent=True,  # Mode solo
        greedy_with_stay=False
    )
    
    # Évaluer un seul layout
    layout_names = evaluator.discover_layouts()
    if layout_names:
        test_layout = layout_names[0]
        print(f"\n🧪 Test du layout: {test_layout}")
        
        result = evaluator.evaluate_single_layout(test_layout)
        
        print(f"\n📊 VÉRIFICATION DU BUG TOMATO PICKUP:")
        print(f"   Layout: {result['layout_name']}")
        print(f"   Parties jouées: {result.get('games_played', 0)}")
        print(f"   Taux de complétion: {result.get('completion_rate', 0):.1%}")
        
        # Vérifier les métriques comportementales spécifiquement pour les tomates
        if 'behavioral_analysis' in result:
            ba = result['behavioral_analysis']
            events = ba['aggregated_events']
            
            tomato_pickup = events.get('tomato_pickup', [0, 0])
            potting_tomato = events.get('potting_tomato', [0, 0])
            soup_delivery = events.get('soup_delivery', [0, 0])
            
            print(f"\n🔍 ANALYSE DES ÉVÉNEMENTS TOMATES:")
            print(f"   tomato_pickup: Agent0={tomato_pickup[0]}, Agent1={tomato_pickup[1]}")
            print(f"   potting_tomato: Agent0={potting_tomato[0]}, Agent1={potting_tomato[1]}")
            print(f"   soup_delivery: Agent0={soup_delivery[0]}, Agent1={soup_delivery[1]}")
            
            # Vérification de cohérence
            total_tomato_pickups = sum(tomato_pickup)
            total_tomato_pottings = sum(potting_tomato)
            total_soup_deliveries = sum(soup_delivery)
            
            print(f"\n✅ VÉRIFICATION DE COHÉRENCE:")
            print(f"   Total tomato pickups: {total_tomato_pickups}")
            print(f"   Total tomato pottings: {total_tomato_pottings}")
            print(f"   Total soup deliveries: {total_soup_deliveries}")
            
            # En mode solo, l'agent 1 devrait avoir 0 pour tous les événements
            agent_1_total_events = sum([
                tomato_pickup[1], potting_tomato[1], soup_delivery[1],
                events.get('onion_pickup', [0, 0])[1],
                events.get('dish_pickup', [0, 0])[1]
            ])
            
            if agent_1_total_events == 0:
                print(f"   ✅ Agent 1 correctement inactif (0 événements)")
            else:
                print(f"   ❌ ERREUR: Agent 1 a {agent_1_total_events} événements alors qu'il devrait être inactif")
            
            # Vérification logique: on ne peut pas potter plus de tomates qu'on en a ramassé
            if total_tomato_pickups >= total_tomato_pottings or total_tomato_pottings == 0:
                print(f"   ✅ Cohérence logique: pickup >= potting")
            else:
                print(f"   ❌ INCOHÉRENCE: Plus de potting ({total_tomato_pottings}) que de pickup ({total_tomato_pickups})")
        
        # Sauvegarder le résultat de test
        evaluator.results[test_layout] = result
        evaluator.save_results("test_solo_tomato_fix.json", include_individual_games=False)
        
        print(f"\n✅ Test terminé - Résultats dans test_solo_tomato_fix.json")
        return True
    else:
        print("❌ Aucun layout trouvé pour le test")
        return False

if __name__ == "__main__":
    test_solo_tomato_fix()
