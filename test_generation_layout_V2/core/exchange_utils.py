import numpy as np
from .generator import is_exchange_candidate
from .grid import Grid

def convert_X_to_Y(grid: Grid) -> Grid:
    arr = grid.arr.copy()
    h,w = arr.shape
    changed = False
    for i in range(1,h-1):
        for j in range(1,w-1):
            if arr[i,j] == 'X' and is_exchange_candidate(arr, i, j):
                arr[i,j] = 'Y'
                changed = True
    return Grid(arr)
