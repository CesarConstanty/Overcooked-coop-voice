#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de création de la structure de dossiers professionnelle
pour le pipeline de génération de layouts Overcooked
"""

import os
from pathlib import Path
import json
import time
from datetime import datetime

def create_directory_structure():
    """Crée la structure de dossiers complète pour le pipeline."""
    
    base_dir = Path(__file__).parent.parent
    outputs_dir = base_dir / "outputs"
    
    print(f"🏗️ Création de la structure de dossiers professionnelle")
    print(f"📁 Base: {base_dir}")
    print(f"📁 Outputs: {outputs_dir}")
    
    # Structure des dossiers
    structure = {
        "outputs": {
            "description": "Dossier principal des résultats du pipeline",
            "subdirs": {
                "recipe_combinations": {
                    "description": "Combinaisons de recettes générées (étape 0)",
                    "subdirs": {}
                },
                "layouts_generes": {
                    "description": "Layouts générés bruts (étape 1)",
                    "subdirs": {
                        "grid_7x7": "Layouts 7x7",
                        "grid_8x8": "Layouts 8x8", 
                        "grid_9x9": "Layouts 9x9",
                        "canonical_forms": "Formes canoniques déduplicates"
                    }
                },
                "detailed_evaluation": {
                    "description": "Évaluations détaillées des layouts (étape 2)",
                    "subdirs": {
                        "simulation_results": "Résultats de simulation détaillés",
                        "performance_metrics": "Métriques de performance",
                        "trajectory_data": "Données de trajectoires",
                        "error_logs": "Logs d'erreurs de simulation"
                    }
                },
                "analysis_results": {
                    "description": "Analyses et insights (étape 3)",
                    "subdirs": {
                        "statistical_analysis": "Analyses statistiques",
                        "visualizations": "Graphiques et visualisations",
                        "insights_reports": "Rapports d'insights",
                        "performance_comparisons": "Comparaisons de performance"
                    }
                },
                "layouts_selectionnes": {
                    "description": "Layouts finaux sélectionnés (étape 4)",
                    "subdirs": {
                        "top_performers": "Meilleurs performers selon critères",
                        "diverse_selection": "Sélection diversifiée",
                        "specialized_layouts": "Layouts spécialisés par type"
                    }
                },
                "trajectoires_layouts": {
                    "description": "Trajectoires détaillées des layouts sélectionnés",
                    "subdirs": {
                        "duo_trajectories": "Trajectoires en mode duo",
                        "solo_trajectories": "Trajectoires en mode solo", 
                        "comparison_data": "Données de comparaison",
                        "optimization_paths": "Chemins d'optimisation"
                    }
                },
                "selection_analysis": {
                    "description": "Analyses de la sélection finale",
                    "subdirs": {
                        "selection_plots": "Graphiques de sélection",
                        "criteria_analysis": "Analyse des critères",
                        "reports": "Rapports de sélection",
                        "export_data": "Données d'export"
                    }
                },
                "logs": {
                    "description": "Logs du pipeline",
                    "subdirs": {
                        "step_logs": "Logs par étape",
                        "error_logs": "Logs d'erreurs",
                        "performance_logs": "Logs de performance",
                        "debug_logs": "Logs de debug"
                    }
                },
                "cache": {
                    "description": "Cache et données temporaires",
                    "subdirs": {
                        "layout_cache": "Cache des layouts",
                        "simulation_cache": "Cache des simulations",
                        "computation_cache": "Cache des calculs",
                        "temp_data": "Données temporaires"
                    }
                }
            }
        },
        "documentation": {
            "description": "Documentation du pipeline",
            "subdirs": {
                "user_guides": "Guides utilisateur",
                "technical_docs": "Documentation technique",
                "examples": "Exemples d'utilisation",
                "troubleshooting": "Guide de dépannage"
            }
        }
    }
    
    # Créer les dossiers
    created_dirs = []
    
    def create_recursive(base_path, structure_dict):
        """Crée récursivement la structure de dossiers."""
        for dir_name, content in structure_dict.items():
            if dir_name == "description":
                continue
                
            dir_path = base_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dir_path)
            
            # Créer README.md avec description
            if isinstance(content, dict):
                description = content.get("description", f"Dossier {dir_name}")
                readme_path = dir_path / "README.md"
                if not readme_path.exists():
                    readme_content = f"""# {dir_name.replace('_', ' ').title()}

{description}

Créé le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Structure

"""
                    # Ajouter sous-dossiers si présents
                    if "subdirs" in content:
                        for subdir, subdesc in content["subdirs"].items():
                            readme_content += f"- **{subdir}**: {subdesc}\n"
                    
                    readme_content += f"""

## Utilisation

Ce dossier fait partie du pipeline de génération de layouts Overcooked.
Consultez la documentation principale pour plus d'informations.

---
*Généré automatiquement par le pipeline*
"""
                    
                    with open(readme_path, 'w', encoding='utf-8') as f:
                        f.write(readme_content)
                
                # Récursion pour les sous-dossiers
                if "subdirs" in content:
                    create_recursive(dir_path, content["subdirs"])
    
    # Créer la structure
    create_recursive(base_dir, structure)
    
    # Créer fichier de structure globale
    structure_file = outputs_dir / "STRUCTURE.json"
    structure_info = {
        "created_at": time.time(),
        "created_date": datetime.now().isoformat(),
        "base_directory": str(base_dir),
        "total_directories": len(created_dirs),
        "directories": [str(d.relative_to(base_dir)) for d in created_dirs],
        "structure": structure
    }
    
    with open(structure_file, 'w', encoding='utf-8') as f:
        json.dump(structure_info, f, indent=2, ensure_ascii=False)
    
    # Créer .gitkeep dans les dossiers vides
    for dir_path in created_dirs:
        if not any(dir_path.iterdir()):
            gitkeep = dir_path / ".gitkeep"
            gitkeep.touch()
    
    print(f"✅ Structure créée avec succès:")
    print(f"  📁 {len(created_dirs)} dossiers créés")
    print(f"  📄 Documentation automatique générée")
    print(f"  📋 Structure sauvegardée: {structure_file}")
    
    # Afficher l'arbre des dossiers principaux
    print(f"\n🌳 Structure créée:")
    for dir_path in sorted(created_dirs):
        if dir_path.parent == outputs_dir:
            level = "├── " if dir_path != sorted([d for d in created_dirs if d.parent == outputs_dir])[-1] else "└── "
            print(f"  {level}{dir_path.name}/")
            
            # Afficher les sous-dossiers principaux
            subdirs = [d for d in created_dirs if d.parent == dir_path]
            for i, subdir in enumerate(sorted(subdirs)):
                is_last = i == len(subdirs) - 1
                sublevel = "    └── " if is_last else "    ├── "
                print(f"  {sublevel}{subdir.name}/")
    
    return structure_info

if __name__ == "__main__":
    create_directory_structure()
