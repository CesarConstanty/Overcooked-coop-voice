#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyseur professionnel des résultats d'évaluation de layouts Overcooked
- Compilation de métriques détaillées et statistiques globales
- Détection des patterns optimaux et insights de performance
- Génération de rapports analytiques et visualisations
- Ranking intelligent des layouts selon critères multiples
- Export de données pour sélection finale et études approfondies
"""

import json
import time
import logging
import statistics
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set, Optional, Any
import argparse
from datetime import datetime
import warnings

# Supprimer les warnings de matplotlib
warnings.filterwarnings('ignore')

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('results_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Classe pour calculer et stocker les métriques de performance."""
    
    def __init__(self):
        self.cooperation_gains = []
        self.efficiency_scores = []
        self.success_rates = []
        self.solo_steps = []
        self.duo_steps = []
        self.exchanges_used = []
        self.layout_quality_scores = []
    
    def add_evaluation(self, evaluation: Dict):
        """Ajoute une évaluation aux métriques."""
        metrics = evaluation.get('summary_metrics', {})
        
        if metrics.get('successful_recipes', 0) > 0:
            self.cooperation_gains.append(metrics.get('avg_cooperation_gain', 0))
            self.efficiency_scores.append(metrics.get('efficiency_score', 0))
            self.success_rates.append(metrics.get('success_rate', 0))
            self.solo_steps.append(metrics.get('total_solo_steps', 0))
            self.duo_steps.append(metrics.get('total_duo_steps', 0))
            self.exchanges_used.append(metrics.get('total_exchanges_used', 0))
            self.layout_quality_scores.append(metrics.get('layout_quality_score', 0))
    
    def get_summary_stats(self) -> Dict:
        """Calcule les statistiques sommaires."""
        def safe_stats(data):
            if not data:
                return {'mean': 0, 'median': 0, 'std': 0, 'min': 0, 'max': 0, 'count': 0}
            return {
                'mean': statistics.mean(data),
                'median': statistics.median(data),
                'std': statistics.stdev(data) if len(data) > 1 else 0,
                'min': min(data),
                'max': max(data),
                'count': len(data)
            }
        
        return {
            'cooperation_gains': safe_stats(self.cooperation_gains),
            'efficiency_scores': safe_stats(self.efficiency_scores),
            'success_rates': safe_stats(self.success_rates),
            'solo_steps': safe_stats(self.solo_steps),
            'duo_steps': safe_stats(self.duo_steps),
            'exchanges_used': safe_stats(self.exchanges_used),
            'layout_quality_scores': safe_stats(self.layout_quality_scores)
        }

