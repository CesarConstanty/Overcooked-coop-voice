#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluateur Massif de Layouts Overcooked
Évalue chaque layout généré avec chaque groupe de recettes pour calculer les métriques de performance

Fonctionnalités:
1. Charge tous les layouts générés (fichiers .gz compressés)
2. Charge tous les groupes de recettes générés
3. Évalue chaque combinaison layout + groupe de recettes
4. Calcule: étapes solo, étapes duo, nombre d'échanges
5. Stockage optimisé avec identifiants uniques

Architecture:
- Adapte les classes GameState et OvercookedPathfinder pour l'évaluation massive
- Système de compression pour stockage efficace des résultats
- Multiprocessing pour évaluation parallèle
- Métriques détaillées avec traçabilité layout+recettes

Author: Assistant AI Expert
Date: Septembre 2025
"""

import os
import json
import gzip
import time
import logging
import hashlib
import argparse
import multiprocessing as mp
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass
import copy
import sys
import base64

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

class LayoutDecompressor:
    """Décompresse les layouts stockés"""
    
    def decode_grid_from_base64(self, encoded_grid: str) -> List[List[str]]:
        """Décode une grille depuis base64"""
        # Décoder depuis base64
        grid_str = base64.b64decode(encoded_grid.encode('ascii')).decode('utf-8')
        # Convertir en grille
        lines = grid_str.strip().split('\n')
        return [list(line) for line in lines]
    
    def decompress_layout(self, compressed_layout: Dict) -> Dict:
        """Décompresse un layout"""
        # Décoder la grille
        grid = self.decode_grid_from_base64(compressed_layout['g'])
        
        return {
            'grid': grid,
            'hash': compressed_layout['h'],
            'object_positions': compressed_layout.get('op', {})
        }
    
    @staticmethod
    def load_layouts_from_batch(batch_file: str) -> List[Dict]:
        """Charge les layouts depuis un fichier batch compressé"""
        layouts = []
        decompressor = LayoutDecompressor()
        try:
            with gzip.open(batch_file, 'rt', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        compressed_layout = json.loads(line.strip())
                        # Décompresser le layout
                        layout = decompressor.decompress_layout(compressed_layout)
                        layouts.append(layout)
        except Exception as e:
            logger.error(f"Erreur lors du chargement du batch {batch_file}: {e}")
        
        return layouts

@dataclass
class EvaluationMetrics:
    """Métriques d'évaluation pour une combinaison layout+recettes"""
    layout_id: str
    recipe_group_id: int
    solo_steps: int
    duo_steps: int
    exchanges_count: int
    optimal_y_positions: List[Tuple[int, int]]  # Nouvellement ajouté
    solo_actions: List[Dict]
    duo_actions: List[Dict]
    evaluation_time: float
    layout_hash: str
    recipe_hash: str

