#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script principal pour lancer le pipeline de génération et d'évaluation de layouts
Combine tous les scripts en un seul point d'entrée avec configuration
"""

import sys
import time
import json
import argparse
import subprocess
from pathlib import Path

class PipelineLauncher:
    """Lanceur principal du pipeline avec support de configuration."""
    
    def __init__(self, config_file="pipeline_config.json"):
        """
        Initialise le lanceur.
        
        Args:
            config_file: Fichier de configuration
        """
        self.base_dir = Path(__file__).parent
        self.scripts_dir = self.base_dir / "scripts"
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        print(f"🚀 Pipeline Launcher initialisé")
        print(f"📁 Dossier: {self.base_dir}")
        print(f"📁 Scripts: {self.scripts_dir}")
        print(f"📄 Configuration: {self.config_file.name}")
    
    def load_config(self):
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            # Créer une configuration par défaut
            default_config = {
                "pipeline_config": {
                    "generation": {
                        "total_layouts_to_generate": 1000,
                        "processes": 4,
                        "batch_size": 250
                    },
                    "evaluation": {
                        "recipe_group_sample_size": 50,
                        "layout_sample_size": 100,
                        "processes": 4
                    },
                    "selection": {
                        "final_layouts_count": 20,
                        "criteria": {
                            "cooperation_gain": {"weight": 0.4},
                            "efficiency": {"weight": 0.35},
                            "exchanges": {"weight": 0.25}
                        },
                        "diversity": {
                            "ensure_layout_diversity": True,
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
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Configuration par défaut créée: {self.config_file.name}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"✅ Configuration chargée")
        return config
    
    def run_script_command(self, cmd, description):
        """Exécute une commande de script."""
        print(f"💻 {description}...")
        print(f"🔧 Commande: {' '.join(cmd)}")
        
        start_time = time.time()
        result = subprocess.run(cmd, cwd=self.base_dir)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} terminé en {duration:.1f}s")
            return True
        else:
            print(f"❌ Échec de {description}")
            return False
    
    def run_step_0_recipes(self):
        """Lance l'étape 0: Génération des groupes de recettes."""
        print(f"\n🍳 ÉTAPE 0: GÉNÉRATION DES GROUPES DE RECETTES")
        print("="*60)
        
        script_path = self.scripts_dir / "0_recipe_generator.py"
        cmd = [sys.executable, str(script_path)]
        
        return self.run_script_command(cmd, "Génération des groupes de recettes")
    
    def run_step_1_generation(self):
        """Lance l'étape 1: Génération de layouts."""
        print(f"\n📋 ÉTAPE 1: GÉNÉRATION DE LAYOUTS")
        print("="*50)
        
        gen_config = self.config["pipeline_config"]["generation"]
        total_layouts = gen_config["total_layouts_to_generate"]
        processes = gen_config["processes"]
        batch_size = gen_config.get("batch_size", 250)
        
        print(f"🎯 Objectif: {total_layouts:,} layouts")
        print(f"⚙️  Processus: {processes}")
        print(f"📦 Taille batch: {batch_size}")
        
        script_path = self.scripts_dir / "1_layout_generator.py"
        # Convertir le count en millions
        millions = total_layouts / 1_000_000
        cmd = [
            sys.executable, str(script_path),
            "--millions", str(millions),
            "--processes", str(processes)
        ]
        
        return self.run_script_command(cmd, "Génération de layouts")
    
    def run_step_2_evaluation(self):
        """Lance l'étape 2: Évaluation exhaustive."""
        print(f"\n🎯 ÉTAPE 2: ÉVALUATION EXHAUSTIVE")
        print("="*60)
        
        eval_config = self.config["pipeline_config"]["evaluation"]
        
        script_path = self.scripts_dir / "2_layout_evaluator.py"
        cmd = [
            sys.executable, str(script_path),
            "--processes", str(eval_config["processes"])
        ]
        
        if eval_config.get("layout_sample_size"):
            cmd.extend(["--layout-sample", str(eval_config["layout_sample_size"])])
        
        if eval_config.get("recipe_group_sample_size"):
            cmd.extend(["--recipe-group-sample", str(eval_config["recipe_group_sample_size"])])
        
        return self.run_script_command(cmd, "Évaluation exhaustive")
    
    def run_step_3_analysis(self):
        """Lance l'étape 3: Analyse des résultats."""
        print(f"\n📊 ÉTAPE 3: ANALYSE DES RÉSULTATS")
        print("="*50)
        
        script_path = self.scripts_dir / "3_result_analyzer.py"
        cmd = [sys.executable, str(script_path)]
        
        return self.run_script_command(cmd, "Analyse des résultats")
    
    def run_step_4_selection(self):
        """Lance l'étape 4: Sélection finale."""
        print(f"\n🎯 ÉTAPE 4: SÉLECTION FINALE")
        print("="*50)
        
        script_path = self.scripts_dir / "4_final_selector.py"
        cmd = [
            sys.executable, str(script_path),
            "--config", str(self.config_file)
        ]
        
        return self.run_script_command(cmd, "Sélection finale")
    
    def run_full_pipeline(self):
        """Lance le pipeline complet."""
        print(f"🚀 LANCEMENT DU PIPELINE COMPLET")
        print("="*80)
        
        start_time = time.time()
        steps_success = []
        
        # Configuration
        selection_config = self.config["pipeline_config"]["selection"]
        output_config = self.config["pipeline_config"]["output"]
        print(f"🎯 Objectif final: {selection_config['final_layouts_count']} layouts sélectionnés")
        print(f"📁 Dossier de sortie: {output_config['final_layouts_dir']}")
        
        # Étape 0: Génération des recettes
        if self.run_step_0_recipes():
            steps_success.append("0_recipes")
        else:
            print("❌ Échec à l'étape 0")
            return False
        
        # Étape 1: Génération des layouts
        if self.run_step_1_generation():
            steps_success.append("1_generation")
        else:
            print("❌ Échec à l'étape 1")
            return False
        
        # Étape 2: Évaluation
        if self.run_step_2_evaluation():
            steps_success.append("2_evaluation")
        else:
            print("❌ Échec à l'étape 2")
            return False
        
        # Étape 3: Analyse
        if self.run_step_3_analysis():
            steps_success.append("3_analysis")
        else:
            print("❌ Échec à l'étape 3")
            return False
        
        # Étape 4: Sélection finale
        if self.run_step_4_selection():
            steps_success.append("4_selection")
        else:
            print("❌ Échec à l'étape 4")
            return False
        
        total_duration = time.time() - start_time
        
        print(f"\n🎉 PIPELINE COMPLET TERMINÉ!")
        print("="*50)
        print(f"⏱️  Durée totale: {total_duration/60:.1f} minutes")
        print(f"✅ Étapes réussies: {', '.join(steps_success)}")
        
        final_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["final_layouts_dir"]
        if final_dir.exists():
            layout_files = list(final_dir.glob("*.layout"))
            print(f"📄 {len(layout_files)} layouts finaux générés dans {final_dir}")
        
        return True
    
    def run_production_pipeline(self):
        """Lance le pipeline de production complet selon la configuration."""
        print(f"🏭 PIPELINE DE PRODUCTION")
        print("="*50)
        
        gen_config = self.config["pipeline_config"]["generation"]
        eval_config = self.config["pipeline_config"]["evaluation"]
        selection_config = self.config["pipeline_config"]["selection"]
        
        print(f"📊 Configuration de production:")
        print(f"   • Layouts à générer: {gen_config['total_layouts_to_generate']:,}")
        print(f"   • Processus: {gen_config['processes']}")
        print(f"   • Échantillon évaluation: {eval_config.get('layout_sample_size', 'tous')} layouts")
        print(f"   • Sélection finale: {selection_config['final_layouts_count']} layouts")
        
        return self.run_full_pipeline()
    
    def run_quick_test(self):
        """Lance un test rapide du pipeline."""
        print(f"⚡ TEST RAPIDE DU PIPELINE")
        print("="*40)
        
        # Sauvegarder la config originale
        original_config = self.config.copy()
        
        # Configuration réduite pour test
        self.config["pipeline_config"]["generation"]["total_layouts_to_generate"] = 100
        self.config["pipeline_config"]["generation"]["processes"] = 2
        self.config["pipeline_config"]["evaluation"]["layout_sample_size"] = 20
        self.config["pipeline_config"]["evaluation"]["recipe_group_sample_size"] = 10
        self.config["pipeline_config"]["selection"]["final_layouts_count"] = 5
        
        print(f"🧪 Configuration de test:")
        print(f"   • 100 layouts générés")
        print(f"   • 20 layouts évalués")
        print(f"   • 10 groupes de recettes")
        print(f"   • 5 layouts finaux sélectionnés")
        
        success = self.run_full_pipeline()
        
        # Restaurer la config
        self.config = original_config
        
        return success

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Pipeline de génération et d'évaluation de layouts")
    parser.add_argument("--config", default="pipeline_config.json",
                       help="Fichier de configuration (défaut: pipeline_config.json)")
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--full", action="store_true",
                           help="Lance le pipeline complet selon la configuration")
    mode_group.add_argument("--production", action="store_true",
                           help="Lance le pipeline de production")
    mode_group.add_argument("--quick-test", action="store_true",
                           help="Lance un test rapide du pipeline")
    mode_group.add_argument("--step", type=str, choices=["0", "1", "2", "3", "4"],
                           help="Lance une étape spécifique (0-4)")
    
    args = parser.parse_args()
    
    try:
        launcher = PipelineLauncher(args.config)
        
        if args.step:
            # Exécuter une étape spécifique
            step_methods = {
                "0": launcher.run_step_0_recipes,
                "1": launcher.run_step_1_generation,
                "2": launcher.run_step_2_evaluation,
                "3": launcher.run_step_3_analysis,
                "4": launcher.run_step_4_selection
            }
            
            success = step_methods[args.step]()
            
        elif args.quick_test:
            success = launcher.run_quick_test()
            
        elif args.production:
            success = launcher.run_production_pipeline()
            
        elif args.full:
            success = launcher.run_full_pipeline()
            
        else:
            # Par défaut: pipeline complet
            success = launcher.run_full_pipeline()
        
        if success:
            print("✅ Opération terminée avec succès!")
        else:
            print("❌ Échec de l'opération")
            exit(1)
            
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
