import json
from copy import deepcopy
from collections import deque
import os
import math
import multiprocessing as mp
from multiprocessing import Pool
import time
from utils import (generate_layout_id, compress_grid, extract_special_tiles, 
                   get_evaluator_version, get_timestamp, write_ndjson, append_ndjson)

SIZE = 8  # Taille de la grille (modifiable)
min_cases_vides = 30
max_cases_vides = 31
# Nombre maximum de layouts à générer par valeur de "cases vides" (par défaut None = illimité)
MAX_LAYOUTS_PER_N_EMPTY = 1000000
OUTPUT_FILE = "layouts.ndjson"
filepath = "test_generation_layout_final"  # Sortie dans le dossier courant test_generation_layout_final

# ----------------------- UTILITAIRES -----------------------
def print_grid(grid):
    for row in grid:
        print(''.join(row))
    print()

def grid_to_str(grid):
    return '\n'.join(''.join(row) for row in grid)

def rotate(grid):
    return [list(row) for row in zip(*grid[::-1])]

def mirror(grid):
    return [row[::-1] for row in grid]

def all_symmetries(grid):
    forms = set()
    g = grid
    for _ in range(4):
        forms.add(grid_to_str(g))
        forms.add(grid_to_str(mirror(g)))
        g = rotate(g)
    return forms

def get_canonical_form(grid):
    """Retourne la forme canonique (lexicographiquement minimale) d'une grille"""
    forms = all_symmetries(grid)
    return min(forms)

def init_grid(size):
    grid = [['X'] * size for _ in range(size)]
    for i in range(1, size - 1):
        for j in range(1, size - 1):
            grid[i][j] = '.'
    return grid

class Fast2x2Checker:
    """
    Classe optimisée pour la vérification des blocs 2x2.
    Utilise une mémorisation locale et des vérifications incrémentales.
    """
    def __init__(self, size):
        self.size = size
        self.valid_zones = set()
        self.invalid_zones = set()
    
    def _get_affected_zones(self, i, j):
        """Retourne toutes les zones 2x2 potentiellement affectées par un placement en (i,j)"""
        zones = []
        for dx in [-1, 0]:
            for dy in [-1, 0]:
                zone_top_left = (i + dx, j + dy)
                if (zone_top_left[0] >= 0 and zone_top_left[1] >= 0 and
                    zone_top_left[0] < self.size - 1 and zone_top_left[1] < self.size - 1):
                    zones.append(zone_top_left)
        return zones
    
    def _check_zone_2x2(self, grid, top_left_i, top_left_j):
        """Vérifie si une zone 2x2 spécifique contient que des murs"""
        try:
            return all(grid[top_left_i + di][top_left_j + dj] == 'X' 
                      for di in [0, 1] for dj in [0, 1])
        except IndexError:
            return False
    
    def creates_2x2_fast(self, grid, i, j):
        """Version optimisée de creates_2x2 avec cache local."""
        affected_zones = self._get_affected_zones(i, j)
        
        for zone in affected_zones:
            zone_key = (zone[0], zone[1])
            
            if zone_key in self.valid_zones:
                self.valid_zones.discard(zone_key)
            if zone_key in self.invalid_zones:
                self.invalid_zones.discard(zone_key)
            
            if self._check_zone_2x2(grid, zone[0], zone[1]):
                self.invalid_zones.add(zone_key)
                return True
            else:
                self.valid_zones.add(zone_key)
        
        return False
    
    def clear_cache_around(self, i, j):
        """Nettoie le cache autour d'une position lors du backtrack"""
        affected_zones = self._get_affected_zones(i, j)
        for zone in affected_zones:
            zone_key = (zone[0], zone[1])
            self.valid_zones.discard(zone_key)
            self.invalid_zones.discard(zone_key)

def get_optimal_coord_order(size):
    """Heuristique d'ordre des coordonnées pour optimiser l'exploration."""
    center_i, center_j = (size - 1) // 2, (size - 1) // 2
    
    all_coords = []
    for i in range(1, size - 1):
        for j in range(1, size - 1):
            dist_center = math.sqrt((i - center_i)**2 + (j - center_j)**2)
            
            axis_bonus = 0
            if i == center_i or j == center_j:
                axis_bonus = -0.5
            
            corner_malus = 0
            if (i in [1, size-2] and j in [1, size-2]):
                corner_malus = 1.0
            
            priority = dist_center + axis_bonus + corner_malus
            all_coords.append((priority, i, j))
    
    all_coords.sort(key=lambda x: x[0])
    return [(i, j) for _, i, j in all_coords]

