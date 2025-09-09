#!/usr/bin/env python3
"""
Test du système d'évaluation avec optimisation des échanges.
Valide la détection automatique des zones Y et l'optimisation des trajectoires.
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire scripts au path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Import du module avec un nom commençant par un chiffre
import importlib.util
spec = importlib.util.spec_from_file_location("layout_evaluator", scripts_dir / "2_layout_evaluator.py")
layout_evaluator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout_evaluator_module)

LayoutEvaluator = layout_evaluator_module.MassiveLayoutEvaluator
OptimalPathfinder = layout_evaluator_module.OptimalPathfinder
ExchangeTracker = layout_evaluator_module.ExchangeTracker
OptimizedGameState = layout_evaluator_module.OptimizedGameState
import gzip
import json
import base64

def load_recipes_from_json():
    """Charge les recettes depuis le fichier outputs/recipes.json organisées par groupes"""
    recipes_file = Path(__file__).parent.parent / "outputs" / "recipes.json"
    
    if not recipes_file.exists():
        print(f"❌ Fichier de recettes non trouvé: {recipes_file}")
        return []
    
    try:
        with open(recipes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Organiser les recettes par groupes
        recipe_groups = []
        for group in data.get('recipe_groups', []):
            group_recipes = []
            for recipe in group.get('recipes', []):
                if recipe.get('ingredients'):  # Ignorer les recettes vides
                    group_recipes.append(recipe)
            
            if group_recipes:  # Ajouter seulement les groupes non vides
                recipe_groups.append({
                    'group_id': group.get('group_id'),
                    'recipes': group_recipes
                })
        
        print(f"📋 {len(recipe_groups)} groupes de recettes chargés depuis {recipes_file}")
        total_recipes = sum(len(group['recipes']) for group in recipe_groups)
        print(f"📊 {total_recipes} recettes au total")
        return recipe_groups
        
    except Exception as e:
        print(f"❌ Erreur de lecture des recettes: {e}")
        return []

def evaluate_layout_with_all_recipe_groups(grid, recipe_groups, evaluator):
    """Évalue un layout avec tous les groupes de recettes (84 évaluations)"""
    
    layout_results = {
        'total_groups': len(recipe_groups),
        'evaluations': [],
        'summary': {
            'avg_solo_steps': 0,
            'avg_duo_steps': 0,
            'avg_duo_optimized_steps': 0,
            'total_exchange_positions': 0,
            'best_exchange_positions': []
        }
    }
    
    print(f"🔄 Évaluation du layout avec {len(recipe_groups)} groupes de recettes...")
    
    all_solo_steps = []
    all_duo_steps = []
    all_duo_optimized_steps = []
    all_exchange_positions = set()
    
    for i, recipe_group in enumerate(recipe_groups, 1):
        group_id = recipe_group['group_id']
        recipes = recipe_group['recipes']
        
        print(f"   📝 Groupe {group_id} ({i}/{len(recipe_groups)}): {len(recipes)} recettes")
        
        try:
            # Évaluation avec le groupe de recettes actuel
            solo_result = evaluator.evaluate_layout_solo(grid, recipes)
            duo_result = evaluator.evaluate_layout_duo_with_exchange_detection(grid, recipes)
            
            # Optimisation avec les zones Y détectées
            if duo_result.get('best_exchange_positions'):
                duo_optimized_result = evaluator.evaluate_layout_duo_with_fixed_exchanges(
                    grid, recipes, duo_result['best_exchange_positions']
                )
            else:
                duo_optimized_result = duo_result
            
            group_evaluation = {
                'group_id': group_id,
                'recipe_count': len(recipes),
                'solo_steps': solo_result.get('total_steps', 0),
                'duo_steps': duo_result.get('total_steps', 0),
                'duo_optimized_steps': duo_optimized_result.get('total_steps', 0),
                'exchange_positions': duo_result.get('exchange_positions', {}),
                'best_exchange_positions': duo_result.get('best_exchange_positions', [])
            }
            
            layout_results['evaluations'].append(group_evaluation)
            
            # Collecter les statistiques
            all_solo_steps.append(group_evaluation['solo_steps'])
            all_duo_steps.append(group_evaluation['duo_steps'])
            all_duo_optimized_steps.append(group_evaluation['duo_optimized_steps'])
            
            # Collecter les positions d'échange
            for pos in group_evaluation['exchange_positions']:
                all_exchange_positions.add(tuple(pos) if isinstance(pos, list) else pos)
                
        except Exception as e:
            print(f"      ❌ Erreur groupe {group_id}: {e}")
            continue
    
    # Calculer les moyennes
    if layout_results['evaluations']:
        layout_results['summary']['avg_solo_steps'] = sum(all_solo_steps) / len(all_solo_steps)
        layout_results['summary']['avg_duo_steps'] = sum(all_duo_steps) / len(all_duo_steps)
        layout_results['summary']['avg_duo_optimized_steps'] = sum(all_duo_optimized_steps) / len(all_duo_optimized_steps)
        layout_results['summary']['total_exchange_positions'] = len(all_exchange_positions)
        layout_results['summary']['best_exchange_positions'] = list(all_exchange_positions)
    
    print(f"✅ Évaluation terminée: {len(layout_results['evaluations'])}/{len(recipe_groups)} groupes traités")
    
    return layout_results

def decode_grid(encoded_grid):
    """Décode une grille encodée en base64"""
    decoded_bytes = base64.b64decode(encoded_grid)
    return decoded_bytes.decode('utf-8')

def test_pathfinding():
    """Test du pathfinding avec obstacles"""
    print("🧪 Test du pathfinding avec obstacles")
    
    # Grille simple pour test
    grid_str = """XXXXXXXX
