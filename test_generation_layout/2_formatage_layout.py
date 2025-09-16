import os
import json
from pathlib import Path

# Paramètres
INPUT_FILE = "test_generation_layout/raw_layouts/layouts_45.json"  # fichier contenant les layouts en JSON
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

# Génération : créer 84 versions de chaque layout avec chacune une combinaison de recettes différente
total_combinations = len(recipe_combinations)
num_layouts = len(layouts)
files_created = 0
files_skipped = 0

for layout_idx, layout_entry in enumerate(layouts):
    # Créer un dossier pour ce layout spécifique
    layout_dir = Path(OUTPUT_BASE_DIR) / f"layout_{layout_idx + 1}"
    os.makedirs(layout_dir, exist_ok=True)
    
    # Préparer les éléments communs du layout
    grid_list = layout_entry['layout']
    grid_lines = [''.join(row).replace('.', ' ') for row in grid_list]
    grid_indented = '\n                '.join(grid_lines)
    
    # Créer 84 versions de ce layout, une pour chaque combinaison de recettes
    for combination_index, current_combination in enumerate(recipe_combinations):
        combination_id = current_combination['combination_id']
        
        # Vérifier si le fichier existe déjà
        out_path = layout_dir / f"layout_{layout_idx + 1}_R_{combination_id:02d}.layout"
        if out_path.exists():
            files_skipped += 1
            print(f"Fichier déjà existant ignoré: {out_path}")
            continue
        
        raw_recipes = current_combination['recipes']

        # Reformater les recettes au format attendu (liste de dicts avec seulement "ingredients")
        formatted_recipes = [
            {"ingredients": recipe["ingredients"]} if isinstance(recipe, dict) and "ingredients" in recipe else recipe
            for recipe in raw_recipes
        ]

        # Construction du contenu du fichier .layout avec le format spécial pour grid
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
        
        files_created += 1
        print(f"Fichier créé: {out_path}")

print(f"Traitement terminé :")
print(f"- Fichiers créés : {files_created}")
print(f"- Fichiers ignorés (déjà existants) : {files_skipped}")
print(f"- Total de fichiers attendus : {num_layouts * total_combinations}")
print(f"Organisation : {num_layouts} dossiers (layout_1 à layout_{num_layouts}), chacun contenant jusqu'à {total_combinations} fichiers .layout")