#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitaires communs pour la génération et évaluation de layouts Overcooked
Author: Claude
Date: 2025-09-17
Changes: Création du module utilitaires communs pour éviter duplication de code
"""

import json
import gzip
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime


def get_evaluator_version() -> str:
    """Retourne la version de l'évaluateur pour traçabilité."""
    return "final_v1.0.0"


def get_timestamp() -> str:
    """Retourne timestamp ISO8601 pour traçabilité."""
    return datetime.now().isoformat()


def compress_grid(grid: List[List[str]]) -> Dict[str, Any]:
    """
    Compresse une grille pour stockage efficace.
    
    Args:
        grid: Grille 2D de caractères
        
    Returns:
        Dict avec grille compressée et métadonnées
    """
    # Run-length encoding pour réduire la taille
    flat = ''.join(''.join(row) for row in grid)
    
    # Méthode simple : stocker comme string + dimensions
    return {
        "format": "flat_string",
        "data": flat,
        "rows": len(grid),
        "cols": len(grid[0]) if grid else 0
    }


def decompress_grid(compressed: Dict[str, Any]) -> List[List[str]]:
    """
    Décompresse une grille compressée.
    
    Args:
        compressed: Grille compressée par compress_grid
        
    Returns:
        Grille 2D de caractères
    """
    if compressed["format"] != "flat_string":
        raise ValueError(f"Format non supporté: {compressed['format']}")
    
    data = compressed["data"]
    rows = compressed["rows"]
    cols = compressed["cols"]
    
    grid = []
    for i in range(rows):
        start_idx = i * cols
        end_idx = start_idx + cols
        row = list(data[start_idx:end_idx])
        grid.append(row)
    
    return grid


def validate_layout_format(layout_data: Dict) -> bool:
    """
    Valide le format d'un layout NDJSON.
    
    Args:
        layout_data: Données du layout à valider
        
    Returns:
        True si le format est valide, False sinon
    """
    try:
        # Vérifier les champs obligatoires
        if not isinstance(layout_data, dict):
            return False
        
        if 'layout_id' not in layout_data:
            return False
        
        if 'grid' not in layout_data:
            return False
        
        # Vérifier le format de la grille
        grid_data = layout_data['grid']
        if not isinstance(grid_data, dict):
            return False
        
        required_grid_fields = ['format', 'data', 'rows', 'cols']
        for field in required_grid_fields:
            if field not in grid_data:
                return False
        
        # Vérifier que le format est correct
        if grid_data['format'] != 'flat_string':
            return False
        
        # Vérifier que rows et cols sont des nombres
        if not isinstance(grid_data['rows'], int) or not isinstance(grid_data['cols'], int):
            return False
        
        # Vérifier que la data est une string
        if not isinstance(grid_data['data'], str):
            return False
        
        # Vérifier la cohérence taille data vs rows*cols
        expected_length = grid_data['rows'] * grid_data['cols']
        if len(grid_data['data']) != expected_length:
            return False
        
        return True
        
    except Exception:
        return False


def extract_special_tiles(grid: List[List[str]]) -> Dict[str, List[Tuple[int, int]]]:
    """
    Extrait les positions des tuiles spéciales (X, objets).
    
    Args:
        grid: Grille 2D de caractères
        
    Returns:
        Dict avec positions par type de tuile
    """
    special_tiles = {}
    
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell != ' ' and cell != 'X':  # X = mur/bordure, espace = vide
                if cell not in special_tiles:
                    special_tiles[cell] = []
                special_tiles[cell].append((i, j))
    
    return special_tiles


def generate_layout_id(grid: List[List[str]], seed: int) -> str:
    """
    Génère un ID unique pour un layout basé sur la grille et le seed.
    
    Args:
        grid: Grille 2D
        seed: Seed utilisé pour la génération
        
    Returns:
        ID unique du layout
    """
    grid_str = ''.join(''.join(row) for row in grid)
    content = f"{grid_str}_{seed}"
    hash_obj = hashlib.md5(content.encode())
    return f"layout_{hash_obj.hexdigest()[:12]}"


