#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ajout d'objets dans les layouts Overcooked
Author: Claude
Date: 2025-09-17
Changes: Ajout option ADD_RECIPES_TO_LAYOUTS et support CLI, adaptation au format NDJSON
"""

import os
import random
import itertools
import argparse
from pathlib import Path
import multiprocessing
from multiprocessing import Pool, cpu_count
import time
from utils import (read_ndjson, write_ndjson, append_ndjson, decompress_grid, 
                   compress_grid, extract_special_tiles, generate_layout_id,
                   get_evaluator_version, get_timestamp, load_recipes)

# ===================== CONFIGURATION =====================
# Option principale : ajouter les recettes aux layouts ou non
ADD_RECIPES_TO_LAYOUTS = False  # True/False — si False, n'ajoute aucune recette aux layouts (layouts "nus")

# Paramètres configurables
INPUT_FILE = "layouts.ndjson"  # Fichier NDJSON d'entrée
OUTPUT_FILE = "layouts_with_objects.ndjson"  # Fichier NDJSON de sortie
DISTANCE_OBJETS = 20  # Distance totale souhaitée entre tous les objets 7*7 : 16 ; 8*8 : 24
NUM_VARIATIONS = 1   # Nombre de variations par layout
OBJECTS = ['1', '2', 'O', 'T', 'S', 'D', 'P']  # Objets à placer
MAX_PROCESSES = None  # Nombre max de processus (None = auto-détection)
MAX_LAYOUTS = None    # Limite le nombre de layouts à traiter (None = tous)
random.seed("07082025")

def extract_grid_from_layout_data(layout_data):
    """Extrait la grille décompressée depuis les données NDJSON"""
    return decompress_grid(layout_data['grid'])

def get_valid_wall_positions(grid):
    """
    Retourne toutes les positions de murs (X) qui sont adjacentes à au moins une case vide.
    Ces positions peuvent accueillir des objets en remplacement du X.
    MODIFICATION: Tous les objets remplacent maintenant un X adjacente à une case vide.
    """
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    valid_walls = []
    
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == 'X':
                # Vérifier qu'il y a au moins une case vide adjacente
                has_adjacent_empty = False
                for di, dj in directions:
                    ni, nj = i + di, j + dj
                    if (0 <= ni < len(grid) and 0 <= nj < len(grid[0]) and 
                        grid[ni][nj] in ['.', ' ']):
                        has_adjacent_empty = True
                        break
                
                if has_adjacent_empty:
                    valid_walls.append((i, j))
    
    return valid_walls

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

def find_empty_positions(grid):
    """Trouve toutes les positions vides dans la grille (marquées par '.' ou ' ')"""
    empty_positions = []
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == '.' or cell == ' ':  # Supporter les deux formats
                empty_positions.append((i, j))
    return empty_positions


def is_edge_position(pos, grid):
    """Vérifie si une position est sur le bord de la grille"""
    i, j = pos
    return i == 0 or i == len(grid) - 1 or j == 0 or j == len(grid[0]) - 1

def get_edge_wall_positions(grid):
    """
    Retourne les positions de murs (X) qui sont sur les extrémités/bords de la grille
    et adjacentes à au moins une case vide.
    """
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    edge_walls = []
    
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == 'X' and is_edge_position((i, j), grid):
                # Vérifier qu'il y a au moins une case vide adjacente
                has_adjacent_empty = False
                for di, dj in directions:
                    ni, nj = i + di, j + dj
                    if (0 <= ni < len(grid) and 0 <= nj < len(grid[0]) and 
                        grid[ni][nj] in ['.', ' ']):
                        has_adjacent_empty = True
                        break
                
                if has_adjacent_empty:
                    edge_walls.append((i, j))
    
    return edge_walls


def get_valid_positions_for_object(grid, obj):
    """Retourne les positions valides pour placer un objet donné"""
    
    if obj == 'S':  # Serving areas : SEULEMENT sur les extrémités (bords de grille)
        return get_edge_wall_positions(grid)
    elif obj in ['1', '2']:  # Joueurs remplacent des cases vides, pas sur les bords
        empty_positions = find_empty_positions(grid)
        return [pos for pos in empty_positions if not is_edge_position(pos, grid)]
    elif obj in ['O', 'T', 'D', 'P']:  # Autres objets : SEULEMENT murs X accessibles
        return get_valid_wall_positions(grid)
    else:  # Objets non spécifiés : murs X accessibles
        return get_valid_wall_positions(grid)


def has_adjacent_empty_space(pos, grid):
    """Vérifie si une position a au moins un espace vide adjacent"""
    i, j = pos
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    for di, dj in directions:
        ni, nj = i + di, j + dj
        if 0 <= ni < len(grid) and 0 <= nj < len(grid[0]):
            if grid[ni][nj] == '.' or grid[ni][nj] == ' ':
                return True
    return False


def place_objects_with_distance_constraint(grid, target_distance, max_attempts=1000):
    """
    Place tous les objets du jeu en respectant une contrainte de distance totale.
    Adaptation pour le nouveau format de grille (cases vides = '.' ou ' ')
    """
    attempts = 0
    
    while attempts < max_attempts:
        # Créer une copie de la grille pour cette tentative
        test_grid = [row[:] for row in grid]
        object_positions = {}
        
        # Essayer de placer chaque objet
        all_placed = True
        for obj in OBJECTS:
            valid_positions = get_valid_positions_for_object(test_grid, obj)
            
            if not valid_positions:
                all_placed = False
                break
            
            # Choisir une position aléatoire valide
            pos = random.choice(valid_positions)
            test_grid[pos[0]][pos[1]] = obj
            object_positions[obj] = pos
        
        if not all_placed:
            attempts += 1
            continue
        
        # Calculer la distance totale
        positions = list(object_positions.values())
        total_distance = calculate_total_path_distance(positions)
        
        # Vérifier si la distance est acceptable (avec une tolérance)
        if abs(total_distance - target_distance) <= 2:
            return test_grid, object_positions, total_distance
        
        attempts += 1
    
    # Si aucune solution trouvée, retourner None
    return None, None, None


def grid_to_string(grid):
    """Convertit une grille 2D en string multi-lignes"""
    return '\n'.join(''.join(row) for row in grid)


def process_single_layout_variation(args):
    """Traite une variation d'un layout (fonction pour multiprocessing)"""
    layout_data, variation_num, add_recipes, distance_target = args
    
    try:
        # Extraire la grille du layout original
        grid = extract_grid_from_layout_data(layout_data)
        
        # Placer les objets avec contrainte de distance
        result = place_objects_with_distance_constraint(grid, distance_target)
        
        if result[0] is None:  # result = (grid, positions, distance)
            return None  # Échec du placement d'objets
        
        modified_grid, object_positions, actual_distance = result
        
        # Créer le nouveau layout avec objets (format simplifié avec distance)
        new_layout_id = f"{layout_data['layout_id']}_d{actual_distance}_v{variation_num:02d}"
        
        result_layout = {
            "layout_id": new_layout_id,
            "grid": compress_grid(modified_grid)
        }
        
        # Ajouter les recettes si demandé
        if add_recipes:
            try:
                recipes = load_recipes("ensemble_recettes.json")
                result_layout["recipes"] = recipes
            except Exception as e:
                print(f"Attention: Impossible de charger les recettes: {e}")
        
        return result_layout
        
    except Exception as e:
        print(f"Erreur lors du traitement du layout {layout_data.get('layout_id', 'unknown')}: {e}")
        return None


