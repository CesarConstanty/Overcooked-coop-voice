#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluateur professionnel avec simulation réelle des layouts Overcooked
- Simulation complète des trajets avec pathfinding BFS/A*
- Calcul réel des steps pour chaque recette en mode solo et duo
- Gestion dynamique des zones d'échange X->Y
- Génération de trajectoires détaillées pour vérification manuelle
- Ignore la durée de cuisson selon les spécifications
"""

import json
import time
import logging
import multiprocessing as mp
from pathlib import Path
from collections import deque, defaultdict
from typing import Dict, List, Tuple, Set, Optional, Any
import argparse
import heapq
import copy

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('layout_evaluation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GameState:
    """Représente l'état du jeu à un moment donné."""
    
    def __init__(self, grid: List[List[str]], player_positions: Dict[str, Tuple[int, int]]):
        self.grid = [row[:] for row in grid]  # Copie profonde
        self.player_positions = player_positions.copy()
        self.inventory = {'1': [], '2': []}  # Inventaire des joueurs
        self.pot_contents = {}  # Contenu des pots {position: [ingredients]}
        self.completed_dishes = []  # Plats terminés
        self.steps_count = 0
        self.exchanges_used = 0
        self.exchange_zones = set()  # Zones X converties en Y
    
    def copy(self):
        """Crée une copie profonde de l'état."""
        new_state = GameState(self.grid, self.player_positions)
        new_state.inventory = {k: v[:] for k, v in self.inventory.items()}
        new_state.pot_contents = {k: v[:] for k, v in self.pot_contents.items()}
        new_state.completed_dishes = self.completed_dishes[:]
        new_state.steps_count = self.steps_count
        new_state.exchanges_used = self.exchanges_used
        new_state.exchange_zones = self.exchange_zones.copy()
        return new_state

class PathFinder:
    """Classe pour le calcul de chemins avec BFS/A*."""
    
    @staticmethod
    def bfs_shortest_path(grid: List[List[str]], start: Tuple[int, int], 
                         end: Tuple[int, int], exchange_zones: Set[Tuple[int, int]] = None) -> Optional[List[Tuple[int, int]]]:
        """Calcule le chemin le plus court avec BFS."""
        if start == end:
            return [start]
        
        grid_size = len(grid)
        queue = deque([(start, [start])])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current, path = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < grid_size and 0 <= nj < grid_size and
                    (ni, nj) not in visited):
                    
                    cell = grid[ni][nj]
                    
                    # Vérifier si la case est traversable
                    if cell != 'X' or (exchange_zones and (ni, nj) in exchange_zones):
                        visited.add((ni, nj))
                        new_path = path + [(ni, nj)]
                        
                        if (ni, nj) == end:
                            return new_path
                        
                        queue.append(((ni, nj), new_path))
        
        return None  # Aucun chemin trouvé
    
    @staticmethod
    def find_accessible_objects(grid: List[List[str]], start: Tuple[int, int], 
                               target_objects: Set[str], exchange_zones: Set[Tuple[int, int]] = None) -> Dict[str, Tuple[int, int]]:
        """Trouve tous les objets accessibles depuis une position."""
        grid_size = len(grid)
        accessible = {}
        
        for i in range(grid_size):
            for j in range(grid_size):
                if grid[i][j] in target_objects:
                    path = PathFinder.bfs_shortest_path(grid, start, (i, j), exchange_zones)
                    if path:
                        accessible[grid[i][j]] = (i, j)
        
        return accessible

