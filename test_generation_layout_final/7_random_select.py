#!/usr/bin/env python3
"""
Script de Sélection Aléatoire de Layouts - Overcooked Sciences Cognitives

Ce script sélectionne aléatoirement 12 layouts et leur assigne 12 recettes différentes aléatoires :
a) Sélection aléatoire de 12 layouts depuis layouts_with_objects.ndjson
b) Sélection aléatoire de 12 combinaisons de recettes différentes
c) Conversion des 2 positions X les plus utilisées en Y (basé sur positions aléatoires)
d) Sauvegarde dans le format standard avec IDs dans layouts_random/

Auteur: Assistant IA Spécialisé  
Date: Septembre 2025
Contexte: Recherche en sciences cognitives sur la coopération humain-IA
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass

# Import des utilitaires locaux
from utils import read_ndjson, write_ndjson, decompress_grid


@dataclass
class RandomLayoutAssignment:
    """Classe pour stocker une assignation aléatoire layout-recette"""
    layout_id: str
    layout_data: Dict
    recipe_combination_id: int
    recipe_combination: Dict
    random_x_positions: List[Tuple[int, int]]  # Positions X aléatoires à convertir


class RandomLayoutSelector:
    """Sélecteur aléatoire de layouts avec assignation de recettes aléatoires"""
    
    def __init__(self):
        """Initialise le sélecteur aléatoire"""
        self.layouts_data = {}
        self.recipe_combinations = []
        self.selected_assignments = []
        
        print("🎲 Sélecteur aléatoire de layouts initialisé")
    
    def load_layouts(self) -> Dict[str, Dict]:
        """Charge tous les layouts disponibles"""
        print("📁 Chargement des layouts...")
        layouts = read_ndjson("layouts_with_objects.ndjson")
        
        layouts_dict = {}
        for layout in layouts:
            layouts_dict[layout['layout_id']] = layout
        
        print(f"✅ {len(layouts_dict)} layouts disponibles")
        return layouts_dict
    
    def load_recipe_combinations(self) -> List[Dict]:
        """Charge toutes les combinaisons de recettes"""
        print("📁 Chargement des combinaisons de recettes...")
        
        with open("ensemble_recettes.json", 'r', encoding='utf-8') as f:
            recipe_data = json.load(f)
        
        combinations = recipe_data.get('recipe_combinations', [])
        print(f"✅ {len(combinations)} combinaisons de recettes disponibles")
        return combinations
    
    def find_x_positions_in_layout(self, layout_data: Dict) -> List[Tuple[int, int]]:
        """Trouve toutes les positions X dans un layout"""
        grid = decompress_grid(layout_data['grid'])
        x_positions = []
        
        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                if cell == 'X':
                    x_positions.append((row_idx, col_idx))
        
        return x_positions
    
    def select_random_assignments(self, layouts: Dict[str, Dict], 
                                recipe_combinations: List[Dict], 
                                target_count: int = 12) -> List[RandomLayoutAssignment]:
        """
        Sélectionne aléatoirement 12 layouts et 12 combinaisons de recettes différentes
        """
        print(f"🎲 Sélection aléatoire de {target_count} assignations layout-recette...")
        
        # Vérifier qu'on a assez de données
        if len(layouts) < target_count:
            print(f"❌ Pas assez de layouts ({len(layouts)} < {target_count})")
            return []
        
        if len(recipe_combinations) < target_count:
            print(f"❌ Pas assez de combinaisons de recettes ({len(recipe_combinations)} < {target_count})")
            return []
        
        # Sélectionner aléatoirement 12 layouts
        layout_ids = list(layouts.keys())
        selected_layout_ids = random.sample(layout_ids, target_count)
        
        # Sélectionner aléatoirement 12 combinaisons de recettes différentes
        selected_recipe_indices = random.sample(range(len(recipe_combinations)), target_count)
        
        assignments = []
        
        for i in range(target_count):
            layout_id = selected_layout_ids[i]
            layout_data = layouts[layout_id]
            recipe_idx = selected_recipe_indices[i]
            recipe_combination = recipe_combinations[recipe_idx]
            
            # Trouver les positions X disponibles dans ce layout
            x_positions = self.find_x_positions_in_layout(layout_data)
            
            # Sélectionner aléatoirement jusqu'à 2 positions X à convertir
            random_x_positions = []
            if x_positions:
                num_to_convert = min(2, len(x_positions))
                random_x_positions = random.sample(x_positions, num_to_convert)
            
            assignment = RandomLayoutAssignment(
                layout_id=layout_id,
                layout_data=layout_data,
                recipe_combination_id=recipe_idx,
                recipe_combination=recipe_combination,
                random_x_positions=random_x_positions
            )
            
            assignments.append(assignment)
        
        print(f"✅ {len(assignments)} assignations aléatoires créées:")
        for i, assignment in enumerate(assignments, 1):
            print(f"  {i:2d}. Layout {assignment.layout_id} + Recette {assignment.recipe_combination_id} "
                  f"({len(assignment.random_x_positions)} conversions X->Y)")
        
        return assignments
    
    def convert_layout_format(self, assignment: RandomLayoutAssignment) -> Dict:
        """
        Convertit un layout au format requis avec conversion X -> Y aléatoire.
        """
        # Décompresser la grille originale
        grid = decompress_grid(assignment.layout_data['grid'])
        
        # Convertir en liste de listes pour modification
        grid_list = [list(row) for row in grid]
        
        # Convertir les positions X sélectionnées aléatoirement en Y
        converted_positions = []
        for pos in assignment.random_x_positions:
            if pos and len(pos) == 2:
                row, col = pos
                if 0 <= row < len(grid_list) and 0 <= col < len(grid_list[0]):
                    if grid_list[row][col] == 'X':
                        grid_list[row][col] = 'Y'
                        converted_positions.append(pos)
                        print(f"  ✅ Converti X->Y en position ({row}, {col})")
        
        # Remplacer les points par des espaces pour les cases vides
        for row in grid_list:
            for j in range(len(row)):
                if row[j] == '.':
                    row[j] = ' '
        
        # Créer le format de grille avec indentation exacte
        grid_lines = []
        for row in grid_list:
            grid_lines.append(''.join(row))
        
        # Format exact avec triple quotes et indentation
        formatted_grid = '"""' + grid_lines[0] + '\n'
        for line in grid_lines[1:]:
            formatted_grid += '                ' + line + '\n'
        formatted_grid = formatted_grid.rstrip('\n') + '"""'
        
        # Utiliser les recettes de la combinaison sélectionnée pour start_all_orders
        start_all_orders = []
        for recipe in assignment.recipe_combination['recipes']:
            start_all_orders.append({"ingredients": recipe['ingredients']})
        
        # Créer le format de sortie selon le template
        output_layout = {
            "grid": formatted_grid,
            "start_all_orders": start_all_orders,
            "counter_goals": [],
            "onion_value": 3,
            "tomato_value": 2,
            "onion_time": 9,
            "tomato_time": 6
        }
        
        return output_layout
    
    def save_random_layouts(self, assignments: List[RandomLayoutAssignment]):
        """Sauvegarde les layouts sélectionnés aléatoirement dans le dossier layouts_random"""
        
        # Créer le dossier de destination
        output_dir = Path("layouts_random")
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Dossier créé: {output_dir}")
        
        print("💾 Conversion et sauvegarde des layouts aléatoires...")
        
        for i, assignment in enumerate(assignments, 1):
            # Convertir le format
            converted_layout = self.convert_layout_format(assignment)
            
            # Générer le nom de fichier selon l'ID du layout et de la recette
            # Format: Ld{layout_suffix}_R{recipe_id}_V00.layout
            layout_suffix = assignment.layout_id.split('_')[-2] if '_' in assignment.layout_id else assignment.layout_id[-8:]
            filename = f"Ld{layout_suffix}_R{assignment.recipe_combination_id:02d}_V00.layout"
            
            # Sauvegarder avec le format JSON exact
            output_path = output_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                # Format manuel pour correspondre exactement au template
                f.write("{\n")
                f.write(f'    "grid":  {converted_layout["grid"]},\n')
                f.write('    "start_all_orders": ')
                f.write(json.dumps(converted_layout["start_all_orders"], separators=(',', ': ')))
                f.write(',\n')
                f.write('    "counter_goals":')
                f.write(json.dumps(converted_layout["counter_goals"]))
                f.write(',\n')
                f.write(f'    "onion_value" : {converted_layout["onion_value"]},\n')
                f.write(f'    "tomato_value" : {converted_layout["tomato_value"]},\n')
                f.write(f'    "onion_time" : {converted_layout["onion_time"]},\n')
                f.write(f'    "tomato_time" : {converted_layout["tomato_time"]}\n')
                f.write("}")
            
            num_recipes = len(assignment.recipe_combination['recipes'])
            print(f"  {i:2d}. {filename}: recette {assignment.recipe_combination_id} "
                  f"({num_recipes} ordres), {len(assignment.random_x_positions)} conversions X->Y")
        
        print(f"✅ {len(assignments)} layouts aléatoires sauvegardés dans {output_dir}")
        
        # Statistiques finales
        recipe_ids = [assignment.recipe_combination_id for assignment in assignments]
        layout_ids = [assignment.layout_id for assignment in assignments]
        
        print(f"📋 Recettes utilisées ({len(set(recipe_ids))} uniques sur {len(recipe_ids)} total): {sorted(set(recipe_ids))}")
        print(f"📋 Layouts utilisés ({len(set(layout_ids))} uniques sur {len(layout_ids)} total): {len(set(layout_ids))} layouts différents")
        
        # Vérification de l'unicité des recettes
        if len(set(recipe_ids)) == len(recipe_ids):
            print(f"🎯 SUCCÈS: Toutes les recettes sont différentes ({len(set(recipe_ids))} uniques)")
        else:
            print(f"⚠️ INFO: Quelques recettes peuvent être dupliquées")
    
    def run_random_selection(self):
        """Exécute le processus complet de sélection aléatoire"""
        print("\n🎲 DÉMARRAGE DE LA SÉLECTION ALÉATOIRE DE LAYOUTS")
        print("="*60)
        
        # Initialiser le générateur aléatoire avec une graine pour la reproductibilité
        # (optionnel: vous pouvez commenter cette ligne pour avoir une vraie randomisation)
        random.seed(42)
        print("🎲 Graine aléatoire fixée à 42 pour la reproductibilité")
        
        # Charger toutes les données
        layouts = self.load_layouts()
        recipe_combinations = self.load_recipe_combinations()
        
        if not layouts:
            print("❌ Aucun layout trouvé")
            return
        
        if not recipe_combinations:
            print("❌ Aucune combinaison de recettes trouvée")
            return
        
        # Effectuer la sélection aléatoire
        assignments = self.select_random_assignments(layouts, recipe_combinations, target_count=12)
        
        if not assignments:
            print("❌ Aucune assignation créée")
            return
        
        # Sauvegarder
        self.save_random_layouts(assignments)
        
        print(f"\n✅ SÉLECTION ALÉATOIRE TERMINÉE!")
        print(f"📊 {len(assignments)} layouts aléatoires sélectionnés et convertis")
        print(f"📁 Fichiers disponibles dans: layouts_random/")


def main():
    """Fonction principale"""
    print("🎲 SÉLECTEUR ALÉATOIRE DE LAYOUTS - OVERCOOKED")
    print("Sélection aléatoire de 12 layouts avec 12 recettes différentes")
    print("Conversion aléatoire de positions X->Y")
    print()
    
    # Créer et exécuter le sélecteur aléatoire
    selector = RandomLayoutSelector()
    selector.run_random_selection()


if __name__ == "__main__":
    main()