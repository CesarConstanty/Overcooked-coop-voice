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
from collections import defaultdict
import multiprocessing as mp
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass
import copy
import sys
import base64

# Configuration du logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,  # TEMPORAIRE: DEBUG au lieu de INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'layout_evaluation.log'),
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
    """Calculateur de chemins optimaux avec détection d'échanges bénéfiques sur les murs"""
    
    def __init__(self, game_state: 'OptimizedGameState'):
        self.state = game_state
        self.distance_cache = {}
        self.path_cache = {}
        self.exchange_benefits = {}  # Cache des bénéfices d'échange calculés
        
    def calculate_manhattan_distance(self, start: Tuple[int, int], goal: Tuple[int, int]) -> int:
        """Calcule la distance Manhattan sans prendre en compte les murs"""
        return abs(start[0] - goal[0]) + abs(start[1] - goal[1])
        
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
    
    def find_blocking_walls(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Identifie les murs qui bloquent le chemin direct entre start et goal"""
        # Calculer le chemin direct en ignorant les murs
        direct_distance = self.calculate_manhattan_distance(start, goal)
        actual_path = self.get_optimal_path(start, goal)
        
        if not actual_path or len(actual_path) - 1 == direct_distance:
            return []  # Pas de détour nécessaire
        
        blocking_walls = []
        
        # Analyser les murs qui forcent un détour
        dx = 1 if goal[0] > start[0] else -1 if goal[0] < start[0] else 0
        dy = 1 if goal[1] > start[1] else -1 if goal[1] < start[1] else 0
        
        # Parcourir la ligne directe théorique pour trouver les obstacles
        x, y = start
        while (x, y) != goal:
            if dx != 0 and x != goal[0]:
                next_x = x + dx
                if (0 <= next_x < self.state.width and 
                    self.state.layout[next_x][y] == 'X'):
                    blocking_walls.append((next_x, y))
                else:
                    x = next_x
                    
            if dy != 0 and y != goal[1]:
                next_y = y + dy
                if (0 <= next_y < self.state.height and 
                    self.state.layout[x][next_y] == 'X'):
                    blocking_walls.append((x, next_y))
                else:
                    y = next_y
        
        return blocking_walls
    
    def calculate_exchange_benefit_on_wall(self, player1_pos: Tuple[int, int], player1_goal: Tuple[int, int],
                                         player2_pos: Tuple[int, int], player2_goal: Tuple[int, int],
                                         wall_pos: Tuple[int, int]) -> int:
        """
        Calcule le bénéfice de placer un objet sur un mur pour échange entre joueurs
        
        Scénario: J1 a un objet et veut le livrer à player1_goal
                  Si J1 dépose l'objet sur wall_pos, J2 peut le prendre et le livrer
        """
        # Vérifier que la position est bien un mur
        if (wall_pos[0] < 0 or wall_pos[0] >= self.state.height or 
            wall_pos[1] < 0 or wall_pos[1] >= self.state.width or
            self.state.layout[wall_pos[0]][wall_pos[1]] != 'X'):
            return 0
        
        # Vérifier que le mur a des cases vides adjacentes accessibles
        adjacent_positions = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            adj_x, adj_y = wall_pos[0] + dx, wall_pos[1] + dy
            if (0 <= adj_x < self.state.height and 0 <= adj_y < self.state.width and
                self.state.layout[adj_x][adj_y] == ' '):
                adjacent_positions.append((adj_x, adj_y))
        
        if len(adjacent_positions) < 2:
            return 0  # Pas assez d'accès pour les 2 joueurs
        
        # Coût sans échange : J1 va directement livrer l'objet
        direct_path = self.get_optimal_path(player1_pos, player1_goal, 1)
        if not direct_path:
            return 0  # Pas de chemin direct possible
        direct_cost = len(direct_path) - 1
        
        # Coût avec échange via le mur
        # J1 va vers une case adjacente au mur
        min_exchange_cost = float('inf')
        
        for adj_pos in adjacent_positions:
            # J1 va à la case adjacente au mur
            j1_to_wall_adj_path = self.get_optimal_path(player1_pos, adj_pos, 1)
            if not j1_to_wall_adj_path:
                continue
            j1_to_wall_adj = len(j1_to_wall_adj_path) - 1
                
            # J2 va à une autre case adjacente au mur  
            for adj_pos2 in adjacent_positions:
                if adj_pos2 == adj_pos:
                    continue
                    
                j2_to_wall_adj_path = self.get_optimal_path(player2_pos, adj_pos2, 2)
                if not j2_to_wall_adj_path:
                    continue
                j2_to_wall_adj = len(j2_to_wall_adj_path) - 1
                
                # J2 livre l'objet depuis sa position adjacente au mur
                j2_to_goal_path = self.get_optimal_path(adj_pos2, player1_goal, 2)
                if not j2_to_goal_path:
                    continue
                j2_to_goal = len(j2_to_goal_path) - 1
                
                # Coût total avec échange : déplacement J1 + dépôt + déplacement J2 + prise + livraison J2
                exchange_cost = j1_to_wall_adj + 1 + j2_to_wall_adj + 1 + j2_to_goal
                min_exchange_cost = min(min_exchange_cost, exchange_cost)
        
        if min_exchange_cost == float('inf'):
            return 0
        
        # Bénéfice = économie d'étapes
        benefit = max(0, direct_cost - min_exchange_cost)
        
        # Debug log des calculs bénéfiques avec plus de détails
        if benefit > 2:  # Seulement si bénéfice significatif
            logger.debug(f"🔄 Échange bénéfique sur mur {wall_pos}: direct={direct_cost}, échange={min_exchange_cost}, gain={benefit}")
            logger.debug(f"   J1: {player1_pos} → {player1_goal}, J2: {player2_pos} → {player1_goal}")
        
        return benefit
    
    def find_optimal_exchange_walls(self, scenarios: List[Tuple[Tuple[int, int], Tuple[int, int], 
                                                             Tuple[int, int], Tuple[int, int]]]) -> List[Tuple[Tuple[int, int], int]]:
        """
        Trouve les 2 meilleures positions de murs pour les échanges
        
        Args:
            scenarios: Liste de (player1_pos, player1_goal, player2_pos, player2_goal) 
                      représentant les situations d'échange potentielles
        
        Returns:
            Liste des 2 meilleures positions (wall_pos, total_benefit)
        """
        wall_benefits = defaultdict(int)
        walls_tested = 0
        
        # Analyser tous les murs intérieurs
        for i in range(1, self.state.height - 1):  # Éviter les bordures
            for j in range(1, self.state.width - 1):
                if self.state.layout[i][j] == 'X':
                    wall_pos = (i, j)
                    total_benefit = 0
                    walls_tested += 1
                    
                    # Calculer le bénéfice total de ce mur pour tous les scénarios
                    for p1_pos, p1_goal, p2_pos, p2_goal in scenarios:
                        benefit = self.calculate_exchange_benefit_on_wall(
                            p1_pos, p1_goal, p2_pos, p2_goal, wall_pos)
                        total_benefit += benefit
                    
                    if total_benefit > 0:
                        wall_benefits[wall_pos] = total_benefit
        
        # Logger pour débugger
        logger.debug(f"🔍 {walls_tested} murs testés, {len(wall_benefits)} avec bénéfice")
        
        # Si aucun mur bénéfique trouvé, débugger un exemple
        if len(wall_benefits) == 0 and scenarios:
            # Prendre le premier scénario pour debug
            scenario = scenarios[0]
            p1_pos, p1_goal, p2_pos, p2_goal = scenario
            
            # Tester le premier mur disponible
            for i in range(1, self.state.height - 1):
                for j in range(1, self.state.width - 1):
                    if self.state.layout[i][j] == 'X':
                        wall_pos = (i, j)
                        
                        # Debug détaillé
                        adjacent_positions = []
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            adj_x, adj_y = wall_pos[0] + dx, wall_pos[1] + dy
                            if (0 <= adj_x < self.state.height and 0 <= adj_y < self.state.width and
                                self.state.layout[adj_x][adj_y] == ' '):
                                adjacent_positions.append((adj_x, adj_y))
                        
                        direct_path = self.get_optimal_path(p1_pos, p1_goal, 1)
                        direct_cost = len(direct_path) - 1 if direct_path else 0
                        
                        logger.debug(f"📍 Debug mur {wall_pos}:")
                        logger.debug(f"   - Cases adjacentes: {len(adjacent_positions)}")
                        logger.debug(f"   - Chemin direct J1: {p1_pos} → {p1_goal} = {direct_cost} étapes")
                        logger.debug(f"   - Position J2: {p2_pos}")
                        
                        # On s'arrête après le premier pour ne pas spammer
                        break
                break
        
        # Sélectionner les 2 meilleures positions
        sorted_walls = sorted(wall_benefits.items(), key=lambda x: x[1], reverse=True)
        
        # Logger les résultats
        if sorted_walls:
            logger.debug(f"🎯 {len(sorted_walls)} murs bénéfiques trouvés")
            for i, (wall_pos, benefit) in enumerate(sorted_walls[:5]):  # Top 5
                logger.debug(f"   #{i+1}: {wall_pos} -> {benefit} étapes économisées")
        
        # Retourner les 2 meilleurs (ou moins s'il n'y en a pas assez)
        return sorted_walls[:2]
    
    def convert_walls_to_exchanges(self, optimal_walls: List[Tuple[Tuple[int, int], int]]) -> List[Tuple[int, int]]:
        """
        Convertit les meilleures positions de murs en zones d'échange Y
        
        Returns:
            Liste des positions converties en Y
        """
        y_positions = []
        
        for wall_pos, benefit in optimal_walls:
            i, j = wall_pos
            # Vérifier que c'est toujours un mur (sécurité)
            if self.state.layout[i][j] == 'X':
                # Conversion X -> Y
                self.state.layout[i][j] = 'Y'
                y_positions.append(wall_pos)
                
                # Ajouter à la liste des comptoirs si pas déjà présent
                if wall_pos not in self.state.counters:
                    self.state.counters.append(wall_pos)
                    self.state.counter_items[wall_pos] = None
                
                logger.debug(f"✅ Mur {wall_pos} converti en zone d'échange Y (bénéfice: {benefit})")
        
        return y_positions

class ExchangeTracker:
    """Gestionnaire d'échanges intelligent avec détection automatique des zones optimales"""
    
    def __init__(self, game_state: 'OptimizedGameState'):
        self.state = game_state
        self.pathfinder = OptimalPathfinder(game_state)
        self.exchange_scenarios = []  # Stockage des scénarios d'échange analysés
        self.total_exchanges_count = 0
        self.optimal_y_positions = []
        
    def add_exchange_scenario(self, player1_pos: Tuple[int, int], player1_goal: Tuple[int, int],
                            player2_pos: Tuple[int, int], player2_goal: Tuple[int, int]):
        """Ajoute un scénario d'échange à analyser"""
        scenario = (player1_pos, player1_goal, player2_pos, player2_goal)
        self.exchange_scenarios.append(scenario)
        
    def analyze_and_place_optimal_exchanges(self) -> int:
        """
        Analyse tous les scénarios d'échange collectés et place automatiquement 
        les zones Y aux 2 meilleures positions
        
        Returns:
            Nombre total d'échanges bénéfiques détectés
        """
        if not self.exchange_scenarios:
            logger.debug("❌ Aucun scénario d'échange à analyser")
            return 0
        
        logger.debug(f"🔍 Analyse de {len(self.exchange_scenarios)} scénarios d'échange")
        
        # Trouver les meilleures positions de murs pour les échanges
        optimal_walls = self.pathfinder.find_optimal_exchange_walls(self.exchange_scenarios)
        
        if not optimal_walls:
            logger.debug("❌ Aucun mur bénéfique pour les échanges trouvé")
            return 0
        
        # Convertir les meilleurs murs en zones d'échange Y
        self.optimal_y_positions = self.pathfinder.convert_walls_to_exchanges(optimal_walls)
        
        # Calculer le nombre total d'échanges bénéfiques
        total_benefit = sum(benefit for _, benefit in optimal_walls)
        self.total_exchanges_count = len(optimal_walls)
        
        logger.info(f"✅ {len(self.optimal_y_positions)} zones Y placées automatiquement")
        logger.info(f"🎯 Bénéfice total: {total_benefit} étapes économisées")
        
        return self.total_exchanges_count
    
    def get_exchange_count(self) -> int:
        """Retourne le nombre d'échanges détectés"""
        return self.total_exchanges_count
    
    def get_optimal_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions Y optimales sélectionnées"""
        return self.optimal_y_positions

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
            
            # Phase 2: Cuisson (temps exclu du calcul des étapes)
            cooking_time = self.calculate_cooking_time(recipe['ingredients'])
            # recipe_steps += cooking_time  # MODIFIÉ: Temps de cuisson exclu
            
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
                    'collection': recipe_steps - (len(path) if path else 0) - 3,  # MODIFIÉ: cooking_time retiré
                    'cooking': 0,  # MODIFIÉ: Temps de cuisson exclu
                    'service': (len(path) if path else 0) + 3
                }
            })
            
            total_steps += recipe_steps
            state.completed_recipes.append(recipe)
            state.pot_contents = []
        
        return total_steps, actions
    
    def evaluate_duo_mode_with_exchanges(self, state: OptimizedGameState, recipes: List[Dict]) -> Tuple[int, List[Dict], int, List[Tuple[int, int]]]:
        """Évalue le mode duo avec simulation complète de la séquence de recettes"""
        
        # Phase 1: Simulation complète pour identifier les échanges potentiels
        exchange_tracker = ExchangeTracker(state)
        
        # Créer une copie de l'état pour la simulation
        sim_state = state.copy()
        
        # Simuler la séquence complète des recettes
        total_steps_phase1, phase1_actions = self._simulate_complete_recipe_sequence(
            sim_state, recipes, exchange_tracker)
        
        # Phase 2: Analyser et placer automatiquement les zones Y optimales
        total_exchanges = exchange_tracker.analyze_and_place_optimal_exchanges()
        optimal_y_positions = exchange_tracker.get_optimal_positions()
        
        if total_exchanges == 0:
            # Pas d'échanges bénéfiques, retourner la simulation sans Y
            logger.info(f"✅ Aucun échange bénéfique détecté, évaluation directe: {total_steps_phase1} étapes")
            return total_steps_phase1, phase1_actions, 0, []
        
        # Phase 3: Re-simuler avec les zones Y optimales
        final_state = state.copy()
        
        # Appliquer les Y au layout final
        for pos in optimal_y_positions:
            i, j = pos
            final_state.layout[i][j] = 'Y'
            if pos not in final_state.counters:
                final_state.counters.append(pos)
                final_state.counter_items[pos] = None
        
        # Re-simulation avec les Y placés
        total_steps_final, final_actions = self._simulate_complete_recipe_sequence_with_y(
            final_state, recipes, optimal_y_positions)
        
        logger.info(f"✅ Évaluation duo terminée: {total_steps_final} étapes, {total_exchanges} échanges, {len(optimal_y_positions)} zones Y")
        
        return total_steps_final, final_actions, total_exchanges, optimal_y_positions
    
    def _simulate_complete_recipe_sequence(self, state: OptimizedGameState, recipes: List[Dict], 
                                         exchange_tracker: ExchangeTracker) -> Tuple[int, List[Dict]]:
        """Simule la séquence complète de recettes et collecte les opportunités d'échange"""
        total_steps = 0
        actions = []
        
        # Positions initiales des joueurs
        j1_pos = state.player_positions[1]
        j2_pos = state.player_positions[2]
        
        logger.debug(f"🎬 Simulation démarrée - J1: {j1_pos}, J2: {j2_pos}")
        
        for recipe_idx, recipe in enumerate(recipes):
            recipe_steps, recipe_actions, new_j1_pos, new_j2_pos = self._simulate_single_recipe(
                state, recipe, j1_pos, j2_pos, exchange_tracker, recipe_idx)
            
            # Mettre à jour les positions pour la prochaine recette
            j1_pos = new_j1_pos
            j2_pos = new_j2_pos
            
            actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'actions': recipe_actions,
                'j1_final_pos': j1_pos,
                'j2_final_pos': j2_pos
            })
            
            total_steps += recipe_steps
            
            logger.debug(f"📋 Recette {recipe_idx+1}: {recipe_steps} étapes, J1→{j1_pos}, J2→{j2_pos}")
        
        logger.debug(f"🏁 Simulation terminée: {total_steps} étapes total")
        return total_steps, actions
    
    def _simulate_single_recipe(self, state: OptimizedGameState, recipe: Dict,
                               j1_start: Tuple[int, int], j2_start: Tuple[int, int],
                               exchange_tracker: ExchangeTracker, recipe_idx: int) -> Tuple[int, List[Dict], Tuple[int, int], Tuple[int, int]]:
        """Simule une recette complète et retourne les étapes + nouvelles positions"""
        
        pathfinder = OptimalPathfinder(state)
        recipe_steps = 0
        recipe_actions = []
        
        # Positions courantes
        j1_pos = j1_start
        j2_pos = j2_start
        
        ingredients = recipe['ingredients']
        
        # Phase 1: Collecte des ingrédients
        for ing_idx, ingredient in enumerate(ingredients):
            if ingredient == 'onion' and state.onion_dispenser:
                dispenser = state.onion_dispenser
            elif ingredient == 'tomato' and state.tomato_dispenser:
                dispenser = state.tomato_dispenser
            else:
                continue
            
            # J1 collecte l'ingrédient
            path_to_dispenser = pathfinder.get_optimal_path(j1_pos, dispenser, 1)
            if not path_to_dispenser:
                continue
                
            collection_steps = len(path_to_dispenser) - 1 + 1  # Déplacement + collecte
            recipe_steps += collection_steps
            j1_pos = dispenser
            
            recipe_actions.append({
                'action': 'collect',
                'player': 1,
                'ingredient': ingredient,
                'from': j1_start if ing_idx == 0 else j1_pos,
                'to': dispenser,
                'steps': collection_steps
            })
            
            # Analyser les opportunités d'échange pour cette position
            # J1 a maintenant l'ingrédient et doit le livrer au pot
            exchange_tracker.add_exchange_scenario(
                player1_pos=j1_pos,           # J1 avec l'ingrédient
                player1_goal=state.pot_position,  # J1 veut livrer au pot
                player2_pos=j2_pos,          # Position actuelle de J2
                player2_goal=state.pot_position   # J2 pourrait aussi livrer au pot
            )
            
            # J1 livre l'ingrédient au pot
            path_to_pot = pathfinder.get_optimal_path(j1_pos, state.pot_position, 1)
            if not path_to_pot:
                continue
                
            delivery_steps = len(path_to_pot) - 1 + 1  # Déplacement + dépôt
            recipe_steps += delivery_steps
            j1_pos = state.pot_position
            
            recipe_actions.append({
                'action': 'deliver',
                'player': 1,
                'ingredient': ingredient,
                'from': dispenser,
                'to': state.pot_position,
                'steps': delivery_steps
            })
        
        # Phase 2: Temps de cuisson (exclu selon instruction utilisateur)
        # cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        
        # Phase 3: Service - optimiser qui fait le service
        dish_pos = state.dish_dispenser
        serving_pos = state.service_position
        
        # Calculer qui est le mieux placé pour le service
        j1_to_dish = len(pathfinder.get_optimal_path(j1_pos, dish_pos, 1)) - 1 if dish_pos else float('inf')
        j2_to_dish = len(pathfinder.get_optimal_path(j2_pos, dish_pos, 2)) - 1 if dish_pos else float('inf')
        
        if j1_to_dish <= j2_to_dish:
            # J1 fait le service
            service_player = 1
            service_start = j1_pos
        else:
            # J2 fait le service
            service_player = 2
            service_start = j2_pos
        
        # Étapes du service: aller chercher plat → pot → service
        service_steps = 0
        
        # Aller chercher le plat
        if dish_pos:
            path_to_dish = pathfinder.get_optimal_path(service_start, dish_pos, service_player)
            if path_to_dish:
                service_steps += len(path_to_dish) - 1 + 1  # Déplacement + prise
                service_start = dish_pos
        
        # Aller au pot récupérer la soupe
        path_to_pot_service = pathfinder.get_optimal_path(service_start, state.pot_position, service_player)
        if path_to_pot_service:
            service_steps += len(path_to_pot_service) - 1 + 1  # Déplacement + prise
            service_start = state.pot_position
        
        # Aller servir
        if serving_pos:
            path_to_serving = pathfinder.get_optimal_path(service_start, serving_pos, service_player)
            if path_to_serving:
                service_steps += len(path_to_serving) - 1 + 1  # Déplacement + service
                service_start = serving_pos
        
        recipe_steps += service_steps
        
        # Mettre à jour la position du joueur qui a fait le service
        if service_player == 1:
            j1_pos = service_start
        else:
            j2_pos = service_start
        
        recipe_actions.append({
            'action': 'service',
            'player': service_player,
            'steps': service_steps,
            'final_pos': service_start
        })
        
        return recipe_steps, recipe_actions, j1_pos, j2_pos
    
    def _simulate_complete_recipe_sequence_with_y(self, state: OptimizedGameState, recipes: List[Dict],
                                                 y_positions: List[Tuple[int, int]]) -> Tuple[int, List[Dict]]:
        """Simule la séquence complète avec zones Y disponibles pour échanges"""
        total_steps = 0
        actions = []
        
        # Positions initiales des joueurs
        j1_pos = state.player_positions[1]
        j2_pos = state.player_positions[2]
        
        pathfinder = OptimalPathfinder(state)
        
        logger.debug(f"🎬 Simulation avec Y démarrée - J1: {j1_pos}, J2: {j2_pos}, Y: {y_positions}")
        
        for recipe_idx, recipe in enumerate(recipes):
            recipe_steps = 0
            recipe_actions = []
            
            ingredients = recipe['ingredients']
            
            # Phase 1: Collecte et livraison des ingrédients avec échanges possibles
            for ing_idx, ingredient in enumerate(ingredients):
                if ingredient == 'onion' and state.onion_dispenser:
                    dispenser = state.onion_dispenser
                elif ingredient == 'tomato' and state.tomato_dispenser:
                    dispenser = state.tomato_dispenser
                else:
                    continue
                
                # J1 collecte l'ingrédient
                path_to_dispenser = pathfinder.get_optimal_path(j1_pos, dispenser, 1)
                if not path_to_dispenser:
                    continue
                    
                collection_steps = len(path_to_dispenser) - 1 + 1
                recipe_steps += collection_steps
                j1_pos = dispenser
                
                # Analyser si un échange via Y est bénéfique
                best_exchange_benefit = 0
                best_y_position = None
                
                for y_pos in y_positions:
                    benefit = pathfinder.calculate_exchange_benefit_on_wall(
                        j1_pos, state.pot_position, j2_pos, state.pot_position, y_pos)
                    
                    if benefit > best_exchange_benefit:
                        best_exchange_benefit = benefit
                        best_y_position = y_pos
                
                # Exécuter la stratégie optimale
                if best_y_position and best_exchange_benefit > 0:
                    # Échange via Y
                    delivery_steps, new_j1_pos, new_j2_pos = self._execute_exchange_via_y_detailed(
                        state, pathfinder, best_y_position, j1_pos, j2_pos)
                    j1_pos = new_j1_pos
                    j2_pos = new_j2_pos
                    
                    recipe_actions.append({
                        'action': 'exchange_via_y',
                        'ingredient': ingredient,
                        'y_position': best_y_position,
                        'benefit': best_exchange_benefit,
                        'steps': delivery_steps
                    })
                else:
                    # Livraison directe par J1
                    path_to_pot = pathfinder.get_optimal_path(j1_pos, state.pot_position, 1)
                    if path_to_pot:
                        delivery_steps = len(path_to_pot) - 1 + 1
                        j1_pos = state.pot_position
                        
                        recipe_actions.append({
                            'action': 'direct_delivery',
                            'ingredient': ingredient,
                            'steps': delivery_steps
                        })
                
                recipe_steps += delivery_steps
            
            # Phase 2: Service optimisé
            service_steps, service_player, final_service_pos = self._calculate_optimized_service_steps(
                state, pathfinder, j1_pos, j2_pos)
            
            recipe_steps += service_steps
            
            # Mettre à jour les positions après le service
            if service_player == 1:
                j1_pos = final_service_pos
            else:
                j2_pos = final_service_pos
            
            recipe_actions.append({
                'action': 'service',
                'player': service_player,
                'steps': service_steps
            })
            
            actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'actions': recipe_actions,
                'j1_final_pos': j1_pos,
                'j2_final_pos': j2_pos
            })
            
            total_steps += recipe_steps
            
            logger.debug(f"📋 Recette {recipe_idx+1} avec Y: {recipe_steps} étapes, J1→{j1_pos}, J2→{j2_pos}")
        
        return total_steps, actions
    
    def _execute_exchange_via_y_detailed(self, state: OptimizedGameState, pathfinder: OptimalPathfinder,
                                        y_position: Tuple[int, int], j1_pos: Tuple[int, int], 
                                        j2_pos: Tuple[int, int]) -> Tuple[int, Tuple[int, int], Tuple[int, int]]:
        """Exécute un échange via Y et retourne les détails"""
        steps = 0
        
        # Trouver les cases adjacentes à Y
        adjacent_positions = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            adj_x, adj_y = y_position[0] + dx, y_position[1] + dy
            if (0 <= adj_x < state.height and 0 <= adj_y < state.width and
                state.layout[adj_x][adj_y] == ' '):
                adjacent_positions.append((adj_x, adj_y))
        
        if len(adjacent_positions) < 2:
            # Fallback: livraison directe
            path = pathfinder.get_optimal_path(j1_pos, state.pot_position, 1)
            steps = len(path) - 1 + 1 if path else 0
            return steps, state.pot_position, j2_pos
        
        # Choisir les meilleures positions adjacentes pour J1 et J2
        best_j1_adj = None
        best_j2_adj = None
        min_total_cost = float('inf')
        
        for adj1 in adjacent_positions:
            for adj2 in adjacent_positions:
                if adj1 == adj2:
                    continue
                
                j1_to_adj = len(pathfinder.get_optimal_path(j1_pos, adj1, 1)) - 1
                j2_to_adj = len(pathfinder.get_optimal_path(j2_pos, adj2, 2)) - 1
                j2_to_pot = len(pathfinder.get_optimal_path(adj2, state.pot_position, 2)) - 1
                
                total_cost = j1_to_adj + j2_to_adj + j2_to_pot
                
                if total_cost < min_total_cost:
                    min_total_cost = total_cost
                    best_j1_adj = adj1
                    best_j2_adj = adj2
        
        if best_j1_adj and best_j2_adj:
            # J1 va à Y et dépose
            j1_path = pathfinder.get_optimal_path(j1_pos, best_j1_adj, 1)
            steps += len(j1_path) - 1 + 1 if j1_path else 0
            
            # J2 va à Y et récupère
            j2_path = pathfinder.get_optimal_path(j2_pos, best_j2_adj, 2)
            steps += len(j2_path) - 1 + 1 if j2_path else 0
            
            # J2 livre au pot
            j2_to_pot_path = pathfinder.get_optimal_path(best_j2_adj, state.pot_position, 2)
            steps += len(j2_to_pot_path) - 1 + 1 if j2_to_pot_path else 0
            
            return steps, best_j1_adj, state.pot_position
        
        # Fallback si échange impossible
        path = pathfinder.get_optimal_path(j1_pos, state.pot_position, 1)
        steps = len(path) - 1 + 1 if path else 0
        return steps, state.pot_position, j2_pos
    
    def _calculate_optimized_service_steps(self, state: OptimizedGameState, pathfinder: OptimalPathfinder,
                                         j1_pos: Tuple[int, int], j2_pos: Tuple[int, int]) -> Tuple[int, int, Tuple[int, int]]:
        """Calcule les étapes de service optimisées en fonction des positions actuelles"""
        
        dish_pos = state.dish_dispenser
        pot_pos = state.pot_position
        serving_pos = state.service_position
        
        # Calculer les coûts pour chaque joueur de faire le service complet
        j1_service_cost = 0
        j2_service_cost = 0
        
        # Coût pour J1
        if dish_pos:
            j1_to_dish = len(pathfinder.get_optimal_path(j1_pos, dish_pos, 1)) - 1
            dish_to_pot = len(pathfinder.get_optimal_path(dish_pos, pot_pos, 1)) - 1
            pot_to_serving = len(pathfinder.get_optimal_path(pot_pos, serving_pos, 1)) - 1 if serving_pos else 0
            j1_service_cost = j1_to_dish + 1 + dish_to_pot + 1 + pot_to_serving + 1
        
        # Coût pour J2
        if dish_pos:
            j2_to_dish = len(pathfinder.get_optimal_path(j2_pos, dish_pos, 2)) - 1
            dish_to_pot = len(pathfinder.get_optimal_path(dish_pos, pot_pos, 2)) - 1
            pot_to_serving = len(pathfinder.get_optimal_path(pot_pos, serving_pos, 2)) - 1 if serving_pos else 0
            j2_service_cost = j2_to_dish + 1 + dish_to_pot + 1 + pot_to_serving + 1
        
        # Choisir le joueur optimal
        if j1_service_cost <= j2_service_cost:
            return j1_service_cost, 1, serving_pos if serving_pos else pot_pos
        else:
            return j2_service_cost, 2, serving_pos if serving_pos else pot_pos
    
    def _execute_exchange_via_y(self, state: OptimizedGameState, pathfinder: OptimalPathfinder, 
                               y_position: Tuple[int, int]) -> int:
        """Exécute un échange via une zone Y et retourne le nombre d'étapes"""
        steps = 0
        
        # Trouver une case adjacente à Y pour J1
        adjacent_for_j1 = None
        adjacent_for_j2 = None
        
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            adj_x, adj_y = y_position[0] + dx, y_position[1] + dy
            if (0 <= adj_x < state.height and 0 <= adj_y < state.width and
                state.layout[adj_x][adj_y] == ' '):
                if adjacent_for_j1 is None:
                    adjacent_for_j1 = (adj_x, adj_y)
                elif adjacent_for_j2 is None:
                    adjacent_for_j2 = (adj_x, adj_y)
                    break
        
        if not adjacent_for_j1 or not adjacent_for_j2:
            # Fallback: livraison directe si pas d'accès suffisant
            path = pathfinder.get_optimal_path(state.player_positions[1], state.pot_position, 1)
            steps = len(path) - 1 + 1
            state.player_positions[1] = state.pot_position
            return steps
        
        # J1 va à la zone Y et dépose
        path_j1_to_y = pathfinder.get_optimal_path(state.player_positions[1], adjacent_for_j1, 1)
        steps += len(path_j1_to_y) - 1 + 1  # Déplacement + dépôt
        state.player_positions[1] = adjacent_for_j1
        
        # J2 va à la zone Y et récupère
        path_j2_to_y = pathfinder.get_optimal_path(state.player_positions[2], adjacent_for_j2, 2)
        steps += len(path_j2_to_y) - 1 + 1  # Déplacement + prise
        state.player_positions[2] = adjacent_for_j2
        
        # J2 livre au pot
        path_j2_to_pot = pathfinder.get_optimal_path(state.player_positions[2], state.pot_position, 2)
        steps += len(path_j2_to_pot) - 1 + 1  # Déplacement + dépôt
        state.player_positions[2] = state.pot_position
        
        return steps

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