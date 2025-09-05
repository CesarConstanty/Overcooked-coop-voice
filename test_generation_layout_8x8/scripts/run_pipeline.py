#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline orchestrateur professionnel pour la génération de layouts Overcooked
- Gestion des 5 étapes du pipeline avec reprise possible
- Logging centralisé et gestion d'erreurs robuste
- Surveillance des ressources et optimisation automatique
- Rapports de progression et métriques de performance
"""

import argparse
import json
import logging
import sys
import time
import traceback
import psutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import multiprocessing as mp

# Configuration du logging principal
def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Configure le système de logging centralisé."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Logger principal
    logger = logging.getLogger("pipeline")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Supprimer les handlers existants
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formatter commun
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler fichier principal
    file_handler = logging.FileHandler(
        log_dir / f"pipeline_execution_{int(time.time())}.log"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler erreurs séparé
    error_handler = logging.FileHandler(
        log_dir / f"pipeline_errors_{int(time.time())}.log"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger

def setup_minimal_logging() -> logging.Logger:
    """Configuration logging minimal pour mode production."""
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.ERROR)
    
    # Handler console uniquement pour erreurs critiques
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger

class ResourceMonitor:
    """Moniteur des ressources système pour optimisation automatique."""
    
    def __init__(self):
        self.start_time = time.time()
        self.initial_memory = psutil.virtual_memory().percent
        self.initial_cpu = psutil.cpu_percent(interval=1)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques actuelles du système."""
        return {
            'memory_percent': psutil.virtual_memory().percent,
            'memory_available_gb': psutil.virtual_memory().available / (1024**3),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_count': psutil.cpu_count(),
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'elapsed_time': time.time() - self.start_time
        }
    
    def get_recommended_processes(self) -> int:
        """Recommande le nombre optimal de processus selon les ressources."""
        stats = self.get_current_stats()
        
        # Facteurs limitants
        cpu_limit = max(1, stats['cpu_count'] - 1)  # Laisser 1 CPU libre
        memory_limit = max(1, int(stats['memory_available_gb'] / 2))  # 2GB par processus
        
        # Adapter selon la charge actuelle
        if stats['memory_percent'] > 80:
            memory_limit = max(1, memory_limit // 2)
        
        if stats['cpu_percent'] > 80:
            cpu_limit = max(1, cpu_limit // 2)
        
        return min(cpu_limit, memory_limit, 8)  # Max 8 processus

class PipelineStep:
    """Représentation d'une étape du pipeline."""
    
    def __init__(self, step_id: int, name: str, script_path: str, description: str):
        self.step_id = step_id
        self.name = name
        self.script_path = script_path
        self.description = description
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status = "pending"  # pending, running, completed, failed, skipped
        self.error_message = ""
        self.output_files: List[str] = []
        self.metrics: Dict[str, Any] = {}
    
    @property
    def duration(self) -> Optional[float]:
        """Durée d'exécution de l'étape."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """Vérifie si l'étape est terminée avec succès."""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Vérifie si l'étape a échoué."""
        return self.status == "failed"

class ProfessionalPipelineOrchestrator:
    """Orchestrateur principal du pipeline professionnel."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise l'orchestrateur."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Dossiers
        self.outputs_dir = self.base_dir / "outputs"
        
        # Mode production
        self.production_mode = self.config.get("production_mode", {})
        self.is_production = self.production_mode.get("enabled", False)
        
        if self.is_production:
            print(f"🏭 Mode production activé")
        
        # Logging adapté au mode
        if self.is_production and self.production_mode.get("minimal_logging", True):
            log_level = "ERROR"
            self.logs_dir = None  # Pas de fichiers de log en production
        else:
            log_level = self.config.get("pipeline_config", {}).get("logging", {}).get("level", "INFO")
            self.logs_dir = self.outputs_dir / "logs" / "step_logs"
        
        self.logger = setup_logging(self.logs_dir, log_level) if self.logs_dir else setup_minimal_logging()
        
        # Scripts directory
        self.scripts_dir = self.base_dir / "scripts"
        
        # Monitoring
        self.resource_monitor = ResourceMonitor()
        
        # Définition des étapes
        self.steps = [
            PipelineStep(0, "Recipe Generation", "0_recipe_generator.py", 
                        "Génération des combinaisons de recettes"),
            PipelineStep(1, "Layout Generation", "1_layout_generator.py", 
                        "Génération massive des layouts avec formes canoniques"),
            PipelineStep(2, "Layout Evaluation", "2_layout_evaluator.py", 
                        "Évaluation massive - chaque layout avec chaque groupe de recettes"),
            PipelineStep(3, "Results Analysis", "3_results_analyzer.py", 
                        "Analyse statistique et ranking des résultats d'évaluation"),
            PipelineStep(4, "Final Selection", "4_final_selector.py", 
                        "Sélection finale selon critères pondérés et formatage .layout")
        ]
        
        # État du pipeline
        self.pipeline_start_time: Optional[float] = None
        self.pipeline_end_time: Optional[float] = None
        self.total_errors = 0
        self.execution_metadata: Dict[str, Any] = {}
        
        self.logger.info("🚀 Pipeline orchestrateur initialisé")
        self.logger.info(f"📁 Base: {self.base_dir}")
        self.logger.info(f"📋 Configuration: {self.config_file}")
        self.logger.info(f"📊 {len(self.steps)} étapes configurées")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def validate_environment(self) -> bool:
        """Valide l'environnement avant exécution."""
        self.logger.info("🔍 Validation de l'environnement...")
        
        issues = []
        
        # Vérifier les scripts
        for step in self.steps:
            script_path = self.scripts_dir / step.script_path
            if not script_path.exists():
                issues.append(f"Script manquant: {script_path}")
        
        # Vérifier les dossiers de sortie
        if not self.outputs_dir.exists():
            issues.append(f"Dossier outputs manquant: {self.outputs_dir}")
        
        # Vérifier les ressources système
        stats = self.resource_monitor.get_current_stats()
        if stats['memory_available_gb'] < 1:
            issues.append(f"Mémoire insuffisante: {stats['memory_available_gb']:.1f}GB disponible")
        
        if stats['disk_usage_percent'] > 90:
            issues.append(f"Espace disque insuffisant: {stats['disk_usage_percent']:.1f}% utilisé")
        
        # Vérifier les dépendances Python
        try:
            import numpy, matplotlib, seaborn, pandas
        except ImportError as e:
            issues.append(f"Dépendance Python manquante: {e}")
        
        if issues:
            self.logger.error("❌ Problèmes d'environnement détectés:")
            for issue in issues:
                self.logger.error(f"  • {issue}")
            return False
        
        self.logger.info("✅ Environnement validé")
        return True
    
    def execute_step(self, step: PipelineStep, force: bool = False) -> bool:
        """Exécute une étape du pipeline."""
        
        # Vérifier si déjà terminée (sauf si force)
        if step.is_completed and not force:
            self.logger.info(f"⏭️ Étape {step.step_id} déjà terminée, passage à la suivante")
            step.status = "skipped"
            return True
        
        self.logger.info(f"🚀 Démarrage étape {step.step_id}: {step.name}")
        self.logger.info(f"📝 {step.description}")
        
        step.start_time = time.time()
        step.status = "running"
        
        script_path = self.scripts_dir / step.script_path
        
        try:
            # Préparer les arguments
            cmd = [sys.executable, str(script_path)]
            
            # Ajouter arguments spécifiques
            if step.step_id == 1:  # Layout generator
                recommended_processes = self.resource_monitor.get_recommended_processes()
                cmd.extend(["--processes", str(recommended_processes)])
                self.logger.info(f"🔧 Processus recommandés: {recommended_processes}")
            
            # Configurer les variables d'environnement
            env = {
                **dict(os.environ),
                'PYTHONPATH': str(self.base_dir),
                'PIPELINE_STEP': str(step.step_id),
                'PIPELINE_BASE_DIR': str(self.base_dir)
            }
            
            # Exécuter le script
            self.logger.info(f"💻 Commande: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.config.get("pipeline_config", {}).get("timeouts", {}).get(f"step_{step.step_id}", 3600)
            )
            
            step.end_time = time.time()
            
            # Analyser le résultat
            if result.returncode == 0:
                step.status = "completed"
                self.logger.info(f"✅ Étape {step.step_id} terminée avec succès ({step.duration:.1f}s)")
                
                # Logger la sortie si demandé
                if result.stdout and self.logger.level <= logging.DEBUG:
                    self.logger.debug(f"Sortie étape {step.step_id}:\n{result.stdout}")
                
                return True
            else:
                step.status = "failed"
                step.error_message = result.stderr or "Erreur inconnue"
                self.logger.error(f"❌ Étape {step.step_id} échouée (code: {result.returncode})")
                self.logger.error(f"Erreur: {step.error_message}")
                
                if result.stdout:
                    self.logger.error(f"Sortie: {result.stdout}")
                
                return False
                
        except subprocess.TimeoutExpired:
            step.end_time = time.time()
            step.status = "failed"
            step.error_message = "Timeout dépassé"
            self.logger.error(f"⏰ Étape {step.step_id} timeout après {step.duration:.1f}s")
            return False
            
        except Exception as e:
            step.end_time = time.time()
            step.status = "failed"
            step.error_message = str(e)
            self.logger.error(f"💥 Erreur étape {step.step_id}: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def run_pipeline(self, start_step: int = 0, end_step: Optional[int] = None, 
                    force: bool = False) -> bool:
        """Exécute le pipeline complet ou partiellement."""
        
        self.pipeline_start_time = time.time()
        
        if end_step is None:
            end_step = len(self.steps) - 1
        
        self.logger.info("🎬 Démarrage du pipeline de génération de layouts")
        self.logger.info(f"📊 Étapes {start_step} à {end_step}")
        self.logger.info(f"🔄 Force rebuild: {force}")
        
        # Validation environnement
        if not self.validate_environment():
            self.logger.error("❌ Échec validation environnement")
            return False
        
        # Statistiques initiales
        initial_stats = self.resource_monitor.get_current_stats()
        self.logger.info(f"💾 Mémoire: {initial_stats['memory_percent']:.1f}% | CPU: {initial_stats['cpu_percent']:.1f}%")
        
        # Exécution des étapes
        success = True
        
        for i in range(start_step, end_step + 1):
            if i >= len(self.steps):
                self.logger.warning(f"⚠️ Étape {i} n'existe pas (max: {len(self.steps) - 1})")
                continue
            
            step = self.steps[i]
            
            # Surveiller les ressources avant chaque étape
            current_stats = self.resource_monitor.get_current_stats()
            if current_stats['memory_percent'] > 85:
                self.logger.warning(f"⚠️ Mémoire élevée: {current_stats['memory_percent']:.1f}%")
            
            # Exécuter l'étape
            step_success = self.execute_step(step, force)
            
            if not step_success:
                self.total_errors += 1
                success = False
                
                # Décider si continuer ou arrêter
                if self.config.get("pipeline_config", {}).get("execution", {}).get("stop_on_error", True):
                    self.logger.error(f"🛑 Arrêt du pipeline suite à l'échec de l'étape {i}")
                    break
                else:
                    self.logger.warning(f"⚠️ Continuation malgré l'échec de l'étape {i}")
        
        self.pipeline_end_time = time.time()
        
        # Nettoyage en mode production
        if self.is_production and self.production_mode.get("cleanup_intermediate_files", True):
            self.cleanup_intermediate_files()
        
        # Rapport final
        self.generate_execution_report()
        
        if success:
            self.logger.info("🎉 Pipeline terminé avec succès!")
        else:
            self.logger.error(f"💥 Pipeline terminé avec {self.total_errors} erreurs")
        
        return success
    
    def generate_execution_report(self):
        """Génère un rapport d'exécution détaillé."""
        
        total_duration = self.pipeline_end_time - self.pipeline_start_time if self.pipeline_end_time else 0
        final_stats = self.resource_monitor.get_current_stats()
        
        report = {
            'execution_info': {
                'start_time': self.pipeline_start_time,
                'end_time': self.pipeline_end_time,
                'total_duration': total_duration,
                'total_errors': self.total_errors,
                'execution_date': datetime.now().isoformat()
            },
            'resource_usage': {
                'initial_stats': {
                    'memory_percent': self.resource_monitor.initial_memory,
                    'cpu_percent': self.resource_monitor.initial_cpu
                },
                'final_stats': final_stats
            },
            'steps_summary': []
        }
        
        # Résumé des étapes
        for step in self.steps:
            step_info = {
                'step_id': step.step_id,
                'name': step.name,
                'status': step.status,
                'duration': step.duration,
                'error_message': step.error_message
            }
            report['steps_summary'].append(step_info)
        
        # Sauvegarder le rapport
        if self.logs_dir:  # Seulement si logs_dir existe (pas en mode production minimal)
            report_file = self.logs_dir / f"execution_report_{int(time.time())}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"📄 Rapport sauvegardé: {report_file}")
        
        # Rapport texte pour le log
        self.logger.info("📊 Rapport d'exécution:")
        self.logger.info(f"  ⏱️ Durée totale: {total_duration:.1f}s ({total_duration/60:.1f}min)")
        self.logger.info(f"  ❌ Erreurs: {self.total_errors}")
        self.logger.info(f"  💾 Mémoire finale: {final_stats['memory_percent']:.1f}%")
        self.logger.info(f"  💻 CPU final: {final_stats['cpu_percent']:.1f}%")
        
        # Détail des étapes
        for step in self.steps:
            status_emoji = {"completed": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏸️"}
            emoji = status_emoji.get(step.status, "❓")
            duration_str = f"{step.duration:.1f}s" if step.duration else "N/A"
            self.logger.info(f"  {emoji} Étape {step.step_id}: {step.name} ({duration_str})")
    
    def cleanup_intermediate_files(self):
        """Nettoie les fichiers intermédiaires en mode production pour optimiser l'espace disque."""
        if not self.is_production:
            return
        
        essential_outputs = self.production_mode.get("essential_outputs", ["final_layouts", "summary_report"])
        cleanup_dirs = []
        
        self.logger.info("🧹 Nettoyage des fichiers intermédiaires...")
        
        # Déterminer les dossiers à nettoyer
        if "final_layouts" not in essential_outputs:
            cleanup_dirs.append("layouts_selectionnes")
        
        if "summary_report" not in essential_outputs:
            cleanup_dirs.append("selection_analysis")
        
        # Toujours nettoyer les fichiers intermédiaires lourds
        cleanup_dirs.extend([
            "layouts_generes",      # Layouts bruts générés (remplacés par sélectionnés)
            "detailed_evaluation",  # Évaluations détaillées (gardé que résumé)
            "trajectoires_layouts", # Trajectoires détaillées
            "recipe_combinations",  # Recettes temporaires
            "analysis_results",     # Analyses intermédiaires
            "logs"                  # Logs de debug
        ])
        
        files_removed = 0
        space_freed = 0
        
        for cleanup_dir in cleanup_dirs:
            dir_path = self.outputs_dir / cleanup_dir
            if dir_path.exists():
                try:
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            files_removed += 1
                            space_freed += file_size
                    
                    # Supprimer les dossiers vides
                    for dir_path in sorted(dir_path.rglob("*"), key=lambda p: str(p), reverse=True):
                        if dir_path.is_dir() and not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur nettoyage {cleanup_dir}: {e}")
        
        space_freed_mb = space_freed / (1024 * 1024)
        self.logger.info(f"🧹 Nettoyage terminé: {files_removed} fichiers supprimés, {space_freed_mb:.1f}MB libérés")

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(
        description="Pipeline orchestrateur professionnel pour layouts Overcooked",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python run_pipeline.py                    # Pipeline complet
  python run_pipeline.py --start 2          # À partir de l'étape 2
  python run_pipeline.py --start 1 --end 3 # Étapes 1 à 3 seulement
  python run_pipeline.py --force            # Forcer la re-exécution
  python run_pipeline.py --step 2           # Étape 2 uniquement
        """
    )
    
    parser.add_argument("--config", default="config/pipeline_config.json",
                       help="Fichier de configuration")
    parser.add_argument("--start", type=int, default=0,
                       help="Étape de démarrage (0-4)")
    parser.add_argument("--end", type=int, 
                       help="Étape de fin (0-4)")
    parser.add_argument("--step", type=int,
                       help="Exécuter une seule étape")
    parser.add_argument("--force", action="store_true",
                       help="Forcer la re-exécution des étapes terminées")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulation sans exécution réelle")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       default="INFO", help="Niveau de logging")
    
    args = parser.parse_args()
    
    try:
        # Mode étape unique
        if args.step is not None:
            args.start = args.step
            args.end = args.step
        
        # Validation des arguments
        if args.start < 0 or args.start > 4:
            print("❌ Étape de démarrage invalide (0-4)")
            return 1
        
        if args.end is not None and (args.end < args.start or args.end > 4):
            print("❌ Étape de fin invalide")
            return 1
        
        # Initialiser le pipeline
        orchestrator = ProfessionalPipelineOrchestrator(args.config)
        
        if args.dry_run:
            print("🔍 Mode simulation - aucune exécution réelle")
            print(f"📊 Étapes planifiées: {args.start} à {args.end or 4}")
            return 0
        
        # Exécuter le pipeline
        success = orchestrator.run_pipeline(
            start_step=args.start,
            end_step=args.end,
            force=args.force
        )
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Interruption utilisateur")
        return 130
    except Exception as e:
        print(f"💥 Erreur critique: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import os
    exit(main())
