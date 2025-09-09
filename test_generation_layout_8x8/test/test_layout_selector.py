#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour le sélecteur de layouts
Teste la sélection et la conversion au format requis
"""

import json
import subprocess
import sys
from pathlib import Path

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

def check_layout_format(layout_file: Path) -> bool:
    """Vérifie qu'un fichier layout respecte le format requis"""
    try:
        with open(layout_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que c'est du JSON valide
        try:
            layout_data = eval(content)  # Utiliser eval car c'est du format Python dict
        except:
            print(f"❌ {layout_file.name}: Format JSON invalide")
            return False
        
        # Vérifier les champs requis
        required_fields = ["grid", "start_all_orders", "counter_goals", 
                          "onion_value", "tomato_value", "onion_time", "tomato_time"]
        
        for field in required_fields:
            if field not in layout_data:
                print(f"❌ {layout_file.name}: Champ manquant: {field}")
                return False
        
        # Vérifier que la grille est une string avec des lignes
        grid = layout_data["grid"]
        if not isinstance(grid, str):
            print(f"❌ {layout_file.name}: Grid doit être une string")
            return False
        
        lines = grid.strip().split('\n')
        if len(lines) < 7:  # Au moins 7 lignes pour une grille 8x8
            print(f"❌ {layout_file.name}: Grille trop petite ({len(lines)} lignes)")
            return False
        
        print(f"✅ {layout_file.name}: Format valide")
        return True
        
    except Exception as e:
        print(f"❌ {layout_file.name}: Erreur de validation: {e}")
        return False

def test_layout_selector():
    """Test complet du sélecteur de layouts"""
    print("🧪 TEST DU SÉLECTEUR DE LAYOUTS")
    print("=" * 40)
    
    base_dir = Path(".")
    
    # Vérifier les prérequis
    evaluation_dir = base_dir / "outputs" / "evaluation_results"
    if not evaluation_dir.exists():
        print("❌ Dossier d'évaluations manquant. Lancer d'abord l'évaluateur.")
        return 1
    
    # Étape 1: Lancer la sélection avec un petit nombre pour les tests
    print("\n1️⃣ LANCEMENT DE LA SÉLECTION")
    cmd = "/home/cesar/environnements/overcooked/bin/python scripts/3_layout_selector.py --count 5"
    success = run_command(cmd, "Sélection de 5 layouts")
    
    if not success:
        print("❌ Échec de la sélection")
        return 1
    
    # Étape 2: Vérifier les fichiers générés
    print("\n2️⃣ VÉRIFICATION DES FICHIERS GÉNÉRÉS")
    output_dir = base_dir / "outputs" / "layouts_finaux"
    
    if not output_dir.exists():
        print("❌ Dossier de sortie non créé")
        return 1
    
    # Vérifier le résumé
    summary_file = output_dir / "selection_summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        print(f"✅ Résumé de sélection: {summary['total_selected']} layouts")
    else:
        print("⚠️  Fichier de résumé manquant")
    
    # Vérifier les fichiers de layout
    layout_files = list(output_dir.glob("*.layout"))
    print(f"📁 {len(layout_files)} fichiers .layout trouvés")
    
    if len(layout_files) == 0:
        print("❌ Aucun fichier layout généré")
        return 1
    
    # Étape 3: Valider le format de chaque layout
    print("\n3️⃣ VALIDATION DU FORMAT")
    valid_layouts = 0
    
    for layout_file in layout_files:
        if check_layout_format(layout_file):
            valid_layouts += 1
    
    # Étape 4: Afficher un exemple
    print("\n4️⃣ EXEMPLE DE LAYOUT GÉNÉRÉ")
    if layout_files:
        example_file = layout_files[0]
        print(f"📄 Contenu de {example_file.name}:")
        with open(example_file, 'r') as f:
            content = f.read()
        print(content[:500] + "..." if len(content) > 500 else content)
    
    # Rapport final
    print("\n" + "=" * 40)
    print(f"📊 RÉSULTATS DU TEST:")
    print(f"   • Layouts générés: {len(layout_files)}")
    print(f"   • Layouts valides: {valid_layouts}")
    print(f"   • Taux de validité: {valid_layouts/len(layout_files)*100:.1f}%")
    
    if valid_layouts == len(layout_files) and len(layout_files) > 0:
        print("🎉 SÉLECTEUR VALIDÉ AVEC SUCCÈS! 🎉")
        return 0
    else:
        print("⚠️  PROBLÈMES DÉTECTÉS DANS LE SÉLECTEUR")
        return 1

def main():
    return test_layout_selector()

if __name__ == "__main__":
    exit(main())