def is_connected_full(grid):
    """Test de connectivité complet - utilisé uniquement en fin"""
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    empty_cells = [(i, j) for i in range(rows) for j in range(cols) if grid[i][j] == '.']

    if not empty_cells:
        return False

    start = empty_cells[0]
    queue = deque([start])
    visited[start[0]][start[1]] = True
    reachable = 1

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while queue:
        x, y = queue.popleft()
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < rows and 0 <= ny < cols and not visited[nx][ny] and grid[nx][ny] == '.':
                visited[nx][ny] = True
                reachable += 1
                queue.append((nx, ny))

    return reachable == len(empty_cells)

def is_connected_incremental(grid, new_wall_i, new_wall_j):
    """Test de connectivité incrémental"""
    rows, cols = len(grid), len(grid[0])
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    adjacent_empty = []
    for dx, dy in directions:
        nx, ny = new_wall_i + dx, new_wall_j + dy
        if 0 <= nx < rows and 0 <= ny < cols and grid[nx][ny] == '.':
            adjacent_empty.append((nx, ny))
    
    if len(adjacent_empty) <= 1:
        return True
    
    visited = set()
    queue = deque([adjacent_empty[0]])
    visited.add(adjacent_empty[0])
    
    while queue:
        x, y = queue.popleft()
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (0 <= nx < rows and 0 <= ny < cols and 
                (nx, ny) not in visited and 
                grid[nx][ny] == '.' and 
                (nx, ny) != (new_wall_i, new_wall_j)):
                visited.add((nx, ny))
                queue.append((nx, ny))
    
    for cell in adjacent_empty:
        if cell not in visited:
            return False
    
    return True

def is_canonical_partial(grid, coords, current_index):
    """Vérifie la canonicité partielle avec fréquence très réduite"""
    if current_index % 16 != 0 or current_index < 16:  # Encore plus réduit pour la performance
        return True
    
    test_grid = [row[:] for row in grid]
    
    for k in range(current_index, len(coords)):
        i, j = coords[k]
        test_grid[i][j] = '?'
    
    canonical = get_canonical_form(test_grid)
    current = grid_to_str(test_grid)
    
    return current == canonical

def has_enough_empty_space(grid, remaining_walls, coords, current_index):
    """Vérifie l'espace restant pour les murs"""
    remaining_positions = len(coords) - current_index
    return remaining_walls <= remaining_positions

def estimate_connectivity_impact(grid, i, j, coords, current_index):
    """Estime l'impact sur la connectivité"""
    rows, cols = len(grid), len(grid[0])
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    adjacent_empty_count = 0
    for dx, dy in directions:
        nx, ny = i + dx, j + dy
        if 0 <= nx < rows and 0 <= ny < cols and grid[nx][ny] == '.':
            adjacent_empty_count += 1
    
    return adjacent_empty_count

def generate_layouts_backtracking_single(args):
    """
    Version de generate_layouts_backtracking adaptée pour multiprocessing.
    Prend un tuple (size, n_empty, seed) en argument et retourne des layouts au format NDJSON.
    """
    size, n_empty, seed = args
    
    n_total = (size - 2) ** 2
    n_walls = n_total - n_empty
    layout = init_grid(size)
    seen = set()
    solutions = []

    # Ordre optimisé des coordonnées
    coords = get_optimal_coord_order(size)
    
    # Checker 2x2 optimisé avec cache
    checker_2x2 = Fast2x2Checker(size)
    
    start_time = time.time()
    
    def backtrack(index, remaining_walls):
        # Si une limite est définie et atteinte, arrêter toute la recherche
        if MAX_LAYOUTS_PER_N_EMPTY is not None and len(solutions) >= MAX_LAYOUTS_PER_N_EMPTY:
            return
        # Élagage précoce : pas assez d'espace
        if not has_enough_empty_space(layout, remaining_walls, coords, index):
            return
        
        # Élagage symétrique (fréquence très réduite pour performance)
        if not is_canonical_partial(layout, coords, index):
            return
            
        if remaining_walls == 0:
            # Vérifier la connectivité et la canonicité, puis ajouter la solution
            if is_connected_full(layout):
                canonical = get_canonical_form(layout)
                if canonical not in seen:
                    seen.add(canonical)
                    solutions.append([row[:] for row in layout])

                    # Si une limite est définie et atteinte, on arrête la recherche
                    if MAX_LAYOUTS_PER_N_EMPTY is not None and len(solutions) >= MAX_LAYOUTS_PER_N_EMPTY:
                        return
            return
        if index >= len(coords):
            return

        i, j = coords[index]

        # Heuristique d'ordre des branches
        connectivity_impact = estimate_connectivity_impact(layout, i, j, coords, index)
        
        if connectivity_impact <= 2:
            # Faible impact : tester d'abord sans mur
            backtrack(index + 1, remaining_walls)
            
            # Essayer avec mur
            layout[i][j] = 'X'
            if (not checker_2x2.creates_2x2_fast(layout, i, j) and 
                is_connected_incremental(layout, i, j)):
                backtrack(index + 1, remaining_walls - 1)
            layout[i][j] = '.'  # backtrack
            checker_2x2.clear_cache_around(i, j)
        else:
            # Impact élevé : tester d'abord avec mur
            layout[i][j] = 'X'
            if (not checker_2x2.creates_2x2_fast(layout, i, j) and 
                is_connected_incremental(layout, i, j)):
                backtrack(index + 1, remaining_walls - 1)
            layout[i][j] = '.'  # backtrack
            checker_2x2.clear_cache_around(i, j)
            
            backtrack(index + 1, remaining_walls)

    backtrack(0, n_walls)

    # Convertir les solutions au nouveau format NDJSON
    ndjson_layouts = []
    for i, grid in enumerate(solutions):
        layout_id = generate_layout_id(grid, seed + i)
        
        layout_data = {
            "layout_id": layout_id,
            "grid": compress_grid(grid)
        }
        ndjson_layouts.append(layout_data)

    end_time = time.time()
    execution_time = end_time - start_time
    
    print(f"[PID={os.getpid()}] [N_EMPTY={n_empty}] Layouts generated: {len(solutions)} (Time: {execution_time:.2f}s)")
    
    return n_empty, len(solutions), execution_time, ndjson_layouts

