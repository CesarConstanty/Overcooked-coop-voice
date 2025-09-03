import itertools
import random
from typing import List, Dict
import json

INGS = ['onion', 'tomato']


def generate_recipe_pool(max_items=3) -> List[List[str]]:
    """Generate all combinations (with repetition) of INGS with length 1..max_items."""
    pool = []
    for k in range(1, max_items + 1):
        for comb in itertools.combinations_with_replacement(INGS, k):
            pool.append(list(comb))
    return pool


def pick_recipes_for_layout(n: int = 6, seed: int = None) -> List[List[str]]:
    pool = generate_recipe_pool(3)
    if seed is not None:
        random.seed(seed)
    if n > len(pool):
        raise ValueError('Requested more recipes than available in pool')
    # return recipes as lists (canonical sorted by ingredient)
    picks = random.sample(pool, n)
    return [sorted(r) for r in picks]


def save_recipes_json(path: str, recipes: List[List[str]], params: Dict = None):
    payload = {
        'recipes': recipes,
        'params': params or {}
    }
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)