def main():
    """Fonction principale avec support CLI"""
    parser = argparse.ArgumentParser(description="Ajout d'objets dans les layouts Overcooked")
    parser.add_argument('--add-recipes', action='store_true', default=ADD_RECIPES_TO_LAYOUTS,
                        help='Ajouter les recettes aux layouts')
    parser.add_argument('--no-add-recipes', dest='add_recipes', action='store_false',
                        help='Ne pas ajouter les recettes (layouts nus)')
    parser.add_argument('--max-layouts', type=int, default=MAX_LAYOUTS,
                        help='Limite le nombre de layouts à traiter')
    parser.add_argument('--variations', type=int, default=NUM_VARIATIONS,
                        help='Nombre de variations par layout')
    parser.add_argument('--distance', type=int, default=DISTANCE_OBJETS,
                        help='Distance cible entre objets')
    parser.add_argument('--input', default=INPUT_FILE,
                        help='Fichier NDJSON d\'entrée')
    parser.add_argument('--output', default=OUTPUT_FILE,
                        help='Fichier NDJSON de sortie')
    parser.add_argument('--processes', type=int, default=MAX_PROCESSES,
                        help='Nombre de processus (None = auto)')
    
    args = parser.parse_args()
    
    print(f"=== AJOUT D'OBJETS DANS LES LAYOUTS ===")
    print(f"Version: {get_evaluator_version()}")
    print(f"Paramètres:")
    print(f"  - Fichier d'entrée: {args.input}")
    print(f"  - Fichier de sortie: {args.output}")
    print(f"  - Ajout de recettes: {'OUI' if args.add_recipes else 'NON'}")
    print(f"  - Distance cible: {args.distance}")
    print(f"  - Variations par layout: {args.variations}")
    print(f"  - Limite layouts: {args.max_layouts or 'Aucune'}")
    print(f"  - Processus: {args.processes or 'Auto'}")
    print("-" * 50)
    
    try:
        result = process_layouts_with_args(args)
        print(f"\n✅ Traitement terminé avec succès!")
        print(f"Layouts générés: {len(result)}")
        
    except Exception as e:
        print(f"\n❌ Erreur during traitement: {e}")
        return 1
    
    return 0


