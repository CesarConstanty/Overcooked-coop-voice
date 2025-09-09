#!/usr/bin/env python3
"""
Test pour vérifier la connectivité du layout problématique
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

def test_layout_connectivity():
    """Test la connectivité du layout problématique."""
    
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
    
    print("🧪 TEST DE CONNECTIVITÉ DU LAYOUT PROBLÉMATIQUE")
    print("=" * 50)
    
    # Afficher le layout
    print("\n📋 Layout à tester:")
    for i, row in enumerate(grid):
        print(f"{i}: {''.join(row)}")
    
    # Trouver les positions des joueurs
    player1_pos = None
    player2_pos = None
    all_non_wall = []
    
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            if grid[i][j] == '1':
                player1_pos = (i, j)
            elif grid[i][j] == '2':
                player2_pos = (i, j)
            
            if grid[i][j] != 'X':
                all_non_wall.append((i, j))
    
    print(f"\n🎮 Positions des joueurs:")
    print(f"   Joueur 1: {player1_pos}")
    print(f"   Joueur 2: {player2_pos}")
    print(f"   Total cases non-murs: {len(all_non_wall)}")
    
    # Test de connectivité depuis le joueur 1
    if player1_pos:
        reachable_from_p1 = bfs_reachable(grid, player1_pos)
        print(f"\n🔍 Accessibilité depuis Joueur 1:")
        print(f"   Cases accessibles: {len(reachable_from_p1)}")
        print(f"   Joueur 2 accessible: {'✅' if player2_pos in reachable_from_p1 else '❌'}")
        
        if player2_pos not in reachable_from_p1:
            print(f"   ⚠️  PROBLÈME: Joueur 2 non accessible depuis Joueur 1!")
    
    # Test de connectivité depuis le joueur 2
    if player2_pos:
        reachable_from_p2 = bfs_reachable(grid, player2_pos)
        print(f"\n🔍 Accessibilité depuis Joueur 2:")
        print(f"   Cases accessibles: {len(reachable_from_p2)}")
        print(f"   Joueur 1 accessible: {'✅' if player1_pos in reachable_from_p2 else '❌'}")
        
        if player1_pos not in reachable_from_p2:
            print(f"   ⚠️  PROBLÈME: Joueur 1 non accessible depuis Joueur 2!")
    
    # Test de connectivité globale
    total_reachable = len(reachable_from_p1) if player1_pos else 0
    connectivity_ok = total_reachable == len(all_non_wall)
    
    print(f"\n📊 Résumé de connectivité:")
    print(f"   Cases totales non-murs: {len(all_non_wall)}")
    print(f"   Cases accessibles depuis J1: {len(reachable_from_p1) if player1_pos else 0}")
    print(f"   Connectivité complète: {'✅' if connectivity_ok else '❌'}")
    
    if not connectivity_ok:
        print(f"\n🚨 LAYOUT INVALIDE: Zones déconnectées détectées!")
        print(f"   {len(all_non_wall) - total_reachable} cases inaccessibles")
        
        # Trouver les zones inaccessibles
        inaccessible = set(all_non_wall) - reachable_from_p1
        print(f"   Cases inaccessibles: {list(inaccessible)}")
    
    return connectivity_ok

if __name__ == "__main__":
    test_layout_connectivity()
