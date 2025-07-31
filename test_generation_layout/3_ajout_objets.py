import os
import json
import random
import itertools
from pathlib import Path
import shutil

# Paramètres configurables
INPUT_DIR = "test_generation_layout/layouts_split"
OUTPUT_BASE_DIR = "test_generation_layout/layouts_with_objects"
DISTANCE_OBJETS = 16  # Distance totale souhaitée entre tous les objets
NUM_VARIATIONS = 10   # Nombre de variations par layout
OBJECTS = ['1', '2', 'O', 'T', 'S', 'D']  # Objets à placer

def parse_grid_from_layout(layout_content):
    """Extrait la grille du contenu du fichier .layout"""
    lines = layout_content.split('\n')
    grid_lines = []
    in_grid = False
    
    for line in lines:
        if '"""' in line and 'grid' in line:
            # Début de la grille
            in_grid = True
            # Vérifier s'il y a du contenu après les premières triple quotes
            after_quotes = line.split('"""')[1] if line.count('"""') >= 1 else ""
            if after_quotes.strip():
                grid_lines.append(list(after_quotes))
            continue
        elif in_grid:
            if '"""' in line:
                # Vérifier s'il y a du contenu avant les triple quotes de fermeture
                before_quotes = line.split('"""')[0] if '"""' in line else line
                if before_quotes.strip():
                    grid_lines.append(list(before_quotes.lstrip()))
                # Fin de la grille
                break
            # Nettoyer la ligne (supprimer l'indentation mais garder les espaces de la grille)
            cleaned_line = line.lstrip()
            if cleaned_line:
                grid_lines.append(list(cleaned_line))
    
    return grid_lines

def calculate_manhattan_distance(pos1, pos2):
    """Calcule la distance de Manhattan entre deux positions"""
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def calculate_total_path_distance(positions):
    """
    Calcule la distance totale pour visiter tous les points.
    Utilise une approximation du plus court chemin (TSP simplifié)
    """
    if len(positions) <= 1:
        return 0
    
    # Pour 5 objets, on peut calculer toutes les permutations
    min_distance = float('inf')
    for perm in itertools.permutations(positions):
        total_dist = 0
        for i in range(len(perm) - 1):
            total_dist += calculate_manhattan_distance(perm[i], perm[i + 1])
        min_distance = min(min_distance, total_dist)
    
    return min_distance

def find_valid_x_positions(grid):
    """Trouve toutes les positions contenant 'X' dans la grille"""
    positions = []
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == 'X':
                positions.append((i, j))
    return positions

def find_empty_positions(grid):
    """Trouve toutes les positions contenant un espace vide dans la grille"""
    positions = []
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == ' ':
                positions.append((i, j))
    return positions

def is_edge_position(pos, grid):
    """Vérifie si une position est sur une extrémité de la grille"""
    i, j = pos
    max_i = len(grid) - 1
    max_j = len(grid[0]) - 1 if grid else 0
    
    # Une position est sur une extrémité si elle est sur le bord de la grille
    return i == 0 or i == max_i or j == 0 or j == max_j

def get_valid_positions_for_object(grid, obj):
    """Retourne les positions valides pour un objet donné avec toutes les contraintes"""
    if obj in ['1', '2']:
        # Les 1 et 2 doivent être placés sur d'anciennes cases vides (pas sur des X)
        candidate_positions = find_empty_positions(grid)
    else:
        candidate_positions = find_valid_x_positions(grid)

    # Filtrer les positions selon toutes les contraintes
    valid_positions = []
    for pos in candidate_positions:
        if is_position_valid_for_placement(pos, grid, obj):
            valid_positions.append(pos)
    return valid_positions

def has_adjacent_empty_space(pos, grid):
    """Vérifie si une position a au moins une case vide adjacente (pas bloquée)"""
    i, j = pos
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # haut, bas, gauche, droite
    
    for di, dj in directions:
        ni, nj = i + di, j + dj
        # Vérifier que la position adjacente est dans les limites
        if 0 <= ni < len(grid) and 0 <= nj < len(grid[0]):
            # Vérifier si c'est un espace vide (espace ou autre case libre)
            if grid[ni][nj] == ' ':
                return True
    
    return False

