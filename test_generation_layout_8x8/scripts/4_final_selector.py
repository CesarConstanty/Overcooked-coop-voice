#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de sélection finale des layouts selon les critères de configuration
Génère les x meilleurs layouts au format final dans layouts_finaux/
"""

import json
import time
from pathlib import Path
from collections import defaultdict
import statistics
import random

class FinalLayoutSelector:
    """Sélecteur final de layouts selon configuration."""
    
    def __init__(self, config_file="pipeline_config.json"):
        """
        Initialise le sélecteur.
        
        Args:
            config_file: Fichier de configuration
        """
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Dossiers
        self.evaluation_dir = self.base_dir / "outputs" / "exhaustive_evaluation"
        self.final_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["final_layouts_dir"]
        self.final_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Sélecteur final de layouts initialisé")
        print(f"📁 Configuration: {self.config_file.name}")
        print(f"📁 Sortie finale: {self.final_dir}")
    
    def load_config(self):
        """Charge la configuration."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Fichier de configuration non trouvé: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"✅ Configuration chargée")
        selection_config = config["pipeline_config"]["selection"]
        print(f"🎯 Sélection: {selection_config['final_layouts_count']} layouts finaux")
        
        return config
    
    def load_latest_evaluation(self):
        """Charge la dernière évaluation exhaustive."""
        if not self.evaluation_dir.exists():
            raise FileNotFoundError(f"Dossier d'évaluation non trouvé: {self.evaluation_dir}")
        
        eval_files = list(self.evaluation_dir.glob("exhaustive_evaluation_*.json"))
        if not eval_files:
            raise FileNotFoundError(f"Aucun fichier d'évaluation trouvé dans {self.evaluation_dir}")
        
        # Prendre le plus récent
        latest_file = max(eval_files, key=lambda f: f.stat().st_mtime)
        
        print(f"📊 Chargement: {latest_file.name}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        evaluations = data['evaluations']
        print(f"✅ {len(evaluations):,} évaluations chargées")
        
        return evaluations, latest_file
    
    def calculate_selection_score(self, evaluation):
        """
        Calcule le score de sélection selon les critères configurés.
        
        Args:
            evaluation: Données d'évaluation d'un layout
            
        Returns:
            float: Score de sélection pondéré
        """
        criteria = self.config["pipeline_config"]["selection"]["criteria"]
        metrics = evaluation["estimated_metrics"]
        
        # Normaliser les métriques (0-1)
        cooperation_gain = min(1.0, max(0.0, (metrics["estimated_cooperation_gain"] - 40) / 20))  # 40-60% → 0-1
        efficiency = min(1.0, max(0.0, (400 - metrics["estimated_duo_steps"]) / 250))  # 150-400 steps → 1-0
        exchanges = min(1.0, max(0.0, metrics["estimated_exchanges"] / 6))  # 0-6 exchanges → 0-1
        
        # Score pondéré
        score = (
            cooperation_gain * criteria["cooperation_gain"]["weight"] +
            efficiency * criteria["efficiency"]["weight"] +
            exchanges * criteria["exchanges"]["weight"]
        )
        
        return score
    
    def apply_quality_filters(self, evaluations):
        """Applique les filtres de qualité."""
        thresholds = self.config["quality_thresholds"]
        
        filtered = []
        for eval_data in evaluations:
            metrics = eval_data["estimated_metrics"]
            structural = eval_data["structural_analysis"]
            
            # Vérifier les seuils
            if (metrics["estimated_cooperation_gain"] >= thresholds["min_cooperation_gain"] and
                structural["connectivity_score"] >= thresholds["min_connectivity_score"] and
                structural["distance_efficiency"] >= thresholds["min_distance_efficiency"]):
                filtered.append(eval_data)
        
        print(f"✅ Filtres de qualité: {len(filtered):,}/{len(evaluations):,} évaluations conservées")
        return filtered
    
    def ensure_diversity(self, top_evaluations):
        """Assure la diversité dans la sélection finale."""
        diversity_config = self.config["pipeline_config"]["selection"]["diversity"]
        
        if not diversity_config["ensure_layout_diversity"]:
            return top_evaluations
        
        # Grouper par groupe de recettes
        by_recipe_group = defaultdict(list)
        for eval_data in top_evaluations:
            recipe_group_id = eval_data["recipe_group_id"]
            by_recipe_group[recipe_group_id].append(eval_data)
        
        # Limiter par groupe de recettes
        max_per_group = diversity_config["max_layouts_per_recipe_group"]
        diversified = []
        
        for recipe_group_id, group_evals in by_recipe_group.items():
            # Prendre les meilleurs de ce groupe
            group_sorted = sorted(group_evals, key=self.calculate_selection_score, reverse=True)
            selected_count = min(len(group_sorted), max_per_group)
            diversified.extend(group_sorted[:selected_count])
        
        # Retrier par score global
        diversified.sort(key=self.calculate_selection_score, reverse=True)
        
        print(f"✅ Diversité assurée: max {max_per_group} layouts par groupe de recettes")
        
        return diversified
    
    def select_final_layouts(self, evaluations):
        """Sélectionne les layouts finaux selon la configuration."""
        target_count = self.config["pipeline_config"]["selection"]["final_layouts_count"]
        
        print(f"\n🎯 SÉLECTION DE {target_count} LAYOUTS FINAUX")
        print("="*60)
        
        # 1. Appliquer les filtres de qualité
        filtered_evaluations = self.apply_quality_filters(evaluations)
        
        if len(filtered_evaluations) < target_count:
            print(f"⚠️  Seulement {len(filtered_evaluations)} layouts passent les filtres de qualité")
            print(f"   Réduction de l'objectif à {len(filtered_evaluations)} layouts")
            target_count = len(filtered_evaluations)
        
        # 2. Calculer les scores de sélection
        print(f"📊 Calcul des scores de sélection...")
        for eval_data in filtered_evaluations:
            eval_data["selection_score"] = self.calculate_selection_score(eval_data)
        
        # 3. Trier par score
        sorted_evaluations = sorted(filtered_evaluations, key=lambda x: x["selection_score"], reverse=True)
        
        # 4. Prendre les top candidats (plus que nécessaire pour diversité)
        top_candidates = sorted_evaluations[:target_count * 3]  # 3x plus pour assurer diversité
        
        # 5. Assurer la diversité
        diversified_candidates = self.ensure_diversity(top_candidates)
        
        # 6. Sélection finale
        final_selection = diversified_candidates[:target_count]
        
        print(f"✅ {len(final_selection)} layouts sélectionnés")
        
        return final_selection
    
    def convert_to_final_format(self, evaluation):
        """
        Convertit une évaluation au format final de layout.
        
        Args:
            evaluation: Données d'évaluation
            
        Returns:
            dict: Layout au format final
        """
        layout_data = {
            "grid": evaluation.get("layout_grid", ""),  # À récupérer depuis les layouts générés
            "start_all_orders": [
                {"ingredients": ["onion"]},
                {"ingredients": ["tomato"]}, 
                {"ingredients": ["onion", "onion"]},
                {"ingredients": ["tomato", "tomato"]},
                {"ingredients": ["onion", "tomato"]}
            ],
            "onion_value": 3,
            "tomato_value": 2,
            "onion_time": 9,
            "tomato_time": 6,
            "metadata": {
                "layout_id": evaluation["layout_id"],
                "recipe_group_id": evaluation["recipe_group_id"],
                "combined_id": evaluation["combined_id"],
                "selection_score": evaluation["selection_score"],
                "estimated_metrics": evaluation["estimated_metrics"],
                "structural_analysis": evaluation["structural_analysis"],
                "recipe_group_info": evaluation["recipe_group_info"]
            }
        }
        
        return layout_data
    
    def load_layout_grids(self):
        """Charge les grilles de layouts depuis les fichiers générés."""
        layouts_dir = self.base_dir / "outputs" / "validated_layouts"
        
        layout_grids = {}
        
        if layouts_dir.exists():
            for layout_file in layouts_dir.glob("*.json"):
                try:
                    with open(layout_file, 'r') as f:
                        data = json.load(f)
                        if 'layouts' in data:
                            for layout in data['layouts']:
                                layout_grids[layout['hash']] = layout['grid']
                except Exception as e:
                    print(f"⚠️  Erreur lecture {layout_file}: {e}")
        
        print(f"✅ {len(layout_grids)} grilles de layouts chargées")
        return layout_grids
    
    def save_final_layouts(self, final_selection, evaluation_file):
        """Sauvegarde les layouts finaux."""
        timestamp = int(time.time())
        
        # Charger les grilles de layouts
        layout_grids = self.load_layout_grids()
        
        # Convertir au format final
        final_layouts = []
        for i, evaluation in enumerate(final_selection):
            layout_id = evaluation["layout_id"]
            
            # Récupérer la grille
            if layout_id in layout_grids:
                evaluation["layout_grid"] = layout_grids[layout_id]
            else:
                print(f"⚠️  Grille non trouvée pour layout {layout_id}")
                continue
            
            final_layout = self.convert_to_final_format(evaluation)
            final_layouts.append(final_layout)
        
        # Sauvegarder les layouts individuels
        layouts_count = 0
        for i, layout_data in enumerate(final_layouts):
            filename = f"layout_{i+1:03d}_{layout_data['metadata']['combined_id'][:12]}.layout"
            layout_file = self.final_dir / filename
            
            # Format .layout simplifié
            layout_content = {
                "grid": layout_data["grid"],
                "start_all_orders": layout_data["start_all_orders"],
                "onion_value": layout_data["onion_value"],
                "tomato_value": layout_data["tomato_value"],
                "onion_time": layout_data["onion_time"],
                "tomato_time": layout_data["tomato_time"]
            }
            
            with open(layout_file, 'w', encoding='utf-8') as f:
                json.dump(layout_content, f, indent=2, ensure_ascii=False)
            
            layouts_count += 1
        
        # Sauvegarder le rapport de sélection
        selection_report = {
            "timestamp": timestamp,
            "selection_config": self.config["pipeline_config"]["selection"],
            "quality_thresholds": self.config["quality_thresholds"],
            "source_evaluation_file": evaluation_file.name,
            "total_layouts_selected": len(final_layouts),
            "selection_statistics": self.generate_selection_statistics(final_selection),
            "layouts_metadata": [layout["metadata"] for layout in final_layouts]
        }
        
        report_file = self.final_dir / f"selection_report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(selection_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 SAUVEGARDE TERMINÉE:")
        print(f"   📄 {layouts_count} layouts individuels sauvés")
        print(f"   📊 Rapport de sélection: {report_file.name}")
        
        return layouts_count, report_file
    
    def generate_selection_statistics(self, final_selection):
        """Génère les statistiques de la sélection finale."""
        if not final_selection:
            return {}
        
        # Métriques
        cooperation_gains = [eval_data["estimated_metrics"]["estimated_cooperation_gain"] for eval_data in final_selection]
        duo_steps = [eval_data["estimated_metrics"]["estimated_duo_steps"] for eval_data in final_selection]
        exchanges = [eval_data["estimated_metrics"]["estimated_exchanges"] for eval_data in final_selection]
        selection_scores = [eval_data["selection_score"] for eval_data in final_selection]
        
        # Groupes de recettes
        recipe_groups = [eval_data["recipe_group_id"] for eval_data in final_selection]
        recipe_group_counts = {}
        for rg in recipe_groups:
            recipe_group_counts[rg] = recipe_group_counts.get(rg, 0) + 1
        
        return {
            "cooperation_gain": {
                "mean": statistics.mean(cooperation_gains),
                "min": min(cooperation_gains),
                "max": max(cooperation_gains),
                "std": statistics.stdev(cooperation_gains) if len(cooperation_gains) > 1 else 0
            },
            "duo_steps": {
                "mean": statistics.mean(duo_steps),
                "min": min(duo_steps),
                "max": max(duo_steps),
                "std": statistics.stdev(duo_steps) if len(duo_steps) > 1 else 0
            },
            "exchanges": {
                "mean": statistics.mean(exchanges),
                "min": min(exchanges),
                "max": max(exchanges),
                "std": statistics.stdev(exchanges) if len(exchanges) > 1 else 0
            },
            "selection_score": {
                "mean": statistics.mean(selection_scores),
                "min": min(selection_scores),
                "max": max(selection_scores),
                "std": statistics.stdev(selection_scores) if len(selection_scores) > 1 else 0
            },
            "recipe_group_distribution": recipe_group_counts,
            "unique_recipe_groups": len(recipe_group_counts)
        }
    
    def run_final_selection(self):
        """Lance la sélection finale complète."""
        print(f"🚀 SÉLECTION FINALE DES LAYOUTS")
        print("="*60)
        
        start_time = time.time()
        
        try:
            # Charger la dernière évaluation
            evaluations, eval_file = self.load_latest_evaluation()
            
            # Sélectionner les layouts finaux
            final_selection = self.select_final_layouts(evaluations)
            
            if not final_selection:
                print("❌ Aucun layout sélectionné")
                return False
            
            # Sauvegarder
            layouts_count, report_file = self.save_final_layouts(final_selection, eval_file)
            
            duration = time.time() - start_time
            
            print(f"\n🎉 SÉLECTION FINALE TERMINÉE!")
            print(f"⏱️  Durée: {duration:.1f}s")
            print(f"📁 Dossier final: {self.final_dir}")
            print(f"📄 {layouts_count} layouts finaux générés")
            
            # Afficher quelques statistiques
            self.show_final_summary(final_selection)
            
            return True
            
        except Exception as e:
            print(f"💥 Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def show_final_summary(self, final_selection):
        """Affiche un résumé de la sélection finale."""
        if not final_selection:
            return
        
        print(f"\n📊 RÉSUMÉ DE LA SÉLECTION:")
        print("-"*40)
        
        stats = self.generate_selection_statistics(final_selection)
        
        print(f"🎯 Gain coopération: {stats['cooperation_gain']['mean']:.1f}% "
              f"({stats['cooperation_gain']['min']:.1f}% - {stats['cooperation_gain']['max']:.1f}%)")
        print(f"⚡ Steps duo: {stats['duo_steps']['mean']:.0f} "
              f"({stats['duo_steps']['min']:.0f} - {stats['duo_steps']['max']:.0f})")
        print(f"🔄 Échanges: {stats['exchanges']['mean']:.1f} "
              f"({stats['exchanges']['min']:.1f} - {stats['exchanges']['max']:.1f})")
        print(f"🏆 Score sélection: {stats['selection_score']['mean']:.3f} "
              f"({stats['selection_score']['min']:.3f} - {stats['selection_score']['max']:.3f})")
        print(f"🍳 Groupes de recettes uniques: {stats['unique_recipe_groups']}")

def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sélection finale des layouts")
    parser.add_argument("--config", default="pipeline_config.json",
                       help="Fichier de configuration (défaut: pipeline_config.json)")
    
    args = parser.parse_args()
    
    try:
        selector = FinalLayoutSelector(args.config)
        success = selector.run_final_selection()
        
        if success:
            print("✅ Sélection finale réussie!")
        else:
            print("❌ Échec de la sélection finale")
            exit(1)
            
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
