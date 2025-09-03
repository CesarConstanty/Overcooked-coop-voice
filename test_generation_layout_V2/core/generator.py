import numpy as np
import random
from .grid import Grid, SIZE
from collections import deque
from .grid import Grid

def exterior_wall_mask():
    arr = np.full((SIZE, SIZE), ' ', dtype='<U1')
    arr[0, :] = 'X'
    arr[-1, :] = 'X'
    arr[:, 0] = 'X'
    arr[:, -1] = 'X'
    return arr

def has_2x2_walls(arr):
    for i in range(SIZE-1):
        for j in range(SIZE-1):
            if arr[i,j]=='X' and arr[i+1,j]=='X' and arr[i,j+1]=='X' and arr[i+1,j+1]=='X':
                return True
    return False

def empties_connected(arr):
    # BFS from first empty
    visited = np.zeros(arr.shape, dtype=bool)
    found = False
    for i in range(SIZE):
        for j in range(SIZE):
            if arr[i,j] == ' ':
                si, sj = i, j
                found = True
                break
        if found: break
    if not found:
        return False
    q = deque([(si,sj)])
    visited[si,sj] = True
    count = 1
    while q:
        i,j = q.popleft()
        for di,dj in [(1,0),(-1,0),(0,1),(0,-1)]:
            ni, nj = i+di, j+dj
            if 0<=ni<SIZE and 0<=nj<SIZE and not visited[ni,nj] and arr[ni,nj]==' ':
                visited[ni,nj] = True
                q.append((ni,nj))
                count +=1
    total_empty = (arr==' ').sum()
    return count == total_empty


def is_exchange_candidate(arr, i, j):
    # position (i,j) must be a wall/counter (X) and have walkable cells on two opposite sides
    if arr[i,j] != 'X':
        return False
    # check opposites: up/down or left/right
    h,w = arr.shape
    # up/down
    if 0<=i-1<h and 0<=i+1<h and arr[i-1,j] == ' ' and arr[i+1,j] == ' ':
        return True
    # left/right
    if 0<=j-1<w and 0<=j+1<w and arr[i,j-1] == ' ' and arr[i,j+1] == ' ':
        return True
    return False


def backtrack_generate(n_empty:int, max_iter=10000, seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    base = exterior_wall_mask()
    # interior indices
    interior = [(i,j) for i in range(1,SIZE-1) for j in range(1,SIZE-1)]
    target_empty = n_empty
    interior_cells = len(interior)
    if target_empty > interior_cells:
        raise ValueError('n_empty too large for interior cells')
    for it in range(max_iter):
        arr = base.copy()
        # set all interior to walls then open empties randomly
        for i,j in interior:
            arr[i,j] = 'X'
        empties = set(random.sample(interior, target_empty)) if target_empty>0 else set()
        for (i,j) in empties:
            arr[i,j] = ' '
        if has_2x2_walls(arr):
            continue
        if not empties_connected(arr):
            continue
        # ok
        return Grid(arr)
    raise RuntimeError('Failed to generate layout')