def process_layouts_with_args(args):
    """Traite tous les layouts au format NDJSON avec les arguments CLI"""
    
    print(f"=== TRAITEMENT DES LAYOUTS ===")
    
    # Convertir les chemins en absolus pour éviter les erreurs
    args.input = os.path.abspath(args.input)
    args.output = os.path.abspath(args.output)
    
    print(f"Fichier d'entrée: {args.input}")
    print(f"Ajout de recettes: {'OUI' if args.add_recipes else 'NON (layouts nus)'}")
    print(f"Distance cible objets: {args.distance}")
    print(f"Variations par layout: {args.variations}")
    
    # Vérifier que le fichier d'entrée existe
    if not os.path.exists(args.input):
        print(f"❌ Erreur: Fichier d'entrée non trouvé: {args.input}")
        return []
    
    # Charger les layouts depuis le fichier NDJSON
    print("Chargement des layouts...")
    layouts = read_ndjson(args.input)
    
    if args.max_layouts is not None:
        layouts = layouts[:args.max_layouts]
        print(f"Limitation à {args.max_layouts} layouts")
    
    print(f"Layouts à traiter: {len(layouts)}")
    
    # Calculer le nombre de cellules vides à partir du premier layout
    if layouts:
        first_grid = extract_grid_from_layout_data(layouts[0])
        empty_cells = sum(row.count('.') + row.count(' ') for row in first_grid)
        
        print(f"Cellules vides détectées: {empty_cells}")
        print(f"Fichier de sortie: {args.output}")
    
    # Préparer les tâches pour le multiprocessing
    tasks = []
    for layout_data in layouts:
        for variation_num in range(args.variations):
            task_args = (layout_data, variation_num, args.add_recipes, args.distance)
            tasks.append(task_args)
    
    print(f"Tâches de variations: {len(tasks)}")
    
    # Traitement en parallèle
    num_processes = args.processes or min(cpu_count(), len(tasks))
    print(f"Processus utilisés: {num_processes}")
    
    start_time = time.time()
    
    if num_processes == 1:
        # Traitement séquentiel pour debug
        results = [process_single_layout_variation(task) for task in tasks]
    else:
        # Traitement parallèle
        with Pool(processes=num_processes) as pool:
            results = pool.map(process_single_layout_variation, tasks)
    
    end_time = time.time()
    
    # Filtrer les résultats réussis et les écrire
    successful_layouts = [result for result in results if result is not None]
    
    if successful_layouts:
        print(f"Écriture de {len(successful_layouts)} layouts avec objets...")
        write_ndjson(successful_layouts, args.output, compress=False)
        print(f"✅ Fichier créé: {args.output}")
    else:
        print("❌ Aucun layout traité avec succès")
    
    # Statistiques finales
    print(f"\n=== RÉSUMÉ ===")
    print(f"Temps total: {end_time - start_time:.2f}s")
    print(f"Layouts traités: {len(successful_layouts)}/{len(tasks)}")
    print(f"Taux de succès: {len(successful_layouts)/len(tasks)*100:.1f}%")
    
    return successful_layouts


if __name__ == "__main__":
    # Protection nécessaire pour multiprocessing
    multiprocessing.freeze_support()
    exit(main())
