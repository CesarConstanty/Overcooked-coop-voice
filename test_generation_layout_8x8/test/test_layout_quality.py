#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test avancé pour valider la qualité des layouts générés
Teste la connectivité, l'accessibilité, et la validité du jeu
"""

import json
import gzip
import base64
from pathlib import Path
from collections import deque
from typing import List, Tuple, Set, Dict

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

def find_object_positions(grid: List[List[str]]) -> Dict[str, List[Tuple[int, int]]]:
    """Trouve toutes les positions des objets dans la grille"""
    positions = {}
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell not in [' ', 'X']:  # Objets non-vides
                if cell not in positions:
                    positions[cell] = []
                positions[cell].append((i, j))
    return positions

def bfs_all_reachable(grid: List[List[str]], start: Tuple[int, int]) -> Set[Tuple[int, int]]:
    """BFS pour trouver toutes les positions accessibles depuis un point"""
    height, width = len(grid), len(grid[0])
    queue = deque([start])
    visited = {start}
    
    while queue:
        current = queue.popleft()
        i, j = current
        
        # Vérifier les 4 directions
        for di, dj in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            ni, nj = i + di, j + dj
            if (0 <= ni < height and 0 <= nj < width and 
                (ni, nj) not in visited and grid[ni][nj] != 'X'):
                visited.add((ni, nj))
                queue.append((ni, nj))
    
    return visited

def check_layout_validity(grid: List[List[str]]) -> Dict:
    """Vérifie la validité complète d'un layout"""
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'stats': {}
    }
    
    height, width = len(grid), len(grid[0])
    
    # 1. Vérifications de base
    if height != 8 or width != 8:
        result['valid'] = False
        result['errors'].append(f"Taille incorrecte: {height}x{width} au lieu de 8x8")
    
    # 2. Vérifier les bordures (doivent être des murs ou des objets de service 'S')
    for i in range(height):
        if grid[0][i] not in ['X', 'S']:
            result['valid'] = False
            result['errors'].append(f"Bordure haute invalide à la colonne {i}: '{grid[0][i]}' au lieu de 'X' ou 'S'")
        if grid[height-1][i] not in ['X', 'S']:
            result['valid'] = False
            result['errors'].append(f"Bordure basse invalide à la colonne {i}: '{grid[height-1][i]}' au lieu de 'X' ou 'S'")
    
    for i in range(height):
        if grid[i][0] not in ['X', 'S']:
            result['valid'] = False
            result['errors'].append(f"Bordure gauche invalide à la ligne {i}: '{grid[i][0]}' au lieu de 'X' ou 'S'")
        if grid[i][width-1] not in ['X', 'S']:
            result['valid'] = False
            result['errors'].append(f"Bordure droite invalide à la ligne {i}: '{grid[i][width-1]}' au lieu de 'X' ou 'S'")
    
    # 3. Trouver les objets
    objects = find_object_positions(grid)
    
    # 4. Vérifier les objets requis et la position de S sur la bordure
    required_objects = ['1', '2', 'O', 'T', 'P', 'D', 'S']
    for obj in required_objects:
        if obj not in objects:
            result['valid'] = False
            result['errors'].append(f"Objet requis manquant: {obj}")
        elif len(objects[obj]) != 1:
            result['valid'] = False
            result['errors'].append(f"Objet {obj}: {len(objects[obj])} trouvés, 1 attendu")
    
    # Vérifier que S est sur la bordure extérieure
    if 'S' in objects:
        s_pos = objects['S'][0]
        i, j = s_pos
        is_on_border = (i == 0 or i == height-1 or j == 0 or j == width-1)
        if not is_on_border:
            result['valid'] = False
            result['errors'].append(f"Station de service S doit être sur la bordure extérieure, trouvée en {s_pos}")
    
    # Vérifier qu'il n'y a pas de zones d'échange Y (ajoutées lors de l'évaluation)
    if 'Y' in objects:
        result['valid'] = False
        result['errors'].append(f"Zones d'échange Y détectées: {len(objects['Y'])} - elles doivent être ajoutées lors de l'évaluation, pas de la génération")
    
    # 5. Vérifier les positions des joueurs (pas SUR les bordures extérieures)
    for player in ['1', '2']:
        if player in objects:
            for pos in objects[player]:
                i, j = pos
                if i == 0 or i == height-1 or j == 0 or j == width-1:
                    result['valid'] = False
                    result['errors'].append(f"Joueur {player} sur la bordure extérieure: {pos}")
    
    # 6. Vérifier la connectivité globale
    # Trouver une position non-mur pour commencer
    start_pos = None
    for i in range(height):
        for j in range(width):
            if grid[i][j] != 'X':
                start_pos = (i, j)
                break
        if start_pos:
            break
    
    if start_pos:
        reachable = bfs_all_reachable(grid, start_pos)
        
        # Compter toutes les positions non-mur
        total_non_wall = 0
        for i in range(height):
            for j in range(width):
                if grid[i][j] != 'X':
                    total_non_wall += 1
        
        if len(reachable) != total_non_wall:
            result['valid'] = False
            result['errors'].append(f"Layout déconnecté: {len(reachable)}/{total_non_wall} positions accessibles")
    
    # 7. Vérifier l'accessibilité des objets depuis les joueurs
    if '1' in objects and '2' in objects:
        for player in ['1', '2']:
            player_pos = objects[player][0]
            player_reachable = bfs_all_reachable(grid, player_pos)
            
            for obj_type, positions in objects.items():
                if obj_type not in ['1', '2']:  # Ignorer les autres joueurs
                    for obj_pos in positions:
                        if obj_pos not in player_reachable:
                            result['valid'] = False
                            result['errors'].append(f"Joueur {player} ne peut pas atteindre {obj_type} à {obj_pos}")
    
    # 8. Vérifier les blocs 2x2 de murs
    for i in range(height-1):
        for j in range(width-1):
            block = [grid[i][j], grid[i][j+1], grid[i+1][j], grid[i+1][j+1]]
            if all(cell == 'X' for cell in block):
                result['warnings'].append(f"Bloc 2x2 de murs détecté à ({i},{j})")
    
    # 9. Statistiques
    result['stats'] = {
        'total_cells': height * width,
        'walls': sum(row.count('X') for row in grid),
        'empty_spaces': sum(row.count(' ') for row in grid),
        'objects': sum(len(positions) for positions in objects.values()),
        'object_types': len(objects)
    }
    
    return result

