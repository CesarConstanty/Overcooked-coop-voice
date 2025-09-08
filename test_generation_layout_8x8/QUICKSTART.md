# 🚀 Guide de Démarrage Rapide - Pipeline Overcooked

> **Temps estimé**: 10 minutes  
> **Prérequis**: Python 3.8+, 4GB RAM libre

## ⚡ Installation Express

```bash
# 1. Installer dépendances
pip install numpy matplotlib seaborn pandas psutil

# 2. Vérifier environnement
python scripts/run_pipeline.py --dry-run

# 3. Exécuter pipeline complet
python scripts/run_pipeline.py
```

## 🎯 Utilisation Basique

### **Commandes Essentielles**

```bash
# Pipeline complet (recommandé)
python scripts/run_pipeline.py

# Étape unique (test rapide)
python scripts/run_pipeline.py --step 0

# Mode debug (troubleshooting)
python scripts/run_pipeline.py --log-level DEBUG
```

### **Résultats Principaux**

Après exécution, vérifiez :

```bash
# Layouts sélectionnés (objectif principal)
ls outputs/layouts_selectionnes/

# Rapports d'analyse
ls outputs/selection_analysis/

# Logs d'exécution
ls outputs/logs/step_logs/
```

## ⚙️ Configuration Rapide

### **Paramètres Fréquents**

Éditez `config/pipeline_config.json` :

```json
{
  "layout_generation": {
    "max_layouts_per_recipe": 1000,    // Réduire pour tests rapides
    "grid_size": [7, 7]                // Taille grille plus petite
  },
  "pipeline_config": {
    "selection": {
      "max_layouts_selected": 20       // Moins de layouts finaux
    }
  }
}
```

## 📊 Comprendre les Résultats

### **Métriques Clés**

- **Score Composite** : 0.0 (mauvais) → 1.0 (excellent)
- **Steps Duo** : Plus bas = meilleur (efficacité)
- **Gain Coopération** : Plus haut = meilleur (intérêt collaboration)
- **Échanges** : 1-3 optimal (complexité équilibrée)

### **Fichiers Importants**

```
outputs/
├── layouts_selectionnes/              # 🎯 RÉSULTATS FINAUX
│   └── selected_*.json
├── selection_analysis/                # 📊 ANALYSES
│   ├── selection_report_*.md         # Rapport lisible
│   └── selection_plots/              # Graphiques
└── logs/                             # 🔍 DEBUG
    └── step_logs/
```

## 🔧 Problèmes Courants

### ❌ **Mémoire insuffisante**
```bash
# Solution : Réduire la charge
# Dans config/pipeline_config.json :
"max_layouts_per_recipe": 500
"multiprocessing": {"enabled": false}
```

### ❌ **Processus trop lent**
```bash
# Solution : Mode test rapide
python scripts/run_pipeline.py --step 0  # Test recettes seulement
python scripts/run_pipeline.py --start 1 --end 1  # Layouts seulement
```

### ❌ **Erreurs de dépendances**
```bash
# Solution : Réinstaller environnement
pip install --upgrade numpy matplotlib seaborn pandas psutil
```

## 🎮 Cas d'Usage Rapides

### **Test Concept (5 min)**
```bash
# Configuration minimale pour test
python scripts/run_pipeline.py --step 0 --step 1
# Vérifie que le système fonctionne
```

### **Génération Production (30-60 min)**
```bash
# Configuration complète
python scripts/run_pipeline.py --log-level INFO
# Génère layouts prêts pour le jeu
```

### **Debug Problème (selon besoin)**
```bash
# Investigation détaillée
python scripts/run_pipeline.py --step X --log-level DEBUG
# X = étape qui pose problème
```

## 📈 Optimisation Performance

### **Système Rapide** (16GB+ RAM, 8+ cores)
```json
{
  "max_layouts_per_recipe": 500000,
  "multiprocessing": {"enabled": true, "processes": 8}
}
```

### **Système Modeste** (8GB RAM, 4 cores)
```json
{
  "max_layouts_per_recipe": 50000,
  "multiprocessing": {"enabled": true, "processes": 4}
}
```

### **Système Minimal** (4GB RAM, 2 cores)
```json
{
  "max_layouts_per_recipe": 5000,
  "multiprocessing": {"enabled": false}
}
```

## 🎯 Objectifs par Étape

| Étape | Objectif | Temps Typique | Vérification |
|-------|----------|---------------|--------------|
| **0** | Générer recettes | < 1s | `outputs/recipe_combinations/` |
| **1** | Créer layouts | 5-30min | `outputs/layouts_generes/` |
| **2** | Évaluer performance | 10-60min | `outputs/detailed_evaluation/` |
| **3** | Analyser résultats | 1-5min | `outputs/analysis_results/` |
| **4** | Sélectionner finaux | < 1min | `outputs/layouts_selectionnes/` |

## 💡 Conseils Pratiques

1. **🔍 Toujours commencer par `--dry-run`** pour valider config
2. **📊 Surveiller logs** pendant exécution longue
3. **💾 Vérifier espace disque** avant lancement (>2GB libre)
4. **⚡ Ajuster parallélisme** selon ressources disponibles
5. **📈 Analyser métriques** dans rapports générés

## 🆘 Support Express

### **Commandes de Debug**
```bash
# Statut environnement
python scripts/run_pipeline.py --dry-run

# Logs temps réel
tail -f outputs/logs/step_logs/pipeline_execution_*.log

# Vérification fichiers générés
find outputs/ -name "*.json" | head -10
```

### **Logs Utiles**
```bash
# Erreurs critiques
grep "ERROR\|CRITICAL" outputs/logs/step_logs/*.log

# Performance métriques  
grep "Mémoire\|CPU\|Duration" outputs/logs/step_logs/*.log

# Résultats finaux
grep "layouts sélectionnés\|terminé avec succès" outputs/logs/step_logs/*.log
```

---

**🎉 Succès** : Si vous voyez `🎉 Pipeline terminé avec succès!` dans les logs, vos layouts sont prêts dans `outputs/layouts_selectionnes/`

**📚 Documentation complète** : Voir `README.md` pour détails avancés

**🔄 Mise à jour** : Pipeline auto-documenté, configuration trackée dans `outputs/STRUCTURE.json`
