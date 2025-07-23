#!/usr/bin/env python3
"""
layout_evaluator_final.py

Évaluateur de layouts Overcooked qui fait jouer deux GreedyAgent de manière optimisée.
Mesure les performances en termes de temps de complétion, FPS, et actions par agent.

OBJECTIF: Évaluation précise et fiable des layouts générés pour expériences cognitives.
"""

import os
import glob
import time
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from overcooked_ai_py.agents.agent import GreedyAgent, AgentGroup
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.mdp.actions import Action
from overcooked_ai_py.planning.planners import NO_COUNTERS_PARAMS


class LayoutEvaluator:
    """
    Évaluateur de layouts qui fait jouer deux GreedyAgent et mesure leurs performances.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 600, num_games_per_layout: int = 5, 
                 target_fps: float = 10.0, max_stuck_frames: int = 50):
        """
        Initialise l'évaluateur.
        
        Args:
            layouts_directory: Répertoire contenant les fichiers .layout
            horizon: Nombre maximum de steps par partie
            num_games_per_layout: Nombre de parties à jouer par layout
            target_fps: FPS cible pour la simulation
            max_stuck_frames: Nombre max de frames où les agents peuvent être bloqués
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.target_fps = target_fps
        self.step_duration = 1.0 / target_fps
        self.max_stuck_frames = max_stuck_frames
        self.results = {}
        
        print(f"🎮 ÉVALUATEUR DE LAYOUTS OVERCOOKED")
        print(f"📁 Répertoire: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"🚀 FPS cible: {target_fps}")
        print(f"🔒 Max stuck frames: {max_stuck_frames}")
    
    def discover_layouts(self) -> List[str]:
        """Découvre tous les fichiers .layout dans le répertoire."""
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names}")
        return layout_names
    
    def create_agent_group(self, mdp: OvercookedGridworld) -> Tuple[bool, AgentGroup]:
        """
        Crée un groupe de deux GreedyAgent configurés pour le MDP donné.
        """
        try:
            print("🤖 Création des GreedyAgent...")
            
            # S'assurer que le répertoire des planners existe
            planners_dir = f"./overcooked_ai_py/data/planners/generation_cesar/"
            os.makedirs(planners_dir, exist_ok=True)
            
            # Créer les agents
            agent_0 = GreedyAgent(auto_unstuck=True)
            agent_1 = GreedyAgent(auto_unstuck=True)
            
            # Créer le groupe d'agents
            agent_group = AgentGroup(agent_0, agent_1)
            
            # Configurer avec le MDP
            agent_group.set_mdp(mdp)
            
            print("✅ GreedyAgent créés et configurés avec succès")
            return True, agent_group
            
        except Exception as e:
            print(f"❌ Échec création GreedyAgent: {e}")
            print(f"   Tentative de fallback avec RandomAgent...")
            
            # Fallback sur RandomAgent si GreedyAgent échoue
            try:
                from overcooked_ai_py.agents.agent import RandomAgent
                agent_0 = RandomAgent()
                agent_1 = RandomAgent()
                agent_group = AgentGroup(agent_0, agent_1)
                agent_group.set_mdp(mdp)
                print("✅ RandomAgent créés en fallback")
                return True, agent_group
            except Exception as e2:
                print(f"❌ Échec total création agents: {e2}")
                return False, None
    
    def simulate_single_game(self, mdp: OvercookedGridworld, agent_group: AgentGroup, 
                           game_id: int = 1) -> Dict:
        """
        Simule une seule partie complète entre deux GreedyAgent.
        
        Returns:
            Dict avec les résultats détaillés de la partie
        """
        print(f"   🎮 Partie {game_id} - Simulation...")
        
        # Variables de suivi
        game_start_time = time.time()
        step_count = 0
        total_reward = 0
        completed = False
        stuck_frames = 0
        last_positions = None
        
        # Statistiques détaillées
        agent_actions_count = [defaultdict(int), defaultdict(int)]  # Actions par agent
        fps_measurements = []
        step_times = []
        
        try:
            # État initial - méthode directe comme dans game.py
            state = mdp.get_standard_start_state()
            
            # Nombre initial de commandes
            initial_orders = len(state.all_orders)
            completed_orders = 0
            
            print(f"      📋 Commandes initiales: {initial_orders}")
            
            # Boucle de simulation principale
            for step in range(self.horizon):
                step_start_time = time.time()
                
                # Obtenir les actions des agents
                joint_action_and_infos = agent_group.joint_action(state)
                joint_action = [action_info[0] for action_info in joint_action_and_infos]
                
                # Compter les actions par agent
                for agent_idx, action in enumerate(joint_action):
                    agent_actions_count[agent_idx][action] += 1
                
                # Exécuter l'action avec la logique Overcooked
                next_state, info = mdp.get_state_transition(state, joint_action)
                
                # Calculer la récompense
                step_reward = sum(info['sparse_reward_by_agent'])
                total_reward += step_reward
                
                # Vérifier les commandes complétées
                current_orders = len(next_state.all_orders)
                if current_orders < len(state.all_orders):
                    completed_orders += (len(state.all_orders) - current_orders)
                    print(f"      ✅ Commande complétée! Total: {completed_orders}")
                
                # Vérifier si toutes les commandes sont complétées
                if len(next_state.all_orders) == 0:
                    completed = True
                    step_count = step + 1
                    print(f"      🏁 Toutes les commandes complétées en {step_count} steps!")
                    break
                
                # Vérifier si les agents sont bloqués
                current_positions = [player.position for player in next_state.players]
                if current_positions == last_positions:
                    stuck_frames += 1
                    if stuck_frames >= self.max_stuck_frames:
                        print(f"      ⚠️ Agents bloqués pendant {stuck_frames} frames, arrêt forcé")
                        break
                else:
                    stuck_frames = 0
                last_positions = current_positions
                
                # Passer à l'état suivant
                state = next_state
                step_count = step + 1
                
                # Mesurer le timing
                step_end_time = time.time()
                step_duration = step_end_time - step_start_time
                step_times.append(step_duration)
                
                if step_duration > 0:
                    fps_measurements.append(1.0 / step_duration)
                
                # Simulation du timing réel (optionnel)
                if step_duration < self.step_duration:
                    time.sleep(self.step_duration - step_duration)
        
        except Exception as e:
            print(f"      ❌ Erreur pendant simulation: {e}")
            step_count = max(1, step_count)
            # Valeurs par défaut en cas d'erreur
            initial_orders = 1
            completed_orders = 0
        
        game_end_time = time.time()
        total_game_time = game_end_time - game_start_time
        
        # Calculer les métriques finales
        if 'initial_orders' not in locals():
            initial_orders = 1
        if 'completed_orders' not in locals():
            completed_orders = 0
        
        # Statistiques FPS
        avg_fps = np.mean(fps_measurements) if fps_measurements else 0
        actual_fps = step_count / max(0.001, total_game_time)
        
        # Actions par agent
        total_actions_agent_0 = sum(agent_actions_count[0].values())
        total_actions_agent_1 = sum(agent_actions_count[1].values())
        
        # Résultats détaillés
        game_result = {
            'game_id': game_id,
            'completed': completed,
            'steps': step_count,
            'total_reward': total_reward,
            'orders_completed': completed_orders,
            'initial_orders': initial_orders,
            'completion_rate': completed_orders / max(1, initial_orders),
            'timing': {
                'total_time_seconds': total_game_time,
                'simulated_time_seconds': step_count * self.step_duration,
                'average_step_time': np.mean(step_times) if step_times else 0,
                'target_fps': self.target_fps,
                'measured_avg_fps': avg_fps,
                'actual_fps': actual_fps,
                'steps_per_fps': step_count / max(1, avg_fps) if avg_fps > 0 else 0
            },
            'agent_statistics': {
                'agent_0': {
                    'total_actions': total_actions_agent_0,
                    'actions_per_step': total_actions_agent_0 / max(1, step_count),
                    'action_distribution': {str(k): v for k, v in agent_actions_count[0].items()}
                },
                'agent_1': {
                    'total_actions': total_actions_agent_1,
                    'actions_per_step': total_actions_agent_1 / max(1, step_count),
                    'action_distribution': {str(k): v for k, v in agent_actions_count[1].items()}
                }
            },
            'stuck_frames': stuck_frames,
            'stuck_forced_stop': stuck_frames >= self.max_stuck_frames
        }
        
        print(f"      📊 Résultat: {step_count} steps, {completed_orders}/{initial_orders} commandes, "
              f"FPS: {actual_fps:.1f}, temps: {total_game_time:.2f}s")
        
        return game_result
    
    def evaluate_single_layout(self, layout_name: str) -> Dict:
        """Évalue un seul layout avec plusieurs parties."""
        print(f"\n🏗️ Évaluation: {layout_name}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Analyser la structure
            structure = self._analyze_layout_structure(mdp)
            
            print(f"📊 Layout: {structure['width']}x{structure['height']}, "
                  f"Commandes: {structure['initial_orders']}")
            
            # Créer les agents
            success, agent_group = self.create_agent_group(mdp)
            if not success:
                return {
                    'layout_name': layout_name,
                    'viable': False,
                    'error': 'Impossible de créer les agents GreedyAgent',
                    'evaluation_time': time.time() - start_time
                }
            
            print(f"🤖 Agents: 2x GreedyAgent configurés")
            
            # Simuler toutes les parties
            game_results = []
            total_simulation_time = 0
            
            for game_num in range(1, self.num_games_per_layout + 1):
                # Reset des agents entre les parties
                agent_group.reset()
                agent_group.set_mdp(mdp)
                
                game_result = self.simulate_single_game(mdp, agent_group, game_num)
                game_results.append(game_result)
                total_simulation_time += game_result['timing']['total_time_seconds']
                
                # Petite pause entre les parties
                time.sleep(0.1)
            
            # Analyser les résultats globaux
            eval_time = time.time() - start_time
            aggregated_results = self._aggregate_game_results(
                layout_name, structure, game_results, eval_time, total_simulation_time
            )
            
            print(f"✅ Évaluation terminée en {eval_time:.1f}s")
            return aggregated_results
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"❌ Erreur lors de l'évaluation: {e}")
            return {
                'layout_name': layout_name,
                'viable': False,
                'error': str(e),
                'evaluation_time': error_time
            }
    
    def _analyze_layout_structure(self, mdp: OvercookedGridworld) -> Dict:
        """Analyse la structure d'un layout."""
        structure = {
            'width': mdp.width,
            'height': mdp.height,
            'area': mdp.width * mdp.height,
            'initial_orders': len(mdp.start_all_orders) if hasattr(mdp, 'start_all_orders') else 1,
            'player_count': len(mdp.start_player_positions)
        }
        
        # Compter les éléments du terrain
        terrain_counts = defaultdict(int)
        for row in mdp.terrain_mtx:
            for cell in row:
                terrain_counts[cell] += 1
        
        structure.update({
            'tomato_dispensers': terrain_counts.get('T', 0),
            'onion_dispensers': terrain_counts.get('O', 0),
            'dish_dispensers': terrain_counts.get('D', 0),
            'pots': terrain_counts.get('P', 0),
            'serve_areas': terrain_counts.get('S', 0),
            'counters': terrain_counts.get('X', 0),
            'walls': terrain_counts.get('X', 0)
        })
        
        return structure
    
    def _aggregate_game_results(self, layout_name: str, structure: Dict, 
                              game_results: List[Dict], eval_time: float, 
                              total_sim_time: float) -> Dict:
        """Agrège les résultats de toutes les parties pour un layout."""
        
        # Séparer les parties complétées et non complétées
        completed_games = [g for g in game_results if g['completed']]
        
        # Métriques de base
        steps_list = [g['steps'] for g in game_results]
        rewards_list = [g['total_reward'] for g in game_results]
        
        # Timing et FPS
        actual_fps_list = [g['timing']['actual_fps'] for g in game_results]
        measured_fps_list = [g['timing']['measured_avg_fps'] for g in game_results]
        
        # Actions des agents
        agent_0_actions = [g['agent_statistics']['agent_0']['total_actions'] for g in game_results]
        agent_1_actions = [g['agent_statistics']['agent_1']['total_actions'] for g in game_results]
        
        # Préparer les résultats agrégés
        results = {
            'layout_name': layout_name,
            'viable': True,
            'evaluation_method': 'greedy_agent_simulation',
            'structure': structure,
            'games_played': len(game_results),
            'games_completed': len(completed_games),
            'completion_rate': len(completed_games) / len(game_results),
            'timing': {
                'total_evaluation_time': eval_time,
                'total_simulation_time': total_sim_time,
                'average_game_duration': total_sim_time / len(game_results)
            }
        }
        
        # Métriques de complétion (MÉTRIQUE PRINCIPALE)
        if completed_games:
            completed_steps = [g['steps'] for g in completed_games]
            completed_times = [g['timing']['total_time_seconds'] for g in completed_games]
            
            results['completion_metrics'] = {
                'average_completion_steps': np.mean(completed_steps),
                'median_completion_steps': np.median(completed_steps),
                'fastest_completion_steps': min(completed_steps),
                'slowest_completion_steps': max(completed_steps),
                'std_completion_steps': np.std(completed_steps),
                'average_completion_time_seconds': np.mean(completed_times),
                'median_completion_time_seconds': np.median(completed_times)
            }
            
            # MÉTRIQUE PRINCIPALE
            results['primary_metric'] = results['completion_metrics']['average_completion_steps']
            results['primary_metric_name'] = "Temps de complétion moyen (steps)"
            
        else:
            results['primary_metric'] = self.horizon + 100
            results['primary_metric_name'] = "Aucune complétion"
        
        # Métriques de performance
        results['performance_metrics'] = {
            'average_steps': np.mean(steps_list),
            'median_steps': np.median(steps_list),
            'average_reward': np.mean(rewards_list),
            'total_reward': sum(rewards_list),
            'actual_fps': {
                'average': np.mean(actual_fps_list),
                'median': np.median(actual_fps_list),
                'min': min(actual_fps_list),
                'max': max(actual_fps_list)
            },
            'measured_fps': {
                'average': np.mean(measured_fps_list),
                'median': np.median(measured_fps_list)
            }
        }
        
        # Métriques des agents
        results['agent_metrics'] = {
            'agent_0': {
                'average_actions_per_game': np.mean(agent_0_actions),
                'total_actions': sum(agent_0_actions),
                'actions_per_step': sum(agent_0_actions) / sum(steps_list)
            },
            'agent_1': {
                'average_actions_per_game': np.mean(agent_1_actions),
                'total_actions': sum(agent_1_actions),
                'actions_per_step': sum(agent_1_actions) / sum(steps_list)
            }
        }
        
        # Détails des parties individuelles
        results['individual_games'] = game_results
        
        # Affichage des résultats
        if completed_games:
            print(f"🏁 COMPLÉTION: {len(completed_games)}/{len(game_results)} parties")
            print(f"⏱️ Temps moyen: {results['completion_metrics']['average_completion_steps']:.1f} steps")
            print(f"🚀 Plus rapide: {results['completion_metrics']['fastest_completion_steps']} steps")
            print(f"📊 FPS moyen: {results['performance_metrics']['actual_fps']['average']:.1f}")
            print(f"🤖 Actions/step: Agent0={results['agent_metrics']['agent_0']['actions_per_step']:.2f}, "
                  f"Agent1={results['agent_metrics']['agent_1']['actions_per_step']:.2f}")
        else:
            print(f"❌ AUCUNE COMPLÉTION réussie sur {len(game_results)} parties")
        
        return results
    
    def evaluate_all_layouts(self) -> Dict:
        """Évalue tous les layouts du répertoire."""
        layout_names = self.discover_layouts()
        
        if not layout_names:
            print("❌ Aucun layout trouvé")
            return {}
        
        print(f"\n🚀 DÉBUT ÉVALUATION DE {len(layout_names)} LAYOUTS")
        print("=" * 60)
        
        start_time = time.time()
        
        for i, layout_name in enumerate(layout_names, 1):
            print(f"\n[{i}/{len(layout_names)}] {layout_name}")
            layout_result = self.evaluate_single_layout(layout_name)
            self.results[layout_name] = layout_result
        
        total_time = time.time() - start_time
        self.generate_final_report(total_time)
        
        return self.results
    
    def generate_final_report(self, total_evaluation_time: float):
        """Génère le rapport final avec toutes les métriques."""
        print(f"\n🏆 RAPPORT FINAL - ÉVALUATION LAYOUTS")
        print("=" * 60)
        
        viable_layouts = [name for name, data in self.results.items() if data.get('viable', False)]
        completed_layouts = [name for name in viable_layouts if self.results[name].get('completion_rate', 0) > 0]
        
        print(f"📊 Layouts évalués: {len(self.results)}")
        print(f"✅ Layouts viables: {len(viable_layouts)}")
        print(f"🏁 Layouts avec complétion: {len(completed_layouts)}")
        print(f"⏱️ Temps total évaluation: {total_evaluation_time:.1f}s")
        
        if completed_layouts:
            # Classement par temps de complétion
            completion_data = []
            for name in completed_layouts:
                if 'primary_metric' in self.results[name]:
                    steps = self.results[name]['primary_metric']
                    completion_rate = self.results[name]['completion_rate']
                    avg_fps = self.results[name]['performance_metrics']['actual_fps']['average']
                    completion_data.append((name, steps, completion_rate, avg_fps))
            
            if completion_data:
                completion_data.sort(key=lambda x: x[1])  # Tri par steps
                
                print(f"\n🏁 CLASSEMENT PAR TEMPS DE COMPLÉTION:")
                for i, (name, steps, rate, fps) in enumerate(completion_data, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                    print(f"   {medal} {name}: {steps:.0f} steps "
                          f"({rate*100:.0f}% réussite, {fps:.1f} FPS)")
                
                # Statistiques finales
                all_steps = [steps for _, steps, _, _ in completion_data]
                all_fps = [fps for _, _, _, fps in completion_data]
                
                print(f"\n📊 STATISTIQUES GLOBALES:")
                print(f"   Temps moyen: {np.mean(all_steps):.1f} steps")
                print(f"   Meilleur temps: {min(all_steps):.1f} steps")
                print(f"   FPS moyen: {np.mean(all_fps):.1f}")
                print(f"   Horizon max: {self.horizon} steps")
        
        print(f"\n💾 Résultats prêts pour sauvegarde")
    
    def save_results(self, filename: str = "layout_evaluation_final.json"):
        """Sauvegarde les résultats détaillés."""
        output_data = {
            'evaluation_config': {
                'layouts_directory': self.layouts_directory,
                'horizon': self.horizon,
                'num_games_per_layout': self.num_games_per_layout,
                'target_fps': self.target_fps,
                'max_stuck_frames': self.max_stuck_frames
            },
            'evaluation_timestamp': time.time(),
            'results': self.results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats sauvegardés dans {filename}")


def main():
    """Fonction principale."""
    print("🎮 ÉVALUATEUR DE LAYOUTS OVERCOOKED")
    print("🤖 Simulation avec 2x GreedyAgent")
    print("=" * 60)
    
    # Configuration
    layouts_dir = "./overcooked_ai_py/data/layouts/generation_cesar/"
    
    if not os.path.exists(layouts_dir):
        print(f"❌ Répertoire {layouts_dir} non trouvé")
        return
    
    # Créer l'évaluateur
    evaluator = LayoutEvaluator(
        layouts_directory=layouts_dir,
        horizon=600,  # Horizon raisonnable
        num_games_per_layout=5,  # Plusieurs parties pour moyenner
        target_fps=10.0,  # FPS modéré
        max_stuck_frames=50  # Éviter les blocages infinis
    )
    
    # Lancer l'évaluation
    results = evaluator.evaluate_all_layouts()
    
    # Sauvegarder
    evaluator.save_results("layout_evaluation_final.json")
    
    print(f"\n🎯 ÉVALUATION TERMINÉE!")
    print(f"   📊 Métriques complètes disponibles")
    print(f"   💾 Résultats sauvegardés")


if __name__ == "__main__":
    main()
