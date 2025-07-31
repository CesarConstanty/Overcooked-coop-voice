import numpy as np
import itertools
from collections import deque
from typing import List, Set, Tuple

def generate_empty_grid(width, height):
    return [['X'] * width for _ in range(height)]

def get_neighbors(x, y, grid):
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < len(grid) and 0 <= ny < len(grid[0]) and grid[nx][ny] == ' ':
            yield nx, ny

def is_fully_connected(grid):
    h, w = len(grid), len(grid[0])
    visited = set()

    for i in range(h):
        for j in range(w):
            if grid[i][j] == ' ':
                start = (i, j)
                break
        else:
            continue
        break
    else:
        return False

    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        for nx, ny in get_neighbors(x, y, grid):
            if (nx, ny) not in visited:
                queue.append((nx, ny))

    return len(visited) == sum(row.count(' ') for row in grid)

def has_two_access_paths(grid: List[List[str]]) -> bool:
    h, w = len(grid), len(grid[0])
    directions = [(-1,0), (1,0), (0,-1), (0,1)]

    for i in range(1, h-1):
        for j in range(1, w-1):
            if grid[i][j] != ' ':
                continue
            access_points = [(i+dx, j+dy) for dx, dy in directions
                             if 0 <= i+dx < h and 0 <= j+dy < w and grid[i+dx][j+dy] == ' ']
            if len(access_points) < 2:
                return False
    return True

def get_symmetries(grid: List[List[str]]) -> Set[str]:
    arr = np.array(grid)
    symmetries = set()
    for k in range(4):
        rot = np.rot90(arr, k)
        for variant in [rot, np.fliplr(rot), np.flipud(rot)]:
            symmetries.add(variant.tobytes())  # Much faster than string conversion
    return symmetries

def grid_to_bytes(grid: List[List[str]]) -> bytes:
    return np.array(grid).tobytes()

def has_2x2_block_of_X(grid: List[List[str]]) -> bool:
    for i in range(len(grid)-1):
        for j in range(len(grid[0])-1):
            if grid[i][j] == grid[i+1][j] == grid[i][j+1] == grid[i+1][j+1] == 'X':
                return True
    return False

def count_all_valid_layouts(width: int, height: int, empty_count: int,
                            extremity: bool = False, print_layout: bool = False,
                            echange: bool = False) -> int:
    layouts = set()
    inner_positions = [(i, j) for i in range(1, height-1) for j in range(1, width-1)]

    total_combinations = 0
    for comb in itertools.combinations(inner_positions, empty_count):
        grid = generate_empty_grid(width, height)
        for x, y in comb:
            grid[x][y] = ' '
        total_combinations += 1

        if not is_fully_connected(grid):
            continue
        if not has_two_access_paths(grid):
            continue

        if extremity:
            for i in range(1, height-1):
                if grid[i][1] != ' ' or grid[i][width-2] != ' ':
                    break
            else:
                for j in range(1, width-1):
                    if grid[1][j] != ' ' or grid[height-2][j] != ' ':
                        break
                else:
                    pass  # All extremity conditions passed
                    ...
        elif extremity:
            continue

        if echange and has_2x2_block_of_X(grid):
            continue

        grid_bytes = grid_to_bytes(grid)
        symmetries = get_symmetries(grid)
        if any(sym in layouts for sym in symmetries):
            continue

        if print_layout:
            for row in grid:
                print("".join(row))
            print()

        layouts.add(grid_bytes)

    print(f"\n✅ {len(layouts)} layouts uniques valides trouvés (sur {total_combinations} possibilités testées).")
    return len(layouts)

count_all_valid_layouts(width=8, height=8, empty_count=20, extremity = True, print_layout=False, echange=True)