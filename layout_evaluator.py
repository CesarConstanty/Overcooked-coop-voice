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
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from overcooked_ai_py.agents.agent import GreedyAgent, AgentGroup
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.mdp.actions import Action
from overcooked_ai_py.planning.planners import NO_COUNTERS_PARAMS


class StayAgent:
    """Agent qui reste immobile (ne fait que STAY) pour les tests."""
    
    def __init__(self):
        self.agent_index = None
        self.mdp = None
    
    def action(self, state):
        """Retourne toujours l'action STAY."""
        return Action.STAY, {}
    
    def set_agent_index(self, agent_index):
        self.agent_index = agent_index
    
    def set_mdp(self, mdp):
        self.mdp = mdp
    
    def reset(self):
        pass


class LayoutEvaluator:
    """
    Évaluateur de layouts qui fait jouer deux GreedyAgent et mesure leurs performances.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 600, num_games_per_layout: int = 5, 
                 target_fps: float = 10.0, max_stuck_frames: int = 50, 
                 single_agent: bool = False, greedy_with_stay: bool = False,
                 parallel_games: bool = False, max_workers: int = None):
        """
        Initialise l'évaluateur.
        
        Args:
            layouts_directory: Répertoire contenant les fichiers .layout
            horizon: Nombre maximum de steps par partie
            num_games_per_layout: Nombre de parties à jouer par layout
            target_fps: FPS cible pour la simulation (ignoré si parallel_games=True)
            max_stuck_frames: Nombre max de frames où les agents peuvent être bloqués
            single_agent: Si True, fait jouer un seul GreedyAgent (mode solo pur)
            greedy_with_stay: Si True, fait jouer un GreedyAgent + un StayAgent
            parallel_games: Si True, exécute les parties en parallèle
            max_workers: Nombre max de processus parallèles (None = auto)
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.target_fps = target_fps
        self.step_duration = 1.0 / target_fps if not parallel_games else 0
        self.max_stuck_frames = max_stuck_frames
        self.single_agent = single_agent
        self.greedy_with_stay = greedy_with_stay
        self.parallel_games = parallel_games
        self.max_workers = max_workers or min(num_games_per_layout, os.cpu_count() or 1)
        self.results = {}
        
        # Déterminer le mode
        if single_agent:
            agent_mode = "1x GreedyAgent (SOLO PUR)"
        elif greedy_with_stay:
            agent_mode = "GreedyAgent + StayAgent"
        else:
            agent_mode = "2x GreedyAgent (COOP)"
            
        parallel_info = f" [PARALLÈLE: {self.max_workers} workers]" if parallel_games else ""
        speed_info = f"🚀 FPS cible: {target_fps}" if not parallel_games else "🚀 Mode: Parallèle (FPS max)"
            
        print(f"🎮 ÉVALUATEUR DE LAYOUTS OVERCOOKED")
        print(f"🤖 Mode: {agent_mode}{parallel_info}")
        print(f"📁 Répertoire: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"{speed_info}")
        print(f"🔒 Max stuck frames: {max_stuck_frames}")
    
    def discover_layouts(self) -> List[str]:
        """Découvre tous les fichiers .layout dans le répertoire."""
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names}")
        return layout_names
    
    def create_agent_group(self, mdp: OvercookedGridworld) -> Tuple[bool, object]:
        """
        Crée un agent ou groupe d'agents GreedyAgent configurés pour le MDP donné.
        Returns (success, agent_or_group)
        """
        try:
            # Déterminer le type d'agents à créer
            if self.single_agent:
                agent_desc = "1x GreedyAgent (solo pur)"
            elif self.greedy_with_stay:
                agent_desc = "GreedyAgent + StayAgent"
            else:
                agent_desc = "2x GreedyAgent (coop)"
                
            print(f"🤖 Création: {agent_desc}...")
            
            # S'assurer que le répertoire des planners existe
            planners_dir = f"./overcooked_ai_py/data/planners/generation_cesar/"
            os.makedirs(planners_dir, exist_ok=True)
            
            if self.single_agent:
                # Mode agent seul : un seul GreedyAgent
                agent = GreedyAgent(auto_unstuck=True)
                agent.set_mdp(mdp)
                agent.set_agent_index(0)  # Toujours le premier joueur
                
                print("✅ GreedyAgent (solo pur) créé avec succès")
                return True, agent
                
            elif self.greedy_with_stay:
                # Mode GreedyAgent + StayAgent
                agent_0 = GreedyAgent(auto_unstuck=True)
                agent_1 = StayAgent()
                
                # Créer le groupe d'agents
                agent_group = AgentGroup(agent_0, agent_1)
                agent_group.set_mdp(mdp)
                
                print("✅ GreedyAgent + StayAgent créés avec succès")
                return True, agent_group
                
            else:
                # Mode coopératif : deux GreedyAgent
                agent_0 = GreedyAgent(auto_unstuck=True)
                agent_1 = GreedyAgent(auto_unstuck=True)
                
                # Créer le groupe d'agents
                agent_group = AgentGroup(agent_0, agent_1)
                agent_group.set_mdp(mdp)
                
                print("✅ 2x GreedyAgent (coop) créés avec succès")
                return True, agent_group
            
        except Exception as e:
            print(f"❌ Échec création agents: {e}")
            print(f"   Tentative de fallback avec RandomAgent...")
            
            # Fallback sur RandomAgent si GreedyAgent échoue
            try:
                from overcooked_ai_py.agents.agent import RandomAgent
                
                if self.single_agent:
                    agent = RandomAgent()
                    agent.set_mdp(mdp)
                    agent.set_agent_index(0)
                    print("✅ RandomAgent (solo) créé en fallback")
                    return True, agent
                    
                elif self.greedy_with_stay:
                    agent_0 = RandomAgent()
                    agent_1 = StayAgent()
                    agent_group = AgentGroup(agent_0, agent_1)
                    agent_group.set_mdp(mdp)
                    print("✅ RandomAgent + StayAgent créés en fallback")
                    return True, agent_group
                    
                else:
                    agent_0 = RandomAgent()
                    agent_1 = RandomAgent()
                    agent_group = AgentGroup(agent_0, agent_1)
                    agent_group.set_mdp(mdp)
                    print("✅ 2x RandomAgent créés en fallback")
                    return True, agent_group
                    
            except Exception as e2:
                print(f"❌ Échec total création agents: {e2}")
                return False, None
    
    def simulate_single_game(self, mdp: OvercookedGridworld, agent_or_group: object, 
                           game_id: int = 1) -> Dict:
        """
        Simule une seule partie complète avec un GreedyAgent seul ou deux GreedyAgent.
        
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
        
        # Métriques comportementales détaillées (inspirées de game.py)
        event_infos_history = []
        trajectory = []  # Pour stocker la trajectoire complète
        behavioral_metrics = {
            'interactions_count': [0, 0],  # Nombre d'interactions par agent
            'stuck_loops': [0, 0],         # Nombre de fois bloqué par agent
            'movement_efficiency': [0, 0],  # Efficacité de mouvement
            'total_distance_traveled': [0, 0], # Distance totale parcourue
            'task_completion_order': [],    # Ordre de complétion des tâches
            'collaboration_events': 0,      # Événements de collaboration
        }
        
        try:
            # État initial - adapté selon le mode
            state = mdp.get_standard_start_state()
            
            # Stocker une référence au MDP pour les corrections de bugs
            self._current_mdp = mdp
            
            if self.single_agent:
                print(f"      🤖 Mode SOLO: Joueur 0 actif en {state.players[0].position}, Joueur 1 inactif en {state.players[1].position}")
            else:
                print(f"      🤖 Mode NORMAL: Joueurs en {[p.position for p in state.players]}")
            
            # Nombre initial de commandes
            initial_orders = len(state.all_orders)
            completed_orders = 0
            
            print(f"      📋 Commandes initiales: {initial_orders}")
            
            # Boucle de simulation principale
            for step in range(self.horizon):
                step_start_time = time.time()
                
                # Obtenir les actions selon le mode
                if self.single_agent:
                    # Mode agent seul : une action pour le joueur 0, STAY pour le joueur 1 (hors carte)
                    action_0, _ = agent_or_group.action(state)
                    joint_action = [action_0, Action.STAY]  # Le joueur 1 reste toujours STAY
                    
                    # Compter les actions (seul l'agent 0 agit vraiment)
                    agent_actions_count[0][action_0] += 1
                    agent_actions_count[1][Action.STAY] += 1
                    
                elif self.greedy_with_stay:
                    # Mode GreedyAgent + StayAgent : utiliser AgentGroup
                    joint_action_and_infos = agent_or_group.joint_action(state)
                    joint_action = [action_info[0] for action_info in joint_action_and_infos]
                    
                    # Compter les actions des deux agents
                    for agent_idx, action in enumerate(joint_action):
                        agent_actions_count[agent_idx][action] += 1
                else:
                    # Mode coopératif : deux agents actifs
                    joint_action_and_infos = agent_or_group.joint_action(state)
                    joint_action = [action_info[0] for action_info in joint_action_and_infos]
                    
                    # Compter les actions des deux agents
                    for agent_idx, action in enumerate(joint_action):
                        agent_actions_count[agent_idx][action] += 1
                
                # Exécuter l'action avec la logique Overcooked
                next_state, info = mdp.get_state_transition(state, joint_action)
                
                # Collecter les métriques comportementales
                event_infos = info.get('event_infos', {})
                
                # CORRECTION BUG OVERCOOKED AI: Les pickups de tomates ne sont pas loggés
                # Nous devons détecter manuellement quand un agent ramasse une tomate
                self._fix_missing_tomato_pickup_events(event_infos, state, next_state)
                
                event_infos_history.append(event_infos)
                
                # Analyser les interactions
                for agent_idx, action in enumerate(joint_action):
                    if action == Action.INTERACT:
                        behavioral_metrics['interactions_count'][agent_idx] += 1
                    
                    # Calculer la distance parcourue
                    if step > 0:  # Pas de calcul au premier step
                        prev_pos = state.players[agent_idx].position
                        new_pos = next_state.players[agent_idx].position
                        distance = abs(new_pos[0] - prev_pos[0]) + abs(new_pos[1] - prev_pos[1])
                        behavioral_metrics['total_distance_traveled'][agent_idx] += distance
                
                # Détecter les événements de collaboration (transferts d'objets)
                for event_type in ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange']:
                    if event_type in event_infos:
                        if any(event_infos[event_type]):
                            behavioral_metrics['collaboration_events'] += 1
                
                # Calculer la récompense
                step_reward = sum(info['sparse_reward_by_agent'])
                total_reward += step_reward
                
                # Vérifier les commandes complétées
                current_orders = len(next_state.all_orders)
                if current_orders < len(state.all_orders):
                    orders_just_completed = len(state.all_orders) - current_orders
                    completed_orders += orders_just_completed
                    print(f"      ✅ {orders_just_completed} commande(s) complétée(s)! Total: {completed_orders}")
                
                # Vérifier si toutes les commandes sont complétées
                if len(next_state.all_orders) == 0:
                    completed = True
                    step_count = step + 1
                    print(f"      🏁 Toutes les commandes complétées en {step_count} steps!")
                    break
                
                # Vérifier si les agents sont bloqués
                if self.single_agent:
                    # Mode solo : vérifier seulement le joueur 0 (le joueur 1 est hors carte)
                    current_positions = [next_state.players[0].position]
                else:
                    # Mode normal : vérifier tous les joueurs
                    current_positions = [player.position for player in next_state.players]
                    
                if current_positions == last_positions:
                    stuck_frames += 1
                    if stuck_frames >= self.max_stuck_frames:
                        print(f"      ⚠️ Agent{'s' if not self.single_agent else ''} bloqué{'s' if not self.single_agent else ''} pendant {stuck_frames} frames, arrêt forcé")
                        break
                else:
                    stuck_frames = 0
                last_positions = current_positions
                
                # Passer à l'état suivant
                state = next_state
                step_count = step + 1
                
                # Stocker la trajectoire
                trajectory_step = {
                    'timestep': step,
                    'state': {
                        'players': [
                            {
                                'position': list(player.position),
                                'held_object': str(player.held_object) if player.held_object else None
                            } for player in state.players
                        ]
                    },
                    'joint_action': [str(action) for action in joint_action],
                    'reward': step_reward,
                    'event_infos': event_infos
                }
                trajectory.append(trajectory_step)
                
                # Mesurer le timing
                step_end_time = time.time()
                step_duration = step_end_time - step_start_time
                step_times.append(step_duration)
                
                if step_duration > 0:
                    fps_measurements.append(1.0 / step_duration)
                
                # Simulation du timing réel désactivée pour optimisation
                # if step_duration < self.step_duration:
                #     time.sleep(self.step_duration - step_duration)
        
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
        
        # Calculer les métriques comportementales agrégées
        behavioral_summary = self._calculate_behavioral_summary(
            event_infos_history, behavioral_metrics, step_count
        )
        
        # Statistiques FPS
        avg_fps = np.mean(fps_measurements) if fps_measurements else 0
        actual_fps = step_count / max(0.001, total_game_time)
        
        # Actions par agent
        total_actions_agent_0 = sum(agent_actions_count[0].values())
        total_actions_agent_1 = sum(agent_actions_count[1].values())
        
        # Calculer les métriques supplémentaires compatibles avec 2_0_0.json
        total_interact_actions = behavioral_metrics['interactions_count']
        
        # Résultats détaillés avec compatibilité 2_0_0.json
        game_result = {
            'game_id': game_id,
            'completed': completed,
            'steps': step_count,
            'total_reward': total_reward,
            'orders_completed': completed_orders,
            'initial_orders': initial_orders,
            'completion_rate': completed_orders / max(1, initial_orders),
            'single_agent_mode': self.single_agent,
            
            # Section info_sum compatible avec 2_0_0.json
            'info_sum': behavioral_summary.get('event_summary', {}),
            
            # Métriques d'actions compatibles avec 2_0_0.json
            'agent_action_count': total_actions_agent_0 if self.single_agent else total_actions_agent_0 + total_actions_agent_1,
            'human_action_count': 0,  # Dans notre cas, pas d'humains
            'agent_interact_count': sum(total_interact_actions),
            'human_interact_count': 0,  # Dans notre cas, pas d'humains
            'agent_stuck_loop': stuck_frames,
            'achieved_orders_len': completed_orders,
            
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
                    'action_distribution': {str(k): v for k, v in agent_actions_count[0].items()},
                    'active': True,
                    'agent_type': 'GreedyAgent',
                    'interact_count': total_interact_actions[0],
                    'distance_traveled': behavioral_metrics['total_distance_traveled'][0]
                },
                'agent_1': {
                    'total_actions': total_actions_agent_1,
                    'actions_per_step': total_actions_agent_1 / max(1, step_count),
                    'action_distribution': {str(k): v for k, v in agent_actions_count[1].items()},
                    'active': not self.single_agent,
                    'agent_type': 'StayAgent' if self.greedy_with_stay else ('GreedyAgent' if not self.single_agent else 'Inactive_OutOfBounds'),
                    'interact_count': total_interact_actions[1],
                    'distance_traveled': behavioral_metrics['total_distance_traveled'][1]
                }
            },
            'stuck_frames': stuck_frames,
            'stuck_forced_stop': stuck_frames >= self.max_stuck_frames,
            'behavioral_metrics': behavioral_summary,
            'trajectory': trajectory,  # Ajouter la trajectoire complète
            'layout_name': mdp.layout_name if hasattr(mdp, 'layout_name') else 'unknown',
            'mdp_terrain': [[str(cell) for cell in row] for row in mdp.terrain_mtx],  # Grille réellement utilisée
            'start_player_positions': mdp.start_player_positions,  # Positions de départ réelles
            'layout_structure': {
                'width': mdp.width,
                'height': mdp.height,
                'player_count': len(mdp.start_player_positions)
            }
        }
        
        mode_info = "SOLO PUR" if self.single_agent else ("GREEDY+STAY" if self.greedy_with_stay else "COOP")
        print(f"      📊 Résultat [{mode_info}]: {step_count} steps, {completed_orders}/{initial_orders} commandes, "
              f"FPS: {actual_fps:.1f}, temps: {total_game_time:.2f}s")
        
        return game_result
    
    def _fix_missing_tomato_pickup_events(self, event_infos: Dict, prev_state, current_state):
        """
        CORRECTION BUG OVERCOOKED AI: Les événements tomato_pickup ne sont pas générés
        quand un agent ramasse une tomate depuis un distributeur.
        
        Cette méthode détecte manuellement quand un agent ramasse une tomate
        en comparant l'état précédent et l'état actuel.
        """
        # Initialiser les événements tomate s'ils n'existent pas
        if 'tomato_pickup' not in event_infos:
            event_infos['tomato_pickup'] = [False, False]
        if 'useful_tomato_pickup' not in event_infos:
            event_infos['useful_tomato_pickup'] = [False, False]
        
        # Vérifier chaque agent
        for agent_idx in range(len(prev_state.players)):
            prev_player = prev_state.players[agent_idx]
            current_player = current_state.players[agent_idx]
            
            # Détecter si l'agent a ramassé une tomate
            prev_has_tomato = (prev_player.held_object is not None and 
                              prev_player.held_object.name == 'tomato')
            current_has_tomato = (current_player.held_object is not None and 
                                 current_player.held_object.name == 'tomato')
            
            # Si l'agent n'avait pas de tomate avant et en a une maintenant
            if not prev_has_tomato and current_has_tomato:
                # Vérifier si l'agent est sur un distributeur de tomates
                pos = current_player.position
                terrain_type = None
                try:
                    # Accéder au terrain via le MDP (si disponible)
                    if hasattr(self, '_current_mdp') and self._current_mdp:
                        terrain_type = self._current_mdp.get_terrain_type(pos)
                    else:
                        # Fallback : détecter basé sur la logique (toute acquisition de tomate = pickup)
                        terrain_type = 'T'  # Assumer distributeur de tomates
                except:
                    terrain_type = 'T'  # Fallback sécurisé
                
                if terrain_type == 'T' or current_has_tomato:  # Distributeur ou détection générale
                    # Déclencher l'événement tomato_pickup
                    event_infos['tomato_pickup'][agent_idx] = True
                    
                    # Pour simplifier, considérer tous les pickups de tomates comme utiles
                    # (dans la vraie logique d'Overcooked, cela dépend de l'état des pots)
                    event_infos['useful_tomato_pickup'][agent_idx] = True
    
    def _calculate_behavioral_summary(self, event_infos_history: List[Dict], 
                                    behavioral_metrics: Dict, step_count: int) -> Dict:
        """
        Calcule un résumé des métriques comportementales basé sur l'historique des événements.
        Compatible avec le format 2_0_0.json: retourne 'event_summary' qui correspond à 'info_sum'
        
        IMPORTANT: En mode solo, tous les événements sont attribués à l'agent 0 uniquement.
        """
        # Agréger tous les event_infos comme dans game.py et 2_0_0.json
        event_summary = {}
        
        # Initialiser avec tous les types d'événements (compatible 2_0_0.json)
        from overcooked_ai_py.mdp.overcooked_mdp import EVENT_TYPES
        for event_type in EVENT_TYPES:
            event_summary[event_type] = [0, 0]  # [agent_0, agent_1]
        
        # Compter les événements pour chaque agent
        for event_info in event_infos_history:
            for event_type, agent_bools in event_info.items():
                if event_type in event_summary:
                    for agent_idx, occurred in enumerate(agent_bools):
                        if occurred and agent_idx < 2:
                            # Attribution normale : chaque agent garde ses propres événements
                            event_summary[event_type][agent_idx] += 1
        
        # Calculer des métriques dérivées
        efficiency_metrics = self._calculate_efficiency_metrics(event_summary, behavioral_metrics, step_count)
        
        return {
            'event_summary': event_summary,  # Ce champ sera utilisé pour 'info_sum'
            'interactions_count': behavioral_metrics['interactions_count'],
            'total_distance_traveled': behavioral_metrics['total_distance_traveled'],
            'collaboration_events': behavioral_metrics['collaboration_events'],
            'efficiency_metrics': efficiency_metrics
        }
    
    def _calculate_efficiency_metrics(self, event_summary: Dict, 
                                    behavioral_metrics: Dict, step_count: int) -> Dict:
        """
        Calcule des métriques d'efficacité comportementale.
        """
        efficiency_metrics = {}
        
        for agent_idx in range(2):
            # Efficacité des pickups (utiles vs totaux)
            total_pickups = (event_summary.get('tomato_pickup', [0, 0])[agent_idx] + 
                           event_summary.get('onion_pickup', [0, 0])[agent_idx] + 
                           event_summary.get('dish_pickup', [0, 0])[agent_idx] + 
                           event_summary.get('soup_pickup', [0, 0])[agent_idx])
            
            useful_pickups = (event_summary.get('useful_tomato_pickup', [0, 0])[agent_idx] + 
                            event_summary.get('useful_onion_pickup', [0, 0])[agent_idx] + 
                            event_summary.get('useful_dish_pickup', [0, 0])[agent_idx])
            
            pickup_efficiency = useful_pickups / max(1, total_pickups) if total_pickups > 0 else 0
            
            # Efficacité de potting (optimal + viable vs total)
            total_potting = (event_summary.get('potting_tomato', [0, 0])[agent_idx] + 
                           event_summary.get('potting_onion', [0, 0])[agent_idx])
            
            optimal_potting = (event_summary.get('optimal_tomato_potting', [0, 0])[agent_idx] + 
                             event_summary.get('optimal_onion_potting', [0, 0])[agent_idx])
            
            viable_potting = (event_summary.get('viable_tomato_potting', [0, 0])[agent_idx] + 
                            event_summary.get('viable_onion_potting', [0, 0])[agent_idx])
            
            potting_efficiency = (optimal_potting + viable_potting) / max(1, total_potting) if total_potting > 0 else 0
            
            # Actions par step
            actions_per_step = behavioral_metrics['interactions_count'][agent_idx] / max(1, step_count)
            
            # Mouvement par step
            movement_per_step = behavioral_metrics['total_distance_traveled'][agent_idx] / max(1, step_count)
            
            efficiency_metrics[f'agent_{agent_idx}'] = {
                'pickup_efficiency': pickup_efficiency,
                'potting_efficiency': potting_efficiency,
                'actions_per_step': actions_per_step,
                'movement_per_step': movement_per_step,
                'total_pickups': total_pickups,
                'useful_pickups': useful_pickups,
                'total_potting': total_potting,
                'optimal_potting': optimal_potting,
                'soup_deliveries': event_summary.get('soup_delivery', [0, 0])[agent_idx]
            }
        
        # Métriques globales d'équipe
        total_soup_deliveries = sum(event_summary.get('soup_delivery', [0, 0]))
        total_collaboration = behavioral_metrics['collaboration_events']
        
        efficiency_metrics['team'] = {
            'total_soup_deliveries': total_soup_deliveries,
            'collaboration_events': total_collaboration,
            'collaboration_per_delivery': total_collaboration / max(1, total_soup_deliveries)
        }
        
        return efficiency_metrics
    
    def _aggregate_behavioral_metrics(self, game_results: List[Dict]) -> Dict:
        """
        Caractérise précisément comment les GreedyAgent(s) complètent ce layout spécifique.
        Focus sur les patterns comportementaux caractéristiques plutôt que sur l'agrégation.
        """
        from overcooked_ai_py.mdp.overcooked_mdp import EVENT_TYPES
        
        # Analyser seulement les parties complétées pour comprendre les stratégies gagnantes
        completed_games = [g for g in game_results if g.get('completed', False)]
        
        if not completed_games:
            return {
                'completion_analysis': 'no_successful_completion',
                'layout_solvability': 'unsolvable_with_current_agents',
                'total_attempts': len(game_results)
            }
        
        # ANALYSE DES PATTERNS DE COMPLETION RÉUSSIS
        completion_patterns = self._analyze_completion_patterns(completed_games)
        
        # CARACTÉRISATION DU LAYOUT
        layout_characteristics = self._characterize_layout_behavior(completed_games)
        
        # IDENTIFICATION DES STRATÉGIES OPTIMALES
        optimal_strategies = self._identify_optimal_strategies(completed_games)
        
        # MÉTRIQUES DE COHÉRENCE (toutes les parties complétées utilisent-elles la même stratégie ?)
        strategy_consistency = self._analyze_strategy_consistency(completed_games)
        
        return {
            'completion_analysis': 'successful_completion_found',
            'total_attempts': len(game_results),
            'successful_completions': len(completed_games),
            'success_rate': len(completed_games) / len(game_results),
            
            # Comment ce layout spécifique est résolu
            'completion_patterns': completion_patterns,
            'layout_characteristics': layout_characteristics,
            'optimal_strategies': optimal_strategies,
            'strategy_consistency': strategy_consistency,
            
            # Variabilité entre les tentatives réussies
            'completion_variability': self._calculate_completion_variability(completed_games)
        }
    
    def _analyze_completion_patterns(self, completed_games: List[Dict]) -> Dict:
        """
        Analyse les patterns spécifiques de complétion pour ce layout.
        Comment les agents résolvent-ils ce niveau particulier ?
        """
        patterns = {
            'temporal_progression': [],  # Progression temporelle des événements clés
            'critical_events_sequence': [],  # Séquence d'événements critiques
            'coordination_patterns': [],  # Patterns de coordination entre agents
            'efficiency_progression': []  # Evolution de l'efficacité au cours du temps
        }
        
        for game in completed_games:
            if 'behavioral_metrics' not in game:
                continue
                
            bm = game['behavioral_metrics']
            
            # Analyser la progression temporelle des livraisons
            if 'event_summary' in bm:
                soup_deliveries = sum(bm['event_summary'].get('soup_delivery', [0, 0]))
                steps = game.get('steps', 1)
                
                # Pattern temporel de ce jeu
                temporal_pattern = {
                    'total_steps': steps,
                    'soup_deliveries': soup_deliveries,
                    'deliveries_per_step': soup_deliveries / steps,
                    'efficiency_score': soup_deliveries / max(steps / 100, 1),  # Normalised
                    'agent_balance': self._calculate_agent_balance(bm['event_summary'])
                }
                patterns['temporal_progression'].append(temporal_pattern)
                
                # Identifier les événements critiques
                critical_events = self._identify_critical_event_sequence(bm['event_summary'])
                patterns['critical_events_sequence'].append(critical_events)
                
                # Patterns de coordination
                coordination = self._analyze_coordination_pattern(bm['event_summary'])
                patterns['coordination_patterns'].append(coordination)
        
        # Caractériser le pattern dominant pour ce layout
        if patterns['temporal_progression']:
            # Identifier le pattern de complétion le plus représentatif
            dominant_pattern = self._identify_dominant_completion_pattern(patterns)
            patterns['dominant_strategy'] = dominant_pattern
        
        return patterns
    
    def _characterize_layout_behavior(self, completed_games: List[Dict]) -> Dict:
        """
        Caractérise les comportements spécifiques à ce layout.
        Quelles sont les contraintes et opportunités de ce niveau ?
        """
        characteristics = {
            'layout_difficulty': 'unknown',
            'required_coordination_level': 'unknown', 
            'bottleneck_identification': [],
            'optimal_agent_roles': {},
            'layout_specific_strategies': []
        }
        
        if not completed_games:
            return characteristics
        
        # Analyser la difficulté basée sur les steps nécessaires
        steps_needed = [g.get('steps', 0) for g in completed_games]
        avg_steps = np.mean(steps_needed)
        
        if avg_steps < 200:
            characteristics['layout_difficulty'] = 'easy'
        elif avg_steps < 400:
            characteristics['layout_difficulty'] = 'moderate' 
        else:
            characteristics['layout_difficulty'] = 'hard'
        
        # Analyser le niveau de coordination requis
        coordination_levels = []
        role_specializations = []
        
        for game in completed_games:
            if 'behavioral_metrics' not in game:
                continue
                
            bm = game['behavioral_metrics']
            if 'event_summary' not in bm:
                continue
                
            events = bm['event_summary']
            
            # Mesurer la coordination par les échanges d'objets
            exchanges = ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange']
            total_exchanges = sum(sum(events.get(ex, [0, 0])) for ex in exchanges)
            coordination_levels.append(total_exchanges)
            
            # Analyser la spécialisation des rôles
            agent_0_soups = events.get('soup_delivery', [0, 0])[0]
            agent_1_soups = events.get('soup_delivery', [0, 0])[1]
            total_soups = agent_0_soups + agent_1_soups
            
            if total_soups > 0:
                specialization = abs(agent_0_soups - agent_1_soups) / total_soups
                role_specializations.append(specialization)
                
                # Identifier les rôles spécifiques
                if agent_0_soups > agent_1_soups * 1.5:
                    characteristics['optimal_agent_roles']['agent_0'] = 'primary_deliverer'
                    characteristics['optimal_agent_roles']['agent_1'] = 'support_prep'
                elif agent_1_soups > agent_0_soups * 1.5:
                    characteristics['optimal_agent_roles']['agent_0'] = 'support_prep'
                    characteristics['optimal_agent_roles']['agent_1'] = 'primary_deliverer'
                else:
                    characteristics['optimal_agent_roles']['both'] = 'balanced_cooperation'
        
        # Déterminer le niveau de coordination requis
        if coordination_levels:
            avg_coordination = np.mean(coordination_levels)
            if avg_coordination < 2:
                characteristics['required_coordination_level'] = 'minimal'
            elif avg_coordination < 5:
                characteristics['required_coordination_level'] = 'moderate'
            else:
                characteristics['required_coordination_level'] = 'high'
        
        # Identifier les stratégies spécifiques à ce layout
        characteristics['layout_specific_strategies'] = self._identify_layout_strategies(completed_games)
        
        return characteristics
    
    def _identify_optimal_strategies(self, completed_games: List[Dict]) -> Dict:
        """
        Identifie les stratégies optimales pour compléter ce layout spécifique.
        """
        strategies = {
            'fastest_completion_strategy': None,
            'most_efficient_strategy': None,
            'most_consistent_strategy': None,
            'strategy_recommendations': []
        }
        
        if not completed_games:
            return strategies
        
        # Identifier la stratégie de complétion la plus rapide
        fastest_game = min(completed_games, key=lambda g: g.get('steps', float('inf')))
        strategies['fastest_completion_strategy'] = self._extract_strategy_profile(fastest_game)
        
        # Identifier la stratégie la plus efficace (meilleur ratio récompense/steps)
        efficiency_scores = []
        for game in completed_games:
            steps = game.get('steps', 1)
            reward = game.get('total_reward', 0)
            efficiency_scores.append((reward / steps, game))
        
        if efficiency_scores:
            most_efficient_game = max(efficiency_scores, key=lambda x: x[0])[1]
            strategies['most_efficient_strategy'] = self._extract_strategy_profile(most_efficient_game)
        
        # Générer des recommandations stratégiques
        strategies['strategy_recommendations'] = self._generate_strategy_recommendations(completed_games)
        
        return strategies
    
    def _analyze_strategy_consistency(self, completed_games: List[Dict]) -> Dict:
        """
        Analyse la cohérence des stratégies utilisées pour ce layout.
        Les différentes tentatives réussies utilisent-elles des approches similaires ?
        """
        consistency = {
            'strategy_variance': 0,
            'dominant_pattern_percentage': 0,
            'layout_determinism': 'unknown',
            'alternative_strategies_count': 0
        }
        
        if len(completed_games) < 2:
            consistency['layout_determinism'] = 'insufficient_data'
            return consistency
        
        # Extraire les profils de stratégie de chaque jeu
        strategy_profiles = []
        for game in completed_games:
            profile = self._extract_strategy_profile(game)
            strategy_profiles.append(profile)
        
        # Calculer la variance entre les stratégies
        consistency['strategy_variance'] = self._calculate_strategy_variance(strategy_profiles)
        
        # Identifier les patterns dominants
        patterns = self._cluster_strategy_patterns(strategy_profiles)
        if patterns:
            dominant_pattern_size = max(len(pattern) for pattern in patterns)
            consistency['dominant_pattern_percentage'] = dominant_pattern_size / len(completed_games)
            consistency['alternative_strategies_count'] = len(patterns)
        
        # Déterminer le déterminisme du layout
        if consistency['strategy_variance'] < 0.2:
            consistency['layout_determinism'] = 'highly_deterministic'
        elif consistency['strategy_variance'] < 0.5:
            consistency['layout_determinism'] = 'moderately_deterministic'
        else:
            consistency['layout_determinism'] = 'multiple_viable_strategies'
        
        return consistency
    
    def _calculate_completion_variability(self, completed_games: List[Dict]) -> Dict:
        """
        Calcule la variabilité entre les différentes tentatives de complétion réussies.
        """
        variability = {
            'steps_variability': 0,
            'strategy_diversity': 0,
            'performance_consistency': 0
        }
        
        if len(completed_games) < 2:
            return variability
        
        # Variabilité en nombre de steps
        steps = [g.get('steps', 0) for g in completed_games]
        variability['steps_variability'] = np.std(steps) / np.mean(steps) if np.mean(steps) > 0 else 0
        
        # Diversité des stratégies
        strategy_profiles = [self._extract_strategy_profile(g) for g in completed_games]
        variability['strategy_diversity'] = self._calculate_strategy_diversity(strategy_profiles)
        
        # Cohérence des performances
        rewards = [g.get('total_reward', 0) for g in completed_games]
        variability['performance_consistency'] = 1 - (np.std(rewards) / np.mean(rewards)) if np.mean(rewards) > 0 else 0
        
        return variability
    
    def _calculate_agent_balance(self, event_summary: Dict) -> Dict:
        """Calcule l'équilibre entre les agents pour ce layout."""
        soup_deliveries = event_summary.get('soup_delivery', [0, 0])
        total_soups = sum(soup_deliveries)
        
        if total_soups == 0:
            return {'balance_type': 'no_deliveries', 'balance_score': 0}
        
        balance_score = min(soup_deliveries) / max(soup_deliveries) if max(soup_deliveries) > 0 else 0
        
        if balance_score > 0.8:
            balance_type = 'highly_balanced'
        elif balance_score > 0.5:
            balance_type = 'moderately_balanced'
        else:
            balance_type = 'specialized_roles'
            
        return {
            'balance_type': balance_type,
            'balance_score': balance_score,
            'agent_0_contribution': soup_deliveries[0] / total_soups,
            'agent_1_contribution': soup_deliveries[1] / total_soups
        }
    
    def _identify_critical_event_sequence(self, event_summary: Dict) -> Dict:
        """Identifie la séquence d'événements critiques pour ce layout."""
        critical_events = {
            'pickup_phase': sum(event_summary.get('tomato_pickup', [0, 0])) + sum(event_summary.get('onion_pickup', [0, 0])),
            'preparation_phase': sum(event_summary.get('potting_tomato', [0, 0])) + sum(event_summary.get('potting_onion', [0, 0])),
            'cooking_phase': sum(event_summary.get('soup_pickup', [0, 0])),
            'delivery_phase': sum(event_summary.get('soup_delivery', [0, 0]))
        }
        
        # Identifier le goulot d'étranglement
        phase_ratios = {}
        total_deliveries = critical_events['delivery_phase']
        if total_deliveries > 0:
            for phase, count in critical_events.items():
                phase_ratios[phase] = count / total_deliveries
        
        return {
            'event_counts': critical_events,
            'phase_efficiency': phase_ratios,
            'bottleneck_phase': min(phase_ratios.items(), key=lambda x: x[1])[0] if phase_ratios else 'unknown'
        }
    
    def _analyze_coordination_pattern(self, event_summary: Dict) -> Dict:
        """Analyse les patterns de coordination spécifiques."""
        exchanges = ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange']
        total_exchanges = sum(sum(event_summary.get(ex, [0, 0])) for ex in exchanges)
        
        deliveries = sum(event_summary.get('soup_delivery', [0, 0]))
        
        if deliveries == 0:
            return {'coordination_type': 'no_completion', 'exchanges_per_delivery': 0}
        
        exchanges_per_delivery = total_exchanges / deliveries
        
        if exchanges_per_delivery < 0.5:
            coordination_type = 'minimal_coordination'
        elif exchanges_per_delivery < 2:
            coordination_type = 'moderate_coordination'
        else:
            coordination_type = 'high_coordination'
            
        return {
            'coordination_type': coordination_type,
            'exchanges_per_delivery': exchanges_per_delivery,
            'total_exchanges': total_exchanges,
            'exchange_breakdown': {ex: sum(event_summary.get(ex, [0, 0])) for ex in exchanges}
        }
    
    def _identify_dominant_completion_pattern(self, patterns: Dict) -> Dict:
        """Identifie le pattern de complétion dominant pour ce layout."""
        if not patterns['temporal_progression']:
            return {'pattern_type': 'no_pattern_found'}
        
        # Analyser les efficacités pour identifier le pattern optimal
        efficiencies = [tp['efficiency_score'] for tp in patterns['temporal_progression']]
        steps = [tp['total_steps'] for tp in patterns['temporal_progression']]
        
        # Le pattern dominant est celui qui combine rapidité et efficacité
        best_idx = 0
        best_score = 0
        
        for i, (eff, step) in enumerate(zip(efficiencies, steps)):
            # Score combiné : efficacité élevée ET steps faibles
            combined_score = eff * (1000 / max(step, 100))  # Favorise moins de steps
            if combined_score > best_score:
                best_score = combined_score
                best_idx = i
        
        dominant = patterns['temporal_progression'][best_idx]
        dominant['pattern_identification'] = 'optimal_speed_efficiency_combination'
        
        return dominant
    
    def _identify_layout_strategies(self, completed_games: List[Dict]) -> List[str]:
        """Identifie les stratégies spécifiques utilisées pour ce layout."""
        strategies = []
        
        for game in completed_games:
            if 'behavioral_metrics' not in game:
                continue
                
            bm = game['behavioral_metrics']
            if 'event_summary' not in bm:
                continue
                
            events = bm['event_summary']
            
            # Identifier les stratégies basées sur les patterns d'événements
            agent_0_pickups = events.get('tomato_pickup', [0, 0])[0] + events.get('onion_pickup', [0, 0])[0]
            agent_1_pickups = events.get('tomato_pickup', [0, 0])[1] + events.get('onion_pickup', [0, 0])[1]
            
            agent_0_deliveries = events.get('soup_delivery', [0, 0])[0]
            agent_1_deliveries = events.get('soup_delivery', [0, 0])[1]
            
            # Stratégie de spécialisation
            if agent_0_deliveries > agent_1_deliveries * 2:
                strategies.append('agent_0_specializes_delivery')
            elif agent_1_deliveries > agent_0_deliveries * 2:
                strategies.append('agent_1_specializes_delivery')
            else:
                strategies.append('balanced_delivery_roles')
            
            # Stratégie de préparation
            if agent_0_pickups > agent_1_pickups * 2:
                strategies.append('agent_0_specializes_preparation')
            elif agent_1_pickups > agent_0_pickups * 2:
                strategies.append('agent_1_specializes_preparation')
            else:
                strategies.append('shared_preparation_duties')
            
            # Niveau de coordination
            exchanges = sum(sum(events.get(ex, [0, 0])) for ex in ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange'])
            total_deliveries = sum(events.get('soup_delivery', [0, 0]))
            
            if exchanges / max(total_deliveries, 1) > 1:
                strategies.append('high_coordination_strategy')
            else:
                strategies.append('low_coordination_strategy')
        
        # Retourner les stratégies dominantes (les plus fréquentes)
        from collections import Counter
        strategy_counts = Counter(strategies)
        dominant_strategies = [strategy for strategy, count in strategy_counts.most_common(3)]
        
        return dominant_strategies
    
    def _extract_strategy_profile(self, game: Dict) -> Dict:
        """Extrait un profil de stratégie complet d'un jeu."""
        profile = {
            'completion_time': game.get('steps', 0),
            'total_reward': game.get('total_reward', 0),
            'agent_balance': {},
            'coordination_level': 0,
            'efficiency_metrics': {}
        }
        
        if 'behavioral_metrics' in game and 'event_summary' in game['behavioral_metrics']:
            events = game['behavioral_metrics']['event_summary']
            
            # Balance entre agents
            soup_deliveries = events.get('soup_delivery', [0, 0])
            total_soups = sum(soup_deliveries)
            if total_soups > 0:
                profile['agent_balance'] = {
                    'agent_0_share': soup_deliveries[0] / total_soups,
                    'agent_1_share': soup_deliveries[1] / total_soups,
                    'balance_score': min(soup_deliveries) / max(soup_deliveries) if max(soup_deliveries) > 0 else 0
                }
            
            # Niveau de coordination
            exchanges = sum(sum(events.get(ex, [0, 0])) for ex in ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange'])
            profile['coordination_level'] = exchanges / max(total_soups, 1)
            
            # Métriques d'efficacité
            if 'efficiency_metrics' in game['behavioral_metrics']:
                em = game['behavioral_metrics']['efficiency_metrics']
                profile['efficiency_metrics'] = {
                    'avg_pickup_efficiency': (em.get('agent_0', {}).get('pickup_efficiency', 0) + em.get('agent_1', {}).get('pickup_efficiency', 0)) / 2,
                    'avg_potting_efficiency': (em.get('agent_0', {}).get('potting_efficiency', 0) + em.get('agent_1', {}).get('potting_efficiency', 0)) / 2
                }
        
        return profile
    
    def _calculate_strategy_variance(self, strategy_profiles: List[Dict]) -> float:
        """Calcule la variance entre différents profils de stratégie."""
        if len(strategy_profiles) < 2:
            return 0
        
        # Normaliser et comparer les métriques clés
        completion_times = [p['completion_time'] for p in strategy_profiles]
        coordination_levels = [p['coordination_level'] for p in strategy_profiles]
        
        # Variance normalisée
        time_variance = np.std(completion_times) / np.mean(completion_times) if np.mean(completion_times) > 0 else 0
        coord_variance = np.std(coordination_levels) / max(np.mean(coordination_levels), 0.1)
        
        return (time_variance + coord_variance) / 2
    
    def _cluster_strategy_patterns(self, strategy_profiles: List[Dict]) -> List[List[Dict]]:
        """Regroupe les profils de stratégie similaires."""
        if len(strategy_profiles) < 2:
            return [strategy_profiles] if strategy_profiles else []
        
        # Clustering simple basé sur la similarité des métriques
        clusters = []
        similarity_threshold = 0.3
        
        for profile in strategy_profiles:
            placed = False
            for cluster in clusters:
                # Vérifier la similarité avec le premier élément du cluster
                if self._calculate_profile_similarity(profile, cluster[0]) > similarity_threshold:
                    cluster.append(profile)
                    placed = True
                    break
            
            if not placed:
                clusters.append([profile])
        
        return clusters
    
    def _calculate_profile_similarity(self, profile1: Dict, profile2: Dict) -> float:
        """Calcule la similarité entre deux profils de stratégie."""
        similarity_score = 0
        comparisons = 0
        
        # Comparer les temps de complétion (normalisé)
        if profile1['completion_time'] > 0 and profile2['completion_time'] > 0:
            time_similarity = 1 - abs(profile1['completion_time'] - profile2['completion_time']) / max(profile1['completion_time'], profile2['completion_time'])
            similarity_score += time_similarity
            comparisons += 1
        
        # Comparer les niveaux de coordination
        coord_diff = abs(profile1['coordination_level'] - profile2['coordination_level'])
        coord_similarity = max(0, 1 - coord_diff)
        similarity_score += coord_similarity
        comparisons += 1
        
        # Comparer la balance des agents
        if profile1['agent_balance'] and profile2['agent_balance']:
            balance_diff = abs(profile1['agent_balance'].get('balance_score', 0) - profile2['agent_balance'].get('balance_score', 0))
            balance_similarity = max(0, 1 - balance_diff)
            similarity_score += balance_similarity
            comparisons += 1
        
        return similarity_score / max(comparisons, 1)
    
    def _calculate_strategy_diversity(self, strategy_profiles: List[Dict]) -> float:
        """Calcule la diversité des stratégies utilisées."""
        if len(strategy_profiles) < 2:
            return 0
        
        total_similarity = 0
        comparisons = 0
        
        for i in range(len(strategy_profiles)):
            for j in range(i + 1, len(strategy_profiles)):
                similarity = self._calculate_profile_similarity(strategy_profiles[i], strategy_profiles[j])
                total_similarity += similarity
                comparisons += 1
        
        avg_similarity = total_similarity / max(comparisons, 1)
        return 1 - avg_similarity  # Diversité = 1 - similarité moyenne
    
    def _generate_strategy_recommendations(self, completed_games: List[Dict]) -> List[str]:
        """Génère des recommandations stratégiques basées sur les parties réussies."""
        recommendations = []
        
        if not completed_games:
            return ['No successful completions found - layout may be too difficult']
        
        # Analyser les patterns de succès
        fastest_steps = min(g.get('steps', float('inf')) for g in completed_games)
        avg_steps = np.mean([g.get('steps', 0) for g in completed_games])
        
        if fastest_steps < avg_steps * 0.8:
            recommendations.append(f'Optimal completion possible in {fastest_steps} steps - focus on speed strategies')
        
        # Analyser les patterns de coordination
        high_coord_games = []
        low_coord_games = []
        
        for game in completed_games:
            if 'behavioral_metrics' in game and 'event_summary' in game['behavioral_metrics']:
                events = game['behavioral_metrics']['event_summary']
                exchanges = sum(sum(events.get(ex, [0, 0])) for ex in ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange'])
                deliveries = sum(events.get('soup_delivery', [0, 0]))
                
                if exchanges / max(deliveries, 1) > 1:
                    high_coord_games.append(game)
                else:
                    low_coord_games.append(game)
        
        if high_coord_games and low_coord_games:
            high_coord_avg = np.mean([g.get('steps', 0) for g in high_coord_games])
            low_coord_avg = np.mean([g.get('steps', 0) for g in low_coord_games])
            
            if high_coord_avg < low_coord_avg:
                recommendations.append('High coordination strategy recommended - agent exchanges improve efficiency')
            else:
                recommendations.append('Independent agent strategy recommended - minimal coordination needed')
        elif high_coord_games:
            recommendations.append('Layout requires high coordination between agents')
        elif low_coord_games:
            recommendations.append('Layout solvable with independent agent strategies')
        
        return recommendations
    
    def _calculate_average_efficiency(self, game_results: List[Dict]) -> Dict:
        """
        Calcule l'efficacité moyenne sur toutes les parties.
        """
        efficiency_sums = {
            'agent_0': {'pickup_efficiency': 0, 'potting_efficiency': 0, 'actions_per_step': 0, 'movement_per_step': 0},
            'agent_1': {'pickup_efficiency': 0, 'potting_efficiency': 0, 'actions_per_step': 0, 'movement_per_step': 0},
            'team': {'collaboration_per_delivery': 0}
        }
        
        valid_games = 0
        
        for game in game_results:
            if 'behavioral_metrics' in game and 'efficiency_metrics' in game['behavioral_metrics']:
                em = game['behavioral_metrics']['efficiency_metrics']
                valid_games += 1
                
                for agent in ['agent_0', 'agent_1']:
                    if agent in em:
                        for metric in efficiency_sums[agent]:
                            efficiency_sums[agent][metric] += em[agent].get(metric, 0)
                
                if 'team' in em:
                    efficiency_sums['team']['collaboration_per_delivery'] += em['team'].get('collaboration_per_delivery', 0)
        
        # Calculer les moyennes
        if valid_games > 0:
            for agent in ['agent_0', 'agent_1']:
                for metric in efficiency_sums[agent]:
                    efficiency_sums[agent][metric] /= valid_games
            
            efficiency_sums['team']['collaboration_per_delivery'] /= valid_games
        
        return efficiency_sums
    
    def _generate_behavioral_insights(self, aggregated_events: Dict, total_interactions: List, 
                                    total_distance: List, num_games: int) -> Dict:
        """
        Génère des insights comportementaux basés sur les données agrégées.
        """
        insights = {}
        
        # Analyse de la spécialisation des agents
        agent_0_soups = aggregated_events.get('soup_delivery', [0, 0])[0]
        agent_1_soups = aggregated_events.get('soup_delivery', [0, 0])[1]
        total_soups = agent_0_soups + agent_1_soups
        
        if total_soups > 0:
            insights['task_distribution'] = {
                'agent_0_soup_share': agent_0_soups / total_soups,
                'agent_1_soup_share': agent_1_soups / total_soups,
                'specialization_index': abs(agent_0_soups - agent_1_soups) / total_soups
            }
        
        # Analyse de l'efficacité comparative
        if total_interactions[0] > 0 and total_interactions[1] > 0:
            interaction_ratio = total_interactions[0] / total_interactions[1]
            insights['agent_activity'] = {
                'interaction_ratio_0_to_1': interaction_ratio,
                'more_active_agent': 0 if interaction_ratio > 1 else 1,
                'activity_balance': min(interaction_ratio, 1/interaction_ratio)  # Plus proche de 1 = plus équilibré
            }
        
        # Analyse des types d'actions dominantes
        pickup_events = ['tomato_pickup', 'onion_pickup', 'dish_pickup', 'soup_pickup']
        potting_events = ['potting_tomato', 'potting_onion']
        
        total_pickups = sum(aggregated_events.get(event, [0, 0])[0] + aggregated_events.get(event, [0, 0])[1] 
                           for event in pickup_events)
        total_pottings = sum(aggregated_events.get(event, [0, 0])[0] + aggregated_events.get(event, [0, 0])[1] 
                            for event in potting_events)
        
        insights['action_patterns'] = {
            'total_pickups': total_pickups,
            'total_pottings': total_pottings,
            'pickups_per_game': total_pickups / num_games,
            'pottings_per_game': total_pottings / num_games,
            'pickup_to_potting_ratio': total_pickups / max(1, total_pottings)
        }
        
        return insights
    
    def evaluate_single_layout(self, layout_name: str) -> Dict:
        """Évalue un seul layout avec plusieurs parties."""
        print(f"\n🏗️ Évaluation: {layout_name}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Vérifier la cohérence de la grille chargée
            grid_verification = self._verify_layout_grid_consistency(layout_name, mdp)
            if grid_verification['has_discrepancy']:
                print(f"⚠️ DIVERGENCE DÉTECTÉE: La grille chargée diffère du fichier .layout pour {layout_name}")
                for issue in grid_verification['issues']:
                    print(f"   - {issue}")
            
            # Analyser la structure
            structure = self._analyze_layout_structure(mdp)
            
            print(f"📊 Layout: {structure['width']}x{structure['height']}, "
                  f"Commandes: {structure['initial_orders']}")
            
            # Créer les agents
            success, agent_or_group = self.create_agent_group(mdp)
            if not success:
                return {
                    'layout_name': layout_name,
                    'viable': False,
                    'error': 'Impossible de créer les agents GreedyAgent',
                    'evaluation_time': time.time() - start_time
                }
            
            agent_info = ("1x GreedyAgent (solo pur)" if self.single_agent else 
                         "GreedyAgent + StayAgent" if self.greedy_with_stay else 
                         "2x GreedyAgent (coop)")
            print(f"🤖 Agents: {agent_info}")
            
            # Simuler toutes les parties
            game_results = []
            total_simulation_time = 0
            
            if self.parallel_games and self.num_games_per_layout > 1:
                # Exécution en parallèle
                print(f"🚀 Simulation en parallèle avec {self.max_workers} workers...")
                
                # Préparer la configuration pour les workers
                evaluator_config = {
                    'layouts_directory': self.layouts_directory,
                    'horizon': self.horizon,
                    'num_games_per_layout': 1,  # Chaque worker fait 1 partie
                    'target_fps': self.target_fps,
                    'max_stuck_frames': self.max_stuck_frames,
                    'single_agent': self.single_agent,
                    'greedy_with_stay': self.greedy_with_stay,
                    'parallel_games': False  # Désactiver le parallélisme dans les workers
                }
                
                # Exécuter les parties en parallèle
                with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                    # Soumettre toutes les tâches
                    future_to_game_id = {
                        executor.submit(simulate_game_parallel, layout_name, game_num, evaluator_config): game_num
                        for game_num in range(1, self.num_games_per_layout + 1)
                    }
                    
                    # Collecter les résultats
                    for future in as_completed(future_to_game_id):
                        game_id = future_to_game_id[future]
                        try:
                            game_result = future.result()
                            if 'error' not in game_result:
                                game_results.append(game_result)
                                total_simulation_time += game_result['timing']['total_time_seconds']
                                print(f"   ✅ Partie {game_id} terminée: {game_result['steps']} steps")
                            else:
                                print(f"   ❌ Partie {game_id} échouée: {game_result['error']}")
                        except Exception as exc:
                            print(f"   ❌ Partie {game_id} a généré une exception: {exc}")
                
            else:
                # Exécution séquentielle (mode classique)
                for game_num in range(1, self.num_games_per_layout + 1):
                    # Reset des agents entre les parties
                    if self.single_agent:
                        agent_or_group.reset()
                        agent_or_group.set_mdp(mdp)
                        agent_or_group.set_agent_index(0)
                    else:
                        agent_or_group.reset()
                        agent_or_group.set_mdp(mdp)
                    
                    game_result = self.simulate_single_game(mdp, agent_or_group, game_num)
                    game_results.append(game_result)
                    total_simulation_time += game_result['timing']['total_time_seconds']
            
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
        
        # Agrégation des métriques comportementales
        behavioral_aggregation = self._aggregate_behavioral_metrics(game_results)
        
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
        
        # Métriques des agents (toujours deux agents, même si un est inactif)
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
        
        # Ajouter les métriques comportementales agrégées
        results['behavioral_analysis'] = behavioral_aggregation
        
        # Détails des parties individuelles (compatible avec 2_0_0.json)
        results['individual_games'] = game_results
        
        # Affichage des résultats
        if completed_games:
            print(f"🏁 COMPLÉTION: {len(completed_games)}/{len(game_results)} parties")
            print(f"⏱️ Temps moyen: {results['completion_metrics']['average_completion_steps']:.1f} steps")
            print(f"🚀 Plus rapide: {results['completion_metrics']['fastest_completion_steps']} steps")
            print(f"📊 FPS moyen: {results['performance_metrics']['actual_fps']['average']:.1f}")
            
            # Affichage des actions adapté au mode
            if self.single_agent:
                print(f"🤖 Actions/step: Agent0={results['agent_metrics']['agent_0']['actions_per_step']:.2f} (mode SOLO), "
                      f"Agent1={results['agent_metrics']['agent_1']['actions_per_step']:.2f} (hors carte)")
            else:
                print(f"🤖 Actions/step: Agent0={results['agent_metrics']['agent_0']['actions_per_step']:.2f}, "
                      f"Agent1={results['agent_metrics']['agent_1']['actions_per_step']:.2f}")
            
            # Affichage des métriques comportementales spécifiques au layout
            if 'behavioral_analysis' in results:
                ba = results['behavioral_analysis']
                print(f"🎯 Analyse comportementale du layout:")
                
                if ba.get('completion_analysis') == 'successful_completion_found':
                    # Stratégies optimales identifiées
                    if 'optimal_strategies' in ba and 'strategy_recommendations' in ba['optimal_strategies']:
                        recs = ba['optimal_strategies']['strategy_recommendations']
                        if recs:
                            print(f"   📋 Recommandations: {recs[0]}")
                    
                    # Caractéristiques du layout
                    if 'layout_characteristics' in ba:
                        lc = ba['layout_characteristics']
                        print(f"   🎮 Difficulté: {lc.get('layout_difficulty', 'unknown')}")
                        print(f"   🤝 Coordination requise: {lc.get('required_coordination_level', 'unknown')}")
                        
                        if 'optimal_agent_roles' in lc:
                            roles = lc['optimal_agent_roles']
                            if 'both' in roles:
                                print(f"   👥 Rôles optimaux: {roles['both']}")
                            else:
                                print(f"   👥 Rôles optimaux: Agent0={roles.get('agent_0', 'unknown')}, Agent1={roles.get('agent_1', 'unknown')}")
                    
                    # Patterns de complétion
                    if 'completion_patterns' in ba and 'dominant_strategy' in ba['completion_patterns']:
                        ds = ba['completion_patterns']['dominant_strategy']
                        if 'efficiency_score' in ds:
                            print(f"   ⚡ Score d'efficacité optimal: {ds['efficiency_score']:.2f}")
                        if 'agent_balance' in ds:
                            balance = ds['agent_balance']
                            print(f"   ⚖️ Équilibre optimal: {balance.get('balance_type', 'unknown')} (score: {balance.get('balance_score', 0):.2f})")
                    
                    # Cohérence des stratégies
                    if 'strategy_consistency' in ba:
                        sc = ba['strategy_consistency']
                        print(f"   🎯 Déterminisme du layout: {sc.get('layout_determinism', 'unknown')}")
                        if sc.get('alternative_strategies_count', 0) > 1:
                            print(f"   🔀 Stratégies alternatives trouvées: {sc['alternative_strategies_count']}")
                        else:
                            print(f"   🎯 Stratégie unique identifiée")
                
                else:
                    print(f"   ❌ Aucune complétion réussie - layout potentiellement trop difficile")
                
                # Statistiques de base toujours affichées
                total_soups = 0
                if 'completion_patterns' in ba and ba['completion_patterns'].get('temporal_progression'):
                    tp = ba['completion_patterns']['temporal_progression'][0]  # Premier jeu réussi
                    total_soups = tp.get('soup_deliveries', 0)
                    print(f"   🍲 Soupes livrées (exemple réussi): {total_soups}")
            else:
                # Fallback vers les anciennes métriques si les nouvelles ne sont pas disponibles
                print(f"🎯 Métriques comportementales basiques:")
                print(f"   ⚠️ Analyse comportementale avancée non disponible")
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
    
    def save_results(self, filename: str = "layout_evaluation_final.json", include_individual_games: bool = False):
        """
        Sauvegarde les résultats détaillés.
        
        Args:
            filename: Nom du fichier de sortie
            include_individual_games: Si True, inclut les détails de chaque partie (fichier volumineux)
                                    Si False, ne sauvegarde que les métriques agrégées par layout
        """
        # Préparer les données d'output en excluant les parties individuelles si demandé
        results_to_save = {}
        
        for layout_name, layout_data in self.results.items():
            if layout_data.get('viable', False):
                # Copier toutes les données sauf individual_games si pas demandé
                filtered_data = {}
                for key, value in layout_data.items():
                    if key == 'individual_games' and not include_individual_games:
                        continue  # Exclure les détails des parties individuelles
                    filtered_data[key] = value
                
                results_to_save[layout_name] = filtered_data
            else:
                # Garder les layouts non viables tels quels (ils n'ont pas d'individual_games)
                results_to_save[layout_name] = layout_data
        
        output_data = {
            'evaluation_config': {
                'layouts_directory': self.layouts_directory,
                'horizon': self.horizon,
                'num_games_per_layout': self.num_games_per_layout,
                'target_fps': self.target_fps,
                'max_stuck_frames': self.max_stuck_frames,
                'single_agent_mode': self.single_agent,
                'greedy_with_stay_mode': self.greedy_with_stay
            },
            'evaluation_timestamp': time.time(),
            'data_type': 'layout_aggregated_metrics' if not include_individual_games else 'detailed_with_individual_games',
            'results': results_to_save
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        data_type_desc = "métriques agrégées par layout" if not include_individual_games else "données détaillées avec parties individuelles"
        print(f"💾 Résultats sauvegardés dans {filename} ({data_type_desc})")
        
        # Afficher la taille du fichier
        import os
        file_size = os.path.getsize(filename)
        if file_size > 1024 * 1024:
            print(f"   📦 Taille: {file_size / (1024 * 1024):.1f} MB")
        elif file_size > 1024:
            print(f"   📦 Taille: {file_size / 1024:.1f} KB")
        else:
            print(f"   📦 Taille: {file_size} bytes")
    
    def save_simulation_data_files(self):
        """
        Génère des fichiers de données de simulation individuels pour chaque game
        organisés dans des dossiers par layout.
        Structure: data_simulation/data_simu_<layoutname>/data_simu_<layoutname>_game_<numéro>.json
        """
        if not self.results:
            print("❌ Aucun résultat à sauvegarder")
            return
        
        # Créer le dossier data_simulation parent
        data_simulation_dir = "data_simulation"
        os.makedirs(data_simulation_dir, exist_ok=True)
        
        files_created = []
        total_games = 0
        
        for layout_name, layout_data in self.results.items():
            if not layout_data.get('viable', False):
                print(f"⚠️ Layout {layout_name} non viable, ignoré")
                continue
                
            # Extraire les données nécessaires
            individual_games = layout_data.get('individual_games', [])
            
            if not individual_games:
                print(f"⚠️ Pas de données de jeu individuelles pour {layout_name}")
                continue
            
            # Créer le dossier spécifique pour ce layout dans data_simulation
            layout_dir = os.path.join(data_simulation_dir, f"data_simu_{layout_name}")
            os.makedirs(layout_dir, exist_ok=True)
            
            # Traiter chaque game individuellement
            for game_idx, game_data in enumerate(individual_games):
                # Créer info_sum pour ce game spécifique
                info_sum = self._calculate_single_game_info_sum(game_data, layout_name)
                
                # Créer l'historique des positions pour ce game uniquement
                history_info = self._create_single_game_history_info(game_data, game_idx)
                
                # Valider la cohérence des mouvements pour ce game
                validation_results = self._validate_movement_coherence(history_info)
                
                if not validation_results['is_coherent']:
                    print(f"⚠️ Layout {layout_name}, Game {game_idx}: {validation_results['invalid_movements']} mouvements incohérents détectés")
                    print(f"   📊 {validation_results['total_movements_checked']} mouvements vérifiés au total")
                
                # Structure finale compatible avec data_collecter_simualtion
                simulation_data = {
                    "simulation_data": {
                        "info_sum": info_sum,
                        "history_info": history_info,
                        "grid": self._extract_grid_from_game_data(game_data, layout_name)
                    }
                }
                
                # Nom du fichier pour ce game
                filename = f"data_simu_{layout_name}_game_{game_idx}.json"
                filepath = os.path.join(layout_dir, filename)
                
                # Sauvegarder
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(simulation_data, f, indent=4, ensure_ascii=False)
                
                files_created.append(filepath)
                total_games += 1
            
            print(f"✅ Layout {layout_name}: {len(individual_games)} fichiers créés dans {layout_dir}/")
        
        print(f"\n📁 {len(files_created)} fichiers de données de simulation créés ({total_games} games total)")
        return files_created
    
    def _extract_grid_from_game_data(self, game_data: Dict, layout_name: str) -> List[List[str]]:
        """
        Extrait la grille utilisée pendant la simulation à partir des données du jeu.
        """
        try:
            # Récupérer la grille depuis les données du jeu (maintenant stockée)
            if 'mdp_terrain' in game_data:
                return game_data['mdp_terrain']
            
            # Si la grille n'est pas dans les données, la recréer depuis le layout
            # mais signaler que c'est une reconstruction
            print(f"⚠️ Grille non trouvée dans les données de simulation pour {layout_name}, reconstruction depuis le layout")
            
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Convertir terrain_mtx en format de liste pour JSON
            grid_as_list = []
            for row in mdp.terrain_mtx:
                grid_row = []
                for cell in row:
                    grid_row.append(str(cell))
                grid_as_list.append(grid_row)
            
            return grid_as_list
            
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction de la grille pour {layout_name}: {e}")
            # Retourner une grille vide en cas d'erreur
            return []
    
    def _verify_layout_grid_consistency(self, layout_name: str, mdp: OvercookedGridworld) -> Dict:
        """
        Vérifie la cohérence entre la grille du fichier .layout et celle chargée par OvercookedGridworld.
        """
        verification_result = {
            'has_discrepancy': False,
            'issues': [],
            'layout_file_found': False,
            'grid_comparison': None
        }
        
        try:
            # Charger la grille depuis le fichier .layout
            layout_path = f"overcooked_ai_py/data/layouts/generation_cesar/{layout_name}.layout"
            
            if not os.path.exists(layout_path):
                verification_result['issues'].append(f"Fichier .layout non trouvé: {layout_path}")
                return verification_result
            
            verification_result['layout_file_found'] = True
            
            with open(layout_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Extraire la grille avec regex
            import re
            pattern = r'"grid":\s*"""(.*?)"""'
            match = re.search(pattern, content, re.DOTALL)
            
            if not match:
                verification_result['issues'].append("Impossible d'extraire la grille du fichier .layout")
                return verification_result
            
            grid_content = match.group(1)
            grid_content = grid_content.replace('\t', '').strip()
            layout_grid_lines = [line.strip() for line in grid_content.split('\n') if line.strip()]
            
            # Comparer avec la grille MDP (terrain_mtx)
            mdp_grid_lines = []
            for row in mdp.terrain_mtx:
                mdp_grid_lines.append(''.join(row))
            
            # Normaliser les largeurs (padding avec des espaces)
            if layout_grid_lines and mdp_grid_lines:
                max_width_layout = max(len(line) for line in layout_grid_lines)
                max_width_mdp = max(len(line) for line in mdp_grid_lines)
                
                layout_grid_normalized = [line + ' ' * (max_width_layout - len(line)) for line in layout_grid_lines]
                mdp_grid_normalized = [line + ' ' * (max_width_mdp - len(line)) for line in mdp_grid_lines]
                
                # Comparer ligne par ligne
                discrepancies = []
                max_lines = max(len(layout_grid_normalized), len(mdp_grid_normalized))
                
                for i in range(max_lines):
                    layout_line = layout_grid_normalized[i] if i < len(layout_grid_normalized) else ''
                    mdp_line = mdp_grid_normalized[i] if i < len(mdp_grid_normalized) else ''
                    
                    if layout_line != mdp_line:
                        discrepancies.append({
                            'line': i,
                            'layout': layout_line,
                            'mdp': mdp_line
                        })
                
                if discrepancies:
                    verification_result['has_discrepancy'] = True
                    verification_result['grid_comparison'] = discrepancies
                    verification_result['issues'].append(f"{len(discrepancies)} lignes diffèrent entre .layout et MDP")
                    
                    # Détailler les premières différences
                    for i, diff in enumerate(discrepancies[:3]):  # Montrer seulement les 3 premières
                        verification_result['issues'].append(
                            f"Ligne {diff['line']}: layout='{diff['layout']}' vs mdp='{diff['mdp']}'"
                        )
                    
                    if len(discrepancies) > 3:
                        verification_result['issues'].append(f"... et {len(discrepancies) - 3} autres différences")
                
        except Exception as e:
            verification_result['issues'].append(f"Erreur lors de la vérification: {e}")
        
        return verification_result
    
    def _calculate_single_game_info_sum(self, game_data: Dict, layout_name: str) -> Dict:
        """
        Calcule les statistiques pour un seul game (pas d'agrégation).
        """
        if not game_data:
            return {}
        
        # Extraire les métriques du game individuel
        info_sum = game_data.get('info_sum', {})
        
        # Structure de base
        single_game_info = {
            "number_games": 1,  # Un seul game
            "layout": layout_name,
            "time_elapsed": game_data.get('timing', {}).get('total_time_seconds', 0),
            "ai_action_per_step": 1,  # Valeur constante
            "step": int(game_data.get('steps', 0)),
            "fps": game_data.get('timing', {}).get('actual_fps', 0),
            "time": game_data.get('timing', {}).get('simulated_time_seconds', 0),
            "recipe_completed": int(game_data.get('orders_completed', 0)),
            "score": int(game_data.get('total_reward', 0)),
            "min_recipe_complete": int(game_data.get('orders_completed', 0)),
            "max_recipe_complete": int(game_data.get('orders_completed', 0)),
        }
        
        # Ajouter les métriques d'actions pour chaque agent
        for agent_key in ['agent_0', 'agent_1']:
            agent_stats = game_data.get('agent_statistics', {}).get(agent_key, {})
            action_count = int(agent_stats.get('total_actions', 0))
            
            action_key = f'{agent_key}_action_count'
            single_game_info[action_key] = action_count
            single_game_info[f'min_{action_key}'] = action_count
            single_game_info[f'max_{action_key}'] = action_count
            single_game_info[f'std_{action_key}'] = 0.0  # Pas de variance pour un seul game
            
            # Ajouter mouvements et interactions
            single_game_info[f'{agent_key}_mouvements'] = int(agent_stats.get('distance_traveled', 0))
            single_game_info[f'{agent_key}_stuck_loop'] = 0  # À calculer si nécessaire
            single_game_info[f'{agent_key}_interaction'] = int(agent_stats.get('interact_count', 0))
        
        # Ajouter toutes les métriques comportementales du info_sum
        for key, value in info_sum.items():
            if key not in single_game_info:  # Éviter d'écraser les clés déjà définies
                single_game_info[key] = value
        
        # Ajouter all_orders (structure standard)
        single_game_info["all_orders"] = [
            {"ingredients": ["onion"]},
            {"ingredients": ["onion", "onion", "onion"]},
            {"ingredients": ["tomato"]},
            {"ingredients": ["tomato", "tomato", "tomato"]},
            {"ingredients": ["onion", "tomato"]}
        ]
        
        return single_game_info
    
    def _create_single_game_history_info(self, game_data: Dict, game_idx: int) -> Dict:
        """
        Crée l'historique des positions des agents pour un seul game.
        """
        history_info = {}
        game_key = f"history_game_0"  # Un seul game, donc toujours game_0
        
        # Extraire les trajectoires du jeu (si disponibles)
        trajectory = game_data.get('trajectory', [])
        
        # Créer l'historique des positions pour ce jeu
        history_entry = {
            "agent_0_history": {},
            "agent_1_history": {}
        }
        
        if trajectory and len(trajectory) > 0:
            # Collecter TOUS les steps de la simulation
            total_steps = len(trajectory)
            
            # Enregistrer tous les steps de la vraie simulation
            for step_idx in range(total_steps):
                if step_idx >= len(trajectory):
                    break
                    
                step_key = f"step_{step_idx}_position"
                step_data = trajectory[step_idx]
                
                # Extraire les vraies positions des agents à ce step précis
                if 'state' in step_data and 'players' in step_data['state']:
                    players = step_data['state']['players']
                    agent_0_pos = list(players[0].get('position', [0, 0])) if len(players) > 0 else [0, 0]
                    agent_1_pos = list(players[1].get('position', [0, 1])) if len(players) > 1 else [0, 1]
                    
                    # S'assurer que les positions sont des int Python standards
                    agent_0_pos = [int(x) for x in agent_0_pos]
                    agent_1_pos = [int(x) for x in agent_1_pos]
                else:
                    # Si pas de données pour ce step, utiliser la position précédente
                    if step_idx > 0:
                        prev_key = f"step_{step_idx-1}_position"
                        agent_0_pos = history_entry["agent_0_history"].get(prev_key, [1, 1])
                        agent_1_pos = history_entry["agent_1_history"].get(prev_key, [1, 2])
                    else:
                        agent_0_pos = [1, 1]
                        agent_1_pos = [1, 2]
                
                history_entry["agent_0_history"][step_key] = agent_0_pos
                history_entry["agent_1_history"][step_key] = agent_1_pos
                
            # Ajouter métadonnées réelles
            history_entry["_metadata"] = {
                "total_trajectory_steps": int(len(trajectory)),
                "recorded_steps": int(total_steps),
                "sampling_method": "complete_simulation_capture",
                "data_source": f"actual_simulation_game_{game_idx}"
            }
        else:
            # Aucune trajectoire disponible
            print(f"⚠️ Aucune trajectoire disponible pour game {game_idx} - aucune donnée de position collectée")
            history_entry["_metadata"] = {
                "total_trajectory_steps": 0,
                "recorded_steps": 0,
                "sampling_method": "no_data_available",
                "data_source": f"none_game_{game_idx}"
            }
        
        history_info[game_key] = [history_entry]
        return history_info
    
    def _calculate_aggregated_info_sum(self, individual_games: List[Dict], layout_name: str) -> Dict:
        """
        Calcule les statistiques agrégées (moyenne, écart-type, min, max) à partir des jeux individuels.
        """
        if not individual_games:
            return {}
        
        # Extraire toutes les métriques de tous les jeux
        all_metrics = {}
        for game in individual_games:
            info_sum = game.get('info_sum', {})
            for key, value in info_sum.items():
                if key not in all_metrics:
                    all_metrics[key] = []
                
                # Traiter différents types de valeurs
                if isinstance(value, list) and len(value) == 2:
                    # Format [agent_0, agent_1]
                    all_metrics[key].append(value)
                elif isinstance(value, (int, float)):
                    all_metrics[key].append([value, 0])  # Format standardisé [agent_0, agent_1]
                else:
                    all_metrics[key].append([0, 0])
        
        # Calculer les statistiques agrégées
        aggregated = {
            "number_games": len(individual_games),
            "layout": layout_name,
            "time_elapsed": np.mean([g.get('timing', {}).get('total_time_seconds', 0) for g in individual_games]),
            "ai_action_per_step": 1,  # Valeur constante
            "step": int(np.mean([g.get('steps', 0) for g in individual_games])),
            "fps": np.mean([g.get('timing', {}).get('actual_fps', 0) for g in individual_games]),
            "time": np.mean([g.get('timing', {}).get('simulated_time_seconds', 0) for g in individual_games]),
            "recipe_completed": int(np.mean([g.get('orders_completed', 0) for g in individual_games])),
            "score": int(np.mean([g.get('total_reward', 0) for g in individual_games])),
            "min_recipe_complete": int(np.min([g.get('orders_completed', 0) for g in individual_games])),
            "max_recipe_complete": int(np.max([g.get('orders_completed', 0) for g in individual_games])),
        }
        
        # Ajouter les métriques d'actions avec statistiques
        for agent_key in ['agent_0', 'agent_1']:
            values = [g.get('agent_statistics', {}).get(agent_key, {}).get('total_actions', 0) for g in individual_games]
            action_key = f'{agent_key}_action_count'
            aggregated[action_key] = int(np.mean(values))
            aggregated[f'min_{action_key}'] = int(np.min(values))
            aggregated[f'max_{action_key}'] = int(np.max(values))
            aggregated[f'std_{action_key}'] = float(np.std(values))
            
            # Ajouter mouvements et interactions
            movement_values = [g.get('agent_statistics', {}).get(agent_key, {}).get('distance_traveled', 0) for g in individual_games]
            interaction_values = [g.get('agent_statistics', {}).get(agent_key, {}).get('interact_count', 0) for g in individual_games]
            
            aggregated[f'{agent_key}_mouvements'] = int(np.mean(movement_values))
            aggregated[f'{agent_key}_stuck_loop'] = 0  # À calculer si nécessaire
            aggregated[f'{agent_key}_interaction'] = int(np.mean(interaction_values))
        
        # Ajouter les métriques comportementales agrégées
        for metric_name, values_list in all_metrics.items():
            if values_list and isinstance(values_list[0], list):
                # Calculer moyennes pour [agent_0, agent_1]
                agent_0_values = [v[0] for v in values_list if len(v) > 0]
                agent_1_values = [v[1] for v in values_list if len(v) > 1]
                
                aggregated[metric_name] = [
                    int(np.mean(agent_0_values)) if agent_0_values else 0,
                    int(np.mean(agent_1_values)) if agent_1_values else 0
                ]
        
        # Ajouter all_orders (structure standard)
        aggregated["all_orders"] = [
            {"ingredients": ["onion"]},
            {"ingredients": ["onion", "onion", "onion"]},
            {"ingredients": ["tomato"]},
            {"ingredients": ["tomato", "tomato", "tomato"]},
            {"ingredients": ["onion", "tomato"]}
        ]
        
        return aggregated
    
    def _create_history_info(self, individual_games: List[Dict]) -> Dict:
        """
        Crée l'historique des positions des agents pour chaque jeu.
        Collecte les vraies données de simulation step-by-step, pas d'échantillonnage.
        """
        history_info = {}
        
        for game_idx, game in enumerate(individual_games):
            game_key = f"history_game_{game_idx}"
            
            # Extraire les trajectoires du jeu (si disponibles)
            trajectory = game.get('trajectory', [])
            
            # Créer l'historique des positions pour ce jeu
            history_entry = {
                "agent_0_history": {},
                "agent_1_history": {}
            }
            
            if trajectory and len(trajectory) > 0:
                # Collecter TOUS les steps de la simulation (pas de limitation artificielle)
                total_steps = len(trajectory)
                
                # Enregistrer tous les steps de la vraie simulation
                for step_idx in range(total_steps):
                    if step_idx >= len(trajectory):
                        break
                        
                    step_key = f"step_{step_idx}_position"
                    step_data = trajectory[step_idx]
                    
                    # Extraire les vraies positions des agents à ce step précis
                    if 'state' in step_data and 'players' in step_data['state']:
                        players = step_data['state']['players']
                        agent_0_pos = list(players[0].get('position', [0, 0])) if len(players) > 0 else [0, 0]
                        agent_1_pos = list(players[1].get('position', [0, 1])) if len(players) > 1 else [0, 1]
                        
                        # S'assurer que les positions sont des int Python standards
                        agent_0_pos = [int(x) for x in agent_0_pos]
                        agent_1_pos = [int(x) for x in agent_1_pos]
                    else:
                        # Si pas de données pour ce step, utiliser la position précédente
                        if step_idx > 0:
                            prev_key = f"step_{step_idx-1}_position"
                            agent_0_pos = history_entry["agent_0_history"].get(prev_key, [1, 1])
                            agent_1_pos = history_entry["agent_1_history"].get(prev_key, [1, 2])
                        else:
                            agent_0_pos = [1, 1]
                            agent_1_pos = [1, 2]
                    
                    history_entry["agent_0_history"][step_key] = agent_0_pos
                    history_entry["agent_1_history"][step_key] = agent_1_pos
                    
                # Ajouter métadonnées réelles
                history_entry["_metadata"] = {
                    "total_trajectory_steps": int(len(trajectory)),
                    "recorded_steps": int(total_steps),
                    "sampling_method": "complete_simulation_capture",
                    "data_source": "actual_simulation"
                }
            else:
                # Aucune trajectoire disponible - signaler mais ne pas générer de fausses données
                print(f"⚠️ Aucune trajectoire disponible pour {game_key} - aucune donnée de position collectée")
                history_entry["_metadata"] = {
                    "total_trajectory_steps": 0,
                    "recorded_steps": 0,
                    "sampling_method": "no_data_available",
                    "data_source": "none"
                }
            
            history_info[game_key] = [history_entry]
        
        return history_info
    
    def _validate_movement_coherence(self, history_info: Dict) -> Dict:
        """
        Valide que tous les mouvements dans l'historique sont cohérents 
        (distance max de 1 case entre steps consécutifs).
        """
        validation_results = {
            'total_movements_checked': 0,
            'invalid_movements': 0,
            'invalid_movement_details': [],
            'is_coherent': True
        }
        
        for game_key, game_data in history_info.items():
            if not game_data or len(game_data) == 0:
                continue
                
            history_entry = game_data[0]
            
            for agent_key in ['agent_0_history', 'agent_1_history']:
                agent_history = history_entry.get(agent_key, {})
                positions = []
                
                # Extraire toutes les positions dans l'ordre
                step_numbers = []
                for step_key in agent_history.keys():
                    if step_key.startswith('step_') and step_key.endswith('_position'):
                        step_num = int(step_key.split('_')[1])
                        step_numbers.append(step_num)
                
                step_numbers.sort()
                
                for step_num in step_numbers:
                    step_key = f"step_{step_num}_position"
                    if step_key in agent_history:
                        positions.append(agent_history[step_key])
                
                # Vérifier les distances entre steps consécutifs
                for i in range(1, len(positions)):
                    pos_prev = positions[i-1]
                    pos_curr = positions[i]
                    
                    # Calculer la distance de Manhattan
                    distance = abs(pos_curr[0] - pos_prev[0]) + abs(pos_curr[1] - pos_prev[1])
                    
                    validation_results['total_movements_checked'] += 1
                    
                    if distance > 1:
                        validation_results['invalid_movements'] += 1
                        validation_results['is_coherent'] = False
                        validation_results['invalid_movement_details'].append({
                            'game': game_key,
                            'agent': agent_key,
                            'step_from': step_numbers[i-1],
                            'step_to': step_numbers[i],
                            'position_from': pos_prev,
                            'position_to': pos_curr,
                            'distance': distance
                        })
        
        return validation_results


def simulate_game_parallel(layout_name: str, game_id: int, evaluator_config: Dict) -> Dict:
    """
    Fonction pour simuler une partie en parallèle.
    Cette fonction est exécutée dans un processus séparé.
    """
    # Recréer l'évaluateur dans le processus worker
    evaluator = LayoutEvaluator(**evaluator_config)
    
    # Charger le MDP
    full_layout_path = f"generation_cesar/{layout_name}"
    mdp = OvercookedGridworld.from_layout_name(full_layout_path)
    
    # Créer les agents
    success, agent_or_group = evaluator.create_agent_group(mdp)
    if not success:
        return {
            'game_id': game_id,
            'error': 'Failed to create agents',
            'completed': False
        }
    
    # Simuler la partie
    return evaluator.simulate_single_game(mdp, agent_or_group, game_id)


def main():
    """Fonction principale."""
    import sys
    
    # Vérifier les arguments pour les différents modes
    single_agent_mode = '--solo' in sys.argv or '--single' in sys.argv
    greedy_with_stay_mode = '--stay' in sys.argv or '--greedy-stay' in sys.argv
    
    # Options d'optimisation
    parallel_mode = '--parallel' in sys.argv or '--fast' in sys.argv
    high_fps = '--speed' in sys.argv or '--turbo' in sys.argv
    
    # Paramètres d'optimisation
    target_fps = 100.0 if high_fps else 10.0
    max_workers = None
    
    # Déterminer le nombre de workers pour le parallélisme
    if parallel_mode:
        for i, arg in enumerate(sys.argv):
            if arg in ['--workers', '-w'] and i + 1 < len(sys.argv):
                try:
                    max_workers = int(sys.argv[i + 1])
                except ValueError:
                    pass
    
    # Déterminer le mode et la description
    if single_agent_mode:
        mode_description = "1x GreedyAgent (SOLO PUR)"
        filename_suffix = "solo"
    elif greedy_with_stay_mode:
        mode_description = "GreedyAgent + StayAgent"
        filename_suffix = "greedy_stay"
    else:
        mode_description = "2x GreedyAgent (COOP)"
        filename_suffix = "coop"
    
    if parallel_mode:
        mode_description += " [PARALLÈLE]"
        filename_suffix += "_parallel"
    elif high_fps:
        mode_description += " [HIGH SPEED]"
        filename_suffix += "_speed"
    
    print("🎮 ÉVALUATEUR DE LAYOUTS OVERCOOKED")
    print(f"🤖 Mode: {mode_description}")
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
        num_games_per_layout=10,  # Plusieurs parties pour moyenner
        target_fps=target_fps,
        parallel_games=parallel_mode,
        max_workers=max_workers,
        max_stuck_frames=50,  # Éviter les blocages infinis
        single_agent=single_agent_mode,  # Mode solo pur
        greedy_with_stay=greedy_with_stay_mode  # Mode GreedyAgent + StayAgent
    )
    
    # Lancer l'évaluation
    results = evaluator.evaluate_all_layouts()
    
    # Sauvegarder avec un nom différent selon le mode
    filename = f"layout_evaluation_{filename_suffix}.json"
    # Sauvegarder seulement les métriques agrégées par layout (pas les parties individuelles)
    evaluator.save_results(filename, include_individual_games=False)
    
    # Générer les fichiers de données de simulation individuels
    print(f"\n🔄 GÉNÉRATION DES FICHIERS DE DONNÉES DE SIMULATION...")
    simulation_files = evaluator.save_simulation_data_files()
    
    print(f"\n🎯 ÉVALUATION TERMINÉE!")
    print(f"   📊 Mode: {mode_description}")
    print(f"   📊 Métriques comportementales complètes par layout")
    print(f"   💾 Résultats agrégés sauvegardés dans {filename}")
    print(f"   📁 {len(simulation_files)} fichiers de simulation créés dans dossiers individuels par layout")
    
    # Optionnel: sauvegarder aussi le fichier détaillé pour debug
    if '--debug' in sys.argv or '--detailed' in sys.argv:
        detailed_filename = f"layout_evaluation_{filename_suffix}_detailed.json"
        evaluator.save_results(detailed_filename, include_individual_games=True)
        print(f"   � Résultats détaillés sauvegardés dans {detailed_filename}")
    
    print(f"\n💡 MODES DISPONIBLES:")
    print(f"   • Mode coopératif (défaut): python {sys.argv[0]}")
    print(f"   • Mode solo pur: python {sys.argv[0]} --solo")
    print(f"   • Mode GreedyAgent + StayAgent: python {sys.argv[0]} --stay")
    print(f"   • Mode parallèle: python {sys.argv[0]} --parallel [--workers N]")
    print(f"   • Mode haute vitesse: python {sys.argv[0]} --speed")
    print(f"   • Ajouter --debug pour sauvegarder aussi les détails complets")
    print(f"\n🚀 OPTIONS D'OPTIMISATION:")
    print(f"   • --parallel : Exécute les parties en parallèle")
    print(f"   • --workers N : Nombre de processus parallèles (défaut: auto)")
    print(f"   • --speed : FPS élevé (100 FPS au lieu de 10)")
    print(f"   • --fast : Équivalent à --parallel --speed")
    print(f"\n📂 FICHIERS GÉNÉRÉS:")
    print(f"   • {filename}: Métriques agrégées par layout")
    print(f"   • data_simulation/data_simu_<layoutname>/: Dossiers individuels par layout")
    print(f"   • data_simu_<layoutname>_game_<N>.json: Un fichier par game joué")


if __name__ == "__main__":
    main()
