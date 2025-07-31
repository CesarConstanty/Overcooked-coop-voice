import os
import json
from pathlib import Path

# Paramètres
INPUT_FILE = "test_generation_layout/raw_layouts/layouts_18.json"  # fichier contenant les layouts en JSON
OUTPUT_BASE_DIR = "test_generation_layout/layouts_split"
RECIPE_SOURCE_FILE = "ensemble_recettes.json"



# Chargement des recettes (84 combinaisons)
with open(RECIPE_SOURCE_FILE, 'r') as f:
    data = json.load(f)
    recipe_combinations = data['recipe_combinations']
    onion_value = data['configuration']['onion_value']
    tomato_value = data['configuration']['tomato_value']
    onion_time = data['configuration']['onion_time']
    tomato_time = data['configuration']['tomato_time']

# Lecture des layouts
with open(INPUT_FILE, 'r') as infile:
    layouts = [json.loads(line) for line in infile]

# Génération : chaque lot contient autant de layouts que de combinaisons de recettes (84)
total_combinations = len(recipe_combinations)
num_layouts = len(layouts)

for idx, layout_entry in enumerate(layouts):
    # Calculer le numéro de lot et l'index de la combinaison dans ce lot
    lot_id = idx // total_combinations + 1
    combination_index = idx % total_combinations
    
    # Récupérer la combinaison de recettes correspondante
    current_combination = recipe_combinations[combination_index]
    combination_id = current_combination['combination_id']
    raw_recipes = current_combination['recipes']

    # Reformater les recettes au format attendu (liste de dicts avec seulement "ingredients")
    formatted_recipes = [
        {"ingredients": recipe["ingredients"]} if isinstance(recipe, dict) and "ingredients" in recipe else recipe
        for recipe in raw_recipes
    ]

    lot_dir = Path(OUTPUT_BASE_DIR) / f"recette_lot_{lot_id}"
    os.makedirs(lot_dir, exist_ok=True)

    grid_list = layout_entry['layout']
    grid_lines = [''.join(row).replace('.', ' ') for row in grid_list]

    # Construction du contenu du fichier .layout avec le format spécial pour grid
    grid_indented = '\n                '.join(grid_lines)
    
    out_path = lot_dir / f"layout_combination_{combination_id:02d}.layout"
    with open(out_path, 'w') as out_file:
        out_file.write("{\n")
        out_file.write(f'    "grid":  """{grid_indented}""",\n')
        out_file.write(f'    "start_all_orders": {json.dumps(formatted_recipes, separators=(",", ": "))},\n')
        out_file.write('    "counter_goals":[],\n')
        out_file.write(f'    "onion_value" : {onion_value},\n')
        out_file.write(f'    "tomato_value" : {tomato_value},\n')
        out_file.write(f'    "onion_time" : {onion_time},\n')
        out_file.write(f'    "tomato_time" : {tomato_time}\n')
        out_file.write("}")

print(f"Layouts exportés : {num_layouts} fichiers répartis dans {(num_layouts - 1) // total_combinations + 1} dossiers.")
print(f"Chaque lot contient {total_combinations} layouts avec des combinaisons de recettes différentes (combination_id 1-{total_combinations}).")