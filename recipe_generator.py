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
    
    def __init__(self, onion_value: int = 1, tomato_value: int = 1):
        """
        Initialize the RecipeGenerator with ingredient values.
        
        Args:
            onion_value (int): Value assigned to onion ingredients
            tomato_value (int): Value assigned to tomato ingredients
        """
        if Recipe is None:
            raise ImportError("overcooked_ai_py module is required but not found")
            
        self.onion_value = onion_value
        self.tomato_value = tomato_value
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
                "total_combinations": len(selected_recipes),
                "recipes_per_combination": len(selected_recipes[0]) if selected_recipes else 0
            },
            "recipe_combinations": formatted_recipes
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Recipes exported to {output_path}")
    
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
    parser.add_argument('--target-value', type=int, default=14,
                       help='Target total value for recipe combinations (default: 14)')
    parser.add_argument('--n-combinations', type=int, default=5,
                       help='Number of diverse combinations to select (default: 5)')
    parser.add_argument('--onion-value', type=int, default=1,
                       help='Value for onion ingredients (default: 1)')
    parser.add_argument('--tomato-value', type=int, default=1,
                       help='Value for tomato ingredients (default: 1)')
    parser.add_argument('--output-json', type=str, default=None,
                       help='Path to save results as JSON file')
    parser.add_argument('--visualize', action='store_true',
                       help='Show diversity matrix visualization')
    parser.add_argument('--save-plot', type=str, default=None,
                       help='Path to save diversity matrix plot')
    
    args = parser.parse_args()
    
    try:
        # Initialize the generator
        generator = RecipeGenerator(onion_value=args.onion_value, 
                                  tomato_value=args.tomato_value)
        
        # Generate combinations
        generator.generate_combinations(combination_size=args.combination_size)
        
        # Print value statistics
        generator.print_value_statistics()
        
        # Filter by target value
        filtered_orders = generator.filter_by_value(target_value=args.target_value)
        
        if not filtered_orders:
            print(f"No combinations found with target value {args.target_value}")
            return
        
        # Calculate and optionally visualize diversity matrix
        diversity_matrix = generator.calculate_diversity_matrix()
        
        if args.visualize or args.save_plot:
            generator.visualize_diversity_matrix(diversity_matrix, save_path=args.save_plot)
        
        # Select most diverse combinations
        selected_recipes, selected_indices = generator.select_most_diverse_combinations(
            n_combinations=args.n_combinations
        )
        
        # Print results
        generator.print_selected_recipes(selected_recipes)
        
        # Export to JSON if requested
        if args.output_json:
            generator.export_to_json(selected_recipes, args.output_json)
        
        print(f"\nProcess completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
