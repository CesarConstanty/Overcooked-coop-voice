# Pipeline Professionnel de Génération de Layouts Overcooked

> **Version**: 2.0.0 Professional Edition  
> **Auteur**: Pipeline de Génération Automatisée  
> **Date**: Décembre 2024  

## 🎯 Vue d'Ensemble

Ce pipeline professionnel génère automatiquement des layouts optimisés pour le jeu Overcooked en utilisant une approche systématique en 5 étapes. Il est capable de traiter des millions de layouts avec une sélection intelligente basée sur 3 critères pondérés : nombre d'étapes en duo, gain de coopération, et nombre d'échanges utilisés.

### ✨ Caractéristiques Principales

- **🔄 Pipeline en 5 étapes** : Génération → Layouts → Évaluation → Analyse → Sélection
- **⚡ Haute Performance** : Multiprocessing optimisé avec monitoring des ressources
- **📊 Sélection Intelligente** : 3 critères pondérés avec visualisations 3D
- **🎨 Visualisations Avancées** : Graphiques statistiques et analyses détaillées
- **📝 Logging Professionnel** : Traçabilité complète et debugging facilité
- **🔧 Configuration Flexible** : Paramètres ajustables via JSON
- **📂 Organisation Structurée** : Dossiers de sortie hiérarchisés professionnels

## 🏗️ Architecture du Pipeline

```
📁 test_generation_layout_8x8/
├── 📋 config/
│   └── pipeline_config.json          # Configuration centrale
├── 🔧 scripts/
│   ├── 0_recipe_generator.py          # Étape 0: Génération recettes
│   ├── 1_layout_generator.py          # Étape 1: Génération layouts
│   ├── 2_layout_evaluator.py          # Étape 2: Évaluation simulations
│   ├── 3_results_analyzer.py          # Étape 3: Analyse & visualisations
│   ├── 4_final_selector.py            # Étape 4: Sélection finale
│   └── run_pipeline.py                # 🚀 Orchestrateur principal
├── 📊 outputs/
│   ├── recipe_combinations/           # Combinaisons de recettes (étape 0)
│   ├── layouts_generes/               # Layouts générés (étape 1)
│   ├── detailed_evaluation/           # Évaluations détaillées (étape 2)
│   ├── analysis_results/              # Analyses et insights (étape 3)
│   ├── layouts_selectionnes/          # Layouts finaux sélectionnés (étape 4)
│   ├── trajectoires_layouts/          # Trajectoires détaillées
│   ├── selection_analysis/            # Analyses de sélection
│   └── logs/                         # Logs du pipeline
└── 📚 documentation/                  # Guides et documentation
```

## 🚀 Démarrage Rapide

### 1. **Installation des Dépendances**

```bash
pip install numpy matplotlib seaborn pandas psutil
```

### 2. **Exécution Pipeline Complet**

```bash
# Pipeline complet (toutes les étapes)
python scripts/run_pipeline.py

# Pipeline avec logging détaillé
python scripts/run_pipeline.py --log-level DEBUG
```

### 3. **Exécutions Partielles**

```bash
# Étape unique
python scripts/run_pipeline.py --step 0

# Range d'étapes
python scripts/run_pipeline.py --start 1 --end 3

# Forcer la re-exécution
python scripts/run_pipeline.py --force
```

### 4. **Mode Simulation**

```bash
# Test sans exécution réelle
python scripts/run_pipeline.py --dry-run
```

## 📋 Guide des Étapes

### **Étape 0: Génération des Recettes** 📝

**Script**: `0_recipe_generator.py`  
**Sortie**: `outputs/recipe_combinations/`

Génère toutes les combinaisons possibles de recettes (1-3 ingrédients) et crée des groupes de 6 recettes uniques.

**Résultats typiques**:
- 9 recettes uniques (oignons/tomates)
- 84 groupes de 6 recettes
- Performance: ~3000 groupes/seconde

**Configuration**:
```json
"recipe_config": {
    "min_ingredients_per_recipe": 1,
    "max_ingredients_per_recipe": 3,
    "allowed_ingredients": ["onion", "tomato"],
    "group_size": 6
}
```

### **Étape 1: Génération des Layouts** 🗺️

**Script**: `1_layout_generator.py`  
**Sortie**: `outputs/layouts_generes/`

Génère des millions de layouts valides avec déduplication par formes canoniques.