def is_position_valid_for_placement(pos, grid, obj):
    """Vérifie si une position est valide pour placer un objet donné"""
    # Vérification 1: L'objet ne doit pas être sur une extrémité si c'est '1' ou '2'
    if obj in ['1', '2'] and is_edge_position(pos, grid):
        return False
    
    # Vérification 2: L'objet ne doit pas être bloqué (doit avoir au moins un espace vide adjacent)
    if not has_adjacent_empty_space(pos, grid):
        return False
    
    return True

def place_objects_with_distance_constraint(grid, target_distance, max_attempts=1000):
    """
    Place les objets de manière à respecter la contrainte de distance.
    Les objets '1' et '2' ne peuvent pas être placés sur les extrémités.
    Retourne une nouvelle grille avec les objets placés.
    """
    # Vérifier qu'il y a assez de positions pour chaque type d'objet
    all_x_positions = find_valid_x_positions(grid)
    positions_for_1_2 = [pos for pos in all_x_positions if not is_edge_position(pos, grid)]
    
    if len(positions_for_1_2) < 2:  # Besoin d'au moins 2 positions intérieures pour '1' et '2'
        print(f"Pas assez de positions intérieures pour '1' et '2'. Disponible: {len(positions_for_1_2)}")
        return None
    
    if len(all_x_positions) < len(OBJECTS):
        print(f"Pas assez de positions X disponibles. Besoin: {len(OBJECTS)}, Disponible: {len(all_x_positions)}")
        return None
    
    best_grid = None
    best_distance_diff = float('inf')
    
    for attempt in range(max_attempts):
        # Copier la grille originale
        new_grid = [row[:] for row in grid]
        selected_positions = []
        
        # Placer les objets avec leurs contraintes
        for obj in OBJECTS:
            valid_positions = get_valid_positions_for_object(grid, obj)
            # Exclure les positions déjà occupées
            available_positions = [pos for pos in valid_positions if pos not in selected_positions]
            
            if not available_positions:
                # Pas de position disponible pour cet objet, essayer une autre combinaison
                break
            
            # Sélectionner une position aléatoire parmi les positions disponibles
            selected_pos = random.choice(available_positions)
            selected_positions.append(selected_pos)
        
        # Vérifier que tous les objets ont été placés
        if len(selected_positions) != len(OBJECTS):
            continue
        
        # Calculer la distance totale
        total_distance = calculate_total_path_distance(selected_positions)
        distance_diff = abs(total_distance - target_distance)
        
        # Si c'est exactement la distance souhaitée, on l'utilise
        if total_distance == target_distance:
            for pos, obj in zip(selected_positions, OBJECTS):
                new_grid[pos[0]][pos[1]] = obj
            return new_grid
        
        # Sinon, garder la meilleure approximation
        if distance_diff < best_distance_diff:
            best_distance_diff = distance_diff
            best_grid = [row[:] for row in new_grid]
            for pos, obj in zip(selected_positions, OBJECTS):
                best_grid[pos[0]][pos[1]] = obj
    
    if best_grid is not None:
        actual_distance = target_distance - best_distance_diff if best_distance_diff <= target_distance else target_distance + best_distance_diff
        print(f"Meilleure approximation trouvée: distance = {actual_distance} (cible: {target_distance})")
    
    return best_grid

def grid_to_string(grid):
    """Convertit une grille en chaîne de caractères pour le format .layout"""
    grid_lines = [''.join(row) for row in grid]
    return '\n                '.join(grid_lines)

