#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de démonstration pour modifier le nombre de layouts finaux
"""

import json
from pathlib import Path

def modify_final_layouts_count(new_count):
    """
    Modifie le nombre de layouts finaux dans la configuration.
    
    Args:
        new_count: Nouveau nombre de layouts finaux à sélectionner
    """
    config_file = Path(__file__).parent / "pipeline_config.json"
    
    # Charger la configuration
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Afficher la configuration actuelle
    current_count = config["pipeline_config"]["selection"]["final_layouts_count"]
    print(f"📊 Configuration actuelle:")
    print(f"   Nombre de layouts finaux: {current_count}")
    
    # Modifier
    config["pipeline_config"]["selection"]["final_layouts_count"] = new_count
    
    # Sauvegarder
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Configuration mise à jour:")
    print(f"   Nouveau nombre de layouts finaux: {new_count}")
    print(f"📁 Les layouts sélectionnés seront sauvés dans: outputs/layouts_finaux/")
    
    return True

def show_current_config():
    """Affiche la configuration actuelle."""
    config_file = Path(__file__).parent / "pipeline_config.json"
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    selection_config = config["pipeline_config"]["selection"]
    output_config = config["pipeline_config"]["output"]
    
    print("📋 CONFIGURATION ACTUELLE DU PIPELINE")
    print("="*50)
    print(f"🎯 Nombre de layouts finaux: {selection_config['final_layouts_count']}")
    print(f"📁 Dossier de sortie: {output_config['final_layouts_dir']}")
    print(f"📄 Format de sortie: {output_config['format']}")
    print()
    print("📊 Critères de sélection:")
    for criterion, details in selection_config["criteria"].items():
        print(f"   • {criterion}: poids {details['weight']} - {details['description']}")
    
    print()
    print("🎛️  Seuils de qualité:")
    quality_config = config["quality_thresholds"]
    for threshold, value in quality_config.items():
        print(f"   • {threshold}: {value}")

def main():
    """Fonction principale."""
    print("🔧 CONFIGURATION DU PIPELINE DE SÉLECTION DE LAYOUTS")
    print("="*60)
    print()
    
    # Afficher la configuration actuelle
    show_current_config()
    
    print()
    print("💡 Exemples d'utilisation:")
    print("   python config_demo.py 25    # Pour sélectionner 25 layouts")
    print("   python config_demo.py 100   # Pour sélectionner 100 layouts")
    print()
    
    # Exemple de modification
    import sys
    if len(sys.argv) > 1:
        try:
            new_count = int(sys.argv[1])
            if new_count > 0:
                print(f"🔄 Modification du nombre de layouts finaux à {new_count}...")
                modify_final_layouts_count(new_count)
                print()
                print("✅ Configuration mise à jour! Vous pouvez maintenant lancer:")
                print("   python run_pipeline.py --step 4")
                print("   # ou")
                print("   python run_pipeline.py --full")
            else:
                print("❌ Le nombre doit être positif")
        except ValueError:
            print("❌ Veuillez fournir un nombre entier valide")

if __name__ == "__main__":
    main()
