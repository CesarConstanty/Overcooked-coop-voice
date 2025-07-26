# Analyse de Distribution de Diversité des Ensembles de Recettes

## Vue d'ensemble

Cette fonctionnalité permet d'analyser et de visualiser **le nombre d'ensembles de recettes en fonction de la diversité de l'ensemble de ces ensembles de recettes**.

## Nouvelles fonctionnalités ajoutées

### 1. `calculate_set_diversity_distribution()`
- **But** : Calcule la distribution des scores de diversité pour tous les ensembles possibles
- **Entrée** : Nombre de combinaisons par ensemble, liste des combinaisons
- **Sortie** : Scores de diversité uniques et leurs fréquences

### 2. `visualize_diversity_distribution()`
- **But** : Visualise la distribution sous forme de graphiques
- **Graphiques générés** :
  - **Histogramme** : Nombre d'ensembles par score de diversité
  - **Distribution cumulative** : Pourcentage cumulé des ensembles
- **Statistiques affichées** :
  - Nombre total d'ensembles évalués
  - Score de diversité minimum/maximum/moyen
  - Top 5 des scores les plus fréquents
  - Pourcentage d'ensembles avec la diversité maximale

### 3. Options en ligne de commande
- `--diversity-distribution` : Affiche l'analyse de distribution
- `--save-distribution-plot` : Sauvegarde le graphique

## Exemples d'utilisation

### Via le script principal
```bash
# Analyse complète avec toutes les combinaisons
python3 recipe_generator.py --combination-size 4 --n-combinations 3 --any-score --diversity-distribution

# Sauvegarde du graphique
python3 recipe_generator.py --combination-size 4 --n-combinations 3 --any-score --diversity-distribution --save-distribution-plot ma_distribution.png
```

### Via les scripts de démonstration
```bash
# Démonstration interactive
python3 demo_diversity_distribution.py

# Comparaison entre différentes tailles d'ensembles
python3 compare_diversity_sizes.py
```

## Interprétation des résultats

### Exemple de résultats obtenus
Pour des ensembles de 3 combinaisons (à partir de 126 combinaisons totales) :
- **Total d'ensembles évalués** : 325,500
- **Score de diversité** : 3.0 - 9.0
- **Diversité moyenne** : 6.72
- **Ensembles avec diversité maximale** : 23,940 (7.35%)

### Distribution typique
1. **Score 7.0** : 90,720 ensembles (27.9%) - le plus fréquent
2. **Score 6.0** : 80,640 ensembles (24.8%)
3. **Score 8.0** : 74,340 ensembles (22.8%)
4. **Score 5.0** : 37,800 ensembles (11.6%)
5. **Score 9.0** : 23,940 ensembles (7.4%) - diversité maximale

### Comparaison par taille d'ensemble

| Taille | Total Sets | Moy Div | Min Div | Max Div |
|--------|------------|---------|---------|---------|
| 2      | 7,875      | 2.24    | 1.0     | 4.0     |
| 3      | 325,500    | 6.72    | 3.0     | 9.0     |
| 4      | 10,009,125 | 13.44   | 6.0     | 17.0    |

**Observations** :
- Plus la taille de l'ensemble augmente, plus la diversité moyenne augmente
- Le nombre total d'ensembles possibles croît de façon combinatoire
- La plage de diversité s'étend avec la taille de l'ensemble

## Applications pratiques

### 1. Optimisation expérimentale
- **Question** : "Combien d'ensembles ont une diversité élevée ?"
- **Réponse** : Visualisation montre que seulement 7.35% des ensembles ont la diversité maximale

### 2. Choix de paramètres
- **Question** : "Quelle taille d'ensemble optimise le rapport diversité/complexité ?"
- **Réponse** : Comparaison des distributions pour différentes tailles

### 3. Validation de sélection
- **Question** : "Notre algorithme sélectionne-t-il vraiment les ensembles les plus divers ?"
- **Réponse** : Vérification que les ensembles sélectionnés sont dans le top percentile

## Fichiers générés

1. **`analyse_rapide_diversite.png`** : Distribution pour analyse rapide
2. **`distribution_via_main.png`** : Distribution via script principal
3. **`comparaison_distributions_diversite.png`** : Comparaison multi-tailles

## Performance

- **Ensembles de 2** : ~7,875 évaluations (rapide)
- **Ensembles de 3** : ~325,500 évaluations (quelques secondes)
- **Ensembles de 4** : ~10M évaluations (plus lent mais faisable)

⚠️ **Note** : La complexité est combinatoire. Pour des analyses sur de grandes données, privilégier l'option "analyse rapide" ou réduire la taille des combinaisons.
