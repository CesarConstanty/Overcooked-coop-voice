#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.layout_compression import LayoutCompressor
import gzip
import json
from collections import deque

def test_empty_cells_connectivity():
    """Test spécifique de la connectivité des cases vides."""
    
    def get_empty_positions(grid):
        """Trouve toutes les cases vides."""
        empty_pos = []
        for i in range(len(grid)):
            for j in range(len(grid[0])):
                if grid[i][j] == ' ':
                    empty_pos.append((i, j))
        return empty_pos
    
    def bfs_empty_only(grid, start):
        """BFS pour explorer uniquement les cases vides."""
        queue = deque([start])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < len(grid) and 0 <= nj < len(grid[0]) and
                    (ni, nj) not in visited and grid[ni][nj] == ' '):
                    
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        return visited
    
    def are_all_empty_connected(grid):
        """Vérifie que toutes les cases vides sont connectées."""
        empty_positions = get_empty_positions(grid)
        
        if not empty_positions:
            return True, 0, 0
        
        start = empty_positions[0]
        reachable = bfs_empty_only(grid, start)
        
        return len(reachable) == len(empty_positions), len(empty_positions), len(reachable)
    
    # Charger les layouts
    batch_file = "outputs/layouts_generes/layout_batch_1.jsonl.gz"
    compressor = LayoutCompressor()
    
    print("🔍 TEST DE CONNECTIVITÉ DES CASES VIDES")
    print("=" * 50)
    
    with gzip.open(batch_file, 'rt', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            compressed_layout = json.loads(line.strip())
            layout = compressor.decompress_layout(compressed_layout)
            grid_str = layout['grid']
            
            # Convertir en grille 2D
            lines = grid_str.strip().split('\n')
            grid = [list(line) for line in lines]
            
            print(f"\nLayout {i} (Hash: {layout['hash'][:8]}):")
            
            # Afficher la grille
            print("+--------+")
            for row in grid:
                print("|" + "".join(row) + "|")
            print("+--------+")
            
            # Tester la connectivité
            is_connected, total_empty, reachable_empty = are_all_empty_connected(grid)
            
            print(f"📊 Cases vides: {total_empty}")
            print(f"📊 Cases vides accessibles: {reachable_empty}")
            
            if is_connected:
                print("✅ Toutes les cases vides sont connectées!")
            else:
                print("❌ PROBLÈME: Cases vides déconnectées!")
                print(f"   {reachable_empty}/{total_empty} cases vides accessibles")

if __name__ == "__main__":
    test_empty_cells_connectivity()
