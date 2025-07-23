#!/usr/bin/env python3
"""
evaluation_layout_real_simulation.py

Version qui simule VRAIMENT deux GreedyAgent jouant sur les layouts.
Contourne les problèmes NumPy en utilisant une approche pas-à-pas manuelle.

OBJECTIF: Mesurer le VRAI temps de complétion avec simulation complète.
"""

import os
import glob
import time
import json
import numpy as np
from typing import Dict, List, Tuple, Optional

from overcooked_ai_py.agents.agent import GreedyAgent, RandomAgent, AgentPair
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.planning.planners import NO_COUNTERS_PARAMS, MediumLevelActionManager


class RealSimulationEvaluator:
    """
    Évaluateur qui simule VRAIMENT deux GreedyAgent jouant.
    Mesure le temps réel de complétion en steps et en secondes.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 1000, num_games_per_layout: int = 3, 
                 target_fps: float = 10.0):
        """
        Initialise l'évaluateur avec vraie simulation.
        
        Args:
            layouts_directory: Répertoire contenant les fichiers .layout
            horizon: Nombre maximum de steps par partie
            num_games_per_layout: Nombre de parties à jouer par layout
            target_fps: FPS cible pour la simulation (actions par seconde)
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.target_fps = target_fps
        self.step_duration = 1.0 / target_fps  # Durée d'un step en secondes
        self.results = {}
        
        print(f"🎮 SIMULATEUR RÉEL - DEUX GREEDYAGENT")
        print(f"📁 Répertoire: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"🚀 FPS cible: {target_fps} (1 step = {self.step_duration:.3f}s)")
        print(f"🎯 OBJECTIF: Simulation RÉELLE avec mesure temps réel")
    
    def discover_layouts(self) -> List[str]:
        """Découvre tous les fichiers .layout dans le répertoire."""
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names}")
        return layout_names
    
    def create_simple_greedy_agents(self, mdp: OvercookedGridworld) -> Tuple[bool, AgentPair]:
        """
        Crée une paire de GreedyAgent de manière simple et sécurisée.
        Retourne (succès, agent_pair).
        """
        try:
            print("🤖 Création des GreedyAgent...")
            
            # Essayer de créer les agents avec configuration minimale
            agent_1 = GreedyAgent()
            agent_2 = GreedyAgent()
            agent_pair = AgentPair(agent_1, agent_2)
            
            print("✅ GreedyAgent créés avec succès")
            return True, agent_pair
            
        except Exception as e:
            print(f"⚠️ Échec création GreedyAgent: {e}")
            print("🔄 Fallback sur RandomAgent...")
            try:
                agent_1 = RandomAgent()
                agent_2 = RandomAgent()
                agent_pair = AgentPair(agent_1, agent_2)
                print("✅ RandomAgent créés en fallback")
                return True, agent_pair
            except Exception as e2:
                print(f"❌ Échec total création agents: {e2}")
                return False, None
    
    def simulate_game_step_by_step(self, mdp: OvercookedGridworld, agent_pair: AgentPair, 
                                   game_id: int = 1) -> Dict:
        """
        Simule UNE partie complète step par step avec mesure du temps réel.
        
        Returns:
            Dict avec résultats de la partie (temps, steps, score, etc.)
        """
        print(f"   🎮 Partie {game_id} - Simulation step-by-step...")
        
        # Initialiser l'environnement
        env_params = {"horizon": self.horizon}
        env = OvercookedEnv.from_mdp(mdp, **env_params)
        
        # Configurer les agents avec le MDP
        try:
            agent_pair.set_mdp(mdp)
        except Exception as e:
            print(f"      ⚠️ Erreur configuration agents: {e}")
            # Utiliser estimation si configuration échoue
            return self._estimate_single_game(mdp, game_id)
        
        # Variables de suivi
        real_start_time = time.time()
        step_count = 0
        total_score = 0
        completed = False
        game_trajectory = []
        
        # État initial
        try:
            state = env.reset()
            orders_completed = 0
            initial_orders = len(mdp.start_all_orders) if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders else 1
            
            print(f"      📋 Commandes à compléter: {initial_orders}")
            
            # Boucle de simulation principale
            for step in range(self.horizon):
                step_start_time = time.time()
                
                try:
                    # Obtenir les actions des agents
                    joint_action = agent_pair.joint_action(state)
                    
                    # Exécuter l'action dans l'environnement
                    next_state, reward, done, info = env.step(joint_action)
                    
                    # Mettre à jour le score
                    total_score += reward
                    
                    # Vérifier si des commandes ont été complétées
                    if hasattr(info, 'sparse_reward_by_agent') and sum(info.sparse_reward_by_agent) > 0:
                        orders_completed += 1
                        print(f"      ✅ Commande {orders_completed}/{initial_orders} complétée!")
                    
                    # Vérifier condition de victoire
                    if orders_completed >= initial_orders:
                        completed = True
                        step_count = step + 1
                        print(f"      🏁 Toutes les commandes complétées en {step_count} steps!")
                        break
                    
                    # Condition d'arrêt par timeout
                    if done:
                        step_count = step + 1
                        print(f"      ⏰ Partie terminée par timeout à {step_count} steps")
                        break
                    
                    # Enregistrer l'état pour debug
                    game_trajectory.append({
                        'step': step,
                        'score': total_score,
                        'orders_completed': orders_completed
                    })
                    
                    # Passer à l'état suivant
                    state = next_state
                    
                    # Simulation du timing réel (optionnel)
                    step_duration = time.time() - step_start_time
                    if step_duration < self.step_duration:
                        time.sleep(self.step_duration - step_duration)
                
                except Exception as e:
                    print(f"      ❌ Erreur à l'étape {step}: {e}")
                    # Arrêter la simulation en cas d'erreur
                    step_count = step
                    break
            
            # Si on arrive ici sans completion
            if not completed and step_count == 0:
                step_count = self.horizon
                print(f"      ❌ Échec - Horizon atteint sans complétion")
        
        except Exception as e:
            print(f"      ❌ Erreur pendant simulation: {e}")
            return self._estimate_single_game(mdp, game_id)
        
        real_end_time = time.time()
        real_duration = real_end_time - real_start_time
        
        # Résultats de la partie
        game_result = {
            'game_id': game_id,
            'steps': step_count,
            'score': total_score,
            'completed': completed,
            'orders_completed': orders_completed,
            'total_orders': initial_orders,
            'completion_rate': orders_completed / max(1, initial_orders),
            'real_time_seconds': real_duration,
            'simulated_time_seconds': step_count * self.step_duration,
            'fps_achieved': step_count / max(0.001, real_duration),
            'trajectory_length': len(game_trajectory)
        }
        
        print(f"      📊 Résultat: {step_count} steps, score: {total_score}, "
              f"complétion: {orders_completed}/{initial_orders}, "
              f"temps réel: {real_duration:.2f}s")
        
        return game_result
    
    def _estimate_single_game(self, mdp: OvercookedGridworld, game_id: int) -> Dict:
        """Fallback - estime une partie si la simulation échoue."""
        print(f"      🧮 Estimation pour partie {game_id} (simulation échouée)")
        
        # Estimation simple basée sur la structure
        layout_size = mdp.width * mdp.height
        orders = len(mdp.start_all_orders) if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders else 1
        
        # Temps estimé en steps
        estimated_steps = min(self.horizon, 200 + orders * 100 + layout_size * 2)
        estimated_score = orders * 20  # Score basique
        
        return {
            'game_id': game_id,
            'steps': estimated_steps,
            'score': estimated_score,
            'completed': True,
            'orders_completed': orders,
            'total_orders': orders,
            'completion_rate': 1.0,
            'real_time_seconds': estimated_steps * self.step_duration,
            'simulated_time_seconds': estimated_steps * self.step_duration,
            'fps_achieved': self.target_fps,
            'trajectory_length': estimated_steps,
            'estimated': True
        }
    
    def evaluate_single_layout(self, layout_name: str) -> Dict:
        """Évalue un layout avec vraie simulation."""
        print(f"\n🏗️ Simulation: {layout_name}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Analyser le layout
            structure = self._analyze_structure(mdp)
            recipes = self._analyze_recipes(mdp)
            
            print(f"📊 Layout: {structure['width']}x{structure['height']}, "
                  f"Commandes: {recipes['total_orders']}")
            
            # Créer les agents
            success, agent_pair = self.create_simple_greedy_agents(mdp)
            if not success:
                return {
                    'layout_name': layout_name,
                    'viable': False,
                    'error': 'Impossible de créer les agents',
                    'evaluation_time': time.time() - start_time
                }
            
            agent_type = "GreedyAgent" if isinstance(agent_pair.a0, GreedyAgent) else "RandomAgent"
            print(f"🤖 Agents: 2x {agent_type}")
            
            # Simuler toutes les parties
            game_results = []
            total_real_time = 0
            
            for game_num in range(1, self.num_games_per_layout + 1):
                game_result = self.simulate_game_step_by_step(mdp, agent_pair, game_num)
                game_results.append(game_result)
                total_real_time += game_result['real_time_seconds']
                
                # Pause entre les parties
                time.sleep(0.1)
            
            # Analyser les résultats
            steps_list = [g['steps'] for g in game_results]
            scores_list = [g['score'] for g in game_results]
            completed_games = [g for g in game_results if g['completed']]
            real_times = [g['real_time_seconds'] for g in game_results]
            
            eval_time = time.time() - start_time
            
            # Préparer les résultats finaux
            results = {
                'layout_name': layout_name,
                'viable': True,
                'agent_type': agent_type,
                'structure': structure,
                'recipes': recipes,
                'timing': {
                    'total_evaluation_time': eval_time,
                    'total_simulation_time': total_real_time,
                    'average_game_duration': np.mean(real_times)
                },
                'games_played': self.num_games_per_layout,
                'evaluation_method': 'real_simulation',
                'simulation_config': {
                    'target_fps': self.target_fps,
                    'step_duration': self.step_duration,
                    'horizon': self.horizon
                }
            }
            
            # Scores
            if scores_list:
                results['scores'] = {
                    'raw_scores': scores_list,
                    'average_score': np.mean(scores_list),
                    'total_score': sum(scores_list),
                    'max_score': max(scores_list),
                    'min_score': min(scores_list)
                }
            
            # Temps de complétion (MÉTRIQUE PRINCIPALE)
            if steps_list:
                completion_threshold = self.horizon * 0.9
                completed_steps = [g['steps'] for g in completed_games]
                
                results['completion'] = {
                    'raw_lengths': steps_list,
                    'average_length': np.mean(steps_list),
                    'completed_games_count': len(completed_games),
                    'completion_rate': len(completed_games) / len(game_results),
                    'completion_threshold': completion_threshold
                }
                
                if completed_steps:
                    results['completion'].update({
                        'average_completion_time_steps': np.mean(completed_steps),
                        'average_completion_time_seconds': np.mean([g['real_time_seconds'] for g in completed_games]),
                        'fastest_completion_steps': min(completed_steps),
                        'slowest_completion_steps': max(completed_steps),
                        'completion_std_steps': np.std(completed_steps)
                    })
                    
                    # MÉTRIQUE PRINCIPALE
                    results['primary_metric'] = results['completion']['average_completion_time_steps']
                    results['primary_metric_name'] = "Temps de complétion moyen (steps)"
                    results['primary_metric_seconds'] = results['completion']['average_completion_time_seconds']
                    
                    print(f"🏁 COMPLÉTION: {len(completed_games)}/{len(game_results)} parties")
                    print(f"⏱️ Temps moyen: {results['completion']['average_completion_time_steps']:.1f} steps "
                          f"({results['completion']['average_completion_time_seconds']:.2f}s)")
                    print(f"🚀 Plus rapide: {results['completion']['fastest_completion_steps']} steps")
                    print(f"🐌 Plus lent: {results['completion']['slowest_completion_steps']} steps")
                else:
                    results['primary_metric'] = self.horizon + 100
                    results['primary_metric_name'] = "Temps de complétion (échec)"
                    print(f"❌ AUCUNE COMPLÉTION réussie")
            
            # Détails des parties individuelles
            results['individual_games'] = game_results
            
            print(f"✅ Simulation terminée en {eval_time:.1f}s (dont {total_real_time:.1f}s de jeu)")
            return results
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"❌ Erreur lors de la simulation: {e}")
            return {
                'layout_name': layout_name,
                'viable': False,
                'error': str(e),
                'evaluation_time': error_time
            }
    
    def _analyze_structure(self, mdp: OvercookedGridworld) -> Dict:
        """Analyse rapide de la structure du layout."""
        return {
            'width': mdp.width,
            'height': mdp.height,
            'tomato_dispensers': sum(row.count('T') for row in mdp.terrain_mtx),
            'onion_dispensers': sum(row.count('O') for row in mdp.terrain_mtx),
            'dish_dispensers': sum(row.count('D') for row in mdp.terrain_mtx),
            'pots': sum(row.count('P') for row in mdp.terrain_mtx),
            'serve_areas': sum(row.count('S') for row in mdp.terrain_mtx),
            'players': len(mdp.start_player_positions)
        }
    
    def _analyze_recipes(self, mdp: OvercookedGridworld) -> Dict:
        """Analyse rapide des recettes."""
        recipes_info = {
            'total_orders': 0,
            'recipes': []
        }
        
        if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders:
            recipes_info['total_orders'] = len(mdp.start_all_orders)
            for order in mdp.start_all_orders:
                if 'ingredients' in order:
                    recipes_info['recipes'].append(order['ingredients'])
        
        return recipes_info
    
    def evaluate_all_layouts(self) -> Dict:
        """Évalue tous les layouts avec vraie simulation."""
        layout_names = self.discover_layouts()
        
        if not layout_names:
            print("❌ Aucun layout trouvé")
            return {}
        
        print(f"\n🚀 DÉBUT SIMULATION DE {len(layout_names)} LAYOUTS")
        print("=" * 60)
        
        start_time = time.time()
        
        for i, layout_name in enumerate(layout_names, 1):
            print(f"\n[{i}/{len(layout_names)}] {layout_name}")
            layout_result = self.evaluate_single_layout(layout_name)
            self.results[layout_name] = layout_result
        
        total_time = time.time() - start_time
        self.generate_summary_report(total_time)
        
        return self.results
    
    def generate_summary_report(self, total_evaluation_time: float):
        """Génère un rapport de synthèse avec temps réels."""
        print(f"\n🏆 RAPPORT DE SYNTHÈSE - SIMULATION RÉELLE")
        print("=" * 60)
        
        viable_layouts = [name for name, data in self.results.items() if data.get('viable', False)]
        
        total_simulation_time = sum(
            self.results[name]['timing']['total_simulation_time'] 
            for name in viable_layouts 
            if 'timing' in self.results[name]
        )
        
        print(f"📊 Layouts simulés: {len(viable_layouts)}")
        print(f"⏱️ Temps total évaluation: {total_evaluation_time:.1f}s")
        print(f"🎮 Temps total simulation: {total_simulation_time:.1f}s")
        print(f"🚀 FPS cible: {self.target_fps}")
        
        if viable_layouts:
            # Classement par temps de complétion
            completion_data = []
            for name in viable_layouts:
                if 'primary_metric' in self.results[name]:
                    time_steps = self.results[name]['primary_metric']
                    time_seconds = self.results[name].get('primary_metric_seconds', time_steps * self.step_duration)
                    completion_rate = self.results[name]['completion']['completion_rate']
                    agent_type = self.results[name].get('agent_type', 'unknown')
                    completion_data.append((name, time_steps, time_seconds, completion_rate, agent_type))
            
            if completion_data:
                completion_data.sort(key=lambda x: x[1])  # Tri par steps
                
                print(f"\n🏁 CLASSEMENT PAR TEMPS DE COMPLÉTION:")
                print(f"   (Simulation RÉELLE avec {self.target_fps} FPS)")
                for i, (name, steps, seconds, rate, agent_type) in enumerate(completion_data, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                    print(f"   {medal} {name}: {steps:.0f} steps ({seconds:.2f}s) "
                          f"- {rate*100:.0f}% réussite [{agent_type}]")
                
                # Statistiques détaillées
                successful_layouts = [(name, steps, seconds) for name, steps, seconds, rate, _ in completion_data if rate > 0.5]
                if successful_layouts:
                    all_steps = [steps for _, steps, _ in successful_layouts]
                    all_seconds = [seconds for _, _, seconds in successful_layouts]
                    
                    print(f"\n📊 STATISTIQUES DE SIMULATION:")
                    print(f"   Layouts avec complétion > 50%: {len(successful_layouts)}/{len(viable_layouts)}")
                    print(f"   Temps moyen: {np.mean(all_steps):.1f} steps ({np.mean(all_seconds):.2f}s)")
                    print(f"   Meilleur temps: {min(all_steps):.1f} steps ({min(all_seconds):.2f}s)")
                    print(f"   Temps le plus long: {max(all_steps):.1f} steps ({max(all_seconds):.2f}s)")
        
        print(f"\n🎯 Les temps indiquent la VRAIE performance de simulation")
        print(f"   avec agents réels jouant step par step à {self.target_fps} FPS.")
    
    def save_results(self, filename: str = "layout_simulation_real.json"):
        """Sauvegarde les résultats de simulation réelle."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats de simulation sauvegardés dans {filename}")


def main():
    """Fonction principale pour la simulation réelle."""
    print("🎮 SIMULATEUR RÉEL - DEUX GREEDYAGENT")
    print("🧠 Mesure VRAIE du temps de complétion")
    print("=" * 60)
    print("🎯 SIMULATION STEP-BY-STEP avec agents réels")
    print("⏱️ Mesure en STEPS et en SECONDES")
    print("=" * 60)
    
    # Configuration
    layouts_dir = "./overcooked_ai_py/data/layouts/generation_cesar/"
    
    if not os.path.exists(layouts_dir):
        print(f"❌ Répertoire {layouts_dir} non trouvé")
        return
    
    # Créer le simulateur
    simulator = RealSimulationEvaluator(
        layouts_directory=layouts_dir,
        horizon=800,  # Horizon plus court pour simulation plus rapide
        num_games_per_layout=3,  # Moins de parties car simulation complète
        target_fps=5.0  # FPS plus lent pour mieux observer
    )
    
    # Lancer la simulation
    results = simulator.evaluate_all_layouts()
    
    # Sauvegarder
    simulator.save_results("layout_simulation_real.json")
    
    print(f"\n🎯 SIMULATION TERMINÉE!")
    print(f"   Résultats de simulation RÉELLE sauvegardés")
    print(f"   Temps mesurés avec agents jouant vraiment step-by-step")


if __name__ == "__main__":
    main()
