import heapq
from collections import deque
from typing import Tuple, List, Dict, Set


def walkable(arr, pos):
    i,j = pos
    return arr[i,j] != 'X'


def manhattan(a,b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def a_star_time_expanded(arr, start: Tuple[int,int], goal: Tuple[int,int], reservations: Dict[Tuple[int,int], Set[int]], edge_reservations: Set[Tuple[Tuple[int,int], Tuple[int,int], int]], max_time=200):
    """A* in (pos,time) avoiding reservations. reservations: pos -> set(times) when occupied.
    edge_reservations: set of ((from),(to), t) meaning move from->to at time t is forbidden.
    Returns list of positions (path) or None."""
    start_node = (start[0], start[1], 0)
    h0 = manhattan(start, goal)
    openq = [(h0, 0, start_node, None)]
    came = {}
    gscore = {start_node:0}
    while openq:
        _, _, (i,j,t), _ = heapq.heappop(openq)
        if t > max_time:
            continue
        if (i,j) == goal:
            # reconstruct path
            node = (i,j,t)
            path = []
            while node in came:
                pos = (node[0], node[1])
                path.append(pos)
                node = came[node]
            path.append((start[0], start[1]))
            return list(reversed(path))
        # neighbors: stay or move to 4-neighbors
        for di,dj in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]:
            ni, nj = i+di, j+dj
            nt = t+1
            if not (0 <= ni < arr.shape[0] and 0 <= nj < arr.shape[1]):
                continue
            if not walkable(arr, (ni,nj)):
                continue
            # check vertex reservation at time nt
            if (ni,nj) in reservations and nt in reservations[(ni,nj)]:
                continue
            # check edge reservation (can't swap)
            if ((i,j),(ni,nj),t) in edge_reservations:
                continue
            neighbor = (ni,nj,nt)
            tentative_g = gscore.get((i,j,t), 0) + 1
            if tentative_g < gscore.get(neighbor, 1e9):
                gscore[neighbor] = tentative_g
                came[neighbor] = (i,j,t)
                f = tentative_g + manhattan((ni,nj), goal)
                heapq.heappush(openq, (f, tentative_g, neighbor, None))
    return None


def build_reservations_from_path(path: List[Tuple[int,int]]):
    # returns reservations dict pos->set(times) and edge_reservations set
    reservations = {}
    edge_res = set()
    for t, pos in enumerate(path):
        reservations.setdefault(pos, set()).add(t)
        if t>0:
            prev = path[t-1]
            edge_res.add((prev, pos, t-1))
    # also reserve final position for subsequent times to avoid other agents stepping onto it
    final = path[-1]
    reservations.setdefault(final, set()).update(range(len(path), len(path)+20))
    return reservations, edge_res


def plan_sequence(arr, start: Tuple[int,int], waypoints: List[Tuple[int,int]], reservations=None, edge_reservations=None):
    """Plan path visiting waypoints in order, returning concatenated path (positions)."""
    if reservations is None:
        reservations = {}
    if edge_reservations is None:
        edge_reservations = set()
    path = [start]
    cur = start
    for wp in waypoints:
        sub = a_star_time_expanded(arr, cur, wp, reservations, edge_reservations)
        if sub is None:
            return None
        # drop first (cur) to avoid duplication
        path += sub[1:]
        # update reservations and edges locally for this agent's plan only (not global)
        cur = wp
    return path
