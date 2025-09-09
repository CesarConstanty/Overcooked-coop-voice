#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de débogage pour analyser les layouts générés et identifier les problèmes
"""

import json
import gzip
import base64
from pathlib import Path
from collections import deque
from typing import List, Tuple, Set

def decode_grid_from_base64(encoded_grid: str) -> List[List[str]]:
    """Décode une grille depuis base64"""
    grid_str = base64.b64decode(encoded_grid.encode('ascii')).decode('utf-8')
    lines = grid_str.strip().split('\n')
    return [list(line) for line in lines]

def print_grid(grid: List[List[str]], title: str = "Grid"):
    """Affiche une grille de façon lisible"""
    print(f"\n{title}:")
    print("+" + "-" * len(grid[0]) + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * len(grid[0]) + "+")

def check_connectivity(grid: List[List[str]]) -> Tuple[bool, Set[Tuple[int, int]], List[Set[Tuple[int, int]]]]:
    """Vérifie la connectivité complète et retourne les composantes"""
    height, width = len(grid), len(grid[0])
    
    # Trouver toutes les positions vides
    empty_positions = set()
    for i in range(height):
        for j in range(width):
            if grid[i][j] not in ['X']:  # Tout ce qui n'est pas un mur
                empty_positions.add((i, j))
    
    if len(empty_positions) <= 1:
        return True, empty_positions, []
    
    # BFS pour trouver les composantes connectées
    visited = set()
    components = []
    
    def bfs_component(start):
        component = set()
        queue = deque([start])
        component.add(start)
        visited.add(start)
        
        while queue:
            current = queue.popleft()
            i, j = current
            
            # Vérifier les 4 directions
            for di, dj in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ni, nj = i + di, j + dj
                if (0 <= ni < height and 0 <= nj < width and 
                    (ni, nj) not in visited and (ni, nj) in empty_positions):
                    visited.add((ni, nj))
                    component.add((ni, nj))
                    queue.append((ni, nj))
        
        return component
    
    for pos in empty_positions:
        if pos not in visited:
            component = bfs_component(pos)
            components.append(component)
    
    is_connected = len(components) == 1
    return is_connected, empty_positions, components

def check_for_dots(grid: List[List[str]]) -> List[Tuple[int, int]]:
    """Cherche les positions avec des points au lieu d'espaces"""
    dots = []
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == '.':
                dots.append((i, j))
    return dots

def check_isolated_cells(grid: List[List[str]]) -> List[Tuple[int, int]]:
    """Cherche les cellules isolées (entourées de murs)"""
    height, width = len(grid), len(grid[0])
    isolated = []
    
    for i in range(height):
        for j in range(width):
            if grid[i][j] != 'X':  # Position non-mur
                # Vérifier si entourée de murs
                neighbors = []
                for di, dj in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    ni, nj = i + di, j + dj
                    if 0 <= ni < height and 0 <= nj < width:
                        neighbors.append(grid[ni][nj])
                    else:
                        neighbors.append('X')  # Bordure = mur
                
                if all(n == 'X' for n in neighbors):
                    isolated.append((i, j))
    
    return isolated

def analyze_layout(layout_data: dict, layout_id: str) -> dict:
    """Analyse complète d'un layout"""
    try:
        # Décompresser la grille
        grid = decode_grid_from_base64(layout_data['g'])
        
        # Vérifications
        dots = check_for_dots(grid)
        isolated = check_isolated_cells(grid)
        is_connected, empty_pos, components = check_connectivity(grid)
        
        analysis = {
            'layout_id': layout_id,
            'grid_size': (len(grid), len(grid[0]) if grid else 0),
            'has_dots': len(dots) > 0,
            'dot_positions': dots,
            'has_isolated_cells': len(isolated) > 0,
            'isolated_positions': isolated,
            'is_connected': is_connected,
            'num_components': len(components),
            'empty_positions_count': len(empty_pos),
            'components_sizes': [len(comp) for comp in components] if components else [],
            'grid': grid
        }
        
        return analysis
        
    except Exception as e:
        return {
            'layout_id': layout_id,
            'error': str(e),
            'grid': None
        }

def main():
    # Charger et analyser les layouts
    layouts_file = Path("outputs/layouts_generes/layout_batch_1.jsonl.gz")
    
    if not layouts_file.exists():
        print(f"Fichier non trouvé: {layouts_file}")
        return
    
    print(f"🔍 Analyse des layouts dans {layouts_file}")
    
    layouts = []
    with gzip.open(layouts_file, 'rt', encoding='utf-8') as f:
        for line in f:
            layouts.append(json.loads(line.strip()))
    
    print(f"📊 {len(layouts)} layouts trouvés")
    
    # Analyser chaque layout
    problems_found = 0
    
    for i, layout_data in enumerate(layouts):
        analysis = analyze_layout(layout_data, f"layout_{i}")
        
        has_problems = (analysis.get('has_dots', False) or 
                       analysis.get('has_isolated_cells', False) or 
                       not analysis.get('is_connected', True))
        
        if has_problems:
            problems_found += 1
            print(f"\n❌ PROBLÈMES DÉTECTÉS - Layout {i} (hash: {layout_data.get('h', 'N/A')})")
            
            if analysis.get('has_dots'):
                print(f"  🔸 Points détectés aux positions: {analysis['dot_positions']}")
            
            if analysis.get('has_isolated_cells'):
                print(f"  🏝️ Cellules isolées aux positions: {analysis['isolated_positions']}")
            
            if not analysis.get('is_connected'):
                print(f"  ✂️ Layout déconnecté: {analysis['num_components']} composantes")
                print(f"     Tailles des composantes: {analysis['components_sizes']}")
            
            if analysis.get('grid'):
                print_grid(analysis['grid'], f"Layout {i} (Problématique)")
            
            if analysis.get('error'):
                print(f"  💥 Erreur: {analysis['error']}")
    
    print(f"\n📈 RÉSUMÉ:")
    print(f"  Total layouts: {len(layouts)}")
    print(f"  Layouts avec problèmes: {problems_found}")
    print(f"  Pourcentage de problèmes: {problems_found/len(layouts)*100:.1f}%")

if __name__ == "__main__":
    main()