def create_layout_file(original_content, new_grid, output_path):
    """Crée un nouveau fichier .layout avec la grille modifiée"""
    lines = original_content.split('\n')
    new_lines = []
    in_grid = False
    
    for line in lines:
        if '"""' in line and 'grid' in line:
            # Remplacer la grille
            new_lines.append(f'    "grid":  """{grid_to_string(new_grid)}""",')
            in_grid = True
            # Ignorer les lignes jusqu'à la fermeture des triple quotes
        elif in_grid and '"""' in line:
            in_grid = False
            continue
        elif in_grid:
            continue
        else:
            new_lines.append(line)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(new_lines))

def process_layouts():
    """Traite tous les layouts dans le dossier d'entrée"""
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_BASE_DIR)
    
    # Créer le dossier de sortie s'il n'existe pas
    output_path.mkdir(exist_ok=True)
    
    # Parcourir tous les dossiers de lots (recette_lot_1, recette_lot_2, etc.)
    lot_dirs = sorted([d for d in input_path.iterdir() if d.is_dir() and d.name.startswith('recette_lot_')])
    
    for lot_dir in lot_dirs:
        print(f"Traitement du dossier: {lot_dir.name}")
        
        # Créer le dossier de sortie pour ce lot de recettes
        output_lot_dir = output_path / lot_dir.name
        output_lot_dir.mkdir(exist_ok=True)
        
        # Parcourir tous les fichiers .layout dans ce dossier
        layout_files = sorted(lot_dir.glob("*.layout"))
        
        for layout_file in layout_files:
            print(f"  Traitement du layout: {layout_file.name}")
            
            # Lire le contenu du fichier
            with open(layout_file, 'r') as f:
                original_content = f.read()
            
            # Extraire la grille
            grid = parse_grid_from_layout(original_content)
            if not grid:
                print(f"    Impossible d'extraire la grille de {layout_file.name}")
                continue
            
            # Créer le dossier de sortie pour ce layout dans le lot correspondant
            layout_name = layout_file.stem  # nom sans extension
            output_layout_dir = output_lot_dir / layout_name
            output_layout_dir.mkdir(exist_ok=True)
            
            # Générer les variations
            successful_variations = 0
            attempts = 0
            max_total_attempts = NUM_VARIATIONS * 20  # Plus d'essais à cause des contraintes
            
            while successful_variations < NUM_VARIATIONS and attempts < max_total_attempts:
                attempts += 1
                
                # Placer les objets avec la contrainte de distance
                new_grid = place_objects_with_distance_constraint(grid, DISTANCE_OBJETS)
                
                if new_grid is not None:
                    successful_variations += 1
                    variation_name = f"V{successful_variations}_{layout_name}.layout"
                    output_file = output_layout_dir / variation_name
                    
                    # Créer le fichier de layout modifié
                    create_layout_file(original_content, new_grid, output_file)
                    print(f"    Créé: {variation_name}")
            
            if successful_variations < NUM_VARIATIONS:
                print(f"    Attention: seulement {successful_variations}/{NUM_VARIATIONS} variations créées pour {layout_file.name}")
    
    print(f"\nStructure créée dans '{OUTPUT_BASE_DIR}':")
    print("├── recette_lot_1/")
    print("│   ├── layout_combination_01/")
    print("│   │   ├── V1_layout_combination_01.layout")
    print("│   │   ├── V2_layout_combination_01.layout")
    print("│   │   └── ... (jusqu'à V10)")
    print("│   ├── layout_combination_02/")
    print("│   │   └── ...")
    print("│   └── ...")
    print("├── recette_lot_2/")
    print("│   └── ...")
    print("└── ...")

def main():
    """Fonction principale"""
    print(f"Démarrage du traitement des layouts...")
    print(f"Distance cible entre objets: {DISTANCE_OBJETS}")
    print(f"Nombre de variations par layout: {NUM_VARIATIONS}")
    print(f"Objets à placer: {OBJECTS}")
    print("-" * 50)
    
    process_layouts()
    
    print("-" * 50)
    print("Traitement terminé!")

if __name__ == "__main__":
    main()
