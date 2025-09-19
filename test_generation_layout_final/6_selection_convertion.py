#!/usr/bin/env python3
"""
Script de Sélection et Conversion de Layouts - Overcooked Sciences Cognitives

Ce script sélectionne les 12 meilleurs layouts selon les critères :
a) Ceux avec le plus d'échanges
b) Nombre d'étapes duo similaire
c) Convertit les 2 positions X les plus utilisées en Y
d) Sauvegarde dans le format standard avec IDs

Auteur: Assistant IA Spécialisé  
Date: Septembre 2025
Contexte: Recherche en sciences cognitives sur la coopération humain-IA
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
import statistics

# Import des utilitaires locaux
from utils import read_ndjson, write_ndjson, decompress_grid


@dataclass
class LayoutScore:
    """Classe pour scorer un layout selon nos critères"""
    layout_id: str
    total_exchanges: int
    avg_coop_actions: float
    max_exchange_positions: List[Tuple[int, int]]
    top_recipe_combination: Dict
    exchange_positions_usage: Dict[str, int]


class LayoutSelector:
    """Sélecteur et convertisseur de layouts optimaux"""
    
    def __init__(self):
        """Initialise le sélecteur"""
        self.layouts_data = {}
        self.evaluation_results = []
        self.selected_layouts = []
        
        print("🔄 Sélecteur de layouts initialisé")
    
    def load_all_evaluation_results(self) -> List[Dict]:
        """Charge tous les résultats d'évaluation des fichiers batch"""
        all_results = []
        batch_files = []
        
        # Trouver tous les fichiers batch
        for i in range(1, 20):  # Chercher jusqu'à batch 20
            batch_file = f"recipe_evaluation_results_batch_{i:04d}.ndjson"
            if os.path.exists(batch_file):
                batch_files.append(batch_file)
            else:
                break
        
        print(f"📁 Chargement des résultats depuis {len(batch_files)} fichiers batch")
        
        for batch_file in batch_files:
            batch_results = read_ndjson(batch_file)
            all_results.extend(batch_results)
            print(f"✅ {batch_file}: {len(batch_results)} résultats")
        
        print(f"📊 Total: {len(all_results)} évaluations chargées")
        return all_results
    
    def load_original_layouts(self) -> Dict[str, Dict]:
        """Charge les layouts originaux avec leurs grilles"""
        print("📁 Chargement des layouts originaux...")
        layouts = read_ndjson("layouts_with_objects.ndjson")
        
        layouts_dict = {}
        for layout in layouts:
            layouts_dict[layout['layout_id']] = layout
        
        print(f"✅ {len(layouts_dict)} layouts originaux chargés")
        return layouts_dict
    
    def calculate_layout_scores(self, evaluation_results: List[Dict]) -> List[LayoutScore]:
        """Calcule les scores pour chaque layout selon nos critères"""
        print("📊 Calcul des scores par layout...")
        
        # Grouper par layout_id
        layout_groups = defaultdict(list)
        for result in evaluation_results:
            layout_groups[result['layout_id']].append(result)
        
        layout_scores = []
        
        for layout_id, results in layout_groups.items():
            # Critère A: Total des échanges pour ce layout
            total_exchanges = 0
            all_exchange_positions = Counter()
            coop_actions_list = []
            
            for result in results:
                coop_actions_list.append(result['coop_actions'])
                for pos_str, count in result['exchanges_per_position'].items():
                    total_exchanges += count
                    all_exchange_positions[pos_str] += count
            
            # Critère B: Nombre d'étapes duo similaire (moyenne)
            avg_coop_actions = statistics.mean(coop_actions_list) if coop_actions_list else 0
            
            # Trouver les positions X les plus utilisées pour les échanges
            top_positions = all_exchange_positions.most_common(2)
            max_exchange_positions = []
            for pos_str, count in top_positions:
                if pos_str and ',' in pos_str:
                    row, col = map(int, pos_str.split(','))
                    max_exchange_positions.append((row, col))
            
            # Trouver la meilleure combinaison de recettes pour ce layout
            best_result = min(results, key=lambda x: x['coop_actions'])
            
            score = LayoutScore(
                layout_id=layout_id,
                total_exchanges=total_exchanges,
                avg_coop_actions=avg_coop_actions,
                max_exchange_positions=max_exchange_positions,
                top_recipe_combination=best_result,
                exchange_positions_usage=dict(all_exchange_positions)
            )
            
            layout_scores.append(score)
        
        print(f"✅ {len(layout_scores)} layouts scorés")
        return layout_scores
    
    def select_best_layouts(self, layout_scores: List[LayoutScore], target_count: int = 12) -> List[LayoutScore]:
        """
        Sélectionne les meilleurs layouts selon les critères combinés.
        
        Nouvelle stratégie pour garantir 12 layouts avec recettes distinctes:
        - Créer une liste de tous les couples (layout, recette) possibles
        - Trier par qualité (échanges, puis actions coopératives)
        - Sélectionner les 12 meilleurs couples avec recettes distinctes
        """
        print(f"🎯 Sélection des {target_count} meilleurs layouts...")
        
        # Créer une liste étendue de toutes les combinaisons (layout, recette)
        all_combinations = []
        
        # Pour chaque layout, examiner TOUTES ses évaluations avec TOUTES les recettes
        evaluation_results = self.load_all_evaluation_results()
        layout_groups = defaultdict(list)
        for result in evaluation_results:
            layout_groups[result['layout_id']].append(result)
        
        for layout_score in layout_scores:
            layout_id = layout_score.layout_id
            layout_results = layout_groups[layout_id]
            
            # Pour ce layout, créer un score pour CHAQUE recette testée
            for result in layout_results:
                recipe_id = result['recipe_combination_id']
                coop_actions = result['coop_actions']
                
                # Calculer les échanges pour cette combinaison spécifique
                total_exchanges = sum(result['exchanges_per_position'].values())
                
                # Calculer les positions d'échange pour cette combinaison
                all_exchange_positions = Counter()
                for pos_str, count in result['exchanges_per_position'].items():
                    all_exchange_positions[pos_str] += count
                
                top_positions = all_exchange_positions.most_common(2)
                max_exchange_positions = []
                for pos_str, count in top_positions:
                    if pos_str and ',' in pos_str:
                        row, col = map(int, pos_str.split(','))
                        max_exchange_positions.append((row, col))
                
                # Créer un score spécifique pour ce couple (layout, recette)
                specific_score = LayoutScore(
                    layout_id=layout_id,
                    total_exchanges=total_exchanges,
                    avg_coop_actions=coop_actions,
                    max_exchange_positions=max_exchange_positions,
                    top_recipe_combination={'recipe_combination_id': recipe_id},
                    exchange_positions_usage=dict(result['exchanges_per_position'])
                )
                
                all_combinations.append(specific_score)
        
        # Trier toutes les combinaisons par qualité
        # Priorité 1: Plus d'échanges, Priorité 2: Moins d'actions coopératives  
        sorted_combinations = sorted(all_combinations, 
                                   key=lambda x: (-x.total_exchanges, x.avg_coop_actions))
        
        print(f"📊 {len(sorted_combinations)} combinaisons (layout, recette) évaluées")
        
        # Sélectionner les meilleures avec recettes ET layouts distinctes
        selected = []
        used_recipe_ids = set()
        used_layout_ids = set()
        
        for combo in sorted_combinations:
            if len(selected) >= target_count:
                break
                
            recipe_id = combo.top_recipe_combination['recipe_combination_id']
            layout_id = combo.layout_id
            
            # Vérifier que ni la recette ni le layout ne sont déjà utilisés
            if recipe_id not in used_recipe_ids and layout_id not in used_layout_ids:
                selected.append(combo)
                used_recipe_ids.add(recipe_id)
                used_layout_ids.add(layout_id)
        
        print(f"✅ {len(selected)} layouts sélectionnés avec layouts ET recettes 100% distinctes:")
        for i, score in enumerate(selected):
            recipe_id = score.top_recipe_combination['recipe_combination_id']
            print(f"  {i+1}. {score.layout_id}: {score.total_exchanges} échanges, {score.avg_coop_actions:.1f} actions, recette {recipe_id}")
        
        # Vérification finale - aucun doublon de recette OU de layout autorisé
        recipe_ids = [score.top_recipe_combination['recipe_combination_id'] for score in selected]
        layout_ids = [score.layout_id for score in selected]
        
        if len(set(recipe_ids)) != len(recipe_ids):
            raise ValueError("ERREUR CRITIQUE: Doublons de recettes détectés!")
            
        if len(set(layout_ids)) != len(layout_ids):
            raise ValueError("ERREUR CRITIQUE: Doublons de layouts détectés!")
        
        print(f"🎯 VALIDATION: {len(set(recipe_ids))} recettes uniques ET {len(set(layout_ids))} layouts uniques confirmés - AUCUN DOUBLON")
        
        return selected
    
    def convert_layout_format(self, original_layout: Dict, layout_score: LayoutScore) -> Dict:
        """
        Convertit un layout au format requis avec conversion X -> Y.
        
        Critère C: Remplace les 2 positions X les plus utilisées par Y
        """
        # Décompresser la grille originale
        grid = decompress_grid(original_layout['grid'])
        
        # Convertir en liste de listes pour modification
        grid_list = [list(row) for row in grid]
        
        # Convertir les 2 positions X les plus utilisées en Y
        converted_positions = []
        for pos in layout_score.max_exchange_positions[:2]:  # Top 2 positions
            if pos and len(pos) == 2:
                row, col = pos
                if 0 <= row < len(grid_list) and 0 <= col < len(grid_list[0]):
                    if grid_list[row][col] == 'X':
                        grid_list[row][col] = 'Y'
                        converted_positions.append(pos)
                        print(f"  ✅ Converti X->Y en position ({row}, {col})")
        
        # Remplacer les points par des espaces pour les cases vides
        for row in grid_list:
            for j in range(len(row)):
                if row[j] == '.':
                    row[j] = ' '
        
        # Créer le format de grille avec indentation exacte comme dans le template
        grid_lines = []
        for row in grid_list:
            grid_lines.append(''.join(row))
        
        # Format exact avec triple quotes et indentation
        formatted_grid = '"""' + grid_lines[0] + '\n'
        for line in grid_lines[1:]:
            formatted_grid += '                ' + line + '\n'
        formatted_grid = formatted_grid.rstrip('\n') + '"""'
        
        # Créer le format de sortie selon le template fourni (format exact)
        output_layout = {
            "grid": formatted_grid,
            "start_all_orders": [
                {"ingredients": ["tomato"]}, 
                {"ingredients": ["onion", "onion"]}, 
                {"ingredients": ["onion", "tomato"]}, 
                {"ingredients": ["onion", "onion", "onion"]}, 
                {"ingredients": ["onion", "onion", "tomato"]}, 
                {"ingredients": ["onion", "tomato", "tomato"]}
            ],
            "counter_goals": [],
            "onion_value": 3,
            "tomato_value": 2,
            "onion_time": 9,
            "tomato_time": 6
        }
        
        return output_layout
    
    def save_selected_layouts(self, selected_scores: List[LayoutScore], original_layouts: Dict[str, Dict]):
        """Sauvegarde les layouts sélectionnés dans le dossier test_generation_layout_final/layouts_sélectionnés"""
        
        # Créer le dossier de destination dans le répertoire courant
        output_dir = Path("layouts_sélectionnés")
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Dossier créé: {output_dir}")
        
        print("💾 Conversion et sauvegarde des layouts sélectionnés...")
        
        for i, score in enumerate(selected_scores, 1):
            layout_id = score.layout_id
            recipe_combination_id = score.top_recipe_combination['recipe_combination_id']
            
            # Récupérer le layout original
            if layout_id not in original_layouts:
                print(f"❌ Layout {layout_id} introuvable dans les données originales")
                continue
            
            original_layout = original_layouts[layout_id]
            
            # Convertir le format
            converted_layout = self.convert_layout_format(original_layout, score)
            
            # Générer le nom de fichier selon l'ID du layout et de la recette
            # Format: L{layout_suffix}_R{recipe_id}_V{version}.layout
            layout_suffix = layout_id.split('_')[-2] if '_' in layout_id else layout_id[-8:]
            filename = f"L{layout_suffix}_R{recipe_combination_id:02d}_V00.layout"
            
            # Sauvegarder avec le format JSON exact (indentation personnalisée)
            output_path = output_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                # Format manuel pour correspondre exactement au template
                f.write("{\n")
                f.write(f'    "grid":  {converted_layout["grid"]},\n')
                f.write('    "start_all_orders": ')
                f.write(json.dumps(converted_layout["start_all_orders"], separators=(',', ': ')))
                f.write(',\n')
                f.write('    "counter_goals":')
                f.write(json.dumps(converted_layout["counter_goals"]))
                f.write(',\n')
                f.write(f'    "onion_value" : {converted_layout["onion_value"]},\n')
                f.write(f'    "tomato_value" : {converted_layout["tomato_value"]},\n')
                f.write(f'    "onion_time" : {converted_layout["onion_time"]},\n')
                f.write(f'    "tomato_time" : {converted_layout["tomato_time"]}\n')
                f.write("}")
            
            print(f"  {i:2d}. {filename}: {score.total_exchanges} échanges, recette {recipe_combination_id}, {len(score.max_exchange_positions)} conversions X->Y")
        
        print(f"✅ {len(selected_scores)} layouts sauvegardés dans {output_dir}")
        
        # Vérification finale des recettes
        final_recipe_ids = sorted(set(score.top_recipe_combination['recipe_combination_id'] for score in selected_scores))
        print(f"📋 Recettes utilisées ({len(final_recipe_ids)} uniques): {final_recipe_ids}")
        
        if len(final_recipe_ids) != len(selected_scores):
            raise ValueError("ERREUR FINALE: Doublons de recettes dans la sauvegarde!")
        
        print(f"🎯 SUCCÈS: Politique ZÉRO DOUBLON respectée - {len(final_recipe_ids)} recettes distinctes")
    
    def run_selection(self):
        """Exécute le processus complet de sélection et conversion"""
        print("\n🚀 DÉMARRAGE DE LA SÉLECTION DE LAYOUTS")
        print("="*60)
        
        # Charger toutes les données
        evaluation_results = self.load_all_evaluation_results()
        original_layouts = self.load_original_layouts()
        
        if not evaluation_results:
            print("❌ Aucun résultat d'évaluation trouvé")
            return
        
        # Calculer les scores
        layout_scores = self.calculate_layout_scores(evaluation_results)
        
        if not layout_scores:
            print("❌ Aucun score calculé")
            return
        
        # Diagnostic: Vérifier la diversité des recettes
        recipe_counts = {}
        for score in layout_scores:
            recipe_id = score.top_recipe_combination['recipe_combination_id']
            recipe_counts[recipe_id] = recipe_counts.get(recipe_id, 0) + 1
        
        unique_recipes = len(recipe_counts)
        print(f"🔍 DIAGNOSTIC: {unique_recipes} recettes uniques utilisées par {len(layout_scores)} layouts")
        print(f"🎯 Objectif: Sélectionner 12 layouts avec recettes distinctes (donc besoin d'au moins 12 recettes uniques)")
        
        if unique_recipes < 12:
            print(f"⚠️ PROBLÈME: Seulement {unique_recipes} recettes uniques disponibles, impossible d'atteindre 12 layouts")
        else:
            print(f"✅ Suffisamment de recettes uniques ({unique_recipes} >= 12)")
        
        # Sélectionner les meilleurs
        selected_scores = self.select_best_layouts(layout_scores, target_count=12)
        
        if not selected_scores:
            print("❌ Aucun layout sélectionné")
            return
        
        # Sauvegarder
        self.save_selected_layouts(selected_scores, original_layouts)
        
        print(f"\n✅ SÉLECTION TERMINÉE!")
        print(f"📊 {len(selected_scores)} layouts sélectionnés et convertis")
        print(f"📁 Fichiers disponibles dans: layouts_sélectionnés/")


def main():
    """Fonction principale"""
    print("🎯 SÉLECTEUR DE LAYOUTS - OVERCOOKED")
    print("Sélection des meilleurs layouts selon critères scientifiques")
    print("Critères: échanges max, étapes similaires, conversion X->Y")
    print()
    
    # Créer et exécuter le sélecteur
    selector = LayoutSelector()
    selector.run_selection()


if __name__ == "__main__":
    main()