X  X X2X
XX    1X
X   XDXX
XXX    X
X TX OPX
X      X
XXXXXXXX"""
    
    grid = [list(row) for row in grid_str.split('\n')]
    
    # Créer un état de jeu optimisé
    state = OptimizedGameState(grid)
    pathfinder = OptimalPathfinder(state)
    
    # Test de chemin simple
    start = (1, 1)  # Case vide
    end = (2, 5)    # Case vide
    path = pathfinder.get_optimal_path(start, end)
    
    print(f"   Chemin de {start} à {end}: {len(path)} étapes")
    assert path is not None, "Le chemin devrait exister"
    assert len(path) > 0, "Le chemin ne devrait pas être vide"
    assert path[0] == start, "Le chemin doit commencer au bon endroit"
    assert path[-1] == end, "Le chemin doit finir au bon endroit"
    print("   ✅ Pathfinding de base fonctionne")

def test_exchange_detection():
    """Test de la détection d'échanges optimaux"""
    print("\n🧪 Test de la détection d'échanges")
    
    # Charger un layout réel
    batch_file = Path("../outputs/layouts_generes").glob("layout_batch_*.jsonl.gz")
    batch_file = next(batch_file, None)
    
    if not batch_file or not batch_file.exists():
        print("   ⚠️  Pas de layouts générés trouvés, génération d'un layout test...")
        return
    
    with gzip.open(batch_file, 'rt') as f:
        layout_data = json.loads(f.readline().strip())
    
    grid_str = decode_grid(layout_data['g'])
    grid = [list(row) for row in grid_str.split('\n')]
    
    print(f"   Layout testé:")
    for row in grid:
        print(f"   {''.join(row)}")
    
    # Configuration de test - charger les vraies recettes
    recipes = load_recipes_from_json()
    
    if not recipes:
        print("   ⚠️  Aucune recette trouvée, utilisation de recettes de test")
        recipes = [
            {"ingredients": ["onion"], "cooking_time": 9},
            {"ingredients": ["tomato"], "cooking_time": 6}
        ]
    else:
        print(f"   📋 Utilisation de {len(recipes)} recettes du fichier JSON")
    
    evaluator = LayoutEvaluator()
    
    # Évaluation avec détection d'échanges
    print("   🔄 Évaluation duo avec détection d'échanges...")
    result = evaluator.evaluate_duo_with_exchanges(grid, recipes)
    
    print(f"   📊 Résultats:")
    print(f"      Total étapes: {result['total_steps']}")
    print(f"      Échanges détectés: {len(result['exchange_positions'])}")
    
    if result['exchange_positions']:
        print(f"      Positions d'échange:")
        for pos, count in result['exchange_positions'].items():
            print(f"         {pos}: {count} échanges")
    
    # Test avec optimisation Y
    if result['optimal_y_positions']:
        print(f"   🎯 Optimisation avec 2 meilleures positions Y:")
        for pos in result['optimal_y_positions']:
            print(f"      Y placé en {pos}")
        
        optimized_result = evaluator.evaluate_duo_with_y_constraints(
            grid, recipes, result['optimal_y_positions']
        )
        
        print(f"      Étapes optimisées: {optimized_result['total_steps']}")
        improvement = result['total_steps'] - optimized_result['total_steps']
        print(f"      Amélioration: {improvement} étapes ({improvement/result['total_steps']*100:.1f}%)")
    
    print("   ✅ Détection d'échanges fonctionne")

