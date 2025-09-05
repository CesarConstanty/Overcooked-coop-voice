#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur de groupes de recettes pour layouts Overcooked
Génère tous les groupes possibles de recettes avec 1-3 ingrédients
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List
from itertools import combinations

logger = logging.getLogger(__name__)

class OptimizedRecipeGenerator:
    """
    Générateur pour créer TOUS les groupes de recettes possibles.
    """
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        self.base_dir = Path(__file__).parent.parent
        self.recipe_config_file = self.base_dir / "config" / "recipe_config.json"
        
        # Charger la configuration des recettes
        self.recipe_config = self.load_recipe_config()
        
        # Configuration des recettes
        recipe_settings = self.recipe_config["configuration"]
        self.group_size = recipe_settings["group_size"]
        self.min_ingredients = recipe_settings["min_ingredient"]
        self.max_ingredients = recipe_settings["max_ingredient"]
        self.allowed_ingredients = ["onion", "tomato"]
        
        # Dossier de sortie
        self.output_dir = self.base_dir / "outputs"
        
        logger.info("🧅 Générateur de recettes initialisé")
        logger.info(f"Ingrédients: {self.allowed_ingredients}")
        logger.info(f"Taille groupes: {self.group_size}")
        logger.info(f"Ingrédients par recette: {self.min_ingredients}-{self.max_ingredients}")

    def load_recipe_config(self) -> Dict:
        """Charge la configuration spécifique des recettes."""
        with open(self.recipe_config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_all_recipe_combinations(self) -> List[List[str]]:
        """
        Génère TOUTES les recettes possibles selon la configuration.
        1-3 ingrédients avec toutes les combinaisons possibles sans répétition.
        """
        all_recipes = []
        
        for num_ingredients in range(self.min_ingredients, self.max_ingredients + 1):
            if num_ingredients == 1:
                # Recettes à 1 ingrédient
                for ingredient in self.allowed_ingredients:
                    all_recipes.append([ingredient])
            
            elif num_ingredients == 2:
                # Recettes à 2 ingrédients - toutes les combinaisons avec répétitions
                for i1 in self.allowed_ingredients:
                    for i2 in self.allowed_ingredients:
                        recipe = sorted([i1, i2])  # Trier pour éviter les doublons
                        if recipe not in all_recipes:
                            all_recipes.append(recipe)
            
            elif num_ingredients == 3:
                # Recettes à 3 ingrédients - toutes les combinaisons avec répétitions
                for i1 in self.allowed_ingredients:
                    for i2 in self.allowed_ingredients:
                        for i3 in self.allowed_ingredients:
                            recipe = sorted([i1, i2, i3])  # Trier pour éviter les doublons
                            if recipe not in all_recipes:
                                all_recipes.append(recipe)
        
        # Retirer les doublons et trier
        unique_recipes = []
        seen = set()
        for recipe in all_recipes:
            recipe_key = tuple(sorted(recipe))
            if recipe_key not in seen:
                seen.add(recipe_key)
                unique_recipes.append(recipe)
        
        logger.info(f"📝 {len(unique_recipes)} recettes uniques générées")
        for i, recipe in enumerate(unique_recipes):
            logger.info(f"  {i+1:2d}. {recipe}")
        
        return unique_recipes
    
    
    def create_recipe_groups(self, all_recipes: List[List[str]]) -> List[Dict]:
        """
        Crée TOUS les groupes possibles de recettes (sans répétition).
        Génère toutes les combinaisons de group_size recettes parmi toutes les recettes possibles.
        """
        if len(all_recipes) < self.group_size:
            logger.warning(f"⚠️ Pas assez de recettes ({len(all_recipes)}) pour créer des groupes de {self.group_size}")
            # Créer un seul groupe avec toutes les recettes disponibles
            group = {
                "group_id": 1,
                "recipes": [{"ingredients": recipe} for recipe in all_recipes]
            }
            return [group]
        
        # Générer TOUTES les combinaisons possibles de group_size recettes
        all_combinations = list(combinations(all_recipes, self.group_size))
        
        logger.info(f"🎯 {len(all_combinations)} groupes possibles trouvés")
        
        groups = []
        for i, recipe_combination in enumerate(all_combinations):
            group = {
                "group_id": i + 1,
                "recipes": [{"ingredients": recipe} for recipe in recipe_combination]
            }
            groups.append(group)
            
            # Log pour les premiers groupes
            if i < 5 or i == len(all_combinations) - 1:
                recipe_names = [str(recipe) for recipe in recipe_combination]
                logger.info(f"  Groupe {i+1}: {recipe_names}")
        
        return groups
    
    
    def save_recipe_groups(self, recipe_groups: List[Dict]) -> str:
        """Sauvegarde tous les groupes de recettes dans un seul fichier."""
        # Créer le dossier de sortie
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = self.output_dir / "recipes.json"
        
        # Préparer les données de sortie
        output_data = {
            "generation_info": {
                "timestamp": time.time(),
                "total_groups": len(recipe_groups),
                "group_size": self.group_size
            },
            "recipe_groups": recipe_groups
        }
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"💾 Groupes de recettes sauvegardés: {output_file}")
        logger.info(f"📊 {len(recipe_groups)} groupes dans un fichier unique")
        
        return str(output_file)
    
    
    def run_generation(self) -> bool:
        """Lance la génération complète des groupes de recettes."""
        start_time = time.time()
        
        try:
            # 1. Générer toutes les recettes possibles
            all_recipes = self.generate_all_recipe_combinations()
            
            # 2. Créer tous les groupes possibles
            recipe_groups = self.create_recipe_groups(all_recipes)
            
            # 3. Sauvegarder
            output_file = self.save_recipe_groups(recipe_groups)
            
            generation_time = time.time() - start_time
            
            logger.info("✅ Génération de recettes terminée!")
            logger.info(f"⏱️ Durée: {generation_time:.2f}s")
            logger.info(f"📊 Résultats: {len(recipe_groups)} groupes dans {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur génération recettes: {e}")
            return False

def main():
    """Fonction principale."""
    try:
        generator = OptimizedRecipeGenerator()
        success = generator.run_generation()
        
        if success:
            print("🎉 Génération de recettes réussie!")
            return 0
        else:
            print("❌ Échec génération recettes")
            return 1
    
    except Exception as e:
        print(f"💥 Erreur critique: {e}")
        return 1

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    exit(main())
