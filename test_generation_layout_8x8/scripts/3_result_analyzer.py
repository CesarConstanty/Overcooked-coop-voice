#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyseur des résultats d'évaluation exhaustive
Extrait des insights et statistiques des évaluations layout x groupes de recettes
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict, Counter
import statistics

class ExhaustiveResultsAnalyzer:
    """Analyseur des résultats d'évaluation exhaustive."""
    
    def __init__(self, results_file):
        """
        Initialise l'analyseur.
        
        Args:
            results_file: Chemin vers le fichier de résultats
        """
        self.results_file = Path(results_file)
        self.data = None
        self.evaluations = []
        
        self.load_results()
    
    def load_results(self):
        """Charge les résultats d'évaluation."""
        if not self.results_file.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {self.results_file}")
        
        print(f"📊 Chargement: {self.results_file.name}")
        
        with open(self.results_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.evaluations = self.data['evaluations']
        
        print(f"✅ {len(self.evaluations):,} évaluations chargées")
        print(f"📋 {self.data['layouts_count']} layouts × {self.data['recipe_groups_count']:,} groupes")
    
    def analyze_layout_performance(self):
        """Analyse les performances par layout."""
        print(f"\n🏗️  ANALYSE DES PERFORMANCES PAR LAYOUT")
        print("="*60)
        
        layout_stats = defaultdict(list)
        
        # Grouper par layout
        for eval_data in self.evaluations:
            layout_id = eval_data['layout_id']
            metrics = eval_data['estimated_metrics']
            
            layout_stats[layout_id].append({
                'duo_steps': metrics['estimated_duo_steps'],
                'cooperation_gain': metrics['estimated_cooperation_gain'],
                'exchanges': metrics['estimated_exchanges'],
                'recipe_complexity': metrics['recipe_complexity_score']
            })
        
        # Calculer statistiques par layout
        layout_analysis = {}
        for layout_id, evals in layout_stats.items():
            layout_analysis[layout_id] = {
                'count': len(evals),
                'avg_duo_steps': statistics.mean(e['duo_steps'] for e in evals),
                'avg_cooperation_gain': statistics.mean(e['cooperation_gain'] for e in evals),
                'avg_exchanges': statistics.mean(e['exchanges'] for e in evals),
                'avg_recipe_complexity': statistics.mean(e['recipe_complexity'] for e in evals),
                'best_cooperation_gain': max(e['cooperation_gain'] for e in evals),
                'worst_cooperation_gain': min(e['cooperation_gain'] for e in evals),
                'std_cooperation_gain': statistics.stdev(e['cooperation_gain'] for e in evals) if len(evals) > 1 else 0
            }
        
        # Trier par gain de coopération moyen
        sorted_layouts = sorted(layout_analysis.items(), 
                              key=lambda x: x[1]['avg_cooperation_gain'], 
                              reverse=True)
        
        print(f"🏆 TOP 5 LAYOUTS (gain coopération moyen):")
        for i, (layout_id, stats) in enumerate(sorted_layouts[:5], 1):
            print(f"   {i}. {layout_id[:16]}...")
            print(f"      Gain moyen: {stats['avg_cooperation_gain']:.1f}% "
                  f"(std: {stats['std_cooperation_gain']:.1f})")
            print(f"      Steps: {stats['avg_duo_steps']:.1f}, "
                  f"Échanges: {stats['avg_exchanges']:.1f}")
            print(f"      Meilleur gain: {stats['best_cooperation_gain']:.1f}%")
        
        print(f"\n📉 5 LAYOUTS LES MOINS PERFORMANTS:")
        for i, (layout_id, stats) in enumerate(sorted_layouts[-5:], 1):
            print(f"   {i}. {layout_id[:16]}...")
            print(f"      Gain moyen: {stats['avg_cooperation_gain']:.1f}% "
                  f"(std: {stats['std_cooperation_gain']:.1f})")
            print(f"      Steps: {stats['avg_duo_steps']:.1f}, "
                  f"Échanges: {stats['avg_exchanges']:.1f}")
        
        return layout_analysis
    
    def analyze_recipe_group_performance(self):
        """Analyse les performances par groupe de recettes."""
        print(f"\n🍳 ANALYSE DES PERFORMANCES PAR GROUPE DE RECETTES")
        print("="*60)
        
        recipe_stats = defaultdict(list)
        
        # Grouper par groupe de recettes
        for eval_data in self.evaluations:
            recipe_group_id = eval_data['recipe_group_id']
            metrics = eval_data['estimated_metrics']
            recipe_info = eval_data['recipe_group_info']
            
            recipe_stats[recipe_group_id].append({
                'duo_steps': metrics['estimated_duo_steps'],
                'cooperation_gain': metrics['estimated_cooperation_gain'],
                'exchanges': metrics['estimated_exchanges'],
                'avg_complexity': recipe_info['avg_complexity'],
                'total_ingredients': recipe_info['total_ingredients']
            })
        
        # Calculer statistiques par groupe
        recipe_analysis = {}
        for recipe_id, evals in recipe_stats.items():
            recipe_analysis[recipe_id] = {
                'count': len(evals),
                'avg_duo_steps': statistics.mean(e['duo_steps'] for e in evals),
                'avg_cooperation_gain': statistics.mean(e['cooperation_gain'] for e in evals),
                'avg_exchanges': statistics.mean(e['exchanges'] for e in evals),
                'recipe_complexity': evals[0]['avg_complexity'],  # Même pour tous
                'total_ingredients': evals[0]['total_ingredients'],  # Même pour tous
                'std_cooperation_gain': statistics.stdev(e['cooperation_gain'] for e in evals) if len(evals) > 1 else 0
            }
        
        # Trier par gain de coopération moyen
        sorted_recipes = sorted(recipe_analysis.items(), 
                              key=lambda x: x[1]['avg_cooperation_gain'], 
                              reverse=True)
        
        print(f"🏆 TOP 5 GROUPES DE RECETTES (gain coopération moyen):")
        for i, (recipe_id, stats) in enumerate(sorted_recipes[:5], 1):
            print(f"   {i}. {recipe_id}")
            print(f"      Gain moyen: {stats['avg_cooperation_gain']:.1f}% "
                  f"(std: {stats['std_cooperation_gain']:.1f})")
            print(f"      Complexité: {stats['recipe_complexity']:.1f}, "
                  f"Ingrédients: {stats['total_ingredients']}")
            print(f"      Steps: {stats['avg_duo_steps']:.1f}, "
                  f"Échanges: {stats['avg_exchanges']:.1f}")
        
        return recipe_analysis
    
    def analyze_complexity_correlation(self):
        """Analyse la corrélation entre complexité des recettes et métriques."""
        print(f"\n📊 ANALYSE COMPLEXITÉ VS MÉTRIQUES")
        print("="*60)
        
        # Grouper par niveau de complexité
        complexity_groups = defaultdict(list)
        
        for eval_data in self.evaluations:
            complexity = eval_data['recipe_group_info']['avg_complexity']
            complexity_level = round(complexity)
            
            metrics = eval_data['estimated_metrics']
            complexity_groups[complexity_level].append({
                'duo_steps': metrics['estimated_duo_steps'],
                'cooperation_gain': metrics['estimated_cooperation_gain'],
                'exchanges': metrics['estimated_exchanges']
            })
        
        print(f"📈 MÉTRIQUES PAR NIVEAU DE COMPLEXITÉ:")
        for complexity in sorted(complexity_groups.keys()):
            evals = complexity_groups[complexity]
            avg_steps = statistics.mean(e['duo_steps'] for e in evals)
            avg_gain = statistics.mean(e['cooperation_gain'] for e in evals)
            avg_exchanges = statistics.mean(e['exchanges'] for e in evals)
            
            print(f"   Complexité {complexity}: {len(evals):,} évaluations")
            print(f"      Steps: {avg_steps:.1f}, "
                  f"Gain: {avg_gain:.1f}%, "
                  f"Échanges: {avg_exchanges:.1f}")
    
    def find_optimal_combinations(self, top_n=10):
        """Trouve les meilleures combinaisons layout-recettes."""
        print(f"\n🎯 TOP {top_n} COMBINAISONS OPTIMALES")
        print("="*60)
        
        # Trier toutes les évaluations par gain de coopération
        sorted_evals = sorted(self.evaluations, 
                            key=lambda x: x['estimated_metrics']['estimated_cooperation_gain'], 
                            reverse=True)
        
        print(f"🏆 MEILLEURES COMBINAISONS (gain de coopération):")
        for i, eval_data in enumerate(sorted_evals[:top_n], 1):
            combined_id = eval_data['combined_id']
            layout_id = eval_data['layout_id'][:12]
            recipe_id = eval_data['recipe_group_id']
            
            metrics = eval_data['estimated_metrics']
            recipe_info = eval_data['recipe_group_info']
            
            print(f"   {i}. {combined_id[:30]}...")
            print(f"      Layout: {layout_id}... | Recettes: {recipe_id}")
            print(f"      Gain: {metrics['estimated_cooperation_gain']:.1f}%, "
                  f"Steps: {metrics['estimated_duo_steps']}, "
                  f"Échanges: {metrics['estimated_exchanges']:.1f}")
            print(f"      Complexité recettes: {recipe_info['avg_complexity']:.1f}, "
                  f"Ingrédients: {recipe_info['total_ingredients']}")
            print()
    
    def generate_summary_report(self):
        """Génère un rapport de synthèse."""
        print(f"\n📋 RAPPORT DE SYNTHÈSE")
        print("="*60)
        
        # Statistiques globales
        all_gains = [e['estimated_metrics']['estimated_cooperation_gain'] for e in self.evaluations]
        all_steps = [e['estimated_metrics']['estimated_duo_steps'] for e in self.evaluations]
        all_exchanges = [e['estimated_metrics']['estimated_exchanges'] for e in self.evaluations]
        
        print(f"🎯 STATISTIQUES GLOBALES:")
        print(f"   Total évaluations: {len(self.evaluations):,}")
        print(f"   Layouts uniques: {len(set(e['layout_id'] for e in self.evaluations))}")
        print(f"   Groupes de recettes: {len(set(e['recipe_group_id'] for e in self.evaluations)):,}")
        
        print(f"\n📊 DISTRIBUTION DES MÉTRIQUES:")
        print(f"   Gain coopération: {statistics.mean(all_gains):.1f}% ± {statistics.stdev(all_gains):.1f}")
        print(f"      Min: {min(all_gains):.1f}%, Max: {max(all_gains):.1f}%")
        print(f"   Steps duo: {statistics.mean(all_steps):.1f} ± {statistics.stdev(all_steps):.1f}")
        print(f"      Min: {min(all_steps)}, Max: {max(all_steps)}")
        print(f"   Échanges: {statistics.mean(all_exchanges):.1f} ± {statistics.stdev(all_exchanges):.1f}")
        print(f"      Min: {min(all_exchanges):.1f}, Max: {max(all_exchanges):.1f}")
        
        # Distribution par quartiles
        sorted_gains = sorted(all_gains)
        q1 = sorted_gains[len(sorted_gains)//4]
        q2 = sorted_gains[len(sorted_gains)//2]
        q3 = sorted_gains[3*len(sorted_gains)//4]
        
        print(f"\n📈 QUARTILES GAIN COOPÉRATION:")
        print(f"   Q1 (25%): {q1:.1f}%")
        print(f"   Q2 (50%): {q2:.1f}%")
        print(f"   Q3 (75%): {q3:.1f}%")
        
        # Recommandations
        print(f"\n💡 RECOMMANDATIONS:")
        best_eval = max(self.evaluations, key=lambda x: x['estimated_metrics']['estimated_cooperation_gain'])
        print(f"   🏆 Meilleure combinaison: {best_eval['combined_id'][:40]}...")
        print(f"      Gain: {best_eval['estimated_metrics']['estimated_cooperation_gain']:.1f}%")
        
        # Layouts les plus polyvalents
        layout_gains = defaultdict(list)
        for eval_data in self.evaluations:
            layout_gains[eval_data['layout_id']].append(
                eval_data['estimated_metrics']['estimated_cooperation_gain']
            )
        
        # Layout avec le gain moyen le plus élevé
        best_layout = max(layout_gains.items(), 
                         key=lambda x: statistics.mean(x[1]))
        print(f"   🏗️  Layout le plus polyvalent: {best_layout[0][:16]}...")
        print(f"      Gain moyen: {statistics.mean(best_layout[1]):.1f}%")

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(
        description='Analyseur des résultats d\'évaluation exhaustive'
    )
    
    parser.add_argument(
        'results_file',
        nargs='?',  # Rendre optionnel
        help='Fichier de résultats JSON à analyser (auto si non spécifié)'
    )
    
    parser.add_argument(
        '--top-combinations',
        type=int,
        default=10,
        help='Nombre de meilleures combinaisons à afficher'
    )
    
    args = parser.parse_args()
    
    try:
        # Si pas de fichier spécifié, chercher le plus récent
        if not args.results_file:
            base_dir = Path(__file__).parent.parent
            eval_dir = base_dir / "outputs" / "exhaustive_evaluation"
            
            if not eval_dir.exists():
                print("❌ Aucun dossier d'évaluation trouvé")
                exit(1)
            
            eval_files = list(eval_dir.glob("exhaustive_evaluation_*.json"))
            if not eval_files:
                print("❌ Aucun fichier d'évaluation trouvé")
                exit(1)
            
            # Prendre le plus récent
            results_file = max(eval_files, key=lambda f: f.stat().st_mtime)
            print(f"📁 Fichier auto-détecté: {results_file.name}")
        else:
            results_file = Path(args.results_file)
        
        analyzer = ExhaustiveResultsAnalyzer(results_file)
        
        # Analyses principales
        analyzer.analyze_layout_performance()
        analyzer.analyze_recipe_group_performance()
        analyzer.analyze_complexity_correlation()
        analyzer.find_optimal_combinations(args.top_combinations)
        analyzer.generate_summary_report()
        
        print("\n✅ Analyse terminée!")
        
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
