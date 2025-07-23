#!/usr/bin/env python3
"""
Exemples d'utilisation du script d'analyse des résultats Overcooked.
"""

import subprocess
import sys
from pathlib import Path

def run_analysis_example():
    """Exécute des exemples d'analyse."""
    
    python_path = "/home/cesar/projet_python/Overcooked-coop-voice/.venv/bin/python"
    script_path = "analyze_evaluation_results.py"
    
    print("🔍 EXEMPLES D'UTILISATION DU SCRIPT D'ANALYSE")
    print("=" * 50)
    
    # Vérifier que le script existe
    if not Path(script_path).exists():
        print(f"❌ Script non trouvé: {script_path}")
        return
    
    examples = [
        {
            "name": "Analyse simple d'un mode",
            "command": [python_path, script_path, "layout_evaluation_coop.json"],
            "description": "Analyse basique des résultats coopératifs"
        },
        {
            "name": "Analyse avec rapport sauvegardé",
            "command": [python_path, script_path, "layout_evaluation_coop.json", 
                       "--report", "rapport_coop.txt"],
            "description": "Analyse avec sauvegarde du rapport dans un fichier"
        },
        {
            "name": "Comparaison entre modes",
            "command": [python_path, script_path, "--compare", 
                       "layout_evaluation_solo.json", "layout_evaluation_coop.json"],
            "description": "Comparaison entre mode solo et coopératif"
        },
        {
            "name": "Analyse sans graphiques",
            "command": [python_path, script_path, "layout_evaluation_coop.json", 
                       "--no-plots"],
            "description": "Analyse rapide sans génération de graphiques"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n📊 Exemple {i}: {example['name']}")
        print(f"Description: {example['description']}")
        print(f"Commande: {' '.join(example['command'])}")
        
        response = input(f"Exécuter cet exemple ? (y/N): ").strip().lower()
        if response in ['y', 'yes', 'o', 'oui']:
            print("🚀 Exécution en cours...")
            try:
                result = subprocess.run(example['command'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=60)
                
                if result.returncode == 0:
                    print("✅ Succès!")
                    # Afficher seulement les premières lignes du résultat
                    lines = result.stdout.split('\n')[:10]
                    print("📋 Aperçu du résultat:")
                    for line in lines:
                        if line.strip():
                            print(f"  {line}")
                    if len(result.stdout.split('\n')) > 10:
                        print("  ... (résultat tronqué)")
                else:
                    print(f"❌ Erreur (code {result.returncode}):")
                    print(result.stderr)
                    
            except subprocess.TimeoutExpired:
                print("⏰ Timeout - commande trop longue")
            except Exception as e:
                print(f"❌ Erreur: {e}")
        else:
            print("⏭️ Exemple ignoré")
    
    print("\n✅ Exemples terminés!")
    print("\n📚 AIDE SUPPLÉMENTAIRE:")
    print("Pour voir toutes les options disponibles:")
    print(f"{python_path} {script_path} --help")

if __name__ == "__main__":
    run_analysis_example()