**Fonctionnalités**:
- ✅ Validation BFS des layouts (accessibilité)
- 🔄 Déduplication par formes canoniques (rotations/symétries)
- ⚡ Multiprocessing optimisé avec monitoring ressources
- 📊 Estimation de progrès en temps réel

**Configuration**:
```json
"layout_generation": {
    "grid_size": [8, 8],
    "max_layouts_per_recipe": 100000,
    "multiprocessing": {
        "enabled": true,
        "chunk_size": 1000
    }
}
```

### **Étape 2: Évaluation des Layouts** 🧪

**Script**: `2_layout_evaluator.py`  
**Sortie**: `outputs/detailed_evaluation/`

Évalue les layouts avec simulation BFS réelle et calcul des métriques de performance.

**Métriques Calculées**:
- 🎯 Nombre d'étapes solo vs duo
- 📈 Pourcentage de gain de coopération  
- 🔄 Nombre d'échanges utilisés
- ⚡ Taux de réussite des simulations
- 🏃 Temps d'exécution moyen

**Optimisations**:
- Mode lightweight pour évaluation rapide
- Trajectoires détaillées on-demand pour layouts sélectionnés
- Gestion mémoire optimisée pour millions de layouts

### **Étape 3: Analyse des Résultats** 📊

**Script**: `3_results_analyzer.py`  
**Sortie**: `outputs/analysis_results/`

Génère analyses statistiques complètes et visualisations.

**Analyses Générées**:
- 📈 Histogrammes de distribution des métriques
- 🌊 Heatmaps de corrélation entre variables
- 📊 Box plots comparatifs
- 🎯 Analyses de tendances et insights
- 📝 Rapports markdown détaillés

### **Étape 4: Sélection Finale** 🎯

**Script**: `4_final_selector.py`  
**Sortie**: `outputs/layouts_selectionnes/` & `outputs/selection_analysis/`

Sélectionne les meilleurs layouts selon 3 critères pondérés.

**Critères de Sélection**:
1. **Nombre d'étapes duo** (40%) - *À minimiser*
2. **Gain de coopération** (35%) - *À maximiser*  
3. **Échanges utilisés** (25%) - *À optimiser dans range 1-3*

**Visualisations 3D**:
- Scatter plot 3D des critères
- Matrices de corrélation
- Analyses comparatives sélectionnés vs tous
- Distributions des scores composites

## ⚙️ Configuration Avancée

### **Fichier Principal**: `config/pipeline_config.json`

```json
{
  "pipeline_config": {
    "execution": {
      "stop_on_error": true,
      "parallel_processing": true
    },
    "selection": {
      "max_layouts_selected": 50,
      "selection_criteria": {
        "duo_steps": {
          "weight": 0.4,
          "minimize": true
        },
        "cooperation_gain_percent": {
          "weight": 0.35,
          "maximize": true  
        },
        "exchanges_used": {
          "weight": 0.25,
          "target_range": [1, 3]
        }
      },
      "filtering": {
        "min_success_rate": 0.8,
        "min_cooperation_gain": 10.0,
        "max_duo_steps": 200
      }
    }
  }
}
```

### **Optimisation des Performances**

```json
"performance": {
  "multiprocessing": {
    "enabled": true,
    "processes": "auto",
    "chunk_size": 1000
  },
  "memory_management": {
    "max_memory_percent": 85,
    "cleanup_frequency": 1000
  }
}
```

## 📊 Métriques et Monitoring

### **Surveillance des Ressources**

Le pipeline surveille automatiquement :
- 💾 **Utilisation mémoire** (alerte à 85%)
- 💻 **Charge CPU** (adaptation dynamique du parallélisme)
- 💿 **Espace disque** (vérification avant exécution)
- ⏱️ **Temps d'exécution** (timeouts configurables)

### **Métriques de Performance Typiques**

| Étape | Temps Typique | Mémoire Peak | CPU Utilisation |
|-------|---------------|--------------|-----------------|
| 0 - Recettes | < 1s | < 50MB | Faible |
| 1 - Layouts | 5-30min | 2-8GB | Haute |
| 2 - Évaluation | 10-60min | 1-4GB | Très haute |
| 3 - Analyse | 1-5min | 500MB | Moyenne |
| 4 - Sélection | < 1min | 200MB | Faible |

## 🔧 Troubleshooting

### **Problèmes Courants**

#### ❌ **Erreur: Mémoire insuffisante**
```bash
# Réduire le parallélisme
python scripts/run_pipeline.py --start 1 
# Puis éditer config pour réduire processes
```

