#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
# Ensure package imports work when running script directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.generator import backtrack_generate
from core.grid import Grid


def place_stations_simple(grid: Grid):
    # Not used now; we place stations after spawns to ensure accessibility
    return grid


def place_stations_accessible(grid: Grid):
    arr = grid.arr.copy()
    h,w = arr.shape
    # find spawns
    spawns = [(i,j) for i in range(h) for j in range(w) if arr[i,j] in ('1','2')]
    if len(spawns) < 2:
        return grid
    # BFS from each spawn
    from collections import deque
    def bfs(start):
        vis = set()
        q = deque([start])
        vis.add(start)
        while q:
            i,j = q.popleft()
            for di,dj in [(1,0),(-1,0),(0,1),(0,-1)]:
                ni,nj = i+di, j+dj
                if 0<=ni<h and 0<=nj<w and (ni,nj) not in vis and arr[ni,nj] != 'X':
                    vis.add((ni,nj))
                    q.append((ni,nj))
        return vis
    vis1 = bfs(spawns[0])
    vis2 = bfs(spawns[1])
    both = [p for p in vis1.intersection(vis2) if arr[p] == ' ']
    needed = ['P','O','T','D','S']
    for p in both:
        if not needed:
            break
        arr[p] = needed.pop(0)
    return Grid(arr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='test')
    parser.add_argument('--n', type=int, default=5)
    parser.add_argument('--n_empty', type=int, default=30)
    parser.add_argument('--select', type=int, default=5)
    parser.add_argument('--recipes_per_layout', type=int, default=6)
    parser.add_argument('--out', default='test_generation_layout_V2')
    args = parser.parse_args()

    outdir = Path(args.out)
    data = outdir / 'data'
    selected = outdir / 'selected_layouts'
    selected_y = outdir / 'selected_layouts_withY'
    data.mkdir(parents=True, exist_ok=True)
    selected.mkdir(parents=True, exist_ok=True)
    selected_y.mkdir(parents=True, exist_ok=True)

    import numpy as np
    from core.generator import is_exchange_candidate
    from core.recipes import pick_recipes_for_layout
    from core.metrics import estimate_recipe_costs
    import csv

    seen = set()
    count = 0
    i = 0
    while count < args.n and i < args.n*50:
        i += 1
        try:
            g = backtrack_generate(args.n_empty, seed=i)
        except Exception:
            continue
        ch = g.canonical_hash()
        if ch in seen:
            continue
        arr = g.arr.copy()
        empties = [(x,y) for x in range(arr.shape[0]) for y in range(arr.shape[1]) if arr[x,y]==' ']
        if len(empties) < 8:
            continue
        # place spawns at two empties farthest apart
        def manhattan(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])
        best = (0, empties[0], empties[0])
        for a in empties:
            for b in empties:
                d = manhattan(a,b)
                if d > best[0]:
                    best = (d,a,b)
        s1, s2 = best[1], best[2]
        arr[s1] = '1'
        arr[s2] = '2'
        # ensure at least one exchange candidate exists
        found_candidate = any(is_exchange_candidate(arr, x, y) for x in range(arr.shape[0]) for y in range(arr.shape[1]))
        if not found_candidate:
            # try to create one by flipping some interior empty to X if connectivity preserved
            from core.generator import empties_connected
            for x in range(1,arr.shape[0]-1):
                for y in range(1,arr.shape[1]-1):
                    if arr[x,y] == ' ':
                        arr[x,y] = 'X'
                        if is_exchange_candidate(arr, x, y) and empties_connected(arr):
                            found_candidate = True
                            break
                        arr[x,y] = ' '
                if found_candidate:
                    break
        if not found_candidate:
            continue
        g2 = Grid(arr)
        # place stations accessible from both spawns
        g3 = place_stations_accessible(g2)
        # verify stations placed
        arr3 = g3.arr
        required = set(['P','O','T','D','S'])
        placed = set([arr3[i,j] for i in range(arr3.shape[0]) for j in range(arr3.shape[1]) if arr3[i,j] in required])
        if placed != required:
            # not all stations could be placed in mutually accessible cells
            continue
        # verify exchange candidate where opposite sides are reachable by different spawns
        from collections import deque
        h,w = arr3.shape
        # compute reachability sets from each spawn
        spawns = [(i,j) for i in range(h) for j in range(w) if arr3[i,j] in ('1','2')]
        if len(spawns) < 2:
            continue
        def bfs_set(start):
            vis = set(); q = deque([start]); vis.add(start)
            while q:
                i,j = q.popleft()
                for di,dj in [(1,0),(-1,0),(0,1),(0,-1)]:
                    ni,nj = i+di, j+dj
                    if 0<=ni<h and 0<=nj<w and (ni,nj) not in vis and arr3[ni,nj] != 'X':
                        vis.add((ni,nj)); q.append((ni,nj))
            return vis
        vis1 = bfs_set(spawns[0])
        vis2 = bfs_set(spawns[1])
        def exchange_between_spawns(arr, i,j):
            if arr[i,j] != 'X': return False
            # up/down
            if 0<=i-1<h and 0<=i+1<h and arr[i-1,j] != 'X' and arr[i+1,j] != 'X':
                a = (i-1,j); b = (i+1,j)
                # require a reachable from spawn1 and b from spawn2 or viceversa
                if (a in vis1 and b in vis2) or (a in vis2 and b in vis1):
                    return True
            # left/right
            if 0<=j-1<w and 0<=j+1<w and arr[i,j-1] != 'X' and arr[i,j+1] != 'X':
                a = (i,j-1); b = (i,j+1)
                if (a in vis1 and b in vis2) or (a in vis2 and b in vis1):
                    return True
            return False
        has_exchange_between_spawns = any(exchange_between_spawns(arr3, x, y) for x in range(h) for y in range(w))
        if not has_exchange_between_spawns:
            continue
        seen.add(ch)
        raw_path = data / f'layout_{count:03d}.layout'
        sel_path = selected / f'layout_{count:03d}_stations.layout'
        g.save_layout(str(raw_path))
        g3.save_layout(str(sel_path))
        # convert X->Y and save copy
        from core.exchange_utils import convert_X_to_Y
        gy = convert_X_to_Y(g3)
        gy.save_layout(str(selected_y / f'layout_{count:03d}_stations_Y.layout'))
        # assign recipes
        recipes = pick_recipes_for_layout(n=args.recipes_per_layout, seed=i)
        # save recipes for reproducibility
        from core.recipes import save_recipes_json
        rec_path = outdir / f'recipes_{count:03d}.json'
        save_recipes_json(str(rec_path), recipes, params={'seed': i, 'n_empty': args.n_empty, 'recipes_per_layout': args.recipes_per_layout})
        # estimate metrics
        estimates = estimate_recipe_costs(g3, recipes)
        # write metrics per layout
        metrics_file = outdir / 'metrics.csv'
        write_header = not metrics_file.exists()
        with open(metrics_file, 'a', newline='') as csvf:
            writer = csv.DictWriter(csvf, fieldnames=['layout','recipe','cost_no_exchange','cost_with_exchange','exchange_gain'])
            if write_header:
                writer.writeheader()
            for r in estimates:
                writer.writerow({'layout': sel_path.name, 'recipe': '+'.join(r['recipe']), 'cost_no_exchange': r['cost_no_exchange'], 'cost_with_exchange': r['cost_with_exchange'], 'exchange_gain': r['exchange_gain']})
        count += 1

    print(f'Generated {count} layouts in {data} and placed stations in {selected}')

if __name__ == '__main__':
    main()
