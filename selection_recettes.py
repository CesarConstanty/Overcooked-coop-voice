import random

# Paramètres
NB_ENSEMBLES = 100
NB_RECETTES_PAR_ENSEMBLE = 6
CIBLE_INGREDIENTS = 12
TOLERANCE = 2
INGREDIENTS = ["onion", "tomato"]

# Toutes les recettes possibles (1 à 3 ingrédients)
toutes_recettes = [
    ["onion"],
    ["tomato"],
    ["onion", "onion"],
    ["onion", "tomato"],
    ["tomato", "tomato"],
    ["onion", "onion", "onion"],
    ["onion", "onion", "tomato"],
    ["onion", "tomato", "tomato"],
    ["tomato", "tomato", "tomato"],
]

ensembles = []
ensembles_uniques = set()

while len(ensembles) < NB_ENSEMBLES:
    # Choisir des recettes uniques
    recettes = random.sample(toutes_recettes, NB_RECETTES_PAR_ENSEMBLE)

    # Vérifier le nombre total d'ingrédients
    total = sum(len(r) for r in recettes)
    if not (CIBLE_INGREDIENTS - TOLERANCE <= total <= CIBLE_INGREDIENTS + TOLERANCE):
        continue

    # Clé unique de l'ensemble (ordre indépendant)
    cle = tuple(sorted(tuple(r) for r in recettes))

    if cle not in ensembles_uniques:
        ensembles_uniques.add(cle)
        ensembles.append([{'ingredients': r} for r in recettes])

# Affichage
for i, e in enumerate(ensembles, 1):
    total = sum(len(r['ingredients']) for r in e)
    print(f"Ensemble {i} ({total} ingrédients)")
    print(e)
    print()