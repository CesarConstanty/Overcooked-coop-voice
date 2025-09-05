#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur professio        # Dossiers de sortie
        self.output_dir = self.base_dir / "outputs" / "recipe_combinations"
        self.output_dir.mkdir(parents=True, exist_ok=True)l de groupes de recettes Overcooked
- Génération exhaustive de recettes 1-3 ingrédients (oignons/tomates uniquement)
- Création de tous les groupes possibles de 6 recettes uniques
- Validation stricte des doublons et optimisation des combinaisons
- Format de sortie professionnel avec métadonnées complètes
"""

import json
import itertools
import logging
import time
import math
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Any
import argparse

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('recipe_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RecipeSignature:
    """Classe pour représenter et comparer les signatures de recettes."""
    
    def __init__(self, onion_count: int, tomato_count: int):
        self.onion_count = onion_count
        self.tomato_count = tomato_count
        self.total_ingredients = onion_count + tomato_count
    
    def __eq__(self, other):
        return (self.onion_count == other.onion_count and 
                self.tomato_count == other.tomato_count)
    
    def __hash__(self):
        return hash((self.onion_count, self.tomato_count))
    
    def __str__(self):
        return f"({self.onion_count}O, {self.tomato_count}T)"
    
    def to_ingredients_list(self) -> List[str]:
        """Convertit la signature en liste d'ingrédients."""
        ingredients = ['onion'] * self.onion_count + ['tomato'] * self.tomato_count
        return ingredients

