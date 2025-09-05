#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluateur exhaustif qui teste tous les layouts avec tous les groupes de recettes
Chaque layout est évalué avec chaque groupe de 6 recettes
L'ID du groupe de recettes est inclus dans le nom du layout évalué
"""

import json
import time
import argparse
from pathlib import Path
import random
from collections import defaultdict
import multiprocessing as mp

class ExhaustiveEvaluator:
    """Évaluateur exhaustif layout x groupes de recettes."""
    
    def __init__(self):
        """Initialise l'évaluateur exhaustif."""
        self.base_dir = Path(__file__).parent.parent
        self.layouts_dir = self.base_dir / "outputs" / "validated_layouts"
        self.evaluation_dir = self.base_dir / "outputs" / "exhaustive_evaluation"
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Évaluateur exhaustif initialisé")
        print(f"📁 Layouts: {self.layouts_dir}")
        print(f"📁 Résultats: {self.evaluation_dir}")
    
    def load_recipe_groups(self):
        """Charge tous les groupes de recettes."""
        # Chercher le fichier de groupes le plus récent
        group_files = list(self.base_dir.glob("outputs/all_recipe_groups_*.json"))
        
        if not group_files:
            print("❌ Aucun fichier de groupes de recettes trouvé")
            print("   Exécutez d'abord: python3 scripts/0_recipe_groups_generator.py")
            return None
        
        # Prendre le plus récent
        latest_file = max(group_files, key=lambda f: f.stat().st_mtime)
        
        print(f"📊 Chargement: {latest_file.name}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        recipe_groups = data['recipe_groups']
        base_recipes = data['base_recipes']
        
        print(f"✅ {len(recipe_groups):,} groupes de recettes chargés")
        print(f"✅ {len(base_recipes)} recettes de base")
        
        return recipe_groups, base_recipes
    
    def load_layouts(self, sample_size=None):
        """Charge les layouts à évaluer."""
        layout_files = list(self.layouts_dir.glob("*.json"))
        
        if not layout_files:
            print(f"❌ Aucun fichier de layout trouvé dans {self.layouts_dir}")
            return []
        
        all_layouts = []
        for layout_file in layout_files:
            try:
                with open(layout_file, 'r') as f:
                    data = json.load(f)
                    if 'layouts' in data:
                        all_layouts.extend(data['layouts'])
            except Exception as e:
                print(f"⚠️  Erreur lecture {layout_file}: {e}")
        
        if len(all_layouts) == 0:
            print("❌ Aucun layout valide trouvé")
            return []
        
        # Échantillonner si demandé
        if sample_size and len(all_layouts) > sample_size:
            all_layouts = random.sample(all_layouts, sample_size)
        
        return all_layouts
    
    def analyze_layout_structure(self, layout_str):
        """Analyse la structure d'un layout (repris de l'évaluateur structural)."""
        lines = layout_str.strip().split('\n')
        grid = [list(line) for line in lines]
        
        # Positions des éléments
        positions = self.extract_positions(grid)
        
        # Calculs de distances et connectivité
        connectivity_score = self.calculate_connectivity(positions)
        distance_efficiency = self.calculate_distance_efficiency(positions)
        interaction_potential = self.calculate_interaction_potential(positions)
        
        return {
            'connectivity_score': connectivity_score,
            'distance_efficiency': distance_efficiency,
            'interaction_potential': interaction_potential,
            'positions': positions
        }
    
    def extract_positions(self, grid):
        """Extrait les positions de tous les objets."""
        positions = {
            'player1': None,
            'player2': None,
            'onion_dispenser': [],
            'tomato_dispenser': [],
            'pot': [],
            'dish_dispenser': [],
            'serving_station': [],
            'counter': [],
            'walls': [],
            'empty': []
        }
        
        for i, row in enumerate(grid):
            for j, cell in enumerate(row):
                pos = (i, j)
                if cell == '1':
                    positions['player1'] = pos
                elif cell == '2':
                    positions['player2'] = pos
                elif cell == 'O':
                    positions['onion_dispenser'].append(pos)
                elif cell == 'T':
                    positions['tomato_dispenser'].append(pos)
                elif cell == 'P':
                    positions['pot'].append(pos)
                elif cell == 'D':
                    positions['dish_dispenser'].append(pos)
                elif cell == 'S':
                    positions['serving_station'].append(pos)
                elif cell == 'Y':
                    positions['counter'].append(pos)
                elif cell == 'X':
                    positions['walls'].append(pos)
                elif cell == '.':
                    positions['empty'].append(pos)
        
        return positions
    
    def manhattan_distance(self, pos1, pos2):
        """Calcule la distance de Manhattan entre deux positions."""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
    
    def calculate_connectivity(self, positions):
        """Calcule un score de connectivité."""
        if not positions['player1'] or not positions['player2']:
            return 0
        
        player_distance = self.manhattan_distance(positions['player1'], positions['player2'])
        
        essential_objects = (
            positions['onion_dispenser'] + positions['tomato_dispenser'] +
            positions['pot'] + positions['dish_dispenser'] + positions['serving_station']
        )
        
        if not essential_objects:
            return 0
        
        p1_distances = [self.manhattan_distance(positions['player1'], obj) for obj in essential_objects]
        p2_distances = [self.manhattan_distance(positions['player2'], obj) for obj in essential_objects]
        
        avg_p1_distance = sum(p1_distances) / len(p1_distances)
        avg_p2_distance = sum(p2_distances) / len(p2_distances)
        
        optimal_player_distance = 3
        distance_score = 1 / (1 + abs(player_distance - optimal_player_distance))
        
        max_distance = 10
        access_score = (2 * max_distance - avg_p1_distance - avg_p2_distance) / (2 * max_distance)
        access_score = max(0, min(1, access_score))
        
        return (distance_score + access_score) / 2
    
    def calculate_distance_efficiency(self, positions):
        """Calcule l'efficacité des distances."""
        if not positions['player1'] or not positions['player2']:
            return 0
        
        workflow_distances = []
        
        for player_pos in [positions['player1'], positions['player2']]:
            ingredient_distances = []
            for ingredient_pos in positions['onion_dispenser'] + positions['tomato_dispenser']:
                ingredient_distances.append(self.manhattan_distance(player_pos, ingredient_pos))
            
            pot_distances = []
            for pot_pos in positions['pot']:
                pot_distances.append(self.manhattan_distance(player_pos, pot_pos))
            
            dish_distances = []
            for dish_pos in positions['dish_dispenser']:
                dish_distances.append(self.manhattan_distance(player_pos, dish_pos))
            
            serving_distances = []
            for serving_pos in positions['serving_station']:
                serving_distances.append(self.manhattan_distance(player_pos, serving_pos))
            
            if (ingredient_distances and pot_distances and 
                dish_distances and serving_distances):
                
                min_workflow = (
                    min(ingredient_distances) + min(pot_distances) +
                    min(dish_distances) + min(serving_distances)
                )
                workflow_distances.append(min_workflow)
        
        if not workflow_distances:
            return 0
        
        avg_workflow = sum(workflow_distances) / len(workflow_distances)
        max_workflow = 20
        
        efficiency_score = (max_workflow - avg_workflow) / max_workflow
        return max(0, min(1, efficiency_score))
    
    def calculate_interaction_potential(self, positions):
        """Calcule le potentiel d'interaction."""
        if not positions['player1'] or not positions['player2']:
            return 0
        
        interaction_zones = positions['counter'] + positions['empty']
        
        shared_zones = 0
        for zone in interaction_zones:
            p1_dist = self.manhattan_distance(positions['player1'], zone)
            p2_dist = self.manhattan_distance(positions['player2'], zone)
            
            if p1_dist <= 3 and p2_dist <= 3:
                shared_zones += 1
        
        max_zones = len(interaction_zones)
        if max_zones == 0:
            return 0
        
        base_score = shared_zones / max_zones
        counter_ratio = len(positions['counter']) / (len(positions['counter']) + len(positions['empty']) + 1)
        
        return min(1, base_score * (1 + counter_ratio * 0.5))
    
    def estimate_metrics_for_recipe_group(self, structural_analysis, recipe_group):
        """
        Estime les métriques pour un groupe de recettes spécifique.
        
        Args:
            structural_analysis: Analyse structurelle du layout
            recipe_group: Groupe de 6 recettes
            
        Returns:
            dict: Métriques estimées pour ce groupe
        """
        recipes = recipe_group['recipes']
        
        # Calculer la complexité du groupe
        total_ingredients = sum(len(recipe['ingredients']) for recipe in recipes)
        avg_complexity = recipe_group['avg_complexity']
        max_complexity = max(recipe['complexity'] for recipe in recipes)
        
        # Facteurs de base
        efficiency_factor = structural_analysis['distance_efficiency']
        connectivity_factor = structural_analysis['connectivity_score']
        interaction_factor = structural_analysis['interaction_potential']
        
        # Estimation duo steps (influenced by recipe complexity)
        base_steps = 120
        complexity_multiplier = 1 + (avg_complexity - 1) * 0.3  # Plus complexe = plus de steps
        ingredient_multiplier = 1 + (total_ingredients - 12) * 0.02  # Plus d'ingrédients = plus de steps
        
        estimated_duo_steps = base_steps * complexity_multiplier * ingredient_multiplier
        estimated_duo_steps *= (2 - efficiency_factor - connectivity_factor * 0.5)
        estimated_duo_steps = max(60, min(400, estimated_duo_steps))
        
        # Estimation solo steps (toujours plus élevé, plus affecté par la complexité)
        solo_multiplier = 1.8 + (avg_complexity - 1) * 0.2
        estimated_solo_steps = estimated_duo_steps * solo_multiplier
        
        # Estimation cooperation gain
        if estimated_solo_steps > 0:
            cooperation_gain = (estimated_solo_steps - estimated_duo_steps) / estimated_solo_steps * 100
        else:
            cooperation_gain = 0
        
        # Estimation exchanges (influenced by recipe complexity and interaction potential)
        base_exchanges = interaction_factor * 6
        complexity_exchange_bonus = (avg_complexity - 1) * 0.5  # Plus complexe = plus d'échanges
        estimated_exchanges = base_exchanges + complexity_exchange_bonus
        estimated_exchanges = max(0, min(12, estimated_exchanges))
        
        return {
            'estimated_duo_steps': round(estimated_duo_steps),
            'estimated_solo_steps': round(estimated_solo_steps),
            'estimated_cooperation_gain': round(cooperation_gain, 1),
            'estimated_exchanges': round(estimated_exchanges, 1),
            'recipe_complexity_score': round(avg_complexity * 20, 1),
            'recipe_group_id': recipe_group['group_id'],
            'recipe_ids': recipe_group['recipe_ids']
        }
    
    def evaluate_layout_with_all_groups(self, layout_data, recipe_groups):
        """
        Évalue un layout avec tous les groupes de recettes.
        
        Args:
            layout_data: Données du layout
            recipe_groups: Liste de tous les groupes de recettes
            
        Returns:
            list: Liste des évaluations pour chaque groupe
        """
        layout_id = layout_data['hash']
        layout_str = layout_data['grid']
        
        # Analyse structurelle une seule fois par layout
        structural_analysis = self.analyze_layout_structure(layout_str)
        
        evaluations = []
        
        for recipe_group in recipe_groups:
            # Créer un nom unique combinant layout et groupe de recettes
            combined_id = f"{layout_id}_{recipe_group['group_id']}"
            
            # Estimer les métriques pour ce groupe de recettes
            metrics = self.estimate_metrics_for_recipe_group(structural_analysis, recipe_group)
            
            evaluation = {
                'layout_id': layout_id,
                'recipe_group_id': recipe_group['group_id'],
                'combined_id': combined_id,
                'layout_hash': layout_data['hash'],
                'n_empty': layout_data['n_empty'],
                'density_type': layout_data.get('density_type', 'unknown'),
                'recipe_group_info': {
                    'group_id': recipe_group['group_id'],
                    'recipe_ids': recipe_group['recipe_ids'],
                    'avg_complexity': recipe_group['avg_complexity'],
                    'total_ingredients': recipe_group['total_ingredients'],
                    'complexity_distribution': recipe_group['complexity_distribution']
                },
                'structural_analysis': structural_analysis,
                'estimated_metrics': metrics
            }
            
            evaluations.append(evaluation)
        
        return evaluations
    
    def evaluate_batch_worker(self, args):
        """Worker pour évaluation parallèle."""
        layouts_batch, recipe_groups, batch_id = args
        
        print(f"📊 Worker {batch_id}: traitement de {len(layouts_batch)} layouts")
        
        all_evaluations = []
        
        for i, layout in enumerate(layouts_batch):
            if i % 5 == 0:
                print(f"   Worker {batch_id}: layout {i}/{len(layouts_batch)}")
            
            layout_evaluations = self.evaluate_layout_with_all_groups(layout, recipe_groups)
            all_evaluations.extend(layout_evaluations)
        
        print(f"✅ Worker {batch_id}: {len(all_evaluations)} évaluations complétées")
        
        return all_evaluations
    
    def run_exhaustive_evaluation(self, layout_sample_size=None, recipe_group_sample_size=None, processes=None):
        """
        Lance l'évaluation exhaustive.
        
        Args:
            layout_sample_size: Nombre de layouts à évaluer (None = tous)
            recipe_group_sample_size: Nombre de groupes de recettes (None = tous)
            processes: Nombre de processus parallèles
        """
        print(f"🚀 ÉVALUATION EXHAUSTIVE")
        print("="*70)
        
        # Charger les groupes de recettes
        recipe_data = self.load_recipe_groups()
        if recipe_data is None:
            return False
        
        recipe_groups, base_recipes = recipe_data
        
        # Échantillonner les groupes de recettes si demandé
        if recipe_group_sample_size and len(recipe_groups) > recipe_group_sample_size:
            recipe_groups = random.sample(recipe_groups, recipe_group_sample_size)
            print(f"📋 Échantillon de {len(recipe_groups)} groupes de recettes")
        
        # Charger les layouts
        layouts = self.load_layouts(layout_sample_size)
        if not layouts:
            return False
        
        print(f"📊 Configuration d'évaluation:")
        print(f"   - Layouts: {len(layouts)}")
        print(f"   - Groupes de recettes: {len(recipe_groups):,}")
        print(f"   - Évaluations totales: {len(layouts) * len(recipe_groups):,}")
        
        # Vérifier si c'est raisonnable
        total_evaluations = len(layouts) * len(recipe_groups)
        if total_evaluations > 1_000_000:
            print(f"⚠️  ATTENTION: {total_evaluations:,} évaluations au total!")
            print("   Cela peut prendre beaucoup de temps...")
        
        # Configuration du parallélisme
        if processes is None:
            processes = min(mp.cpu_count() - 1, 4)  # Limiter pour éviter surcharge
        
        print(f"🚀 Évaluation parallèle avec {processes} processus")
        
        start_time = time.time()
        
        # Diviser les layouts en batches pour parallélisation
        batch_size = max(1, len(layouts) // processes)
        layout_batches = [layouts[i:i+batch_size] for i in range(0, len(layouts), batch_size)]
        
        # Préparer les arguments pour les workers
        worker_args = [(batch, recipe_groups, i) for i, batch in enumerate(layout_batches)]
        
        # Exécution parallèle
        if processes == 1:
            # Mode séquentiel pour debug
            batch_results = [self.evaluate_batch_worker(args) for args in worker_args]
        else:
            # Mode parallèle
            with mp.Pool(processes) as pool:
                batch_results = pool.map(self.evaluate_batch_worker, worker_args)
        
        # Combiner tous les résultats
        all_evaluations = []
        for batch_result in batch_results:
            all_evaluations.extend(batch_result)
        
        duration = time.time() - start_time
        
        print(f"\n🎉 ÉVALUATION EXHAUSTIVE TERMINÉE!")
        print(f"📊 Résultats:")
        print(f"   - Évaluations réalisées: {len(all_evaluations):,}")
        print(f"   - Durée: {duration:.1f}s ({duration/60:.1f} min)")
        if duration > 0:
            print(f"   - Vitesse: {len(all_evaluations)/duration:.1f} éval/seconde")
        
        # Sauvegarder les résultats
        output_file = self.save_exhaustive_results(all_evaluations, layouts, recipe_groups)
        
        print(f"💾 Résultats sauvés: {output_file.name}")
        
        # Afficher quelques statistiques
        self.print_evaluation_statistics(all_evaluations)
        
        return True
    
    def save_exhaustive_results(self, all_evaluations, layouts, recipe_groups):
        """Sauvegarde les résultats de l'évaluation exhaustive."""
        timestamp = int(time.time())
        output_file = self.evaluation_dir / f"exhaustive_evaluation_{timestamp}.json"
        
        # Statistiques de l'évaluation
        stats = {
            'total_evaluations': len(all_evaluations),
            'unique_layouts': len(layouts),
            'recipe_groups_used': len(recipe_groups),
            'evaluations_per_layout': len(recipe_groups),
            'avg_estimated_duo_steps': sum(eval_data['estimated_metrics']['estimated_duo_steps'] 
                                         for eval_data in all_evaluations) / len(all_evaluations),
            'avg_estimated_exchanges': sum(eval_data['estimated_metrics']['estimated_exchanges'] 
                                         for eval_data in all_evaluations) / len(all_evaluations)
        }
        
        output_data = {
            'timestamp': timestamp,
            'evaluation_type': 'exhaustive_layout_recipe_groups',
            'statistics': stats,
            'layouts_count': len(layouts),
            'recipe_groups_count': len(recipe_groups),
            'total_evaluations': len(all_evaluations),
            'evaluations': all_evaluations
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        return output_file
    
    def print_evaluation_statistics(self, all_evaluations):
        """Affiche les statistiques d'évaluation."""
        if not all_evaluations:
            return
        
        print(f"\n📈 STATISTIQUES D'ÉVALUATION:")
        print("="*60)
        
        # Métriques moyennes
        duo_steps = [eval_data['estimated_metrics']['estimated_duo_steps'] for eval_data in all_evaluations]
        exchanges = [eval_data['estimated_metrics']['estimated_exchanges'] for eval_data in all_evaluations]
        cooperation_gains = [eval_data['estimated_metrics']['estimated_cooperation_gain'] for eval_data in all_evaluations]
        
        print(f"🎯 MÉTRIQUES MOYENNES:")
        print(f"   - Steps duo: {sum(duo_steps) / len(duo_steps):.1f}")
        print(f"   - Échanges: {sum(exchanges) / len(exchanges):.1f}")
        print(f"   - Gain coopération: {sum(cooperation_gains) / len(cooperation_gains):.1f}%")
        
        # Top évaluations
        top_cooperation = sorted(all_evaluations, 
                               key=lambda x: x['estimated_metrics']['estimated_cooperation_gain'], 
                               reverse=True)[:5]
        
        print(f"\n🏆 TOP 5 MEILLEURES ÉVALUATIONS (gain coopération):")
        for i, eval_data in enumerate(top_cooperation, 1):
            combined_id = eval_data['combined_id']
            gain = eval_data['estimated_metrics']['estimated_cooperation_gain']
            steps = eval_data['estimated_metrics']['estimated_duo_steps']
            exchanges = eval_data['estimated_metrics']['estimated_exchanges']
            recipe_group = eval_data['recipe_group_id']
            
            print(f"   {i}. {combined_id[:20]}...")
            print(f"      Gain: {gain:.1f}%, Steps: {steps}, Échanges: {exchanges:.1f}")
            print(f"      Groupe recettes: {recipe_group}")

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(
        description='Évaluateur exhaustif layout x groupes de recettes'
    )
    
    parser.add_argument(
        '--layout-sample',
        type=int,
        default=None,
        help='Nombre de layouts à évaluer (défaut: tous)'
    )
    
    parser.add_argument(
        '--recipe-group-sample',
        type=int,
        default=None,
        help='Nombre de groupes de recettes (défaut: tous)'
    )
    
    parser.add_argument(
        '--processes',
        type=int,
        default=None,
        help='Nombre de processus parallèles (défaut: auto)'
    )
    
    args = parser.parse_args()
    
    try:
        evaluator = ExhaustiveEvaluator()
        success = evaluator.run_exhaustive_evaluation(
            layout_sample_size=args.layout_sample,
            recipe_group_sample_size=args.recipe_group_sample,
            processes=args.processes
        )
        
        if success:
            print("✅ Évaluation exhaustive réussie!")
        else:
            print("❌ Échec de l'évaluation")
            exit(1)
            
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
