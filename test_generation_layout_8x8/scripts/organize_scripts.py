#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nettoyage et organisation des scripts - Un script par étape
Objectif : Production et évaluation en masse de layouts
"""

import shutil
from pathlib import Path

class ScriptsCleaner:
    """Nettoyeur et organisateur des scripts."""
    
    def __init__(self):
        """Initialise le nettoyeur."""
        self.base_dir = Path(__file__).parent.parent
        self.scripts_dir = self.base_dir / "scripts"
        
        print(f"🧹 Organisation des scripts dans: {self.scripts_dir}")
    
    def analyze_current_scripts(self):
        """Analyse les scripts actuels."""
        print(f"\n📊 ANALYSE DES SCRIPTS ACTUELS")
        print("="*60)
        
        scripts = list(self.scripts_dir.glob("*.py"))
        scripts = [s for s in scripts if not s.name.startswith("__")]
        
        # Grouper par étape
        by_step = {
            "0_generation_recettes": [],
            "1_generation_layouts": [],
            "3_evaluation": [],
            "4_selection_analyse": [],
            "utils": []
        }
        
        for script in scripts:
            name = script.name
            if name.startswith("0_"):
                by_step["0_generation_recettes"].append(script)
            elif name.startswith("1_"):
                by_step["1_generation_layouts"].append(script)
            elif name.startswith("3_"):
                by_step["3_evaluation"].append(script)
            elif name.startswith("4_"):
                by_step["4_selection_analyse"].append(script)
            else:
                by_step["utils"].append(script)
        
        for step, step_scripts in by_step.items():
            print(f"\n📁 {step.upper()}:")
            for script in step_scripts:
                size = script.stat().st_size / 1024
                print(f"   📄 {script.name} ({size:.1f} KB)")
        
        return by_step
    
    def define_final_pipeline(self):
        """Définit le pipeline final avec un script par étape."""
        print(f"\n🎯 PIPELINE FINAL RECOMMANDÉ")
        print("="*60)
        
        final_pipeline = {
            "0_recipe_generator.py": {
                "source": "0_recipe_groups_generator.py",
                "description": "Génération des groupes de recettes (sans doublons)",
                "action": "renommer"
            },
            "1_layout_generator.py": {
                "source": "1_validated_layout_generator.py", 
                "description": "Génération massive de layouts validés",
                "action": "renommer"
            },
            "2_layout_evaluator.py": {
                "source": "3_exhaustive_evaluator.py",
                "description": "Évaluation exhaustive layouts × groupes de recettes",
                "action": "renommer"
            },
            "3_result_analyzer.py": {
                "source": "4_exhaustive_analyzer.py",
                "description": "Analyse des résultats et sélection optimale",
                "action": "renommer"
            },
            "utils_cleanup.py": {
                "source": "cleanup_outputs.py",
                "description": "Nettoyage et organisation des outputs",
                "action": "renommer"
            }
        }
        
        print(f"🚀 ÉTAPES DU PIPELINE DE PRODUCTION:")
        for i, (final_name, info) in enumerate(final_pipeline.items(), 1):
            print(f"   {i}. {final_name}")
            print(f"      ← {info['source']}")
            print(f"      📝 {info['description']}")
        
        return final_pipeline
    
    def identify_scripts_to_remove(self, final_pipeline):
        """Identifie les scripts à supprimer."""
        print(f"\n🗑️  SCRIPTS À SUPPRIMER")
        print("="*60)
        
        # Scripts à conserver (sources du pipeline final)
        keep_sources = set(info["source"] for info in final_pipeline.values())
        keep_sources.add("verify_recipes.py")  # Utilitaire de vérification
        
        # Tous les scripts
        all_scripts = list(self.scripts_dir.glob("*.py"))
        all_scripts = [s for s in all_scripts if not s.name.startswith("__")]
        
        # Scripts à supprimer
        to_remove = []
        for script in all_scripts:
            if script.name not in keep_sources and script.name != Path(__file__).name:
                to_remove.append(script)
        
        print(f"📋 SCRIPTS OBSOLÈTES:")
        total_size = 0
        for script in to_remove:
            size = script.stat().st_size
            total_size += size
            print(f"   🗑️  {script.name} ({size/1024:.1f} KB)")
        
        print(f"\n📊 ÉCONOMIE: {len(to_remove)} scripts, {total_size/1024:.1f} KB")
        
        return to_remove
    
    def reorganize_scripts(self, final_pipeline, to_remove, confirm=True):
        """Réorganise les scripts selon le pipeline final."""
        
        if confirm:
            print(f"\n⚠️  ATTENTION: Réorganisation des scripts")
            print(f"   - {len(to_remove)} scripts seront supprimés")
            print(f"   - {len(final_pipeline)} scripts seront renommés")
            response = input("Confirmer la réorganisation ? (oui/non): ").lower().strip()
            if response not in ['oui', 'o', 'yes', 'y']:
                print("❌ Réorganisation annulée")
                return False
        
        print(f"\n🔄 RÉORGANISATION EN COURS...")
        
        # 1. Supprimer les scripts obsolètes
        for script in to_remove:
            try:
                script.unlink()
                print(f"   🗑️  Supprimé: {script.name}")
            except Exception as e:
                print(f"   ❌ Erreur suppression {script.name}: {e}")
        
        # 2. Renommer selon le pipeline final
        for final_name, info in final_pipeline.items():
            source_path = self.scripts_dir / info["source"]
            final_path = self.scripts_dir / final_name
            
            if source_path.exists():
                try:
                    if final_path.exists():
                        final_path.unlink()  # Supprimer si existe déjà
                    
                    source_path.rename(final_path)
                    print(f"   ✅ {info['source']} → {final_name}")
                except Exception as e:
                    print(f"   ❌ Erreur renommage {info['source']}: {e}")
            else:
                print(f"   ⚠️  Source manquante: {info['source']}")
        
        return True
    
    def create_pipeline_documentation(self):
        """Crée la documentation du pipeline."""
        print(f"\n📚 CRÉATION DE LA DOCUMENTATION")
        print("="*60)
        
        doc_content = '''# Pipeline de Production et Évaluation de Layouts

## 🎯 Objectif
Production et évaluation en masse de layouts pour l'étude de coopération humain-IA dans Overcooked.

## 🚀 Pipeline de Production

### Étape 0: Génération des Recettes
```bash
python3 scripts/0_recipe_generator.py --group-size 6
```
- Génère tous les groupes de 6 recettes différentes
- Élimine les doublons fonctionnels
- Sortie: `outputs/all_recipe_groups_*.json`

### Étape 1: Génération des Layouts
```bash
python3 scripts/1_layout_generator.py --target-count 1000 --processes 4
```
- Génère des layouts 8x8 validés avec connectivité complète
- Vérifie l'accessibilité de tous les objets
- Sortie: `outputs/validated_layouts/`

### Étape 2: Évaluation Exhaustive
```bash
python3 scripts/2_layout_evaluator.py --layout-sample 100 --processes 4
```
- Évalue chaque layout avec chaque groupe de recettes
- Calcule les métriques de coopération (efficiency, gain, exchanges)
- Sortie: `outputs/exhaustive_evaluation/`

### Étape 3: Analyse et Sélection
```bash
python3 scripts/3_result_analyzer.py outputs/exhaustive_evaluation/results.json
```
- Analyse les résultats d'évaluation
- Identifie les meilleures combinaisons layout-recettes
- Génère des rapports de performance

### Utilitaires

#### Nettoyage des Outputs
```bash
python3 scripts/utils_cleanup.py --auto-confirm
```
- Nettoie les fichiers obsolètes
- Organise la structure des dossiers

#### Vérification des Recettes
```bash
python3 scripts/verify_recipes.py outputs/all_recipe_groups_*.json
```
- Vérifie l'absence de doublons dans les recettes

## 📊 Structure des Outputs

```
outputs/
├── validated_layouts/          # Layouts générés et validés
├── exhaustive_evaluation/      # Résultats d'évaluations
├── final_selection/           # Sélection finale pour expériences
├── all_recipe_groups_*.json   # Groupes de recettes
└── base_recipes_*.json        # Recettes de base
```

## 🎮 Métriques de Coopération

1. **Efficiency (duo_steps)**: Nombre d'étapes en mode coopératif
2. **Cooperation Gain**: Pourcentage d'amélioration vs solo  
3. **Exchanges**: Nombre d'échanges d'objets estimés

## 🔧 Configuration

Les paramètres sont configurables via les arguments de ligne de commande :
- `--target-count`: Nombre de layouts à générer
- `--processes`: Parallélisme (défaut: 4)
- `--layout-sample`: Échantillon de layouts pour évaluation
- `--recipe-group-sample`: Échantillon de groupes de recettes

## 📈 Performance

- Génération: ~1000 layouts/minute
- Évaluation: ~20,000 évaluations/seconde  
- Pipeline complet: quelques minutes pour 1000 layouts × 924 groupes
'''
        
        readme_path = self.base_dir / "README_PIPELINE.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        print(f"✅ Documentation créée: README_PIPELINE.md")
    
    def show_final_structure(self):
        """Affiche la structure finale des scripts."""
        print(f"\n🎯 STRUCTURE FINALE DES SCRIPTS")
        print("="*60)
        
        scripts = sorted(self.scripts_dir.glob("*.py"))
        scripts = [s for s in scripts if not s.name.startswith("__")]
        
        pipeline_scripts = []
        utility_scripts = []
        
        for script in scripts:
            if script.name.startswith(('0_', '1_', '2_', '3_')):
                pipeline_scripts.append(script)
            else:
                utility_scripts.append(script)
        
        print(f"🚀 SCRIPTS DU PIPELINE:")
        for script in pipeline_scripts:
            size = script.stat().st_size / 1024
            print(f"   📄 {script.name} ({size:.1f} KB)")
        
        print(f"\n🔧 SCRIPTS UTILITAIRES:")
        for script in utility_scripts:
            size = script.stat().st_size / 1024
            print(f"   📄 {script.name} ({size:.1f} KB)")
        
        print(f"\n📊 TOTAL: {len(scripts)} scripts")

def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Organisation des scripts du pipeline")
    parser.add_argument("--analyze-only", action="store_true",
                       help="Analyser uniquement, sans réorganiser")
    parser.add_argument("--auto-confirm", action="store_true",
                       help="Réorganiser automatiquement sans confirmation")
    
    args = parser.parse_args()
    
    try:
        cleaner = ScriptsCleaner()
        
        # Analyse
        cleaner.analyze_current_scripts()
        final_pipeline = cleaner.define_final_pipeline()
        to_remove = cleaner.identify_scripts_to_remove(final_pipeline)
        
        if args.analyze_only:
            print("\n🔍 Analyse terminée (aucune modification)")
        else:
            # Réorganisation
            success = cleaner.reorganize_scripts(
                final_pipeline, to_remove, 
                confirm=not args.auto_confirm
            )
            
            if success:
                cleaner.create_pipeline_documentation()
                cleaner.show_final_structure()
                print("\n✅ Réorganisation terminée!")
            else:
                print("\n❌ Réorganisation annulée")
        
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