class ProfessionalRecipeGenerator:
    """Générateur professionnel de groupes de recettes."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise le générateur avec la configuration."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Paramètres depuis la configuration
        recipe_config = self.config["recipe_config"]
        self.min_ingredients = recipe_config["min_ingredients_per_recipe"]
        self.max_ingredients = recipe_config["max_ingredients_per_recipe"]
        self.allowed_ingredients = recipe_config["allowed_ingredients"]
        self.group_size = recipe_config["group_size"]
        self.ensure_no_duplicates = recipe_config["ensure_no_duplicates"]
        
        # Dossiers de sortie
        self.output_dir = self.base_dir / "outputs" / "recipe_combinations"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🍽️  Générateur de recettes initialisé")
        logger.info(f"📊 Contraintes: {self.min_ingredients}-{self.max_ingredients} ingrédients")
        logger.info(f"🥕 Ingrédients autorisés: {self.allowed_ingredients}")
        logger.info(f"👥 Taille des groupes: {self.group_size}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_all_possible_recipes(self) -> List[Dict]:
        """Génère toutes les recettes possibles selon les contraintes."""
        recipes = []
        recipe_signatures = set()
        recipe_id = 1
        
        logger.info("🔄 Génération de toutes les recettes possibles...")
        
        # Générer toutes les combinaisons possibles
        for total_ingredients in range(self.min_ingredients, self.max_ingredients + 1):
            logger.info(f"   Génération recettes à {total_ingredients} ingrédient(s)")
            
            # Pour chaque nombre total d'ingrédients, générer toutes les répartitions oignons/tomates
            for onion_count in range(total_ingredients + 1):
                tomato_count = total_ingredients - onion_count
                
                # Créer la signature
                signature = RecipeSignature(onion_count, tomato_count)
                
                # Éviter les doublons
                if signature in recipe_signatures:
                    continue
                
                recipe_signatures.add(signature)
                
                # Créer la recette
                recipe = {
                    'id': f'R{recipe_id:03d}',
                    'ingredients': signature.to_ingredients_list(),
                    'signature': {
                        'onion_count': onion_count,
                        'tomato_count': tomato_count,
                        'total_ingredients': total_ingredients
                    },
                    'complexity': total_ingredients,
                    'onion_value': 3,  # Valeurs par défaut depuis l'exemple
                    'tomato_value': 2,
                    'onion_time': 9,
                    'tomato_time': 6,
                    'type': self.classify_recipe_type(onion_count, tomato_count),
                    'metadata': {
                        'generation_timestamp': time.time(),
                        'unique_signature': str(signature)
                    }
                }
                
                recipes.append(recipe)
                recipe_id += 1
        
        logger.info(f"✅ {len(recipes)} recettes uniques générées")
        return recipes
    
    def classify_recipe_type(self, onion_count: int, tomato_count: int) -> str:
        """Classifie le type de recette selon sa composition."""
        total = onion_count + tomato_count
        
        if total == 1:
            return 'simple'
        elif total == 2:
            if onion_count == tomato_count:
                return 'mixed_balanced'
            else:
                return 'double_single'
        elif total == 3:
            if abs(onion_count - tomato_count) <= 1:
                return 'complex_balanced'
            else:
                return 'complex_dominated'
        else:
            return 'unknown'
    
    def validate_recipe_group(self, recipes: List[Dict]) -> bool:
        """Valide qu'un groupe de recettes ne contient pas de doublons."""
        if not self.ensure_no_duplicates:
            return True
        
        signatures = set()
        for recipe in recipes:
            sig = (recipe['signature']['onion_count'], recipe['signature']['tomato_count'])
            if sig in signatures:
                return False
            signatures.add(sig)
        
        return True
    
    def calculate_group_statistics(self, recipes: List[Dict]) -> Dict:
        """Calcule les statistiques d'un groupe de recettes."""
        total_ingredients = sum(r['signature']['total_ingredients'] for r in recipes)
        complexities = [r['complexity'] for r in recipes]
        
        # Répartition par type
        type_distribution = defaultdict(int)
        for recipe in recipes:
            type_distribution[recipe['type']] += 1
        
        # Répartition ingrédients
        onion_total = sum(r['signature']['onion_count'] for r in recipes)
        tomato_total = sum(r['signature']['tomato_count'] for r in recipes)
        
        return {
            'recipe_count': len(recipes),
            'total_ingredients': total_ingredients,
            'avg_complexity': total_ingredients / len(recipes) if recipes else 0,
            'min_complexity': min(complexities) if complexities else 0,
            'max_complexity': max(complexities) if complexities else 0,
            'onion_total': onion_total,
            'tomato_total': tomato_total,
            'ingredient_balance': abs(onion_total - tomato_total),
            'type_distribution': dict(type_distribution),
            'complexity_distribution': {
                str(i): complexities.count(i) for i in range(self.min_ingredients, self.max_ingredients + 1)
            }
        }
    
    def generate_all_recipe_groups(self, recipes: List[Dict]) -> List[Dict]:
        """Génère tous les groupes possibles de recettes."""
        logger.info(f"🔄 Génération des groupes de {self.group_size} recettes...")
        
        # Calculer le nombre total de combinaisons
        total_combinations = math.comb(len(recipes), self.group_size)
        logger.info(f"📊 Nombre total de combinaisons: {total_combinations:,}")
        
        if total_combinations > 10_000_000:  # Limite de sécurité
            logger.warning(f"⚠️  Nombre de combinaisons très élevé: {total_combinations:,}")
            logger.warning("Considérez réduire le nombre de recettes ou la taille des groupes")
        
        recipe_groups = []
        processed = 0
        
        # Générer toutes les combinaisons
        for group_recipes in itertools.combinations(recipes, self.group_size):
            group_recipes_list = list(group_recipes)
            
            # Valider le groupe
            if not self.validate_recipe_group(group_recipes_list):
                continue
            
            # Calculer les statistiques du groupe
            group_stats = self.calculate_group_statistics(group_recipes_list)
            
            # Créer le groupe
            group = {
                'group_id': f'G{len(recipe_groups) + 1:06d}',
                'recipes': group_recipes_list,
                'statistics': group_stats,
                'metadata': {
                    'generation_timestamp': time.time(),
                    'validation_passed': True,
                    'generation_index': len(recipe_groups)
                }
            }
            
            recipe_groups.append(group)
            processed += 1
            
            # Log du progrès
            if processed % 10000 == 0:
                progress = processed / total_combinations * 100
                logger.info(f"📈 Progression: {processed:,}/{total_combinations:,} ({progress:.1f}%)")
        
        logger.info(f"✅ {len(recipe_groups):,} groupes valides générés")
        return recipe_groups
    
    def save_results(self, recipes: List[Dict], recipe_groups: List[Dict]) -> Tuple[str, str]:
        """Sauvegarde les résultats dans des fichiers JSON."""
        timestamp = int(time.time())
        
        # Sauvegarder les recettes de base
        base_recipes_file = self.output_dir / f"base_recipes_{timestamp}.json"
        base_recipes_data = {
            'generation_info': {
                'timestamp': timestamp,
                'total_recipes': len(recipes),
                'constraints': {
                    'min_ingredients': self.min_ingredients,
                    'max_ingredients': self.max_ingredients,
                    'allowed_ingredients': self.allowed_ingredients,
                    'ensure_no_duplicates': self.ensure_no_duplicates
                },
                'generation_time': time.time()
            },
            'recipes': recipes,
            'statistics': self.calculate_global_recipe_statistics(recipes)
        }
        
        with open(base_recipes_file, 'w', encoding='utf-8') as f:
            json.dump(base_recipes_data, f, indent=2, ensure_ascii=False)
        
        # Sauvegarder les groupes de recettes
        groups_file = self.output_dir / f"all_recipe_groups_{timestamp}.json"
        groups_data = {
            'generation_info': {
                'timestamp': timestamp,
                'total_groups': len(recipe_groups),
                'group_size': self.group_size,
                'base_recipes_count': len(recipes),
                'generation_time': time.time()
            },
            'recipe_groups': recipe_groups,
            'base_recipes': recipes,  # Inclure pour référence
            'global_statistics': self.calculate_global_group_statistics(recipe_groups)
        }
        
        with open(groups_file, 'w', encoding='utf-8') as f:
            json.dump(groups_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Fichiers sauvegardés:")
        logger.info(f"   📄 Recettes: {base_recipes_file.name}")
        logger.info(f"   📄 Groupes: {groups_file.name}")
        
        return str(base_recipes_file), str(groups_file)
    
    def calculate_global_recipe_statistics(self, recipes: List[Dict]) -> Dict:
        """Calcule les statistiques globales des recettes."""
        complexity_distribution = defaultdict(int)
        type_distribution = defaultdict(int)
        
        for recipe in recipes:
            complexity_distribution[recipe['complexity']] += 1
            type_distribution[recipe['type']] += 1
        
        return {
            'total_recipes': len(recipes),
            'complexity_distribution': dict(complexity_distribution),
            'type_distribution': dict(type_distribution),
            'ingredients_range': f"{self.min_ingredients}-{self.max_ingredients}",
            'unique_signatures': len(set(
                (r['signature']['onion_count'], r['signature']['tomato_count']) 
                for r in recipes
            ))
        }
    
    def calculate_global_group_statistics(self, recipe_groups: List[Dict]) -> Dict:
        """Calcule les statistiques globales des groupes."""
        avg_complexities = [group['statistics']['avg_complexity'] for group in recipe_groups]
        ingredient_balances = [group['statistics']['ingredient_balance'] for group in recipe_groups]
        
        return {
            'total_groups': len(recipe_groups),
            'avg_group_complexity': sum(avg_complexities) / len(avg_complexities) if avg_complexities else 0,
            'min_group_complexity': min(avg_complexities) if avg_complexities else 0,
            'max_group_complexity': max(avg_complexities) if avg_complexities else 0,
            'avg_ingredient_balance': sum(ingredient_balances) / len(ingredient_balances) if ingredient_balances else 0,
            'group_size': self.group_size
        }
    
    def run_generation(self) -> bool:
        """Lance la génération complète des recettes et groupes."""
        start_time = time.time()
        
        try:
            logger.info("🚀 Démarrage génération des recettes et groupes")
            
            # 1. Générer toutes les recettes possibles
            recipes = self.generate_all_possible_recipes()
            if not recipes:
                logger.error("❌ Aucune recette générée")
                return False
            
            # 2. Générer tous les groupes possibles
            recipe_groups = self.generate_all_recipe_groups(recipes)
            if not recipe_groups:
                logger.error("❌ Aucun groupe de recettes généré")
                return False
            
            # 3. Sauvegarder les résultats
            base_file, groups_file = self.save_results(recipes, recipe_groups)
            
            # 4. Rapport final
            generation_time = time.time() - start_time
            logger.info(f"✅ Génération terminée en {generation_time:.1f}s")
            logger.info(f"📊 Résultats:")
            logger.info(f"   🍽️  Recettes uniques: {len(recipes)}")
            logger.info(f"   👥 Groupes générés: {len(recipe_groups):,}")
            logger.info(f"   ⚡ Performance: {len(recipe_groups)/generation_time:.1f} groupes/sec")
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Erreur durant la génération: {e}", exc_info=True)
            return False

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Générateur professionnel de groupes de recettes Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json", 
                       help="Fichier de configuration")
    parser.add_argument("--group-size", type=int,
                       help="Taille des groupes de recettes (override config)")
    parser.add_argument("--max-ingredients", type=int,
                       help="Nombre maximum d'ingrédients par recette (override config)")
    
    args = parser.parse_args()
    
    try:
        generator = ProfessionalRecipeGenerator(args.config)
        
        # Overrides depuis la ligne de commande
        if args.group_size:
            generator.group_size = args.group_size
            logger.info(f"🎯 Taille des groupes overridée: {args.group_size}")
        
        if args.max_ingredients:
            generator.max_ingredients = args.max_ingredients
            logger.info(f"🎯 Max ingrédients overridé: {args.max_ingredients}")
        
        success = generator.run_generation()
        
        if success:
            logger.info("🎉 Génération réussie!")
            return 0
        else:
            logger.error("❌ Échec de la génération")
            return 1
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