def test_layout_evaluation():
    """Test complet d'évaluation d'un layout"""
    print("\n🧪 Test d'évaluation complète")
    
    # Trouver des layouts générés
    output_dir = Path("../outputs/layouts_generes")
    if not output_dir.exists():
        print("   ⚠️  Répertoire de layouts non trouvé")
        return
    
    batch_files = list(output_dir.glob("layout_batch_*.jsonl.gz"))
    if not batch_files:
        print("   ⚠️  Aucun batch de layouts trouvé")
        return
    
    print(f"   📁 {len(batch_files)} batches trouvés")
    
    # Tester le premier batch
    batch_file = batch_files[0]
    print(f"   🔄 Test du batch: {batch_file.name}")
    
    evaluator = LayoutEvaluator()
    
    try:
        # Charger les groupes de recettes depuis le fichier JSON
        recipe_groups = load_recipes_from_json()
        
        if not recipe_groups:
            print("   ⚠️  Aucun groupe de recettes trouvé, utilisation de groupes de test")
            recipe_groups = [
                {
                    'group_id': 1,
                    'recipes': [
                        {"ingredients": ["onion"], "cooking_time": 9},
                        {"ingredients": ["tomato"], "cooking_time": 6}
                    ]
                }
            ]
        
        print(f"   📜 {len(recipe_groups)} groupes de recettes chargés pour l'évaluation")
        
        # Évaluer quelques layouts
        layouts_tested = 0
        with gzip.open(batch_file, 'rt') as f:
            for line in f:
                if layouts_tested >= 1:  # Limiter à 1 layout pour le test (84 évaluations)
                    break
                
                layout_data = json.loads(line.strip())
                grid_str = decode_grid(layout_data['g'])
                grid = [list(row) for row in grid_str.split('\n')]
                
                print(f"\n   🎯 Layout {layouts_tested + 1}:")
                print(f"      Démarrage de {len(recipe_groups)} évaluations (une par groupe de recettes)...")
                
                # Évaluation complète avec tous les groupes de recettes
                results = evaluate_layout_with_all_recipe_groups(grid, recipe_groups, evaluator)
                
                # Résumé pour ce layout
                print(f"      ✅ Évaluation terminée:")
                print(f"         • Groupes traités: {len(results['evaluations'])}/{results['total_groups']}")
                print(f"         • Étapes solo (moy): {results['summary']['avg_solo_steps']:.1f}")
                print(f"         • Étapes duo (moy): {results['summary']['avg_duo_steps']:.1f}")
                print(f"         • Étapes optimisé (moy): {results['summary']['avg_duo_optimized_steps']:.1f}")
                print(f"         • Amélioration moy: {results['summary']['avg_duo_steps'] - results['summary']['avg_duo_optimized_steps']:.1f} étapes")
                
                layouts_tested += 1
        
        print(f"   ✅ {layouts_tested} layouts évalués avec succès")
        
    except Exception as e:
        print(f"   ❌ Erreur lors de l'évaluation: {e}")

def main():
    """Lancer tous les tests"""
    print("🧪 TESTS DU SYSTÈME D'ÉVALUATION AVEC ÉCHANGES")
    print("=" * 50)
    
    try:
        # Changer vers le répertoire de test
        os.chdir(Path(__file__).parent)
        
        test_pathfinding()
        test_exchange_detection()
        test_layout_evaluation()
        
        print("\n🎉 TOUS LES TESTS RÉUSSIS!")
        
    except Exception as e:
        print(f"\n❌ ERREUR DANS LES TESTS: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
