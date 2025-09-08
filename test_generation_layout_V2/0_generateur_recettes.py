#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur de combinaisons de recettes pour Overcooked
Génère toutes les combinaisons possibles selon les paramètres du fichier recipe_config.json
"""

import json
import itertools
from datetime import datetime
from typing import List, Dict, Tuple, Any
import numpy as np


class RecipeGenerator:
    """Générateur de combinaisons de recettes pour les expériences Overcooked."""
    
    def __init__(self, config_file: str = "recipe_config.json"):
        """
        Initialise le générateur avec les paramètres du fichier de configuration.
        
        Args:
            config_file (str): Chemin vers le fichier de configuration JSON
        """
        self.config_file = config_file
        self.config = self._load_config()
        
        # Paramètres de configuration
        self.combination_size = self.config["combination_size"]
        self.n_combinations = self.config["n_combinations"]
        self.onion_value = self.config["onion_value"]
        self.tomato_value = self.config["tomato_value"]
        self.onion_time = self.config["onion_time"]
        self.tomato_time = self.config["tomato_time"]
        
        # Générer toutes les recettes possibles
        self.all_recipes = self._generate_all_possible_recipes()
        
        print(f"🔧 Configuration chargée:")
        print(f"   - Taille des combinaisons: {self.combination_size}")
        print(f"   - Nombre de combinaisons à générer: {self.n_combinations}")
        print(f"   - Valeurs: Oignon={self.onion_value}, Tomate={self.tomato_value}")
        print(f"   - Temps: Oignon={self.onion_time}s, Tomate={self.tomato_time}s")
        print(f"📋 {len(self.all_recipes)} recettes uniques générées")
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge les paramètres depuis le fichier de configuration."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data["configuration"]
        except Exception as e:
            print(f"❌ Erreur lors du chargement de {self.config_file}: {e}")
            raise
    
    def _generate_all_possible_recipes(self, max_ingredients: int = 3) -> List[Dict[str, Any]]:
        """
        Génère toutes les recettes possibles avec les ingrédients disponibles.
        
        Args:
            max_ingredients (int): Nombre maximum d'ingrédients par recette
            
        Returns:
            List[Dict]: Liste de toutes les recettes possibles
        """
        recipes = []
        ingredients = ["onion", "tomato"]
        
        # Générer toutes les combinaisons possibles d'ingrédients (avec répétition)
        for length in range(1, max_ingredients + 1):
            for combination in itertools.combinations_with_replacement(ingredients, length):
                # Convertir en liste pour permettre les modifications
                recipe_ingredients = list(combination)
                
                # Calculer les statistiques de la recette
                onion_count = recipe_ingredients.count("onion")
                tomato_count = recipe_ingredients.count("tomato")
                
                recipe = {
                    "ingredients": recipe_ingredients,
                    "recipe_value": onion_count * self.onion_value + tomato_count * self.tomato_value,
                    "cooking_time": onion_count * self.onion_time + tomato_count * self.tomato_time,
                    "ingredient_count": len(recipe_ingredients),
                    "onion_count": onion_count,
                    "tomato_count": tomato_count
                }
                
                recipes.append(recipe)
        
        return recipes
    
    def generate_all_combinations(self) -> List[List[Dict[str, Any]]]:
        """
        Génère toutes les combinaisons possibles de recettes.
        
        Returns:
            List[List[Dict]]: Liste de toutes les combinaisons possibles
        """
        print(f"🔄 Génération de toutes les combinaisons de {self.combination_size} recettes...")
        
        # Générer toutes les combinaisons possibles
        all_combinations = list(itertools.combinations(self.all_recipes, self.combination_size))
        
        print(f"✅ {len(all_combinations):,} combinaisons générées")
        
        # Limiter au nombre demandé si nécessaire
        if self.n_combinations < len(all_combinations):
            print(f"🎯 Sélection de {self.n_combinations} combinaisons parmi {len(all_combinations)}")
            # Sélection diversifiée (prendre des combinaisons espacées)
            step = len(all_combinations) // self.n_combinations
            selected_combinations = [all_combinations[i * step] for i in range(self.n_combinations)]
        else:
            selected_combinations = all_combinations
            print(f"📋 Toutes les {len(all_combinations)} combinaisons conservées")
        
        return selected_combinations
    
    def _calculate_statistics(self, combinations: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Calcule les statistiques des combinaisons générées."""
        values = []
        for combination in combinations:
            total_value = sum(recipe["recipe_value"] for recipe in combination)
            values.append(total_value)
        
        return {
            "total_combinations_exported": len(combinations),
            "recipes_per_combination": self.combination_size,
            "unique_recipes_count": len(self.all_recipes),
            "diversity_optimized": True,
            "value_range": {
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "mean": round(np.mean(values), 1) if values else 0
            }
        }
    
    def _format_combinations_for_export(self, combinations: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Formate les combinaisons pour l'export JSON."""
        
        # Formatage des combinaisons avec IDs
        formatted_combinations = []
        for combo_idx, combination in enumerate(combinations, 1):
            total_value = sum(recipe["recipe_value"] for recipe in combination)
            total_cooking_time = sum(recipe["cooking_time"] for recipe in combination)
            total_ingredients = sum(recipe["ingredient_count"] for recipe in combination)
            
            formatted_recipes = []
            for recipe_idx, recipe in enumerate(combination, 1):
                formatted_recipe = {
                    "recipe_id": recipe_idx,
                    "ingredients": recipe["ingredients"],
                    "recipe_value": recipe["recipe_value"],
                    "cooking_time": recipe["cooking_time"]
                }
                formatted_recipes.append(formatted_recipe)
            
            formatted_combination = {
                "combination_id": combo_idx,
                "recipes": formatted_recipes,
                "total_value": total_value,
                "total_cooking_time": total_cooking_time,
                "total_ingredients": total_ingredients
            }
            formatted_combinations.append(formatted_combination)
        
        return formatted_combinations
    
    def _create_layout_integration_format(self, combinations: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Crée le format d'intégration pour les layouts."""
        
        # Extraire toutes les recettes uniques
        unique_recipes = []
        recipe_to_index = {}
        
        for recipe in self.all_recipes:
            recipe_key = tuple(recipe["ingredients"])
            if recipe_key not in recipe_to_index:
                recipe_to_index[recipe_key] = len(unique_recipes)
                unique_recipes.append(recipe["ingredients"])
        
        # Créer les indices des combinaisons
        combination_indices = []
        for combination in combinations:
            indices = []
            for recipe in combination:
                recipe_key = tuple(recipe["ingredients"])
                indices.append(recipe_to_index[recipe_key])
            combination_indices.append(indices)
        
        return {
            "recipe_list": unique_recipes,
            "combination_indices": combination_indices
        }
    
    def export_to_json(self, output_file: str = "ensemble_recettes.json") -> None:
        """
        Génère toutes les combinaisons et les exporte au format JSON.
        
        Args:
            output_file (str): Nom du fichier de sortie
        """
        print(f"🚀 Début de la génération complète...")
        
        # Générer toutes les combinaisons
        combinations = self.generate_all_combinations()
        
        # Calculer les statistiques
        statistics = self._calculate_statistics(combinations)
        
        # Formater les données pour l'export
        formatted_combinations = self._format_combinations_for_export(combinations)
        layout_format = self._create_layout_integration_format(combinations)
        
        # Créer la structure complète
        export_data = {
            "configuration": {
                "onion_value": self.onion_value,
                "tomato_value": self.tomato_value,
                "onion_time": self.onion_time,
                "tomato_time": self.tomato_time,
                "generation_date": datetime.now().strftime("%Y-%m-%d"),
                "purpose": "Layout generation for Overcooked cognitive science experiments",
                "export_type": "selected_combinations"
            },
            "statistics": statistics,
            "all_unique_recipes": self.all_recipes,
            "recipe_combinations": formatted_combinations,
            "layout_integration_format": layout_format
        }
        
        # Sauvegarder
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Export terminé avec succès!")
            print(f"📁 Fichier généré: {output_file}")
            print(f"📊 Statistiques:")
            print(f"   - {statistics['total_combinations_exported']} combinaisons exportées")
            print(f"   - {statistics['unique_recipes_count']} recettes uniques")
            print(f"   - Valeurs: {statistics['value_range']['min']}-{statistics['value_range']['max']} (moy: {statistics['value_range']['mean']})")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'export: {e}")
            raise


def main():
    """Fonction principale."""
    try:
        # Créer le générateur
        generator = RecipeGenerator()
        
        # Générer et exporter
        generator.export_to_json()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    main()