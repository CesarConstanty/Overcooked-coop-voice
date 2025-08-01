#!/usr/bin/env python3
"""
Test avec des paramètres optimisés pour améliorer le taux de complétion
"""

import sys
import os

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, '/home/cesar/python-projects/Overcooked-coop-voice')

from layout_evaluator import LayoutEvaluator

def test_with_longer_horizon():
    """Test avec un horizon plus long pour voir si c'est un problème de temps."""
    print("=== TEST AVEC HORIZON ÉTENDU ===")
    
    evaluator = LayoutEvaluator(
        layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/demo",
        horizon=1200,  # Double de l'original
        num_games_per_layout=3,
        verbose=True
    )
    
    # Test un seul layout
    layout_name = "V1_layout_combination_01"
    print(f"🧪 Test {layout_name} avec horizon 1200 steps...")
    
    result = evaluator.evaluate_single_layout(layout_name)
    
    print(f"\n📊 Résultats avec horizon étendu:")
    print(f"  - Viable: {result.get('viable', 'N/A')}")
    print(f"  - Parties jouées: {result.get('games_played', 'N/A')}")
    print(f"  - Taux complétion: {result.get('completion_rate', 'N/A')}")
    print(f"  - Parties complétées: {result.get('games_completed', 'N/A')}")
    
    if result.get('completion_rate', 0) > 0:
        print(f"✅ Amélioration avec horizon étendu!")
        if 'completion_metrics' in result:
            cm = result['completion_metrics']
            print(f"  - Steps moyen pour complétion: {cm.get('average_completion_steps', 'N/A')}")
            print(f"  - Plus rapide: {cm.get('fastest_completion_steps', 'N/A')} steps")
    else:
        print(f"❌ Toujours aucune complétion même avec horizon étendu")

def test_single_agent_mode():
    """Test en mode agent unique pour voir si c'est plus simple."""
    print("\n=== TEST MODE AGENT UNIQUE ===")
    
    evaluator = LayoutEvaluator(
        layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/demo",
        horizon=800,
        num_games_per_layout=2,
        single_agent=True,  # Mode solo
        verbose=True
    )
    
    layout_name = "V1_layout_combination_01"
    print(f"🧪 Test {layout_name} en mode solo...")
    
    result = evaluator.evaluate_single_layout(layout_name)
    
    print(f"\n📊 Résultats en mode solo:")
    print(f"  - Viable: {result.get('viable', 'N/A')}")
    print(f"  - Taux complétion: {result.get('completion_rate', 'N/A')}")
    
    if result.get('completion_rate', 0) > 0:
        print(f"✅ Mode solo fonctionne mieux!")
    else:
        print(f"❌ Mode solo ne résout pas le problème")

def analyze_layout_structure():
    """Analyse la structure du layout pour comprendre la difficulté."""
    print("\n=== ANALYSE STRUCTURE LAYOUT ===")
    
    from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
    
    layout_name = "generation_cesar/demo/V1_layout_combination_01"
    mdp = OvercookedGridworld.from_layout_name(layout_name)
    
    print(f"📋 Analyse de {layout_name}:")
    print(f"  - Dimensions: {mdp.width}x{mdp.height}")
    print(f"  - Positions joueurs: {mdp.start_player_positions}")
    print(f"  - Nombre de commandes: {len(mdp.start_all_orders)}")
    print(f"  - Commandes: {[order['ingredients'] for order in mdp.start_all_orders]}")
    
    # Analyser la grille
    terrain_counts = {}
    for row in mdp.terrain_mtx:
        for cell in row:
            terrain_counts[cell] = terrain_counts.get(cell, 0) + 1
    
    print(f"  - Éléments du terrain:")
    for element, count in sorted(terrain_counts.items()):
        element_names = {
            'T': 'Distributeurs de tomates',
            'O': 'Distributeurs d\'oignons', 
            'D': 'Distributeurs d\'assiettes',
            'P': 'Casseroles',
            'S': 'Zones de service',
            'X': 'Murs/Comptoirs',
            ' ': 'Espaces libres',
            '1': 'Position joueur 1',
            '2': 'Position joueur 2'
        }
        name = element_names.get(element, f'Élément {element}')
        print(f"    - {name}: {count}")
    
    # Afficher la grille
    print(f"\n🗺️ Grille du layout:")
    for i, row in enumerate(mdp.terrain_mtx):
        print(f"    {i:2d}: {''.join(row)}")

if __name__ == "__main__":
    print("🔧 TEST D'OPTIMISATION LAYOUT_EVALUATOR")
    print("=" * 55)
    
    # Analyser d'abord la structure
    analyze_layout_structure()
    
    # Test avec horizon étendu
    test_with_longer_horizon()
    
    # Test en mode solo
    test_single_agent_mode()
    
    print(f"\n🎯 Recommandations:")
    print(f"  1. Si horizon étendu améliore: augmenter la valeur par défaut")
    print(f"  2. Si mode solo fonctionne: problème de coordination entre agents")
    print(f"  3. Si aucun n'améliore: layouts potentiellement impossibles à résoudre")
