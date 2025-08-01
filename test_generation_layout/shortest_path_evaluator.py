#!/usr/bin/env python3
"""
Shortest Path Evaluator - Analyseur des différences de distances solo vs duo

Ce module analyse les différences de distances entre les modes solo et duo pour:
1. Visualiser les distances solo et duo par layout
2. Calculer et visualiser les différences entre solo et duo
3. Sélectionner les layouts avec les plus grandes différences
4. Analyser la répartition des étapes totales en mode duo

Author: Assistant
Date: 2025
"""

import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
import statistics

class ShortestPathAnalyzer:
    """Analyseur des différences de distances solo vs duo"""
    
    def __init__(self, base_category: str = "all"):
        """
        Initialise l'analyseur pour les données de path evaluation.
        
        Args:
            base_category: Type d'analyse ("all" pour toutes les données)
        """
        self.base_category = base_category
        
        # Dossier de données
        self.data_dir = "path_evaluation_results"
        
        # Dossier de sortie
        self.output_dir = f"analysis_plots/path_comparison_analysis"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def discover_layout_data(self) -> List[Dict]:
        """Découvre et charge tous les données de layouts depuis path_evaluation_results"""
        
        all_layout_data = []
        
        if not os.path.exists(self.data_dir):
            print(f"❌ Dossier {self.data_dir} non trouvé!")
            return []
        
        # Chercher tous les fichiers recette_lot_X_results.json
        json_files = glob.glob(os.path.join(self.data_dir, "recette_lot_*_results.json"))
        
        print(f"🔍 Fichiers trouvés: {len(json_files)} fichiers de données")
        
        for json_file in json_files:
            try:
                print(f"   📂 Chargement de {os.path.basename(json_file)}...", end=" ")
                
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    
                    # Chaque fichier contient une liste de layouts avec leurs données
                    for layout_info in data:
                        if all(key in layout_info for key in ['layout_path', 'solo_distance', 'coop_distance']):
                            # Extraire le nom du layout depuis le path
                            layout_name = os.path.basename(layout_info['layout_path']).replace('.layout', '')
                            
                            layout_data = {
                                'layout_name': layout_name,
                                'layout_path': layout_info['layout_path'],
                                'solo_distance': layout_info['solo_distance'],
                                'coop_distance': layout_info['coop_distance'],
                                'improvement_ratio': layout_info.get('improvement_ratio', 0),
                                'difference': layout_info['coop_distance'] - layout_info['solo_distance'],
                                'efficiency_gain': layout_info['solo_distance'] - layout_info['coop_distance']
                            }
                            
                            all_layout_data.append(layout_data)
                    
                    print(f"✅ {len(data)} layouts chargés")
                    
            except Exception as e:
                print(f"❌ Erreur: {e}")
                continue
        
        print(f"\n✅ Total: {len(all_layout_data)} layouts chargés depuis tous les fichiers")
        return all_layout_data
    
    def analyze_layouts_comparison(self, layout_data: List[Dict]) -> Dict[str, Dict]:
        """Analyse comparative des layouts entre solo et duo"""
        
        comparison_data = {}
        
        print(f"\n📊 Analyse de {len(layout_data)} layouts...")
        
        for i, layout_info in enumerate(layout_data):
            layout_name = layout_info['layout_name']
            
            if i % 1000 == 0:
                print(f"   Traitement: {i}/{len(layout_data)} layouts...")
            
            # Calculer les statistiques
            solo_dist = layout_info['solo_distance']
            coop_dist = layout_info['coop_distance']
            
            difference = coop_dist - solo_dist
            ratio = coop_dist / solo_dist if solo_dist > 0 else 0
            
            comparison_data[layout_name] = {
                'layout_name': layout_name,
                'layout_path': layout_info['layout_path'],
                'solo_distance': solo_dist,
                'coop_distance': coop_dist,
                'steps_difference': difference,
                'steps_ratio': ratio,
                'efficiency_gain': -difference,  # Gain négatif = plus d'étapes en duo
                'improvement_ratio': layout_info.get('improvement_ratio', abs(difference/solo_dist) if solo_dist > 0 else 0)
            }
        
        print(f"\n✅ {len(comparison_data)} layouts analysés")
        return comparison_data
    
    def create_steps_comparison_chart(self, comparison_data: Dict[str, Dict]) -> str:
        """Crée un graphique comparatif des distances solo vs duo"""
        
        layout_names = []
        solo_distances = []
        coop_distances = []
        
        # Prendre un échantillon représentatif pour l'affichage (sinon trop de données)
        sample_size = min(100, len(comparison_data))
        sampled_data = dict(list(comparison_data.items())[:sample_size])
        
        for layout_name, data in sampled_data.items():
            layout_names.append(layout_name[:15] + "..." if len(layout_name) > 15 else layout_name)
            solo_distances.append(data['solo_distance'])
            coop_distances.append(data['coop_distance'])
        
        plt.figure(figsize=(20, 12))
        
        # Créer le graphique
        x = np.arange(len(layout_names))
        width = 0.35
        
        bars1 = plt.bar(x - width/2, solo_distances, width, label='Solo', 
                       alpha=0.8, color='blue', edgecolor='navy')
        bars2 = plt.bar(x + width/2, coop_distances, width, label='Duo', 
                       alpha=0.8, color='red', edgecolor='darkred')
        
        # Configuration
        plt.title(f'Comparaison des Distances: Solo vs Duo\n'
                 f'Échantillon de {len(sampled_data)} layouts (total: {len(comparison_data)})', 
                 fontsize=16, fontweight='bold')
        plt.xlabel('Layouts', fontsize=12)
        plt.ylabel('Distance Totale', fontsize=12)
        plt.legend(fontsize=12)
        
        # Configurer les ticks de l'axe X
        plt.xticks(x, layout_names, rotation=45, ha='right')
        plt.grid(True, alpha=0.3, axis='y')
        
        # Ajouter des statistiques
        all_solo = [data['solo_distance'] for data in comparison_data.values()]
        all_coop = [data['coop_distance'] for data in comparison_data.values()]
        
        avg_solo = np.mean(all_solo)
        avg_coop = np.mean(all_coop)
        avg_difference = avg_coop - avg_solo
        
        stats_text = (f'Moyennes globales:\n'
                     f'Solo: {avg_solo:.1f} steps\n'
                     f'Duo: {avg_coop:.1f} steps\n'
                     f'Différence: {avg_difference:.1f} steps\n'
                     f'Amélioration: {(avg_solo-avg_coop)/avg_solo*100:.1f}%')
        
        plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                fontsize=12, verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.4", facecolor="lightgreen", alpha=0.8))
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/distances_comparison_solo_vs_duo.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ Graphique des comparaisons sauvegardé: {output_path}")
        return output_path
    
    def create_difference_analysis_chart(self, comparison_data: Dict[str, Dict]) -> str:
        """Crée un graphique d'analyse des différences solo-duo"""
        
        differences = [data['steps_difference'] for data in comparison_data.values()]
        ratios = [data['steps_ratio'] for data in comparison_data.values()]
        improvements = [data['efficiency_gain'] for data in comparison_data.values()]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Graphique 1: Histogramme des différences
        ax1.hist(differences, bins=50, alpha=0.7, color='purple', edgecolor='black')
        ax1.axvline(np.mean(differences), color='red', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {np.mean(differences):.1f}')
        ax1.axvline(0, color='black', linestyle='-', linewidth=1, label='Égalité')
        ax1.set_title('Distribution des Différences (Duo - Solo)', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Différence de Distance', fontsize=12)
        ax1.set_ylabel('Nombre de Layouts', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Graphique 2: Histogramme des ratios
        ax2.hist(ratios, bins=50, alpha=0.7, color='orange', edgecolor='black')
        ax2.axvline(np.mean(ratios), color='red', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {np.mean(ratios):.2f}')
        ax2.axvline(1, color='black', linestyle='-', linewidth=1, label='Ratio = 1')
        ax2.set_title('Distribution des Ratios (Duo / Solo)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Ratio Distance Duo / Solo', fontsize=12)
        ax2.set_ylabel('Nombre de Layouts', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Graphique 3: Scatter plot Solo vs Duo
        solo_distances = [data['solo_distance'] for data in comparison_data.values()]
        coop_distances = [data['coop_distance'] for data in comparison_data.values()]
        
        # Utiliser un échantillon pour la lisibilité
        sample_size = min(2000, len(solo_distances))
        indices = np.random.choice(len(solo_distances), sample_size, replace=False)
        
        solo_sample = [solo_distances[i] for i in indices]
        coop_sample = [coop_distances[i] for i in indices]
        
        ax3.scatter(solo_sample, coop_sample, alpha=0.6, s=20)
        
        # Ligne y=x pour montrer l'égalité
        min_val = min(min(solo_sample), min(coop_sample))
        max_val = max(max(solo_sample), max(coop_sample))
        ax3.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='y=x (égalité)')
        
        ax3.set_title(f'Scatter Plot: Solo vs Duo\n(Échantillon de {sample_size} layouts)', 
                     fontsize=14, fontweight='bold')
        ax3.set_xlabel('Distance Solo', fontsize=12)
        ax3.set_ylabel('Distance Duo', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Graphique 4: Histogramme des améliorations
        ax4.hist(improvements, bins=50, alpha=0.7, color='green', edgecolor='black')
        ax4.axvline(np.mean(improvements), color='red', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {np.mean(improvements):.1f}')
        ax4.axvline(0, color='black', linestyle='-', linewidth=1, label='Pas d\'amélioration')
        ax4.set_title('Distribution des Améliorations (Solo - Duo)', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Amélioration (distances économisées)', fontsize=12)
        ax4.set_ylabel('Nombre de Layouts', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # Statistiques globales
        coop_better_count = sum(1 for diff in differences if diff < 0)
        solo_better_count = sum(1 for diff in differences if diff > 0)
        equal_count = sum(1 for diff in differences if abs(diff) < 1)
        
        stats_text = (f'Statistiques:\n'
                     f'Total layouts: {len(differences)}\n'
                     f'Duo meilleur: {coop_better_count} ({coop_better_count/len(differences)*100:.1f}%)\n'
                     f'Solo meilleur: {solo_better_count} ({solo_better_count/len(differences)*100:.1f}%)\n'
                     f'Équivalent: {equal_count} ({equal_count/len(differences)*100:.1f}%)\n'
                     f'Amélioration moyenne: {np.mean(improvements):.1f}')
        
        fig.suptitle('Analyse Complète des Différences Solo vs Duo', fontsize=16, fontweight='bold')
        
        # Ajouter les statistiques dans une zone libre
        fig.text(0.02, 0.02, stats_text, fontsize=11, 
                bbox=dict(boxstyle="round,pad=0.4", facecolor="lightblue", alpha=0.8))
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/difference_analysis_comprehensive.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ Graphique des différences sauvegardé: {output_path}")
        return output_path
    
    def select_high_difference_layouts(self, comparison_data: Dict[str, Dict], 
                                     selection_count: int = 50) -> List[Tuple[str, float, Dict]]:
        """Sélectionne les layouts avec les plus grandes différences solo-duo"""
        
        # Créer une liste avec les différences absolues (amélioration = solo - duo)
        layout_differences = []
        for layout_name, data in comparison_data.items():
            improvement = data['efficiency_gain']  # Solo - Duo (positif = duo meilleur)
            layout_differences.append((layout_name, improvement, data))
        
        # Trier par amélioration décroissante (plus grande amélioration en premier)
        layout_differences.sort(key=lambda x: x[1], reverse=True)
        
        # Sélectionner les premiers
        selected_layouts = layout_differences[:selection_count]
        
        print(f"\n🎯 Sélection des {len(selected_layouts)} layouts avec les plus grandes améliorations Solo→Duo:")
        
        # Afficher les statistiques de sélection
        selected_improvements = [x[1] for x in selected_layouts]
        min_improvement = min(selected_improvements)
        max_improvement = max(selected_improvements)
        avg_improvement = statistics.mean(selected_improvements)
        
        print(f"   📊 Range des améliorations sélectionnées: {min_improvement:.1f} - {max_improvement:.1f} steps")
        print(f"   📊 Amélioration moyenne sélectionnée: {avg_improvement:.1f} steps")
        
        # Compter les types d'améliorations
        significant_improvement = sum(1 for _, improvement, _ in selected_layouts if improvement > 50)
        moderate_improvement = sum(1 for _, improvement, _ in selected_layouts if 20 <= improvement <= 50)
        
        print(f"   📊 Layouts avec amélioration > 50 steps: {significant_improvement}")
        print(f"   📊 Layouts avec amélioration 20-50 steps: {moderate_improvement}")
        
        return selected_layouts
    
    def create_selected_layouts_visualization(self, selected_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Crée une visualisation des layouts sélectionnés"""
        
        layout_names = []
        solo_distances = []
        duo_distances = []
        improvements = []
        
        # Garder l'ordre de sélection (meilleure amélioration en premier)
        for layout_name, improvement, data in selected_layouts:
            layout_names.append(layout_name[:20] + "..." if len(layout_name) > 20 else layout_name)
            solo_distances.append(data['solo_distance'])
            duo_distances.append(data['coop_distance'])
            improvements.append(improvement)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 16))
        
        # Graphique 1: Comparaison Solo vs Duo pour les layouts sélectionnés
        x = np.arange(len(layout_names))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, solo_distances, width, label='Solo', 
                       alpha=0.8, color='blue', edgecolor='navy')
        bars2 = ax1.bar(x + width/2, duo_distances, width, label='Duo', 
                       alpha=0.8, color='red', edgecolor='darkred')
        
        ax1.set_title(f'Layouts Sélectionnés: Plus Grandes Améliorations Solo→Duo\n'
                     f'Top {len(layout_names)} layouts avec les meilleures améliorations', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Layout (trié par amélioration décroissante)', fontsize=12)
        ax1.set_ylabel('Distance Totale', fontsize=12)
        ax1.legend(fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels(layout_names, rotation=45, ha='right')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les valeurs d'amélioration sur le graphique
        for i, improvement in enumerate(improvements):
            ax1.text(i, max(solo_distances[i], duo_distances[i]) + 5, f'+{improvement:.0f}', 
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='green')
        
        # Graphique 2: Distribution des distances duo pour les layouts sélectionnés
        ax2.hist(duo_distances, bins=min(20, len(duo_distances)), alpha=0.7, color='red', 
                edgecolor='darkred', label=f'Distribution Distances Duo')
        
        # Ajouter des statistiques
        mean_duo = np.mean(duo_distances)
        median_duo = np.median(duo_distances)
        std_duo = np.std(duo_distances)
        mean_improvement = np.mean(improvements)
        
        ax2.axvline(mean_duo, color='blue', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {mean_duo:.1f}')
        ax2.axvline(median_duo, color='green', linestyle='--', linewidth=2, 
                   label=f'Médiane: {median_duo:.1f}')
        
        ax2.set_title(f'Distribution des Distances en Mode Duo - Layouts Sélectionnés\n'
                     f'Amélioration moyenne: {mean_improvement:.1f} steps', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Distance en Mode Duo', fontsize=12)
        ax2.set_ylabel('Nombre de Layouts', fontsize=12)
        ax2.legend(fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        # Ajouter des statistiques textuelles
        stats_text = (f'Statistiques Layouts Sélectionnés:\n'
                     f'Distances Duo - Min: {min(duo_distances):.0f}\n'
                     f'Distances Duo - Max: {max(duo_distances):.0f}\n'
                     f'Écart-type: {std_duo:.1f}\n'
                     f'Amélioration min: {min(improvements):.0f}\n'
                     f'Amélioration max: {max(improvements):.0f}')
        
        ax2.text(0.98, 0.98, stats_text, transform=ax2.transAxes, 
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.8))
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/selected_high_improvement_layouts.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ Visualisation des layouts sélectionnés sauvegardée: {output_path}")
        return output_path
    
    def create_duo_steps_distribution(self, selected_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Crée une analyse détaillée de la distribution des distances en duo"""
        
        # Extraire les données des layouts sélectionnés
        layout_names = []
        duo_distances = []
        solo_distances = []
        improvements = []
        
        for layout_name, improvement, data in selected_layouts:
            layout_names.append(layout_name)
            duo_distances.append(data['coop_distance'])
            solo_distances.append(data['solo_distance'])
            improvements.append(improvement)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Graphique 1: Histogramme des distances duo
        ax1.hist(duo_distances, bins=20, alpha=0.7, color='red', edgecolor='darkred')
        
        mean_duo = np.mean(duo_distances)
        median_duo = np.median(duo_distances)
        
        ax1.axvline(mean_duo, color='blue', linestyle='--', linewidth=2, 
                   label=f'Moyenne: {mean_duo:.1f}')
        ax1.axvline(median_duo, color='green', linestyle='--', linewidth=2, 
                   label=f'Médiane: {median_duo:.1f}')
        
        ax1.set_title(f'Distribution des Distances en Mode Duo\n'
                     f'Layouts avec les meilleures améliorations ({len(selected_layouts)} layouts)', 
                     fontsize=12, fontweight='bold')
        ax1.set_xlabel('Distance Totale en Duo', fontsize=10)
        ax1.set_ylabel('Nombre de Layouts', fontsize=10)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Graphique 2: Scatter plot Amélioration vs Distance Duo
        colors = plt.cm.viridis([i/len(improvements) for i in range(len(improvements))])
        scatter = ax2.scatter(duo_distances, improvements, c=colors, alpha=0.7, s=50)
        
        ax2.set_title('Relation: Distance Duo vs Amélioration', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Distance en Mode Duo', fontsize=10)
        ax2.set_ylabel('Amélioration (Solo - Duo)', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        # Ajouter une ligne de tendance
        z = np.polyfit(duo_distances, improvements, 1)
        p = np.poly1d(z)
        ax2.plot(duo_distances, p(duo_distances), "r--", alpha=0.8, 
                label=f'Tendance: y={z[0]:.2f}x+{z[1]:.1f}')
        ax2.legend()
        
        # Graphique 3: Box plot des distances par quartile d'amélioration
        # Diviser en quartiles selon l'amélioration
        sorted_by_improvement = sorted(zip(improvements, duo_distances), reverse=True)
        quartile_size = len(sorted_by_improvement) // 4
        
        quartiles_data = []
        quartile_labels = []
        
        for i in range(4):
            start = i * quartile_size
            end = start + quartile_size if i < 3 else len(sorted_by_improvement)
            quartile_distances = [item[1] for item in sorted_by_improvement[start:end]]
            quartiles_data.append(quartile_distances)
            quartile_labels.append(f'Q{i+1}\n(Top {start+1}-{end})')
        
        bp = ax3.boxplot(quartiles_data, labels=quartile_labels, patch_artist=True)
        
        # Colorer les box plots
        colors_box = ['gold', 'lightgreen', 'lightblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors_box):
            patch.set_facecolor(color)
        
        ax3.set_title('Distribution des Distances Duo par Quartile d\'Amélioration', 
                     fontsize=12, fontweight='bold')
        ax3.set_ylabel('Distance en Mode Duo', fontsize=10)
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Graphique 4: Top 10 des layouts avec annotation
        top_10 = selected_layouts[:10]
        top_names = [name[:15] + "..." if len(name) > 15 else name for name, _, _ in top_10]
        top_duo = [data['coop_distance'] for _, _, data in top_10]
        top_improvements = [improvement for _, improvement, _ in top_10]
        
        bars = ax4.bar(range(len(top_10)), top_duo, 
                      color=plt.cm.RdYlBu_r([imp/max(top_improvements) for imp in top_improvements]),
                      alpha=0.8, edgecolor='black')
        
        ax4.set_title('Top 10 des Layouts: Distances Duo avec Améliorations', 
                     fontsize=12, fontweight='bold')
        ax4.set_xlabel('Layouts (classés par amélioration)', fontsize=10)
        ax4.set_ylabel('Distance en Mode Duo', fontsize=10)
        ax4.set_xticks(range(len(top_10)))
        ax4.set_xticklabels(top_names, rotation=45, ha='right')
        ax4.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les valeurs d'amélioration sur les barres
        for i, (bar, improvement) in enumerate(zip(bars, top_improvements)):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'+{improvement:.0f}', ha='center', va='bottom', 
                    fontsize=9, fontweight='bold', color='darkgreen')
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/duo_distances_detailed_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ Analyse détaillée des distances duo sauvegardée: {output_path}")
        return output_path
    
    def generate_comprehensive_report(self, comparison_data: Dict[str, Dict], 
                                    selected_layouts: List[Tuple[str, float, Dict]]) -> str:
        """Génère un rapport complet de l'analyse"""
        
        report_path = f"{self.output_dir}/shortest_path_analysis_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"RAPPORT D'ANALYSE DES DIFFÉRENCES DE DISTANCES SOLO VS DUO\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"📅 Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"� Source des données: path_evaluation_results\n")
            f.write(f"� Modes comparés: Solo vs Duo\n\n")
            
            # 1. Statistiques globales de comparaison
            f.write("📊 STATISTIQUES GLOBALES DE COMPARAISON\n")
            f.write("-" * 45 + "\n")
            f.write(f"Nombre total de layouts comparés: {len(comparison_data)}\n")
            
            # Calculer les statistiques globales
            all_solo = [data['solo_distance'] for data in comparison_data.values()]
            all_duo = [data['coop_distance'] for data in comparison_data.values()]
            all_improvements = [data['efficiency_gain'] for data in comparison_data.values()]
            
            duo_better_count = sum(1 for improvement in all_improvements if improvement > 0)
            solo_better_count = sum(1 for improvement in all_improvements if improvement < 0)
            equal_count = sum(1 for improvement in all_improvements if abs(improvement) < 1)
            
            f.write(f"Layouts où le duo est plus efficace: {duo_better_count} ({duo_better_count/len(comparison_data)*100:.1f}%)\n")
            f.write(f"Layouts où le solo est plus efficace: {solo_better_count} ({solo_better_count/len(comparison_data)*100:.1f}%)\n")
            f.write(f"Layouts avec performance équivalente: {equal_count} ({equal_count/len(comparison_data)*100:.1f}%)\n\n")
            
            f.write(f"Distance moyenne Solo: {np.mean(all_solo):.1f} steps\n")
            f.write(f"Distance moyenne Duo: {np.mean(all_duo):.1f} steps\n")
            f.write(f"Amélioration moyenne (Solo - Duo): {np.mean(all_improvements):.1f} steps\n")
            f.write(f"Pourcentage d'amélioration moyen: {(np.mean(all_improvements)/np.mean(all_solo))*100:.1f}%\n\n")
            
            # 2. Analyse des layouts sélectionnés
            f.write("🎯 ANALYSE DES LAYOUTS AVEC LES MEILLEURES AMÉLIORATIONS\n")
            f.write("-" * 55 + "\n")
            f.write(f"Nombre de layouts sélectionnés: {len(selected_layouts)}\n")
            f.write(f"Critère de sélection: Meilleures améliorations Solo→Duo\n\n")
            
            if selected_layouts:
                selected_improvements = [improvement for _, improvement, _ in selected_layouts]
                selected_duo = [data['coop_distance'] for _, _, data in selected_layouts]
                selected_solo = [data['solo_distance'] for _, _, data in selected_layouts]
                
                f.write(f"Range des améliorations sélectionnées: {min(selected_improvements):.1f} - {max(selected_improvements):.1f} steps\n")
                f.write(f"Amélioration moyenne sélectionnée: {np.mean(selected_improvements):.1f} steps\n")
                f.write(f"Distance solo moyenne sélectionnée: {np.mean(selected_solo):.1f} steps\n")
                f.write(f"Distance duo moyenne sélectionnée: {np.mean(selected_duo):.1f} steps\n")
                f.write(f"Pourcentage d'amélioration moyen: {(np.mean(selected_improvements)/np.mean(selected_solo))*100:.1f}%\n\n")
            
            # 3. Top 15 des layouts avec les meilleures améliorations
            f.write("🥇 TOP 15 DES LAYOUTS AVEC LES MEILLEURES AMÉLIORATIONS\n")
            f.write("-" * 55 + "\n")
            
            for i, (layout_name, improvement, data) in enumerate(selected_layouts[:15], 1):
                solo_dist = data['solo_distance']
                duo_dist = data['coop_distance']
                percentage = (improvement / solo_dist) * 100 if solo_dist > 0 else 0
                
                f.write(f"{i:2d}. {layout_name[:40]:<40}: "
                       f"Solo={solo_dist:4.0f}, Duo={duo_dist:4.0f}, "
                       f"Amélioration={improvement:4.0f} ({percentage:5.1f}%)\n")
            
            if len(selected_layouts) > 15:
                f.write(f"... et {len(selected_layouts) - 15} autres layouts\n")
            
            # 4. Catégories d'amélioration
            f.write(f"\n📈 CATÉGORIES D'AMÉLIORATION\n")
            f.write("-" * 30 + "\n")
            
            if selected_layouts:
                excellent = sum(1 for _, improvement, _ in selected_layouts if improvement > 100)
                very_good = sum(1 for _, improvement, _ in selected_layouts if 50 <= improvement <= 100)
                good = sum(1 for _, improvement, _ in selected_layouts if 20 <= improvement < 50)
                moderate = sum(1 for _, improvement, _ in selected_layouts if improvement < 20)
                
                f.write(f"Excellente amélioration (>100 steps): {excellent}\n")
                f.write(f"Très bonne amélioration (50-100 steps): {very_good}\n")
                f.write(f"Bonne amélioration (20-50 steps): {good}\n")
                f.write(f"Amélioration modérée (<20 steps): {moderate}\n")
            
            f.write(f"\n📊 Fichiers de visualisation générés dans: {self.output_dir}\n")
        
        return report_path

class ShortestPathEvaluator:
    """Évaluateur principal pour l'analyse des différences de paths"""
    
    def __init__(self, base_category: str = "symmetric"):
        """
        Initialise l'évaluateur pour une catégorie de base.
        
        Args:
            base_category: Catégorie de base à analyser
        """
        self.base_category = base_category
        self.analyzer = ShortestPathAnalyzer(base_category)
    
    def run_complete_analysis(self, selection_count: int = 50):
        """Lance l'analyse complète des différences de distances"""
        
        print(f"🚀 SHORTEST PATH ANALYSIS - ANALYSE COMPLÈTE DES DISTANCES SOLO VS DUO")
        print("=" * 70)
        
        # 1. Découvrir et charger les données
        print(f"\n📂 ÉTAPE 1: Chargement des données depuis path_evaluation_results...")
        layout_data = self.analyzer.discover_layout_data()
        
        if not layout_data:
            print(f"❌ Aucune donnée trouvée dans {self.analyzer.data_dir}!")
            return
        
        # 2. Analyser les comparaisons
        print(f"\n📊 ÉTAPE 2: Analyse comparative solo vs duo...")
        comparison_data = self.analyzer.analyze_layouts_comparison(layout_data)
        
        if not comparison_data:
            print(f"❌ Aucune donnée de comparaison disponible!")
            return
        
        # 3. Créer le graphique de comparaison des distances
        print(f"\n📈 ÉTAPE 3: Création du graphique de comparaison des distances...")
        comparison_chart = self.analyzer.create_steps_comparison_chart(comparison_data)
        
        # 4. Créer le graphique d'analyse des différences
        print(f"\n📊 ÉTAPE 4: Création de l'analyse complète des différences...")
        difference_chart = self.analyzer.create_difference_analysis_chart(comparison_data)
        
        # 5. Sélectionner les layouts avec les plus grandes améliorations
        print(f"\n🎯 ÉTAPE 5: Sélection des {selection_count} layouts avec les meilleures améliorations...")
        selected_layouts = self.analyzer.select_high_difference_layouts(comparison_data, selection_count)
        
        # 6. Créer la visualisation des layouts sélectionnés
        print(f"\n🎨 ÉTAPE 6: Création de la visualisation des layouts sélectionnés...")
        selection_viz = self.analyzer.create_selected_layouts_visualization(selected_layouts)
        
        # 7. Créer l'analyse détaillée des distances duo
        print(f"\n📊 ÉTAPE 7: Création de l'analyse détaillée des distances duo...")
        duo_analysis = self.analyzer.create_duo_steps_distribution(selected_layouts)
        
        # 8. Générer le rapport complet
        print(f"\n📋 ÉTAPE 8: Génération du rapport complet...")
        report_path = self.analyzer.generate_comprehensive_report(comparison_data, selected_layouts)
        print(f"   ✅ Rapport sauvegardé: {report_path}")
        
        # Résumé final
        print(f"\n🎉 ANALYSE TERMINÉE!")
        print("=" * 50)
        print(f"📊 {len(comparison_data)} layouts analysés")
        print(f"🎯 {len(selected_layouts)} layouts sélectionnés avec les meilleures améliorations")
        print(f"📈 Graphiques générés dans: {self.analyzer.output_dir}")
        
        # Statistiques finales
        all_improvements = [data['efficiency_gain'] for data in comparison_data.values()]
        duo_better = sum(1 for improvement in all_improvements if improvement > 0)
        solo_better = sum(1 for improvement in all_improvements if improvement < 0)
        avg_improvement = np.mean(all_improvements)
        
        print(f"📊 Résumé global:")
        print(f"   - Layouts où duo est meilleur: {duo_better} ({duo_better/len(comparison_data)*100:.1f}%)")
        print(f"   - Layouts où solo est meilleur: {solo_better} ({solo_better/len(comparison_data)*100:.1f}%)")
        print(f"   - Amélioration moyenne: {avg_improvement:.1f} steps")
        print(f"   - Top amélioration: {max(all_improvements):.1f} steps")
    
    @staticmethod
    def analyze_all_data(selection_count: int = 50):
        """Analyse toutes les données disponibles"""
        
        print(f"🚀 SHORTEST PATH ANALYSIS - ANALYSE GLOBALE")
        print("=" * 50)
        
        try:
            evaluator = ShortestPathEvaluator("all")
            evaluator.run_complete_analysis(selection_count)
            
            print(f"✅ ANALYSE GLOBALE TERMINÉE")
            
        except Exception as e:
            print(f"❌ ERREUR lors de l'analyse: {e}")
            return

def main():
    """Fonction principale"""
    import sys
    
    if len(sys.argv) > 1:
        selection_count = int(sys.argv[1]) if sys.argv[1].isdigit() else 50
        print(f"💡 Sélection de {selection_count} layouts avec les meilleures améliorations")
    else:
        selection_count = 50
        print("💡 Usage: python shortest_path_evaluator.py [nombre_layouts_à_sélectionner]")
        print(f"   Par défaut: sélection des {selection_count} meilleurs layouts")
    
    print("\n🎯 Analyse globale des données path_evaluation_results")
    ShortestPathEvaluator.analyze_all_data(selection_count)

if __name__ == "__main__":
    main()