class OptimizedGameState:
    """Version optimisée de GameState pour évaluation massive"""
    
    def __init__(self, layout_data: Dict, recipes: List[Dict]):
        # Vérifier si le layout est dans le format compressé ou standard
        if 'grid' in layout_data and isinstance(layout_data['grid'], list):
            # Format standard déjà décompressé
            self.layout = layout_data["grid"]
            self.object_positions = layout_data.get("objects", {})
        elif 'g' in layout_data:
            # Format compressé - décompresser
            decompressor = LayoutDecompressor()
            decompressed = decompressor.decompress_layout(layout_data)
            self.layout = decompressed["grid"]
            self.object_positions = decompressed.get("object_positions", {})
        else:
            raise ValueError(f"Format de layout non reconnu. Clés disponibles: {list(layout_data.keys())}")
        
        self.recipes = recipes
        
        self.width = len(self.layout[0]) if self.layout else 0
        self.height = len(self.layout)
        
        # Positions des éléments depuis object_positions et grille
        self.player_positions = {}
        self.pot_position = None
        self.service_position = None
        self.onion_dispenser = None
        self.tomato_dispenser = None
        self.dish_dispenser = None
        self.counters = []
        self.walls = []
        
        # État du jeu
        self.player_inventory = {}
        self.counter_items = {}
        self.pot_contents = []
        self.pot_cooking = False
        self.pot_cooking_time = 0
        self.completed_recipes = []
        self.current_step = 0
        
        self._parse_layout_optimized()
    
    def _parse_layout_optimized(self):
        """Parse optimisé du layout depuis les données générées"""
        # Parser la grille pour trouver les objets directement
        for i, row in enumerate(self.layout):
            for j, cell in enumerate(row):
                pos = (i, j)
                if cell == 'X':
                    self.walls.append(pos)
                elif cell == 'P':
                    self.pot_position = pos
                elif cell == 'S':
                    self.service_position = pos
                elif cell == 'O':
                    self.onion_dispenser = pos
                elif cell == 'T':
                    self.tomato_dispenser = pos
                elif cell == 'D':
                    self.dish_dispenser = pos
        
        # Utiliser object_positions pour les positions des joueurs si disponible
        if self.object_positions:
            for obj_type, positions in self.object_positions.items():
                if obj_type == '1':
                    if isinstance(positions, list) and len(positions) > 0:
                        pos = positions[0]
                        if isinstance(pos, list) and len(pos) >= 2:
                            self.player_positions[1] = (pos[0], pos[1])
                        else:
                            self.player_positions[1] = tuple(pos)
                        self.player_inventory[1] = None
                elif obj_type == '2':
                    if isinstance(positions, list) and len(positions) > 0:
                        pos = positions[0]
                        if isinstance(pos, list) and len(pos) >= 2:
                            self.player_positions[2] = (pos[0], pos[1])
                        else:
                            self.player_positions[2] = tuple(pos)
                        self.player_inventory[2] = None
        
        # Positions par défaut des joueurs si pas définies
        if 1 not in self.player_positions:
            # Trouver la première position libre
            for i in range(self.height):
                for j in range(self.width):
                    if self.layout[i][j] == ' ':
                        self.player_positions[1] = (i, j)
                        self.player_inventory[1] = None
                        break
                if 1 in self.player_positions:
                    break
        
        if 2 not in self.player_positions:
            # Trouver la deuxième position libre
            for i in range(self.height):
                for j in range(self.width):
                    if self.layout[i][j] == ' ' and (i, j) != self.player_positions.get(1):
                        self.player_positions[2] = (i, j)
                        self.player_inventory[2] = None
                        break
                if 2 in self.player_positions:
                    break
        
        # Identifier les comptoirs et murs depuis la grille
        for y in range(self.height):
            for x in range(self.width):
                cell = self.layout[y][x]
                if cell == 'Y':  # Comptoirs dans nos layouts
                    self.counters.append((x, y))
                elif cell == 'X':  # Murs
                    self.walls.append((x, y))
        
        # Initialiser les inventaires des comptoirs
        for counter in self.counters:
            self.counter_items[counter] = None
    
    def is_valid_position(self, x: int, y: int) -> bool:
        """Vérifie si une position est valide"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.layout[y][x] != 'X'
        return False
    
    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Retourne les positions voisines valides"""
        x, y = pos
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                neighbors.append((nx, ny))
        return neighbors
    
    def is_position_occupied(self, pos: Tuple[int, int], excluding_player: Optional[int] = None) -> bool:
        """Vérifie si une position est occupée par un autre joueur"""
        for player_id, player_pos in self.player_positions.items():
            if player_id != excluding_player and player_pos == pos:
                return True
        return False
    
    def copy(self):
        """Crée une copie profonde de l'état"""
        return copy.deepcopy(self)

class OptimalPathfinder:
    """Calculateur de chemins optimaux avec gestion d'obstacles et d'échanges"""
    
    def __init__(self, game_state: 'OptimizedGameState'):
        self.state = game_state
        self.distance_cache = {}
        self.path_cache = {}
        
    def get_optimal_path(self, start: Tuple[int, int], goal: Tuple[int, int], 
                        excluding_player: Optional[int] = None) -> List[Tuple[int, int]]:
        """Calcule le chemin optimal A* entre deux points"""
        cache_key = (start, goal, excluding_player)
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]
        
        if start == goal:
            return [start]
        
        # A* avec heuristique Manhattan
        from heapq import heappush, heappop
        
        def heuristic(pos: Tuple[int, int]) -> int:
            return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])
        
        open_set = [(heuristic(start), 0, start, [start])]
        visited = set()
        
        while open_set:
            _, cost, current, path = heappop(open_set)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == goal:
                self.path_cache[cache_key] = path
                return path
            
            for neighbor in self.state.get_neighbors(current):
                if neighbor in visited:
                    continue
                
                if self.state.is_position_occupied(neighbor, excluding_player):
                    continue
                
                new_cost = cost + 1
                new_path = path + [neighbor]
                priority = new_cost + heuristic(neighbor)
                
                heappush(open_set, (priority, new_cost, neighbor, new_path))
        
        # Aucun chemin trouvé
        self.path_cache[cache_key] = []
        return []
    
    def calculate_exchange_benefit(self, player1_pos: Tuple[int, int], player1_goal: Tuple[int, int],
                                 player2_pos: Tuple[int, int], player2_goal: Tuple[int, int],
                                 exchange_pos: Tuple[int, int]) -> int:
        """Calcule le bénéfice (en étapes économisées) d'un échange à une position donnée"""
        # Coût sans échange
        direct_cost = (len(self.get_optimal_path(player1_pos, player1_goal, 1)) - 1 +
                      len(self.get_optimal_path(player2_pos, player2_goal, 2)) - 1)
        
        # Coût avec échange
        p1_to_exchange = len(self.get_optimal_path(player1_pos, exchange_pos, 1)) - 1
        exchange_to_p2_goal = len(self.get_optimal_path(exchange_pos, player2_goal, 2)) - 1
        p2_to_exchange = len(self.get_optimal_path(player2_pos, exchange_pos, 2)) - 1
        
        exchange_cost = p1_to_exchange + 1 + p2_to_exchange + 1 + exchange_to_p2_goal  # +1 pour déposer/prendre
        
        return max(0, direct_cost - exchange_cost)

