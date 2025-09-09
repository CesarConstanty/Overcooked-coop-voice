#!/usr/bin/env python3
"""Test d'évaluation réelle avec détection d'échanges"""

import sys
import json
import gzip
import importlib.util
from pathlib import Path

def main():
    print("🎯 TEST ÉVALUATION RÉELLE AVEC DÉTECTION ÉCHANGES")
    print("=" * 60)
    
    # Import dynamique de l'évaluateur
    evaluator_path = Path(__file__).parent / "scripts" / "2_layout_evaluator.py"
    spec = importlib.util.spec_from_file_location("layout_evaluator", evaluator_path)
    evaluator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator_module)
    
    OptimizedGameState = evaluator_module.OptimizedGameState
    ExchangeTracker = evaluator_module.ExchangeTracker
    OptimalPathfinder = evaluator_module.OptimalPathfinder
    
    # Charger un layout réel
    with gzip.open('outputs/layouts_generes/layout_batch_1.jsonl.gz', 'rt') as f:
        layout_data = json.loads(f.readline())
    
    print(f"📁 Layout chargé:")
    print(f"   Hash: {layout_data['h']}")
    print(f"   Object positions: {layout_data['op']}")
    
    # Charger quelques recettes
    with open('outputs/recipes.json', 'r') as f:
        recipes_data = json.load(f)
    
    # Prendre les premières recettes du premier groupe
    first_group = recipes_data["recipe_groups"][0]
    test_recipes = first_group["recipes"][:3]  # 3 premières recettes
    
    print(f"🍳 Recettes de test: {len(test_recipes)}")
    for i, recipe in enumerate(test_recipes):
        print(f"   {i+1}: {recipe['ingredients']}")
    
    # Créer l'état de jeu
    try:
        state = OptimizedGameState(layout_data, test_recipes)
        print(f"✅ État de jeu créé")
        print(f"   Player positions: {state.player_positions}")
        print(f"   Pot: {state.pot_position}")
        print(f"   Service: {state.service_position}")
        print(f"   Onion: {state.onion_dispenser}")
        print(f"   Tomato: {state.tomato_dispenser}")
        print(f"   Dish: {state.dish_dispenser}")
        
        # Afficher la grille
        print(f"\n🗺️  Grille:")
        for i, row in enumerate(state.layout):
            print(f"   {i}: {''.join(row)}")
        
        # Test du tracker d'échanges
        tracker = ExchangeTracker(state)
        print(f"\n📍 Exchange Tracker:")
        print(f"   Positions d'échange potentielles: {len(tracker.potential_exchanges)}")
        for pos in tracker.potential_exchanges:
            print(f"   - {pos}")
        
        # Test pathfinding
        pathfinder = OptimalPathfinder(state)
        print(f"\n🛤️  Test Pathfinding:")
        
        if state.player_positions[1] and state.onion_dispenser:
            p1_pos = state.player_positions[1]
            onion_pos = state.onion_dispenser
            path = pathfinder.get_optimal_path(p1_pos, onion_pos, 1)
            print(f"   Joueur 1 {p1_pos} → Oignon {onion_pos}: {len(path)-1} étapes")
            print(f"   Chemin: {path}")
            
            # Test bénéfice d'échange
            if state.player_positions[2] and tracker.potential_exchanges:
                p2_pos = state.player_positions[2]
                exchange_pos = tracker.potential_exchanges[0]
                
                benefit = pathfinder.calculate_exchange_benefit(
                    p1_pos, onion_pos, p2_pos, state.pot_position, exchange_pos
                )
                print(f"   Bénéfice échange à {exchange_pos}: {benefit} étapes")
                
                if benefit > 0:
                    tracker.record_exchange(exchange_pos)
                    print(f"   ✅ Échange enregistré!")
        
        # Test sélection des Y
        selected_y = tracker.select_optimal_y_positions()
        print(f"\n🎯 Positions Y sélectionnées: {selected_y}")
        
        # Appliquer les Y
        if selected_y:
            tracker.apply_y_positions()
            print(f"   ✅ Positions Y appliquées au layout")
            
            print(f"\n🗺️  Grille avec Y:")
            for i, row in enumerate(state.layout):
                print(f"   {i}: {''.join(row)}")
        
        print(f"\n✅ Test évaluation réelle réussi!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
