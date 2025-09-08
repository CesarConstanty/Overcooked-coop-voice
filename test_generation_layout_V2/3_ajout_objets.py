import os
import random
import itertools
from pathlib import Path
import multiprocessing
from multiprocessing import Pool, cpu_count
import time

# Paramètres configurables
INPUT_DIR = "test_generation_layout/layouts_split"
OUTPUT_BASE_DIR = "test_generation_layout/layouts_with_objects"
DISTANCE_OBJETS = 16  # Distance totale souhaitée entre tous les objets 7*7 : 16 ; 8*8 : 24
NUM_VARIATIONS = 10   # Nombre de variations par layout
OBJECTS = ['1', '2', 'O', 'T', 'S', 'D', 'P']  # Objets à placer
MAX_PROCESSES = None  # Nombre max de processus (None = auto-détection)
MAX_LAYOUTS = None    # Limite le nombre de layouts à traiter (None = tous)
random.seed("07082025")

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
    
    # Vérification 2: L'objet 'S' doit obligatoirement être sur une extrémité
    if obj == 'S' and not is_edge_position(pos, grid):
        return False
    
    # Vérification 3: L'objet ne doit pas être bloqué (doit avoir au moins un espace vide adjacent)
    if not has_adjacent_empty_space(pos, grid):
        return False
    
    return True

def place_objects_with_distance_constraint(grid, target_distance, max_attempts=1000):
    """
    Place les objets de manière à respecter la contrainte de distance.
    Les objets '1' et '2' ne peuvent pas être placés sur les extrémités.
    L'objet 'S' doit obligatoirement être placé sur une extrémité.
    Retourne une nouvelle grille avec les objets placés.
    """
    # Vérifier qu'il y a assez de positions pour chaque type d'objet
    all_x_positions = find_valid_x_positions(grid)
    positions_for_1_2 = [pos for pos in all_x_positions if not is_edge_position(pos, grid)]
    edge_positions = [pos for pos in all_x_positions if is_edge_position(pos, grid)]
    
    if len(positions_for_1_2) < 2:  # Besoin d'au moins 2 positions intérieures pour '1' et '2'
        print(f"Pas assez de positions intérieures pour '1' et '2'. Disponible: {len(positions_for_1_2)}")
        return None
    
    if len(edge_positions) < 1:  # Besoin d'au moins 1 position d'extrémité pour 'S'
        print(f"Pas assez de positions d'extrémité pour 'S'. Disponible: {len(edge_positions)}")
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

def check_existing_variations(layout_file, output_base_path):
    """Vérifie quelles variations existent déjà pour un layout donné"""
    # Extraire les informations du nom de fichier
    filename_parts = layout_file.stem.split('_')
    if len(filename_parts) < 4:
        return []
    
    layout_num = filename_parts[1]  # X
    recipe_id = filename_parts[3]   # YY
    
    # Créer le dossier de sortie pour ce fichier layout spécifique
    layout_name = layout_file.stem
    output_layout_dir = output_base_path / layout_name
    
    if not output_layout_dir.exists():
        return []
    
    # Vérifier quelles variations existent déjà
    existing_variations = []
    for variation_num in range(1, NUM_VARIATIONS + 1):
        variation_name = f"L{layout_num}_R{recipe_id}_V{variation_num:02d}.layout"
        variation_file = output_layout_dir / variation_name
        if variation_file.exists():
            existing_variations.append(variation_num)
    
    return existing_variations

def generate_single_variation(args):
    """Génère une seule variation pour un layout donné (fonction pour multiprocessing)"""
    layout_file, output_base_path, variation_num = args
    
    # Extraire les informations du nom de fichier
    filename_parts = layout_file.stem.split('_')
    if len(filename_parts) >= 4:
        layout_num = filename_parts[1]  # X
        recipe_id = filename_parts[3]   # YY
    else:
        return f"Format de nom de fichier non reconnu: {layout_file.name}", False
    
    # Créer le dossier de sortie pour ce fichier layout spécifique
    layout_name = layout_file.stem
    output_layout_dir = output_base_path / layout_name
    output_layout_dir.mkdir(exist_ok=True)
    
    # Vérifier si cette variation existe déjà
    variation_name = f"L{layout_num}_R{recipe_id}_V{variation_num:02d}.layout"
    output_file = output_layout_dir / variation_name
    
    if output_file.exists():
        return f"Existe déjà: {variation_name} (PID: {os.getpid()})", True
    
    # Seed unique pour chaque processus
    random.seed(int(time.time() * 1000000) % 2**32 + variation_num + os.getpid())
    
    try:
        # Lire le contenu du fichier
        with open(layout_file, 'r') as f:
            original_content = f.read()
        
        # Extraire la grille
        grid = parse_grid_from_layout(original_content)
        if not grid:
            return f"Impossible d'extraire la grille de {layout_file.name}", False
        
        # Générer une variation
        max_attempts = 1000
        new_grid = place_objects_with_distance_constraint(grid, DISTANCE_OBJETS, max_attempts)
        
        if new_grid is not None:
            # Créer le fichier de layout modifié immédiatement
            create_layout_file(original_content, new_grid, output_file)
            return f"Créé: {variation_name} (PID: {os.getpid()})", True
        else:
            return f"Échec génération variation {variation_num} pour {layout_file.name}", False
            
    except Exception as e:
        return f"Erreur lors du traitement de {layout_file.name}, variation {variation_num}: {e}", False

