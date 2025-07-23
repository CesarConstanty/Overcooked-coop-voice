#!/usr/bin/env python3
"""
Script d'analyse des résultats d'évaluation des layouts Overcooked.
Analyse les données comportementales compatibles avec le format 2_0_0.json.

Usage:
    python analyze_evaluation_results.py [file1.json] [file2.json] ...
    python analyze_evaluation_results.py --compare layout_evaluation_solo.json layout_evaluation_coop.json
    python analyze_evaluation_results.py --detailed layout_evaluation_solo_detailed.json
"""

import json
import argparse
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import sys

class OvercookedResultsAnalyzer:
    """Analyseur de résultats d'évaluation Overcooked."""
    
    def __init__(self):
        self.event_types = [
            'tomato_pickup', 'useful_tomato_pickup', 'tomato_drop', 'useful_tomato_drop',
            'potting_tomato', 'tomato_exchange', 'onion_pickup', 'useful_onion_pickup',
            'onion_drop', 'useful_onion_drop', 'potting_onion', 'onion_exchange',
            'dish_pickup', 'useful_dish_pickup', 'dish_drop', 'useful_dish_drop',
            'dish_exchange', 'soup_pickup', 'soup_delivery', 'soup_drop', 'soup_exchange',
            'optimal_onion_potting', 'optimal_tomato_potting', 'viable_onion_potting',
            'viable_tomato_potting', 'catastrophic_onion_potting', 'catastrophic_tomato_potting',
            'useless_onion_potting', 'useless_tomato_potting'
        ]
        
    def load_results(self, filepath: str) -> Dict:
        """Charge un fichier de résultats JSON."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ Fichier chargé: {filepath}")
            return data
        except Exception as e:
            print(f"❌ Erreur lors du chargement de {filepath}: {e}")
            return {}
    
    def analyze_aggregated_results(self, data: Dict) -> Dict:
        """Analyse les résultats agrégés par layout."""
        analysis = {
            'summary': {},
            'layouts_performance': {},
            'behavioral_insights': {},
            'comparison': {}
        }
        
        if 'results' not in data:
            print("❌ Format de données non reconnu")
            return analysis
        
        # Résumé général
        total_layouts = len(data['results'])
        viable_layouts = sum(1 for layout in data['results'].values() if layout.get('viable', False))
        completed_layouts = sum(1 for layout in data['results'].values() 
                               if layout.get('completion_rate', 0) > 0)
        
        analysis['summary'] = {
            'total_layouts': total_layouts,
            'viable_layouts': viable_layouts,
            'completed_layouts': completed_layouts,
            'viability_rate': viable_layouts / max(total_layouts, 1),
            'completion_rate': completed_layouts / max(total_layouts, 1),
            'evaluation_mode': self._get_evaluation_mode(data),
            'evaluation_date': data.get('evaluation_timestamp', 'Unknown')
        }
        
        # Analyse par layout
        for layout_name, layout_data in data['results'].items():
            analysis['layouts_performance'][layout_name] = self._analyze_layout_performance(layout_data)
        
        # Insights comportementaux globaux
        analysis['behavioral_insights'] = self._extract_behavioral_insights(data['results'])
        
        return analysis
    
    def analyze_detailed_results(self, data: Dict) -> Dict:
        """Analyse les résultats détaillés avec parties individuelles."""
        analysis = {
            'summary': {},
            'individual_games': {},
            'behavioral_patterns': {},
            'event_analysis': {}
        }
        
        if 'results' not in data:
            return analysis
        
        # Analyser les parties individuelles
        for layout_name, layout_data in data['results'].items():
            if 'individual_games' in layout_data:
                analysis['individual_games'][layout_name] = self._analyze_individual_games(
                    layout_data['individual_games']
                )
                
                # Analyse des événements détaillée
                analysis['event_analysis'][layout_name] = self._analyze_events_detailed(
                    layout_data['individual_games']
                )
        
        return analysis
    
    def _get_evaluation_mode(self, data: Dict) -> str:
        """Détermine le mode d'évaluation."""
        config = data.get('evaluation_config', {})
        if config.get('single_agent_mode', False):
            return "Solo (1x GreedyAgent)"
        elif config.get('greedy_with_stay_mode', False):
            return "GreedyAgent + StayAgent"
        else:
            return "Coopératif (2x GreedyAgent)"
    
    def _analyze_layout_performance(self, layout_data: Dict) -> Dict:
        """Analyse la performance d'un layout spécifique."""
        performance = {
            'viable': layout_data.get('viable', False),
            'completion_rate': layout_data.get('completion_rate', 0),
            'games_played': layout_data.get('games_played', 0),
            'games_completed': layout_data.get('games_completed', 0),
            'structure': layout_data.get('structure', {}),
            'metrics': {}
        }
        
        # Métriques de performance
        if 'completion_metrics' in layout_data:
            cm = layout_data['completion_metrics']
            performance['metrics'] = {
                'avg_completion_steps': cm.get('average_completion_steps', 0),
                'fastest_completion': cm.get('fastest_completion_steps', 0),
                'slowest_completion': cm.get('slowest_completion_steps', 0),
                'std_completion': cm.get('std_completion_steps', 0),
                'efficiency_score': self._calculate_efficiency_score(cm)
            }
        
        # Analyse comportementale
        if 'behavioral_analysis' in layout_data:
            ba = layout_data['behavioral_analysis']
            performance['behavioral'] = {
                'layout_difficulty': ba.get('layout_characteristics', {}).get('layout_difficulty', 'unknown'),
                'coordination_required': ba.get('layout_characteristics', {}).get('required_coordination_level', 'unknown'),
                'optimal_strategy': ba.get('optimal_strategies', {}).get('fastest_completion_strategy', {}),
                'determinism': ba.get('strategy_consistency', {}).get('layout_determinism', 'unknown')
            }
        
        return performance
    
    def _calculate_efficiency_score(self, completion_metrics: Dict) -> float:
        """Calcule un score d'efficacité basé sur les métriques."""
        avg_steps = completion_metrics.get('average_completion_steps', 600)
        # Score inversement proportionnel aux steps (plus c'est rapide, plus c'est efficace)
        return max(0, (600 - avg_steps) / 600)
    
    def _extract_behavioral_insights(self, results: Dict) -> Dict:
        """Extrait des insights comportementaux globaux."""
        insights = {
            'difficulty_distribution': defaultdict(int),
            'coordination_requirements': defaultdict(int),
            'strategy_patterns': defaultdict(int),
            'layout_determinism': defaultdict(int),
            'performance_correlations': {}
        }
        
        completed_layouts = []
        
        for layout_name, layout_data in results.items():
            if not layout_data.get('viable', False):
                continue
                
            ba = layout_data.get('behavioral_analysis', {})
            lc = ba.get('layout_characteristics', {})
            sc = ba.get('strategy_consistency', {})
            
            # Distribution des difficultés
            difficulty = lc.get('layout_difficulty', 'unknown')
            insights['difficulty_distribution'][difficulty] += 1
            
            # Exigences de coordination
            coordination = lc.get('required_coordination_level', 'unknown')
            insights['coordination_requirements'][coordination] += 1
            
            # Déterminisme des stratégies
            determinism = sc.get('layout_determinism', 'unknown')
            insights['layout_determinism'][determinism] += 1
            
            # Collecter les données pour les corrélations
            if layout_data.get('completion_rate', 0) > 0:
                cm = layout_data.get('completion_metrics', {})
                completed_layouts.append({
                    'layout': layout_name,
                    'avg_steps': cm.get('average_completion_steps', 600),
                    'difficulty': difficulty,
                    'coordination': coordination,
                    'efficiency': self._calculate_efficiency_score(cm)
                })
        
        # Analyse des corrélations
        if completed_layouts:
            insights['performance_correlations'] = self._analyze_performance_correlations(completed_layouts)
        
        return insights
    
    def _analyze_performance_correlations(self, layouts_data: List[Dict]) -> Dict:
        """Analyse les corrélations entre caractéristiques et performance."""
        correlations = {}
        
        # Corrélation difficulté vs steps
        difficulty_steps = defaultdict(list)
        for layout in layouts_data:
            difficulty_steps[layout['difficulty']].append(layout['avg_steps'])
        
        correlations['difficulty_vs_steps'] = {
            diff: np.mean(steps) for diff, steps in difficulty_steps.items()
        }
        
        # Corrélation coordination vs efficacité
        coordination_efficiency = defaultdict(list)
        for layout in layouts_data:
            coordination_efficiency[layout['coordination']].append(layout['efficiency'])
        
        correlations['coordination_vs_efficiency'] = {
            coord: np.mean(eff) for coord, eff in coordination_efficiency.items()
        }
        
        return correlations
    
    def _analyze_individual_games(self, games: List[Dict]) -> Dict:
        """Analyse les parties individuelles."""
        analysis = {
            'total_games': len(games),
            'completed_games': sum(1 for g in games if g.get('completed', False)),
            'event_statistics': {},
            'agent_performance': {},
            'temporal_analysis': {}
        }
        
        # Analyse des événements
        event_totals = defaultdict(lambda: [0, 0])  # [agent_0, agent_1]
        
        for game in games:
            info_sum = game.get('info_sum', {})
            for event_type in self.event_types:
                if event_type in info_sum:
                    event_totals[event_type][0] += info_sum[event_type][0]
                    event_totals[event_type][1] += info_sum[event_type][1]
        
        analysis['event_statistics'] = dict(event_totals)
        
        # Performance des agents
        total_actions = [0, 0]
        total_interactions = [0, 0]
        total_distance = [0, 0]
        
        for game in games:
            stats = game.get('agent_statistics', {})
            for i in range(2):
                agent_key = f'agent_{i}'
                if agent_key in stats:
                    total_actions[i] += stats[agent_key].get('total_actions', 0)
                    total_interactions[i] += stats[agent_key].get('interact_count', 0)
                    total_distance[i] += stats[agent_key].get('distance_traveled', 0)
        
        analysis['agent_performance'] = {
            'total_actions': total_actions,
            'total_interactions': total_interactions,
            'total_distance': total_distance,
            'avg_actions_per_game': [a / len(games) for a in total_actions],
            'avg_interactions_per_game': [i / len(games) for i in total_interactions],
            'avg_distance_per_game': [d / len(games) for d in total_distance]
        }
        
        return analysis
    
    def _analyze_events_detailed(self, games: List[Dict]) -> Dict:
        """Analyse détaillée des événements."""
        analysis = {
            'pickup_efficiency': {},
            'potting_analysis': {},
            'coordination_metrics': {},
            'delivery_patterns': {}
        }
        
        # Efficacité des pickups
        total_pickups = [0, 0]
        useful_pickups = [0, 0]
        
        for game in games:
            info_sum = game.get('info_sum', {})
            for agent_idx in range(2):
                # Pickups totaux
                total_pickups[agent_idx] += (
                    info_sum.get('tomato_pickup', [0, 0])[agent_idx] +
                    info_sum.get('onion_pickup', [0, 0])[agent_idx] +
                    info_sum.get('dish_pickup', [0, 0])[agent_idx] +
                    info_sum.get('soup_pickup', [0, 0])[agent_idx]
                )
                
                # Pickups utiles
                useful_pickups[agent_idx] += (
                    info_sum.get('useful_tomato_pickup', [0, 0])[agent_idx] +
                    info_sum.get('useful_onion_pickup', [0, 0])[agent_idx] +
                    info_sum.get('useful_dish_pickup', [0, 0])[agent_idx]
                )
        
        analysis['pickup_efficiency'] = {
            'total_pickups': total_pickups,
            'useful_pickups': useful_pickups,
            'efficiency_rate': [
                useful_pickups[i] / max(total_pickups[i], 1) for i in range(2)
            ]
        }
        
        # Analyse du potting
        potting_types = ['optimal', 'viable', 'catastrophic', 'useless']
        potting_analysis = {pot_type: {'onion': [0, 0], 'tomato': [0, 0]} for pot_type in potting_types}
        
        for game in games:
            info_sum = game.get('info_sum', {})
            for pot_type in potting_types:
                for ingredient in ['onion', 'tomato']:
                    event_key = f'{pot_type}_{ingredient}_potting'
                    if event_key in info_sum:
                        for agent_idx in range(2):
                            potting_analysis[pot_type][ingredient][agent_idx] += info_sum[event_key][agent_idx]
        
        analysis['potting_analysis'] = potting_analysis
        
        # Métriques de coordination
        total_exchanges = [0, 0]
        for game in games:
            info_sum = game.get('info_sum', {})
            for exchange_type in ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange']:
                if exchange_type in info_sum:
                    for agent_idx in range(2):
                        total_exchanges[agent_idx] += info_sum[exchange_type][agent_idx]
        
        analysis['coordination_metrics'] = {
            'total_exchanges': total_exchanges,
            'avg_exchanges_per_game': [e / len(games) for e in total_exchanges]
        }
        
        return analysis
    
    def compare_modes(self, data_list: List[Dict]) -> Dict:
        """Compare différents modes d'évaluation."""
        comparison = {
            'modes': [],
            'performance_comparison': {},
            'behavioral_differences': {},
            'layout_suitability': {}
        }
        
        for data in data_list:
            mode = self._get_evaluation_mode(data)
            comparison['modes'].append(mode)
            
            # Performance par layout
            for layout_name, layout_data in data.get('results', {}).items():
                if layout_name not in comparison['performance_comparison']:
                    comparison['performance_comparison'][layout_name] = {}
                
                completion_rate = layout_data.get('completion_rate', 0)
                avg_steps = layout_data.get('completion_metrics', {}).get('average_completion_steps', 600)
                
                comparison['performance_comparison'][layout_name][mode] = {
                    'completion_rate': completion_rate,
                    'avg_steps': avg_steps,
                    'efficiency': self._calculate_efficiency_score({'average_completion_steps': avg_steps})
                }
        
        return comparison
    
    def generate_report(self, analysis: Dict, output_file: Optional[str] = None) -> str:
        """Génère un rapport d'analyse textuel."""
        report_lines = []
        
        # En-tête
        report_lines.append("🎯 RAPPORT D'ANALYSE - ÉVALUATION LAYOUTS OVERCOOKED")
        report_lines.append("=" * 60)
        report_lines.append("")
        
        # Résumé
        if 'summary' in analysis:
            summary = analysis['summary']
            report_lines.append("📊 RÉSUMÉ GÉNÉRAL")
            report_lines.append("-" * 20)
            report_lines.append(f"Mode d'évaluation: {summary.get('evaluation_mode', 'Unknown')}")
            report_lines.append(f"Layouts totaux: {summary.get('total_layouts', 0)}")
            report_lines.append(f"Layouts viables: {summary.get('viable_layouts', 0)} ({summary.get('viability_rate', 0):.1%})")
            report_lines.append(f"Layouts complétés: {summary.get('completed_layouts', 0)} ({summary.get('completion_rate', 0):.1%})")
            report_lines.append("")
        
        # Performance par layout
        if 'layouts_performance' in analysis:
            report_lines.append("🏗️ PERFORMANCE PAR LAYOUT")
            report_lines.append("-" * 30)
            
            for layout_name, perf in analysis['layouts_performance'].items():
                report_lines.append(f"\n📋 {layout_name}")
                report_lines.append(f"  • Viable: {'✅' if perf['viable'] else '❌'}")
                report_lines.append(f"  • Taux de complétion: {perf['completion_rate']:.1%}")
                report_lines.append(f"  • Parties jouées: {perf['games_played']}")
                
                if 'metrics' in perf and perf['metrics']:
                    metrics = perf['metrics']
                    report_lines.append(f"  • Steps moyen: {metrics.get('avg_completion_steps', 0):.0f}")
                    report_lines.append(f"  • Meilleur temps: {metrics.get('fastest_completion', 0):.0f} steps")
                    report_lines.append(f"  • Score d'efficacité: {metrics.get('efficiency_score', 0):.3f}")
                
                if 'behavioral' in perf:
                    behavioral = perf['behavioral']
                    report_lines.append(f"  • Difficulté: {behavioral.get('layout_difficulty', 'unknown')}")
                    report_lines.append(f"  • Coordination requise: {behavioral.get('coordination_required', 'unknown')}")
                    report_lines.append(f"  • Déterminisme: {behavioral.get('determinism', 'unknown')}")
        
        # Insights comportementaux
        if 'behavioral_insights' in analysis:
            insights = analysis['behavioral_insights']
            report_lines.append("\n🧠 INSIGHTS COMPORTEMENTAUX")
            report_lines.append("-" * 30)
            
            # Distribution des difficultés
            if 'difficulty_distribution' in insights:
                report_lines.append("\n📈 Distribution des difficultés:")
                for difficulty, count in insights['difficulty_distribution'].items():
                    report_lines.append(f"  • {difficulty}: {count} layouts")
            
            # Exigences de coordination
            if 'coordination_requirements' in insights:
                report_lines.append("\n🤝 Exigences de coordination:")
                for coord, count in insights['coordination_requirements'].items():
                    report_lines.append(f"  • {coord}: {count} layouts")
            
            # Corrélations de performance
            if 'performance_correlations' in insights:
                corr = insights['performance_correlations']
                report_lines.append("\n📊 Corrélations de performance:")
                
                if 'difficulty_vs_steps' in corr:
                    report_lines.append("  • Difficulté vs Steps moyens:")
                    for diff, steps in corr['difficulty_vs_steps'].items():
                        report_lines.append(f"    - {diff}: {steps:.0f} steps")
                
                if 'coordination_vs_efficiency' in corr:
                    report_lines.append("  • Coordination vs Efficacité:")
                    for coord, eff in corr['coordination_vs_efficiency'].items():
                        report_lines.append(f"    - {coord}: {eff:.3f}")
        
        # Analyse des parties individuelles
        if 'individual_games' in analysis:
            report_lines.append("\n🎮 ANALYSE DES PARTIES INDIVIDUELLES")
            report_lines.append("-" * 40)
            
            for layout_name, games_analysis in analysis['individual_games'].items():
                report_lines.append(f"\n📋 {layout_name}")
                report_lines.append(f"  • Total parties: {games_analysis.get('total_games', 0)}")
                report_lines.append(f"  • Parties complétées: {games_analysis.get('completed_games', 0)}")
                
                # Performance des agents
                if 'agent_performance' in games_analysis:
                    ap = games_analysis['agent_performance']
                    report_lines.append("  • Performance des agents:")
                    for i in range(2):
                        actions = ap.get('avg_actions_per_game', [0, 0])[i]
                        interactions = ap.get('avg_interactions_per_game', [0, 0])[i]
                        distance = ap.get('avg_distance_per_game', [0, 0])[i]
                        report_lines.append(f"    - Agent {i}: {actions:.1f} actions/partie, {interactions:.1f} interactions/partie, {distance:.1f} distance/partie")
        
        # Analyse des événements
        if 'event_analysis' in analysis:
            report_lines.append("\n🔍 ANALYSE DES ÉVÉNEMENTS")
            report_lines.append("-" * 30)
            
            for layout_name, event_analysis in analysis['event_analysis'].items():
                report_lines.append(f"\n📋 {layout_name}")
                
                # Efficacité des pickups
                if 'pickup_efficiency' in event_analysis:
                    pe = event_analysis['pickup_efficiency']
                    total_pickups = pe.get('total_pickups', [0, 0])
                    useful_pickups = pe.get('useful_pickups', [0, 0])
                    efficiency = pe.get('efficiency_rate', [0, 0])
                    
                    report_lines.append("  • Efficacité des pickups:")
                    for i in range(2):
                        report_lines.append(f"    - Agent {i}: {useful_pickups[i]}/{total_pickups[i]} ({efficiency[i]:.1%})")
                
                # Analyse du potting
                if 'potting_analysis' in event_analysis:
                    pa = event_analysis['potting_analysis']
                    report_lines.append("  • Analyse du potting:")
                    for pot_type in ['optimal', 'viable', 'catastrophic', 'useless']:
                        onion_total = sum(pa.get(pot_type, {}).get('onion', [0, 0]))
                        tomato_total = sum(pa.get(pot_type, {}).get('tomato', [0, 0]))
                        if onion_total + tomato_total > 0:
                            report_lines.append(f"    - {pot_type}: {onion_total} oignons, {tomato_total} tomates")
        
        report_text = "\n".join(report_lines)
        
        # Sauvegarder si demandé
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"📄 Rapport sauvegardé: {output_file}")
        
        return report_text
    
    def create_visualizations(self, analysis: Dict, output_dir: str = "analysis_plots") -> None:
        """Crée des visualisations des résultats."""
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        Path(output_dir).mkdir(exist_ok=True)
        
        # Style
        plt.style.use('default')
        sns.set_palette("husl")
        
        # 1. Distribution des taux de complétion
        if 'layouts_performance' in analysis:
            completion_rates = []
            layout_names = []
            
            for layout_name, perf in analysis['layouts_performance'].items():
                if perf['viable']:
                    completion_rates.append(perf['completion_rate'])
                    layout_names.append(layout_name)
            
            if completion_rates:
                plt.figure(figsize=(12, 6))
                bars = plt.bar(layout_names, completion_rates)
                plt.title('Taux de Complétion par Layout')
                plt.ylabel('Taux de Complétion')
                plt.xlabel('Layout')
                plt.xticks(rotation=45)
                plt.ylim(0, 1)
                
                # Colorer selon le taux
                for bar, rate in zip(bars, completion_rates):
                    if rate == 1.0:
                        bar.set_color('green')
                    elif rate > 0.5:
                        bar.set_color('orange')
                    elif rate > 0:
                        bar.set_color('red')
                    else:
                        bar.set_color('darkred')
                
                plt.tight_layout()
                plt.savefig(f"{output_dir}/completion_rates.png", dpi=300, bbox_inches='tight')
                plt.close()
        
        # 2. Distribution des efficacités
        if 'layouts_performance' in analysis:
            efficiency_scores = []
            layout_names = []
            
            for layout_name, perf in analysis['layouts_performance'].items():
                if perf['viable'] and 'metrics' in perf:
                    efficiency = perf['metrics'].get('efficiency_score', 0)
                    efficiency_scores.append(efficiency)
                    layout_names.append(layout_name)
            
            if efficiency_scores:
                plt.figure(figsize=(10, 6))
                plt.hist(efficiency_scores, bins=10, alpha=0.7, edgecolor='black')
                plt.title('Distribution des Scores d\'Efficacité')
                plt.xlabel('Score d\'Efficacité')
                plt.ylabel('Nombre de Layouts')
                plt.axvline(np.mean(efficiency_scores), color='red', linestyle='--', 
                           label=f'Moyenne: {np.mean(efficiency_scores):.3f}')
                plt.legend()
                plt.tight_layout()
                plt.savefig(f"{output_dir}/efficiency_distribution.png", dpi=300, bbox_inches='tight')
                plt.close()
        
        # 3. Corrélations comportementales
        if 'behavioral_insights' in analysis and 'performance_correlations' in analysis['behavioral_insights']:
            corr = analysis['behavioral_insights']['performance_correlations']
            
            # Difficulté vs Steps
            if 'difficulty_vs_steps' in corr:
                difficulties = list(corr['difficulty_vs_steps'].keys())
                steps = list(corr['difficulty_vs_steps'].values())
                
                plt.figure(figsize=(8, 6))
                bars = plt.bar(difficulties, steps)
                plt.title('Steps Moyens par Niveau de Difficulté')
                plt.ylabel('Steps Moyens')
                plt.xlabel('Niveau de Difficulté')
                
                # Gradient de couleur
                colors = ['green', 'orange', 'red']
                for bar, color in zip(bars, colors[:len(bars)]):
                    bar.set_color(color)
                
                plt.tight_layout()
                plt.savefig(f"{output_dir}/difficulty_vs_steps.png", dpi=300, bbox_inches='tight')
                plt.close()
        
        print(f"📊 Visualisations sauvegardées dans: {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description="Analyse des résultats d'évaluation Overcooked")
    parser.add_argument('files', nargs='+', help='Fichiers JSON à analyser')
    parser.add_argument('--compare', action='store_true', help='Comparer plusieurs modes')
    parser.add_argument('--detailed', action='store_true', help='Analyse détaillée avec parties individuelles')
    parser.add_argument('--report', help='Fichier de sortie pour le rapport')
    parser.add_argument('--plots', help='Répertoire pour les graphiques', default='analysis_plots')
    parser.add_argument('--no-plots', action='store_true', help='Désactiver la génération de graphiques')
    
    args = parser.parse_args()
    
    analyzer = OvercookedResultsAnalyzer()
    
    print("🔍 ANALYSE DES RÉSULTATS OVERCOOKED")
    print("=" * 40)
    
    # Charger les données
    data_list = []
    for filepath in args.files:
        data = analyzer.load_results(filepath)
        if data:
            data_list.append(data)
    
    if not data_list:
        print("❌ Aucun fichier valide trouvé")
        sys.exit(1)
    
    # Analyse principale
    if args.compare and len(data_list) > 1:
        print("\n🔄 Comparaison de modes...")
        analysis = analyzer.compare_modes(data_list)
        
        # Analyser aussi chaque mode individuellement
        for i, data in enumerate(data_list):
            print(f"\n📊 Analyse du mode {i+1}...")
            if args.detailed and data.get('data_type') == 'detailed_with_individual_games':
                mode_analysis = analyzer.analyze_detailed_results(data)
            else:
                mode_analysis = analyzer.analyze_aggregated_results(data)
            
            # Fusionner avec l'analyse de comparaison
            analysis[f'mode_{i+1}_analysis'] = mode_analysis
    
    else:
        # Analyse d'un seul mode
        data = data_list[0]
        print(f"\n📊 Analyse des données...")
        
        if args.detailed and data.get('data_type') == 'detailed_with_individual_games':
            analysis = analyzer.analyze_detailed_results(data)
        else:
            analysis = analyzer.analyze_aggregated_results(data)
    
    # Générer le rapport
    print("\n📄 Génération du rapport...")
    report_file = args.report if args.report else None
    report = analyzer.generate_report(analysis, report_file)
    
    # Afficher le rapport
    print("\n" + report)
    
    # Créer les visualisations
    if not args.no_plots:
        try:
            print(f"\n📊 Génération des graphiques...")
            analyzer.create_visualizations(analysis, args.plots)
        except ImportError:
            print("⚠️ matplotlib/seaborn non disponible, graphiques ignorés")
        except Exception as e:
            print(f"⚠️ Erreur lors de la génération des graphiques: {e}")
    
    print("\n✅ Analyse terminée!")

if __name__ == "__main__":
    main()
