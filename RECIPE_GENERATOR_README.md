# Recipe Generator for Overcooked Cognitive Science Experiments

Ce module permet de générer des ensembles diversifiés de recettes pour le jeu Overcooked, spécialement conçu pour les expériences en sciences cognitives.

## Fonctionnalités

- **Génération de combinaisons** : Crée toutes les combinaisons possibles de recettes avec une taille paramétrable
- **Filtrage par valeur** : Sélectionne les combinaisons ayant une valeur totale d'ingrédients spécifique
- **Analyse de diversité** : Calcule la diversité entre les combinaisons de recettes
- **Sélection optimale** : Choisit les combinaisons les plus diverses pour maximiser la variété expérimentale
- **Visualisation** : Génère des matrices de diversité sous forme de heatmaps
- **Export flexible** : Sauvegarde les résultats en format JSON

## Installation

Assurez-vous d'avoir les dépendances suivantes installées :

```bash
pip install numpy matplotlib overcooked_ai_py
```

## Utilisation

### Utilisation en ligne de commande

```bash
# Utilisation basique avec les paramètres par défaut
python recipe_generator.py

# Personnalisation des paramètres
python recipe_generator.py --combination-size 6 --target-value 14 --n-combinations 5

# Export en JSON et visualisation
python recipe_generator.py --output-json results.json --visualize --save-plot diversity.png

# Aide complète
python recipe_generator.py --help
```

### Utilisation programmatique

```python
from recipe_generator import RecipeGenerator

# Initialiser le générateur
generator = RecipeGenerator(onion_value=1, tomato_value=1)

# Générer des combinaisons de 6 recettes
generator.generate_combinations(combination_size=6)

# Filtrer par valeur totale
filtered_orders = generator.filter_by_value(target_value=14)

# Sélectionner les 5 combinaisons les plus diverses
selected_recipes, indices = generator.select_most_diverse_combinations(n_combinations=5)

# Afficher les résultats
generator.print_selected_recipes(selected_recipes)

# Exporter en JSON
generator.export_to_json(selected_recipes, "my_recipes.json")
```

## Paramètres disponibles

### Paramètres de ligne de commande

- `--combination-size` : Nombre de recettes par combinaison (défaut: 6)
- `--target-value` : Valeur totale cible pour les combinaisons (défaut: 14)
- `--n-combinations` : Nombre de combinaisons diverses à sélectionner (défaut: 5)
- `--onion-value` : Valeur des ingrédients oignon (défaut: 1)
- `--tomato-value` : Valeur des ingrédients tomate (défaut: 1)
- `--output-json` : Chemin pour sauvegarder les résultats en JSON
- `--visualize` : Afficher la matrice de diversité
- `--save-plot` : Sauvegarder la visualisation de la matrice

### Configuration via JSON

Utilisez le fichier `recipe_config.json` pour définir plusieurs conditions expérimentales :

```json
{
  "experimental_conditions": {
    "condition_1": {
      "combination_size": 6,
      "target_value": 12,
      "n_combinations": 3,
      "description": "Condition de faible complexité"
    }
  }
}
```

## Exemples

### Exemple 1 : Génération basique

```python
# Voir example_usage.py pour des exemples complets
python example_usage.py
```

### Exemple 2 : Conditions expérimentales multiples

```python
# Traitement de plusieurs conditions avec des paramètres différents
for target_value in [12, 14, 16]:
    generator = RecipeGenerator()
    generator.generate_combinations(combination_size=6)
    filtered_orders = generator.filter_by_value(target_value=target_value)
    
    if filtered_orders:
        selected_recipes, _ = generator.select_most_diverse_combinations(n_combinations=3)
        generator.export_to_json(selected_recipes, f"recipes_value_{target_value}.json")
```

## Méthode de calcul de la diversité

La diversité entre deux combinaisons de recettes est calculée comme le nombre de recettes différentes entre elles. La sélection des combinaisons les plus diverses maximise la somme totale des différences par paires entre toutes les combinaisons sélectionnées.

## Format de sortie

Les recettes sont exportées au format JSON avec la structure suivante :

```json
{
  "metadata": {
    "onion_value": 1,
    "tomato_value": 1,
    "total_combinations": 5,
    "recipes_per_combination": 6
  },
  "recipe_combinations": [
    [
      {"ingredients": ["onion", "tomato"]},
      {"ingredients": ["onion", "onion"]},
      ...
    ]
  ]
}
```

## Développement

### Structure du code

- `RecipeGenerator` : Classe principale pour la génération et l'analyse
- `main()` : Interface en ligne de commande
- `example_usage.py` : Exemples d'utilisation
- `recipe_config.json` : Configuration des conditions expérimentales

### Tests

Pour tester le module :

```bash
python recipe_generator.py --n-combinations 3 --visualize
```

## Contribution

Ce module a été développé pour des expériences en sciences cognitives utilisant le jeu Overcooked. Les contributions sont les bienvenues pour améliorer les algorithmes de diversité ou ajouter de nouvelles fonctionnalités d'analyse.
