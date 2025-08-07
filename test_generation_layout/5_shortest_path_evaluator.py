#!/usr/bin/env python3
"""
Sélecteur Automatique des Meilleurs Layouts Overcooked pour Expériences en Sciences Cognitives

Ce module implémente une méthodologie structurée pour:
1. Analyser systématiquement les lots de recettes
2. Comparer les versions de layouts (solo vs duo)
3. Sélectionner automatiquement les meilleurs layouts
4. Visualiser toutes les étapes de sélection

Auteur: Assistant IA
Date: Août 2025
Objectif: Sélection optimale pour protocole expérimental en sciences cognitives
"""

import os
import json
import glob
import shutil
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
import statistics

# Configuration matplotlib pour de beaux graphiques
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

class CognitiveLayoutSelector:
    """Sélecteur automatique de layouts pour expériences en sciences cognitives"""
    
    def __init__(self):
        """Initialise le sélecteur de layouts"""
        # Configuration des dossiers
        self.data_dir = "path_evaluation_results"
        self.layouts_source_dir = "layouts_with_objects"
        self.selected_layouts_dir = "layouts_selectionnés"
        self.output_dir = "analysis_plots/cognitive_layout_selection"
        
        # Créer les dossiers de sortie
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.selected_layouts_dir, exist_ok=True)
        
        # Structure pour stocker les données analysées
        self.recipe_lots_data = {}
        self.layout_combinations_data = {}
        self.best_versions_per_combination = {}
        self.final_rankings = []
    
    def load_recipe_lot_data(self, lot_number: int) -> Dict:
        """Charge les données d'un lot de recettes spécifique"""
        
        lot_file = f"{self.data_dir}/recette_lot_{lot_number}_results.json"
        
        if not os.path.exists(lot_file):
            print(f"❌ Fichier {lot_file} non trouvé!")
            return {}
        
        try:
            with open(lot_file, 'r') as f:
                data = json.load(f)
            
            print(f"✅ Lot {lot_number}: {len(data)} layouts chargés")
            return data
            
        except Exception as e:
            print(f"❌ Erreur lors du chargement du lot {lot_number}: {e}")
            return {}
    
    def extract_layout_combination_info(self, layout_path: str) -> Tuple[str, str, str]:
        """Extrait les informations de combination, version depuis le path du layout"""
        
        # Ex: layouts_with_objects/layout_combination_01/V1_layout_combination_01.layout
        # -> combination: "01", version: "V1", combination_id: "combination_01"
        
        if 'layout_combination_' in layout_path:
            # Extraire le numéro de combination
            parts = layout_path.split('layout_combination_')
            if len(parts) > 1:
                combination_num = parts[1].split('/')[0]  # Ex: "01"
                
                # Extraire la version depuis le nom du fichier
                filename = os.path.basename(layout_path)
                if filename.startswith('V') and '_' in filename:
                    version = filename.split('_')[0]  # Ex: "V1"
                else:
                    version = "V1"  # Version par défaut
                
                combination_id = f"combination_{combination_num}"
                
                return combination_id, version, combination_num
        
        return "unknown", "V1", "00"
    
    def organize_data_by_combinations_and_versions(self, lot_data: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
        """Organise les données par combination puis par version"""
        
        combinations = defaultdict(lambda: defaultdict(list))
        
        for layout_info in lot_data:
            layout_path = layout_info.get('layout_path', '')
            combination_id, version, combination_num = self.extract_layout_combination_info(layout_path)
            
            # Ajouter les infos extraites
            layout_info['combination_id'] = combination_id
            layout_info['version'] = version
            layout_info['combination_num'] = combination_num
            layout_info['difference_solo_duo'] = layout_info['solo_distance'] - layout_info['coop_distance']
            
            combinations[combination_id][version].append(layout_info)
        
        return dict(combinations)
    
    def find_best_version_for_combination(self, combination_data: Dict[str, List[Dict]]) -> Dict:
        """Trouve la version avec la plus grande différence solo-duo pour une combination"""
        
        best_version_info = None
        best_difference = -float('inf')
        
        print(f"      Analyse des versions:")
        
        for version, layouts_list in combination_data.items():
            if not layouts_list:
                continue
            
            # Calculer la différence moyenne pour cette version
            version_differences = [layout['difference_solo_duo'] for layout in layouts_list]
            avg_difference = np.mean(version_differences)
            
            print(f"        {version}: {len(layouts_list)} layouts, différence moyenne: {avg_difference:.1f}")
            
            if avg_difference > best_difference:
                best_difference = avg_difference
                # Prendre le layout avec la meilleure différence de cette version
                best_layout = max(layouts_list, key=lambda x: x['difference_solo_duo'])
                best_version_info = {
                    'best_layout': best_layout,
                    'version': version,
                    'avg_difference': avg_difference,
                    'layouts_count': len(layouts_list),
                    'all_layouts': layouts_list
                }
        
        if best_version_info:
            print(f"      🏆 Meilleure version: {best_version_info['version']} "
                  f"(différence: {best_version_info['avg_difference']:.1f})")
        
        return best_version_info
    
    def analyze_recipe_lot_step_by_step(self, lot_number: int) -> Dict:
        """Analyse complète d'un lot avec sélection par étapes"""
        
        print(f"\n📊 ANALYSE DU LOT DE RECETTES {lot_number}")
        print("="*50)
        
        # 1.1 Charger les données du lot
        lot_data = self.load_recipe_lot_data(lot_number)
        if not lot_data:
            return {}
        
        # 1.2 Organiser par combinations et versions
        combinations_data = self.organize_data_by_combinations_and_versions(lot_data)
        print(f"📋 {len(combinations_data)} combinations trouvées")
        
        # 1.3 Pour chaque combination, sélectionner la meilleure version
        selected_layouts = {}
        all_differences = []
        
        for combination_id, versions_data in combinations_data.items():
            print(f"   🔍 Analyse de {combination_id}:")
            
            best_version_info = self.find_best_version_for_combination(versions_data)
            
            if best_version_info:
                selected_layouts[combination_id] = best_version_info
                all_differences.append(best_version_info['avg_difference'])
        
        # 1.4 Calculer les statistiques du lot
        lot_stats = {
            'lot_number': lot_number,
            'total_combinations': len(combinations_data),
            'selected_layouts': selected_layouts,
            'avg_difference': np.mean(all_differences) if all_differences else 0,
            'total_layouts_analyzed': len(lot_data),
            'layouts_selected': len(selected_layouts),
            'max_difference': max(all_differences) if all_differences else 0,
            'min_difference': min(all_differences) if all_differences else 0
        }
        
        print(f"📈 Différence moyenne du lot: {lot_stats['avg_difference']:.1f} steps")
        print(f"📈 {lot_stats['layouts_selected']} layouts sélectionnés sur {lot_stats['total_combinations']} combinations")
        
        return lot_stats
    
    def create_lot_analysis_visualization(self, lot_stats: Dict) -> str:
        """Crée une visualisation détaillée pour un lot"""
        
        lot_number = lot_stats['lot_number']
        selected_layouts = lot_stats['selected_layouts']
        
        if not selected_layouts:
            return ""
        
        # Préparer les données pour la visualisation
        combination_names = []
        solo_distances = []
        duo_distances = []
        differences = []
        versions = []
        
        for combination_id, layout_info in selected_layouts.items():
            best_layout = layout_info['best_layout']
            combination_names.append(combination_id.replace('combination_', 'C'))
            solo_distances.append(best_layout['solo_distance'])
            duo_distances.append(best_layout['coop_distance'])
            differences.append(best_layout['difference_solo_duo'])
            versions.append(layout_info['version'])
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Graphique 1: Comparaison Solo vs Duo par combination
        x = np.arange(len(combination_names))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, solo_distances, width, label='Solo', 
                       alpha=0.8, color='skyblue', edgecolor='navy')
        bars2 = ax1.bar(x + width/2, duo_distances, width, label='Duo', 
                       alpha=0.8, color='lightcoral', edgecolor='darkred')
        
        ax1.set_title(f'Lot {lot_number}: Distances Solo vs Duo par Combination\n'
                     f'Meilleures versions sélectionnées', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Combinations', fontsize=12)
        ax1.set_ylabel('Distance Totale', fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels(combination_names, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les différences au-dessus des barres
        for i, diff in enumerate(differences):
            ax1.text(i, max(solo_distances[i], duo_distances[i]) + 5, 
                    f'+{diff:.0f}', ha='center', va='bottom', 
                    fontsize=10, fontweight='bold', color='green')
        
        # Graphique 2: Différences par combination avec versions
        colors = plt.cm.Set3(np.linspace(0, 1, len(differences)))
        bars = ax2.bar(x, differences, color=colors, alpha=0.8, edgecolor='black')
        
        ax2.set_title(f'Lot {lot_number}: Différences Solo-Duo par Combination', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Combinations', fontsize=12)
        ax2.set_ylabel('Différence (Solo - Duo)', fontsize=12)
        ax2.set_xticks(x)
        ax2.set_xticklabels(combination_names, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les versions sur les barres
        for i, (bar, version) in enumerate(zip(bars, versions)):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                    version, ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # Graphique 3: Distribution des différences
        ax3.hist(differences, bins=min(10, len(differences)), alpha=0.7, 
                color='lightgreen', edgecolor='darkgreen')
        ax3.axvline(np.mean(differences), color='red', linestyle='--', linewidth=2,
                   label=f'Moyenne: {np.mean(differences):.1f}')
        ax3.set_title(f'Lot {lot_number}: Distribution des Différences', 
                     fontsize=14, fontweight='bold')
        ax3.set_xlabel('Différence (Solo - Duo)', fontsize=12)
        ax3.set_ylabel('Nombre de Combinations', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Graphique 4: Heatmap des performances
        # Créer une matrice version vs combination
        version_set = sorted(set(versions))
        perf_matrix = np.zeros((len(version_set), len(combination_names)))
        
        for i, combination_id in enumerate(selected_layouts.keys()):
            layout_info = selected_layouts[combination_id]
            version = layout_info['version']
            version_idx = version_set.index(version)
            perf_matrix[version_idx, i] = layout_info['avg_difference']
        
        im = ax4.imshow(perf_matrix, cmap='RdYlGn', aspect='auto')
        ax4.set_title(f'Lot {lot_number}: Heatmap Performances par Version', 
                     fontsize=14, fontweight='bold')
        ax4.set_xlabel('Combinations', fontsize=12)
        ax4.set_ylabel('Versions', fontsize=12)
        ax4.set_xticks(range(len(combination_names)))
        ax4.set_xticklabels(combination_names, rotation=45, ha='right')
        ax4.set_yticks(range(len(version_set)))
        ax4.set_yticklabels(version_set)
        
        # Ajouter les valeurs dans la heatmap
        for i in range(len(version_set)):
            for j in range(len(combination_names)):
                value = perf_matrix[i, j]
                if value > 0:
                    ax4.text(j, i, f'{value:.0f}', ha='center', va='center',
                            color='white' if value > np.max(perf_matrix)/2 else 'black',
                            fontweight='bold')
        
        plt.colorbar(im, ax=ax4, label='Différence Solo-Duo')
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/lot_{lot_number}_analysis_detail.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   📊 Visualisation détaillée sauvegardée: {output_path}")
        return output_path
    
    def analyze_all_recipe_lots(self) -> Dict[int, Dict]:
        """Analyse tous les lots de recettes disponibles"""
        
        print(f"\n🚀 ANALYSE DE TOUS LES LOTS DE RECETTES")
        print("="*60)
        
        # Détecter les lots disponibles
        lot_files = glob.glob(f"{self.data_dir}/recette_lot_*_results.json")
        lot_numbers = []
        
        for file_path in lot_files:
            filename = os.path.basename(file_path)
            if 'recette_lot_' in filename:
                try:
                    lot_num = int(filename.split('recette_lot_')[1].split('_results')[0])
                    lot_numbers.append(lot_num)
                except ValueError:
                    continue
        
        lot_numbers.sort()
        print(f"📋 Lots détectés: {lot_numbers}")
        
        # Analyser chaque lot
        all_lots_stats = {}
        
        for lot_number in lot_numbers:
            lot_stats = self.analyze_recipe_lot_step_by_step(lot_number)
            if lot_stats:
                all_lots_stats[lot_number] = lot_stats
                
                # Créer la visualisation pour ce lot
                self.create_lot_analysis_visualization(lot_stats)
                
                # Stocker pour la suite
                self.recipe_lots_data[lot_number] = lot_stats
        
        return all_lots_stats
    
    def rank_lots_by_performance(self, all_lots_stats: Dict[int, Dict]) -> List[Tuple[int, float]]:
        """Classe les lots par différence moyenne décroissante"""
        
        print(f"\n📈 CLASSEMENT DES LOTS PAR PERFORMANCE")
        print("="*45)
        
        lot_rankings = []
        
        for lot_number, lot_stats in all_lots_stats.items():
            avg_difference = lot_stats['avg_difference']
            lot_rankings.append((lot_number, avg_difference))
        
        # Trier par différence décroissante
        lot_rankings.sort(key=lambda x: x[1], reverse=True)
        
        print("🏆 CLASSEMENT FINAL:")
        for rank, (lot_number, avg_difference) in enumerate(lot_rankings, 1):
            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"   {emoji} {rank:2d}. Lot {lot_number:2d}: {avg_difference:6.1f} steps de différence moyenne")
        
        return lot_rankings
    
    def create_global_comparison_visualization(self, lot_rankings: List[Tuple[int, float]]) -> str:
        """Crée une visualisation de comparaison globale entre tous les lots"""
        
        lots = [lot_num for lot_num, _ in lot_rankings]
        avg_differences = [avg_diff for _, avg_diff in lot_rankings]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # Graphique 1: Classement des lots
        colors = plt.cm.RdYlGn(np.linspace(0.3, 1, len(lots)))
        bars1 = ax1.bar(range(len(lots)), avg_differences, color=colors, 
                       alpha=0.8, edgecolor='black')
        ax1.set_title('Classement des Lots par Différence Moyenne Solo-Duo', 
                     fontsize=16, fontweight='bold')
        ax1.set_xlabel('Lots (classés par performance)', fontsize=12)
        ax1.set_ylabel('Différence Moyenne (Solo - Duo)', fontsize=12)
        ax1.set_xticks(range(len(lots)))
        ax1.set_xticklabels([f'Lot {lot}' for lot in lots])
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les valeurs sur les barres
        for bar, avg_diff in zip(bars1, avg_differences):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{avg_diff:.1f}', ha='center', va='bottom', 
                    fontsize=10, fontweight='bold')
        
        # Graphique 2: Nombre de layouts sélectionnés par lot
        layouts_selected = []
        for lot_num in lots:
            if lot_num in self.recipe_lots_data:
                layouts_selected.append(self.recipe_lots_data[lot_num]['layouts_selected'])
            else:
                layouts_selected.append(0)
        
        ax2.bar(range(len(lots)), layouts_selected, alpha=0.8, 
               color='lightblue', edgecolor='navy')
        ax2.set_title('Nombre de Layouts Sélectionnés par Lot', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Lots', fontsize=12)
        ax2.set_ylabel('Nombre de Layouts Sélectionnés', fontsize=12)
        ax2.set_xticks(range(len(lots)))
        ax2.set_xticklabels([f'Lot {lot}' for lot in lots])
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Graphique 3: Évolution des performances
        ax3.plot(range(len(lots)), avg_differences, marker='o', linewidth=3, 
                markersize=8, color='purple', alpha=0.8)
        ax3.fill_between(range(len(lots)), avg_differences, alpha=0.3, color='purple')
        ax3.set_title('Évolution des Performances par Lot', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Position dans le classement', fontsize=12)
        ax3.set_ylabel('Différence Moyenne (Solo - Duo)', fontsize=12)
        ax3.set_xticks(range(len(lots)))
        ax3.set_xticklabels([f'Lot {lot}' for lot in lots])
        ax3.grid(True, alpha=0.3)
        
        # Graphique 4: Distribution des différences moyennes
        ax4.hist(avg_differences, bins=min(10, len(avg_differences)), alpha=0.7, 
                color='orange', edgecolor='darkorange')
        ax4.axvline(np.mean(avg_differences), color='red', linestyle='--', linewidth=2,
                   label=f'Moyenne globale: {np.mean(avg_differences):.1f}')
        ax4.set_title('Distribution des Performances des Lots', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Différence Moyenne (Solo - Duo)', fontsize=12)
        ax4.set_ylabel('Nombre de Lots', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Sauvegarder
        output_path = f"{self.output_dir}/global_lots_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"📊 Comparaison globale sauvegardée: {output_path}")
        return output_path
    
    def copy_winner_lot_layouts(self, winner_lot_number: int) -> int:
        """Copie les layouts du lot gagnant vers le dossier de sélection"""
        
        print(f"\n📁 COPIE DES LAYOUTS DU LOT GAGNANT {winner_lot_number}")
        print("="*50)
        
        if winner_lot_number not in self.recipe_lots_data:
            print(f"❌ Données du lot {winner_lot_number} non trouvées!")
            return 0
        
        selected_layouts = self.recipe_lots_data[winner_lot_number]['selected_layouts']
        copied_count = 0
        failed_count = 0
        
        # Créer le dossier de destination
        winner_dest_dir = f"{self.selected_layouts_dir}/lot_{winner_lot_number}_winner"
        os.makedirs(winner_dest_dir, exist_ok=True)
        
        print(f"📂 Destination: {winner_dest_dir}")
        
        for combination_id, layout_info in selected_layouts.items():
            best_layout = layout_info['best_layout']
            layout_path = best_layout['layout_path']
            layout_filename = os.path.basename(layout_path)
            
            source_path = layout_path
            dest_path = os.path.join(winner_dest_dir, layout_filename)
            
            try:
                if os.path.exists(source_path):
                    shutil.copy2(source_path, dest_path)
                    copied_count += 1
                    print(f"   ✅ {layout_filename} (diff: {best_layout['difference_solo_duo']:.0f}, "
                          f"version: {layout_info['version']})")
                else:
                    failed_count += 1
                    print(f"   ❌ Source non trouvée: {layout_filename}")
                    
            except Exception as e:
                failed_count += 1
                print(f"   ❌ Erreur lors de la copie de {layout_filename}: {e}")
        
        # Créer un fichier de résumé
        summary_file = os.path.join(winner_dest_dir, f"selection_summary_lot_{winner_lot_number}.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(f"LAYOUTS SÉLECTIONNÉS - LOT GAGNANT {winner_lot_number}\n")
            f.write("="*70 + "\n\n")
            f.write(f"Date de sélection: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Critère: Lot avec la plus grande différence moyenne Solo-Duo\n\n")
            
            lot_stats = self.recipe_lots_data[winner_lot_number]
            f.write(f"STATISTIQUES DU LOT GAGNANT:\n")
            f.write(f"Différence moyenne: {lot_stats['avg_difference']:.1f} steps\n")
            f.write(f"Nombre de combinations: {lot_stats['total_combinations']}\n")
            f.write(f"Layouts copiés avec succès: {copied_count}\n")
            f.write(f"Échecs de copie: {failed_count}\n\n")
            
            f.write("LAYOUTS SÉLECTIONNÉS:\n")
            f.write("-" * 50 + "\n")
            for i, (combination_id, layout_info) in enumerate(selected_layouts.items(), 1):
                best_layout = layout_info['best_layout']
                layout_name = os.path.basename(best_layout['layout_path'])
                f.write(f"{i:2d}. {layout_name:<40} - {combination_id:<15} - "
                       f"Version: {layout_info['version']:<3} - "
                       f"Différence: {best_layout['difference_solo_duo']:3.0f} steps\n")
        
        print(f"\n✅ Copie terminée: {copied_count}/{len(selected_layouts)} layouts copiés")
        print(f"📄 Résumé sauvegardé: {summary_file}")
        
        return copied_count
    
    def generate_final_report(self, lot_rankings: List[Tuple[int, float]], 
                            winner_lot: int, copied_count: int) -> str:
        """Génère le rapport final de l'analyse cognitive"""
        
        report_path = f"{self.output_dir}/cognitive_layout_selection_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("RAPPORT FINAL - SÉLECTION DE LAYOUTS POUR SCIENCES COGNITIVES\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"📅 Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"🎯 Objectif: Sélection automatique des meilleurs layouts pour expérience\n")
            f.write(f"📊 Critère: Maximisation de la différence Solo vs Duo\n\n")
            
            # 1. Méthodologie
            f.write("📋 MÉTHODOLOGIE APPLIQUÉE\n")
            f.write("-" * 25 + "\n")
            f.write("1. Pour chaque lot de recettes:\n")
            f.write("   - Comparaison Solo vs Duo pour chaque layout\n")
            f.write("   - Analyse de toutes les versions (V1, V2, etc.)\n")
            f.write("   - Sélection de la version avec la plus grande différence\n")
            f.write("2. Classement des lots par différence moyenne\n")
            f.write("3. Sélection du lot gagnant pour l'expérience\n\n")
            
            # 2. Résumé de l'analyse
            f.write("📊 RÉSUMÉ DE L'ANALYSE\n")
            f.write("-" * 25 + "\n")
            f.write(f"Nombre de lots analysés: {len(lot_rankings)}\n")
            
            total_combinations = sum(self.recipe_lots_data[lot]['total_combinations'] 
                                   for lot in self.recipe_lots_data)
            total_selected = sum(self.recipe_lots_data[lot]['layouts_selected'] 
                               for lot in self.recipe_lots_data)
            f.write(f"Total de combinations évaluées: {total_combinations}\n")
            f.write(f"Total de layouts sélectionnés: {total_selected}\n")
            f.write(f"Layouts finalement retenus: {copied_count}\n\n")
            
            # 3. Classement des lots
            f.write("🏆 CLASSEMENT COMPLET DES LOTS\n")
            f.write("-" * 35 + "\n")
            for rank, (lot_number, avg_difference) in enumerate(lot_rankings, 1):
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
                if lot_number in self.recipe_lots_data:
                    lot_stats = self.recipe_lots_data[lot_number]
                    f.write(f"{medal} {rank:2d}. Lot {lot_number:2d}: "
                           f"{avg_difference:6.1f} steps "
                           f"({lot_stats['layouts_selected']} layouts sélectionnés)\n")
            
            # 4. Détails du lot gagnant
            f.write(f"\n🎊 LOT GAGNANT SÉLECTIONNÉ: LOT {winner_lot}\n")
            f.write("-" * 40 + "\n")
            
            if winner_lot in self.recipe_lots_data:
                winner_stats = self.recipe_lots_data[winner_lot]
                f.write(f"Différence moyenne: {winner_stats['avg_difference']:.1f} steps\n")
                f.write(f"Nombre de combinations: {winner_stats['total_combinations']}\n")
                f.write(f"Layouts sélectionnés: {winner_stats['layouts_selected']}\n")
                f.write(f"Différence maximale: {winner_stats['max_difference']:.1f} steps\n")
                f.write(f"Différence minimale: {winner_stats['min_difference']:.1f} steps\n\n")
                
                # 5. Layouts du lot gagnant
                f.write("🏅 DÉTAIL DES LAYOUTS SÉLECTIONNÉS\n")
                f.write("-" * 35 + "\n")
                selected_layouts = winner_stats['selected_layouts']
                
                # Trier par différence décroissante
                sorted_layouts = sorted(selected_layouts.items(), 
                                      key=lambda x: x[1]['best_layout']['difference_solo_duo'], 
                                      reverse=True)
                
                for i, (combination_id, layout_info) in enumerate(sorted_layouts, 1):
                    best_layout = layout_info['best_layout']
                    layout_name = os.path.basename(best_layout['layout_path'])
                    f.write(f"{i:2d}. {layout_name:<35} - "
                           f"{combination_id:<15} - "
                           f"Version: {layout_info['version']:<3} - "
                           f"Solo: {best_layout['solo_distance']:3.0f} - "
                           f"Duo: {best_layout['coop_distance']:3.0f} - "
                           f"Différence: {best_layout['difference_solo_duo']:3.0f}\n")
            
            f.write(f"\n📁 Layouts copiés dans: {self.selected_layouts_dir}/lot_{winner_lot}_winner/\n")
            f.write(f"📊 Visualisations dans: {self.output_dir}/\n")
        
        return report_path
    
    def run_complete_cognitive_selection(self):
        """Lance le processus complet de sélection cognitive"""
        
        print("🧠 SÉLECTION COGNITIVE DES MEILLEURS LAYOUTS OVERCOOKED")
        print("=" * 65)
        print("🎯 Objectif: Sélectionner automatiquement les layouts optimaux")
        print("📊 Méthode: Analyse structurée avec visualisations à chaque étape")
        
        # PHASE 1: Analyse par lots
        print(f"\n📊 PHASE 1: ANALYSE STRUCTURÉE PAR LOTS DE RECETTES")
        all_lots_stats = self.analyze_all_recipe_lots()
        
        if not all_lots_stats:
            print("❌ Aucune donnée analysée!")
            return
        
        # PHASE 2: Classement des lots
        print(f"\n📈 PHASE 2: CLASSEMENT ET COMPARAISON DES LOTS")
        lot_rankings = self.rank_lots_by_performance(all_lots_stats)
        
        # PHASE 3: Visualisation globale
        print(f"\n📊 PHASE 3: CRÉATION DE LA VISUALISATION GLOBALE")
        self.create_global_comparison_visualization(lot_rankings)
        
        # PHASE 4: Sélection finale
        if lot_rankings:
            winner_lot = lot_rankings[0][0]
            winner_avg_diff = lot_rankings[0][1]
            
            print(f"\n🏆 PHASE 4: SÉLECTION FINALE")
            print(f"🥇 Lot gagnant: {winner_lot} ({winner_avg_diff:.1f} steps de différence moyenne)")
            
            copied_count = self.copy_winner_lot_layouts(winner_lot)
            
            # PHASE 5: Rapport final
            print(f"\n📋 PHASE 5: GÉNÉRATION DU RAPPORT FINAL")
            report_path = self.generate_final_report(lot_rankings, winner_lot, copied_count)
            print(f"📄 Rapport final: {report_path}")
            
            # RÉSUMÉ FINAL
            print(f"\n🎉 SÉLECTION COGNITIVE TERMINÉE!")
            print("=" * 50)
            print(f"🏆 Lot gagnant: {winner_lot}")
            print(f"📊 {len(all_lots_stats)} lots analysés")
            print(f"📁 {copied_count} layouts sélectionnés et copiés")
            print(f"📈 Différence moyenne optimale: {winner_avg_diff:.1f} steps")
            print(f"📂 Layouts dans: {self.selected_layouts_dir}")
            print(f"📊 Visualisations dans: {self.output_dir}")
        
        else:
            print("❌ Aucun lot analysé avec succès!")
        
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

def main():
    """Fonction principale pour la sélection cognitive de layouts"""
    
    print("🧠 COGNITIVE LAYOUT SELECTOR - OVERCOOKED")
    print("Sélection automatique des meilleurs layouts pour expériences en sciences cognitives")
    print()
    
    selector = CognitiveLayoutSelector()
    selector.run_complete_cognitive_selection()

if __name__ == "__main__":
    main()
