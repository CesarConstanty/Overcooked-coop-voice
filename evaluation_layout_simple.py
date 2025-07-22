#!/usr/bin/env python3
"""
evaluation_layout_simple.py

Version simplifiée de l'évaluateur de layouts pour éviter les problèmes de compatibilité.
Utilise RandomAgent comme substitut et simule des temps de complétion basés sur la structure.
"""

import os
import glob
import time
import json
import numpy as np
from typing import Dict, List, Tuple, Optional

from overcooked_ai_py.agents.benchmarking import AgentEvaluator
from overcooked_ai_py.agents.agent import RandomAgent, AgentPair
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import NO_COUNTERS_PARAMS


class SimpleLayoutEvaluator:
    """
    Classe simplifiée pour l'évaluation rapide de layouts.
    Utilise des agents plus simples pour éviter les problèmes de compatibilité.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 800, num_games_per_layout: int = 3):
        """
        Initialise l'évaluateur simplifié.
        
        Args:
            layouts_directory: Répertoire contenant les fichiers .layout
            horizon: Nombre maximum de steps par partie
            num_games_per_layout: Nombre de parties à jouer par layout
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.results = {}
        
        print(f"🎮 ÉVALUATEUR SIMPLIFIÉ DE LAYOUTS OVERCOOKED")
        print(f"📁 Répertoire: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"🤖 Utilisation d'agents RandomAgent pour éviter les blocages")
    
    def discover_layouts(self) -> List[str]:
        """Découvre tous les fichiers .layout dans le répertoire."""
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names}")
        return layout_names
    
    def analyze_layout_structure(self, mdp: OvercookedGridworld) -> Dict:
        """Analyse la structure d'un layout."""
        elements = {
            'width': mdp.width,
            'height': mdp.height,
            'tomato_dispensers': sum(row.count('T') for row in mdp.terrain_mtx),
            'onion_dispensers': sum(row.count('O') for row in mdp.terrain_mtx),
            'dish_dispensers': sum(row.count('D') for row in mdp.terrain_mtx),
            'pots': sum(row.count('P') for row in mdp.terrain_mtx),
            'serve_areas': sum(row.count('S') for row in mdp.terrain_mtx),
            'players': len(mdp.start_player_positions),
            'walls': sum(row.count('X') for row in mdp.terrain_mtx),
            'counters': sum(row.count('-') for row in mdp.terrain_mtx)
        }
        
        # Vérifier la viabilité
        viable = (
            elements['tomato_dispensers'] > 0 and 
            elements['onion_dispensers'] > 0 and
            elements['dish_dispensers'] > 0 and
            elements['pots'] > 0 and
            elements['serve_areas'] > 0 and
            elements['players'] >= 2
        )
        
        elements['viable'] = viable
        elements['complexity_score'] = (
            elements['tomato_dispensers'] + elements['onion_dispensers'] + 
            elements['dish_dispensers'] + elements['pots'] + elements['serve_areas']
        )
        
        return elements
    
    def analyze_recipes(self, mdp: OvercookedGridworld) -> Dict:
        """Analyse les recettes demandées."""
        recipes_info = {
            'recipes': [],
            'num_recipes': 0,
            'total_orders': 0,
            'requires_onions': False,
            'requires_tomatoes': False
        }
        
        if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders:
            recipes_info['total_orders'] = len(mdp.start_all_orders)
            
            for order in mdp.start_all_orders:
                if 'ingredients' in order:
                    ingredients = order['ingredients']
                    recipes_info['recipes'].append({
                        'ingredients': ingredients,
                        'onion_count': ingredients.count('onion'),
                        'tomato_count': ingredients.count('tomato'),
                        'value': order.get('value', None)
                    })
                    
                    if 'onion' in ingredients:
                        recipes_info['requires_onions'] = True
                    if 'tomato' in ingredients:
                        recipes_info['requires_tomatoes'] = True
            
            recipes_info['num_recipes'] = len(set(str(r['ingredients']) for r in recipes_info['recipes']))
        
        return recipes_info
    
    def estimate_completion_time(self, structure: Dict, recipes: Dict) -> Dict:
        """
        Estime le temps de complétion basé sur la structure du layout.
        Utilisé comme substitut quand l'évaluation complète échoue.
        """
        # Calcul basé sur la complexité du layout
        base_time = 200  # Temps de base
        
        # Facteurs qui influencent le temps
        distance_factor = (structure['width'] + structure['height']) * 5
        ingredient_factor = recipes['total_orders'] * 50
        complexity_factor = structure['complexity_score'] * 30
        
        # Pénalités pour les layouts difficiles
        if structure['pots'] < recipes['total_orders']:
            complexity_factor += 100  # Pas assez de casseroles
        
        if structure['onion_dispensers'] < 1 and recipes['requires_onions']:
            complexity_factor += 200  # Manque d'oignons
            
        if structure['tomato_dispensers'] < 1 and recipes['requires_tomatoes']:
            complexity_factor += 200  # Manque de tomates
        
        estimated_time = base_time + distance_factor + ingredient_factor + complexity_factor
        
        # Simulation de plusieurs parties avec variation
        games_times = []
        for i in range(self.num_games_per_layout):
            variation = np.random.normal(0, estimated_time * 0.1)  # 10% de variation
            game_time = max(100, estimated_time + variation)  # Minimum 100 steps
            game_time = min(self.horizon, game_time)  # Maximum horizon
            games_times.append(int(game_time))
        
        # Simulation de scores (basé sur complétion)
        scores = []
        for game_time in games_times:
            if game_time < self.horizon * 0.8:  # Complétion réussie
                score = recipes['total_orders'] * 20  # 20 points par recette
            else:
                score = max(0, recipes['total_orders'] * 10 - (game_time - 400))  # Score partiel
            scores.append(max(0, score))
        
        return {
            'estimated_times': games_times,
            'estimated_scores': scores,
            'estimated_completion_rate': sum(1 for t in games_times if t < self.horizon * 0.8) / len(games_times),
            'average_time': np.mean(games_times),
            'method': 'structural_estimation'
        }
    
    def evaluate_single_layout(self, layout_name: str) -> Dict:
        """Évalue un seul layout avec méthode simplifiée."""
        print(f"\n🏗️ Évaluation: {layout_name}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Analyser la structure
            structure_analysis = self.analyze_layout_structure(mdp)
            print(f"📊 Structure: {structure_analysis['width']}x{structure_analysis['height']}, "
                  f"T={structure_analysis['tomato_dispensers']}, "
                  f"O={structure_analysis['onion_dispensers']}, "
                  f"P={structure_analysis['pots']}, "
                  f"S={structure_analysis['serve_areas']}")
            
            # Analyser les recettes
            recipes_info = self.analyze_recipes(mdp)
            print(f"🍲 Recettes: {recipes_info['num_recipes']} types, "
                  f"Total: {recipes_info['total_orders']} commandes")
            for recipe in recipes_info['recipes'][:3]:
                print(f"   - {recipe['ingredients']} (valeur: {recipe.get('value', 'inconnue')})")
            
            # Vérifier la viabilité
            if not structure_analysis['viable']:
                print("❌ Layout non viable - éléments manquants")
                return {
                    'layout_name': layout_name,
                    'viable': False,
                    'structure': structure_analysis,
                    'recipes': recipes_info,
                    'error': 'Layout manque d\'éléments essentiels',
                    'evaluation_time': time.time() - start_time
                }
            
            print("✅ Layout viable")
            
            # Tentative d'évaluation avec RandomAgent
            try:
                print("🤖 Tentative d'évaluation avec RandomAgent...")
                env_params = {"horizon": self.horizon}
                mlam_params = NO_COUNTERS_PARAMS.copy()  # Paramètres simplifiés
                mlam_params["max_iter"] = 2  # Réduire les itérations
                
                evaluator = AgentEvaluator.from_mdp(mdp, env_params, mlam_params=mlam_params)
                
                evaluation_results = evaluator.evaluate_random_pair(
                    num_games=self.num_games_per_layout,
                    native_eval=True
                )
                
                print("✅ Évaluation RandomAgent réussie")
                real_evaluation = True
                
            except Exception as e:
                print(f"⚠️ Évaluation RandomAgent échouée: {e}")
                print("🧮 Utilisation de l'estimation structurelle...")
                evaluation_results = self.estimate_completion_time(structure_analysis, recipes_info)
                real_evaluation = False
            
            eval_time = time.time() - start_time
            
            # Traiter les résultats
            results = {
                'layout_name': layout_name,
                'viable': True,
                'structure': structure_analysis,
                'recipes': recipes_info,
                'timing': {
                    'total_evaluation_time': eval_time,
                },
                'games_played': self.num_games_per_layout,
                'evaluation_method': 'real_agent' if real_evaluation else 'structural_estimation'
            }
            
            # Analyser les scores et temps
            if real_evaluation and 'ep_rewards' in evaluation_results:
                rewards = evaluation_results['ep_rewards']
                if hasattr(rewards, 'tolist'):
                    rewards = rewards.tolist()
                if isinstance(rewards, list) and len(rewards) > 0 and isinstance(rewards[0], list):
                    rewards = [item for sublist in rewards for item in sublist]
                rewards = [float(r) for r in rewards if isinstance(r, (int, float))]
                
                if rewards:
                    results['scores'] = {
                        'raw_scores': rewards,
                        'average_score': np.mean(rewards),
                        'max_score': max(rewards),
                        'min_score': min(rewards)
                    }
                    print(f"📈 Points: {rewards} (moy: {results['scores']['average_score']:.1f})")
            elif not real_evaluation:
                # Utiliser les scores estimés
                rewards = evaluation_results['estimated_scores']
                results['scores'] = {
                    'raw_scores': rewards,
                    'average_score': np.mean(rewards),
                    'max_score': max(rewards),
                    'min_score': min(rewards)
                }
                print(f"📈 Points estimés: {rewards} (moy: {results['scores']['average_score']:.1f})")
            
            # Analyser les temps de complétion
            if real_evaluation and 'ep_lengths' in evaluation_results:
                lengths = evaluation_results['ep_lengths']
                if hasattr(lengths, 'tolist'):
                    lengths = lengths.tolist()
                if isinstance(lengths, list) and len(lengths) > 0 and isinstance(lengths[0], list):
                    lengths = [item for sublist in lengths for item in sublist]
                lengths = [int(l) for l in lengths if isinstance(l, (int, float))]
            else:
                # Utiliser les temps estimés
                lengths = evaluation_results['estimated_times']
            
            if lengths:
                completed_games = [l for l in lengths if l < self.horizon]
                
                results['completion'] = {
                    'raw_lengths': lengths,
                    'average_length': np.mean(lengths),
                    'completed_games_count': len(completed_games),
                    'completion_rate': len(completed_games) / len(lengths),
                    'average_completion_time': np.mean(completed_games) if completed_games else None,
                    'fastest_completion': min(completed_games) if completed_games else None,
                    'slowest_completion': max(completed_games) if completed_games else None
                }
                
                print(f"⏱️ Durées: {lengths} steps")
                print(f"✅ Parties complétées: {len(completed_games)}/{len(lengths)} ({results['completion']['completion_rate']*100:.1f}%)")
                
                if completed_games:
                    print(f"🏁 Temps de complétion moyen: {results['completion']['average_completion_time']:.1f} steps")
                    print(f"🚀 Plus rapide: {results['completion']['fastest_completion']} steps")
                    print(f"🐌 Plus lent: {results['completion']['slowest_completion']} steps")
                    
                    # MÉTRIQUE PRINCIPALE pour le classement
                    results['primary_metric'] = results['completion']['average_completion_time']
                    results['primary_metric_name'] = "Temps de complétion moyen (steps)"
                else:
                    print(f"❌ AUCUNE RECETTE COMPLÉTÉE")
                    results['primary_metric'] = self.horizon + 100
                    results['primary_metric_name'] = "Temps de complétion (pénalisé - aucune complétion)"
            
            print(f"✅ Évaluation terminée en {eval_time:.1f}s")
            return results
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"❌ Erreur lors de l'évaluation: {e}")
            return {
                'layout_name': layout_name,
                'viable': False,
                'error': str(e),
                'evaluation_time': error_time
            }
    
    def evaluate_all_layouts(self) -> Dict:
        """Évalue tous les layouts découverts."""
        layout_names = self.discover_layouts()
        
        if not layout_names:
            print("❌ Aucun layout trouvé dans le répertoire spécifié")
            return {}
        
        print(f"\n🚀 DÉBUT ÉVALUATION DE {len(layout_names)} LAYOUTS")
        print("=" * 60)
        
        start_time = time.time()
        
        for i, layout_name in enumerate(layout_names, 1):
            print(f"\n[{i}/{len(layout_names)}] {layout_name}")
            layout_result = self.evaluate_single_layout(layout_name)
            self.results[layout_name] = layout_result
        
        total_time = time.time() - start_time
        
        # Générer un rapport de synthèse
        self.generate_summary_report(total_time)
        
        return self.results
    
    def generate_summary_report(self, total_evaluation_time: float):
        """Génère un rapport de synthèse des évaluations."""
        print(f"\n🏆 RAPPORT DE SYNTHÈSE")
        print("=" * 60)
        
        # Statistiques générales
        total_layouts = len(self.results)
        viable_layouts = [name for name, data in self.results.items() if data.get('viable', False)]
        failed_layouts = [name for name, data in self.results.items() if not data.get('viable', False)]
        
        print(f"📊 Layouts analysés: {total_layouts}")
        print(f"✅ Layouts viables: {len(viable_layouts)}")
        print(f"❌ Layouts échoués: {len(failed_layouts)}")
        print(f"⏱️ Temps total: {total_evaluation_time:.1f}s ({total_evaluation_time/60:.1f}min)")
        
        if failed_layouts:
            print(f"\n❌ Layouts échoués: {failed_layouts}")
        
        if viable_layouts:
            # Classement par temps de complétion
            completion_layouts = [(name, self.results[name]['primary_metric'], 
                                 self.results[name]['completion']['completion_rate']) 
                                for name in viable_layouts 
                                if 'primary_metric' in self.results[name]]
            
            if completion_layouts:
                completion_layouts.sort(key=lambda x: x[1])
                
                print(f"\n🏁 CLASSEMENT PAR TEMPS DE COMPLÉTION (OBJECTIF PRINCIPAL):")
                for i, (name, time_metric, completion_rate) in enumerate(completion_layouts, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                    method = self.results[name].get('evaluation_method', 'inconnue')
                    if time_metric < self.horizon:
                        print(f"   {medal} {name}: {time_metric:.0f} steps ({completion_rate*100:.0f}% réussite) [{method}]")
                    else:
                        print(f"   {medal} {name}: ÉCHEC ({completion_rate*100:.0f}% réussite) [{method}]")
        
        print(f"\n💡 Les évaluations marquées [structural_estimation] sont des estimations")
        print(f"   basées sur la structure du layout en cas d'échec de l'évaluation complète.")
    
    def save_results(self, filename: str = "layout_evaluation_results_simple.json"):
        """Sauvegarde les résultats dans un fichier JSON."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats sauvegardés dans {filename}")


def main():
    """Fonction principale pour lancer l'évaluation simplifiée."""
    print("🎮 ÉVALUATEUR SIMPLIFIÉ DE LAYOUTS OVERCOOKED")
    print("🧠 Expériences en sciences cognitives")
    print("=" * 50)
    
    # Configuration
    layouts_dir = "./overcooked_ai_py/data/layouts/generation_cesar/"
    
    # Vérifier que le répertoire existe
    if not os.path.exists(layouts_dir):
        print(f"❌ Répertoire {layouts_dir} non trouvé")
        return
    
    # Créer l'évaluateur
    evaluator = SimpleLayoutEvaluator(
        layouts_directory=layouts_dir,
        horizon=800,  # Horizon réduit pour éviter les timeouts
        num_games_per_layout=3  # Moins de parties pour plus de rapidité
    )
    
    # Lancer l'évaluation
    results = evaluator.evaluate_all_layouts()
    
    # Sauvegarder les résultats
    evaluator.save_results("layout_evaluation_results_simple.json")
    
    print(f"\n🎯 Évaluation terminée! {len(results)} layouts analysés.")
    print("💾 Résultats sauvegardés dans layout_evaluation_results_simple.json")


if __name__ == "__main__":
    main()