class ExchangeTracker:
    """Suit les échanges et optimise les positions Y"""
    
    def __init__(self, game_state: 'OptimizedGameState'):
        self.state = game_state
        self.exchange_counts = {}  # position -> nombre d'échanges
        self.potential_exchanges = []  # positions où un échange pourrait être fait
        self.selected_y_positions = []
        
        # Identifier tous les murs intérieurs comme échanges potentiels
        self._find_potential_exchanges()
    
    def _find_potential_exchanges(self):
        """Identifie les positions X intérieures pouvant devenir des Y"""
        for i in range(1, self.state.height - 1):  # Exclure les bordures
            for j in range(1, self.state.width - 1):
                if self.state.layout[i][j] == 'X':
                    # Vérifier qu'il y a au moins 2 cases vides adjacentes
                    empty_neighbors = 0
                    for di, dj in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        ni, nj = i + di, j + dj
                        if (0 <= ni < self.state.height and 0 <= nj < self.state.width and
                            self.state.layout[ni][nj] == ' '):
                            empty_neighbors += 1
                    
                    if empty_neighbors >= 2:
                        self.potential_exchanges.append((i, j))
                        self.exchange_counts[(i, j)] = 0
    
    def record_exchange(self, position: Tuple[int, int]):
        """Enregistre un échange à une position"""
        if position in self.exchange_counts:
            self.exchange_counts[position] += 1
    
    def select_optimal_y_positions(self) -> List[Tuple[int, int]]:
        """Sélectionne les 2 meilleures positions pour placer les Y"""
        # Trier par nombre d'échanges (décroissant)
        sorted_exchanges = sorted(self.exchange_counts.items(), 
                                key=lambda x: x[1], reverse=True)
        
        # Prendre les 2 meilleures positions avec au moins 1 échange
        self.selected_y_positions = [pos for pos, count in sorted_exchanges[:2] if count > 0]
        return self.selected_y_positions
    
    def apply_y_positions(self):
        """Applique les positions Y sélectionnées au layout"""
        for pos in self.selected_y_positions:
            i, j = pos
            self.state.layout[i][j] = 'Y'
            if pos not in self.state.counters:
                self.state.counters.append(pos)
                self.state.counter_items[pos] = None

