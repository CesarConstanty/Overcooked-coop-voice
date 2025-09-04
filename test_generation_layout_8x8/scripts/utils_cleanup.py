#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage du dossier outputs
Supprime les fichiers anciens et organise la structure
"""

import json
import shutil
import time
from pathlib import Path
from collections import defaultdict

class OutputsCleaner:
    """Nettoyeur du dossier outputs."""
    
    def __init__(self):
        """Initialise le nettoyeur."""
        self.base_dir = Path(__file__).parent.parent
        self.outputs_dir = self.base_dir / "outputs"
        
        print(f"🧹 Nettoyage du dossier: {self.outputs_dir}")
    
    def analyze_current_structure(self):
        """Analyse la structure actuelle."""
        print(f"\n📊 ANALYSE DE LA STRUCTURE ACTUELLE")
        print("="*60)
        
        if not self.outputs_dir.exists():
            print("❌ Dossier outputs n'existe pas")
            return
        
        total_size = 0
        file_count = 0
        dir_count = 0
        
        for item in self.outputs_dir.rglob("*"):
            if item.is_file():
                size = item.stat().st_size
                total_size += size
                file_count += 1
                print(f"📄 {item.relative_to(self.outputs_dir)} ({size/1024/1024:.1f} MB)")
            elif item.is_dir():
                dir_count += 1
                files_in_dir = len(list(item.iterdir()))
                print(f"📁 {item.relative_to(self.outputs_dir)}/ ({files_in_dir} éléments)")
        
        print(f"\n📈 RÉSUMÉ:")
        print(f"   - Fichiers: {file_count}")
        print(f"   - Dossiers: {dir_count}")
        print(f"   - Taille totale: {total_size/1024/1024:.1f} MB")
    
    def identify_obsolete_files(self):
        """Identifie les fichiers obsolètes à supprimer."""
        print(f"\n🔍 IDENTIFICATION DES FICHIERS OBSOLÈTES")
        print("="*60)
        
        obsolete_patterns = [
            # Anciens fichiers de sélection
            "selected_layouts_*.json",
            "layout_files_*/",
            # Anciennes évaluations
            "evaluation_results_*.json", 
            # Dossiers vides
            "analysis_reports/",
            # Anciens fichiers massive
            "massive_layouts/",
            "massive_evaluation/",
            # Ancienne génération de recettes (garder la plus récente)
            "all_recipe_groups_*.json",
            "base_recipes_*.json"
        ]
        
        obsolete_files = []
        keep_files = []
        
        # Fichiers de recettes - garder le plus récent
        recipe_files = list(self.outputs_dir.glob("all_recipe_groups_*.json"))
        base_recipe_files = list(self.outputs_dir.glob("base_recipes_*.json"))
        
        if recipe_files:
            # Garder le plus récent
            latest_recipe = max(recipe_files, key=lambda f: f.stat().st_mtime)
            keep_files.append(latest_recipe)
            
            # Marquer les autres comme obsolètes
            for f in recipe_files:
                if f != latest_recipe:
                    obsolete_files.append(f)
        
        if base_recipe_files:
            # Garder le plus récent
            latest_base = max(base_recipe_files, key=lambda f: f.stat().st_mtime)
            keep_files.append(latest_base)
            
            # Marquer les autres comme obsolètes
            for f in base_recipe_files:
                if f != latest_base:
                    obsolete_files.append(f)
        
        # Dossiers et fichiers obsolètes
        for pattern in ["selected_layouts", "massive_layouts", "massive_evaluation", "cooperation_evaluation"]:
            pattern_dir = self.outputs_dir / pattern
            if pattern_dir.exists():
                obsolete_files.append(pattern_dir)
        
        # Dossier analysis_reports vide
        analysis_dir = self.outputs_dir / "analysis_reports"
        if analysis_dir.exists() and not any(analysis_dir.iterdir()):
            obsolete_files.append(analysis_dir)
        
        print(f"🗑️  FICHIERS/DOSSIERS À SUPPRIMER:")
        total_obsolete_size = 0
        for item in obsolete_files:
            if item.exists():
                if item.is_file():
                    size = item.stat().st_size
                    total_obsolete_size += size
                    print(f"   📄 {item.name} ({size/1024/1024:.1f} MB)")
                else:
                    # Calculer taille du dossier
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    total_obsolete_size += size
                    print(f"   📁 {item.name}/ ({size/1024/1024:.1f} MB)")
        
        print(f"\n💾 FICHIERS À CONSERVER:")
        for item in keep_files:
            if item.exists():
                size = item.stat().st_size
                print(f"   ✅ {item.name} ({size/1024/1024:.1f} MB)")
        
        print(f"\n📊 ÉCONOMIE D'ESPACE: {total_obsolete_size/1024/1024:.1f} MB")
        
        return obsolete_files, keep_files
    
    def create_clean_structure(self):
        """Crée une structure propre recommandée."""
        print(f"\n🏗️  STRUCTURE RECOMMANDÉE")
        print("="*60)
        
        recommended_dirs = [
            "validated_layouts",      # Layouts générés et validés
            "exhaustive_evaluation",  # Résultats d'évaluation exhaustive
            "final_selection"         # Sélection finale pour les expériences
        ]
        
        print(f"📁 DOSSIERS RECOMMANDÉS:")
        for dir_name in recommended_dirs:
            dir_path = self.outputs_dir / dir_name
            if dir_path.exists():
                file_count = len(list(dir_path.glob("*.json")))
                print(f"   ✅ {dir_name}/ ({file_count} fichiers)")
            else:
                print(f"   📁 {dir_name}/ (à créer)")
                dir_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📄 FICHIERS PRINCIPAUX:")
        main_files = [
            "all_recipe_groups_*.json (le plus récent)",
            "base_recipes_*.json (le plus récent)"
        ]
        
        for file_desc in main_files:
            print(f"   📄 {file_desc}")
    
    def perform_cleanup(self, confirm=True):
        """Effectue le nettoyage."""
        obsolete_files, keep_files = self.identify_obsolete_files()
        
        if not obsolete_files:
            print("✅ Aucun fichier obsolète trouvé !")
            return
        
        if confirm:
            print(f"\n⚠️  ATTENTION: {len(obsolete_files)} éléments vont être supprimés")
            response = input("Confirmer la suppression ? (oui/non): ").lower().strip()
            if response not in ['oui', 'o', 'yes', 'y']:
                print("❌ Nettoyage annulé")
                return
        
        print(f"\n🗑️  SUPPRESSION EN COURS...")
        deleted_count = 0
        deleted_size = 0
        
        for item in obsolete_files:
            if item.exists():
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        item.unlink()
                        deleted_size += size
                        print(f"   🗑️  Supprimé: {item.name}")
                    else:
                        # Supprimer dossier récursivement
                        size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        shutil.rmtree(item)
                        deleted_size += size
                        print(f"   🗑️  Supprimé: {item.name}/")
                    
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Erreur suppression {item.name}: {e}")
        
        print(f"\n✅ NETTOYAGE TERMINÉ:")
        print(f"   - Éléments supprimés: {deleted_count}")
        print(f"   - Espace libéré: {deleted_size/1024/1024:.1f} MB")
        
        # Créer structure propre
        self.create_clean_structure()
    
    def show_final_structure(self):
        """Affiche la structure finale."""
        print(f"\n🎯 STRUCTURE FINALE")
        print("="*60)
        
        if not self.outputs_dir.exists():
            print("❌ Dossier outputs n'existe pas")
            return
        
        def print_tree(path, prefix="", max_depth=2, current_depth=0):
            if current_depth >= max_depth:
                return
            
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                
                if item.is_file():
                    size = item.stat().st_size
                    print(f"{prefix}{current_prefix}{item.name} ({size/1024/1024:.1f} MB)")
                else:
                    print(f"{prefix}{current_prefix}{item.name}/")
                    if current_depth < max_depth - 1:
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        print_tree(item, next_prefix, max_depth, current_depth + 1)
        
        print(f"outputs/")
        print_tree(self.outputs_dir)

def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nettoyage du dossier outputs")
    parser.add_argument("--analyze-only", action="store_true", 
                       help="Analyser uniquement, sans supprimer")
    parser.add_argument("--auto-confirm", action="store_true",
                       help="Supprimer automatiquement sans confirmation")
    
    args = parser.parse_args()
    
    try:
        cleaner = OutputsCleaner()
        
        # Toujours analyser d'abord
        cleaner.analyze_current_structure()
        
        if args.analyze_only:
            cleaner.identify_obsolete_files()
            cleaner.create_clean_structure()
            print("\n🔍 Analyse terminée (aucune suppression)")
        else:
            cleaner.perform_cleanup(confirm=not args.auto_confirm)
            cleaner.show_final_structure()
        
        print("\n✅ Script de nettoyage terminé!")
        
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