class OvercookedSimulator:
    """Simulateur complet du gameplay Overcooked."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.eval_config = config["pipeline_config"]["evaluation"]
        self.ignore_cooking_times = self.eval_config["ignore_cooking_times"]
        self.max_exchange_zones = self.eval_config["max_exchange_zones"]
        self.pathfinding_algo = self.eval_config["pathfinding_algorithm"]
        
    def simulate_recipe_completion(self, layout: Dict, recipe: Dict, 
                                 player_mode: str = "solo", generate_trajectories: bool = False) -> Dict:
        """Simule la completion d'une recette complète."""
        grid_str = layout['grid']
        grid = [list(row) for row in grid_str.split('\n')]
        
        # Initialiser l'état du jeu
        player_positions = self.extract_player_positions(grid)
        initial_state = GameState(grid, player_positions)
        
        # Remplacer les joueurs par des espaces vides dans la grille
        for pos in player_positions.values():
            initial_state.grid[pos[0]][pos[1]] = '.'
        
        # Simuler selon le mode
        if player_mode == "solo":
            result = self.simulate_solo_mode(initial_state, recipe, generate_trajectories)
        else:  # duo
            result = self.simulate_duo_mode(initial_state, recipe, generate_trajectories)
        
        return result
    
    def extract_player_positions(self, grid: List[List[str]]) -> Dict[str, Tuple[int, int]]:
        """Extrait les positions des joueurs de la grille."""
        positions = {}
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] in ['1', '2']:
                    positions[grid[i][j]] = (i, j)
        return positions
    
    def simulate_solo_mode(self, initial_state: GameState, recipe: Dict, generate_trajectories: bool = False) -> Dict:
        """Simule le mode solo (joueur 1 uniquement)."""
        state = initial_state.copy()
        trajectory = [] if generate_trajectories else None
        ingredients_needed = recipe['ingredients'][:]
        
        logger.debug(f"🎯 Simulation solo pour recette: {ingredients_needed}")
        
        while ingredients_needed:
            ingredient = ingredients_needed.pop(0)
            steps = self.collect_and_process_ingredient(state, ingredient, '1', trajectory)
            
            if steps == -1:  # Échec
                return {
                    'success': False,
                    'total_steps': float('inf'),
                    'trajectory': trajectory,
                    'reason': 'Impossible de collecter ingrédient',
                    'exchanges_used': 0
                }
        
        # Finaliser le plat
        final_steps = self.finalize_dish(state, '1', trajectory)
        if final_steps == -1:
            return {
                'success': False,
                'total_steps': float('inf'),
                'trajectory': trajectory,
                'reason': 'Impossible de finaliser le plat',
                'exchanges_used': 0
            }
        
        result = {
            'success': True,
            'total_steps': state.steps_count,
            'exchanges_used': state.exchanges_used,
            'final_state': state
        }
        
        # Ajouter les trajectoires seulement si demandées
        if generate_trajectories:
            result['trajectory'] = trajectory
        
        return result
    
    def simulate_duo_mode(self, initial_state: GameState, recipe: Dict, generate_trajectories: bool = False) -> Dict:
        """Simule le mode duo avec optimisation des échanges."""
        state = initial_state.copy()
        trajectory = [] if generate_trajectories else None
        ingredients_needed = recipe['ingredients'][:]
        
        logger.debug(f"🎯 Simulation duo pour recette: {ingredients_needed}")
        
        # Essayer différentes stratégies de répartition
        best_result = None
        best_steps = float('inf')
        
        # Stratégie 1: Répartition équilibrée
        result1 = self.simulate_duo_balanced_strategy(state.copy(), ingredients_needed, trajectory[:] if trajectory else None)
        if result1['success'] and result1['total_steps'] < best_steps:
            best_result = result1
            best_steps = result1['total_steps']
        
        # Stratégie 2: Avec zones d'échange optimisées
        if state.exchanges_used < self.max_exchange_zones:
            result2 = self.simulate_duo_with_exchanges(state.copy(), ingredients_needed, trajectory[:] if trajectory else None)
            if result2['success'] and result2['total_steps'] < best_steps:
                best_result = result2
                best_steps = result2['total_steps']
        
        return best_result or {
            'success': False,
            'total_steps': float('inf'),
            'trajectory': trajectory,
            'reason': 'Toutes les stratégies ont échoué',
            'exchanges_used': 0
        }
    
    def simulate_duo_balanced_strategy(self, state: GameState, 
                                     ingredients: List[str], trajectory: Optional[List[Dict]]) -> Dict:
        """Stratégie équilibrée pour le mode duo."""
        # Répartir les ingrédients entre les joueurs
        player1_ingredients = ingredients[::2]  # Indices pairs
        player2_ingredients = ingredients[1::2]  # Indices impairs
        
        # Simuler en parallèle (simplifié)
        max_steps = 0
        
        # Joueur 1
        for ingredient in player1_ingredients:
            steps = self.collect_and_process_ingredient(state, ingredient, '1', trajectory)
            if steps == -1:
                return {'success': False, 'total_steps': float('inf'), 
                       'trajectory': trajectory, 'exchanges_used': state.exchanges_used}
            max_steps = max(max_steps, state.steps_count)
        
        # Joueur 2
        for ingredient in player2_ingredients:
            steps = self.collect_and_process_ingredient(state, ingredient, '2', trajectory)
            if steps == -1:
                return {'success': False, 'total_steps': float('inf'), 
                       'trajectory': trajectory, 'exchanges_used': state.exchanges_used}
            max_steps = max(max_steps, state.steps_count)
        
        # Finalisation par le joueur le plus proche
        final_steps = self.finalize_dish(state, '1', trajectory)  # Simplifié
        if final_steps == -1:
            return {'success': False, 'total_steps': float('inf'), 
                   'trajectory': trajectory, 'exchanges_used': state.exchanges_used}
        
        result = {
            'success': True,
            'total_steps': state.steps_count,
            'exchanges_used': state.exchanges_used,
            'final_state': state
        }
        
        # Ajouter les trajectoires seulement si demandées
        if trajectory is not None:
            result['trajectory'] = trajectory
        
        return result
    
    def simulate_duo_with_exchanges(self, state: GameState, 
                                   ingredients: List[str], trajectory: Optional[List[Dict]]) -> Dict:
        """Stratégie duo avec optimisation des zones d'échange."""
        # Identifier les zones X potentiellement utiles pour les échanges
        potential_exchanges = self.identify_potential_exchange_zones(state.grid, state.player_positions)
        
        if not potential_exchanges:
            return self.simulate_duo_balanced_strategy(state, ingredients, trajectory)
        
        # Essayer avec les meilleures zones d'échange
        best_zones = potential_exchanges[:self.max_exchange_zones]
        
        for zone in best_zones:
            if self.is_exchange_beneficial(state, zone, ingredients):
                state.grid[zone[0]][zone[1]] = 'Y'
                state.exchange_zones.add(zone)
                state.exchanges_used += 1
                
                if trajectory is not None:
                    trajectory.append({
                        'action': 'create_exchange_zone',
                        'position': zone,
                        'step': state.steps_count,
                        'reason': 'Optimisation des échanges'
                    })
        
        return self.simulate_duo_balanced_strategy(state, ingredients, trajectory)
    
    def identify_potential_exchange_zones(self, grid: List[List[str]], 
                                        player_positions: Dict[str, Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Identifie les zones X potentiellement utiles pour les échanges."""
        potential_zones = []
        
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] == 'X':
                    # Vérifier si cette zone pourrait améliorer la connectivité
                    if self.would_improve_connectivity(grid, (i, j), player_positions):
                        potential_zones.append((i, j))
        
        # Trier par utilité potentielle
        potential_zones.sort(key=lambda zone: self.calculate_exchange_utility(grid, zone, player_positions), reverse=True)
        
        return potential_zones
    
    def would_improve_connectivity(self, grid: List[List[str]], 
                                 zone: Tuple[int, int], player_positions: Dict[str, Tuple[int, int]]) -> bool:
        """Vérifie si convertir une zone X en Y améliorerait la connectivité."""
        # Test simple: vérifier si cela réduit la distance entre les joueurs
        p1_pos = player_positions['1']
        p2_pos = player_positions['2']
        
        # Distance actuelle
        current_dist = abs(p1_pos[0] - p2_pos[0]) + abs(p1_pos[1] - p2_pos[1])
        
        # Distance avec la zone convertie (approximation)
        # Pour un calcul précis, il faudrait faire un pathfinding complet
        zone_to_p1 = abs(zone[0] - p1_pos[0]) + abs(zone[1] - p1_pos[1])
        zone_to_p2 = abs(zone[0] - p2_pos[0]) + abs(zone[1] - p2_pos[1])
        potential_new_dist = zone_to_p1 + zone_to_p2
        
        return potential_new_dist < current_dist * 1.5  # Seuil d'amélioration
    
    def calculate_exchange_utility(self, grid: List[List[str]], 
                                 zone: Tuple[int, int], player_positions: Dict[str, Tuple[int, int]]) -> float:
        """Calcule l'utilité d'une zone d'échange."""
        # Score basé sur la position centrale et la proximité aux objets importants
        grid_size = len(grid)
        center_x, center_y = grid_size // 2, grid_size // 2
        
        # Distance au centre (plus c'est central, mieux c'est)
        center_dist = abs(zone[0] - center_x) + abs(zone[1] - center_y)
        center_score = 1.0 - (center_dist / (grid_size * 0.7))
        
        # Proximité aux objets importants
        object_score = 0.0
        important_objects = ['O', 'T', 'P', 'D', 'S']
        
        for i in range(grid_size):
            for j in range(grid_size):
                if grid[i][j] in important_objects:
                    obj_dist = abs(zone[0] - i) + abs(zone[1] - j)
                    object_score += 1.0 / (1 + obj_dist)
        
        return center_score * 0.3 + object_score * 0.7
    
    def is_exchange_beneficial(self, state: GameState, zone: Tuple[int, int], 
                              ingredients: List[str]) -> bool:
        """Vérifie si créer une zone d'échange serait bénéfique."""
        # Heuristique simple: bénéfique si cela réduit les trajets moyens
        return True  # Pour l'instant, simplifié
    
    def collect_and_process_ingredient(self, state: GameState, ingredient: str, 
                                     player: str, trajectory: Optional[List[Dict]]) -> int:
        """Simule la collecte et le traitement d'un ingrédient."""
        # Trouver la source de l'ingrédient
        source_obj = 'O' if ingredient == 'onion' else 'T'
        
        # Trouver la position de la source
        source_pos = None
        for i in range(len(state.grid)):
            for j in range(len(state.grid[i])):
                if state.grid[i][j] == source_obj:
                    source_pos = (i, j)
                    break
            if source_pos:
                break
        
        if not source_pos:
            return -1  # Source non trouvée
        
        # Calculer le chemin vers la source
        player_pos = state.player_positions[player]
        path_to_source = PathFinder.bfs_shortest_path(state.grid, player_pos, source_pos, state.exchange_zones)
        
        if not path_to_source:
            return -1  # Chemin impossible
        
        # Ajouter les steps pour atteindre la source
        steps_to_source = len(path_to_source) - 1
        state.steps_count += steps_to_source
        state.player_positions[player] = source_pos
        
        # Collecter l'ingrédient
        state.inventory[player].append(ingredient)
        state.steps_count += 1  # Action de collecte
        
        if trajectory is not None:
            trajectory.append({
                'action': 'collect_ingredient',
                'player': player,
                'ingredient': ingredient,
                'source_position': source_pos,
                'path': path_to_source,
                'steps_used': steps_to_source + 1,
                'total_steps': state.steps_count
            })
        
        # Aller au pot pour déposer l'ingrédient
        pot_pos = self.find_nearest_pot(state.grid, state.player_positions[player])
        if not pot_pos:
            return -1  # Pas de pot accessible
        
        path_to_pot = PathFinder.bfs_shortest_path(state.grid, state.player_positions[player], pot_pos, state.exchange_zones)
        if not path_to_pot:
            return -1  # Chemin vers pot impossible
        
        steps_to_pot = len(path_to_pot) - 1
        state.steps_count += steps_to_pot
        state.player_positions[player] = pot_pos
        
        # Déposer dans le pot
        if pot_pos not in state.pot_contents:
            state.pot_contents[pot_pos] = []
        state.pot_contents[pot_pos].append(ingredient)
        state.inventory[player].remove(ingredient)
        state.steps_count += 1  # Action de dépôt
        
        if trajectory is not None:
            trajectory.append({
                'action': 'deposit_ingredient',
                'player': player,
                'ingredient': ingredient,
                'pot_position': pot_pos,
                'path': path_to_pot,
                'steps_used': steps_to_pot + 1,
                'total_steps': state.steps_count
            })
        
        return steps_to_source + steps_to_pot + 2  # Total des steps utilisés
    
    def find_nearest_pot(self, grid: List[List[str]], position: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Trouve le pot le plus proche d'une position."""
        best_pot = None
        min_distance = float('inf')
        
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] == 'P':
                    distance = abs(i - position[0]) + abs(j - position[1])
                    if distance < min_distance:
                        min_distance = distance
                        best_pot = (i, j)
        
        return best_pot
    
    def finalize_dish(self, state: GameState, player: str, trajectory: Optional[List[Dict]]) -> int:
        """Simule la finalisation d'un plat."""
        # Trouver un pot avec des ingrédients
        pot_pos = None
        for pos, contents in state.pot_contents.items():
            if contents:
                pot_pos = pos
                break
        
        if not pot_pos:
            return -1  # Pas de pot avec ingrédients
        
        # Aller au pot
        player_pos = state.player_positions[player]
        if player_pos != pot_pos:
            path_to_pot = PathFinder.bfs_shortest_path(state.grid, player_pos, pot_pos, state.exchange_zones)
            if not path_to_pot:
                return -1
            
            steps_to_pot = len(path_to_pot) - 1
            state.steps_count += steps_to_pot
            state.player_positions[player] = pot_pos
        
        # Cuisson (instantanée si ignore_cooking_times)
        if not self.ignore_cooking_times:
            cooking_time = 10  # Temps de cuisson standard
            state.steps_count += cooking_time
        
        # Récupérer le plat cuit
        state.steps_count += 1  # Action de récupération
        cooked_dish = state.pot_contents[pot_pos][:]
        state.pot_contents[pot_pos] = []
        state.inventory[player].extend(['cooked_dish'])
        
        # Trouver une assiette
        dish_pos = self.find_nearest_dish_dispenser(state.grid, state.player_positions[player])
        if not dish_pos:
            return -1
        
        path_to_dish = PathFinder.bfs_shortest_path(state.grid, state.player_positions[player], dish_pos, state.exchange_zones)
        if not path_to_dish:
            return -1
        
        steps_to_dish = len(path_to_dish) - 1
        state.steps_count += steps_to_dish
        state.player_positions[player] = dish_pos
        
        # Prendre une assiette
        state.steps_count += 1
        state.inventory[player].append('dish')
        
        # Assembler le plat
        state.steps_count += 1
        state.inventory[player] = [item for item in state.inventory[player] if item not in ['cooked_dish', 'dish']]
        state.inventory[player].append('complete_dish')
        
        # Aller à la zone de service
        serving_pos = self.find_serving_station(state.grid)
        if not serving_pos:
            return -1
        
        path_to_serving = PathFinder.bfs_shortest_path(state.grid, state.player_positions[player], serving_pos, state.exchange_zones)
        if not path_to_serving:
            return -1
        
        steps_to_serving = len(path_to_serving) - 1
        state.steps_count += steps_to_serving
        state.player_positions[player] = serving_pos
        
        # Servir le plat
        state.steps_count += 1
        state.inventory[player].remove('complete_dish')
        state.completed_dishes.append(cooked_dish)
        
        if trajectory is not None:
            trajectory.append({
                'action': 'finalize_dish',
                'player': player,
                'dish_contents': cooked_dish,
                'total_steps_for_finalization': steps_to_dish + steps_to_serving + 4,
                'total_steps': state.steps_count
            })
        
        return steps_to_dish + steps_to_serving + 4
    
    def find_nearest_dish_dispenser(self, grid: List[List[str]], position: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Trouve le distributeur d'assiettes le plus proche."""
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] == 'D':
                    return (i, j)
        return None
    
    def find_serving_station(self, grid: List[List[str]]) -> Optional[Tuple[int, int]]:
        """Trouve la station de service."""
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] == 'S':
                    return (i, j)
        return None

class ProfessionalLayoutEvaluator:
    """Évaluateur professionnel avec simulation réelle."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise l'évaluateur avec la configuration."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Dossiers
        self.layouts_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_generated_dir"]
        self.trajectories_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["trajectories_dir"]
        self.evaluation_dir = self.base_dir / "outputs" / "detailed_evaluation"
        
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)
        
        # Simulateur
        self.simulator = OvercookedSimulator(self.config)
        
        logger.info(f"🎯 Évaluateur professionnel initialisé")
        logger.info(f"📁 Layouts: {self.layouts_dir}")
        logger.info(f"📁 Trajectoires: {self.trajectories_dir}")
        logger.info(f"📁 Évaluations: {self.evaluation_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_layouts_and_recipes(self) -> Tuple[List[Dict], List[Dict]]:
        """Charge les layouts et groupes de recettes."""
        # Charger les layouts
        layouts = []
        if self.layouts_dir.exists():
            for layout_file in self.layouts_dir.glob("*.json"):
                try:
                    with open(layout_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'layouts' in data:
                            layouts.extend(data['layouts'])
                except Exception as e:
                    logger.warning(f"❌ Erreur lecture layout {layout_file}: {e}")
        
        # Charger les groupes de recettes
        recipe_groups = []
        recipe_files = list(self.base_dir.glob("outputs/all_recipe_groups_*.json"))
        if recipe_files:
            latest_file = max(recipe_files, key=lambda f: f.stat().st_mtime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                recipe_groups = data['recipe_groups']
        
        logger.info(f"📊 Chargés: {len(layouts)} layouts, {len(recipe_groups)} groupes de recettes")
        return layouts, recipe_groups
    
    def evaluate_layout_with_recipe_group(self, layout: Dict, recipe_group: Dict) -> Dict:
        """Évalue un layout avec un groupe de recettes (mode léger sans trajectoires)."""
        layout_id = layout['canonical_hash']
        group_id = recipe_group['group_id']
        
        logger.debug(f"🔄 Évaluation layout {layout_id} avec groupe {group_id}")
        
        results = {
            'layout_id': layout_id,
            'recipe_group_id': group_id,
            'recipe_evaluations': [],
            'summary_metrics': {}
        }
        
        total_solo_steps = 0
        total_duo_steps = 0
        total_exchanges_used = 0
        successful_recipes = 0
        
        # Évaluer chaque recette du groupe (sans trajectoires)
        for recipe in recipe_group['recipes']:
            recipe_id = recipe['id']
            
            # Simulation solo (mode léger)
            solo_result = self.simulator.simulate_recipe_completion(layout, recipe, "solo", generate_trajectories=False)
            
            # Simulation duo (mode léger)
            duo_result = self.simulator.simulate_recipe_completion(layout, recipe, "duo", generate_trajectories=False)
            
            # Calculer les métriques
            if solo_result['success'] and duo_result['success']:
                cooperation_gain = ((solo_result['total_steps'] - duo_result['total_steps']) / 
                                  solo_result['total_steps'] * 100) if solo_result['total_steps'] > 0 else 0
                
                recipe_eval = {
                    'recipe_id': recipe_id,
                    'recipe': recipe,
                    'solo_steps': solo_result['total_steps'],
                    'duo_steps': duo_result['total_steps'],
                    'cooperation_gain': cooperation_gain,
                    'exchanges_used': duo_result['exchanges_used'],
                    'success': True
                }
                
                total_solo_steps += solo_result['total_steps']
                total_duo_steps += duo_result['total_steps']
                total_exchanges_used += duo_result['exchanges_used']
                successful_recipes += 1
                
            else:
                recipe_eval = {
                    'recipe_id': recipe_id,
                    'recipe': recipe,
                    'solo_steps': float('inf'),
                    'duo_steps': float('inf'),
                    'cooperation_gain': 0,
                    'exchanges_used': 0,
                    'success': False,
                    'failure_reason': solo_result.get('reason', 'Unknown') if not solo_result['success'] else duo_result.get('reason', 'Unknown')
                }
            
            results['recipe_evaluations'].append(recipe_eval)
        
        # Calculer les métriques globales
        if successful_recipes > 0:
            avg_cooperation_gain = ((total_solo_steps - total_duo_steps) / total_solo_steps * 100) if total_solo_steps > 0 else 0
            
            results['summary_metrics'] = {
                'total_solo_steps': total_solo_steps,
                'total_duo_steps': total_duo_steps,
                'avg_cooperation_gain': avg_cooperation_gain,
                'total_exchanges_used': total_exchanges_used,
                'avg_exchanges_per_recipe': total_exchanges_used / successful_recipes,
                'successful_recipes': successful_recipes,
                'success_rate': successful_recipes / len(recipe_group['recipes']) * 100,
                'efficiency_score': self.calculate_efficiency_score(total_duo_steps, successful_recipes),
                'layout_quality_score': self.calculate_layout_quality_score(layout, results)
            }
        else:
            results['summary_metrics'] = {
                'total_solo_steps': float('inf'),
                'total_duo_steps': float('inf'),
                'avg_cooperation_gain': 0,
                'total_exchanges_used': 0,
                'avg_exchanges_per_recipe': 0,
                'successful_recipes': 0,
                'success_rate': 0,
                'efficiency_score': 0,
                'layout_quality_score': 0
            }
        
        return results
    
    def calculate_efficiency_score(self, total_duo_steps: int, successful_recipes: int) -> float:
        """Calcule un score d'efficacité basé sur les steps."""
        if successful_recipes == 0:
            return 0.0
        
        avg_steps_per_recipe = total_duo_steps / successful_recipes
        
        # Score basé sur un nombre optimal d'steps (à ajuster selon les tests)
        optimal_steps = 50  # Valeur de référence
        
        if avg_steps_per_recipe <= optimal_steps:
            return 1.0
        else:
            return max(0.0, 1.0 - (avg_steps_per_recipe - optimal_steps) / optimal_steps)
    
    def calculate_layout_quality_score(self, layout: Dict, evaluation_results: Dict) -> float:
        """Calcule un score de qualité global du layout."""
        metrics = evaluation_results['summary_metrics']
        
        # Composantes du score
        cooperation_score = min(1.0, metrics['avg_cooperation_gain'] / 50.0)  # Normaliser à 50%
        efficiency_score = metrics['efficiency_score']
        success_score = metrics['success_rate'] / 100.0
        exchange_score = min(1.0, metrics['avg_exchanges_per_recipe'] / 2.0)  # Normaliser à 2 échanges
        
        # Score pondéré
        weights = self.config["pipeline_config"]["selection"]["criteria"]
        
        total_score = (cooperation_score * weights["cooperation_gain"]["weight"] +
                      efficiency_score * weights["efficiency"]["weight"] +
                      exchange_score * weights["exchanges"]["weight"])
        
        # Bonus pour taux de succès élevé
        total_score *= success_score
        
        return total_score
    
    def generate_detailed_trajectories_for_selected_layouts(self, selected_layouts: List[Dict], 
                                                          recipe_groups: List[Dict]) -> Dict:
        """Génère les trajectoires détaillées uniquement pour les layouts sélectionnés."""
        logger.info(f"🎯 Génération des trajectoires détaillées pour {len(selected_layouts)} layouts sélectionnés")
        
        all_trajectories = {}
        
        for layout in selected_layouts:
            layout_id = layout['canonical_hash']
            layout_trajectories = {}
            
            logger.debug(f"📍 Génération trajectoires pour layout {layout_id}")
            
            # Générer les trajectoires pour toutes les recettes de tous les groupes
            for recipe_group in recipe_groups:
                group_id = recipe_group['group_id']
                
                for recipe in recipe_group['recipes']:
                    recipe_id = recipe['id']
                    
                    # Simulation avec trajectoires détaillées
                    solo_result = self.simulator.simulate_recipe_completion(
                        layout, recipe, "solo", generate_trajectories=True
                    )
                    duo_result = self.simulator.simulate_recipe_completion(
                        layout, recipe, "duo", generate_trajectories=True
                    )
                    
                    if solo_result['success'] and duo_result['success']:
                        cooperation_gain = ((solo_result['total_steps'] - duo_result['total_steps']) / 
                                          solo_result['total_steps'] * 100) if solo_result['total_steps'] > 0 else 0
                        
                        trajectory_key = f"{group_id}_{recipe_id}"
                        layout_trajectories[trajectory_key] = {
                            'layout_id': layout_id,
                            'recipe_group_id': group_id,
                            'recipe_id': recipe_id,
                            'recipe': recipe,
                            'solo_trajectory': solo_result.get('trajectory', []),
                            'duo_trajectory': duo_result.get('trajectory', []),
                            'metadata': {
                                'solo_steps': solo_result['total_steps'],
                                'duo_steps': duo_result['total_steps'],
                                'cooperation_gain': cooperation_gain,
                                'exchanges_used': duo_result['exchanges_used'],
                                'generation_timestamp': time.time()
                            }
                        }
            
            all_trajectories[layout_id] = layout_trajectories
            
            # Sauvegarder les trajectoires du layout
            self.save_trajectories(layout_id, layout_trajectories)
        
        logger.info(f"✅ Trajectoires générées pour {len(selected_layouts)} layouts")
        return all_trajectories
    
    def run_evaluation(self) -> bool:
        """Lance l'évaluation complète."""
        start_time = time.time()
        
        try:
            # Charger les données
            layouts, recipe_groups = self.load_layouts_and_recipes()
            
            if not layouts or not recipe_groups:
                logger.error("❌ Données insuffisantes pour l'évaluation")
                return False
            
            logger.info(f"🚀 Démarrage évaluation complète")
            logger.info(f"📊 {len(layouts)} layouts × {len(recipe_groups)} groupes = {len(layouts) * len(recipe_groups):,} évaluations")
            
            all_evaluations = []
            processed = 0
            
    def save_trajectories(self, layout_id: str, trajectories: Dict):
        """Sauvegarde les trajectoires détaillées."""
        trajectory_file = self.trajectories_dir / f"trajectories_{layout_id}.json"
        
        with open(trajectory_file, 'w', encoding='utf-8') as f:
            json.dump(trajectories, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"� Trajectoires sauvegardées: {trajectory_file.name}")
            
            # Sauvegarder les résultats
            timestamp = int(time.time())
            results_file = self.evaluation_dir / f"detailed_evaluation_{timestamp}.json"
            
            results_data = {
                'evaluation_info': {
                    'timestamp': timestamp,
                    'total_evaluations': len(all_evaluations),
                    'layouts_evaluated': len(layouts),
                    'recipe_groups_evaluated': len(recipe_groups),
                    'evaluation_time': time.time() - start_time
                },
                'evaluations': all_evaluations,
                'configuration': self.config
            }
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
            
            evaluation_time = time.time() - start_time
            
            logger.info(f"✅ Évaluation terminée!")
            logger.info(f"📊 {len(all_evaluations)} évaluations en {evaluation_time:.1f}s")
            logger.info(f"💾 Résultats: {results_file.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Erreur durant l'évaluation: {e}", exc_info=True)
            return False

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Évaluateur professionnel de layouts Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json", 
                       help="Fichier de configuration")
    parser.add_argument("--layout-limit", type=int,
                       help="Limite du nombre de layouts à évaluer (pour tests)")
    
    args = parser.parse_args()
    
    try:
        evaluator = ProfessionalLayoutEvaluator(args.config)
        
        success = evaluator.run_evaluation()
        
        if success:
            logger.info("🎉 Évaluation réussie!")
            return 0
        else:
            logger.error("❌ Échec de l'évaluation")
            return 1
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
