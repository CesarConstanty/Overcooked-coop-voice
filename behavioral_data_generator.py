#!/usr/bin/env python3
"""
behavioral_data_generator.py

Générateur de données comportementales complètes pour GreedyAgent dans différents layouts.
Produit des données exhaustives pour caractériser précisément le comportement des agents
et les propriétés des layouts.

OBJECTIF: Collecter toutes les métriques comportementales nécessaires pour une analyse
approfondie des interactions agent-layout.
"""

import os
import json
import time
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from pathlib import Path
import argparse

from overcooked_ai_py.agents.agent import GreedyAgent, AgentGroup
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld, EVENT_TYPES
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.mdp.actions import Action
from overcooked_ai_py.planning.planners import NO_COUNTERS_PARAMS


class StayAgent:
    """Agent qui reste immobile pour les tests comparatifs."""
    
    def __init__(self):
        self.agent_index = None
        self.mdp = None
    
    def action(self, state):
        return Action.STAY, {}
    
    def set_agent_index(self, agent_index):
        self.agent_index = agent_index
    
    def set_mdp(self, mdp):
        self.mdp = mdp
    
    def reset(self):
        pass


class BehavioralDataGenerator:
    """
    Générateur de données comportementales exhaustives pour caractériser
    le comportement des GreedyAgent dans différents layouts.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 600, num_games_per_layout: int = 10):
        """
        Initialise le générateur de données comportementales.
        
        Args:
            layouts_directory: Répertoire contenant les layouts à analyser
            horizon: Nombre maximum de steps par partie
            num_games_per_layout: Nombre de parties par layout pour avoir des statistiques robustes
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.results = {}
        
        print(f"🔬 GÉNÉRATEUR DE DONNÉES COMPORTEMENTALES")
        print(f"📁 Layouts: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"📊 Types d'événements trackés: {len(EVENT_TYPES)}")
    
    def discover_layouts(self) -> List[str]:
        """Découvre tous les layouts disponibles."""
        import glob
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names}")
        return layout_names
    
    def generate_complete_behavioral_data(self, output_file: str = "behavioral_data_complete.json") -> Dict:
        """
        Génère des données comportementales complètes pour tous les layouts.
        """
        print(f"\n🚀 GÉNÉRATION DE DONNÉES COMPORTEMENTALES COMPLÈTES")
        print(f"=" * 60)
        
        layout_names = self.discover_layouts()
        
        complete_data = {
            'metadata': {
                'generation_timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'layouts_analyzed': len(layout_names),
                'games_per_layout': self.num_games_per_layout,
                'horizon': self.horizon,
                'event_types_tracked': EVENT_TYPES,
                'analysis_modes': ['cooperative', 'solo', 'greedy_with_stay']
            },
            'layouts': {}
        }
        
        for layout_name in layout_names:
            print(f"\n📋 Analyse comportementale: {layout_name}")
            print("-" * 40)
            
            layout_data = self._analyze_layout_behavior_complete(layout_name)
            complete_data['layouts'][layout_name] = layout_data
            
            # Sauvegarder progressivement
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(complete_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Données comportementales complètes sauvegardées: {output_file}")
        return complete_data
    
    def _analyze_layout_behavior_complete(self, layout_name: str) -> Dict:
        """
        Analyse comportementale complète d'un layout spécifique.
        """
        layout_analysis = {
            'layout_info': self._get_layout_info(layout_name),
            'behavioral_modes': {},
            'comparative_analysis': {},
            'layout_characteristics': {},
            'agent_behavior_patterns': {},
            'performance_metrics': {},
            'coordination_analysis': {},
            'difficulty_assessment': {}
        }
        
        # Analyser le comportement dans différents modes
        modes = [
            ('cooperative', False, False),
            ('solo', True, False),
            ('greedy_with_stay', False, True)
        ]
        
        for mode_name, single_agent, greedy_with_stay in modes:
            print(f"  🤖 Mode {mode_name}...")
            mode_data = self._analyze_behavior_in_mode(
                layout_name, mode_name, single_agent, greedy_with_stay
            )
            layout_analysis['behavioral_modes'][mode_name] = mode_data
        
        # Analyse comparative entre modes
        layout_analysis['comparative_analysis'] = self._compare_modes(
            layout_analysis['behavioral_modes']
        )
        
        # Caractérisation du layout
        layout_analysis['layout_characteristics'] = self._characterize_layout(
            layout_analysis['behavioral_modes']
        )
        
        # Patterns de comportement des agents
        layout_analysis['agent_behavior_patterns'] = self._analyze_agent_patterns(
            layout_analysis['behavioral_modes']
        )
        
        # Métriques de performance
        layout_analysis['performance_metrics'] = self._calculate_performance_metrics(
            layout_analysis['behavioral_modes']
        )
        
        # Analyse de coordination
        layout_analysis['coordination_analysis'] = self._analyze_coordination_requirements(
            layout_analysis['behavioral_modes']
        )
        
        # Évaluation de difficulté
        layout_analysis['difficulty_assessment'] = self._assess_layout_difficulty(
            layout_analysis['behavioral_modes']
        )
        
        return layout_analysis
    
    def _get_layout_info(self, layout_name: str) -> Dict:
        """Extrait les informations structurelles du layout."""
        layout_path = os.path.join(self.layouts_directory, f"{layout_name}.layout")
        
        try:
            with open(layout_path, 'r') as f:
                layout_content = f.read()
            
            # Parser le contenu du layout
            layout_dict = eval(layout_content)  # Note: en production, utiliser ast.literal_eval
            
            grid = layout_dict.get('grid', '')
            grid_lines = [line.strip() for line in grid.strip().split('\n') if line.strip()]
            
            # Analyser la structure
            height = len(grid_lines)
            width = max(len(line) for line in grid_lines) if grid_lines else 0
            
            # Compter les éléments
            elements = {
                'tomato_dispensers': 0,
                'onion_dispensers': 0,
                'pots': 0,
                'counters': 0,
                'serving_areas': 0,
                'dish_dispensers': 0,
                'start_positions': 0
            }
            
            for line in grid_lines:
                elements['tomato_dispensers'] += line.count('T')
                elements['onion_dispensers'] += line.count('O')
                elements['pots'] += line.count('P')
                elements['counters'] += line.count(' ')
                elements['serving_areas'] += line.count('S')
                elements['dish_dispensers'] += line.count('D')
                elements['start_positions'] += line.count('1') + line.count('2')
            
            return {
                'layout_name': layout_name,
                'dimensions': {'width': width, 'height': height},
                'total_cells': width * height,
                'elements': elements,
                'orders': layout_dict.get('start_all_orders', []),
                'ingredient_values': {
                    'onion_value': layout_dict.get('onion_value', 21),
                    'tomato_value': layout_dict.get('tomato_value', 13),
                    'onion_time': layout_dict.get('onion_time', 15),
                    'tomato_time': layout_dict.get('tomato_time', 7)
                }
            }
            
        except Exception as e:
            print(f"    ⚠️ Erreur lecture layout {layout_name}: {e}")
            return {'layout_name': layout_name, 'error': str(e)}
    
    def _analyze_behavior_in_mode(self, layout_name: str, mode_name: str, 
                                single_agent: bool, greedy_with_stay: bool) -> Dict:
        """
        Analyse le comportement dans un mode spécifique.
        """
        try:
            # Créer le MDP
            mdp = OvercookedGridworld.from_layout_name(layout_name)
            
            # Créer les agents
            if single_agent:
                agent = GreedyAgent(auto_unstuck=True)
                agent.set_mdp(mdp)
                agent.set_agent_index(0)
                agent_group = agent
            elif greedy_with_stay:
                agent_0 = GreedyAgent(auto_unstuck=True)
                agent_1 = StayAgent()
                agent_group = AgentGroup(agent_0, agent_1)
                agent_group.set_mdp(mdp)
            else:
                agent_0 = GreedyAgent(auto_unstuck=True)
                agent_1 = GreedyAgent(auto_unstuck=True)
                agent_group = AgentGroup(agent_0, agent_1)
                agent_group.set_mdp(mdp)
            
            # Collecter les données sur plusieurs parties
            games_data = []
            for game_id in range(self.num_games_per_layout):
                game_data = self._simulate_game_with_detailed_tracking(
                    mdp, agent_group, game_id, single_agent
                )
                games_data.append(game_data)
            
            # Analyser les données collectées
            mode_analysis = self._analyze_games_data(games_data, mode_name)
            mode_analysis['raw_games'] = games_data
            
            return mode_analysis
            
        except Exception as e:
            print(f"    ❌ Erreur mode {mode_name}: {e}")
            return {'error': str(e), 'mode': mode_name}
    
    def _simulate_game_with_detailed_tracking(self, mdp: OvercookedGridworld, 
                                            agent_group, game_id: int, single_agent: bool) -> Dict:
        """
        Simule une partie avec un tracking détaillé de tous les événements
        et comportements pour l'analyse comportementale.
        """
        game_data = {
            'game_id': game_id,
            'completed': False,
            'steps': 0,
            'total_reward': 0,
            'trajectory': [],
            'event_sequence': [],
            'agent_states': [],
            'coordination_events': [],
            'decision_points': [],
            'efficiency_timeline': [],
            'spatial_movement': {'agent_0': [], 'agent_1': []},
            'task_allocation': [],
            'bottleneck_events': [],
            'info_sum': {event_type: [0, 0] for event_type in EVENT_TYPES}
        }
        
        try:
            state = mdp.get_standard_start_state()
            stuck_frames = 0
            last_positions = None
            
            for step in range(self.horizon):
                step_start_time = time.time()
                
                # Enregistrer l'état avant action
                state_snapshot = self._capture_state_snapshot(state, step)
                game_data['agent_states'].append(state_snapshot)
                
                # Obtenir les actions
                if single_agent:
                    action_0, _ = agent_group.action(state)
                    joint_action = [action_0, Action.STAY]
                else:
                    joint_action_and_infos = agent_group.joint_action(state)
                    joint_action = [action_info[0] for action_info in joint_action_and_infos]
                
                # Enregistrer les positions pour tracking spatial
                for agent_idx, player in enumerate(state.players):
                    agent_key = f'agent_{agent_idx}'
                    if agent_key in game_data['spatial_movement']:
                        game_data['spatial_movement'][agent_key].append({
                            'step': step,
                            'position': player.position,
                            'action': joint_action[agent_idx],
                            'held_object': player.held_object.name if player.held_object else None
                        })
                
                # Exécuter l'action
                next_state, info = mdp.get_state_transition(state, joint_action)
                
                # Enregistrer les événements
                event_infos = info.get('event_infos', {})
                self._fix_missing_events(event_infos, state, next_state)
                
                # Accumuler les événements pour info_sum
                for event_type, agent_bools in event_infos.items():
                    if event_type in game_data['info_sum']:
                        for agent_idx, occurred in enumerate(agent_bools):
                            if occurred and agent_idx < 2:
                                game_data['info_sum'][event_type][agent_idx] += 1
                
                # Enregistrer l'événement avec contexte
                event_record = {
                    'step': step,
                    'events': event_infos,
                    'actions': joint_action,
                    'reward': sum(info['sparse_reward_by_agent']),
                    'state_change': self._analyze_state_change(state, next_state)
                }
                game_data['event_sequence'].append(event_record)
                
                # Détecter les points de décision critiques
                decision_point = self._detect_decision_point(state, next_state, joint_action, event_infos)
                if decision_point:
                    game_data['decision_points'].append(decision_point)
                
                # Détecter les événements de coordination
                coordination_event = self._detect_coordination_event(event_infos, state, next_state)
                if coordination_event:
                    game_data['coordination_events'].append(coordination_event)
                
                # Analyser l'allocation des tâches
                task_allocation = self._analyze_task_allocation(state, next_state, joint_action)
                game_data['task_allocation'].append(task_allocation)
                
                # Calculer l'efficacité instantanée
                efficiency = self._calculate_step_efficiency(state, next_state, joint_action, event_infos)
                game_data['efficiency_timeline'].append(efficiency)
                
                # Mettre à jour les métriques de jeu
                game_data['total_reward'] += sum(info['sparse_reward_by_agent'])
                game_data['steps'] = step + 1
                
                # Vérifier la complétion
                if len(next_state.all_orders) == 0:
                    game_data['completed'] = True
                    break
                
                # Détecter les blocages
                current_positions = [player.position for player in next_state.players]
                if current_positions == last_positions:
                    stuck_frames += 1
                    if stuck_frames >= 50:  # Max stuck frames
                        game_data['bottleneck_events'].append({
                            'step': step,
                            'type': 'stuck_agents',
                            'duration': stuck_frames,
                            'positions': current_positions
                        })
                        break
                else:
                    stuck_frames = 0
                last_positions = current_positions
                
                state = next_state
            
            # Post-traitement des données de jeu
            game_data = self._post_process_game_data(game_data)
            
        except Exception as e:
            print(f"      ❌ Erreur simulation partie {game_id}: {e}")
            game_data['error'] = str(e)
        
        return game_data
    
    def _capture_state_snapshot(self, state, step: int) -> Dict:
        """Capture un snapshot détaillé de l'état pour analyse."""
        return {
            'step': step,
            'players': [
                {
                    'position': player.position,
                    'orientation': player.orientation,
                    'held_object': player.held_object.name if player.held_object else None
                }
                for player in state.players
            ],
            'pots': [
                {
                    'position': pos,
                    'contents': pot.ingredients,
                    'cooking_time': pot.cook_time,
                    'is_ready': pot.is_ready
                }
                for pos, pot in state.objects.items() if hasattr(pot, 'ingredients')
            ],
            'counters': [
                {
                    'position': pos,
                    'object': obj.name if obj else None
                }
                for pos, obj in state.objects.items() if not hasattr(obj, 'ingredients')
            ],
            'orders_remaining': len(state.all_orders),
            'orders': [order.ingredients for order in state.all_orders]
        }
    
    def _fix_missing_events(self, event_infos: Dict, prev_state, current_state):
        """Corrige les événements manqués par le système Overcooked."""
        # Fix pour les pickups de tomates manqués
        if 'tomato_pickup' not in event_infos:
            event_infos['tomato_pickup'] = [False, False]
        if 'useful_tomato_pickup' not in event_infos:
            event_infos['useful_tomato_pickup'] = [False, False]
        
        for agent_idx in range(len(prev_state.players)):
            prev_player = prev_state.players[agent_idx]
            current_player = current_state.players[agent_idx]
            
            # Détecter pickup de tomate
            prev_has_tomato = (prev_player.held_object is not None and 
                              prev_player.held_object.name == 'tomato')
            current_has_tomato = (current_player.held_object is not None and 
                                 current_player.held_object.name == 'tomato')
            
            if not prev_has_tomato and current_has_tomato:
                event_infos['tomato_pickup'][agent_idx] = True
                event_infos['useful_tomato_pickup'][agent_idx] = True
    
    def _analyze_state_change(self, prev_state, current_state) -> Dict:
        """Analyse les changements entre deux états."""
        changes = {
            'player_movements': [],
            'object_pickups': [],
            'object_drops': [],
            'pot_changes': [],
            'order_completions': 0
        }
        
        # Mouvements des joueurs
        for i, (prev_player, current_player) in enumerate(zip(prev_state.players, current_state.players)):
            if prev_player.position != current_player.position:
                changes['player_movements'].append({
                    'agent': i,
                    'from': prev_player.position,
                    'to': current_player.position
                })
            
            # Changements d'objets tenus
            prev_obj = prev_player.held_object.name if prev_player.held_object else None
            current_obj = current_player.held_object.name if current_player.held_object else None
            
            if prev_obj != current_obj:
                if prev_obj is None and current_obj is not None:
                    changes['object_pickups'].append({'agent': i, 'object': current_obj})
                elif prev_obj is not None and current_obj is None:
                    changes['object_drops'].append({'agent': i, 'object': prev_obj})
        
        # Changements de commandes
        changes['order_completions'] = len(prev_state.all_orders) - len(current_state.all_orders)
        
        return changes
    
    def _detect_decision_point(self, state, next_state, joint_action, event_infos) -> Optional[Dict]:
        """Détecte les points de décision critiques."""
        # Point de décision si un agent interagit ou change de direction
        for agent_idx, action in enumerate(joint_action):
            if action == Action.INTERACT:
                return {
                    'step': len(state.players),  # Approximation du step
                    'agent': agent_idx,
                    'type': 'interaction',
                    'action': action,
                    'context': {
                        'position': state.players[agent_idx].position,
                        'held_object': state.players[agent_idx].held_object.name if state.players[agent_idx].held_object else None,
                        'events_triggered': [event for event, bools in event_infos.items() if bools[agent_idx]]
                    }
                }
        
        return None
    
    def _detect_coordination_event(self, event_infos, state, next_state) -> Optional[Dict]:
        """Détecte les événements de coordination entre agents."""
        coordination_events = ['tomato_exchange', 'onion_exchange', 'dish_exchange', 'soup_exchange']
        
        for event_type in coordination_events:
            if event_type in event_infos and any(event_infos[event_type]):
                return {
                    'type': event_type,
                    'agents_involved': [i for i, involved in enumerate(event_infos[event_type]) if involved],
                    'context': {
                        'agent_positions': [player.position for player in state.players],
                        'agent_objects': [player.held_object.name if player.held_object else None for player in state.players]
                    }
                }
        
        return None
    
    def _analyze_task_allocation(self, state, next_state, joint_action) -> Dict:
        """Analyse l'allocation des tâches entre agents."""
        allocation = {
            'agent_0': {'task': 'unknown', 'efficiency': 0},
            'agent_1': {'task': 'unknown', 'efficiency': 0}
        }
        
        for agent_idx, action in enumerate(joint_action):
            player = state.players[agent_idx]
            
            # Déterminer la tâche basée sur l'action et le contexte
            if action == Action.INTERACT:
                if player.held_object is None:
                    allocation[f'agent_{agent_idx}']['task'] = 'pickup'
                elif player.held_object.name in ['tomato', 'onion']:
                    allocation[f'agent_{agent_idx}']['task'] = 'ingredient_handling'
                elif player.held_object.name == 'dish':
                    allocation[f'agent_{agent_idx}']['task'] = 'dish_handling'
                elif player.held_object.name == 'soup':
                    allocation[f'agent_{agent_idx}']['task'] = 'delivery'
            elif action in [Action.NORTH, Action.SOUTH, Action.EAST, Action.WEST]:
                allocation[f'agent_{agent_idx}']['task'] = 'movement'
            else:
                allocation[f'agent_{agent_idx}']['task'] = 'idle'
        
        return allocation
    
    def _calculate_step_efficiency(self, state, next_state, joint_action, event_infos) -> Dict:
        """Calcule l'efficacité instantanée du step."""
        efficiency = {
            'productive_actions': 0,
            'wasted_actions': 0,
            'coordination_score': 0,
            'progress_score': 0
        }
        
        # Compter les actions productives
        productive_events = ['soup_delivery', 'soup_pickup', 'potting_onion', 'potting_tomato', 
                           'useful_onion_pickup', 'useful_tomato_pickup', 'useful_dish_pickup']
        
        for event_type in productive_events:
            if event_type in event_infos:
                efficiency['productive_actions'] += sum(event_infos[event_type])
        
        # Progression (réduction du nombre de commandes)
        efficiency['progress_score'] = len(state.all_orders) - len(next_state.all_orders)
        
        return efficiency
    
    def _post_process_game_data(self, game_data: Dict) -> Dict:
        """Post-traitement des données de jeu pour l'analyse."""
        # Calculer des métriques dérivées
        game_data['derived_metrics'] = {
            'movement_efficiency': self._calculate_movement_efficiency(game_data['spatial_movement']),
            'coordination_frequency': len(game_data['coordination_events']) / max(game_data['steps'], 1),
            'decision_density': len(game_data['decision_points']) / max(game_data['steps'], 1),
            'task_distribution': self._analyze_task_distribution(game_data['task_allocation']),
            'efficiency_trend': self._analyze_efficiency_trend(game_data['efficiency_timeline']),
            'bottleneck_analysis': self._analyze_bottlenecks(game_data['bottleneck_events'])
        }
        
        return game_data
    
    def _calculate_movement_efficiency(self, spatial_movement: Dict) -> Dict:
        """Calcule l'efficacité de mouvement des agents."""
        efficiency = {}
        
        for agent_key, movements in spatial_movement.items():
            if not movements:
                efficiency[agent_key] = {'total_distance': 0, 'unique_positions': 0, 'backtracking': 0}
                continue
            
            total_distance = 0
            positions_visited = set()
            backtrack_count = 0
            position_history = []
            
            for movement in movements:
                pos = movement['position']
                positions_visited.add(pos)
                position_history.append(pos)
                
                if len(position_history) > 1:
                    prev_pos = position_history[-2]
                    distance = abs(pos[0] - prev_pos[0]) + abs(pos[1] - prev_pos[1])
                    total_distance += distance
                    
                    # Détecter le backtracking
                    if len(position_history) > 2 and pos == position_history[-3]:
                        backtrack_count += 1
            
            efficiency[agent_key] = {
                'total_distance': total_distance,
                'unique_positions': len(positions_visited),
                'backtracking': backtrack_count,
                'efficiency_ratio': len(positions_visited) / max(total_distance, 1)
            }
        
        return efficiency
    
    def _analyze_task_distribution(self, task_allocation: List[Dict]) -> Dict:
        """Analyse la distribution des tâches entre agents."""
        task_counts = {'agent_0': Counter(), 'agent_1': Counter()}
        
        for allocation in task_allocation:
            for agent_key, task_info in allocation.items():
                task_counts[agent_key][task_info['task']] += 1
        
        return {
            'agent_0_tasks': dict(task_counts['agent_0']),
            'agent_1_tasks': dict(task_counts['agent_1']),
            'specialization_score': self._calculate_specialization_score(task_counts)
        }
    
    def _calculate_specialization_score(self, task_counts: Dict) -> float:
        """Calcule un score de spécialisation entre agents."""
        # Score basé sur la différence de distribution des tâches
        agent_0_dist = task_counts['agent_0']
        agent_1_dist = task_counts['agent_1']
        
        all_tasks = set(agent_0_dist.keys()) | set(agent_1_dist.keys())
        
        if not all_tasks:
            return 0.0
        
        specialization = 0.0
        for task in all_tasks:
            count_0 = agent_0_dist.get(task, 0)
            count_1 = agent_1_dist.get(task, 0)
            total = count_0 + count_1
            
            if total > 0:
                # Plus la différence est grande, plus il y a spécialisation
                specialization += abs(count_0 - count_1) / total
        
        return specialization / len(all_tasks)
    
    def _analyze_efficiency_trend(self, efficiency_timeline: List[Dict]) -> Dict:
        """Analyse la tendance d'efficacité au cours du temps."""
        if not efficiency_timeline:
            return {'trend': 'no_data', 'avg_efficiency': 0}
        
        productive_scores = [ef['productive_actions'] for ef in efficiency_timeline]
        progress_scores = [ef['progress_score'] for ef in efficiency_timeline]
        
        return {
            'avg_productive_actions': np.mean(productive_scores),
            'avg_progress_score': np.mean(progress_scores),
            'efficiency_variance': np.var(productive_scores),
            'trend': 'improving' if len(productive_scores) > 1 and productive_scores[-1] > productive_scores[0] else 'stable'
        }
    
    def _analyze_bottlenecks(self, bottleneck_events: List[Dict]) -> Dict:
        """Analyse les événements de goulots d'étranglement."""
        return {
            'total_bottlenecks': len(bottleneck_events),
            'types': Counter([event['type'] for event in bottleneck_events]),
            'avg_duration': np.mean([event.get('duration', 0) for event in bottleneck_events]) if bottleneck_events else 0
        }
    
    def _analyze_games_data(self, games_data: List[Dict], mode_name: str) -> Dict:
        """Analyse les données de toutes les parties d'un mode."""
        analysis = {
            'mode': mode_name,
            'total_games': len(games_data),
            'completed_games': sum(1 for game in games_data if game.get('completed', False)),
            'success_rate': 0,
            'performance_metrics': {},
            'behavioral_patterns': {},
            'coordination_analysis': {},
            'efficiency_analysis': {},
            'spatial_analysis': {},
            'temporal_analysis': {}
        }
        
        completed_games = [game for game in games_data if game.get('completed', False)]
        analysis['success_rate'] = len(completed_games) / len(games_data) if games_data else 0
        
        if completed_games:
            # Métriques de performance
            analysis['performance_metrics'] = {
                'avg_completion_steps': np.mean([game['steps'] for game in completed_games]),
                'std_completion_steps': np.std([game['steps'] for game in completed_games]),
                'min_completion_steps': min(game['steps'] for game in completed_games),
                'max_completion_steps': max(game['steps'] for game in completed_games),
                'avg_total_reward': np.mean([game['total_reward'] for game in completed_games]),
                'completion_efficiency': np.mean([game['total_reward'] / game['steps'] for game in completed_games])
            }
            
            # Patterns comportementaux
            analysis['behavioral_patterns'] = self._extract_behavioral_patterns(completed_games)
            
            # Analyse de coordination
            analysis['coordination_analysis'] = self._analyze_coordination_patterns(completed_games)
            
            # Analyse d'efficacité
            analysis['efficiency_analysis'] = self._analyze_efficiency_patterns(completed_games)
            
            # Analyse spatiale
            analysis['spatial_analysis'] = self._analyze_spatial_patterns(completed_games)
            
            # Analyse temporelle
            analysis['temporal_analysis'] = self._analyze_temporal_patterns(completed_games)
        
        return analysis
    
    def _extract_behavioral_patterns(self, games_data: List[Dict]) -> Dict:
        """Extrait les patterns comportementaux des données de jeu."""
        patterns = {
            'dominant_strategies': {},
            'agent_specialization': {},
            'common_sequences': {},
            'decision_patterns': {}
        }
        
        # Analyser les stratégies dominantes
        all_task_distributions = []
        for game in games_data:
            if 'derived_metrics' in game and 'task_distribution' in game['derived_metrics']:
                all_task_distributions.append(game['derived_metrics']['task_distribution'])
        
        if all_task_distributions:
            patterns['agent_specialization'] = self._identify_specialization_patterns(all_task_distributions)
        
        # Analyser les séquences communes d'événements
        all_event_sequences = []
        for game in games_data:
            if 'event_sequence' in game:
                sequence = [event['events'] for event in game['event_sequence']]
                all_event_sequences.append(sequence)
        
        patterns['common_sequences'] = self._find_common_event_sequences(all_event_sequences)
        
        return patterns
    
    def _identify_specialization_patterns(self, task_distributions: List[Dict]) -> Dict:
        """Identifie les patterns de spécialisation des agents."""
        specialization_scores = []
        agent_0_roles = Counter()
        agent_1_roles = Counter()
        
        for dist in task_distributions:
            specialization_scores.append(dist.get('specialization_score', 0))
            
            # Identifier le rôle dominant de chaque agent
            agent_0_tasks = dist.get('agent_0_tasks', {})
            agent_1_tasks = dist.get('agent_1_tasks', {})
            
            if agent_0_tasks:
                dominant_task_0 = max(agent_0_tasks.items(), key=lambda x: x[1])[0]
                agent_0_roles[dominant_task_0] += 1
            
            if agent_1_tasks:
                dominant_task_1 = max(agent_1_tasks.items(), key=lambda x: x[1])[0]
                agent_1_roles[dominant_task_1] += 1
        
        return {
            'avg_specialization_score': np.mean(specialization_scores),
            'specialization_consistency': 1 - np.std(specialization_scores),
            'agent_0_dominant_roles': dict(agent_0_roles.most_common(3)),
            'agent_1_dominant_roles': dict(agent_1_roles.most_common(3))
        }
    
    def _find_common_event_sequences(self, event_sequences: List[List]) -> Dict:
        """Trouve les séquences d'événements communes."""
        # Simplification : chercher les patterns de 3 événements consécutifs
        pattern_counts = Counter()
        
        for sequence in event_sequences:
            for i in range(len(sequence) - 2):
                # Créer un pattern basé sur les types d'événements
                pattern = []
                for j in range(3):
                    events = sequence[i + j]
                    main_event = self._get_main_event(events)
                    pattern.append(main_event)
                
                pattern_tuple = tuple(pattern)
                pattern_counts[pattern_tuple] += 1
        
        return {
            'most_common_patterns': dict(pattern_counts.most_common(5)),
            'total_unique_patterns': len(pattern_counts),
            'pattern_diversity': len(pattern_counts) / max(sum(pattern_counts.values()), 1)
        }
    
    def _get_main_event(self, events: Dict) -> str:
        """Obtient l'événement principal d'un dict d'événements."""
        priority_events = ['soup_delivery', 'soup_pickup', 'potting_onion', 'potting_tomato', 
                          'onion_pickup', 'tomato_pickup', 'dish_pickup']
        
        for event_type in priority_events:
            if event_type in events and any(events[event_type]):
                return event_type
        
        return 'no_significant_event'
    
    def _analyze_coordination_patterns(self, games_data: List[Dict]) -> Dict:
        """Analyse les patterns de coordination."""
        coordination_metrics = {
            'avg_coordination_events': 0,
            'coordination_types': Counter(),
            'coordination_timing': [],
            'coordination_effectiveness': []
        }
        
        all_coordination_events = []
        for game in games_data:
            coord_events = game.get('coordination_events', [])
            all_coordination_events.extend(coord_events)
            
            # Timing de coordination (quand dans le jeu)
            for event in coord_events:
                # Approximation du timing basé sur le contexte
                coordination_metrics['coordination_timing'].append(len(coord_events))
        
        if all_coordination_events:
            coordination_metrics['avg_coordination_events'] = len(all_coordination_events) / len(games_data)
            coordination_metrics['coordination_types'] = Counter([event['type'] for event in all_coordination_events])
        
        return coordination_metrics
    
    def _analyze_efficiency_patterns(self, games_data: List[Dict]) -> Dict:
        """Analyse les patterns d'efficacité."""
        efficiency_metrics = {
            'movement_efficiency': {'agent_0': [], 'agent_1': []},
            'task_efficiency': [],
            'overall_efficiency_trend': []
        }
        
        for game in games_data:
            if 'derived_metrics' in game:
                dm = game['derived_metrics']
                
                # Efficacité de mouvement
                if 'movement_efficiency' in dm:
                    for agent_key, metrics in dm['movement_efficiency'].items():
                        if agent_key in efficiency_metrics['movement_efficiency']:
                            efficiency_metrics['movement_efficiency'][agent_key].append(
                                metrics.get('efficiency_ratio', 0)
                            )
                
                # Tendance d'efficacité
                if 'efficiency_trend' in dm:
                    efficiency_metrics['overall_efficiency_trend'].append(
                        dm['efficiency_trend'].get('avg_productive_actions', 0)
                    )
        
        # Calculer les moyennes
        for agent_key in efficiency_metrics['movement_efficiency']:
            values = efficiency_metrics['movement_efficiency'][agent_key]
            efficiency_metrics['movement_efficiency'][agent_key] = {
                'avg': np.mean(values) if values else 0,
                'std': np.std(values) if values else 0
            }
        
        return efficiency_metrics
    
    def _analyze_spatial_patterns(self, games_data: List[Dict]) -> Dict:
        """Analyse les patterns spatiaux de mouvement."""
        spatial_metrics = {
            'coverage_analysis': {},
            'movement_patterns': {},
            'territory_analysis': {}
        }
        
        all_positions = {'agent_0': [], 'agent_1': []}
        
        for game in games_data:
            spatial_movement = game.get('spatial_movement', {})
            for agent_key, movements in spatial_movement.items():
                if agent_key in all_positions:
                    positions = [mov['position'] for mov in movements]
                    all_positions[agent_key].extend(positions)
        
        # Analyser la couverture spatiale
        for agent_key, positions in all_positions.items():
            if positions:
                unique_positions = set(positions)
                spatial_metrics['coverage_analysis'][agent_key] = {
                    'unique_positions_visited': len(unique_positions),
                    'total_movements': len(positions),
                    'coverage_efficiency': len(unique_positions) / len(positions)
                }
        
        return spatial_metrics
    
    def _analyze_temporal_patterns(self, games_data: List[Dict]) -> Dict:
        """Analyse les patterns temporels."""
        temporal_metrics = {
            'phase_analysis': {},
            'rhythm_analysis': {},
            'progression_patterns': {}
        }
        
        # Analyser les phases de jeu (début, milieu, fin)
        for game in games_data:
            steps = game.get('steps', 0)
            if steps > 0:
                # Diviser en phases
                phase_length = steps // 3
                phases = ['early', 'mid', 'late']
                
                event_sequence = game.get('event_sequence', [])
                for i, phase in enumerate(phases):
                    start_step = i * phase_length
                    end_step = (i + 1) * phase_length if i < 2 else steps
                    
                    phase_events = [event for event in event_sequence 
                                  if start_step <= event.get('step', 0) < end_step]
                    
                    if phase not in temporal_metrics['phase_analysis']:
                        temporal_metrics['phase_analysis'][phase] = []
                    
                    temporal_metrics['phase_analysis'][phase].append({
                        'events_count': len(phase_events),
                        'productivity': sum(event.get('reward', 0) for event in phase_events)
                    })
        
        return temporal_metrics
    
    def _compare_modes(self, behavioral_modes: Dict) -> Dict:
        """Compare les différents modes comportementaux."""
        comparison = {
            'performance_comparison': {},
            'behavioral_differences': {},
            'suitability_ranking': {},
            'coordination_requirements': {}
        }
        
        modes = list(behavioral_modes.keys())
        
        # Comparer les performances
        for mode in modes:
            mode_data = behavioral_modes[mode]
            if 'performance_metrics' in mode_data:
                pm = mode_data['performance_metrics']
                comparison['performance_comparison'][mode] = {
                    'success_rate': mode_data.get('success_rate', 0),
                    'avg_completion_steps': pm.get('avg_completion_steps', float('inf')),
                    'completion_efficiency': pm.get('completion_efficiency', 0)
                }
        
        # Identifier le mode le plus adapté
        best_mode = None
        best_score = -1
        
        for mode, metrics in comparison['performance_comparison'].items():
            # Score combiné : success_rate * efficiency / steps (normalisé)
            score = (metrics['success_rate'] * metrics['completion_efficiency'] * 
                    (600 / max(metrics['avg_completion_steps'], 100)))
            
            if score > best_score:
                best_score = score
                best_mode = mode
        
        comparison['suitability_ranking'] = {
            'best_mode': best_mode,
            'scores': {mode: metrics['success_rate'] * metrics['completion_efficiency'] 
                      for mode, metrics in comparison['performance_comparison'].items()}
        }
        
        return comparison
    
    def _characterize_layout(self, behavioral_modes: Dict) -> Dict:
        """Caractérise le layout basé sur les comportements observés."""
        characteristics = {
            'difficulty_level': 'unknown',
            'cooperation_requirement': 'unknown',
            'layout_type': 'unknown',
            'bottlenecks': [],
            'optimal_strategies': {},
            'agent_roles': {}
        }
        
        # Évaluer la difficulté basée sur le taux de succès
        success_rates = [mode_data.get('success_rate', 0) for mode_data in behavioral_modes.values()]
        avg_success_rate = np.mean(success_rates)
        
        if avg_success_rate > 0.8:
            characteristics['difficulty_level'] = 'easy'
        elif avg_success_rate > 0.5:
            characteristics['difficulty_level'] = 'medium'
        elif avg_success_rate > 0.2:
            characteristics['difficulty_level'] = 'hard'
        else:
            characteristics['difficulty_level'] = 'very_hard'
        
        # Évaluer les exigences de coopération
        if 'cooperative' in behavioral_modes and 'solo' in behavioral_modes:
            coop_success = behavioral_modes['cooperative'].get('success_rate', 0)
            solo_success = behavioral_modes['solo'].get('success_rate', 0)
            
            if coop_success > solo_success * 1.5:
                characteristics['cooperation_requirement'] = 'high'
            elif coop_success > solo_success * 1.1:
                characteristics['cooperation_requirement'] = 'medium'
            else:
                characteristics['cooperation_requirement'] = 'low'
        
        return characteristics
    
    def _analyze_agent_patterns(self, behavioral_modes: Dict) -> Dict:
        """Analyse les patterns spécifiques aux agents."""
        patterns = {
            'specialization_tendency': {},
            'role_preferences': {},
            'adaptation_ability': {},
            'individual_vs_team_performance': {}
        }
        
        for mode_name, mode_data in behavioral_modes.items():
            if 'behavioral_patterns' in mode_data:
                bp = mode_data['behavioral_patterns']
                
                if 'agent_specialization' in bp:
                    specialization = bp['agent_specialization']
                    patterns['specialization_tendency'][mode_name] = {
                        'specialization_score': specialization.get('avg_specialization_score', 0),
                        'consistency': specialization.get('specialization_consistency', 0)
                    }
        
        return patterns
    
    def _calculate_performance_metrics(self, behavioral_modes: Dict) -> Dict:
        """Calcule des métriques de performance complètes."""
        metrics = {
            'overall_viability': 0,
            'mode_comparison': {},
            'efficiency_metrics': {},
            'consistency_metrics': {}
        }
        
        viable_modes = 0
        total_modes = len(behavioral_modes)
        
        for mode_name, mode_data in behavioral_modes.items():
            success_rate = mode_data.get('success_rate', 0)
            if success_rate > 0:
                viable_modes += 1
            
            metrics['mode_comparison'][mode_name] = {
                'viability': success_rate > 0,
                'success_rate': success_rate,
                'performance_level': 'high' if success_rate > 0.8 else ('medium' if success_rate > 0.4 else 'low')
            }
        
        metrics['overall_viability'] = viable_modes / total_modes if total_modes > 0 else 0
        
        return metrics
    
    def _analyze_coordination_requirements(self, behavioral_modes: Dict) -> Dict:
        """Analyse les exigences de coordination du layout."""
        analysis = {
            'coordination_necessity': 'unknown',
            'coordination_patterns': {},
            'solo_vs_team_effectiveness': {},
            'coordination_bottlenecks': []
        }
        
        if 'cooperative' in behavioral_modes and 'solo' in behavioral_modes:
            coop_data = behavioral_modes['cooperative']
            solo_data = behavioral_modes['solo']
            
            coop_success = coop_data.get('success_rate', 0)
            solo_success = solo_data.get('success_rate', 0)
            
            analysis['solo_vs_team_effectiveness'] = {
                'cooperative_success_rate': coop_success,
                'solo_success_rate': solo_success,
                'team_advantage': coop_success - solo_success,
                'relative_effectiveness': coop_success / max(solo_success, 0.01)
            }
            
            if coop_success > solo_success * 2:
                analysis['coordination_necessity'] = 'essential'
            elif coop_success > solo_success * 1.2:
                analysis['coordination_necessity'] = 'beneficial'
            elif coop_success < solo_success * 0.8:
                analysis['coordination_necessity'] = 'counterproductive'
            else:
                analysis['coordination_necessity'] = 'neutral'
        
        return analysis
    
    def _assess_layout_difficulty(self, behavioral_modes: Dict) -> Dict:
        """Évalue la difficulté du layout de manière complète."""
        assessment = {
            'overall_difficulty': 'unknown',
            'difficulty_factors': {},
            'mode_specific_difficulty': {},
            'learning_curve': 'unknown'
        }
        
        difficulty_scores = []
        
        for mode_name, mode_data in behavioral_modes.items():
            success_rate = mode_data.get('success_rate', 0)
            avg_steps = mode_data.get('performance_metrics', {}).get('avg_completion_steps', 600)
            
            # Score de difficulté : combinaison du taux d'échec et de la longueur
            difficulty_score = (1 - success_rate) + (avg_steps / 600)
            difficulty_scores.append(difficulty_score)
            
            if difficulty_score < 0.5:
                mode_difficulty = 'easy'
            elif difficulty_score < 1.0:
                mode_difficulty = 'medium'
            elif difficulty_score < 1.5:
                mode_difficulty = 'hard'
            else:
                mode_difficulty = 'very_hard'
            
            assessment['mode_specific_difficulty'][mode_name] = {
                'difficulty_level': mode_difficulty,
                'difficulty_score': difficulty_score,
                'success_rate': success_rate,
                'avg_completion_steps': avg_steps
            }
        
        # Difficulté globale
        avg_difficulty = np.mean(difficulty_scores) if difficulty_scores else 1.0
        
        if avg_difficulty < 0.5:
            assessment['overall_difficulty'] = 'easy'
        elif avg_difficulty < 1.0:
            assessment['overall_difficulty'] = 'medium'
        elif avg_difficulty < 1.5:
            assessment['overall_difficulty'] = 'hard'
        else:
            assessment['overall_difficulty'] = 'very_hard'
        
        return assessment


def main():
    parser = argparse.ArgumentParser(description="Générateur de données comportementales pour layouts Overcooked")
    parser.add_argument('--layouts-dir', default="./overcooked_ai_py/data/layouts/generation_cesar/",
                       help='Répertoire des layouts')
    parser.add_argument('--horizon', type=int, default=600,
                       help='Horizon de simulation')
    parser.add_argument('--games-per-layout', type=int, default=10,
                       help='Nombre de parties par layout')
    parser.add_argument('--output', default="behavioral_data_complete.json",
                       help='Fichier de sortie')
    
    args = parser.parse_args()
    
    print("🔬 GÉNÉRATION DE DONNÉES COMPORTEMENTALES COMPLÈTES")
    print("=" * 60)
    
    generator = BehavioralDataGenerator(
        layouts_directory=args.layouts_dir,
        horizon=args.horizon,
        num_games_per_layout=args.games_per_layout
    )
    
    complete_data = generator.generate_complete_behavioral_data(args.output)
    
    print(f"\n✅ Génération terminée!")
    print(f"📊 Données sauvegardées: {args.output}")
    print(f"🏗️ Layouts analysés: {complete_data['metadata']['layouts_analyzed']}")
    print(f"🎮 Total parties simulées: {complete_data['metadata']['layouts_analyzed'] * args.games_per_layout * 3}")  # 3 modes


if __name__ == "__main__":
    main()