def test_layout_batch(batch_file: Path) -> Dict:
    """Teste un batch complet de layouts"""
    print(f"🧪 Test du batch: {batch_file}")
    
    # Charger les layouts
    layouts = []
    try:
        with gzip.open(batch_file, 'rt', encoding='utf-8') as f:
            for line in f:
                layouts.append(json.loads(line.strip()))
    except Exception as e:
        return {'error': f"Erreur de chargement: {e}"}
    
    print(f"📊 {len(layouts)} layouts à tester")
    
    results = {
        'total_layouts': len(layouts),
        'valid_layouts': 0,
        'invalid_layouts': 0,
        'layout_results': [],
        'global_stats': {
            'total_errors': 0,
            'total_warnings': 0,
            'common_errors': {},
            'common_warnings': {}
        }
    }
    
    for i, layout_data in enumerate(layouts):
        try:
            # Décompresser la grille
            grid = decode_grid_from_base64(layout_data['g'])
            
            # Tester le layout
            validation = check_layout_validity(grid)
            validation['layout_id'] = i
            validation['hash'] = layout_data.get('h', 'N/A')
            
            # Compter les résultats
            if validation['valid']:
                results['valid_layouts'] += 1
            else:
                results['invalid_layouts'] += 1
                print(f"❌ Layout {i} INVALIDE:")
                for error in validation['errors']:
                    print(f"   • {error}")
                    # Compter les erreurs communes
                    error_type = error.split(':')[0]
                    results['global_stats']['common_errors'][error_type] = \
                        results['global_stats']['common_errors'].get(error_type, 0) + 1
                
                # Afficher la grille problématique
                print_grid(grid, f"Layout {i} (Invalide)")
            
            if validation['warnings']:
                print(f"⚠️  Layout {i} - Avertissements:")
                for warning in validation['warnings']:
                    print(f"   • {warning}")
                    warning_type = warning.split(':')[0]
                    results['global_stats']['common_warnings'][warning_type] = \
                        results['global_stats']['common_warnings'].get(warning_type, 0) + 1
            
            results['global_stats']['total_errors'] += len(validation['errors'])
            results['global_stats']['total_warnings'] += len(validation['warnings'])
            results['layout_results'].append(validation)
            
        except Exception as e:
            print(f"💥 Erreur lors du test du layout {i}: {e}")
            results['invalid_layouts'] += 1
    
    return results

def main():
    """Fonction principale de test"""
    layouts_file = Path("outputs/layouts_generes/layout_batch_1.jsonl.gz")
    
    if not layouts_file.exists():
        print(f"❌ Fichier non trouvé: {layouts_file}")
        return
    
    # Tester le batch
    results = test_layout_batch(layouts_file)
    
    if 'error' in results:
        print(f"❌ {results['error']}")
        return
    
    # Rapport final
    print(f"\n📋 RAPPORT FINAL:")
    print(f"   Total layouts testés: {results['total_layouts']}")
    print(f"   ✅ Layouts valides: {results['valid_layouts']}")
    print(f"   ❌ Layouts invalides: {results['invalid_layouts']}")
    print(f"   📊 Taux de validité: {results['valid_layouts']/results['total_layouts']*100:.1f}%")
    
    if results['global_stats']['total_errors'] > 0:
        print(f"\n🔍 ERREURS COMMUNES:")
        for error_type, count in results['global_stats']['common_errors'].items():
            print(f"   • {error_type}: {count} occurrences")
    
    if results['global_stats']['total_warnings'] > 0:
        print(f"\n⚠️  AVERTISSEMENTS COMMUNS:")
        for warning_type, count in results['global_stats']['common_warnings'].items():
            print(f"   • {warning_type}: {count} occurrences")
    
    # Verdict
    if results['valid_layouts'] == results['total_layouts']:
        print(f"\n🎉 TOUS LES LAYOUTS SONT VALIDES! 🎉")
        return 0
    else:
        print(f"\n⚠️  DES PROBLÈMES ONT ÉTÉ DÉTECTÉS")
        return 1

if __name__ == "__main__":
    exit(main())
