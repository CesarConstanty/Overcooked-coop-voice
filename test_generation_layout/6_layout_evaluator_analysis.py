#!/usr/bin/env python3
"""
Layout Evaluator Analysis - Analyseur des résultats d'évaluation des layouts

Ce module analyse les résultats d'évaluation des layouts pour:
1. Charger tous les fichiers JSON de résultats d'évaluation
2. Pour chaque layout, trouver la combinaison recette/version qui maximise (distance_solo - distance_coop)
3. Classer les layouts par cette différence maximale
4. Sélectionner un ensemble diversifié de layouts (pas deux fois la même recette)
5. Générer une visualisation et un fichier CSV des résultats

Author: Assistant
Date: 2025-08-06
"""

import os
import json
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import re

class LayoutEvaluationAnalyzer:
    """Analyseur des résultats d'évaluation des layouts"""
    
    def __init__(self, results_dir: str = "test_generation_layout/path_evaluation_results"):
        """
        Initialise l'analyseur.
        
        Args:
            results_dir: Répertoire contenant les fichiers de résultats JSON
        """
        self.results_dir = results_dir
        self.layout_scores = {}  # {layout_id: {max_diff, best_recipe, best_version, solo_dist, coop_dist}}
        self.recipe_mapping = {}  # Mapping des numéros de recettes vers leurs noms
        
        # Créer le dossier de sortie
        self.output_dir = "layout_analysis_results"
        os.makedirs(self.output_dir, exist_ok=True)
        
  #  def load_recipe_mapping(self, recipe_config_file: str = "recipe_config.json"):
  #      """Charge le mapping des recettes depuis le fichier de configuration"""
  #      with open(recipe_config_file, 'r') as f:
  #          config = json.load(f)
  #          # Essayer différentes structures possibles
  #          if 'recipes' in config:
  #              self.recipe_mapping = {i+1: recipe.get('name', f'Recipe_{i+1:02d}') for i, recipe in enumerate(config['recipes'])}
  #          elif isinstance(config, list):
  #              self.recipe_mapping = {i+1: recipe.get('name', f'Recipe_{i+1:02d}') for i, recipe in enumerate(config)}
  #          else:
  #              # Si la structure est différente, créer des noms par défaut
  #              for i in range(1, 85):
  #                  self.recipe_mapping[i] = f"Recipe_{i:02d}"
  #          print(f"✅ Chargé {len(self.recipe_mapping)} recettes depuis {recipe_config_file}")
    
    def parse_filename(self, filename: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Parse le nom de fichier pour extraire l'ID du layout et le numéro de recette.
        
        Format attendu: layout_X_R_YY_results.json
        
        Args:
            filename: Nom du fichier
            
        Returns:
            Tuple (layout_id, recipe_number) ou (None, None) si parsing échoue
        """
        match = re.match(r'layout_(\d+)_R_(\d+)_results\.json', filename)
        if match:
            layout_id = match.group(1)
            recipe_num = int(match.group(2))
            return layout_id, recipe_num
        return None, None
    
    def calculate_max_difference(self, data: List[Dict]) -> Tuple[float, int, int, int]:
        """
        Calcule la différence maximale en pourcentage ((solo - coop) / solo * 100) pour toutes les versions.
        
        Args:
            data: Liste des versions du layout
            
        Returns:
            Tuple (max_percentage_diff, best_version, solo_distance, coop_distance)
        """
        max_percentage_diff = -float('inf')
        best_version = 1
        best_solo = 0
        best_coop = 0
        
        for version_data in data:
            if 'solo_distance' in version_data and 'coop_distance' in version_data:
                solo_dist = version_data['solo_distance']
                coop_dist = version_data['coop_distance']
                
                # Éviter la division par zéro
                if solo_dist > 0:
                    # Calcul de la différence en pourcentage: (solo - coop) / solo * 100
                    percentage_diff = ((solo_dist - coop_dist) / solo_dist) * 100
                    
                    if percentage_diff > max_percentage_diff:
                        max_percentage_diff = percentage_diff
                        best_version = version_data.get('variation_num', 1)
                        best_solo = solo_dist
                        best_coop = coop_dist
        
        return max_percentage_diff, best_version, best_solo, best_coop
    
    def analyze_all_layouts(self):
        """Analyse tous les layouts et trouve le score maximum pour chacun"""
        
        if not os.path.exists(self.results_dir):
            print(f"❌ Répertoire {self.results_dir} non trouvé!")
            return
        
        # Rechercher tous les fichiers JSON
        json_pattern = os.path.join(self.results_dir, "layout_*_R_*_results.json")
        json_files = glob.glob(json_pattern)
        
        if not json_files:
            print(f"❌ Aucun fichier JSON trouvé dans {self.results_dir}")
            return
        
        print(f"📁 Trouvé {len(json_files)} fichiers JSON à analyser")
        
        layout_data = defaultdict(dict)  # {layout_id: {recipe_num: (data, filename)}}
        file_recipe_map = {}  # (layout_id, recipe_num) -> filename
        # Charger tous les fichiers
        for json_file in json_files:
            filename = os.path.basename(json_file)
            layout_id, recipe_num = self.parse_filename(filename)
            if layout_id is None or recipe_num is None:
                print(f"⚠️  Nom de fichier non reconnu: {filename}")
                continue
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    layout_data[layout_id][recipe_num] = data
                    file_recipe_map[(layout_id, recipe_num)] = filename
            except Exception as e:
                print(f"❌ Erreur lors du chargement de {json_file}: {e}")
                continue
        print(f"✅ Données chargées pour {len(layout_data)} layouts")
        # Analyser chaque layout
        for layout_id, recipes in layout_data.items():
            max_diff_overall = -float('inf')
            best_recipe = None
            best_version = 1
            best_solo = 0
            best_coop = 0
            # Parcourir toutes les recettes de ce layout
            for recipe_num, recipe_data in recipes.items():
                if isinstance(recipe_data, list) and len(recipe_data) > 0:
                    max_percentage_diff, version, solo_dist, coop_dist = self.calculate_max_difference(recipe_data)
                    if max_percentage_diff > max_diff_overall:
                        max_diff_overall = max_percentage_diff
                        best_recipe = recipe_num
                        best_version = version
                        best_solo = solo_dist
                        best_coop = coop_dist
            # Enregistrer le meilleur score pour ce layout
            if best_recipe is not None:
                # Utiliser le numéro de recette extrait du nom de fichier
                self.layout_scores[layout_id] = {
                    'max_difference': max_diff_overall,
                    'best_recipe': best_recipe,  # toujours celui du nom de fichier
                    'best_version': best_version,
                    'solo_distance': best_solo,
                    'coop_distance': best_coop,
                    'recipe_name': self.recipe_mapping.get(best_recipe, f"Recipe_{best_recipe:02d}"),
                    'file_recipe_num': best_recipe  # pour usage explicite si besoin
                }
        print(f"✅ Analyse terminée pour {len(self.layout_scores)} layouts")
    
    def select_diverse_layouts(self, max_layouts: int = 780) -> List[str]:
        """
        Sélectionne un ensemble de layouts diversifiés (pas deux fois la même recette).
        
        Args:
            max_layouts: Nombre maximum de layouts à sélectionner
            
        Returns:
            Liste des IDs des layouts sélectionnés
        """
        if not self.layout_scores:
            return []
        
        # Trier les layouts par différence décroissante
        sorted_layouts = sorted(
            self.layout_scores.items(),
            key=lambda x: x[1]['max_difference'],
            reverse=True
        )
        
        selected_layouts = []
        used_recipes = set()
        
        for layout_id, data in sorted_layouts:
            recipe = data['best_recipe']
            
            # Si cette recette n'a pas encore été utilisée, sélectionner ce layout
            if recipe not in used_recipes and len(selected_layouts) < max_layouts:
                selected_layouts.append(layout_id)
                used_recipes.add(recipe)
        
        print(f"✅ Sélectionné {len(selected_layouts)} layouts diversifiés")
        return selected_layouts
    
    def generate_csv_report(self, selected_layouts: List[str]):
        """Génère un rapport CSV des layouts sélectionnés, trié par Coop_Distance et avec Layout_name (utilise le numéro de recette du nom de fichier)"""
        if not selected_layouts:
            print("⚠️  Aucun layout sélectionné pour le rapport CSV")
            return

        csv_data = []
        for layout_id in selected_layouts:
            if layout_id in self.layout_scores:
                data = self.layout_scores[layout_id]
                recipe_num = data['best_recipe']  # toujours celui du nom de fichier
                layout_name = f"L{layout_id}_R{recipe_num}_V{data['best_version']}.layout"
                csv_data.append({
                    'Layout_ID': layout_id,
                    'Recipe_Number': recipe_num,
                    'Recipe_Name': data['recipe_name'],
                    'Version': data['best_version'],
                    'Solo_Distance': data['solo_distance'],
                    'Coop_Distance': data['coop_distance'],
                    'Difference_Percentage': data['max_difference'],
                    'Improvement_Ratio': round(data['max_difference'], 2),
                    'Layout_name': layout_name
                })
        # Créer un DataFrame, trier par Coop_Distance et sauvegarder
        df = pd.DataFrame(csv_data)
        df = df.sort_values(by='Coop_Distance', ascending=True)
        csv_file = os.path.join(self.output_dir, "best_layouts_analysis.csv")
        df.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"✅ Rapport CSV généré: {csv_file}")
        return csv_file
    
    def create_visualization(self, selected_layouts: List[str]):
        """Crée une visualisation graphique des layouts sélectionnés avec distance duo en abscisse et différence pourcentage en ordonnée (PNG uniquement)"""
        if not selected_layouts:
            print("⚠️  Aucun layout sélectionné pour la visualisation")
            return

        # Préparer les données pour le graphique
        coop_distances = []
        percentage_differences = []
        layout_labels = []
        recipe_names = []
        colors = []

        # Créer une palette de couleurs
        color_palette = plt.cm.Set3(np.linspace(0, 1, len(selected_layouts)))

        for i, layout_id in enumerate(selected_layouts):
            if layout_id in self.layout_scores:
                data = self.layout_scores[layout_id]
                coop_distances.append(data['coop_distance'])
                percentage_differences.append(data['max_difference'])
                layout_labels.append(f"L{layout_id}")
                recipe_names.append(data['recipe_name'])
                colors.append(color_palette[i])

        # Créer le graphique scatter
        plt.figure(figsize=(14, 10))

        # Graphique en nuage de points
        scatter = plt.scatter(coop_distances, percentage_differences, 
                            c=colors, s=100, alpha=0.7, edgecolors='black', linewidth=1.5)

        # Ajouter les labels des layouts
        for i, (x, y, label, recipe) in enumerate(zip(coop_distances, percentage_differences, layout_labels, recipe_names)):
            plt.annotate(f'{label}\n{recipe}', (x, y), 
                        xytext=(5, 5), textcoords='offset points', 
                        fontsize=8, ha='left', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor=colors[i], alpha=0.3))

        # Personnaliser le graphique
        plt.title('Layouts Sélectionnés - Relation Distance Coopération vs Amélioration', 
                 fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Distance Coopération (Duo)', fontsize=12, fontweight='bold')
        plt.ylabel('Amélioration par rapport au Solo (%)', fontsize=12, fontweight='bold')

        # Ajouter une grille
        plt.grid(True, alpha=0.3)

        # Ajouter des lignes de référence
        if percentage_differences:
            plt.axhline(y=np.mean(percentage_differences), color='red', linestyle='--', alpha=0.5, 
                       label=f'Moyenne: {np.mean(percentage_differences):.1f}%')

        # Ajuster la mise en page
        plt.tight_layout()
        plt.legend()

        # Sauvegarder le graphique (PNG uniquement)
        plot_file = os.path.join(self.output_dir, "layouts_coop_vs_improvement.png")
        plt.savefig(plot_file, dpi=300, bbox_inches='tight', facecolor='white')

        # Créer aussi un graphique en barres pour la différence en pourcentage
        plt.figure(figsize=(16, 10))

        # Trier par différence décroissante pour le graphique en barres
        sorted_data = sorted(zip(layout_labels, percentage_differences, recipe_names, colors), 
                            key=lambda x: x[1], reverse=True)

        sorted_labels, sorted_diffs, sorted_recipes, sorted_colors = zip(*sorted_data)

        # Diagramme en barres
        bars = plt.bar(range(len(sorted_labels)), sorted_diffs, color=sorted_colors, 
                      alpha=0.8, edgecolor='black', linewidth=0.5)

        # Personnaliser le graphique en barres
        plt.title('Layouts Sélectionnés - Amélioration en Pourcentage (Solo vs Duo)', 
                 fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Layouts', fontsize=12, fontweight='bold')
        plt.ylabel('Amélioration (%)', fontsize=12, fontweight='bold')

        # Configurer l'axe X
        plt.xticks(range(len(sorted_labels)), sorted_labels, rotation=45, ha='right')

        # Ajouter les noms des recettes et les pourcentages sur les barres
        for i, (bar, recipe_name, diff) in enumerate(zip(bars, sorted_recipes, sorted_diffs)):
            height = bar.get_height()
            # Nom de recette au-dessus de la barre
            plt.text(bar.get_x() + bar.get_width()/2., height + max(sorted_diffs) * 0.01,
                    recipe_name, ha='center', va='bottom', fontsize=8, rotation=0)

            # Pourcentage au milieu de la barre
            plt.text(bar.get_x() + bar.get_width()/2., height/2,
                    f'{diff:.1f}%', ha='center', va='center', fontsize=10, fontweight='bold', color='white')

        # Ajuster la mise en page
        plt.tight_layout()
        plt.grid(axis='y', alpha=0.3)

        # Sauvegarder le graphique en barres (PNG uniquement)
        bar_plot_file = os.path.join(self.output_dir, "layouts_percentage_improvement_bars.png")
        plt.savefig(bar_plot_file, dpi=300, bbox_inches='tight', facecolor='white')

        print(f"✅ Visualisations générées:")
        print(f"   📊 Graphique scatter: {plot_file}")
        print(f"   📊 Graphique en barres: {bar_plot_file}")

        # Afficher les graphiques
        plt.show()

        return plot_file, bar_plot_file
    
    def print_summary_statistics(self):
        """Affiche des statistiques de résumé"""
        
        if not self.layout_scores:
            print("⚠️  Aucune donnée à analyser")
            return
        
        differences = [data['max_difference'] for data in self.layout_scores.values()]
        
        print("\n" + "="*60)
        print("📊 STATISTIQUES DE RÉSUMÉ")
        print("="*60)
        print(f"Nombre total de layouts analysés: {len(self.layout_scores)}")
        print(f"Amélioration moyenne (% Solo -> Duo): {np.mean(differences):.2f}%")
        print(f"Amélioration médiane: {np.median(differences):.2f}%")
        print(f"Amélioration minimale: {np.min(differences):.2f}%")
        print(f"Amélioration maximale: {np.max(differences):.2f}%")
        print(f"Écart-type: {np.std(differences):.2f}%")
        
        # Top 10 des layouts
        top_layouts = sorted(
            self.layout_scores.items(),
            key=lambda x: x[1]['max_difference'],
            reverse=True
        )[:10]
        
        print(f"\n🏆 TOP 10 DES LAYOUTS:")
        print("-" * 80)
        print(f"{'Rang':<4} {'Layout':<10} {'Recette':<15} {'Version':<8} {'Amélioration %':<12} {'Recipe Name'}")
        print("-" * 80)
        
        for i, (layout_id, data) in enumerate(top_layouts, 1):
            print(f"{i:<4} {layout_id:<10} {data['best_recipe']:<15} {data['best_version']:<8} {data['max_difference']:<12.1f} {data['recipe_name']}")
    
    def run_full_analysis(self, max_layouts: int = 780):
        """Exécute l'analyse complète"""
        
        print("🚀 DÉMARRAGE DE L'ANALYSE DES LAYOUTS")
        print("="*60)
        
        # 1. Charger le mapping des recettes : Mapping présent dans nom fichier
        #self.load_recipe_mapping()
        
        # 2. Analyser tous les layouts
        print("\n📊 Analyse de tous les layouts...")
        self.analyze_all_layouts()
        
        if not self.layout_scores:
            print("❌ Aucune donnée analysée. Vérifiez le format des fichiers JSON.")
            return
        
        # 3. Afficher les statistiques
        self.print_summary_statistics()
        
        # 4. Sélectionner des layouts diversifiés selon l'amélioration apportée par coopération
        print(f"\n🎯 Sélection de {max_layouts} layouts diversifiés...")
        selected_layouts = self.select_diverse_layouts(max_layouts)
        
        if not selected_layouts:
            print("❌ Aucun layout sélectionné.")
            return
        
        # 5. Générer le rapport CSV
        print(f"\n📄 Génération du rapport CSV...")
        csv_file = self.generate_csv_report(selected_layouts)
        
        # 6. Créer la visualisation
        print(f"\n📈 Création de la visualisation...")
        plot_files = self.create_visualization(selected_layouts)
        
        print("\n" + "="*60)
        print("✅ ANALYSE TERMINÉE AVEC SUCCÈS!")
        print("="*60)
        print(f"📁 Résultats sauvegardés dans: {self.output_dir}/")
        print(f"📄 Rapport CSV: {csv_file}")
        if isinstance(plot_files, tuple):
            print(f"📈 Graphique scatter: {plot_files[0]}")
            print(f"📈 Graphique barres: {plot_files[1]}")
        else:
            print(f"📈 Graphique: {plot_files}")


def main():
    """Fonction principale"""
    
    # Vérifier que le répertoire existe
    results_dir = "test_generation_layout/path_evaluation_results"
    if not os.path.exists(results_dir):
        print(f"❌ Répertoire '{results_dir}' non trouvé!")
        print("Veuillez vous assurer que le répertoire contient les fichiers de résultats.")
        return
    
    # Créer l'analyseur et lancer l'analyse
    analyzer = LayoutEvaluationAnalyzer(results_dir)
    analyzer.run_full_analysis(max_layouts=780)


if __name__ == "__main__":
    main()
