#!/usr/bin/env python3
"""
Script de diagnostic pour identifier les problèmes dans le système d'évaluation
"""

import sys
import json
import gzip
from pathlib import Path
import base64

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

# Import du décompresseur depuis le répertoire parent
sys.path.append(str(Path(__file__).parent.parent))
from layout_compression import LayoutDecompressor

def test_layout_format_compatibility():
    """Test 1: Vérifier la compatibilité des formats de layout"""
    print("=== TEST 1: Compatibilité format layout ===")
    
    # Charger un layout généré
    layouts_dir = Path("outputs/layouts_generes")
    batch_file = layouts_dir / "layout_batch_1.jsonl.gz"
    
    if not batch_file.exists():
        print("❌ Fichier de layouts non trouvé")
        return False
    
    try:
        with gzip.open(batch_file, 'rt') as f:
            first_line = f.readline()
            layout_data = json.loads(first_line)
        
        print(f"✅ Layout chargé avec clés: {list(layout_data.keys())}")
        print(f"   Format grid: {'g' in layout_data}")
        print(f"   Object positions: {'op' in layout_data}")
        print(f"   Hash: {'h' in layout_data}")
        
        # Test décompression
        decompressor = LayoutDecompressor()
        decompressed = decompressor.decompress_layout(layout_data)
        
        print(f"✅ Décompression réussie")
        print(f"   Grid size: {len(decompressed['grid'])}x{len(decompressed['grid'][0])}")
        print(f"   Object positions: {decompressed.get('object_positions', {})}")
        
        # Afficher la grille
        print("   Grille:")
        for row in decompressed['grid']:
            print(f"   {''.join(row)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_exchange_detection():
    """Test 2: Vérifier la détection des positions d'échange potentielles"""
    print("\n=== TEST 2: Détection échanges potentiels ===")
    
    # Créer un layout de test simple
    test_layout = {
        "grid": [
            ['X', 'X', 'X', 'X', 'X', 'X', 'X', 'X'],
            ['X', ' ', ' ', 'X', ' ', ' ', ' ', 'X'],
            ['X', ' ', 'O', 'X', 'T', ' ', ' ', 'X'],
            ['X', 'S', 'X', 'X', 'X', 'P', ' ', 'X'],
            ['X', ' ', ' ', 'X', ' ', ' ', 'D', 'X'],
            ['X', ' ', ' ', 'X', ' ', ' ', ' ', 'X'],
            ['X', ' ', ' ', ' ', ' ', ' ', ' ', 'X'],
            ['X', 'X', 'X', 'X', 'X', 'X', 'X', 'X']
        ],
        "object_positions": {
            "1": [[1, 1]],
            "2": [[6, 6]]
        }
    }
    
    try:
        # Import dynamique pour éviter problème nom fichier avec chiffres  
        import importlib.util
        evaluator_path = Path(__file__).parent / "scripts" / "2_layout_evaluator.py"
        spec = importlib.util.spec_from_file_location("layout_evaluator", evaluator_path)
        evaluator_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator_module)
        
        OptimizedGameState = evaluator_module.OptimizedGameState
        ExchangeTracker = evaluator_module.ExchangeTracker
        
        # Créer l'état de jeu
        state = OptimizedGameState(test_layout, [])
        print(f"✅ État de jeu créé")
        print(f"   Positions joueurs: {state.player_positions}")
        
        # Créer le tracker d'échanges
        tracker = ExchangeTracker(state)
        print(f"✅ Tracker d'échanges créé")
        print(f"   Échanges potentiels: {len(tracker.potential_exchanges)}")
        
        for pos in tracker.potential_exchanges:
            print(f"   Position X candidate: {pos}")
        
        # Simuler quelques échanges
        if tracker.potential_exchanges:
            test_pos = tracker.potential_exchanges[0]
            tracker.record_exchange(test_pos)
            tracker.record_exchange(test_pos)
            print(f"✅ Enregistré 2 échanges à {test_pos}")
            
            # Sélectionner les positions Y
            y_positions = tracker.select_optimal_y_positions()
            print(f"✅ Positions Y sélectionnées: {y_positions}")
            
            return len(y_positions) > 0
        else:
            print("❌ Aucune position d'échange potentielle détectée")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_recipe_loading():
    """Test 3: Vérifier le chargement des recettes"""
    print("\n=== TEST 3: Chargement recettes ===")
    
    recipes_file = Path("outputs/recipes.json")
    
    if not recipes_file.exists():
        print("❌ Fichier de recettes non trouvé")
        return False
    
    try:
        with open(recipes_file, 'r') as f:
            data = json.load(f)
        
        recipe_groups = data.get("recipe_groups", [])
        print(f"✅ {len(recipe_groups)} groupes de recettes chargés")
        
        # Vérifier quelques groupes
        total_recipes = 0
        for i, group in enumerate(recipe_groups[:3]):
            recipes_in_group = len(group.get("recipes", []))
            total_recipes += recipes_in_group
            print(f"   Groupe {i+1}: {recipes_in_group} recettes")
            if recipes_in_group > 0:
                example = group["recipes"][0]
                print(f"     Exemple: {example}")
        
        print(f"✅ Total échantillon: {total_recipes} recettes")
        return len(recipe_groups) == 84
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_pathfinding():
    """Test 4: Vérifier le pathfinding A*"""
    print("\n=== TEST 4: Pathfinding A* ===")
    
    # Layout de test simple
    test_layout = {
        "grid": [
            ['X', 'X', 'X', 'X', 'X'],
            ['X', ' ', ' ', ' ', 'X'],
            ['X', ' ', 'X', ' ', 'X'],
            ['X', ' ', ' ', ' ', 'X'],
            ['X', 'X', 'X', 'X', 'X']
        ],
        "object_positions": {
            "1": [[1, 1]],
            "2": [[3, 3]]
        }
    }
    
    try:
        # Import dynamique pour éviter problème nom fichier avec chiffres  
        import importlib.util
        evaluator_path = Path(__file__).parent / "scripts" / "2_layout_evaluator.py"
        spec = importlib.util.spec_from_file_location("layout_evaluator", evaluator_path)
        evaluator_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator_module)
        
        OptimizedGameState = evaluator_module.OptimizedGameState
        OptimalPathfinder = evaluator_module.OptimalPathfinder
        
        state = OptimizedGameState(test_layout, [])
        pathfinder = OptimalPathfinder(state)
        
        # Test chemin simple
        start = (1, 1)
        goal = (3, 3)
        path = pathfinder.get_optimal_path(start, goal, 1)
        
        print(f"✅ Chemin calculé de {start} à {goal}")
        print(f"   Longueur: {len(path) - 1} étapes")
        print(f"   Chemin: {path}")
        
        # Test bénéfice d'échange
        if len(path) > 2:
            exchange_pos = (2, 2)
            benefit = pathfinder.calculate_exchange_benefit(
                start, goal, (1, 3), (3, 1), exchange_pos
            )
            print(f"✅ Bénéfice échange à {exchange_pos}: {benefit}")
        
        return len(path) > 0
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Exécute tous les tests de diagnostic"""
    print("🔍 DIAGNOSTIC DU SYSTÈME D'ÉVALUATION")
    print("=" * 50)
    
    tests = [
        test_layout_format_compatibility,
        test_exchange_detection, 
        test_recipe_loading,
        test_pathfinding
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Erreur critique dans {test.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DES TESTS")
    print(f"Tests réussis: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✅ Tous les tests sont passés!")
    else:
        print("❌ Certains tests ont échoué - investigation nécessaire")
    
    return all(results)

if __name__ == "__main__":
    main()