def process_layouts():
    """Traite tous les layouts dans le dossier d'entrée en parallèle"""
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_BASE_DIR)
    
    # Créer le dossier de sortie s'il n'existe pas
    output_path.mkdir(exist_ok=True)
    
    # Parcourir tous les dossiers de layouts (layout_1, layout_2, etc.)
    layout_dirs = sorted([d for d in input_path.iterdir() if d.is_dir() and d.name.startswith('layout_')])
    
    # Collecter toutes les tâches de variation à traiter (seulement celles manquantes)
    all_variation_tasks = []
    total_existing = 0
    total_to_generate = 0
    
    for layout_dir in layout_dirs:
        print(f"Scan du dossier: {layout_dir.name}")
        layout_files = sorted(layout_dir.glob("*.layout"))
        
        # Appliquer la limite si spécifiée
        if MAX_LAYOUTS is not None:
            layout_files = layout_files[:MAX_LAYOUTS]
        
        for layout_file in layout_files:
            # Vérifier quelles variations existent déjà
            existing_variations = check_existing_variations(layout_file, output_path)
            total_existing += len(existing_variations)
            
            # Créer des tâches uniquement pour les variations manquantes
            for variation_num in range(1, NUM_VARIATIONS + 1):
                if variation_num not in existing_variations:
                    all_variation_tasks.append((layout_file, output_path, variation_num))
                    total_to_generate += 1
            
            # Afficher le statut pour ce layout
            if existing_variations:
                missing_count = NUM_VARIATIONS - len(existing_variations)
                if missing_count == 0:
                    print(f"  {layout_file.name}: ✓ Complet ({NUM_VARIATIONS}/{NUM_VARIATIONS} variations)")
                else:
                    print(f"  {layout_file.name}: ⚠ Partiel ({len(existing_variations)}/{NUM_VARIATIONS} variations, {missing_count} manquantes)")
            else:
                print(f"  {layout_file.name}: ○ Nouveau ({NUM_VARIATIONS} variations à créer)")
    
    print(f"\n=== ÉTAT DU TRAITEMENT ===")
    print(f"- Variations déjà existantes: {total_existing}")
    print(f"- Variations à générer: {total_to_generate}")
    print(f"- Total final attendu: {total_existing + total_to_generate}")
    
    if not all_variation_tasks:
        print("\n🎉 Toutes les variations sont déjà générées !")
        print("Aucun traitement nécessaire.")
        return
    
    print(f"\nTrouvé {len(all_variation_tasks)} tâches de variation à traiter")
    num_processes = min(len(all_variation_tasks), MAX_PROCESSES or cpu_count())
    print(f"Utilisation de {num_processes} processus")
    print("-" * 50)
    
    start_time = time.time()
    
    # Traiter toutes les variations manquantes en parallèle
    with Pool(processes=num_processes) as pool:
        results = pool.map(generate_single_variation, all_variation_tasks)
    
    end_time = time.time()
    
    # Analyser les résultats
    successful_variations = 0
    failed_variations = 0
    skipped_variations = 0
    
    for message, success in results:
        if success:
            if "Existe déjà" in message:
                skipped_variations += 1
                print(f"  ⏭ {message}")
            else:
                successful_variations += 1
                print(f"  ✓ {message}")
        else:
            failed_variations += 1
            print(f"  ✗ {message}")
    
    print(f"\nRésumé:")
    print(f"- Tâches traitées: {len(all_variation_tasks)}")
    print(f"- Variations créées avec succès: {successful_variations}")
    print(f"- Variations déjà existantes (ignorées): {skipped_variations}")
    print(f"- Variations échouées: {failed_variations}")
    print(f"- Variations pré-existantes: {total_existing}")
    print(f"- Total final: {total_existing + successful_variations} variations")
    print(f"- Temps d'exécution: {end_time - start_time:.2f} secondes")
    if len(all_variation_tasks) > 0:
        print(f"- Vitesse moyenne: {len(all_variation_tasks) / (end_time - start_time):.1f} tâches/seconde")
    
    print(f"\nStructure créée dans '{OUTPUT_BASE_DIR}':")
    print("├── layout_1_combination_01/")
    print("│   ├── L1_R01_V01.layout")
    print("│   ├── L1_R01_V02.layout")
    print("│   └── ... (jusqu'à V10)")
    print("├── layout_1_combination_02/")
    print("│   ├── L1_R02_V01.layout")
    print("│   └── ...")
    print("├── layout_2_combination_01/")
    print("│   ├── L2_R01_V01.layout")
    print("│   └── ...")
    print("└── ...")

def main():
    """Fonction principale"""
    import sys
    
    # Permettre de spécifier une limite via les arguments de ligne de commande
    if len(sys.argv) > 1:
        try:
            global MAX_LAYOUTS
            MAX_LAYOUTS = int(sys.argv[1])
            print(f"Mode test activé: traitement limité à {MAX_LAYOUTS} layouts par dossier")
        except ValueError:
            print("Argument invalide pour la limite de layouts. Utilisation de tous les layouts.")
    
    print(f"Démarrage du traitement des layouts...")
    print(f"Distance cible entre objets: {DISTANCE_OBJETS}")
    print(f"Nombre de variations par layout: {NUM_VARIATIONS}")
    print(f"Objets à placer: {OBJECTS}")
    print(f"Processeurs disponibles: {cpu_count()}")
    print(f"Processeurs utilisés: {MAX_PROCESSES or cpu_count()}")
    if MAX_LAYOUTS:
        print(f"Limite de layouts par dossier: {MAX_LAYOUTS}")
    print("-" * 50)
    
    process_layouts()
    
    print("-" * 50)
    print("Traitement terminé!")

if __name__ == "__main__":
    # Protection nécessaire pour multiprocessing sur certains systèmes
    multiprocessing.freeze_support()
    main()