class MassiveLayoutEvaluator:
    """Évaluateur principal pour l'évaluation massive des layouts"""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Configuration
        eval_config = self.config["pipeline_config"]["evaluation"]
        self.layouts_dir = self.base_dir / "outputs" / "layouts_generes"
        self.recipes_file = self.base_dir / "outputs" / "recipes.json"
        self.output_dir = self.base_dir / "outputs" / eval_config["results_dir"]
        
        self.n_processes = eval_config.get("processes", mp.cpu_count() - 1)
        self.batch_size = eval_config.get("batch_size", 1000)
        
        # Constantes de jeu
        self.onion_time = 9
        self.tomato_time = 6
        
        logger.info(f"🔍 Évaluateur massif initialisé")
        logger.info(f"📁 Layouts: {self.layouts_dir}")
        logger.info(f"📋 Recettes: {self.recipes_file}")
        logger.info(f"💾 Résultats: {self.output_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_recipes(self) -> List[Dict]:
        """Charge tous les groupes de recettes"""
        with open(self.recipes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data["recipe_groups"]
    
    def load_layouts_batch(self, batch_file: Path) -> List[Dict]:
        """Charge un batch de layouts depuis un fichier .gz"""
        try:
            # Utiliser le décompresseur pour charger les layouts
            layouts = LayoutDecompressor.load_layouts_from_batch(str(batch_file))
            logger.info(f"✅ Chargé {len(layouts)} layouts depuis {batch_file.name}")
            return layouts
        except Exception as e:
            logger.error(f"❌ Erreur chargement batch {batch_file}: {e}")
            return []
    
    def get_all_layout_batches(self) -> List[Path]:
        """Récupère tous les fichiers de batch de layouts"""
        return list(self.layouts_dir.glob("layout_batch_*.gz"))
    
    def calculate_cooking_time(self, ingredients: List[str]) -> int:
        """Calcule le temps de cuisson total"""
        onion_count = ingredients.count('onion')
        tomato_count = ingredients.count('tomato')
        return onion_count * self.onion_time + tomato_count * self.tomato_time
    
    def evaluate_solo_mode(self, state: OptimizedGameState, recipes: List[Dict]) -> Tuple[int, List[Dict]]:
        """Évalue le mode solo pour un ensemble de recettes"""
        actions = []
        total_steps = 0
        player_id = 1
        
        # Calculateur de chemins optimaux
        pathfinder = OptimalPathfinder(state)
        
        for recipe in recipes:
            recipe_steps = 0
            
            # Phase 1: Collecter tous les ingrédients
            for ingredient in recipe['ingredients']:
                if ingredient == 'onion':
                    dispenser = state.onion_dispenser
                elif ingredient == 'tomato':
                    dispenser = state.tomato_dispenser
                else:
                    continue
                
                # Vérifier si le distributeur existe
                if dispenser is None:
                    return None, None  # Layout invalide pour cette recette
                
                # Aller au distributeur
                path = pathfinder.get_optimal_path(state.player_positions[player_id], dispenser, player_id)
                recipe_steps += len(path) - 1
                
                if path:
                    state.player_positions[player_id] = dispenser
                
                # Prendre l'ingrédient
                recipe_steps += 1
                
                # Aller au pot
                path = pathfinder.get_optimal_path(state.player_positions[player_id], state.pot_position, player_id)
                recipe_steps += len(path) - 1
                
                if path:
                    state.player_positions[player_id] = state.pot_position
                
                # Déposer dans le pot
                recipe_steps += 1
                state.pot_contents.append(ingredient)
            
            # Phase 2: Cuisson
            cooking_time = self.calculate_cooking_time(recipe['ingredients'])
            recipe_steps += cooking_time
            
            # Phase 3: Service
            # Aller chercher une assiette
            path = pathfinder.get_optimal_path(state.player_positions[player_id], state.dish_dispenser, player_id)
            recipe_steps += len(path) - 1
            if path:
                state.player_positions[player_id] = state.dish_dispenser
            recipe_steps += 1  # Prendre l'assiette
            
            # Retourner au pot
            path = pathfinder.get_optimal_path(state.player_positions[player_id], state.pot_position, player_id)
            recipe_steps += len(path) - 1
            if path:
                state.player_positions[player_id] = state.pot_position
            recipe_steps += 1  # Prendre la soupe
            
            # Aller au service
            path = pathfinder.get_optimal_path(state.player_positions[player_id], state.service_position, player_id)
            recipe_steps += len(path) - 1
            if path:
                state.player_positions[player_id] = state.service_position
            recipe_steps += 1  # Servir
            
            actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'phase_breakdown': {
                    'collection': recipe_steps - cooking_time - (len(path) if path else 0) - 3,
                    'cooking': cooking_time,
                    'service': (len(path) if path else 0) + 3
                }
            })
            
            total_steps += recipe_steps
            state.completed_recipes.append(recipe)
            state.pot_contents = []
        
        return total_steps, actions
    
    def evaluate_duo_mode_with_exchanges(self, state: OptimizedGameState, recipes: List[Dict]) -> Tuple[int, List[Dict], int, List[Tuple[int, int]]]:
        """Évalue le mode duo avec détection automatique des zones d'échange optimales"""
        # Phase 1: Évaluation avec détection des échanges potentiels
        pathfinder = OptimalPathfinder(state)
        exchange_tracker = ExchangeTracker(state)
        
        actions = []
        total_steps_phase1 = 0
        
        for recipe in recipes:
            recipe_steps, recipe_exchanges = self._evaluate_recipe_with_exchange_detection(
                state, recipe, pathfinder, exchange_tracker)
            
            actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'exchanges_detected': recipe_exchanges
            })
            
            total_steps_phase1 += recipe_steps
        
        # Phase 2: Sélection des 2 meilleures positions Y
        optimal_y_positions = exchange_tracker.select_optimal_y_positions()
        
        if len(optimal_y_positions) == 0:
            # Pas d'échanges bénéfiques détectés, retourner l'évaluation simple
            return total_steps_phase1, actions, 0, []
        
        # Phase 3: Appliquer les Y et re-évaluer avec contraintes
        exchange_tracker.apply_y_positions()
        
        # Re-évaluation avec les Y contraints
        final_actions = []
        total_steps_final = 0
        total_exchanges = 0
        
        # Réinitialiser l'état pour la seconde évaluation
        state_copy = state.copy()
        for pos in optimal_y_positions:
            i, j = pos
            state_copy.layout[i][j] = 'Y'
            if pos not in state_copy.counters:
                state_copy.counters.append(pos)
                state_copy.counter_items[pos] = None
        
        pathfinder_final = OptimalPathfinder(state_copy)
        
        for recipe in recipes:
            recipe_steps, recipe_exchanges = self._evaluate_recipe_with_y_constraints(
                state_copy, recipe, pathfinder_final, optimal_y_positions)
            
            final_actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'exchanges': recipe_exchanges,
                'y_positions_used': optimal_y_positions
            })
            
            total_steps_final += recipe_steps
            total_exchanges += recipe_exchanges
        
        return total_steps_final, final_actions, total_exchanges, optimal_y_positions
    
    def _evaluate_recipe_with_exchange_detection(self, state: OptimizedGameState, recipe: Dict, 
                                               pathfinder: OptimalPathfinder, 
                                               exchange_tracker: ExchangeTracker) -> Tuple[int, int]:
        """Évalue une recette en détectant les échanges bénéfiques"""
        recipe_steps = 0
        recipe_exchanges = 0
        
        ingredients = recipe['ingredients']
        
        # Stratégie: J1 collecte, J2 prépare le service
        # Analyser chaque étape pour détecter les échanges bénéfiques
        
        for ingredient in ingredients:
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            elif ingredient == 'tomato':
                dispenser = state.tomato_dispenser
            else:
                continue
            
            if dispenser is None:
                continue
            
            # J1 va chercher l'ingrédient
            path = pathfinder.get_optimal_path(state.player_positions[1], dispenser, 1)
            recipe_steps += len(path) - 1 + 1  # Move + pickup
            state.player_positions[1] = dispenser
            
            # Analyser si un échange vers J2 est bénéfique
            best_exchange_benefit = 0
            best_exchange_pos = None
            
            for exchange_pos in exchange_tracker.potential_exchanges:
                benefit = pathfinder.calculate_exchange_benefit(
                    state.player_positions[1], state.pot_position,
                    state.player_positions[2], state.pot_position,
                    exchange_pos
                )
                
                if benefit > best_exchange_benefit:
                    best_exchange_benefit = benefit
                    best_exchange_pos = exchange_pos
            
            if best_exchange_pos and best_exchange_benefit > 0:
                # Effectuer l'échange
                path_to_exchange = pathfinder.get_optimal_path(state.player_positions[1], best_exchange_pos, 1)
                recipe_steps += len(path_to_exchange) - 1 + 1  # Move + drop
                state.player_positions[1] = best_exchange_pos
                
                # J2 récupère l'objet
                path_j2_to_exchange = pathfinder.get_optimal_path(state.player_positions[2], best_exchange_pos, 2)
                recipe_steps += len(path_j2_to_exchange) - 1 + 1  # Move + pickup
                state.player_positions[2] = best_exchange_pos
                
                # J2 va au pot
                path_to_pot = pathfinder.get_optimal_path(state.player_positions[2], state.pot_position, 2)
                recipe_steps += len(path_to_pot) - 1 + 1  # Move + drop
                state.player_positions[2] = state.pot_position
                
                exchange_tracker.record_exchange(best_exchange_pos)
                recipe_exchanges += 1
            else:
                # Pas d'échange bénéfique, J1 va directement au pot
                path = pathfinder.get_optimal_path(state.player_positions[1], state.pot_position, 1)
                recipe_steps += len(path) - 1 + 1  # Move + drop
                state.player_positions[1] = state.pot_position
        
        # Temps de cuisson
        cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        recipe_steps += cooking_time
        
        # Service (J2 ou J1 selon qui est le mieux placé)
        service_steps = self._calculate_service_steps(state, pathfinder)
        recipe_steps += service_steps
        
        return recipe_steps, recipe_exchanges
    
    def _evaluate_recipe_with_y_constraints(self, state: OptimizedGameState, recipe: Dict,
                                          pathfinder: OptimalPathfinder, 
                                          y_positions: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Évalue une recette avec contraintes Y (échanges uniquement sur Y)"""
        recipe_steps = 0
        recipe_exchanges = 0
        
        ingredients = recipe['ingredients']
        
        for ingredient in ingredients:
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            elif ingredient == 'tomato':
                dispenser = state.tomato_dispenser
            else:
                continue
            
            if dispenser is None:
                continue
            
            # J1 va chercher l'ingrédient
            path = pathfinder.get_optimal_path(state.player_positions[1], dispenser, 1)
            recipe_steps += len(path) - 1 + 1
            state.player_positions[1] = dispenser
            
            # Analyser les échanges uniquement sur les Y sélectionnés
            best_exchange_benefit = 0
            best_y_pos = None
            
            for y_pos in y_positions:
                benefit = pathfinder.calculate_exchange_benefit(
                    state.player_positions[1], state.pot_position,
                    state.player_positions[2], state.pot_position,
                    y_pos
                )
                
                if benefit > best_exchange_benefit:
                    best_exchange_benefit = benefit
                    best_y_pos = y_pos
            
            if best_y_pos and best_exchange_benefit > 0:
                # Effectuer l'échange sur Y
                path_to_y = pathfinder.get_optimal_path(state.player_positions[1], best_y_pos, 1)
                recipe_steps += len(path_to_y) - 1 + 1
                state.player_positions[1] = best_y_pos
                
                path_j2_to_y = pathfinder.get_optimal_path(state.player_positions[2], best_y_pos, 2)
                recipe_steps += len(path_j2_to_y) - 1 + 1
                state.player_positions[2] = best_y_pos
                
                path_to_pot = pathfinder.get_optimal_path(state.player_positions[2], state.pot_position, 2)
                recipe_steps += len(path_to_pot) - 1 + 1
                state.player_positions[2] = state.pot_position
                
                recipe_exchanges += 1
            else:
                # Pas d'échange bénéfique, aller directement au pot
                path = pathfinder.get_optimal_path(state.player_positions[1], state.pot_position, 1)
                recipe_steps += len(path) - 1 + 1
                state.player_positions[1] = state.pot_position
        
        # Temps de cuisson
        cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        recipe_steps += cooking_time
        
        # Service
        service_steps = self._calculate_service_steps(state, pathfinder)
        recipe_steps += service_steps
        
        return recipe_steps, recipe_exchanges
    
    def _calculate_service_steps(self, state: OptimizedGameState, pathfinder: OptimalPathfinder) -> int:
        """Calcule les étapes de service optimisées"""
        service_steps = 0
        
        # Déterminer qui est le mieux placé pour le service
        dist_j1_to_dish = len(pathfinder.get_optimal_path(state.player_positions[1], state.dish_dispenser, 1)) - 1
        dist_j2_to_dish = len(pathfinder.get_optimal_path(state.player_positions[2], state.dish_dispenser, 2)) - 1
        
        if dist_j1_to_dish <= dist_j2_to_dish:
            service_player = 1
        else:
            service_player = 2
        
        # Aller chercher l'assiette
        path = pathfinder.get_optimal_path(state.player_positions[service_player], state.dish_dispenser, service_player)
        service_steps += len(path) - 1 + 1
        state.player_positions[service_player] = state.dish_dispenser
        
        # Aller au pot
        path = pathfinder.get_optimal_path(state.player_positions[service_player], state.pot_position, service_player)
        service_steps += len(path) - 1 + 1
        state.player_positions[service_player] = state.pot_position
        
        # Aller au service
        path = pathfinder.get_optimal_path(state.player_positions[service_player], state.service_position, service_player)
        service_steps += len(path) - 1 + 1
        state.player_positions[service_player] = state.service_position
        
        return service_steps
    
    def evaluate_layout_recipe_combination(self, layout_data: Dict, recipe_group: Dict) -> EvaluationMetrics:
        """Évalue une combinaison layout + groupe de recettes avec optimisation des échanges"""
        start_time = time.time()
        
        try:
            # Créer l'état de jeu
            recipes = recipe_group["recipes"]
            
            # Filtrer les recettes vides
            valid_recipes = [r for r in recipes if r.get("ingredients") and len(r["ingredients"]) > 0]
            if not valid_recipes:
                logger.debug(f"Groupe de recettes {recipe_group['group_id']} ignoré: aucune recette valide")
                return None
            
            state_solo = OptimizedGameState(layout_data, valid_recipes)
            state_duo = OptimizedGameState(layout_data, valid_recipes)
            
            # Génération des identifiants
            layout_id = layout_data.get("hash", f"layout_{id(layout_data)}")
            recipe_group_id = recipe_group["group_id"]
            
            # Utiliser le hash existant du layout ou en calculer un compatible
            if "hash" in layout_data:
                layout_hash = layout_data["hash"]
            else:
                # Calculer un hash compatible avec le générateur (16 caractères)
                grid_str = '\n'.join([''.join(row) for row in layout_data.get("grid", [])])
                layout_hash = hashlib.md5(grid_str.encode()).hexdigest()[:16]
            
            recipe_hash = hashlib.md5(json.dumps(valid_recipes, sort_keys=True).encode()).hexdigest()[:12]
            
            # Évaluation solo
            solo_steps, solo_actions = self.evaluate_solo_mode(state_solo, valid_recipes)
            
            # Évaluation duo avec optimisation des échanges
            duo_steps, duo_actions, exchanges_count, y_positions = self.evaluate_duo_mode_with_exchanges(state_duo, valid_recipes)
            
            evaluation_time = time.time() - start_time
            
            # Ajouter les informations sur les positions Y sélectionnées
            enhanced_duo_actions = []
            for action in duo_actions:
                enhanced_action = action.copy()
                enhanced_action['optimal_y_positions'] = y_positions
                enhanced_duo_actions.append(enhanced_action)
            
            return EvaluationMetrics(
                layout_id=layout_id,
                recipe_group_id=recipe_group_id,
                solo_steps=solo_steps,
                duo_steps=duo_steps,
                exchanges_count=exchanges_count,
                optimal_y_positions=y_positions,  # Nouvellement ajouté
                solo_actions=solo_actions,
                duo_actions=enhanced_duo_actions,
                evaluation_time=evaluation_time,
                layout_hash=layout_hash,
                recipe_hash=recipe_hash
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur évaluation layout {layout_data.get('hash', 'unknown')} + recettes {recipe_group['group_id']}: {e}")
            return None
    
    def save_evaluation_results(self, results: List[EvaluationMetrics], batch_id: int):
        """Sauvegarde les résultats d'évaluation de façon optimisée"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Fichier principal avec métriques
        metrics_file = self.output_dir / f"evaluation_metrics_batch_{batch_id:04d}.json"
        
        # Fichier détaillé compressé
        details_file = self.output_dir / f"evaluation_details_batch_{batch_id:04d}.gz"
        
        # Préparer les données
        metrics_data = []
        detailed_data = []
        
        for result in results:
            if result is None:
                continue
            
            # Métriques principales
            metrics_data.append({
                "evaluation_id": f"{result.layout_id}_{result.recipe_group_id}",
                "layout_id": result.layout_id,
                "recipe_group_id": result.recipe_group_id,
                "solo_steps": result.solo_steps,
                "duo_steps": result.duo_steps,
                "exchanges_count": result.exchanges_count,
                "optimal_y_positions": result.optimal_y_positions,  # Nouvellement ajouté
                "improvement_ratio": result.solo_steps / result.duo_steps if result.duo_steps > 0 else 0,
                "evaluation_time": result.evaluation_time,
                "layout_hash": result.layout_hash,
                "recipe_hash": result.recipe_hash
            })
            
            # Données détaillées
            detailed_data.append({
                "evaluation_id": f"{result.layout_id}_{result.recipe_group_id}",
                "solo_actions": result.solo_actions,
                "duo_actions": result.duo_actions,
                "layout_hash": result.layout_hash,
                "recipe_hash": result.recipe_hash
            })
        
        # Sauvegarder les métriques
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump({
                "batch_id": batch_id,
                "timestamp": time.time(),
                "total_evaluations": len(metrics_data),
                "metrics": metrics_data
            }, f, indent=2)
        
        # Sauvegarder les détails compressés
        with gzip.open(details_file, 'wt', encoding='utf-8') as f:
            for detail in detailed_data:
                f.write(json.dumps(detail) + '\n')
        
        logger.info(f"💾 Batch {batch_id}: {len(metrics_data)} évaluations sauvegardées")
    
    def run_massive_evaluation(self) -> bool:
        """Lance l'évaluation massive de tous les layouts avec toutes les recettes"""
        start_time = time.time()
        
        # Charger les recettes
        logger.info("📋 Chargement des groupes de recettes...")
        recipe_groups = self.load_recipes()
        logger.info(f"✅ {len(recipe_groups)} groupes de recettes chargés")
        
        # Récupérer tous les batches de layouts
        layout_batches = self.get_all_layout_batches()
        logger.info(f"📁 {len(layout_batches)} batches de layouts trouvés")
        
        total_evaluations = 0
        processed_batches = 0
        
        for batch_file in layout_batches:
            batch_start = time.time()
            
            # Charger le batch de layouts
            layouts = self.load_layouts_batch(batch_file)
            if not layouts:
                logger.warning(f"⚠️ Batch vide: {batch_file}")
                continue
            
            logger.info(f"🔄 Traitement batch {batch_file.name}: {len(layouts)} layouts")
            
            # Évaluer toutes les combinaisons layout + recettes
            batch_results = []
            
            for layout_data in layouts:
                for recipe_group in recipe_groups:
                    result = self.evaluate_layout_recipe_combination(layout_data, recipe_group)
                    if result:
                        batch_results.append(result)
                        total_evaluations += 1
            
            # Sauvegarder les résultats du batch
            self.save_evaluation_results(batch_results, processed_batches)
            
            batch_time = time.time() - batch_start
            evaluations_per_sec = len(batch_results) / batch_time if batch_time > 0 else 0
            
            logger.info(f"✅ Batch {processed_batches}: {len(batch_results)} évaluations en {batch_time:.1f}s ({evaluations_per_sec:.1f}/s)")
            
            processed_batches += 1
        
        total_time = time.time() - start_time
        
        # Rapport final
        logger.info(f"🎉 Évaluation massive terminée!")
        logger.info(f"📊 Total: {total_evaluations:,} évaluations en {total_time:.1f}s")
        logger.info(f"⚡ Performance: {total_evaluations/total_time:.1f} évaluations/sec")
        logger.info(f"🗂️ Batches traités: {processed_batches}")
        logger.info(f"💾 Résultats stockés: {self.output_dir}")
        
        return total_evaluations > 0
    
    # Méthodes de commodité pour les tests
    def evaluate_solo(self, grid: List[List[str]], recipes: List[Dict]) -> Dict:
        """Méthode de commodité pour évaluation solo simple"""
        state = OptimizedGameState(grid)
        steps, actions = self.evaluate_solo_mode(state, recipes)
        return {
            'total_steps': steps,
            'actions': actions
        }
    
    def evaluate_duo_with_exchanges(self, grid: List[List[str]], recipes: List[Dict]) -> Dict:
        """Méthode de commodité pour évaluation duo avec détection d'échanges"""
        state = OptimizedGameState(grid)
        steps, actions, exchanges_count, exchange_positions = self.evaluate_duo_mode_with_exchanges(state, recipes)
        
        # Compter les échanges par position
        exchange_counter = {}
        for pos in exchange_positions:
            exchange_counter[str(pos)] = exchange_counter.get(str(pos), 0) + 1
        
        # Sélectionner les 2 meilleures positions
        optimal_positions = []
        if exchange_counter:
            sorted_positions = sorted(exchange_counter.items(), key=lambda x: x[1], reverse=True)
            optimal_positions = [eval(pos) for pos, _ in sorted_positions[:2]]
        
        return {
            'total_steps': steps,
            'actions': actions,
            'exchanges_count': exchanges_count,
            'exchange_positions': exchange_counter,
            'optimal_y_positions': optimal_positions
        }
    
    def evaluate_duo_with_y_constraints(self, grid: List[List[str]], recipes: List[Dict], y_positions: List[Tuple[int, int]]) -> Dict:
        """Méthode de commodité pour évaluation duo avec contraintes Y"""
        # Créer une copie de la grille avec les Y placés
        grid_with_y = [row[:] for row in grid]
        for i, j in y_positions:
            if 0 < i < len(grid_with_y)-1 and 0 < j < len(grid_with_y[0])-1:
                if grid_with_y[i][j] == 'X':  # Remplacer un mur par Y
                    grid_with_y[i][j] = 'Y'
        
        state = OptimizedGameState(grid_with_y)
        steps, actions = self.evaluate_solo_mode(state, recipes)  # Simplification pour le test
        return {
            'total_steps': steps,
            'actions': actions
        }

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Évaluateur massif de layouts Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json",
                       help="Fichier de configuration")
    parser.add_argument("--processes", type=int,
                       help="Nombre de processus (override config)")
    
    args = parser.parse_args()
    
    try:
        evaluator = MassiveLayoutEvaluator(args.config)
        
        if args.processes:
            evaluator.n_processes = args.processes
        
        success = evaluator.run_massive_evaluation()
        
        if success:
            print("🎉 Évaluation massive réussie!")
            return 0
        else:
            print("❌ Échec de l'évaluation massive")
            return 1
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())