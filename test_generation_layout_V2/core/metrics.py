import numpy as np
from collections import deque
from .grid import Grid

def multi_source_bfs(arr, sources):
    h,w = arr.shape
    dist = np.full(arr.shape, -1, dtype=int)
    q = deque()
    for (i,j) in sources:
        dist[i,j] = 0
        q.append((i,j))
    while q:
        i,j = q.popleft()
        for di,dj in [(1,0),(-1,0),(0,1),(0,-1)]:
            ni, nj = i+di, j+dj
            if 0<=ni<h and 0<=nj<w and arr[ni,nj] != 'X' and dist[ni,nj]==-1:
                dist[ni,nj] = dist[i,j]+1
                q.append((ni,nj))
    return dist

def avg_distance_to_service(grid: Grid):
    arr = grid.arr
    service = [(i,j) for i in range(arr.shape[0]) for j in range(arr.shape[1]) if arr[i,j]=='S']
    if not service:
        return None
    dist = multi_source_bfs(arr, service)
    empties = [(i,j) for i in range(arr.shape[0]) for j in range(arr.shape[1]) if arr[i,j] in [' ', 'P','O','T','D','1','2']]
    vals = [dist[i,j] for (i,j) in empties if dist[i,j]>=0]
    if not vals:
        return None
    return sum(vals)/len(vals)


def find_positions(arr, token):
    return [(i,j) for i in range(arr.shape[0]) for j in range(arr.shape[1]) if arr[i,j]==token]


def estimate_recipe_costs(grid: Grid, recipes):
    """Compute costs using prioritized planning: agent1 plans full sequence, reservations applied, then agent2 plans.
    Each recipe treated as single task: agent(s) must visit dispensers for ingredients, then pot, then service. This is simplified: we create a waypoint sequence per agent."""
    from .planner import plan_sequence, build_reservations_from_path
    arr = grid.arr
    pots = find_positions(arr, 'P')
    onions = find_positions(arr, 'O')
    toms = find_positions(arr, 'T')
    service = find_positions(arr, 'S')
    spawns = find_positions(arr, '1') + find_positions(arr, '2')
    if len(spawns) < 2:
        return None

    results = []
    # for each recipe, create a naive assignment: all ingredients picked by agent1 (no exchange) vs split between two agents (with exchange)
    for recipe in recipes:
        # No-exchange: single-agent (spawn 1) collects all ingredients in sequence then pot then service
        # choose nearest dispensers per ingredient
        def nearest(srcs, ref):
            if not srcs: return None
            return min(srcs, key=lambda p: abs(p[0]-ref[0]) + abs(p[1]-ref[1]))

        # build waypoint list for single-agent
        start1 = spawns[0]
        waypoints1 = []
        cur = start1
        for ing in recipe:
            srcs = onions if ing=='onion' else toms
            pick = nearest(srcs, cur)
            if pick is None:
                waypoints1 = None; break
            waypoints1.append(pick)
            cur = pick
        if waypoints1 is None or not pots or not service:
            results.append({'recipe': recipe, 'cost_no_exchange': float('inf'), 'cost_with_exchange': float('inf'), 'exchange_gain': 0})
            continue
        waypoints1.append(pots[0])
        waypoints1.append(service[0])

        path1 = plan_sequence(arr, start1, waypoints1)
        if path1 is None:
            cost_no = float('inf')
        else:
            cost_no = len(path1)-1 + len(recipe)*2  # add pickup/drop/serve costs (approx)

    # With-exchange: split ingredients between both agents roughly half-half
        start2 = spawns[1]
        half = len(recipe)//2
        rec1 = recipe[:half]
        rec2 = recipe[half:]
        # agent1 waypoints
        way1 = []
        cur = start1
        for ing in rec1:
            srcs = onions if ing=='onion' else toms
            pick = nearest(srcs, cur)
            if pick is None:
                way1 = None; break
            way1.append(pick); cur = pick
        # agent2 waypoints
        way2 = []
        cur2 = start2
        for ing in rec2:
            srcs = onions if ing=='onion' else toms
            pick = nearest(srcs, cur2)
            if pick is None:
                way2 = None; break
            way2.append(pick); cur2 = pick
        if way1 is None or way2 is None:
            cost_with = float('inf')
        else:
            # append pot and service to one agent (simplification: agent1 delivers to pot then service)
            way1.append(pots[0]); way1.append(service[0])
            # prioritized planning: agent1 then agent2
            path_a1 = plan_sequence(arr, start1, way1)
            if path_a1 is None:
                cost_with = float('inf')
            else:
                reservations, edges = build_reservations_from_path(path_a1)
                path_a2 = plan_sequence(arr, start2, way2, reservations=reservations, edge_reservations=edges)
                if path_a2 is None:
                    cost_with = float('inf')
                else:
                    # simple exchange modeling: if there exists a Y adjacent to both agents' paths at similar times,
                    # allow an exchange with +1 cost; here we approximate by adding 1 when both agents have at least one move
                    exchange_extra = 1 if ('Y' in arr) or any(arr[x,y]=='Y' for x in range(arr.shape[0]) for y in range(arr.shape[1])) else 0
                    cost_with = max(len(path_a1)-1 + len(rec1)*2, len(path_a2)-1 + len(rec2)*2) + exchange_extra

        exchange_gain = cost_no - cost_with if (cost_no != float('inf') and cost_with != float('inf')) else 0
        results.append({'recipe': recipe, 'cost_no_exchange': cost_no, 'cost_with_exchange': cost_with, 'exchange_gain': exchange_gain})
    return results