def read_ndjson(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Lit un fichier NDJSON (optionnellement compressé).
    
    Args:
        filepath: Chemin vers le fichier NDJSON (ou .ndjson.gz)
        
    Returns:
        Liste des objets JSON
    """
    filepath = Path(filepath)
    
    if filepath.suffix == '.gz':
        open_func = gzip.open
        mode = 'rt'
    else:
        open_func = open
        mode = 'r'
    
    results = []
    with open_func(filepath, mode, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    
    return results


def write_ndjson(data: List[Dict[str, Any]], filepath: Union[str, Path], compress: bool = False) -> None:
    """
    Écrit des données au format NDJSON (optionnellement compressé).
    
    Args:
        data: Liste d'objets à écrire
        filepath: Chemin de sortie
        compress: Si True, compresse avec gzip
    """
    filepath = Path(filepath)
    
    if compress and not filepath.suffix.endswith('.gz'):
        filepath = filepath.with_suffix(filepath.suffix + '.gz')
    
    if compress:
        open_func = gzip.open
        mode = 'wt'
    else:
        open_func = open
        mode = 'w'
    
    with open_func(filepath, mode, encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def append_ndjson(item: Dict[str, Any], filepath: Union[str, Path], compress: bool = False) -> None:
    """
    Ajoute une entrée à un fichier NDJSON existant.
    
    Args:
        item: Objet à ajouter
        filepath: Chemin du fichier
        compress: Si True, utilise compression gzip
    """
    filepath = Path(filepath)
    
    if compress and not filepath.suffix.endswith('.gz'):
        filepath = filepath.with_suffix(filepath.suffix + '.gz')
    
    if compress:
        open_func = gzip.open
        mode = 'at'
    else:
        open_func = open
        mode = 'a'
    
    with open_func(filepath, mode, encoding='utf-8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')


def load_recipes(recipes_file: str = "ensemble_recettes.json") -> List[Dict[str, Any]]:
    """
    Charge le fichier de recettes au nouveau format.
    
    Args:
        recipes_file: Chemin vers ensemble_recettes.json
        
    Returns:
        Liste des recettes avec recipe_id, name, ingredients, steps
    """
    # Adapter selon le format actuel du fichier généré
    with open(recipes_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Si c'est l'ancien format avec recipe_combinations
    if 'recipe_combinations' in data:
        recipes = []
        for i, combo in enumerate(data['recipe_combinations']):
            recipe_id = f"recipe_{combo['combination_id']:03d}"
            recipes.append({
                "recipe_id": recipe_id,
                "name": f"Combo_{combo['combination_id']}",
                "ingredients": [r['ingredients'] for r in combo['recipes']],
                "steps": []  # À compléter si nécessaire
            })
        return recipes
    
    # Sinon, format déjà correct
    return data


def validate_evaluation_format(eval_data: Dict[str, Any]) -> bool:
    """
    Valide qu'une évaluation respecte le format attendu.
    
    Args:
        eval_data: Données d'évaluation à valider
        
    Returns:
        True si valide, False sinon
    """
    required_fields = [
        'layout_id', 'layout_name', 'recipe_id', 'seed', 'evaluator_version',
        'status', 'solo', 'duo', 'timestamp'
    ]
    
    if not all(field in eval_data for field in required_fields):
        return False
    
    # Vérifier les sous-structures
    if 'steps' not in eval_data['solo']:
        return False
    
    if not all(field in eval_data['duo'] for field in ['steps', 'exchanges_total', 'exchanges_by_X']):
        return False
    
    return True


def manhattan_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
    """Calcule la distance de Manhattan entre deux positions."""
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


def get_neighbors(pos: Tuple[int, int], grid_size: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    Retourne les voisins valides d'une position.
    
    Args:
        pos: Position (row, col)
        grid_size: Taille de la grille (rows, cols)
        
    Returns:
        Liste des positions voisines valides
    """
    row, col = pos
    max_row, max_col = grid_size
    
    neighbors = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        new_row, new_col = row + dr, col + dc
        if 0 <= new_row < max_row and 0 <= new_col < max_col:
            neighbors.append((new_row, new_col))
    
    return neighbors


# Constantes utiles
OBJECTS = ['1', '2', 'O', 'T', 'S', 'D', 'P']  # Joueurs et objets du jeu
WALL_CHAR = 'X'
EMPTY_CHAR = ' '
COUNTER_CHAR = 'X'  # Les comptoirs d'échange sont aussi marqués X

# Mapping des objets pour lisibilité
OBJECT_NAMES = {
    '1': 'Player1',
    '2': 'Player2', 
    'O': 'Onion_Dispenser',
    'T': 'Tomato_Dispenser',
    'S': 'Serving_Station',
    'D': 'Dish_Dispenser',
    'P': 'Pot'
}
