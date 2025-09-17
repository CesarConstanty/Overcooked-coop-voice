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
ADD_RECIPES_TO_LAYOUTS = True  # True/False — si False, n'ajoute aucune recette aux layouts (layouts "nus")

# Paramètres configurables
INPUT_FILE = "layouts.ndjson"  # Fichier NDJSON d'entrée
OUTPUT_FILE = "layouts_with_objects.ndjson"  # Fichier NDJSON de sortie
DISTANCE_OBJETS = 16  # Distance totale souhaitée entre tous les objets 7*7 : 16 ; 8*8 : 24
NUM_VARIATIONS = 1   # Nombre de variations par layout
OBJECTS = ['1', '2', 'O', 'T', 'S', 'D', 'P']  # Objets à placer
MAX_PROCESSES = None  # Nombre max de processus (None = auto-détection)
MAX_LAYOUTS = None    # Limite le nombre de layouts à traiter (None = tous)
random.seed("07082025")

def extract_grid_from_layout_data(layout_data):
    """Extrait la grille décompressée depuis les données NDJSON"""
    return decompress_grid(layout_data['grid'])

def calculate_manhattan_distance(pos1, pos2):
    """Calcule la distance de Manhattan entre deux positions"""
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
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


def process_single_layout_variation(args):
    """Traite une variation d'un layout (fonction pour multiprocessing)"""
    layout_data, variation_num, add_recipes, distance_target = args
    
    try:
        # Extraire la grille du layout original
        grid = extract_grid_from_layout_data(layout_data)
        
        # Placer les objets avec contrainte de distance
        modified_grid = place_objects_with_distance_constraint(grid, distance_target)
        
        if modified_grid is None:
            return None  # Échec du placement d'objets
        
        # Créer le nouveau layout avec objets
        new_layout_id = f"{layout_data['layout_id']}_obj_v{variation_num:02d}"
        new_layout_name = f"{layout_data['name']}_with_objects_v{variation_num:02d}"
        
        result_layout = {
            "layout_id": new_layout_id,
            "name": new_layout_name,
            "grid": compress_grid(modified_grid),
            "special_tiles": extract_special_tiles(modified_grid),
            "meta": {
                **layout_data['meta'],  # Hériter des métadonnées originales
                "with_objects": True,
                "variation_num": variation_num,
                "distance_target": distance_target,
                "add_recipes": add_recipes,
                "processing_time": get_timestamp(),
                "processor_version": get_evaluator_version()
            }
        }
        
        # Ajouter les recettes si demandé
        if add_recipes:
            try:
                recipes = load_recipes("ensemble_recettes.json")
                result_layout["recipes"] = recipes
            except Exception as e:
                print(f"Attention: Impossible de charger les recettes: {e}")
                result_layout["meta"]["recipes_error"] = str(e)
        
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
    print(f"Fichier d'entrée: {args.input}")
    print(f"Fichier de sortie: {args.output}")
    print(f"Ajout de recettes: {'OUI' if args.add_recipes else 'NON (layouts nus)'}")
    print(f"Distance cible objets: {args.distance}")
    print(f"Variations par layout: {args.variations}")
    
    # Charger les layouts depuis le fichier NDJSON
    print("Chargement des layouts...")
    layouts = read_ndjson(args.input)
    
    if args.max_layouts is not None:
        layouts = layouts[:args.max_layouts]
        print(f"Limitation à {args.max_layouts} layouts")
    
    print(f"Layouts à traiter: {len(layouts)}")
    
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