#### ❌ **Timeout sur l'évaluation**
```bash
# Augmenter les timeouts dans config
"timeouts": {
  "step_2": 7200  # 2 heures
}
```

#### ❌ **Layouts invalides générés**
```bash
# Vérifier la validation BFS
python scripts/1_layout_generator.py --validate-only
```

### **Logging et Debug**

```bash
# Debug complet
python scripts/run_pipeline.py --log-level DEBUG

# Logs spécifiques
tail -f outputs/logs/step_logs/pipeline_execution_*.log

# Erreurs uniquement  
tail -f outputs/logs/step_logs/pipeline_errors_*.log
```

## 📈 Résultats et Interprétation

### **Sorties Principales**

1. **Layouts Sélectionnés** (`outputs/layouts_selectionnes/`)
   - 🏆 Top performers selon critères pondérés
   - 📁 Organisés par type et performance
   - 🔄 Prêts pour intégration jeu

2. **Trajectoires Détaillées** (`outputs/trajectoires_layouts/`)
   - 🛤️ Chemins optimaux solo et duo
   - 📊 Données de comparaison détaillées
   - ⚡ Optimisations possibles

3. **Analyses Statistiques** (`outputs/analysis_results/`)
   - 📈 Insights sur les patterns de performance
   - 🎯 Recommendations d'optimisation
   - 📊 Métriques de qualité globale

### **Critères de Qualité**

Un layout de **haute qualité** présente :
- 🎯 **Score composite > 0.7** (normalisé)
- ⚡ **Steps duo < 50** (efficacité)
- 📈 **Gain coopération > 25%** (intérêt collaboration)
- 🔄 **1-3 échanges** (complexité optimale)
- ✅ **Taux réussite > 90%** (fiabilité)

## 🔄 Workflow de Développement

### **Test du Pipeline**

```bash
# Test rapide avec dataset réduit
python scripts/run_pipeline.py --dry-run

# Test étape par étape
for i in {0..4}; do
  python scripts/run_pipeline.py --step $i
done

# Test performance avec monitoring
python scripts/run_pipeline.py --log-level INFO
```

### **Customisation Avancée**

1. **Nouveaux Critères de Sélection**
   - Modifier `4_final_selector.py`
   - Ajouter critères dans `SelectionCriteria`
   - Mettre à jour visualisations

2. **Algorithmes d'Évaluation**
   - Étendre `OvercookedSimulator` 
   - Implémenter nouveaux pathfinding
   - Ajouter métriques personnalisées

3. **Visualisations Personnalisées**
   - Étendre `LayoutVisualizer`
   - Ajouter nouveaux types de plots
   - Exporter formats additionnels

## 📝 Changelog

### **Version 2.0.0** (Décembre 2024)
- ✨ Pipeline professionnel complet
- 🎯 Sélection basée sur 3 critères pondérés  
- 📊 Visualisations 3D et analyses avancées
- ⚡ Optimisations performance et mémoire
- 🔧 Configuration flexible et monitoring
- 📂 Structure de dossiers professionnelle

### **Version 1.x** (Précédent)
- 🔧 Scripts de base et fonctionnalités initiales

## 🤝 Support et Contribution

### **Signalement de Bugs**

1. Vérifier les logs dans `outputs/logs/`
2. Reproduire avec `--log-level DEBUG`  
3. Inclure configuration et métriques système

### **Requests de Fonctionnalités**

Les améliorations peuvent inclure :
- 🎮 Support de nouveaux types de jeux
- 📊 Algorithmes d'évaluation avancés  
- 🎨 Nouvelles visualisations
- ⚡ Optimisations performance

---

## 📚 Références Techniques

### **Algorithmes Utilisés**

- **BFS (Breadth-First Search)** : Validation layouts et pathfinding
- **Canonical Forms** : Déduplication par symétries/rotations
- **Min-Max Normalization** : Normalisation des critères de sélection
- **Weighted Scoring** : Agrégation pondérée des critères multiples

### **Optimisations Implémentées**

- **Multiprocessing Pool** : Parallélisation CPU-intensive tasks
- **Memory Mapping** : Gestion efficace grands datasets
- **Lazy Loading** : Chargement données on-demand
- **Resource Monitoring** : Adaptation dynamique ressources

---

*📧 Pour questions techniques ou support : consultez les logs détaillés et la documentation intégrée dans `outputs/`*

*🔄 Pipeline mis à jour automatiquement - Version tracking dans `outputs/STRUCTURE.json`*