class LayoutAnalyzer:
    """Analyseur spécialisé pour les patterns de layouts."""
    
    def __init__(self):
        self.layout_patterns = defaultdict(list)
        self.object_distributions = defaultdict(Counter)
        self.size_analysis = defaultdict(list)
    
    def analyze_layout_structure(self, layout: Dict, evaluation: Dict):
        """Analyse la structure d'un layout et ses performances."""
        grid = layout.get('grid', '')
        if not grid:
            return
        
        lines = grid.split('\n')
        grid_size = len(lines)
        
        # Compter les objets
        object_counts = Counter()
        for line in lines:
            for char in line:
                if char in 'OTPDS12XY.':
                    object_counts[char] += 1
        
        # Analyser les métriques de performance
        metrics = evaluation.get('summary_metrics', {})
        layout_id = layout.get('canonical_hash', 'unknown')
        
        # Stocker les patterns
        pattern_key = f"size_{grid_size}"
        self.layout_patterns[pattern_key].append({
            'layout_id': layout_id,
            'object_counts': dict(object_counts),
            'cooperation_gain': metrics.get('avg_cooperation_gain', 0),
            'efficiency_score': metrics.get('efficiency_score', 0),
            'success_rate': metrics.get('success_rate', 0),
            'quality_score': metrics.get('layout_quality_score', 0)
        })
        
        # Analyser la distribution des objets
        for obj, count in object_counts.items():
            self.object_distributions[obj][count] += 1
        
        # Analyser par taille
        self.size_analysis[grid_size].append(metrics.get('layout_quality_score', 0))
    
    def find_optimal_patterns(self) -> Dict:
        """Identifie les patterns optimaux."""
        optimal_patterns = {}
        
        for pattern_type, layouts in self.layout_patterns.items():
            if not layouts:
                continue
            
            # Trier par score de qualité
            sorted_layouts = sorted(layouts, key=lambda x: x['quality_score'], reverse=True)
            top_10_percent = max(1, len(sorted_layouts) // 10)
            top_layouts = sorted_layouts[:top_10_percent]
            
            # Analyser les caractéristiques communes
            common_characteristics = self.extract_common_characteristics(top_layouts)
            
            optimal_patterns[pattern_type] = {
                'top_layouts_count': len(top_layouts),
                'avg_quality_score': statistics.mean([l['quality_score'] for l in top_layouts]),
                'avg_cooperation_gain': statistics.mean([l['cooperation_gain'] for l in top_layouts]),
                'common_characteristics': common_characteristics,
                'best_layout_id': top_layouts[0]['layout_id'] if top_layouts else None
            }
        
        return optimal_patterns
    
    def extract_common_characteristics(self, layouts: List[Dict]) -> Dict:
        """Extrait les caractéristiques communes des meilleurs layouts."""
        if not layouts:
            return {}
        
        # Analyser les objets les plus fréquents
        all_objects = defaultdict(list)
        for layout in layouts:
            for obj, count in layout['object_counts'].items():
                all_objects[obj].append(count)
        
        common_objects = {}
        for obj, counts in all_objects.items():
            if len(counts) >= len(layouts) * 0.7:  # Présent dans au moins 70% des layouts
                common_objects[obj] = {
                    'avg_count': statistics.mean(counts),
                    'frequency': len(counts) / len(layouts)
                }
        
        return {
            'object_patterns': common_objects,
            'sample_size': len(layouts)
        }

class RecipeAnalyzer:
    """Analyseur spécialisé pour les performances par recette."""
    
    def __init__(self):
        self.recipe_performance = defaultdict(list)
        self.ingredient_analysis = defaultdict(list)
        self.difficulty_ranking = []
    
    def analyze_recipe_performance(self, evaluation: Dict):
        """Analyse les performances par recette."""
        for recipe_eval in evaluation.get('recipe_evaluations', []):
            recipe_id = recipe_eval.get('recipe_id', 'unknown')
            recipe = recipe_eval.get('recipe', {})
            
            if recipe_eval.get('success', False):
                performance_data = {
                    'recipe_id': recipe_id,
                    'ingredients': recipe.get('ingredients', []),
                    'solo_steps': recipe_eval.get('solo_steps', 0),
                    'duo_steps': recipe_eval.get('duo_steps', 0),
                    'cooperation_gain': recipe_eval.get('cooperation_gain', 0),
                    'exchanges_used': recipe_eval.get('exchanges_used', 0)
                }
                
                self.recipe_performance[recipe_id].append(performance_data)
                
                # Analyser par nombre d'ingrédients
                ingredient_count = len(recipe.get('ingredients', []))
                self.ingredient_analysis[ingredient_count].append(performance_data)
    
    def calculate_recipe_difficulty(self) -> Dict:
        """Calcule le niveau de difficulté des recettes."""
        recipe_difficulties = {}
        
        for recipe_id, performances in self.recipe_performance.items():
            if not performances:
                continue
            
            avg_solo_steps = statistics.mean([p['solo_steps'] for p in performances])
            avg_cooperation_gain = statistics.mean([p['cooperation_gain'] for p in performances])
            avg_exchanges = statistics.mean([p['exchanges_used'] for p in performances])
            
            # Score de difficulté (plus c'est élevé, plus c'est difficile)
            difficulty_score = (avg_solo_steps * 0.4 + 
                              (100 - avg_cooperation_gain) * 0.4 + 
                              avg_exchanges * 0.2)
            
            recipe_difficulties[recipe_id] = {
                'difficulty_score': difficulty_score,
                'avg_solo_steps': avg_solo_steps,
                'avg_cooperation_gain': avg_cooperation_gain,
                'avg_exchanges_used': avg_exchanges,
                'sample_size': len(performances)
            }
        
        # Trier par difficulté
        self.difficulty_ranking = sorted(recipe_difficulties.items(), 
                                       key=lambda x: x[1]['difficulty_score'], 
                                       reverse=True)
        
        return recipe_difficulties

class ProfessionalResultsAnalyzer:
    """Analyseur principal pour les résultats d'évaluation."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise l'analyseur avec la configuration."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Dossiers
        self.evaluation_dir = self.base_dir / "outputs" / "detailed_evaluation"
        self.analysis_dir = self.base_dir / "outputs" / "performance_metrics"
        self.plots_dir = self.analysis_dir / "plots"
        
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        
        # Analyseurs spécialisés
        self.performance_metrics = PerformanceMetrics()
        self.layout_analyzer = LayoutAnalyzer()
        self.recipe_analyzer = RecipeAnalyzer()
        
        logger.info(f"🔬 Analyseur de résultats initialisé")
        logger.info(f"📁 Évaluations: {self.evaluation_dir}")
        logger.info(f"📁 Analyses: {self.analysis_dir}")
        logger.info(f"📊 Graphiques: {self.plots_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_evaluation_results(self) -> List[Dict]:
        """Charge tous les fichiers d'évaluation disponibles."""
        evaluation_files = list(self.evaluation_dir.glob("detailed_evaluation_*.json"))
        
        if not evaluation_files:
            raise FileNotFoundError(f"Aucun fichier d'évaluation trouvé dans {self.evaluation_dir}")
        
        # Utiliser le fichier le plus récent
        latest_file = max(evaluation_files, key=lambda f: f.stat().st_mtime)
        
        logger.info(f"📂 Chargement: {latest_file.name}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        evaluations = data.get('evaluations', [])
        evaluation_info = data.get('evaluation_info', {})
        
        logger.info(f"📊 {len(evaluations)} évaluations chargées")
        logger.info(f"⏱️ Temps d'évaluation: {evaluation_info.get('evaluation_time', 0):.1f}s")
        
        return evaluations, evaluation_info
    
    def analyze_all_results(self) -> Dict:
        """Lance l'analyse complète des résultats."""
        start_time = time.time()
        
        try:
            # Charger les données
            evaluations, evaluation_info = self.load_evaluation_results()
            
            logger.info(f"🚀 Démarrage de l'analyse complète")
            
            # Analyser chaque évaluation
            layouts_analyzed = 0
            successful_evaluations = 0
            
            for evaluation in evaluations:
                # Métriques globales
                self.performance_metrics.add_evaluation(evaluation)
                
                # Analyser les recettes
                self.recipe_analyzer.analyze_recipe_performance(evaluation)
                
                # Analyser le layout (si disponible dans l'évaluation)
                # Note: Nous devrons charger les layouts séparément
                layouts_analyzed += 1
                
                if evaluation.get('summary_metrics', {}).get('successful_recipes', 0) > 0:
                    successful_evaluations += 1
            
            # Générer les analyses
            performance_summary = self.performance_metrics.get_summary_stats()
            recipe_difficulties = self.recipe_analyzer.calculate_recipe_difficulty()
            
            # Générer les visualisations
            self.generate_visualizations()
            
            # Compiler le rapport final
            analysis_results = {
                'analysis_info': {
                    'timestamp': time.time(),
                    'analysis_duration': time.time() - start_time,
                    'evaluations_analyzed': len(evaluations),
                    'layouts_analyzed': layouts_analyzed,
                    'successful_evaluations': successful_evaluations,
                    'success_rate': successful_evaluations / len(evaluations) * 100 if evaluations else 0
                },
                'performance_summary': performance_summary,
                'recipe_analysis': {
                    'difficulty_ranking': dict(self.recipe_analyzer.difficulty_ranking[:20]),  # Top 20
                    'ingredient_analysis': self.analyze_by_ingredient_count()
                },
                'layout_insights': self.generate_layout_insights(),
                'recommendations': self.generate_recommendations(performance_summary, recipe_difficulties)
            }
            
            # Sauvegarder les résultats
            self.save_analysis_results(analysis_results)
            
            analysis_time = time.time() - start_time
            logger.info(f"✅ Analyse terminée en {analysis_time:.1f}s")
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"💥 Erreur durant l'analyse: {e}", exc_info=True)
            raise
    
    def analyze_by_ingredient_count(self) -> Dict:
        """Analyse les performances par nombre d'ingrédients."""
        ingredient_analysis = {}
        
        for ingredient_count, performances in self.recipe_analyzer.ingredient_analysis.items():
            if not performances:
                continue
            
            avg_cooperation_gain = statistics.mean([p['cooperation_gain'] for p in performances])
            avg_solo_steps = statistics.mean([p['solo_steps'] for p in performances])
            avg_duo_steps = statistics.mean([p['duo_steps'] for p in performances])
            avg_exchanges = statistics.mean([p['exchanges_used'] for p in performances])
            
            ingredient_analysis[f"{ingredient_count}_ingredients"] = {
                'recipe_count': len(performances),
                'avg_cooperation_gain': avg_cooperation_gain,
                'avg_solo_steps': avg_solo_steps,
                'avg_duo_steps': avg_duo_steps,
                'avg_exchanges_used': avg_exchanges,
                'efficiency_ratio': avg_solo_steps / avg_duo_steps if avg_duo_steps > 0 else 0
            }
        
        return ingredient_analysis
    
    def generate_layout_insights(self) -> Dict:
        """Génère des insights sur les layouts."""
        # Pour l'instant, retourner des insights basiques
        # Cette fonction sera enrichie quand nous aurons accès aux layouts
        return {
            'layout_count_analyzed': len(self.layout_analyzer.layout_patterns),
            'optimal_patterns': self.layout_analyzer.find_optimal_patterns(),
            'object_distributions': dict(self.layout_analyzer.object_distributions)
        }
    
    def generate_recommendations(self, performance_summary: Dict, recipe_difficulties: Dict) -> Dict:
        """Génère des recommandations basées sur l'analyse."""
        recommendations = {
            'layout_optimization': [],
            'recipe_balancing': [],
            'cooperation_enhancement': [],
            'performance_targets': {}
        }
        
        # Recommandations pour les layouts
        coop_stats = performance_summary.get('cooperation_gains', {})
        if coop_stats.get('mean', 0) < 20:
            recommendations['layout_optimization'].append(
                "Augmenter les opportunités de coopération - gain moyen actuel: {:.1f}%".format(coop_stats.get('mean', 0))
            )
        
        # Recommandations pour les recettes
        if len(recipe_difficulties) > 0:
            easiest_recipes = sorted(recipe_difficulties.items(), key=lambda x: x[1]['difficulty_score'])[:3]
            hardest_recipes = sorted(recipe_difficulties.items(), key=lambda x: x[1]['difficulty_score'], reverse=True)[:3]
            
            recommendations['recipe_balancing'].append(
                f"Recettes les plus faciles: {[r[0] for r in easiest_recipes]}"
            )
            recommendations['recipe_balancing'].append(
                f"Recettes les plus difficiles: {[r[0] for r in hardest_recipes]}"
            )
        
        # Recommandations pour la coopération
        exchanges_stats = performance_summary.get('exchanges_used', {})
        if exchanges_stats.get('mean', 0) < 1:
            recommendations['cooperation_enhancement'].append(
                "Encourager l'utilisation des zones d'échange - utilisation moyenne: {:.1f}".format(exchanges_stats.get('mean', 0))
            )
        
        # Cibles de performance
        recommendations['performance_targets'] = {
            'target_cooperation_gain': max(25, coop_stats.get('mean', 0) * 1.2),
            'target_efficiency_score': 0.8,
            'target_success_rate': 95.0
        }
        
        return recommendations
    
    def generate_visualizations(self):
        """Génère les graphiques et visualisations."""
        logger.info("📊 Génération des visualisations...")
        
        try:
            # Configuration des plots
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
            
            # 1. Distribution des gains de coopération
            if self.performance_metrics.cooperation_gains:
                plt.figure(figsize=(10, 6))
                plt.hist(self.performance_metrics.cooperation_gains, bins=20, alpha=0.7, edgecolor='black')
                plt.title('Distribution des Gains de Coopération')
                plt.xlabel('Gain de Coopération (%)')
                plt.ylabel('Fréquence')
                plt.grid(True, alpha=0.3)
                plt.savefig(self.plots_dir / 'cooperation_gains_distribution.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 2. Corrélation Steps Solo vs Duo
            if self.performance_metrics.solo_steps and self.performance_metrics.duo_steps:
                plt.figure(figsize=(10, 8))
                plt.scatter(self.performance_metrics.solo_steps, self.performance_metrics.duo_steps, alpha=0.6)
                plt.plot([0, max(self.performance_metrics.solo_steps)], [0, max(self.performance_metrics.solo_steps)], 'r--', label='Ligne d\'égalité')
                plt.title('Corrélation Steps Solo vs Duo')
                plt.xlabel('Steps Solo')
                plt.ylabel('Steps Duo')
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.savefig(self.plots_dir / 'solo_vs_duo_correlation.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 3. Scores de qualité des layouts
            if self.performance_metrics.layout_quality_scores:
                plt.figure(figsize=(12, 6))
                plt.boxplot(self.performance_metrics.layout_quality_scores)
                plt.title('Distribution des Scores de Qualité des Layouts')
                plt.ylabel('Score de Qualité')
                plt.grid(True, alpha=0.3)
                plt.savefig(self.plots_dir / 'layout_quality_scores.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 4. Analyse des échanges utilisés
            if self.performance_metrics.exchanges_used:
                plt.figure(figsize=(10, 6))
                exchange_counts = Counter(self.performance_metrics.exchanges_used)
                exchanges, counts = zip(*sorted(exchange_counts.items()))
                plt.bar(exchanges, counts, alpha=0.7, edgecolor='black')
                plt.title('Utilisation des Zones d\'Échange')
                plt.xlabel('Nombre d\'Échanges Utilisés')
                plt.ylabel('Fréquence')
                plt.grid(True, alpha=0.3)
                plt.savefig(self.plots_dir / 'exchanges_usage.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            logger.info(f"✅ Visualisations sauvegardées dans {self.plots_dir}")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur génération visualisations: {e}")
    
    def save_analysis_results(self, results: Dict):
        """Sauvegarde les résultats d'analyse."""
        timestamp = int(time.time())
        
        # Fichier JSON détaillé
        json_file = self.analysis_dir / f"analysis_results_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Rapport markdown
        markdown_file = self.analysis_dir / f"analysis_report_{timestamp}.md"
        self.generate_markdown_report(results, markdown_file)
        
        # CSV pour analyse externe
        csv_file = self.analysis_dir / f"performance_summary_{timestamp}.csv"
        self.export_csv_summary(csv_file)
        
        logger.info(f"💾 Résultats sauvegardés:")
        logger.info(f"  📄 JSON: {json_file.name}")
        logger.info(f"  📝 Rapport: {markdown_file.name}")
        logger.info(f"  📊 CSV: {csv_file.name}")
    
    def generate_markdown_report(self, results: Dict, output_file: Path):
        """Génère un rapport markdown lisible."""
        report_content = f"""# Rapport d'Analyse des Layouts Overcooked

Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Résumé Exécutif

- **Évaluations analysées**: {results['analysis_info']['evaluations_analyzed']:,}
- **Layouts analysés**: {results['analysis_info']['layouts_analyzed']:,}
- **Taux de succès global**: {results['analysis_info']['success_rate']:.1f}%
- **Durée d'analyse**: {results['analysis_info']['analysis_duration']:.1f}s

## 🎯 Métriques de Performance

### Gains de Coopération
- **Moyenne**: {results['performance_summary']['cooperation_gains']['mean']:.1f}%
- **Médiane**: {results['performance_summary']['cooperation_gains']['median']:.1f}%
- **Maximum**: {results['performance_summary']['cooperation_gains']['max']:.1f}%

### Efficacité des Layouts
- **Score moyen**: {results['performance_summary']['efficiency_scores']['mean']:.3f}
- **Écart-type**: {results['performance_summary']['efficiency_scores']['std']:.3f}

### Utilisation des Échanges
- **Moyenne**: {results['performance_summary']['exchanges_used']['mean']:.1f}
- **Maximum**: {results['performance_summary']['exchanges_used']['max']}

## 🍳 Analyse des Recettes

### Top 5 Recettes les Plus Difficiles
"""
        
        difficulty_ranking = results['recipe_analysis']['difficulty_ranking']
        for i, (recipe_id, data) in enumerate(list(difficulty_ranking.items())[:5], 1):
            report_content += f"{i}. **{recipe_id}** - Score: {data['difficulty_score']:.1f}\n"
        
        report_content += f"""

### Analyse par Nombre d'Ingrédients
"""
        
        ingredient_analysis = results['recipe_analysis']['ingredient_analysis']
        for ingredient_count, data in ingredient_analysis.items():
            report_content += f"- **{ingredient_count}**: Gain coopération {data['avg_cooperation_gain']:.1f}%, Efficacité {data['efficiency_ratio']:.2f}x\n"
        
        report_content += f"""

## 🎨 Recommandations

### Optimisation des Layouts
"""
        for rec in results['recommendations']['layout_optimization']:
            report_content += f"- {rec}\n"
        
        report_content += f"""

### Équilibrage des Recettes
"""
        for rec in results['recommendations']['recipe_balancing']:
            report_content += f"- {rec}\n"
        
        report_content += f"""

### Amélioration de la Coopération
"""
        for rec in results['recommendations']['cooperation_enhancement']:
            report_content += f"- {rec}\n"
        
        report_content += f"""

## 🎯 Objectifs de Performance

- **Gain de coopération cible**: {results['recommendations']['performance_targets']['target_cooperation_gain']:.1f}%
- **Score d'efficacité cible**: {results['recommendations']['performance_targets']['target_efficiency_score']:.1f}
- **Taux de succès cible**: {results['recommendations']['performance_targets']['target_success_rate']:.1f}%

---
*Rapport généré automatiquement par l'analyseur professionnel de layouts Overcooked*
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
    
    def export_csv_summary(self, output_file: Path):
        """Exporte un résumé CSV pour analyse externe."""
        try:
            # Créer un DataFrame avec les métriques principales
            data = []
            
            # Si nous avions les IDs des layouts, nous pourrions créer une ligne par layout
            # Pour l'instant, créons un résumé global
            summary_stats = self.performance_metrics.get_summary_stats()
            
            for metric_name, stats in summary_stats.items():
                if stats['count'] > 0:
                    data.append({
                        'metric': metric_name,
                        'mean': stats['mean'],
                        'median': stats['median'],
                        'std': stats['std'],
                        'min': stats['min'],
                        'max': stats['max'],
                        'count': stats['count']
                    })
            
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False)
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur export CSV: {e}")

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Analyseur professionnel de résultats Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json", 
                       help="Fichier de configuration")
    parser.add_argument("--evaluation-file", 
                       help="Fichier d'évaluation spécifique à analyser")
    parser.add_argument("--no-plots", action="store_true",
                       help="Désactiver la génération de graphiques")
    
    args = parser.parse_args()
    
    try:
        analyzer = ProfessionalResultsAnalyzer(args.config)
        
        results = analyzer.analyze_all_results()
        
        logger.info("🎉 Analyse terminée avec succès!")
        logger.info(f"📊 {results['analysis_info']['evaluations_analyzed']} évaluations analysées")
        logger.info(f"✅ Taux de succès: {results['analysis_info']['success_rate']:.1f}%")
        
        return 0
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
