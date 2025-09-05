#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validation et test du pipeline professionnel
Vérifie que tous les composants fonctionnent correctement
"""

import json
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

def run_command(cmd: List[str], cwd: Path = None, timeout: int = 60) -> Tuple[bool, str, str]:
    """Exécute une commande et retourne le résultat."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout dépassé"
    except Exception as e:
        return False, "", str(e)

def check_dependencies() -> bool:
    """Vérifie les dépendances Python."""
    print("🔍 Vérification des dépendances...")
    
    required_modules = [
        'numpy', 'matplotlib', 'seaborn', 'pandas', 'psutil'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - MANQUANT")
            missing.append(module)
    
    if missing:
        print(f"\n💥 Dépendances manquantes: {', '.join(missing)}")
        print("💡 Installation: pip install " + " ".join(missing))
        return False
    
    print("✅ Toutes les dépendances sont installées")
    return True

def check_file_structure() -> bool:
    """Vérifie la structure des fichiers."""
    print("\n📁 Vérification de la structure des fichiers...")
    
    base_dir = Path(__file__).parent
    
    required_files = [
        "config/pipeline_config.json",
        "scripts/0_recipe_generator.py",
        "scripts/1_layout_generator.py", 
        "scripts/2_layout_evaluator.py",
        "scripts/3_results_analyzer.py",
        "scripts/4_final_selector.py",
        "scripts/run_pipeline.py"
    ]
    
    missing = []
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MANQUANT")
            missing.append(file_path)
    
    if missing:
        print(f"\n💥 Fichiers manquants: {len(missing)}")
        return False
    
    print("✅ Structure des fichiers complète")
    return True

def check_configuration() -> bool:
    """Vérifie la configuration."""
    print("\n⚙️ Vérification de la configuration...")
    
    base_dir = Path(__file__).parent
    config_file = base_dir / "config/pipeline_config.json"
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_sections = [
            "recipe_config",
            "layout_generation", 
            "evaluation_config",
            "pipeline_config"
        ]
        
        missing = []
        for section in required_sections:
            if section in config:
                print(f"  ✅ {section}")
            else:
                print(f"  ❌ {section} - MANQUANT")
                missing.append(section)
        
        if missing:
            print(f"\n💥 Sections de configuration manquantes: {len(missing)}")
            return False
        
        # Vérifier la section selection
        if "selection" in config.get("pipeline_config", {}):
            selection = config["pipeline_config"]["selection"]
            if "selection_criteria" in selection:
                criteria = selection["selection_criteria"]
                required_criteria = ["duo_steps", "cooperation_gain_percent", "exchanges_used"]
                
                for criterion in required_criteria:
                    if criterion in criteria:
                        weight = criteria[criterion].get("weight", 0)
                        print(f"  ✅ Critère {criterion}: poids {weight}")
                    else:
                        print(f"  ❌ Critère {criterion} manquant")
                        return False
        
        print("✅ Configuration valide")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture configuration: {e}")
        return False

def test_dry_run() -> bool:
    """Test en mode simulation."""
    print("\n🧪 Test en mode simulation...")
    
    base_dir = Path(__file__).parent
    python_exe = sys.executable
    
    cmd = [python_exe, "scripts/run_pipeline.py", "--dry-run"]
    
    success, stdout, stderr = run_command(cmd, cwd=base_dir, timeout=30)
    
    if success:
        print("✅ Mode simulation réussi")
        if "Mode simulation" in stdout:
            print("✅ Détection du mode simulation")
        return True
    else:
        print(f"❌ Échec mode simulation: {stderr}")
        return False

def test_step_0() -> bool:
    """Test de l'étape 0 (génération recettes)."""
    print("\n🍽️ Test de l'étape 0 (génération recettes)...")
    
    base_dir = Path(__file__).parent
    python_exe = sys.executable
    
    cmd = [python_exe, "scripts/run_pipeline.py", "--step", "0"]
    
    success, stdout, stderr = run_command(cmd, cwd=base_dir, timeout=60)
    
    if success:
        print("✅ Génération de recettes réussie")
        
        # Vérifier fichiers générés
        recipe_dir = base_dir / "outputs/recipe_combinations"
        json_files = list(recipe_dir.glob("*.json"))
        
        if json_files:
            print(f"✅ {len(json_files)} fichiers générés")
            return True
        else:
            print("❌ Aucun fichier généré")
            return False
    else:
        print(f"❌ Échec génération recettes: {stderr}")
        return False

def check_outputs_structure() -> bool:
    """Vérifie que la structure de sortie existe."""
    print("\n📂 Vérification structure de sortie...")
    
    base_dir = Path(__file__).parent
    outputs_dir = base_dir / "outputs"
    
    if not outputs_dir.exists():
        print("❌ Dossier outputs inexistant")
        return False
    
    required_dirs = [
        "recipe_combinations",
        "layouts_generes",
        "detailed_evaluation", 
        "analysis_results",
        "layouts_selectionnes",
        "logs"
    ]
    
    missing = []
    for dir_name in required_dirs:
        dir_path = outputs_dir / dir_name
        if dir_path.exists():
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ❌ {dir_name}/ - MANQUANT")
            missing.append(dir_name)
    
    if missing:
        print(f"\n💥 Dossiers de sortie manquants: {len(missing)}")
        return False
    
    print("✅ Structure de sortie complète")
    return True

def main():
    """Fonction principale de validation."""
    print("🚀 Validation du Pipeline Professionnel Overcooked")
    print("=" * 50)
    
    start_time = time.time()
    
    tests = [
        ("Dépendances Python", check_dependencies),
        ("Structure des fichiers", check_file_structure),
        ("Configuration", check_configuration),
        ("Structure de sortie", check_outputs_structure),
        ("Test simulation", test_dry_run),
        ("Test étape 0", test_step_0)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: RÉUSSI")
            else:
                failed += 1
                print(f"❌ {test_name}: ÉCHOUÉ")
        except Exception as e:
            failed += 1
            print(f"💥 {test_name}: ERREUR - {e}")
    
    duration = time.time() - start_time
    
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("="*60)
    print(f"⏱️ Durée: {duration:.1f}s")
    print(f"✅ Tests réussis: {passed}")
    print(f"❌ Tests échoués: {failed}")
    print(f"📊 Taux de réussite: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 PIPELINE ENTIÈREMENT VALIDÉ!")
        print("🚀 Vous pouvez exécuter le pipeline complet:")
        print("   python scripts/run_pipeline.py")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) échoué(s)")
        print("🔧 Corrigez les problèmes avant d'exécuter le pipeline")
        return 1

if __name__ == "__main__":
    exit(main())
