#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test complet du pipeline de génération et d'évaluation
Vérifie que tout le processus fonctionne de bout en bout
"""

import json
import gzip
import subprocess
import sys
from pathlib import Path
import time

def run_command(cmd: str, description: str) -> bool:
    """Exécute une commande et retourne le succès"""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False

def check_file_exists(file_path: Path, description: str) -> bool:
    """Vérifie qu'un fichier existe"""
    if file_path.exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ Fichier manquant: {file_path}")
        return False

def analyze_results(results_dir: Path) -> dict:
    """Analyse les résultats d'évaluation"""
    metrics_files = list(results_dir.glob("evaluation_metrics_batch_*.json"))
    
    if not metrics_files:
        return {"error": "Aucun fichier de métriques trouvé"}
    
    total_evaluations = 0
    successful_evaluations = 0
    
    for metrics_file in metrics_files:
        with open(metrics_file, 'r') as f:
            data = json.load(f)
            batch_total = data.get('total_evaluations', 0)
            total_evaluations += batch_total
            
            # Compter les évaluations réussies (celles avec des métriques valides)
            for metric in data.get('metrics', []):
                if metric.get('solo_steps', 0) > 0 and metric.get('duo_steps', 0) > 0:
                    successful_evaluations += 1
    
    return {
        'total_evaluations': total_evaluations,
        'successful_evaluations': successful_evaluations,
        'success_rate': (successful_evaluations / total_evaluations * 100) if total_evaluations > 0 else 0
    }

def main():
    """Test complet du pipeline"""
    print("🧪 TEST COMPLET DU PIPELINE OVERCOOKED")
    print("=" * 50)
    
    base_dir = Path(".")
    test_target = 10  # Nombre de layouts pour le test
    
    # Étape 1: Nettoyer les anciens fichiers
    print("\n1️⃣ NETTOYAGE")
    for pattern in ["outputs/layouts_generes/*", "outputs/evaluation_results/*"]:
        run_command(f"rm -rf {pattern}", f"Nettoyage: {pattern}")
    
    # Étape 2: Génération des layouts
    print("\n2️⃣ GÉNÉRATION DES LAYOUTS")
    cmd = f"/home/cesar/environnements/overcooked/bin/python scripts/1_layout_generator.py --target {test_target}"
    success = run_command(cmd, f"Génération de {test_target} layouts")
    
    if not success:
        print("❌ Échec de la génération")
        return 1
    
    # Vérification des fichiers générés
    layouts_dir = base_dir / "outputs" / "layouts_generes"
    layout_files = list(layouts_dir.glob("layout_batch_*.jsonl.gz"))
    
    if not layout_files:
        print("❌ Aucun fichier de layout généré")
        return 1
    
    print(f"✅ {len(layout_files)} batch(s) de layouts générés")
    
    # Étape 3: Validation de la qualité des layouts
    print("\n3️⃣ VALIDATION DE LA QUALITÉ")
    cmd = "/home/cesar/environnements/overcooked/bin/python test/test_layout_quality.py"
    success = run_command(cmd, "Validation de la qualité des layouts")
    
    if not success:
        print("❌ Validation échoué - layouts de mauvaise qualité")
        return 1
    
    print("✅ Tous les layouts sont valides")
    
    # Étape 4: Évaluation des layouts
    print("\n4️⃣ ÉVALUATION DES LAYOUTS")
    cmd = "/home/cesar/environnements/overcooked/bin/python scripts/2_layout_evaluator.py"
    success = run_command(cmd, "Évaluation des combinaisons layout+recettes")
    
    if not success:
        print("❌ Échec de l'évaluation")
        return 1
    
    # Vérification des résultats d'évaluation
    results_dir = base_dir / "outputs" / "evaluation_results"
    if not check_file_exists(results_dir, "Dossier de résultats"):
        return 1
    
    # Analyse des résultats
    print("\n5️⃣ ANALYSE DES RÉSULTATS")
    analysis = analyze_results(results_dir)
    
    if "error" in analysis:
        print(f"❌ {analysis['error']}")
        return 1
    
    print(f"📊 Statistiques d'évaluation:")
    print(f"   • Total évaluations: {analysis['total_evaluations']:,}")
    print(f"   • Évaluations réussies: {analysis['successful_evaluations']:,}")
    print(f"   • Taux de succès: {analysis['success_rate']:.1f}%")
    
    # Étape 6: Vérification de l'intégrité des données
    print("\n6️⃣ VÉRIFICATION DE L'INTÉGRITÉ")
    
    # Compter les layouts générés
    total_layouts = 0
    for layout_file in layout_files:
        with gzip.open(layout_file, 'rt') as f:
            total_layouts += sum(1 for _ in f)
    
    # Vérifier que le nombre d'évaluations correspond
    expected_evaluations = total_layouts * 84  # 84 groupes de recettes
    
    if analysis['total_evaluations'] == expected_evaluations:
        print(f"✅ Cohérence des données: {total_layouts} layouts × 84 recettes = {expected_evaluations} évaluations")
    else:
        print(f"⚠️  Incohérence: {analysis['total_evaluations']} évaluations trouvées, {expected_evaluations} attendues")
    
    # Verdict final
    print("\n" + "=" * 50)
    if analysis['success_rate'] >= 95:  # Au moins 95% de succès
        print("🎉 PIPELINE VALIDÉ AVEC SUCCÈS! 🎉")
        print(f"   • {total_layouts} layouts générés et validés")
        print(f"   • {analysis['total_evaluations']:,} évaluations réalisées")
        print(f"   • {analysis['success_rate']:.1f}% de taux de succès")
        return 0
    else:
        print("⚠️  PIPELINE PARTIELLEMENT FONCTIONNEL")
        print(f"   • Taux de succès: {analysis['success_rate']:.1f}% (< 95%)")
        return 1

if __name__ == "__main__":
    exit(main())
