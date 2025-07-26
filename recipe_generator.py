#!/usr/bin/env python3
"""
Recipe Generator for Overcooked Cognitive Science Experiments

This module generates diverse sets of recipes for the Overcooked game environment,
allowing researchers to create balanced experimental conditions with parameterizable
diversity selection.

Author: Cesar Constanty
Date: July 25, 2025
"""

import numpy as np
import matplotlib.pyplot as plt
from itertools import combinations
from copy import deepcopy
from typing import List, Tuple, Dict, Any, Optional
import json
import argparse

try:
    from overcooked_ai_py.mdp.overcooked_mdp import Recipe
except ImportError:
    print("Warning: overcooked_ai_py not found. Please install the required dependencies.")
    Recipe = None


class RecipeGenerator:
    """
    A class to generate and analyze diverse recipe combinations for Overcooked experiments.
    
    This class handles the generation of recipe combinations with equal total ingredient values,
    analyzes their diversity, and selects the most diverse subsets for experimental use.
    """
    
    def __init__(self, onion_value: int = 3, tomato_value: int = 2, 
                 onion_time: int = 9, tomato_time: int = 6):
        """
        Initialize the RecipeGenerator with ingredient values and cooking times.
        
        Args:
            onion_value (int): Value assigned to onion ingredients
            tomato_value (int): Value assigned to tomato ingredients
            onion_time (int): Cooking time for onion ingredients
            tomato_time (int): Cooking time for tomato ingredients
        """
        if Recipe is None:
            raise ImportError("overcooked_ai_py module is required but not found")
            
        self.onion_value = onion_value
        self.tomato_value = tomato_value
        self.onion_time = onion_time
        self.tomato_time = tomato_time
        self.recipes = {}
        self.combinations = {}
        self.selected_orders = []
        
        # Configure recipes
        Recipe.configure({'onion_value': onion_value, 'tomato_value': tomato_value})
        self._initialize_recipes()
    
    def _initialize_recipes(self):
        """Initialize the recipes dictionary with all available recipes and their values."""
        print(f"Available recipes: {Recipe.ALL_RECIPES}")
        
        for recipe in Recipe.ALL_RECIPES:
            self.recipes[recipe] = recipe.value
            print(f"Recipe: {recipe} - Value: {recipe.value}")
    
    def generate_combinations(self, combination_size: int = 6) -> Dict[Tuple, int]:
        """
        Generate all possible combinations of recipes and calculate their total values.
        
        Args:
            combination_size (int): Number of recipes per combination
            
        Returns:
            Dict[Tuple, int]: Dictionary mapping recipe combinations to their total values
        """
        print(f"Generating combinations of {combination_size} recipes...")
        
        comb = combinations(self.recipes, combination_size)
        total_combinations = len(list(deepcopy(comb)))
        print(f"Total possible combinations: {total_combinations}")
        
        # Recreate iterator and calculate values
        comb = combinations(self.recipes, combination_size)
        comb_value = {}
        
        for orders in comb:
            total_value = sum(recipe.value for recipe in orders)
            comb_value[orders] = total_value
        
        # Sort combinations by value
        self.combinations = {k: v for k, v in sorted(comb_value.items(), key=lambda item: item[1])}
        
        return self.combinations
    
    def filter_by_value(self, target_value: int) -> List[Tuple]:
        """
        Filter combinations by a specific total value.
        
        Args:
            target_value (int): Target total value for filtering
            
        Returns:
            List[Tuple]: List of recipe combinations with the target value
        """
        filtered_orders = [orders for orders, value in self.combinations.items() 
                          if value == target_value]
        print(f"Number of orders with value {target_value}: {len(filtered_orders)}")
        
        self.selected_orders = filtered_orders
        return filtered_orders
    
    def print_value_statistics(self):
        """Print statistics about the distribution of combination values."""
        print("\nValue distribution statistics:")
        
        former_value = 0
        count = 0
        
        for orders, value in self.combinations.items():
            if value != former_value:
                if former_value != 0:
                    print(f"Value: {former_value}, Number of combinations: {count}")
                former_value = value
                count = 1
            else:
                count += 1
        
        # Print the last group
        if count > 0:
            print(f"Value: {former_value}, Number of combinations: {count}")
    
    def calculate_diversity_matrix(self, orders: Optional[List[Tuple]] = None) -> np.ndarray:
        """
        Calculate the diversity matrix between recipe combinations.
        
        The diversity is measured as the number of different recipes between combinations.
        
        Args:
            orders (List[Tuple], optional): List of recipe combinations. 
                                          Uses self.selected_orders if None.
            
        Returns:
            np.ndarray: Matrix where element [i,j] represents the number of different 
                       recipes between combination i and combination j
        """
        if orders is None:
            orders = self.selected_orders
        
        if not orders:
            raise ValueError("No orders available. Run filter_by_value() first.")
        
        n_orders = len(orders)
        diversity_matrix = np.zeros((n_orders, n_orders))
        
        for i in range(n_orders):
            for j in range(n_orders):
                # Number of recipes in i that are not in j
                diversity_matrix[i, j] = len(set(orders[i]) - set(orders[j]))
        
        return diversity_matrix
    
    def visualize_diversity_matrix(self, diversity_matrix: np.ndarray, 
                                 save_path: Optional[str] = None):
        """
        Visualize the diversity matrix as a heatmap.
        
        Args:
            diversity_matrix (np.ndarray): The diversity matrix to visualize
            save_path (str, optional): Path to save the plot. If None, displays the plot.
        """
        plt.figure(figsize=(10, 8))
        plt.imshow(diversity_matrix, cmap='hot', interpolation='nearest')
        plt.colorbar(label='Number of Different Recipes')
        plt.title('Recipe Combination Diversity Matrix')
        plt.xlabel('Combination Index')
        plt.ylabel('Combination Index')
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Diversity matrix saved to {save_path}")
        else:
            plt.show()
    
    def calculate_set_diversity_distribution(self, n_combinations: int, 
                                           orders: Optional[List[Tuple]] = None) -> Tuple[List[float], List[int]]:
        """
        Calculate the distribution of diversity scores for all possible sets of n_combinations.
        
        Args:
            n_combinations (int): Number of combinations per set
            orders (List[Tuple], optional): List of recipe combinations. 
                                          Uses all combinations if None.
            
        Returns:
            Tuple[List[float], List[int]]: Diversity scores and their frequencies
        """
        if orders is None:
            orders = list(self.combinations.keys())
        
        if not orders:
            raise ValueError("No orders available.")
        
        if n_combinations > len(orders):
            raise ValueError(f"Cannot select {n_combinations} combinations from {len(orders)} available")
        
        print(f"Calculating diversity distribution for sets of {n_combinations} combinations...")
        print(f"Total combinations available: {len(orders)}")
        
        # Calculate diversity matrix
        diversity_matrix = self.calculate_diversity_matrix(orders)
        
        # Generate all possible sets of n_combinations
        all_possible_sets = list(combinations(range(len(orders)), n_combinations))
        print(f"Total possible sets to evaluate: {len(all_possible_sets)}")
        
        # Calculate diversity score for each set
        diversity_scores = []
        for set_indices in all_possible_sets:
            total_diversity = 0
            for i in set_indices:
                for j in set_indices:
                    if j > i:  # Avoid double counting
                        total_diversity += diversity_matrix[i, j]
            diversity_scores.append(total_diversity)
        
        # Calculate frequency distribution
        unique_scores, counts = np.unique(diversity_scores, return_counts=True)
        
        print(f"Diversity scores range: {min(diversity_scores)} - {max(diversity_scores)}")
        print(f"Number of unique diversity scores: {len(unique_scores)}")
        
        return list(unique_scores), list(counts)
    
    def visualize_diversity_distribution(self, n_combinations: int, 
                                       orders: Optional[List[Tuple]] = None,
                                       save_path: Optional[str] = None):
        """
        Visualize the distribution of diversity scores for recipe sets.
        
        Args:
            n_combinations (int): Number of combinations per set
            orders (List[Tuple], optional): List of recipe combinations
            save_path (str, optional): Path to save the plot
        """
        # Calculate diversity distribution
        diversity_scores, frequencies = self.calculate_set_diversity_distribution(n_combinations, orders)
        
        # Create the visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Histogram of diversity scores
        ax1.bar(diversity_scores, frequencies, alpha=0.7, color='skyblue', edgecolor='navy')
        ax1.set_xlabel('Score de Diversité')
        ax1.set_ylabel('Nombre d\'Ensembles')
        ax1.set_title(f'Distribution des Scores de Diversité\n(Ensembles de {n_combinations} recettes)')
        ax1.grid(True, alpha=0.3)
        
        # Add statistics text
        mean_diversity = np.average(diversity_scores, weights=frequencies)
        max_diversity = max(diversity_scores)
        max_frequency = max(frequencies)
        total_sets = sum(frequencies)
        
        stats_text = f'Total ensembles: {total_sets}\n'
        stats_text += f'Diversité moyenne: {mean_diversity:.1f}\n'
        stats_text += f'Diversité maximale: {max_diversity}\n'
        stats_text += f'Ensembles avec diversité max: {frequencies[diversity_scores.index(max_diversity)]}'
        
        ax1.text(0.05, 0.95, stats_text, transform=ax1.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Cumulative distribution
        cumulative_freq = np.cumsum(frequencies)
        cumulative_percent = 100 * cumulative_freq / total_sets
        
        ax2.plot(diversity_scores, cumulative_percent, marker='o', linewidth=2, markersize=4)
        ax2.set_xlabel('Score de Diversité')
        ax2.set_ylabel('Pourcentage Cumulé (%)')
        ax2.set_title('Distribution Cumulative de la Diversité')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)
        
        # Add percentile lines
        for percentile in [25, 50, 75, 90]:
            idx = np.searchsorted(cumulative_percent, percentile)
            if idx < len(diversity_scores):
                ax2.axhline(y=percentile, color='red', linestyle='--', alpha=0.5)
                ax2.axvline(x=diversity_scores[idx], color='red', linestyle='--', alpha=0.5)
                ax2.text(diversity_scores[idx], percentile + 2, f'P{percentile}', 
                        ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Diversity distribution plot saved to {save_path}")
        else:
            plt.show()
        
        # Print detailed statistics
        print("\n" + "="*60)
        print("STATISTIQUES DE DISTRIBUTION DE LA DIVERSITÉ")
        print("="*60)
        print(f"Nombre total d'ensembles évalués: {total_sets:,}")
        print(f"Taille de chaque ensemble: {n_combinations} recettes")
        print(f"Score de diversité minimum: {min(diversity_scores)}")
        print(f"Score de diversité maximum: {max_diversity}")
        print(f"Score de diversité moyen: {mean_diversity:.2f}")
        print(f"Nombre d'ensembles avec la diversité maximale: {frequencies[diversity_scores.index(max_diversity)]}")
        print(f"Pourcentage d'ensembles avec la diversité maximale: {100 * frequencies[diversity_scores.index(max_diversity)] / total_sets:.2f}%")
        
        # Top 5 most common diversity scores
        sorted_indices = np.argsort(frequencies)[::-1]
        print("\nTop 5 des scores de diversité les plus fréquents:")
        for i in range(min(5, len(sorted_indices))):
            idx = sorted_indices[i]
            score = diversity_scores[idx]
            freq = frequencies[idx]
            percent = 100 * freq / total_sets
            print(f"  {i+1}. Score {score}: {freq:,} ensembles ({percent:.1f}%)")
        
        return diversity_scores, frequencies
    
    def select_most_diverse_combinations(self, n_combinations: int, 
                                       orders: Optional[List[Tuple]] = None) -> Tuple[List[Tuple], List[int]]:
        """
        Select the most diverse subset of recipe combinations.
        
        Args:
            n_combinations (int): Number of combinations to select
            orders (List[Tuple], optional): List of recipe combinations. 
                                          Uses self.selected_orders if None.
            
        Returns:
            Tuple[List[Tuple], List[int]]: Selected recipe combinations and their indices
        """
        if orders is None:
            orders = self.selected_orders
        
        if not orders:
            raise ValueError("No orders available. Run filter_by_value() first.")
        
        if n_combinations > len(orders):
            raise ValueError(f"Cannot select {n_combinations} combinations from {len(orders)} available")
        
        print(f"Selecting {n_combinations} most diverse combinations from {len(orders)} available...")
        
        # Calculate diversity matrix
        diversity_matrix = self.calculate_diversity_matrix(orders)
        
        # Generate all possible combinations of n_combinations
        all_possible_combinations = list(combinations(range(len(orders)), n_combinations))
        print(f"Evaluating {len(all_possible_combinations)} possible combinations...")
        
        # Calculate total diversity for each combination
        all_combinations_diversity = []
        for comb in all_possible_combinations:
            total_diversity = 0
            for i in comb:
                for j in comb:
                    if j > i:  # Avoid double counting
                        total_diversity += diversity_matrix[i, j]
            all_combinations_diversity.append(total_diversity)
        
        # Find the combination with maximum diversity
        max_diversity = max(all_combinations_diversity)
        max_indices = np.where(np.array(all_combinations_diversity) == max_diversity)[0]
        
        # Select the middle one if multiple combinations have the same max diversity
        selected_index = max_indices[len(max_indices) // 2]
        selected_combination_indices = list(all_possible_combinations)[selected_index]
        
        print(f"Maximum diversity score: {max_diversity}")
        print(f"Selected combination indices: {selected_combination_indices}")
        
        # Extract selected recipes
        selected_recipes = [orders[index] for index in selected_combination_indices]
        
        return selected_recipes, list(selected_combination_indices)
    
    def select_most_diverse_any_score(self, n_combinations: int) -> Tuple[List[Tuple], List[int]]:
        """
        Select the most diverse subset of recipe combinations regardless of score.
        
        This method considers ALL possible combinations and selects the most diverse ones
        without filtering by target value first.
        
        Args:
            n_combinations (int): Number of combinations to select
            
        Returns:
            Tuple[List[Tuple], List[int]]: Selected recipe combinations and their indices
        """
        if not self.combinations:
            raise ValueError("No combinations available. Run generate_combinations() first.")
        
        # Get all combinations regardless of score
        all_orders = list(self.combinations.keys())
        
        print(f"Selecting {n_combinations} most diverse combinations from all {len(all_orders)} available combinations (any score)...")
        
        # Calculate diversity matrix for all combinations
        diversity_matrix = self.calculate_diversity_matrix(all_orders)
        
        # Generate all possible combinations of n_combinations
        all_possible_combinations = list(combinations(range(len(all_orders)), n_combinations))
        print(f"Evaluating {len(all_possible_combinations)} possible combinations...")
        
        # Calculate total diversity for each combination
        all_combinations_diversity = []
        for comb in all_possible_combinations:
            total_diversity = 0
            for i in comb:
                for j in comb:
                    if j > i:  # Avoid double counting
                        total_diversity += diversity_matrix[i, j]
            all_combinations_diversity.append(total_diversity)
        
        # Find the combination with maximum diversity
        max_diversity = max(all_combinations_diversity)
        max_indices = np.where(np.array(all_combinations_diversity) == max_diversity)[0]
        
        # Select the middle one if multiple combinations have the same max diversity
        selected_index = max_indices[len(max_indices) // 2]
        selected_combination_indices = list(all_possible_combinations)[selected_index]
        
        print(f"Maximum diversity score: {max_diversity}")
        print(f"Selected combination indices: {selected_combination_indices}")
        
        # Extract selected recipes
        selected_recipes = [all_orders[index] for index in selected_combination_indices]
        
        # Print the scores of selected combinations
        print("Selected combinations with their scores:")
        for i, recipe_combo in enumerate(selected_recipes):
            score = self.combinations[recipe_combo]
            print(f"  Combination {i+1}: score = {score}")
        
        return selected_recipes, list(selected_combination_indices)
    
    def format_recipes_for_export(self, selected_recipes: List[Tuple]) -> List[List[Dict[str, List[str]]]]:
        """
        Format selected recipes for export in a standardized format.
        
        Args:
            selected_recipes (List[Tuple]): Selected recipe combinations
            
        Returns:
            List[List[Dict[str, List[str]]]]: Formatted recipes ready for export
        """
        formatted_recipes = []
        
        for order in selected_recipes:
            formatted_order = [{"ingredients": list(ingredients)} for ingredients in order]
            formatted_recipes.append(formatted_order)
        
        return formatted_recipes
    
    def export_to_json(self, selected_recipes: List[Tuple], output_path: str):
        """
        Export selected recipes to a JSON file.
        
        Args:
            selected_recipes (List[Tuple]): Selected recipe combinations
            output_path (str): Path to save the JSON file
        """
        formatted_recipes = self.format_recipes_for_export(selected_recipes)
        
        export_data = {
            "metadata": {
                "onion_value": self.onion_value,
                "tomato_value": self.tomato_value,
                "onion_time": self.onion_time,
                "tomato_time": self.tomato_time,
                "total_combinations": len(selected_recipes),
                "recipes_per_combination": len(selected_recipes[0]) if selected_recipes else 0
            },
            "recipe_combinations": formatted_recipes
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Recipes exported to {output_path}")
    
    def export_ensemble_recettes(self, selected_recipes: List[Tuple], output_path: str = "ensemble_recettes.json"):
        """
        Export selected recipes to ensemble_recettes.json with unified format for layout_generator.py
        
        Args:
            selected_recipes (List[Tuple]): Selected recipe combinations
            output_path (str): Path to save the JSON file (default: ensemble_recettes.json)
        """
        self._export_unified_format(selected_recipes, output_path)
    
    def _export_unified_format(self, selected_recipes: List[Tuple], output_path: str):
        """Export recipes with unified format compatible with layout_generator.py RecipeManager."""
        # Calculate recipe statistics
        all_recipes = []
        combination_values = []
        
        for combination in selected_recipes:
            total_value = sum(sum(self.onion_value if ing == 'onion' else self.tomato_value for ing in list(recipe)) for recipe in combination)
            combination_values.append(total_value)
            
            for recipe in combination:
                if recipe not in all_recipes:
                    all_recipes.append(recipe)
        
        # Format individual recipes with their properties
        formatted_all_recipes = []
        for recipe in all_recipes:
            ingredients_list = list(recipe)
            recipe_info = {
                "ingredients": ingredients_list,
                "recipe_value": sum(self.onion_value if ing == 'onion' else self.tomato_value for ing in ingredients_list),
                "cooking_time": sum(self.onion_time if ing == 'onion' else self.tomato_time for ing in ingredients_list),
                "ingredient_count": len(ingredients_list),
                "onion_count": ingredients_list.count('onion'),
                "tomato_count": ingredients_list.count('tomato')
            }
            formatted_all_recipes.append(recipe_info)
        
        # Format recipe combinations for experiments
        formatted_combinations = []
        for i, combination in enumerate(selected_recipes):
            combination_info = {
                "combination_id": i + 1,
                "recipes": [],
                "total_value": combination_values[i],
                "total_cooking_time": sum(sum(self.onion_time if ing == 'onion' else self.tomato_time for ing in list(recipe)) for recipe in combination),
                "total_ingredients": sum(len(list(recipe)) for recipe in combination)
            }
            
            for j, recipe in enumerate(combination):
                ingredients_list = list(recipe)
                recipe_detail = {
                    "recipe_id": j + 1,
                    "ingredients": ingredients_list,
                    "recipe_value": sum(self.onion_value if ing == 'onion' else self.tomato_value for ing in ingredients_list),
                    "cooking_time": sum(self.onion_time if ing == 'onion' else self.tomato_time for ing in ingredients_list)
                }
                combination_info["recipes"].append(recipe_detail)
            
            formatted_combinations.append(combination_info)
        
        # Determine export type based on number of combinations
        export_type = "all_combinations" if len(selected_recipes) > 20 else "selected_combinations"
        
        # Create comprehensive export data with unified format
        export_data = {
            "configuration": {
                "onion_value": self.onion_value,
                "tomato_value": self.tomato_value,
                "onion_time": self.onion_time,
                "tomato_time": self.tomato_time,
                "generation_date": "2025-07-25",
                "purpose": "Layout generation for Overcooked cognitive science experiments",
                "export_type": export_type
            },
            "statistics": {
                "total_combinations_exported": len(selected_recipes),
                "recipes_per_combination": len(selected_recipes[0]) if selected_recipes else 0,
                "unique_recipes_count": len(all_recipes),
                "diversity_optimized": export_type == "selected_combinations",
                "value_range": {
                    "min": min(combination_values) if combination_values else 0,
                    "max": max(combination_values) if combination_values else 0,
                    "mean": sum(combination_values) / len(combination_values) if combination_values else 0
                }
            },
            "all_unique_recipes": formatted_all_recipes,
            "recipe_combinations": formatted_combinations,
            "layout_integration_format": {
                "recipe_list": [list(recipe) for recipe in all_recipes],
                "combination_indices": [
                    [all_recipes.index(recipe) for recipe in combination] 
                    for combination in selected_recipes
                ]
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Ensemble de recettes exporté vers {output_path}")
        print(f"- {len(selected_recipes)} combinaisons exportées")
        print(f"- {len(all_recipes)} recettes uniques")
        print(f"- Type d'export: {export_type}")
        print(f"- Valeurs: {min(combination_values)}-{max(combination_values)} (moyenne: {sum(combination_values)/len(combination_values):.1f})")
        print(f"- Format unifié compatible avec layout_generator.py")
    
    def print_selected_recipes(self, selected_recipes: List[Tuple]):
        """
        Print selected recipes in a human-readable format.
        
        Args:
            selected_recipes (List[Tuple]): Selected recipe combinations
        """
        print(f"\nSelected {len(selected_recipes)} most diverse recipe combinations:")
        print("=" * 60)
        
        for i, order in enumerate(selected_recipes, 1):
            print(f"\nCombination {i}:")
            formatted_order = [{"ingredients": list(ingredients)} for ingredients in order]
            for j, recipe in enumerate(formatted_order, 1):
                print(f"  Recipe {j}: {recipe}")


def main():
    """Main function to run the recipe generator with command line arguments."""
    parser = argparse.ArgumentParser(description='Generate diverse recipe combinations for Overcooked experiments')
    parser.add_argument('--combination-size', type=int, default=6,
                       help='Number of recipes per combination (default: 6)')
    parser.add_argument('--target-value', type=int, default=33,
                       help='Target total value for recipe combinations (default: 33)')
    parser.add_argument('--n-combinations', type=int, default=5,
                       help='Number of diverse combinations to select (default: 5)')
    parser.add_argument('--onion-value', type=int, default=3,
                       help='Value for onion ingredients (default: 3)')
    parser.add_argument('--tomato-value', type=int, default=2,
                       help='Value for tomato ingredients (default: 2)')
    parser.add_argument('--onion-time', type=int, default=9,
                       help='Cooking time for onion ingredients (default: 9)')
    parser.add_argument('--tomato-time', type=int, default=6,
                       help='Cooking time for tomato ingredients (default: 6)')
    parser.add_argument('--output-json', type=str, default=None,
                       help='Path to save results as JSON file')
    parser.add_argument('--any-score', action='store_true',
                       help='Select most diverse combinations regardless of score')
    parser.add_argument('--any-combinations', action='store_true',
                       help='Export all generated combinations instead of selecting diverse ones')
    parser.add_argument('--visualize', action='store_true',
                       help='Show diversity matrix visualization')
    parser.add_argument('--save-plot', type=str, default=None,
                       help='Path to save diversity matrix plot')
    parser.add_argument('--diversity-distribution', action='store_true',
                       help='Show diversity distribution analysis')
    parser.add_argument('--save-distribution-plot', type=str, default=None,
                       help='Path to save diversity distribution plot')
    
    args = parser.parse_args()
    
    try:
        # Initialize the generator
        generator = RecipeGenerator(onion_value=args.onion_value, 
                                  tomato_value=args.tomato_value,
                                  onion_time=args.onion_time,
                                  tomato_time=args.tomato_time)
        
        # Generate combinations
        generator.generate_combinations(combination_size=args.combination_size)
        
        # Print value statistics
        generator.print_value_statistics()
        
        # Handle --any-combinations option (export all combinations)
        if args.any_combinations:
            print(f"\nExporting ALL {len(generator.combinations)} generated combinations...")
            
            # Convert all combinations to the expected format
            all_combinations_list = list(generator.combinations.keys())
            
            # Print sample of combinations
            print(f"Sample of generated combinations:")
            for i, combo in enumerate(all_combinations_list[:5]):  # Show first 5
                score = generator.combinations[combo]
                print(f"  Combination {i+1}: score = {score}")
                for j, recipe in enumerate(combo):
                    print(f"    Recipe {j+1}: {list(recipe)}")
            
            if len(all_combinations_list) > 5:
                print(f"  ... and {len(all_combinations_list) - 5} more combinations")
            
            # Export all combinations
            generator.export_ensemble_recettes(all_combinations_list, "ensemble_recettes.json")
            
            if args.output_json:
                generator.export_to_json(all_combinations_list, args.output_json)
            
            print(f"\nProcess completed successfully! All {len(all_combinations_list)} combinations exported.")
            return 0
        
        # Select combinations based on method chosen (original logic)
        if args.any_score:
            # Select most diverse combinations regardless of score
            selected_recipes, selected_indices = generator.select_most_diverse_any_score(
                n_combinations=args.n_combinations
            )
            # Calculate diversity matrix for visualization if needed
            if args.visualize or args.save_plot:
                all_orders = list(generator.combinations.keys())
                diversity_matrix = generator.calculate_diversity_matrix(all_orders)
                generator.visualize_diversity_matrix(diversity_matrix, save_path=args.save_plot)
            
            # Show diversity distribution if requested
            if args.diversity_distribution or args.save_distribution_plot:
                all_orders = list(generator.combinations.keys())
                generator.visualize_diversity_distribution(
                    n_combinations=args.n_combinations,
                    orders=all_orders,
                    save_path=args.save_distribution_plot
                )
        else:
            # Filter by target value first, then select most diverse
            filtered_orders = generator.filter_by_value(target_value=args.target_value)
            
            if not filtered_orders:
                print(f"No combinations found with target value {args.target_value}")
                return
            
            # Calculate and optionally visualize diversity matrix
            diversity_matrix = generator.calculate_diversity_matrix()
            
            if args.visualize or args.save_plot:
                generator.visualize_diversity_matrix(diversity_matrix, save_path=args.save_plot)
            
            # Show diversity distribution if requested
            if args.diversity_distribution or args.save_distribution_plot:
                generator.visualize_diversity_distribution(
                    n_combinations=args.n_combinations,
                    orders=filtered_orders,
                    save_path=args.save_distribution_plot
                )
            
            # Select most diverse combinations from filtered ones
            selected_recipes, selected_indices = generator.select_most_diverse_combinations(
                n_combinations=args.n_combinations
            )
        
        # Print results
        generator.print_selected_recipes(selected_recipes)
        
        # Export to JSON if requested
        if args.output_json:
            generator.export_to_json(selected_recipes, args.output_json)
        
        # Always generate ensemble_recettes.json for layout_generator.py
        generator.export_ensemble_recettes(selected_recipes, "ensemble_recettes.json")
        
        print(f"\nProcess completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
