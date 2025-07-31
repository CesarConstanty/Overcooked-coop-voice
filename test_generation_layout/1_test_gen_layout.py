import json
from copy import deepcopy
from collections import deque
import os

SIZE = 7  # Taille de la grille (modifiable)
OUTPUT_TEMPLATE = "layouts_{}.json"
filepath = "test_generation_layout/raw_layouts/"

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

def is_unique(grid, seen_hashes):
    forms = all_symmetries(grid)
    for f in forms:
        if f in seen_hashes:
            return False
    seen_hashes.add(min(forms))
    return True

def init_grid(size):
    grid = [['X'] * size for _ in range(size)]
    for i in range(1, size - 1):
        for j in range(1, size - 1):
            grid[i][j] = '.'
    return grid

def creates_2x2(grid, i, j):
    for dx in [-1, 0]:
        for dy in [-1, 0]:
            try:
                if all(grid[i+dx+di][j+dy+dj] == 'X' for di in [0,1] for dj in [0,1]):
                    return True
            except IndexError:
                continue
    return False

def is_connected(grid):
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

def generate_layouts_backtracking(size, n_empty, output_file):
    n_total = (size - 2) ** 2
    n_walls = n_total - n_empty
    layout = init_grid(size)
    seen = set()
    solutions = []

    coords = [(i, j) for i in range(1, size-1) for j in range(1, size-1)]

    def backtrack(index, remaining_walls):
        if remaining_walls == 0:
            if is_connected(layout) and is_unique(layout, seen):
                solutions.append([row[:] for row in layout])
            return
        if index >= len(coords):
            return

        i, j = coords[index]

        # Essayer avec mur
        layout[i][j] = 'X'
        if not creates_2x2(layout, i, j):
            backtrack(index + 1, remaining_walls - 1)
        layout[i][j] = '.'  # backtrack

        # Essayer sans mur
        backtrack(index + 1, remaining_walls)

    backtrack(0, n_walls)

    with open(output_file, 'w') as f:
        for grid in solutions:
            json.dump({"layout": grid}, f)
            f.write('\n')

    print(f"[N_EMPTY={n_empty}] Layouts generated: {len(solutions)}")

# ------------------ POINT D'ENTRÉE ------------------
if __name__ == "__main__":
    for N_EMPTY in range(10, 30):
        os.makedirs(filepath, exist_ok=True)
        filename = filepath + OUTPUT_TEMPLATE.format(N_EMPTY)
        generate_layouts_backtracking(SIZE, N_EMPTY, filename)