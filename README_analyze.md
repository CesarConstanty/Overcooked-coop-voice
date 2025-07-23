# Analyse des Résultats Overcooked

Ce répertoire contient des outils pour analyser les résultats d'évaluation des layouts Overcooked produits par le système d'évaluation.

## Installation des dépendances

Installez d'abord les dépendances nécessaires :

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Installer les dépendances d'analyse
pip install -r requirements_analyze.txt
```

## Scripts disponibles

### 1. `analyze_evaluation_results.py` - Script principal d'analyse

Script complet pour analyser les fichiers de résultats JSON.

#### Utilisation de base

```bash
# Analyse simple d'un fichier
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py layout_evaluation_coop.json

# Analyse avec sauvegarde du rapport
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py layout_evaluation_coop.json --report rapport.txt

# Comparaison entre plusieurs modes
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py --compare layout_evaluation_solo.json layout_evaluation_coop.json

# Analyse détaillée (si données disponibles)
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py --detailed layout_evaluation_detailed.json

# Analyse sans graphiques (plus rapide)
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py layout_evaluation_coop.json --no-plots
```

#### Options disponibles

- `--compare` : Compare plusieurs modes d'évaluation
- `--detailed` : Analyse détaillée avec parties individuelles (si disponible)
- `--report FICHIER` : Sauvegarde le rapport dans un fichier
- `--plots DOSSIER` : Répertoire pour les graphiques (défaut: analysis_plots)
- `--no-plots` : Désactive la génération de graphiques
- `--help` : Affiche l'aide complète

### 2. `analyze_evaluation_results_simple.py` - Version simplifiée

Version sans dépendances externes pour une analyse rapide.

```bash
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results_simple.py layout_evaluation_coop.json
```

### 3. `examples_analysis.py` - Exemples interactifs

Script pour tester différents exemples d'utilisation.

```bash
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python examples_analysis.py
```

## Types d'analyses disponibles

### Analyse agrégée (par défaut)

Analyse les résultats globaux par layout :
- Taux de viabilité et de complétion
- Métriques de performance (steps moyens, efficacité)
- Caractéristiques comportementales (difficulté, coordination)
- Insights comportementaux globaux
- Corrélations de performance

### Analyse détaillée

Analyse les parties individuelles (si données disponibles) :
- Statistiques par partie
- Analyse des événements détaillée
- Performance individuelle des agents
- Patterns de coordination
- Efficacité des actions

### Comparaison de modes

Compare différents modes d'évaluation :
- Performance relative par layout
- Différences comportementales
- Adaptation des layouts aux différents modes

## Formats de données supportés

Le script analyse les fichiers JSON produits par `layout_evaluator_final.py` :

- **Format agrégé** : Résultats globaux par layout
- **Format détaillé** : Inclut les parties individuelles avec `info_sum`
- **Compatibilité** : Format compatible avec 2_0_0.json

## Sorties générées

### Rapport textuel

Rapport complet incluant :
- Résumé général de l'évaluation
- Performance détaillée par layout
- Insights comportementaux
- Corrélations et patterns

### Graphiques (si matplotlib disponible)

- Distribution des taux de complétion
- Distribution des scores d'efficacité
- Corrélations difficulté vs performance
- Histogrammes des métriques clés

### Fichiers de sortie

- `rapport_[nom].txt` : Rapport textuel (si --report spécifié)
- `analysis_plots/` : Répertoire des graphiques
  - `completion_rates.png` : Taux de complétion par layout
  - `efficiency_distribution.png` : Distribution des efficacités
  - `difficulty_vs_steps.png` : Corrélation difficulté/performance

## Exemples d'utilisation courante

### Analyser les résultats d'une évaluation

```bash
# Analyse complète avec rapport et graphiques
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py layout_evaluation_coop.json --report rapport_coop.txt

# Analyse rapide sans graphiques
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py layout_evaluation_coop.json --no-plots
```

### Comparer différents modes

```bash
# Comparer solo vs coopératif
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py --compare layout_evaluation_solo.json layout_evaluation_coop.json --report comparaison.txt
```

### Analyse pour la recherche

```bash
# Analyse détaillée pour recherche comportementale
/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python analyze_evaluation_results.py --detailed layout_evaluation_detailed.json --report recherche_comportementale.txt
```

## Dépendances

Les dépendances sont listées dans `requirements_analyze.txt` :

- **pandas** : Manipulation de données
- **numpy** : Calculs numériques  
- **matplotlib** : Graphiques de base
- **seaborn** : Graphiques statistiques avancés
- **scipy** : Analyses statistiques

## Intégration avec le workflow

Ce script s'intègre parfaitement avec :
1. `layout_evaluator_final.py` - Génération des données
2. Les notebooks Jupyter - Analyse interactive
3. Les scripts d'évaluation automatisée

Les données produites sont compatibles avec les formats d'analyse existants pour assurer la continuité de la recherche.
