#!/usr/bin/env python3
"""
Simulation Analysis - Analyseur des données de simulation Overcooked

Ce module analyse les données de simulation pour:
1. Visualiser la distribution des taux de completion des recettes (0%, x%<100%, 100%)
2. Analyser les layouts parfaits (100%) en fonction du nombre de steps
3. Sélectionner les 75 meilleurs layouts autour de la médiane de steps
4. Copier ces layouts dans un dossier de sélection

Author: Assistant
Date: 2025
"""

import os
import json
import glob
import shutil
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
import statistics

class SimulationAnalyzer:
    """Analyseur des données de simulation Overcooked"""
    
    def __init__(self, category: str = "symmetric"):
        """
        Initialise l'analyseur pour une catégorie spécifique.
        
        Args:
            category: Catégorie de layouts à analyser ("symmetric", "complementary", "symmetric_complex")
        """
        self.category = category
        self.data_simulation_dir = f"data_simulation/{category}"
        self.layouts_source_dir = f"overcooked_ai_py/data/layouts/generation_cesar/{category}"
        self.layouts_output_dir = f"overcooked_ai_py/data/layouts/generation_cesar/selection_{category}"
        self.output_dir = f"analysis_plots/{category}_simulation_summary"
        
        # Créer les dossiers de sortie s'ils n'existent pas
        os.makedirs(self.output_dir, exist_ok=True)
        
    def discover_layout_folders(self) -> List[str]:
        """Découvre tous les dossiers de layouts dans data_simulation pour la catégorie"""
        if not os.path.exists(self.data_simulation_dir):
            print(f"❌ Directory not found: {self.data_simulation_dir}")
            return []
        
        # Déterminer le préfixe de recherche selon la catégorie
        # Pour les catégories solo, on cherche les noms de base sans le suffixe _solo
        base_category = self.category
        if self.category.endswith("_solo"):
            base_category = self.category.replace("_solo", "")
        
        layout_pattern = f"data_simu_layout_{base_category}_"
        
        layout_dirs = [d for d in os.listdir(self.data_simulation_dir) 
                      if d.startswith(layout_pattern) and 
                      os.path.isdir(os.path.join(self.data_simulation_dir, d))]
        
        layout_names = []
        for dir_name in layout_dirs:
            # Extraire le numéro du layout : data_simu_layout_{base_category}_X -> X
            try:
                layout_num = dir_name.replace(layout_pattern, "")
                layout_names.append(layout_num)
            except:
                continue
        
        # Trier par numéro de layout
        layout_names.sort(key=lambda x: int(x) if x.isdigit() else float('inf'))
        return layout_names
    
    def load_layout_simulation_data(self, layout_number: str) -> Dict:
        """Charge les données de simulation pour un layout spécifique"""
        # Déterminer le préfixe de recherche selon la catégorie
        # Pour les catégories solo, on cherche les noms de base sans le suffixe _solo
        base_category = self.category
        if self.category.endswith("_solo"):
            base_category = self.category.replace("_solo", "")
        
        layout_dir = f"{self.data_simulation_dir}/data_simu_layout_{base_category}_{layout_number}"
        
        if not os.path.exists(layout_dir):
            return {}
        
        # Rechercher tous les fichiers JSON de simulation
        json_pattern = f"data_simu_layout_{base_category}_{layout_number}_game_*.json"
        json_files = glob.glob(os.path.join(layout_dir, json_pattern))
        
        all_recipes_completed = []
        all_steps = []
        all_scores = []
        layout_info = None
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    
                    if 'simulation_data' in data and 'info_sum' in data['simulation_data']:
                        info_sum = data['simulation_data']['info_sum']
                        
                        recipes_completed = info_sum.get('recipe_completed', 0)
                        steps = info_sum.get('step', 0)
                        score = info_sum.get('score', 0)
                        
                        all_recipes_completed.append(recipes_completed)
                        all_steps.append(steps)
                        all_scores.append(score)
                        
                        # Stocker les infos du layout (même pour tous les games)
                        if layout_info is None:
                            layout_info = {
                                'layout_name': info_sum.get('layout', f'layout_{self.category}_{layout_number}'),
                                'max_possible_recipes': self._estimate_max_recipes(info_sum)
                            }
                        
            except Exception as e:
                print(f"❌ Error loading {json_file}: {e}")
                continue
        
        if not all_recipes_completed:
            return {}
        
        # Calculer les statistiques
        avg_recipes = np.mean(all_recipes_completed)
        max_recipes = layout_info['max_possible_recipes'] if layout_info else 6  # Fallback à 6
        completion_percentage = (avg_recipes / max_recipes) * 100 if max_recipes > 0 else 0
        
        avg_steps = np.mean(all_steps)
        avg_score = np.mean(all_scores)
        
        return {
            'layout_number': layout_number,
            'layout_name': layout_info['layout_name'] if layout_info else f'layout_{self.category}_{layout_number}',
            'completion_percentage': completion_percentage,
            'avg_recipes_completed': avg_recipes,
            'max_possible_recipes': max_recipes,
            'avg_steps': avg_steps,
            'avg_score': avg_score,
            'num_simulations': len(all_recipes_completed),
            'all_recipes': all_recipes_completed,
            'all_steps': all_steps,
            'all_scores': all_scores
        }
    
    def _estimate_max_recipes(self, info_sum: Dict) -> int:
        """Estime le nombre maximum de recettes possible basé sur les données"""
        # Chercher des indices dans les données
        all_orders = info_sum.get('all_orders', [])
        if all_orders:
            return len(all_orders)
        
        # Heuristique basée sur les observations des données existantes
        return 6  # Valeur par défaut observée dans les données
    
    def analyze_all_layouts(self) -> Dict[str, Dict]:
        """Analyse tous les layouts et compile les statistiques"""
        layout_numbers = self.discover_layout_folders()
        
        print(f"🔍 Found {len(layout_numbers)} layouts to analyze")
        
        all_layout_data = {}
        successful_analyses = 0
        
        for layout_num in layout_numbers:
            print(f"📊 Analyzing layout {layout_num}...", end=" ")
            
            layout_data = self.load_layout_simulation_data(layout_num)
            
            if layout_data:
                all_layout_data[layout_num] = layout_data
                successful_analyses += 1
                print(f"✅ {layout_data['completion_percentage']:.1f}% completion")
            else:
                print("❌ No data")
        
        print(f"\n✅ Successfully analyzed {successful_analyses}/{len(layout_numbers)} layouts")
        return all_layout_data
    
    def categorize_layouts_by_completion(self, layout_data: Dict[str, Dict]) -> Dict[str, List]:
        """Catégorise les layouts selon leur taux de completion"""
        categories = {
            '0_percent': [],      # 0% de completion
            'partial': [],        # Entre 0% et 100%
            '100_percent': []     # 100% de completion
        }
        
        for layout_num, data in layout_data.items():
            completion = data['completion_percentage']
            
            if completion == 0:
                categories['0_percent'].append((layout_num, data))
            elif completion == 100:
                categories['100_percent'].append((layout_num, data))
            else:
                categories['partial'].append((layout_num, data))
        
        # Trier par layout number
        for category in categories.values():
            category.sort(key=lambda x: int(x[0]))
        
        return categories
    
    def create_completion_distribution_chart(self, categories: Dict[str, List]) -> str:
        """Crée un graphique en barres de la distribution des completions"""
        
        counts = {
            '0% Completion': len(categories['0_percent']),
            'Partial (0%<x<100%)': len(categories['partial']),
            '100% Completion': len(categories['100_percent'])
        }
        
        # Créer le graphique
        plt.figure(figsize=(12, 8))
        
        # Couleurs pour chaque catégorie
        colors = ['red', 'orange', 'green']
        bars = plt.bar(counts.keys(), counts.values(), color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        
        # Ajouter les valeurs sur les barres
        for bar, count in zip(bars, counts.values()):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{count}\nlayouts', ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        # Configuration du graphique
        total_layouts = sum(counts.values())
        plt.title(f'Distribution des Layouts {self.category.upper()} selon le Taux de Completion des Recettes\n'
                 f'Total: {total_layouts} layouts analysés', fontsize=14, fontweight='bold')
        plt.ylabel('Nombre de Layouts', fontsize=12)
        plt.xlabel('Catégorie de Completion', fontsize=12)
        
        # Ajouter les pourcentages
        for i, (category, count) in enumerate(counts.items()):
            percentage = (count / total_layouts) * 100
            plt.text(i, count/2, f'{percentage:.1f}%', ha='center', va='center', 
                    fontsize=14, fontweight='bold', color='white')
        
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/completion_distribution_{self.category}.png"
        os.makedirs(self.output_dir, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def analyze_perfect_layouts_steps(self, perfect_layouts: List[Tuple[str, Dict]]) -> Dict:
        """Analyse les layouts parfaits en fonction du nombre de steps"""
        
        steps_data = []
        layout_steps_info = []
        
        for layout_num, data in perfect_layouts:
            avg_steps = data['avg_steps']
            steps_data.append(avg_steps)
            layout_steps_info.append((layout_num, avg_steps, data))
        
        if not steps_data:
            return {}
        
        # Calculer les statistiques
        median_steps = statistics.median(steps_data)
        mean_steps = statistics.mean(steps_data)
        std_steps = statistics.stdev(steps_data) if len(steps_data) > 1 else 0
        min_steps = min(steps_data)
        max_steps = max(steps_data)
        
        # Trier par nombre de steps
        layout_steps_info.sort(key=lambda x: x[1])
        
        return {
            'steps_data': steps_data,
            'layout_steps_info': layout_steps_info,
            'median_steps': median_steps,
            'mean_steps': mean_steps,
            'std_steps': std_steps,
            'min_steps': min_steps,
            'max_steps': max_steps,
            'total_perfect_layouts': len(perfect_layouts)
        }
    
    def create_perfect_layouts_steps_chart(self, steps_analysis: Dict) -> str:
        """Crée un histogramme des layouts parfaits en fonction du nombre de steps"""
        
        steps_data = steps_analysis['steps_data']
        median_steps = steps_analysis['median_steps']
        mean_steps = steps_analysis['mean_steps']
        
        plt.figure(figsize=(14, 10))
        
        # Créer l'histogramme
        n_bins = min(30, len(set(steps_data)))  # Maximum 30 bins
        counts, bins, patches = plt.hist(steps_data, bins=n_bins, alpha=0.7, color='green', 
                                        edgecolor='black', linewidth=1)
        
        # Ajouter les lignes de médiane et moyenne
        plt.axvline(median_steps, color='red', linestyle='--', linewidth=3, 
                   label=f'Médiane: {median_steps:.1f} steps')
        plt.axvline(mean_steps, color='blue', linestyle='--', linewidth=3, 
                   label=f'Moyenne: {mean_steps:.1f} steps')
        
        # Configuration du graphique
        plt.title(f'Distribution des Layouts {self.category.upper()} Parfaits (100% completion) par Nombre de Steps\n'
                 f'Total: {len(steps_data)} layouts analysés', fontsize=14, fontweight='bold')
        plt.xlabel('Nombre de Steps Moyen', fontsize=12)
        plt.ylabel('Nombre de Layouts', fontsize=12)
        plt.legend(fontsize=12)
        plt.grid(True, alpha=0.3)
        
        # Ajouter des statistiques textuelles
        stats_text = (f'Statistiques:\n'
                     f'Min: {steps_analysis["min_steps"]:.1f} steps\n'
                     f'Max: {steps_analysis["max_steps"]:.1f} steps\n'
                     f'Écart-type: {steps_analysis["std_steps"]:.1f} steps')
        
        plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.4", facecolor="lightblue", alpha=0.8))
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/perfect_layouts_steps_distribution_{self.category}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def select_median_layouts(self, steps_analysis: Dict, target_count: int = 75) -> List[Tuple[str, float, Dict]]:
        """Sélectionne les layouts les plus proches de la médiane"""
        
        layout_steps_info = steps_analysis['layout_steps_info']
        median_steps = steps_analysis['median_steps']
        
        # Calculer la distance à la médiane pour chaque layout
        layouts_with_distance = []
        for layout_num, avg_steps, data in layout_steps_info:
            distance_to_median = abs(avg_steps - median_steps)
            layouts_with_distance.append((layout_num, avg_steps, data, distance_to_median))
        
        # Trier par distance à la médiane (plus proche en premier)
        # En cas d'égalité, privilégier les layouts avec steps == médiane
        layouts_with_distance.sort(key=lambda x: (x[3], abs(x[1] - median_steps)))
        
        # Sélectionner les target_count premiers
        selected_layouts = layouts_with_distance[:target_count]
        
        print(f"\n🎯 Sélection des {len(selected_layouts)} layouts les plus proches de la médiane ({median_steps:.1f} steps):")
        
        # Afficher quelques statistiques sur la sélection
        selected_steps = [x[1] for x in selected_layouts]
        min_selected = min(selected_steps)
        max_selected = max(selected_steps)
        avg_selected = statistics.mean(selected_steps)
        
        print(f"   📊 Range des steps sélectionnés: {min_selected:.1f} - {max_selected:.1f}")
        print(f"   📊 Moyenne des steps sélectionnés: {avg_selected:.1f}")
        print(f"   📊 Layouts avec steps exactement égaux à la médiane: {sum(1 for x in selected_layouts if abs(x[1] - median_steps) < 0.1)}")
        
        return [(x[0], x[1], x[2]) for x in selected_layouts]
    
    def copy_selected_layouts(self, selected_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Copie les layouts sélectionnés dans le dossier de destination"""
        
        # Créer le dossier de destination s'il n'existe pas
        os.makedirs(self.layouts_output_dir, exist_ok=True)
        
        copied_count = 0
        failed_count = 0
        
        print(f"\n📁 Copie des layouts vers {self.layouts_output_dir}:")
        
        # Déterminer le préfixe de source selon la catégorie
        # Pour les catégories solo, on cherche les layouts de base sans le suffixe _solo
        base_category = self.category
        if self.category.endswith("_solo"):
            base_category = self.category.replace("_solo", "")
        
        for layout_num, avg_steps, data in selected_layouts:
            # Le fichier source utilise le nom de base
            source_file = f"{self.layouts_source_dir.replace(self.category, base_category)}/layout_{base_category}_{layout_num}.layout"
            # Le fichier de destination garde le nom de la catégorie complète
            dest_file = f"{self.layouts_output_dir}/layout_{self.category}_{layout_num}.layout"
            
            try:
                if os.path.exists(source_file):
                    shutil.copy2(source_file, dest_file)
                    copied_count += 1
                    print(f"   ✅ Copié layout_{self.category}_{layout_num} ({avg_steps:.1f} steps)")
                else:
                    failed_count += 1
                    print(f"   ❌ Source non trouvée: layout_{base_category}_{layout_num} -> {source_file}")
                    
            except Exception as e:
                failed_count += 1
                print(f"   ❌ Erreur lors de la copie de layout_{self.category}_{layout_num}: {e}")
        
        # Créer un fichier de résumé de la sélection
        summary_file = f"{self.layouts_output_dir}/selection_summary_{self.category}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(f"RÉSUMÉ DE LA SÉLECTION DE LAYOUTS {self.category.upper()}\n")
            f.write("="*70 + "\n\n")
            f.write(f"Date de sélection: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Catégorie de layouts: {self.category}\n")
            if self.category.endswith("_solo"):
                f.write(f"Note: Mode SOLO - Layouts basés sur {base_category}\n")
            f.write(f"Nombre total de layouts sélectionnés: {len(selected_layouts)}\n")
            f.write(f"Layouts copiés avec succès: {copied_count}\n")
            f.write(f"Échecs de copie: {failed_count}\n\n")
            
            if selected_layouts:
                selected_steps = [x[1] for x in selected_layouts]
                median_steps = statistics.median(selected_steps)
                f.write(f"Critère de sélection: Proximité à la médiane\n")
                f.write(f"Médiane des steps: {median_steps:.1f}\n")
                f.write(f"Range des steps: {min(selected_steps):.1f} - {max(selected_steps):.1f}\n")
                f.write(f"Moyenne des steps: {statistics.mean(selected_steps):.1f}\n\n")
            
            f.write("LISTE DES LAYOUTS SÉLECTIONNÉS:\n")
            f.write("-" * 40 + "\n")
            for i, (layout_num, avg_steps, data) in enumerate(selected_layouts, 1):
                f.write(f"{i:3d}. Layout {self.category}_{layout_num:3s}: {avg_steps:6.1f} steps (Score: {data['avg_score']:.1f})\n")
        
        print(f"\n✅ Copie terminée: {copied_count}/{len(selected_layouts)} layouts copiés")
        print(f"📄 Résumé sauvegardé: {summary_file}")
        
        return self.layouts_output_dir
    
    def create_selection_visualization(self, selected_layouts: List[Tuple[str, float, Dict]], 
                                     steps_analysis: Dict) -> str:
        """Crée une visualisation des layouts sélectionnés"""
        
        all_steps = steps_analysis['steps_data']
        selected_steps = [x[1] for x in selected_layouts]
        median_steps = steps_analysis['median_steps']
        
        plt.figure(figsize=(16, 10))
        
        # Subplot 1: Histogramme de tous les layouts avec sélection mise en évidence
        plt.subplot(2, 1, 1)
        
        # Histogramme de tous les layouts parfaits
        n_bins = min(30, len(set(all_steps)))
        plt.hist(all_steps, bins=n_bins, alpha=0.5, color='lightblue', 
                label=f'Tous les layouts parfaits ({len(all_steps)})', edgecolor='black')
        
        # Histogramme des layouts sélectionnés
        plt.hist(selected_steps, bins=n_bins, alpha=0.8, color='red', 
                label=f'Layouts sélectionnés ({len(selected_steps)})', edgecolor='darkred')
        
        # Ligne de médiane
        plt.axvline(median_steps, color='green', linestyle='--', linewidth=3, 
                   label=f'Médiane: {median_steps:.1f} steps')
        
        plt.title(f'Sélection des Layouts {self.category.upper()} Proches de la Médiane', fontsize=14, fontweight='bold')
        plt.xlabel('Nombre de Steps Moyen', fontsize=12)
        plt.ylabel('Nombre de Layouts', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Subplot 2: Scatter plot des layouts sélectionnés
        plt.subplot(2, 1, 2)
        
        layout_numbers = [int(x[0]) if x[0].isdigit() else 0 for x in selected_layouts]
        steps_values = [x[1] for x in selected_layouts]
        scores = [x[2]['avg_score'] for x in selected_layouts]
        
        # Utiliser la score comme taille des points
        sizes = [max(20, min(200, score * 5)) for score in scores]
        
        scatter = plt.scatter(layout_numbers, steps_values, c=scores, s=sizes, 
                            alpha=0.7, cmap='viridis', edgecolors='black')
        
        # Ligne de médiane
        plt.axhline(median_steps, color='red', linestyle='--', linewidth=2, 
                   label=f'Médiane: {median_steps:.1f} steps')
        
        plt.title(f'Layouts {self.category.upper()} Sélectionnés: Numéro vs Steps (taille = score)', fontsize=14, fontweight='bold')
        plt.xlabel('Numéro de Layout', fontsize=12)
        plt.ylabel('Nombre de Steps Moyen', fontsize=12)
        plt.colorbar(scatter, label='Score Moyen')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/selected_layouts_visualization_{self.category}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def generate_comprehensive_report(self, layout_data: Dict[str, Dict], 
                                    categories: Dict[str, List],
                                    steps_analysis: Dict,
                                    selected_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Génère un rapport complet de l'analyse"""
        
        report_path = f"{self.output_dir}/simulation_analysis_report_{self.category}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"RAPPORT COMPLET D'ANALYSE DES SIMULATIONS OVERCOOKED - {self.category.upper()}\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"📅 Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📁 Catégorie analysée: {self.category}\n")
            f.write(f"📂 Dossier source des données: {self.data_simulation_dir}\n\n")
            
            # 1. Statistiques globales
            f.write("📊 STATISTIQUES GLOBALES\n")
            f.write("-" * 40 + "\n")
            total_layouts = len(layout_data)
            f.write(f"Nombre total de layouts analysés: {total_layouts}\n")
            
            # Distribution par catégorie
            zero_count = len(categories['0_percent'])
            partial_count = len(categories['partial'])
            perfect_count = len(categories['100_percent'])
            
            f.write(f"Layouts à 0% completion: {zero_count} ({zero_count/total_layouts*100:.1f}%)\n")
            f.write(f"Layouts partiels (0%<x<100%): {partial_count} ({partial_count/total_layouts*100:.1f}%)\n")
            f.write(f"Layouts parfaits (100%): {perfect_count} ({perfect_count/total_layouts*100:.1f}%)\n\n")
            
            # 2. Analyse des layouts parfaits
            if steps_analysis:
                f.write("🏆 ANALYSE DES LAYOUTS PARFAITS (100% COMPLETION)\n")
                f.write("-" * 50 + "\n")
                f.write(f"Nombre de layouts parfaits: {steps_analysis['total_perfect_layouts']}\n")
                f.write(f"Nombre de steps - Minimum: {steps_analysis['min_steps']:.1f}\n")
                f.write(f"Nombre de steps - Maximum: {steps_analysis['max_steps']:.1f}\n")
                f.write(f"Nombre de steps - Moyenne: {steps_analysis['mean_steps']:.1f}\n")
                f.write(f"Nombre de steps - Médiane: {steps_analysis['median_steps']:.1f}\n")
                f.write(f"Nombre de steps - Écart-type: {steps_analysis['std_steps']:.1f}\n\n")
            
            # 3. Sélection des layouts
            f.write(f"🎯 SÉLECTION DES LAYOUTS POUR {self.category.upper()}\n")
            f.write("-" * 45 + "\n")
            f.write(f"Nombre de layouts sélectionnés: {len(selected_layouts)}\n")
            f.write(f"Critère de sélection: Proximité à la médiane des steps\n")
            
            if selected_layouts:
                selected_steps = [x[1] for x in selected_layouts]
                f.write(f"Range des steps sélectionnés: {min(selected_steps):.1f} - {max(selected_steps):.1f}\n")
                f.write(f"Moyenne des steps sélectionnés: {statistics.mean(selected_steps):.1f}\n")
                
                # Compter les layouts exactement à la médiane
                if steps_analysis:
                    median_exact_count = sum(1 for x in selected_layouts 
                                           if abs(x[1] - steps_analysis['median_steps']) < 0.1)
                    f.write(f"Layouts avec steps = médiane (±0.1): {median_exact_count}\n\n")
            
            # 4. Top 10 des layouts sélectionnés
            f.write("🥇 TOP 10 DES LAYOUTS SÉLECTIONNÉS\n")
            f.write("-" * 35 + "\n")
            for i, (layout_num, avg_steps, data) in enumerate(selected_layouts[:10], 1):
                distance = abs(avg_steps - steps_analysis['median_steps']) if steps_analysis else 0
                f.write(f"{i:2d}. Layout {self.category}_{layout_num:3s}: {avg_steps:6.1f} steps "
                       f"(distance médiane: {distance:5.1f}, score: {data['avg_score']:5.1f})\n")
            
            if len(selected_layouts) > 10:
                f.write(f"... et {len(selected_layouts) - 10} autres layouts\n")
            
            f.write(f"\n💾 Dossier de destination: {self.layouts_output_dir}\n")
            f.write(f"📊 Fichiers de visualisation générés dans: {self.output_dir}\n")
        
        return report_path

class SimulationEvaluator:
    """Évaluateur principal pour l'analyse complète des simulations"""
    
    def __init__(self, category: str = "symmetric"):
        """
        Initialise l'évaluateur pour une catégorie spécifique.
        
        Args:
            category: Catégorie de layouts à analyser ("symmetric", "complementary", "symmetric_complex")
        """
        self.category = category
        self.analyzer = SimulationAnalyzer(category)
    
    def run_complete_analysis(self, target_selection_count: int = 75):
        """Lance l'analyse complète des simulations pour la catégorie"""
        
        print(f"🚀 SIMULATION ANALYSIS - ANALYSE COMPLÈTE POUR {self.category.upper()}")
        print("=" * 70)
        
        # 1. Analyser tous les layouts
        print(f"\n📊 ÉTAPE 1: Analyse de tous les layouts {self.category}...")
        layout_data = self.analyzer.analyze_all_layouts()
        
        if not layout_data:
            print(f"❌ Aucune donnée de layout trouvée pour {self.category}!")
            return
        
        # 2. Catégoriser par taux de completion
        print("\n📈 ÉTAPE 2: Catégorisation par taux de completion...")
        categories = self.analyzer.categorize_layouts_by_completion(layout_data)
        
        print(f"   - Layouts à 0%: {len(categories['0_percent'])}")
        print(f"   - Layouts partiels: {len(categories['partial'])}")
        print(f"   - Layouts parfaits: {len(categories['100_percent'])}")
        
        # 3. Créer le graphique de distribution
        print("\n📊 ÉTAPE 3: Création du graphique de distribution...")
        dist_chart_path = self.analyzer.create_completion_distribution_chart(categories)
        print(f"   ✅ Graphique sauvegardé: {dist_chart_path}")
        
        # 4. Analyser les layouts parfaits
        if categories['100_percent']:
            print("\n🏆 ÉTAPE 4: Analyse des layouts parfaits...")
            steps_analysis = self.analyzer.analyze_perfect_layouts_steps(categories['100_percent'])
            
            print(f"   📊 Médiane des steps: {steps_analysis['median_steps']:.1f}")
            print(f"   📊 Moyenne des steps: {steps_analysis['mean_steps']:.1f}")
            print(f"   📊 Range: {steps_analysis['min_steps']:.1f} - {steps_analysis['max_steps']:.1f}")
            
            # 5. Créer le graphique des steps
            print("\n📈 ÉTAPE 5: Création du graphique des steps...")
            steps_chart_path = self.analyzer.create_perfect_layouts_steps_chart(steps_analysis)
            print(f"   ✅ Graphique sauvegardé: {steps_chart_path}")
            
            # 6. Sélectionner les layouts autour de la médiane
            print(f"\n🎯 ÉTAPE 6: Sélection des {target_selection_count} meilleurs layouts...")
            selected_layouts = self.analyzer.select_median_layouts(steps_analysis, target_count=target_selection_count)
            
            # 7. Copier les layouts sélectionnés
            print("\n📁 ÉTAPE 7: Copie des layouts sélectionnés...")
            output_dir = self.analyzer.copy_selected_layouts(selected_layouts)
            
            # 8. Créer la visualisation de la sélection
            print("\n🎨 ÉTAPE 8: Création de la visualisation de sélection...")
            selection_viz_path = self.analyzer.create_selection_visualization(selected_layouts, steps_analysis)
            print(f"   ✅ Visualisation sauvegardée: {selection_viz_path}")
            
            # 9. Générer le rapport complet
            print("\n📋 ÉTAPE 9: Génération du rapport complet...")
            report_path = self.analyzer.generate_comprehensive_report(
                layout_data, categories, steps_analysis, selected_layouts)
            print(f"   ✅ Rapport sauvegardé: {report_path}")
            
        else:
            print("❌ Aucun layout parfait trouvé!")
            steps_analysis = {}
            selected_layouts = []
        
        # Résumé final
        print(f"\n🎉 ANALYSE TERMINÉE POUR {self.category.upper()}!")
        print("=" * 50)
        print(f"📊 {len(layout_data)} layouts analysés")
        print(f"🏆 {len(categories['100_percent'])} layouts parfaits trouvés")
        print(f"🎯 {len(selected_layouts)} layouts sélectionnés pour {self.category}")
        print(f"📁 Layouts copiés dans: {self.analyzer.layouts_output_dir}")
        print(f"📈 Graphiques dans: {self.analyzer.output_dir}")
    
    @staticmethod
    def analyze_all_categories(target_selection_count: int = 75):
        """Analyse toutes les catégories disponibles dans data_simulation"""
        
        # Détecter les catégories disponibles
        base_dir = "data_simulation"
        if not os.path.exists(base_dir):
            print(f"❌ Dossier {base_dir} non trouvé!")
            return
        
        available_categories = [d for d in os.listdir(base_dir) 
                              if os.path.isdir(os.path.join(base_dir, d))]
        
        if not available_categories:
            print(f"❌ Aucune catégorie trouvée dans {base_dir}")
            return
        
        # Trier les catégories pour un affichage cohérent
        available_categories.sort()
        
        print(f"🔍 Catégories détectées: {available_categories}")
        print(f"📊 Total: {len(available_categories)} catégories à analyser")
        
        # Statistiques globales
        total_layouts = 0
        total_perfect_layouts = 0
        total_selected_layouts = 0
        
        for i, category in enumerate(available_categories, 1):
            print(f"\n{'='*80}")
            print(f"🚀 ANALYSE {i}/{len(available_categories)}: {category.upper()}")
            print(f"{'='*80}")
            
            try:
                evaluator = SimulationEvaluator(category)
                
                # Analyser avec un nombre adapté selon la catégorie
                # Pour les catégories solo, on peut sélectionner moins de layouts
                adjusted_target = target_selection_count
                if "_solo" in category:
                    adjusted_target = min(target_selection_count, 50)  # Limiter pour les modes solo
                    print(f"🎯 Mode solo détecté - Sélection ajustée à {adjusted_target} layouts max")
                
                result_summary = evaluator.run_complete_analysis_with_summary(adjusted_target)
                
                # Accumuler les statistiques
                total_layouts += result_summary.get('total_layouts', 0)
                total_perfect_layouts += result_summary.get('perfect_layouts', 0)
                total_selected_layouts += result_summary.get('selected_layouts', 0)
                
                print(f"✅ ANALYSE TERMINÉE POUR {category.upper()}")
                print(f"   📊 {result_summary.get('total_layouts', 0)} layouts analysés")
                print(f"   🏆 {result_summary.get('perfect_layouts', 0)} layouts parfaits")
                print(f"   🎯 {result_summary.get('selected_layouts', 0)} layouts sélectionnés")
                
            except Exception as e:
                print(f"❌ ERREUR lors de l'analyse de {category}: {e}")
                print(f"   Passage à la catégorie suivante...")
                continue
        
        # Résumé global final
        print(f"\n{'='*80}")
        print(f"🎊 ANALYSE GLOBALE TERMINÉE - TOUTES CATÉGORIES")
        print(f"{'='*80}")
        print(f"📈 STATISTIQUES GLOBALES:")
        print(f"   🗂️ Catégories analysées: {len(available_categories)}")
        print(f"   📊 Total layouts analysés: {total_layouts}")
        print(f"   🏆 Total layouts parfaits: {total_perfect_layouts}")
        print(f"   🎯 Total layouts sélectionnés: {total_selected_layouts}")
        
        if total_layouts > 0:
            perfect_rate = (total_perfect_layouts / total_layouts) * 100
            print(f"   📊 Taux de layouts parfaits: {perfect_rate:.1f}%")
        
        print(f"\n📁 Résultats disponibles dans:")
        for category in available_categories:
            print(f"   • analysis_plots/{category}_simulation_summary/")
            print(f"   • overcooked_ai_py/data/layouts/generation_cesar/selection_{category}/")
    
    def run_complete_analysis_with_summary(self, target_selection_count: int = 75) -> dict:
        """Version de run_complete_analysis qui retourne un résumé pour les statistiques globales"""
        
        print(f"🚀 SIMULATION ANALYSIS - ANALYSE COMPLÈTE POUR {self.category.upper()}")
        print("=" * 70)
        
        # 1. Analyser tous les layouts
        print(f"\n📊 ÉTAPE 1: Analyse de tous les layouts {self.category}...")
        layout_data = self.analyzer.analyze_all_layouts()
        
        if not layout_data:
            print(f"❌ Aucune donnée de layout trouvée pour {self.category}!")
            return {'total_layouts': 0, 'perfect_layouts': 0, 'selected_layouts': 0}
        
        # 2. Catégoriser par taux de completion
        print("\n📈 ÉTAPE 2: Catégorisation par taux de completion...")
        categories = self.analyzer.categorize_layouts_by_completion(layout_data)
        
        print(f"   - Layouts à 0%: {len(categories['0_percent'])}")
        print(f"   - Layouts partiels: {len(categories['partial'])}")
        print(f"   - Layouts parfaits: {len(categories['100_percent'])}")
        
        # 3. Créer le graphique de distribution
        print("\n📊 ÉTAPE 3: Création du graphique de distribution...")
        dist_chart_path = self.analyzer.create_completion_distribution_chart(categories)
        print(f"   ✅ Graphique sauvegardé: {dist_chart_path}")
        
        selected_layouts = []
        
        # 4. Analyser les layouts parfaits
        if categories['100_percent']:
            print("\n🏆 ÉTAPE 4: Analyse des layouts parfaits...")
            steps_analysis = self.analyzer.analyze_perfect_layouts_steps(categories['100_percent'])
            
            print(f"   📊 Médiane des steps: {steps_analysis['median_steps']:.1f}")
            print(f"   📊 Moyenne des steps: {steps_analysis['mean_steps']:.1f}")
            print(f"   📊 Range: {steps_analysis['min_steps']:.1f} - {steps_analysis['max_steps']:.1f}")
            
            # 5. Créer le graphique des steps
            print("\n📈 ÉTAPE 5: Création du graphique des steps...")
            steps_chart_path = self.analyzer.create_perfect_layouts_steps_chart(steps_analysis)
            print(f"   ✅ Graphique sauvegardé: {steps_chart_path}")
            
            # 6. Sélectionner les layouts autour de la médiane
            print(f"\n🎯 ÉTAPE 6: Sélection des {target_selection_count} meilleurs layouts...")
            selected_layouts = self.analyzer.select_median_layouts(steps_analysis, target_count=target_selection_count)
            
            # 7. Copier les layouts sélectionnés
            print("\n📁 ÉTAPE 7: Copie des layouts sélectionnés...")
            output_dir = self.analyzer.copy_selected_layouts(selected_layouts)
            
            # 8. Créer la visualisation de la sélection
            print("\n🎨 ÉTAPE 8: Création de la visualisation de sélection...")
            selection_viz_path = self.analyzer.create_selection_visualization(selected_layouts, steps_analysis)
            print(f"   ✅ Visualisation sauvegardée: {selection_viz_path}")
            
            # 9. Générer le rapport complet
            print("\n📋 ÉTAPE 9: Génération du rapport complet...")
            report_path = self.analyzer.generate_comprehensive_report(
                layout_data, categories, steps_analysis, selected_layouts)
            print(f"   ✅ Rapport sauvegardé: {report_path}")
            
        else:
            print("❌ Aucun layout parfait trouvé!")
            steps_analysis = {}
        
        # Résumé final
        print(f"\n🎉 ANALYSE TERMINÉE POUR {self.category.upper()}!")
        print("=" * 50)
        print(f"📊 {len(layout_data)} layouts analysés")
        print(f"🏆 {len(categories['100_percent'])} layouts parfaits trouvés")
        print(f"🎯 {len(selected_layouts)} layouts sélectionnés pour {self.category}")
        print(f"📁 Layouts copiés dans: {self.analyzer.layouts_output_dir}")
        print(f"📈 Graphiques dans: {self.analyzer.output_dir}")
        
        return {
            'total_layouts': len(layout_data),
            'perfect_layouts': len(categories['100_percent']),
            'selected_layouts': len(selected_layouts)
        }

def main():
    """Fonction principale avec support de paramètres"""
    import sys
    
    # Déterminer la catégorie à analyser
    if len(sys.argv) > 1:
        category = sys.argv[1]
        if category == "all":
            # Analyser toutes les catégories
            SimulationEvaluator.analyze_all_categories()
        else:
            # Analyser une catégorie spécifique
            evaluator = SimulationEvaluator(category)
            evaluator.run_complete_analysis()
    else:
        # Par défaut, analyser toutes les catégories disponibles
        print("💡 Usage: python simulation_analysis.py [category|all]")
        print("   Exemples de catégories: symmetric, complementary, symmetric_complex, symmetric_solo...")
        print("   'all' ou sans argument pour analyser toutes les catégories disponibles")
        print("\n🎯 Analyse par défaut: TOUTES LES CATÉGORIES DISPONIBLES")
        
        SimulationEvaluator.analyze_all_categories()

if __name__ == "__main__":
    main()
