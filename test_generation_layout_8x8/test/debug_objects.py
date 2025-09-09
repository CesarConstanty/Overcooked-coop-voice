#!/usr/bin/env python3
"""
Debug spécifique de l'accessibilité des objets dans le layout problématique
"""

def parse_layout_string(layout_str):
    """Parse le string de layout en grille."""
    lines = [line.strip() for line in layout_str.strip().split('\n') if line.strip()]
    return [list(line) for line in lines]

def bfs_reachable(grid, start):
    """BFS pour trouver toutes les cases accessibles."""
    from collections import deque
    
    queue = deque([start])
    visited = {start}
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    grid_size = len(grid)
    
    while queue:
        current = queue.popleft()
        
        for di, dj in directions:
            ni, nj = current[0] + di, current[1] + dj
            
            if (0 <= ni < grid_size and 0 <= nj < grid_size and
                (ni, nj) not in visited and grid[ni][nj] != 'X'):
                
                visited.add((ni, nj))
                queue.append((ni, nj))
    
    return visited

def debug_objects_accessibility():
    """Debug spécifique de l'accessibilité des objets."""
    
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
    
    print("🎯 ANALYSE D'ACCESSIBILITÉ DES OBJETS")
    print("=" * 50)
    
    # Afficher le layout avec coordonnées
    print("\n📋 Layout avec coordonnées:")
    print("   ", end="")
    for j in range(len(grid[0])):
        print(f"{j}", end="")
    print()
    
    for i, row in enumerate(grid):
        print(f"{i}: {''.join(row)}")
    
    # Identifier objets et joueurs
    objects = {}
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            cell = grid[i][j]
            if cell in ['1', '2', 'T', 'O', 'P', 'D', 'S']:
                objects[cell] = (i, j)
    
    print(f"\n🎯 Positions des objets:")
    for obj, pos in objects.items():
        print(f"   {obj}: {pos}")
    
    # Tester accessibilité depuis chaque joueur
    player1_pos = objects.get('1')
    player2_pos = objects.get('2')
    
    if player1_pos:
        reachable_from_p1 = bfs_reachable(grid, player1_pos)
        print(f"\n🔍 Accessibilité depuis Joueur 1 {player1_pos}:")
        
        for obj, pos in objects.items():
            if obj != '1':
                accessible = pos in reachable_from_p1
                print(f"   {obj} {pos}: {'✅' if accessible else '❌'}")
    
    if player2_pos:
        reachable_from_p2 = bfs_reachable(grid, player2_pos)
        print(f"\n🔍 Accessibilité depuis Joueur 2 {player2_pos}:")
        
        for obj, pos in objects.items():
            if obj != '2':
                accessible = pos in reachable_from_p2
                print(f"   {obj} {pos}: {'✅' if accessible else '❌'}")
    
    # Analyse spéciale pour T
    t_pos = objects.get('T')
    if t_pos:
        print(f"\n🍅 ANALYSE SPÉCIALE DES TOMATES T {t_pos}:")
        
        # Cases adjacentes à T
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        direction_names = ['droite', 'gauche', 'bas', 'haut']
        
        adjacent_free = 0
        for (di, dj), name in zip(directions, direction_names):
            ni, nj = t_pos[0] + di, t_pos[1] + dj
            if 0 <= ni < len(grid) and 0 <= nj < len(grid[0]):
                cell = grid[ni][nj]
                is_free = cell != 'X'
                if is_free:
                    adjacent_free += 1
                print(f"   {name} ({ni},{nj}): '{cell}' {'✅' if is_free else '❌'}")
        
        print(f"   Cases libres adjacentes: {adjacent_free}")
        
        if adjacent_free <= 1:
            print(f"   🚨 PROBLÈME: T n'a que {adjacent_free} case(s) libre(s) adjacente(s)!")
            print(f"   💡 Dans Overcooked, il faut pouvoir approcher l'objet ET repartir!")
    
    # Test global de connectivité
    all_objects = list(objects.values())
    all_reachable_from_p1 = all(pos in reachable_from_p1 for pos in all_objects if pos != player1_pos)
    all_reachable_from_p2 = all(pos in reachable_from_p2 for pos in all_objects if pos != player2_pos)
    
    print(f"\n📊 RÉSUMÉ GLOBAL:")
    print(f"   Tous objets accessibles depuis J1: {'✅' if all_reachable_from_p1 else '❌'}")
    print(f"   Tous objets accessibles depuis J2: {'✅' if all_reachable_from_p2 else '❌'}")
    
    if not (all_reachable_from_p1 and all_reachable_from_p2):
        print(f"   🚨 LAYOUT PROBLÉMATIQUE CONFIRMÉ!")

if __name__ == "__main__":
    debug_objects_accessibility()
