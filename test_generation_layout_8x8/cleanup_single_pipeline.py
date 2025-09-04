#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage - Un seul fichier de lancement
Supprime les anciens pipelines et crée un fichier unique
"""

from pathlib import Path
import shutil

def cleanup_pipeline_files():
    """Nettoie les fichiers de pipeline pour ne garder qu'un seul."""
    base_dir = Path(__file__).parent
    
    print("🧹 NETTOYAGE DES FICHIERS DE PIPELINE")
    print("="*50)
    
    # Fichiers à supprimer
    files_to_remove = [
        "run_cooperation_pipeline.py",
        "run_exhaustive_pipeline.py", 
        "run_pipeline_from_config.py"
    ]
    
    # Fichier à conserver et renommer
    current_main = "run_production_pipeline.py"
    new_main = "run_pipeline.py"
    
    print("🗑️  Suppression des anciens fichiers:")
    for filename in files_to_remove:
        file_path = base_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"   ✅ Supprimé: {filename}")
        else:
            print(f"   ⚠️  Non trouvé: {filename}")
    
    # Renommer le fichier principal
    current_path = base_dir / current_main
    new_path = base_dir / new_main
    
    if current_path.exists():
        if new_path.exists():
            new_path.unlink()  # Supprimer si existe déjà
        
        current_path.rename(new_path)
        print(f"✅ Renommé: {current_main} → {new_main}")
    else:
        print(f"❌ Fichier principal non trouvé: {current_main}")
        return False
    
    # Supprimer les anciens fichiers de configuration obsolètes
    config_files_to_remove = [
        "cooperation_config.json",
        "pipeline_config.json"
    ]
    
    print("\n🗑️  Suppression des anciens fichiers de config:")
    for filename in config_files_to_remove:
        file_path = base_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"   ✅ Supprimé: {filename}")
    
    print(f"\n🎯 FICHIER DE LANCEMENT UNIQUE:")
    print(f"   📄 {new_main}")
    
    return True

def show_usage():
    """Affiche l'usage du fichier de lancement unique."""
    print(f"\n📚 USAGE DU PIPELINE UNIQUE:")
    print("="*50)
    
    examples = [
        ("Pipeline complet", "python3 run_pipeline.py"),
        ("Test rapide", "python3 run_pipeline.py --quick-test"),
        ("Étape spécifique", "python3 run_pipeline.py --step 1"),
        ("Configuration personnalisée", "python3 run_pipeline.py --layout-count 500 --processes 8"),
        ("Aide", "python3 run_pipeline.py --help")
    ]
    
    for description, command in examples:
        print(f"📝 {description}:")
        print(f"   {command}")
        print()

if __name__ == "__main__":
    try:
        success = cleanup_pipeline_files()
        if success:
            show_usage()
            print("✅ Nettoyage terminé! Un seul fichier de lancement reste.")
        else:
            print("❌ Échec du nettoyage")
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
