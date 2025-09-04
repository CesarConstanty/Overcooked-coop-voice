#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de démonstration du pipeline configuré
Teste le système complet avec configuration
"""

import json
from pathlib import Path

def create_demo_config():
    """Crée une configuration de démonstration."""
    base_dir = Path(__file__).parent
    config_file = base_dir / "demo_config.json"
    
    demo_config = {
        "pipeline_config": {
            "generation": {
                "total_layouts_to_generate": 500,
                "processes": 4,
                "batch_size": 125
            },
            "evaluation": {
                "recipe_group_sample_size": 20,
                "layout_sample_size": 50,
                "processes": 4
            },
            "selection": {
                "final_layouts_count": 10,
                "criteria": {
                    "cooperation_gain": {"weight": 0.5},
                    "efficiency": {"weight": 0.3},
                    "exchanges": {"weight": 0.2}
                },
                "diversity": {
                    "ensure_layout_diversity": True,
                    "max_layouts_per_recipe_group": 2
                }
            },
            "output": {
                "final_layouts_dir": "layouts_finaux_demo"
            }
        },
        "quality_thresholds": {
            "min_cooperation_gain": 25.0,
            "min_connectivity_score": 0.7,
            "min_distance_efficiency": 0.5
        }
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(demo_config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Configuration de démonstration créée: {config_file}")
    return config_file

def show_pipeline_usage():
    """Affiche les exemples d'utilisation du pipeline."""
    print(f"""
🚀 PIPELINE DE GÉNÉRATION DE LAYOUTS - GUIDE D'UTILISATION
=========================================================

📄 Configuration:
   Le pipeline utilise un fichier de configuration JSON pour tous les paramètres.
   Par défaut: pipeline_config.json

🎯 Modes d'exécution:

1. 🧪 Test rapide:
   python run_pipeline.py --quick-test
   
2. 🏭 Pipeline de production:
   python run_pipeline.py --production
   
3. 🔧 Étape spécifique:
   python run_pipeline.py --step 0    # Génération des recettes
   python run_pipeline.py --step 1    # Génération des layouts
   python run_pipeline.py --step 2    # Évaluation exhaustive
   python run_pipeline.py --step 3    # Analyse des résultats
   python run_pipeline.py --step 4    # Sélection finale

4. ⚙️  Configuration personnalisée:
   python run_pipeline.py --config demo_config.json

📊 Structure de configuration:

{
  "pipeline_config": {
    "generation": {
      "total_layouts_to_generate": 10000,  // Nombre de layouts à générer
      "processes": 4,                      // Processus parallèles
      "batch_size": 250                    // Taille des batches
    },
    "evaluation": {
      "recipe_group_sample_size": 50,      // Échantillon de groupes de recettes
      "layout_sample_size": 100,           // Échantillon de layouts à évaluer
      "processes": 4                       // Processus parallèles
    },
    "selection": {
      "final_layouts_count": 50,           // Nombre final de layouts
      "criteria": {
        "cooperation_gain": {"weight": 0.4}, // Poids gain coopération
        "efficiency": {"weight": 0.35},      // Poids efficacité
        "exchanges": {"weight": 0.25}        // Poids échanges
      },
      "diversity": {
        "ensure_layout_diversity": true,     // Assurer diversité
        "max_layouts_per_recipe_group": 3   // Max par groupe recettes
      }
    },
    "output": {
      "final_layouts_dir": "layouts_finaux" // Dossier de sortie
    }
  },
  "quality_thresholds": {
    "min_cooperation_gain": 30.0,           // Seuil min gain coopération (%)
    "min_connectivity_score": 0.8,          // Seuil min connectivité (0-1)
    "min_distance_efficiency": 0.6          // Seuil min efficacité distance (0-1)
  }
}

🎯 Sorties du pipeline:

📁 outputs/
   ├── recipe_groups/           # Groupes de recettes générés
   ├── validated_layouts/       # Layouts validés générés
   ├── exhaustive_evaluation/   # Résultats d'évaluation
   ├── analysis_results/        # Analyses et statistiques
   └── layouts_finaux/          # Layouts sélectionnés au format final
       ├── layout_001_*.layout  # Layouts individuels
       ├── layout_002_*.layout
       ├── ...
       └── selection_report_*.json  # Rapport de sélection

✨ Avantages du système:

1. 🔧 Configuration flexible: Tous les paramètres via fichier JSON
2. 🚀 Exécution modulaire: Étapes individuelles ou pipeline complet
3. 📊 Sélection intelligente: Critères pondérés et diversité assurée
4. 🎯 Sortie finale: Layouts prêts à l'emploi au format attendu
5. 📈 Métriques détaillées: Coopération, efficacité, échanges
6. 🔍 Validation complète: Connectivité, accessibilité, qualité

🏁 Résultat final:
   X layouts optimisés pour la coopération humain-IA, sélectionnés
   selon vos critères et sauvegardés au format prêt à l'emploi.
""")

def main():
    """Fonction principale de démonstration."""
    print(f"🧪 DÉMONSTRATION DU PIPELINE CONFIGURÉ")
    print("="*50)
    
    # Créer config de démo
    config_file = create_demo_config()
    
    # Afficher le guide d'utilisation
    show_pipeline_usage()
    
    print(f"\n🎯 Pour lancer la démonstration:")
    print(f"   python run_pipeline.py --config {config_file.name} --quick-test")
    
    print(f"\n🏭 Pour lancer la production:")
    print(f"   python run_pipeline.py --config {config_file.name} --production")

if __name__ == "__main__":
    main()
