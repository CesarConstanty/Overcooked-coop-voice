#!/usr/bin/env python3
"""
Debug détaillé de la connectivité du layout problématique
"""

def parse_layout_string(layout_str):
    """Parse le string de layout en grille."""
    lines = [line.strip() for line in layout_str.strip().split('\n') if line.strip()]
    return [list(line) for line in lines]

def bfs_path_exists(grid, start, end):
    """Vérifie s'il existe un chemin entre start et end."""
    from collections import deque
    
    if start == end:
        return True, [start]
    
    queue = deque([(start, [start])])
    visited = {start}
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    grid_size = len(grid)
    
    while queue:
        current, path = queue.popleft()
        
        for di, dj in directions:
            ni, nj = current[0] + di, current[1] + dj
            
            if (0 <= ni < grid_size and 0 <= nj < grid_size and
                (ni, nj) not in visited and grid[ni][nj] != 'X'):
                
                new_path = path + [(ni, nj)]
                
                if (ni, nj) == end:
                    return True, new_path
                
                visited.add((ni, nj))
                queue.append(((ni, nj), new_path))
    
    return False, []

def visualize_path(grid, path):
    """Visualise le chemin sur la grille."""
    # Créer une copie de la grille
    visual_grid = [row[:] for row in grid]
    
    # Marquer le chemin
    for i, (r, c) in enumerate(path):
        if visual_grid[r][c] not in ['1', '2']:
            visual_grid[r][c] = '•'
    
    print("📍 Visualisation du chemin (• = chemin):")
    for i, row in enumerate(visual_grid):
        print(f"{i}: {''.join(row)}")

def test_layout_detailed():
    """Test détaillé du layout problématique."""
    
    # Layout problématique
    layout_str = """XXXXXXXX
X    O X
XTX X XX
XXXX   X
SD XX 1X
X X   PX
X 2  X X
XXXXXXXX"""
    
    grid = parse_layout_string(layout_str)
    
    print("🔍 DEBUG DÉTAILLÉ DE CONNECTIVITÉ")
    print("=" * 50)
    
    # Afficher le layout avec coordonnées
    print("\n📋 Layout avec coordonnées:")
    print("   01234567")
    for i, row in enumerate(grid):
        print(f"{i}: {''.join(row)}")
    
    # Trouver les positions des joueurs
    player1_pos = None
    player2_pos = None
    
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            if grid[i][j] == '1':
                player1_pos = (i, j)
            elif grid[i][j] == '2':
                player2_pos = (i, j)
    
    print(f"\n🎮 Positions:")
    print(f"   Joueur 1: {player1_pos} -> grid[{player1_pos[0]}][{player1_pos[1]}] = '{grid[player1_pos[0]][player1_pos[1]]}'")
    print(f"   Joueur 2: {player2_pos} -> grid[{player2_pos[0]}][{player2_pos[1]}] = '{grid[player2_pos[0]][player2_pos[1]]}'")
    
    # Test de chemin direct entre les deux joueurs
    path_exists, path = bfs_path_exists(grid, player1_pos, player2_pos)
    
    print(f"\n🛣️  Chemin entre joueurs:")
    print(f"   Chemin existe: {'✅' if path_exists else '❌'}")
    if path_exists:
        print(f"   Longueur du chemin: {len(path)}")
        print(f"   Chemin: {' -> '.join([f'({r},{c})' for r, c in path])}")
        visualize_path(grid, path)
    else:
        print("   ❌ AUCUN CHEMIN TROUVÉ!")
    
    # Vérifier chaque mouvement possible depuis les joueurs
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    dir_names = ["droite", "gauche", "bas", "haut"]
    
    print(f"\n🧭 Mouvements possibles depuis Joueur 1 {player1_pos}:")
    for (di, dj), name in zip(directions, dir_names):
        ni, nj = player1_pos[0] + di, player1_pos[1] + dj
        if 0 <= ni < len(grid) and 0 <= nj < len(grid[0]):
            cell = grid[ni][nj]
            accessible = cell != 'X'
            print(f"   {name}: ({ni},{nj}) = '{cell}' {'✅' if accessible else '❌'}")
        else:
            print(f"   {name}: hors grille ❌")
    
    print(f"\n🧭 Mouvements possibles depuis Joueur 2 {player2_pos}:")
    for (di, dj), name in zip(directions, dir_names):
        ni, nj = player2_pos[0] + di, player2_pos[1] + dj
        if 0 <= ni < len(grid) and 0 <= nj < len(grid[0]):
            cell = grid[ni][nj]
            accessible = cell != 'X'
            print(f"   {name}: ({ni},{nj}) = '{cell}' {'✅' if accessible else '❌'}")
        else:
            print(f"   {name}: hors grille ❌")

if __name__ == "__main__":
    test_layout_detailed()