def generate_layouts_parallel(size_range, n_empty_range, num_processes=None, seed=42):
    """
    Version parallélisée de la génération de layouts.
    Génère tous les layouts dans un seul fichier NDJSON.
    
    Args:
        size_range: Actuellement utilisé SIZE constant, mais extensible
        n_empty_range: range des valeurs N_EMPTY à traiter
        num_processes: nombre de processus (None = auto-détection)
        seed: seed de base pour la génération
    """
    if num_processes is None:
        num_processes = min(mp.cpu_count(), len(n_empty_range))
    
    print(f"Démarrage de la génération parallèle avec {num_processes} processus")
    print(f"Range N_EMPTY: {list(n_empty_range)}")
    print(f"Sortie: {OUTPUT_FILE}")
    
    # Préparer les arguments pour chaque processus avec seeds différents
    tasks = []
    for i, n_empty in enumerate(n_empty_range):
        process_seed = seed + i * 10000  # Séparer les seeds par processus
        tasks.append((SIZE, n_empty, process_seed))
    
    start_time = time.time()
    
    # Exécution parallèle
    with Pool(processes=num_processes) as pool:
        results = pool.map(generate_layouts_backtracking_single, tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Collecter tous les layouts et les écrire dans un seul fichier NDJSON
    all_layouts = []
    total_layouts = 0
    
    for n_empty, count, exec_time, ndjson_layouts in results:
        all_layouts.extend(ndjson_layouts)
        total_layouts += count
    
    # Écrire le fichier NDJSON final
    output_path = os.path.join(filepath, OUTPUT_FILE)
    write_ndjson(all_layouts, output_path, compress=False)
    
    # Résumé des résultats
    print(f"\n=== RÉSUMÉ DE LA GÉNÉRATION PARALLÈLE ===")
    print(f"Temps total: {total_time:.2f}s")
    print(f"Layouts générés au total: {total_layouts}")
    print(f"Processus utilisés: {num_processes}")
    print(f"Fichier de sortie: {output_path}")
    
    for n_empty, count, exec_time, _ in results:
        print(f"  N_EMPTY={n_empty}: {count} layouts ({exec_time:.2f}s)")
    
    return results

def test_layout_constraints(grid, verbose=False):
    """
    Teste et affiche les résultats des contraintes de base pour un layout donné.
    Les contraintes de serving area seront vérifiées lors de l'ajout d'objets.
    """
    size = len(grid)
    results = {
        'connected': is_connected_full(grid),
        'no_2x2_blocks': True  # Sera vérifié
    }
    
    # Vérifier les blocs 2x2
    checker = Fast2x2Checker(size)
    for i in range(size):
        for j in range(size):
            if grid[i][j] == 'X' and checker.creates_2x2_fast(grid, i, j):
                results['no_2x2_blocks'] = False
                break
        if not results['no_2x2_blocks']:
            break
    
    if verbose:
        print("=== VALIDATION DES CONTRAINTES DE BASE ===")
        print(f"✅ Connectivité: {results['connected']}")
        print(f"✅ Pas de blocs 2x2: {results['no_2x2_blocks']}")
        print("ℹ️  Contrainte serving area vérifiée lors de l'ajout d'objets")
        print_grid(grid)
    
    return all(results.values())

# ------------------ POINT D'ENTRÉE ------------------
if __name__ == "__main__":
    import argparse
    import sys
    
    # Parser des arguments
    parser = argparse.ArgumentParser(description="Générateur de layouts Overcooked avec contraintes")
    parser.add_argument('recipes_file', nargs='?', default=None,
                       help='Fichier de recettes (optionnel, ignoré)')
    parser.add_argument('layouts_per_recipe', nargs='?', type=int, default=None,
                       help='Nombre de layouts par recette (ignoré si --layouts-total utilisé)')
    parser.add_argument('--grid-size', type=int, default=SIZE,
                       help=f'Taille de la grille NxN (défaut: {SIZE})')
    parser.add_argument('--layouts-total', type=int, default=None,
                       help='Nombre total de layouts à générer')
    parser.add_argument('--min-empty', type=int, default=min_cases_vides,
                       help=f'Minimum de cases vides (défaut: {min_cases_vides})')
    parser.add_argument('--max-empty', type=int, default=max_cases_vides,
                       help=f'Maximum de cases vides (défaut: {max_cases_vides})')
    parser.add_argument('--output', default=OUTPUT_FILE,
                       help=f'Fichier de sortie (défaut: {OUTPUT_FILE})')
    parser.add_argument('--processes', type=int, default=None,
                       help='Nombre de processus (défaut: auto)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Seed pour reproductibilité (défaut: 42)')
    
    args = parser.parse_args()
    
    # Validation des paramètres
    if args.grid_size < 5 or args.grid_size > 20:
        print("❌ Erreur: La taille de grille doit être entre 5 et 20")
        sys.exit(1)
    
    if args.min_empty >= args.grid_size * args.grid_size:
        print("❌ Erreur: Le nombre minimum de cases vides doit être inférieur à la taille totale de la grille")
        sys.exit(1)
    
    # Utiliser les paramètres
    SIZE = args.grid_size
    min_cases_vides = args.min_empty
    max_cases_vides = args.max_empty
    OUTPUT_FILE = args.output
    
    # Adapter le nombre de cases vides à la taille de grille
    total_cells = SIZE * SIZE
    if args.min_empty == 50 and args.max_empty == 51 and SIZE != 10:
        # Adapter automatiquement pour les autres tailles
        empty_ratio = 50 / 100  # 50% de cases vides pour une grille 10x10
        min_cases_vides = max(10, int(total_cells * empty_ratio))
        max_cases_vides = min_cases_vides + 1
        print(f"🔧 Adaptation automatique pour grille {SIZE}x{SIZE}:")
        print(f"   Cases vides: {min_cases_vides}-{max_cases_vides} (ratio ~{empty_ratio:.0%})")
    
    # Déterminer le nombre de layouts à générer
    if args.layouts_total:
        # Mode: générer un nombre total spécifique
        layouts_to_generate = args.layouts_total
        # Répartir sur les différentes valeurs de cases vides
        n_empty_range = range(min_cases_vides, max_cases_vides)
        layouts_per_empty = max(1, layouts_to_generate // len(n_empty_range))
        MAX_LAYOUTS_PER_N_EMPTY = layouts_per_empty
        print(f"🎯 Mode total: {layouts_to_generate} layouts à générer")
        print(f"   {layouts_per_empty} layouts par valeur de cases vides")
    elif args.layouts_per_recipe:
        # Mode hérité: layouts par recette
        MAX_LAYOUTS_PER_N_EMPTY = args.layouts_per_recipe
        print(f"🎯 Mode par recette: {args.layouts_per_recipe} layouts")
    else:
        # Mode par défaut
        print(f"🎯 Mode par défaut: {MAX_LAYOUTS_PER_N_EMPTY} layouts")
    
    # Créer le répertoire de sortie si nécessaire
    os.makedirs(filepath, exist_ok=True)
    
    # Calculer le nombre de processus
    num_processes = args.processes if args.processes else min(mp.cpu_count(), 8)
    
    # Lancer la génération parallèle avec seed déterministe
    n_empty_range = range(min_cases_vides, max_cases_vides)
    
    print(f"Génération de layouts {SIZE}x{SIZE} au format NDJSON")
    print(f"Contraintes appliquées:")
    print(f"  a) Serving areas sur extrémités uniquement")
    print(f"  b) Toutes les cases vides connectées")
    print(f"  c) Pas de carré de X de taille 2x2")
    print(f"Seed: {args.seed}")
    print(f"Range cases vides: {list(n_empty_range)}")
    
    results = generate_layouts_parallel(SIZE, n_empty_range, num_processes, args.seed)
