#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur de tous les groupes possibles de 6 recettes différentes
Crée toutes les combinaisons C(n,6) où n est le nombre total de recettes
"""

import json
import itertools
from pathlib import Path
import time

class RecipeGroupGenerator:
    """Générateur de tous les groupes possibles de 6 recettes."""
    
    def __init__(self):
        """Initialise le générateur de groupes de recettes."""
        self.base_dir = Path(__file__).parent.parent
        self.output_dir = self.base_dir / "outputs"
        self.output_dir.mkdir(exist_ok=True)
        
        print("🍽️  Générateur de groupes de recettes initialisé")
    
    def normalize_recipe(self, ingredients):
        """
        Normalise une recette en comptant les ingrédients.
        
        Args:
            ingredients: Liste d'ingrédients
            
        Returns:
            tuple: Signature normalisée (onion_count, tomato_count)
        """
        onion_count = ingredients.count('onion')
        tomato_count = ingredients.count('tomato')
        return (onion_count, tomato_count)
    
    def eliminate_duplicate_recipes(self, recipes):
        """
        Élimine les recettes dupliquées basées sur leur composition.
        
        Args:
            recipes: Liste des recettes brutes
            
        Returns:
            list: Liste des recettes uniques
        """
        seen_signatures = set()
        unique_recipes = []
        
        for recipe in recipes:
            signature = self.normalize_recipe(recipe['ingredients'])
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_recipes.append(recipe)
            else:
                print(f"   ⚠️  Doublon éliminé: {recipe['ingredients']} (signature: {signature})")
        
        return unique_recipes
    
    def generate_base_recipes(self):
        """Génère les recettes de base sans doublons."""
        print("🍳 Génération des recettes de base")
        
        recipes = []
        recipe_id = 1
        
        # Recettes simples (1 ingrédient)
        simple_recipes = [
            ['onion'],
            ['tomato']
        ]
        
        for ingredients in simple_recipes:
            recipes.append({
                'id': f'R{recipe_id:02d}',
                'ingredients': ingredients,
                'onion_value': 2,
                'tomato_value': 2,
                'onion_time': 6,
                'tomato_time': 6,
                'complexity': len(ingredients),
                'type': 'simple'
            })
            recipe_id += 1
        
        # Recettes doubles (2 mêmes ingrédients)
        double_recipes = [
            ['onion', 'onion'],
            ['tomato', 'tomato']
        ]
        
        for ingredients in double_recipes:
            recipes.append({
                'id': f'R{recipe_id:02d}',
                'ingredients': ingredients,
                'onion_value': 2,
                'tomato_value': 2,
                'onion_time': 6,
                'tomato_time': 6,
                'complexity': len(ingredients),
                'type': 'double'
            })
            recipe_id += 1
        
        # Recettes mixtes (2 ingrédients différents)
        mixed_2_recipes = [
            ['onion', 'tomato']  # Une seule version car l'ordre n'importe pas
        ]
        
        for ingredients in mixed_2_recipes:
            recipes.append({
                'id': f'R{recipe_id:02d}',
                'ingredients': ingredients,
                'onion_value': 2,
                'tomato_value': 2,
                'onion_time': 6,
                'tomato_time': 6,
                'complexity': len(ingredients),
                'type': 'mixed_2'
            })
            recipe_id += 1
        
        # Recettes moyennes (3 ingrédients) - Élimination des doublons évidents
        medium_recipes = [
            ['onion', 'onion', 'tomato'],  # 2 onions, 1 tomato
            ['tomato', 'tomato', 'onion'], # 2 tomatoes, 1 onion  
            ['onion', 'tomato', 'tomato']  # 1 onion, 2 tomatoes
            # Éliminé: ['tomato', 'onion', 'tomato'], ['onion', 'tomato', 'onion'], ['tomato', 'onion', 'onion'] (doublons)
        ]
        
        for ingredients in medium_recipes:
            recipes.append({
                'id': f'R{recipe_id:02d}',
                'ingredients': ingredients,
                'onion_value': 3,
                'tomato_value': 3,
                'onion_time': 8,
                'tomato_time': 6,
                'complexity': len(ingredients),
                'type': 'medium'
            })
            recipe_id += 1
        
        # Recettes complexes (4+ ingrédients) - Élimination des doublons évidents
        complex_recipes = [
            ['onion', 'onion', 'tomato', 'tomato'],    # 2 onions, 2 tomatoes
            ['onion', 'onion', 'onion', 'tomato'],     # 3 onions, 1 tomato
            ['tomato', 'tomato', 'tomato', 'onion'],   # 3 tomatoes, 1 onion
            ['onion', 'tomato', 'tomato', 'tomato'],   # 1 onion, 3 tomatoes
            ['onion', 'onion', 'tomato', 'tomato', 'onion'],     # 3 onions, 2 tomatoes
            ['tomato', 'tomato', 'onion', 'onion', 'tomato']     # 2 onions, 3 tomatoes
            # Éliminés: doublons basés sur l'ordre des ingrédients
        ]
        
        for ingredients in complex_recipes:
            recipes.append({
                'id': f'R{recipe_id:02d}',
                'ingredients': ingredients,
                'onion_value': 3,
                'tomato_value': 3,
                'onion_time': 9,
                'tomato_time': 6,
                'complexity': len(ingredients),
                'type': 'complex'
            })
            recipe_id += 1
        
        print(f"📊 Recettes générées avant nettoyage: {len(recipes)}")
        
        # Éliminer les doublons basés sur la composition
        unique_recipes = self.eliminate_duplicate_recipes(recipes)
        
        print(f"✅ Recettes uniques après nettoyage: {len(unique_recipes)}")
        
        # Renuméroter les IDs après nettoyage
        for i, recipe in enumerate(unique_recipes, 1):
            recipe['id'] = f'R{i:02d}'
        
        return unique_recipes
    
    def generate_all_recipe_groups(self, recipes, group_size=6):
        """
        Génère tous les groupes possibles de recettes.
        
        Args:
            recipes: Liste des recettes de base
            group_size: Taille des groupes (défaut: 6)
            
        Returns:
            list: Liste de tous les groupes possibles
        """
        print(f"🔢 Génération de tous les groupes de {group_size} recettes")
        print(f"   À partir de {len(recipes)} recettes de base")
        
        # Calculer le nombre total de combinaisons
        from math import comb
        total_combinations = comb(len(recipes), group_size)
        print(f"   Nombre total de combinaisons: {total_combinations:,}")
        
        if total_combinations > 100000:
            print(f"⚠️  ATTENTION: {total_combinations:,} combinaisons générées!")
            print("   Cela peut prendre beaucoup de temps et d'espace...")
        
        # Générer toutes les combinaisons
        all_groups = []
        group_id = 1
        
        start_time = time.time()
        
        for recipe_combination in itertools.combinations(recipes, group_size):
            group = {
                'group_id': f'G{group_id:06d}',
                'recipes': list(recipe_combination),
                'recipe_ids': [recipe['id'] for recipe in recipe_combination],
                'complexity_distribution': self.analyze_group_complexity(recipe_combination),
                'total_ingredients': sum(len(recipe['ingredients']) for recipe in recipe_combination),
                'avg_complexity': sum(recipe['complexity'] for recipe in recipe_combination) / len(recipe_combination)
            }
            
            all_groups.append(group)
            group_id += 1
            
            # Affichage de progression
            if group_id % 10000 == 0:
                elapsed = time.time() - start_time
                print(f"   Progression: {group_id:,}/{total_combinations:,} ({elapsed:.1f}s)")
        
        elapsed = time.time() - start_time
        print(f"✅ {len(all_groups):,} groupes générés en {elapsed:.1f}s")
        
        return all_groups
    
    def analyze_group_complexity(self, recipe_group):
        """Analyse la distribution de complexité d'un groupe de recettes."""
        complexity_count = {}
        type_count = {}
        
        for recipe in recipe_group:
            complexity = recipe['complexity']
            recipe_type = recipe['type']
            
            complexity_count[complexity] = complexity_count.get(complexity, 0) + 1
            type_count[recipe_type] = type_count.get(recipe_type, 0) + 1
        
        return {
            'by_complexity': complexity_count,
            'by_type': type_count,
            'min_complexity': min(recipe['complexity'] for recipe in recipe_group),
            'max_complexity': max(recipe['complexity'] for recipe in recipe_group),
            'diversity_score': len(set(recipe['complexity'] for recipe in recipe_group))
        }
    
    def save_recipe_groups(self, all_groups, base_recipes):
        """Sauvegarde tous les groupes de recettes."""
        timestamp = int(time.time())
        
        # Fichier principal avec tous les groupes
        main_file = self.output_dir / f"all_recipe_groups_{timestamp}.json"
        
        output_data = {
            'timestamp': timestamp,
            'generation_info': {
                'base_recipes_count': len(base_recipes),
                'group_size': 6,
                'total_groups': len(all_groups),
                'generation_method': 'exhaustive_combinations'
            },
            'base_recipes': base_recipes,
            'recipe_groups': all_groups,
            'statistics': self.calculate_groups_statistics(all_groups)
        }
        
        print(f"💾 Sauvegarde de {len(all_groups):,} groupes...")
        
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        file_size_mb = main_file.stat().st_size / (1024 * 1024)
        print(f"✅ Fichier principal sauvé: {main_file.name} ({file_size_mb:.1f} MB)")
        
        # Sauvegarder également les recettes de base séparément
        base_recipes_file = self.output_dir / f"base_recipes_{timestamp}.json"
        
        base_data = {
            'timestamp': timestamp,
            'total_recipes': len(base_recipes),
            'recipes': base_recipes
        }
        
        with open(base_recipes_file, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Recettes de base sauvées: {base_recipes_file.name}")
        
        return main_file, base_recipes_file
    
    def calculate_groups_statistics(self, all_groups):
        """Calcule les statistiques sur tous les groupes."""
        if not all_groups:
            return {}
        
        # Distribution des complexités moyennes
        avg_complexities = [group['avg_complexity'] for group in all_groups]
        total_ingredients = [group['total_ingredients'] for group in all_groups]
        diversity_scores = [group['complexity_distribution']['diversity_score'] for group in all_groups]
        
        stats = {
            'complexity_stats': {
                'min_avg_complexity': min(avg_complexities),
                'max_avg_complexity': max(avg_complexities),
                'avg_complexity': sum(avg_complexities) / len(avg_complexities)
            },
            'ingredients_stats': {
                'min_total_ingredients': min(total_ingredients),
                'max_total_ingredients': max(total_ingredients),
                'avg_total_ingredients': sum(total_ingredients) / len(total_ingredients)
            },
            'diversity_stats': {
                'min_diversity': min(diversity_scores),
                'max_diversity': max(diversity_scores),
                'avg_diversity': sum(diversity_scores) / len(diversity_scores)
            }
        }
        
        return stats
    
    def run_generation(self, group_size=6):
        """Lance la génération complète des groupes de recettes."""
        print(f"🚀 GÉNÉRATION DE TOUS LES GROUPES DE RECETTES")
        print(f"📊 Taille des groupes: {group_size} recettes")
        print("="*70)
        
        # Générer les recettes de base
        print("📋 Génération des recettes de base...")
        base_recipes = self.generate_base_recipes()
        
        print(f"✅ {len(base_recipes)} recettes de base générées")
        
        # Afficher la distribution des types
        type_distribution = {}
        for recipe in base_recipes:
            recipe_type = recipe['type']
            type_distribution[recipe_type] = type_distribution.get(recipe_type, 0) + 1
        
        print(f"📊 Distribution par type:")
        for recipe_type, count in type_distribution.items():
            print(f"   - {recipe_type}: {count} recettes")
        
        # Générer tous les groupes
        all_groups = self.generate_all_recipe_groups(base_recipes, group_size)
        
        # Sauvegarder
        main_file, base_file = self.save_recipe_groups(all_groups, base_recipes)
        
        # Afficher le résumé
        print(f"\n🎉 GÉNÉRATION TERMINÉE!")
        print(f"📊 Résumé:")
        print(f"   - Recettes de base: {len(base_recipes)}")
        print(f"   - Groupes générés: {len(all_groups):,}")
        print(f"   - Fichier principal: {main_file.name}")
        print(f"   - Fichier recettes: {base_file.name}")
        
        # Afficher quelques exemples
        print(f"\n📋 Exemples de groupes:")
        for i, group in enumerate(all_groups[:3]):
            print(f"   {group['group_id']}: {group['recipe_ids']}")
            print(f"      Complexité moyenne: {group['avg_complexity']:.1f}")
            print(f"      Total ingrédients: {group['total_ingredients']}")
        
        if len(all_groups) > 3:
            print(f"   ... et {len(all_groups) - 3:,} autres groupes")
        
        return True

def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Génère tous les groupes possibles de recettes'
    )
    
    parser.add_argument(
        '--group-size',
        type=int,
        default=6,
        help='Taille des groupes de recettes (défaut: 6)'
    )
    
    args = parser.parse_args()
    
    try:
        generator = RecipeGroupGenerator()
        success = generator.run_generation(args.group_size)
        
        if success:
            print("✅ Génération réussie!")
        else:
            print("❌ Échec de la génération")
            exit(1)
            
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
