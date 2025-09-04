# Pipeline de Génération de Layouts Overcooked 8x8

## 🎯 Vue d'ensemble

Ce pipeline automatise la génération, l'évaluation et la sélection de layouts optimisés pour la coopération humain-IA dans Overcooked. Il utilise un système de configuration centralisé pour un contrôle précis de tous les paramètres.

## 🏗️ Architecture du Pipeline

### Étapes du Pipeline

1. **🍳 Étape 0: Génération des groupes de recettes**
   - Génère 924 groupes uniques de 6 recettes différentes
   - Élimine les doublons fonctionnels
   - Output: `outputs/recipe_groups/`

2. **📋 Étape 1: Génération des layouts**
   - Génère X layouts validés (configurable)
   - Validation complète de connectivité
   - Vérification d'accessibilité des objets
   - Output: `outputs/validated_layouts/`

3. **🎯 Étape 2: Évaluation exhaustive**
   - Évalue les combinaisons layout × groupe de recettes
   - Calcule les métriques de coopération
   - Performance: 100,000+ évaluations/seconde
   - Output: `outputs/exhaustive_evaluation/`

4. **📊 Étape 3: Analyse des résultats**
   - Analyse statistique des évaluations
   - Identification des meilleures combinaisons
   - Génération de rapports détaillés
   - Output: `outputs/analysis_results/`

5. **🎯 Étape 4: Sélection finale**
   - Sélectionne les X meilleurs layouts selon critères
   - Assure la diversité des groupes de recettes
   - Génère layouts au format final
   - Output: `outputs/layouts_finaux/`

## ⚙️ Configuration

### Fichier de Configuration (`pipeline_config.json`)

```json
{
  "pipeline_config": {
    "generation": {
      "total_layouts_to_generate": 10000,
      "processes": 4,
      "batch_size": 250
    },
    "evaluation": {
      "recipe_group_sample_size": 50,
      "layout_sample_size": 100,
      "processes": 4
    },
    "selection": {
      "final_layouts_count": 50,
      "criteria": {
        "cooperation_gain": {"weight": 0.4},
        "efficiency": {"weight": 0.35},
        "exchanges": {"weight": 0.25}
      },
      "diversity": {
        "ensure_layout_diversity": true,
        "max_layouts_per_recipe_group": 3
      }
    },
    "output": {
      "final_layouts_dir": "layouts_finaux"
    }
  },
  "quality_thresholds": {
    "min_cooperation_gain": 30.0,
    "min_connectivity_score": 0.8,
    "min_distance_efficiency": 0.6
  }
}
```

### Paramètres Clés

- **`total_layouts_to_generate`**: Nombre de layouts à générer
- **`final_layouts_count`**: Nombre de layouts dans la sélection finale
- **`criteria.*.weight`**: Poids des critères de sélection (somme = 1.0)
- **`quality_thresholds`**: Seuils minimaux de qualité

## 🚀 Utilisation

### Modes d'Exécution

```bash
# Test rapide (paramètres réduits)
python run_pipeline.py --quick-test

# Pipeline de production (selon configuration)
python run_pipeline.py --production

# Pipeline complet (par défaut)
python run_pipeline.py

# Étape spécifique
python run_pipeline.py --step 1  # Génération layouts
python run_pipeline.py --step 4  # Sélection finale

# Configuration personnalisée
python run_pipeline.py --config ma_config.json
```

### Démonstration

```bash
# Créer configuration de démonstration
python demo_pipeline.py

# Lancer la démonstration
python run_pipeline.py --config demo_config.json --quick-test
```

## 📊 Métriques d'Évaluation

### Critères de Coopération

1. **Gain de Coopération** (`cooperation_gain`)
   - Pourcentage d'amélioration duo vs. solo
   - Poids par défaut: 0.4

2. **Efficacité** (`efficiency`)
   - Nombre d'étapes pour terminer en duo
   - Inversement proportionnel (moins = mieux)
   - Poids par défaut: 0.35

3. **Potentiel d'Échanges** (`exchanges`)
   - Nombre d'échanges d'objets possibles
   - Poids par défaut: 0.25

### Seuils de Qualité

- **Gain coopération minimal**: 30%
- **Score connectivité minimal**: 0.8
- **Efficacité distance minimale**: 0.6

## 📁 Structure des Sorties

```
outputs/
├── recipe_groups/
│   └── recipe_groups_*.json           # 924 groupes de recettes
├── validated_layouts/
│   └── validated_layouts_*.json       # Layouts générés et validés
├── exhaustive_evaluation/
│   └── exhaustive_evaluation_*.json   # Évaluations complètes
├── analysis_results/
│   └── analysis_report_*.json         # Analyses statistiques
└── layouts_finaux/
    ├── layout_001_*.layout            # Layouts sélectionnés
    ├── layout_002_*.layout
    ├── ...
    └── selection_report_*.json        # Rapport de sélection
```

## 🔧 Composants Techniques

### Scripts Principaux

- **`run_pipeline.py`**: Lanceur unique avec support configuration
- **`scripts/0_recipe_generator.py`**: Génération groupes de recettes
- **`scripts/1_layout_generator.py`**: Génération layouts validés
- **`scripts/2_layout_evaluator.py`**: Évaluation exhaustive
- **`scripts/3_result_analyzer.py`**: Analyse des résultats
- **`scripts/4_final_selector.py`**: Sélection finale

### Classes Clés

- **`ValidatedLayoutGenerator8x8`**: Génération avec validation complète
- **`ExhaustiveEvaluator`**: Évaluation haute performance
- **`FinalLayoutSelector`**: Sélection selon critères pondérés

## 🎯 Avantages du Système

1. **🔧 Configuration Centralisée**: Tous les paramètres dans un fichier JSON
2. **🚀 Exécution Modulaire**: Étapes individuelles ou pipeline complet
3. **📊 Sélection Intelligente**: Critères pondérés configurable
4. **🎯 Diversité Assurée**: Distribution équilibrée des groupes de recettes
5. **📈 Performance Optimisée**: Génération 2000+ layouts/sec, évaluation 100k+/sec
6. **🔍 Validation Complète**: Connectivité, accessibilité, qualité garanties

## 🏁 Résultat Final

Le pipeline produit X layouts optimisés pour la coopération humain-IA, sélectionnés selon vos critères de qualité et de performance, prêts à l'emploi au format `.layout` standard.

### Format de Sortie

Chaque layout final contient:
- **Grille validée** avec connectivité complète
- **Métriques de coopération** calculées
- **Métadonnées** de sélection et d'évaluation
- **Configuration** des recettes et paramètres MDP

Les layouts sont immédiatement utilisables dans l'environnement Overcooked pour des expériences de coopération humain-IA.
