#!/usr/bin/env python3
"""
Évaluateur d'Actions pour Recettes - Overcooked Sciences Cognitives

Ce module évalue le nombre d'actions nécessaires pour compléter des ensembles de recettes
dans les layouts Overcooked, en comparant les stratégies solo et coopératives.

Fonctionnalités principales:
1. Évalue les actions nécessaires pour 1 joueur seul
2. Évalue les actions nécessaires pour 2 joueurs avec échanges optimisés via comptoirs Y
3. Les comptoirs Y sont placés stratégiquement pour minimiser les distances de déplacement
4. Compte les échanges réalisés sur chaque position Y (ou X en repli)
5. Génère un fichier de résultats structuré pour analyse cognitive

Système d'échange optimisé:
- Y = comptoirs d'échange prioritaires, positionnés pour contourner les obstacles
- X = comptoirs de repli si aucun Y disponible
- Les Y permettent de faire passer objets d'un côté à l'autre des obstacles efficacement

Auteur: Assistant IA Spécialisé  
Date: Septembre 2025
Contexte: Recherche en sciences cognitives sur la coopération humain-IA
"""

import json
import heapq
import time
import os
import argparse
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass
from functools import partial

# Import des utilitaires locaux
from utils import read_ndjson, write_ndjson, decompress_grid, get_timestamp


@dataclass
class Recipe:
    """Représente une recette à réaliser"""
    recipe_id: int
    ingredients: List[str]
    recipe_value: int
    cooking_time: int


class AStarPathfinder:
    """Implémentation A* pour pathfinding optimisé dans grilles Overcooked"""
    
    def __init__(self, grid: List[List[str]]):
        """Initialise le pathfinder avec la grille"""
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0
        
        # Pré-calculer les positions valides
        self.valid_positions = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if grid[r][c] != 'X':  # Toute position non-mur est valide
                    self.valid_positions.add((r, c))
    
    def manhattan_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Distance de Manhattan entre deux positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
    
    def get_neighbors(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Retourne les voisins valides d'une position"""
        r, c = position
        neighbors = []
        
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:  # 4 directions
            nr, nc = r + dr, c + dc
            if (nr, nc) in self.valid_positions:
                neighbors.append((nr, nc))
        
        return neighbors
    
    def find_shortest_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """Trouve le plus court chemin avec A*"""
        if start == goal:
            return [start]
        
        if start not in self.valid_positions or goal not in self.valid_positions:
            return None
        
        # Priority queue: (f_score, g_score, position, path)
        open_set = [(0, 0, start, [start])]
        visited = set()
        
        while open_set:
            f_score, g_score, current, path = heapq.heappop(open_set)
            
            if current in visited:
                continue
            
            visited.add(current)
            
            if current == goal:
                return path
            
            for neighbor in self.get_neighbors(current):
                if neighbor not in visited:
                    new_g_score = g_score + 1
                    new_f_score = new_g_score + self.manhattan_distance(neighbor, goal)
                    new_path = path + [neighbor]
                    
                    heapq.heappush(open_set, (new_f_score, new_g_score, neighbor, new_path))
        
        return None  # Pas de chemin trouvé
    
    def calculate_distance(self, start: Tuple[int, int], goal: Tuple[int, int]) -> int:
        """Calcule la distance du plus court chemin"""
        path = self.find_shortest_path(start, goal)
        return len(path) - 1 if path else float('inf')


class RecipeActionEvaluator:
    """Évaluateur d'actions pour les recettes Overcooked"""
    
    def __init__(self):
        """Initialise l'évaluateur"""
        self.layouts_file = "layouts_with_objects.ndjson"
        self.recipes_file = "ensemble_recettes.json"
        self.output_file = "recipe_evaluation_results.ndjson"
        
        # Cache pour les pathfinders
        self.pathfinder_cache = {}
    
    def load_layouts(self) -> List[Dict]:
        """Charge les layouts depuis le fichier NDJSON"""
        print("📁 Chargement des layouts...")
        layouts = read_ndjson(self.layouts_file)
        print(f"✅ {len(layouts)} layouts chargés")
        return layouts
    
    def load_recipe_combinations(self) -> List[Dict]:
        """Charge les combinaisons de recettes"""
        print("🍽️ Chargement des combinaisons de recettes...")
        
        with open(self.recipes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Gérer le nouveau format de fichier généré par 0_generateur_recettes.py
        if 'selected_combinations' in data:
            combinations = data['selected_combinations']
        elif 'recipe_combinations' in data:
            combinations = data['recipe_combinations']
        elif isinstance(data, list):
            combinations = data
        else:
            combinations = []
            
        print(f"✅ {len(combinations)} combinaisons de recettes chargées")
        
        return combinations
    
    def get_pathfinder(self, grid: List[List[str]]) -> AStarPathfinder:
        """Obtient un pathfinder pour une grille (avec cache)"""
        grid_str = ''.join(''.join(row) for row in grid)
        
        if grid_str not in self.pathfinder_cache:
            self.pathfinder_cache[grid_str] = AStarPathfinder(grid)
        
        return self.pathfinder_cache[grid_str]
    
    def can_access_wall_for_exchange(self, pathfinder: AStarPathfinder, player_pos: Tuple[int, int], exchange_pos: Tuple[int, int]) -> bool:
        """
        Vérifie si un joueur peut accéder à un comptoir d'échange (Y ou X).
        - Pour Y: peut être directement accessible ou nécessiter case adjacente
        - Pour X: le joueur doit pouvoir atteindre une case adjacente au mur
        """
        exchange_i, exchange_j = exchange_pos
        
        # Vérifier si la position d'échange est directement accessible (cas Y)
        if exchange_pos in pathfinder.valid_positions:
            distance = pathfinder.calculate_distance(player_pos, exchange_pos)
            return distance != float('inf')
        
        # Sinon, vérifier l'accès aux cases adjacentes (cas X)
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for di, dj in directions:
            adj_i, adj_j = exchange_i + di, exchange_j + dj
            if (adj_i, adj_j) in pathfinder.valid_positions:
                # Vérifier si le joueur peut atteindre cette position adjacente
                distance = pathfinder.calculate_distance(player_pos, (adj_i, adj_j))
                if distance != float('inf'):
                    return True
        
        return False
    
    def get_exchange_distance(self, pathfinder: AStarPathfinder, player_pos: Tuple[int, int], exchange_pos: Tuple[int, int]) -> int:
        """
        Calcule la distance pour qu'un joueur accède à un comptoir d'échange (Y ou X).
        - Pour Y: distance directe si accessible, sinon vers case adjacente la plus proche
        - Pour X: distance vers la case adjacente au mur la plus proche
        """
        # Vérifier si la position d'échange est directement accessible (cas Y)
        if exchange_pos in pathfinder.valid_positions:
            return pathfinder.calculate_distance(player_pos, exchange_pos)
        
        # Sinon, chercher la case adjacente la plus proche (cas X)
        exchange_i, exchange_j = exchange_pos
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        min_distance = float('inf')
        
        for di, dj in directions:
            adj_i, adj_j = exchange_i + di, exchange_j + dj
            if (adj_i, adj_j) in pathfinder.valid_positions:
                distance = pathfinder.calculate_distance(player_pos, (adj_i, adj_j))
                if distance < min_distance:
                    min_distance = distance
        
        return min_distance if min_distance != float('inf') else float('inf')
    
    def get_player_position_after_exchange(self, pathfinder: AStarPathfinder, exchange_pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Détermine où positionner un joueur après interaction avec un comptoir d'échange.
        - Pour Y (directement accessible): position Y elle-même
        - Pour X (mur): case adjacente accessible la plus proche
        """
        # Si la position d'échange est directement accessible (cas Y)
        if exchange_pos in pathfinder.valid_positions:
            return exchange_pos
        
        # Sinon, trouver case adjacente accessible (cas X)
        exchange_i, exchange_j = exchange_pos
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for di, dj in directions:
            adj_i, adj_j = exchange_i + di, exchange_j + dj
            if (adj_i, adj_j) in pathfinder.valid_positions:
                return (adj_i, adj_j)
        
        # Fallback: retourner position originale si aucune case adjacente trouvée
        return exchange_pos
    
    def extract_positions(self, grid: List[List[str]]) -> Dict[str, List[Tuple[int, int]]]:
        """Extrait les positions des éléments dans la grille"""
        positions = defaultdict(list)
        
        for r in range(len(grid)):
            for c in range(len(grid[0])):
                cell = grid[r][c]
                if cell != '.':  # Tout sauf les cases vides
                    positions[cell].append((r, c))
        
        return dict(positions)
    
    def evaluate_solo_actions(self, grid: List[List[str]], recipes: List[Recipe]) -> int:
        """
        Évalue le nombre d'actions nécessaires pour 1 joueur seul.
        
        Le joueur 1 doit réaliser toutes les recettes en solo.
        Le joueur 2 est ignoré dans cette évaluation.
        """
        positions = self.extract_positions(grid)
        pathfinder = self.get_pathfinder(grid)
        
        # Position du joueur 1
        if '1' not in positions:
            return float('inf')
        
        player_pos = positions['1'][0]
        total_actions = 0
        
        # Positions des éléments nécessaires
        onion_dispensers = positions.get('O', [])
        tomato_dispensers = positions.get('T', [])
        pots = positions.get('P', [])
        dishes = positions.get('D', [])
        serving_areas = positions.get('S', [])
        
        if not (onion_dispensers and tomato_dispensers and pots and dishes and serving_areas):
            return float('inf')
        
        current_pos = player_pos
        
        for recipe in recipes:
            # Actions pour cette recette
            recipe_actions = 0
            
            # 1. Collecter les ingrédients
            for ingredient in recipe.ingredients:
                if ingredient == 'onion':
                    # Aller au distributeur d'oignons le plus proche
                    closest_onion = min(onion_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                    distance = pathfinder.calculate_distance(current_pos, closest_onion)
                    recipe_actions += distance + 1  # distance + action de ramassage
                    current_pos = closest_onion
                    
                elif ingredient == 'tomato':
                    # Aller au distributeur de tomates le plus proche
                    closest_tomato = min(tomato_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                    distance = pathfinder.calculate_distance(current_pos, closest_tomato)
                    recipe_actions += distance + 1  # distance + action de ramassage
                    current_pos = closest_tomato
            
            # 2. Aller à la casserole et cuisiner
            closest_pot = min(pots, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_pot)
            recipe_actions += distance + 1  # distance + action de dépôt
            current_pos = closest_pot
            
            # 3. Attendre la cuisson (temps de cuisson = actions)
            recipe_actions += recipe.cooking_time
            
            # 4. Aller chercher une assiette
            closest_dish = min(dishes, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_dish)
            recipe_actions += distance + 1  # distance + action de ramassage
            current_pos = closest_dish
            
            # 5. Retourner à la casserole pour servir
            distance = pathfinder.calculate_distance(current_pos, closest_pot)
            recipe_actions += distance + 1  # distance + action de ramassage du plat cuisiné
            current_pos = closest_pot
            
            # 6. Aller à la zone de service
            closest_serving = min(serving_areas, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_serving)
            recipe_actions += distance + 1  # distance + action de service
            current_pos = closest_serving
            
            total_actions += recipe_actions
        
        return total_actions
    
    def evaluate_coop_actions(self, grid: List[List[str]], recipes: List[Recipe]) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """
        Évalue le nombre d'actions nécessaires pour 2 joueurs coopératifs.
        
        Règles strictes:
        a) Les joueurs ne peuvent déplacer qu'un objet à la fois
        b) Les joueurs peuvent poser les objets sur les comptoirs X, et l'autre joueur peut ensuite les récupérer
        c) Cette solution permet de diminuer le nombre d'étapes nécessaires pour compléter le niveau
        d) Compte le nombre d'échanges réalisés sur chaque position X
        e) Le résultat est le nombre d'étapes cumulées des deux joueurs
        
        Retourne (total_actions_cumulées, exchanges_per_position).
        """
        positions = self.extract_positions(grid)
        pathfinder = self.get_pathfinder(grid)
        
        # Positions des joueurs
        if '1' not in positions or '2' not in positions:
            return float('inf'), {}
        
        player1_pos = positions['1'][0]
        player2_pos = positions['2'][0]
        
        # Positions des éléments
        onion_dispensers = positions.get('O', [])
        tomato_dispensers = positions.get('T', [])
        pots = positions.get('P', [])
        dishes = positions.get('D', [])
        serving_areas = positions.get('S', [])
        
        # Les Y sont les comptoirs d'échange optimaux placés stratégiquement
        # pour minimiser les distances de déplacement entre joueurs
        exchange_points = positions.get('Y', [])
        
        # Si pas de Y disponibles, utiliser les X comme solution de repli
        if not exchange_points:
            exchange_points = positions.get('X', [])
        
        if not (onion_dispensers and tomato_dispensers and pots and dishes and serving_areas):
            return float('inf'), {}
        
        # Compteur d'échanges par position (Y prioritaires, X en repli)
        exchanges_per_position = defaultdict(int)
        
        # Stratégie coopérative optimisée avec division des tâches
        # Évaluer deux stratégies et prendre la meilleure
        
        # Stratégie 1: Division égale des recettes
        strategy1_actions, strategy1_exchanges = self._evaluate_split_recipes_strategy(
            pathfinder, player1_pos, player2_pos, recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
        )
        
        # Stratégie 2: Spécialisation (P1 ingrédients, P2 service) avec échanges
        strategy2_actions, strategy2_exchanges = self._evaluate_specialization_strategy(
            pathfinder, player1_pos, player2_pos, recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
        )
        
        # Choisir la meilleure stratégie
        if strategy1_actions <= strategy2_actions:
            return strategy1_actions, strategy1_exchanges
        else:
            return strategy2_actions, strategy2_exchanges
    
    def _evaluate_split_recipes_strategy(self, pathfinder: AStarPathfinder, 
                                        player1_pos: Tuple[int, int], player2_pos: Tuple[int, int],
                                        recipes: List[Recipe], onion_dispensers: List[Tuple[int, int]],
                                        tomato_dispensers: List[Tuple[int, int]], pots: List[Tuple[int, int]],
                                        dishes: List[Tuple[int, int]], serving_areas: List[Tuple[int, int]],
                                        exchange_points: List[Tuple[int, int]]) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """Stratégie 1: Division égale des recettes entre joueurs"""
        
        exchanges_per_position = defaultdict(int)
        mid_point = len(recipes) // 2
        player1_recipes = recipes[:mid_point]
        player2_recipes = recipes[mid_point:]
        
        # Calculer actions pour chaque joueur en parallèle
        player1_actions = self._calculate_player_actions_optimized(
            pathfinder, player1_pos, player1_recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas,
            exchange_points, exchanges_per_position, player_id=1
        )
        
        player2_actions = self._calculate_player_actions_optimized(
            pathfinder, player2_pos, player2_recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas,
            exchange_points, exchanges_per_position, player_id=2
        )
        
        # Actions cumulées des deux joueurs (pas maximum, mais somme)
        total_cumulated_actions = player1_actions + player2_actions
        
        return total_cumulated_actions, dict(exchanges_per_position)
    
    def _evaluate_specialization_strategy(self, pathfinder: AStarPathfinder,
                                        player1_pos: Tuple[int, int], player2_pos: Tuple[int, int],
                                        recipes: List[Recipe], onion_dispensers: List[Tuple[int, int]],
                                        tomato_dispensers: List[Tuple[int, int]], pots: List[Tuple[int, int]],
                                        dishes: List[Tuple[int, int]], serving_areas: List[Tuple[int, int]],
                                        exchange_points: List[Tuple[int, int]]) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """
        Stratégie 2: Spécialisation optimisée avec échanges d'ingrédients uniquement.
        
        RÈGLES STRICTES:
        - AUCUN échange de soupe cuisinée/plats finis
        - Seuls les ingrédients bruts peuvent être échangés  
        - Minimiser le nombre total d'étapes coopératives
        """
        
        exchanges_per_position = defaultdict(int)
        
        if not exchange_points:
            # Pas d'échanges possibles, revenir à la stratégie de division
            return self._evaluate_split_recipes_strategy(
                pathfinder, player1_pos, player2_pos, recipes,
                onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
            )
        
        # Analyser les stratégies possibles et choisir la plus optimale
        strategies = []
        
        # Stratégie 1: P1 collecte, P2 cuisine et sert (avec échanges d'ingrédients)
        strategy1_actions, strategy1_exchanges = self._evaluate_collect_cook_strategy(
            pathfinder, player1_pos, player2_pos, recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
        )
        strategies.append((strategy1_actions, strategy1_exchanges, "collect_cook"))
        
        # Stratégie 2: Division équilibrée avec échanges optimisés
        strategy2_actions, strategy2_exchanges = self._evaluate_balanced_strategy(
            pathfinder, player1_pos, player2_pos, recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
        )
        strategies.append((strategy2_actions, strategy2_exchanges, "balanced"))
        
        # Choisir la stratégie avec le moins d'actions totales
        best_strategy = min(strategies, key=lambda x: x[0])
        return best_strategy[0], best_strategy[1]
    
    def _evaluate_collect_cook_strategy(self, pathfinder: AStarPathfinder,
                                      player1_pos: Tuple[int, int], player2_pos: Tuple[int, int],
                                      recipes: List[Recipe], onion_dispensers: List[Tuple[int, int]],
                                      tomato_dispensers: List[Tuple[int, int]], pots: List[Tuple[int, int]],
                                      dishes: List[Tuple[int, int]], serving_areas: List[Tuple[int, int]],
                                      exchange_points: List[Tuple[int, int]]) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """
        P1 collecte les ingrédients, P2 cuisine et sert avec échanges via comptoirs X.
        
        RÈGLES STRICTES D'ÉCHANGE:
        1) Un objet déplacé à la fois
        2) Peut poser un objet sur un mur/comptoir (X) en se plaçant sur une case vide adjacente
        3) Peut récupérer un objet posé sur un comptoir en étant sur une case vide adjacente  
        4) Déposer + récupérer un objet = 1 échange
        5) Permet de passer l'objet d'un côté à l'autre sans faire le tour des obstacles
        """
        
        exchanges_per_position = defaultdict(int)
        
        # Choisir le comptoir d'échange optimal (accessible par les deux joueurs)
        best_exchange = None
        min_total_distance = float('inf')
        
        for exchange_wall in exchange_points:
            if (self.can_access_wall_for_exchange(pathfinder, player1_pos, exchange_wall) and 
                self.can_access_wall_for_exchange(pathfinder, player2_pos, exchange_wall)):
                
                dist1 = self.get_exchange_distance(pathfinder, player1_pos, exchange_wall)
                dist2 = self.get_exchange_distance(pathfinder, player2_pos, exchange_wall)
                total_dist = dist1 + dist2
                
                if total_dist < min_total_distance:
                    min_total_distance = total_dist
                    best_exchange = exchange_wall
        
        if best_exchange is None:
            # Pas d'échange possible, revenir à la stratégie de division
            return self._evaluate_split_recipes_strategy(
                pathfinder, player1_pos, player2_pos, recipes,
                onion_dispensers, tomato_dispensers, pots, dishes, serving_areas, exchange_points
            )
        
        player1_actions = 0
        player2_actions = 0
        current_p1_pos = player1_pos
        current_p2_pos = player2_pos
        
        for recipe in recipes:
            # P1 collecte TOUS les ingrédients de la recette
            for ingredient in recipe.ingredients:
                if ingredient == 'onion':
                    # P1 va chercher un oignon
                    closest_onion = min(onion_dispensers, 
                                      key=lambda pos: pathfinder.calculate_distance(current_p1_pos, pos))
                    distance_to_onion = pathfinder.calculate_distance(current_p1_pos, closest_onion)
                    player1_actions += distance_to_onion + 1  # aller + ramasser
                    current_p1_pos = closest_onion
                    
                    # P1 va au comptoir pour DÉPOSER l'oignon
                    distance_to_exchange = self.get_exchange_distance(pathfinder, current_p1_pos, best_exchange)
                    player1_actions += distance_to_exchange + 1  # aller près du comptoir + déposer
                    
                    # P1 se positionne au comptoir d'échange après dépôt
                    current_p1_pos = self.get_player_position_after_exchange(pathfinder, best_exchange)
                    
                    # P2 va au comptoir pour RÉCUPÉRER l'oignon
                    distance_p2_to_exchange = self.get_exchange_distance(pathfinder, current_p2_pos, best_exchange)
                    player2_actions += distance_p2_to_exchange + 1  # aller près du comptoir + récupérer
                    
                    # P2 se positionne au comptoir d'échange après récupération
                    current_p2_pos = self.get_player_position_after_exchange(pathfinder, best_exchange)
                    
                    # COMPTABILISER 1 ÉCHANGE (dépôt + récupération = 1 échange complet)
                    exchanges_per_position[best_exchange] += 1
                    
                elif ingredient == 'tomato':
                    # P1 va chercher une tomate
                    closest_tomato = min(tomato_dispensers, 
                                       key=lambda pos: pathfinder.calculate_distance(current_p1_pos, pos))
                    distance_to_tomato = pathfinder.calculate_distance(current_p1_pos, closest_tomato)
                    player1_actions += distance_to_tomato + 1  # aller + ramasser
                    current_p1_pos = closest_tomato
                    
                    # P1 va au comptoir pour DÉPOSER la tomate
                    distance_to_exchange = self.get_exchange_distance(pathfinder, current_p1_pos, best_exchange)
                    player1_actions += distance_to_exchange + 1  # aller près du comptoir + déposer
                    
                    # P1 se positionne au comptoir d'échange après dépôt
                    current_p1_pos = self.get_player_position_after_exchange(pathfinder, best_exchange)
                    
                    # P2 va au comptoir pour RÉCUPÉRER la tomate
                    distance_p2_to_exchange = self.get_exchange_distance(pathfinder, current_p2_pos, best_exchange)
                    player2_actions += distance_p2_to_exchange + 1  # aller près du comptoir + récupérer
                    
                    # P2 se positionne au comptoir d'échange après récupération
                    current_p2_pos = self.get_player_position_after_exchange(pathfinder, best_exchange)
                    
                    # COMPTABILISER 1 ÉCHANGE (dépôt + récupération = 1 échange complet)
                    exchanges_per_position[best_exchange] += 1
            
            # P2 a maintenant tous les ingrédients, va cuisiner DIRECTEMENT
            closest_pot = min(pots, key=lambda pos: pathfinder.calculate_distance(current_p2_pos, pos))
            distance_to_pot = pathfinder.calculate_distance(current_p2_pos, closest_pot)
            player2_actions += distance_to_pot + 1 + recipe.cooking_time  # aller + déposer + cuire
            current_p2_pos = closest_pot
            
            # P2 prend assiette et sert DIRECTEMENT (pas d'échange de plat cuisiné)
            closest_dish = min(dishes, key=lambda pos: pathfinder.calculate_distance(current_p2_pos, pos))
            distance_to_dish = pathfinder.calculate_distance(current_p2_pos, closest_dish)
            player2_actions += distance_to_dish + 1  # aller + ramasser assiette
            current_p2_pos = closest_dish
            
            # Retour à la casserole pour récupérer le plat cuisiné
            distance_back_to_pot = pathfinder.calculate_distance(current_p2_pos, closest_pot)
            player2_actions += distance_back_to_pot + 1  # aller + ramasser plat cuisiné
            current_p2_pos = closest_pot
            
            # Service final DIRECT
            closest_serving = min(serving_areas, key=lambda pos: pathfinder.calculate_distance(current_p2_pos, pos))
            distance_to_serving = pathfinder.calculate_distance(current_p2_pos, closest_serving)
            player2_actions += distance_to_serving + 1  # aller + servir
            current_p2_pos = closest_serving
        
        # Actions cumulées des deux joueurs
        total_cumulated_actions = player1_actions + player2_actions
        
        return total_cumulated_actions, dict(exchanges_per_position)
    
    def _evaluate_balanced_strategy(self, pathfinder: AStarPathfinder,
                                  player1_pos: Tuple[int, int], player2_pos: Tuple[int, int],
                                  recipes: List[Recipe], onion_dispensers: List[Tuple[int, int]],
                                  tomato_dispensers: List[Tuple[int, int]], pots: List[Tuple[int, int]],
                                  dishes: List[Tuple[int, int]], serving_areas: List[Tuple[int, int]],
                                  exchange_points: List[Tuple[int, int]]) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """Stratégie équilibrée avec échanges d'ingrédients optimisés"""
        
        exchanges_per_position = defaultdict(int)
        
        # Division optimale des recettes selon la géométrie
        mid_point = len(recipes) // 2
        player1_recipes = recipes[:mid_point]
        player2_recipes = recipes[mid_point:]
        
        # Calculer les actions pour chaque joueur avec échanges d'ingrédients seulement
        player1_actions = self._calculate_player_actions_optimized(
            pathfinder, player1_pos, player1_recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas,
            exchange_points, exchanges_per_position, player_id=1
        )
        
        player2_actions = self._calculate_player_actions_optimized(
            pathfinder, player2_pos, player2_recipes,
            onion_dispensers, tomato_dispensers, pots, dishes, serving_areas,
            exchange_points, exchanges_per_position, player_id=2
        )
        
        total_cumulated_actions = player1_actions + player2_actions
        
        return total_cumulated_actions, dict(exchanges_per_position)
    
    def _calculate_player_actions_optimized(self, pathfinder: AStarPathfinder, start_pos: Tuple[int, int],
                                          recipes: List[Recipe], onion_dispensers: List[Tuple[int, int]],
                                          tomato_dispensers: List[Tuple[int, int]], pots: List[Tuple[int, int]],
                                          dishes: List[Tuple[int, int]], serving_areas: List[Tuple[int, int]],
                                          exchange_points: List[Tuple[int, int]], 
                                          exchanges_per_position: Dict[Tuple[int, int], int],
                                          player_id: int) -> int:
        """
        Calcule les actions pour un joueur avec stratégie optimisée.
        RÈGLE STRICTE: Aucun échange de soupe cuisinée, seulement d'ingrédients bruts.
        """
        
        current_pos = start_pos
        total_actions = 0
        
        for recipe in recipes:
            recipe_actions = 0
            
            # Stratégie optimisée: utiliser les échanges seulement pour les ingrédients
            use_exchange = len(exchange_points) > 0 and len(recipe.ingredients) > 1
            
            if use_exchange:
                # Échange d'ingrédients UNIQUEMENT (pas de plats cuisinés)
                accessible_exchanges = [ex for ex in exchange_points 
                                      if self.can_access_wall_for_exchange(pathfinder, current_pos, ex)]
                
                if not accessible_exchanges:
                    use_exchange = False
                else:
                    closest_exchange = min(accessible_exchanges, 
                                         key=lambda pos: self.get_exchange_distance(pathfinder, current_pos, pos))
                
                    # Collecte et échange d'ingrédients optimisés
                    for ingredient in recipe.ingredients:
                        if ingredient == 'onion':
                            closest_onion = min(onion_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                            distance_to_onion = pathfinder.calculate_distance(current_pos, closest_onion)
                            recipe_actions += distance_to_onion + 1  # aller + ramasser
                            current_pos = closest_onion
                            
                            # Aller au comptoir pour DÉPOSER l'oignon (ingrédient brut uniquement)
                            distance_to_exchange = self.get_exchange_distance(pathfinder, current_pos, closest_exchange)
                            recipe_actions += distance_to_exchange + 1  # aller près du mur + déposer
                            
                            # Se positionner près du mur pour efficacité
                            wall_i, wall_j = closest_exchange
                            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                            for di, dj in directions:
                                adj_i, adj_j = wall_i + di, wall_j + dj
                                if (adj_i, adj_j) in pathfinder.valid_positions:
                                    current_pos = (adj_i, adj_j)
                                    break
                            
                            # Simuler que l'autre joueur RÉCUPÈRE l'oignon
                            # (Le coût de récupération sera compté dans l'autre joueur)
                            # COMPTABILISER 1 ÉCHANGE (dépôt + récupération = 1 échange complet)
                            exchanges_per_position[closest_exchange] += 1
                            
                        elif ingredient == 'tomato':
                            closest_tomato = min(tomato_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                            distance_to_tomato = pathfinder.calculate_distance(current_pos, closest_tomato)
                            recipe_actions += distance_to_tomato + 1  # aller + ramasser
                            current_pos = closest_tomato
                            
                            # Aller au comptoir pour DÉPOSER la tomate (ingrédient brut uniquement)
                            distance_to_exchange = self.get_exchange_distance(pathfinder, current_pos, closest_exchange)
                            recipe_actions += distance_to_exchange + 1  # aller près du mur + déposer
                            
                            # Se positionner près du mur
                            wall_i, wall_j = closest_exchange
                            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                            for di, dj in directions:
                                adj_i, adj_j = wall_i + di, wall_j + dj
                                if (adj_i, adj_j) in pathfinder.valid_positions:
                                    current_pos = (adj_i, adj_j)
                                    break
                            
                            # COMPTABILISER 1 ÉCHANGE (dépôt + récupération = 1 échange complet)
                            exchanges_per_position[closest_exchange] += 1
                    
                    # Simuler récupération des ingrédients depuis le comptoir (si c'est le joueur qui cuisine)
                    if player_id == 2:  # Le joueur 2 récupère les ingrédients déposés par le joueur 1
                        # Aller au comptoir pour récupérer tous les ingrédients
                        distance_to_exchange = self.get_exchange_distance(pathfinder, current_pos, closest_exchange)
                        recipe_actions += distance_to_exchange  # aller près du mur
                        recipe_actions += len(recipe.ingredients)  # récupérer tous les ingrédients (1 action par ingrédient)
                        
                        # Se positionner près du mur après récupération
                        wall_i, wall_j = closest_exchange
                        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                        for di, dj in directions:
                            adj_i, adj_j = wall_i + di, wall_j + dj
                            if (adj_i, adj_j) in pathfinder.valid_positions:
                                current_pos = (adj_i, adj_j)
                                break
                
            else:
                # Stratégie directe sans échange
                for ingredient in recipe.ingredients:
                    if ingredient == 'onion':
                        closest_onion = min(onion_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                        distance = pathfinder.calculate_distance(current_pos, closest_onion)
                        recipe_actions += distance + 1
                        current_pos = closest_onion
                        
                    elif ingredient == 'tomato':
                        closest_tomato = min(tomato_dispensers, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
                        distance = pathfinder.calculate_distance(current_pos, closest_tomato)
                        recipe_actions += distance + 1
                        current_pos = closest_tomato
            
            # Cuisson (aller à la casserole + déposer + attendre) - JAMAIS d'échange de plat cuisiné
            closest_pot = min(pots, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_pot)
            recipe_actions += distance + 1 + recipe.cooking_time  # aller + déposer + cuire
            current_pos = closest_pot
            
            # Service (assiette + récupération + service) - DIRECT, pas d'échange
            closest_dish = min(dishes, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_dish)
            recipe_actions += distance + 1  # aller + ramasser assiette
            current_pos = closest_dish
            
            # Retour casserole pour récupérer le plat (DIRECT, pas d'échange de plat cuisiné)
            distance = pathfinder.calculate_distance(current_pos, closest_pot)
            recipe_actions += distance + 1  # aller + ramasser plat
            current_pos = closest_pot
            
            # Service final (DIRECT, pas d'échange de plat cuisiné)
            closest_serving = min(serving_areas, key=lambda pos: pathfinder.calculate_distance(current_pos, pos))
            distance = pathfinder.calculate_distance(current_pos, closest_serving)
            recipe_actions += distance + 1  # aller + servir
            current_pos = closest_serving
            
            total_actions += recipe_actions
        
        return total_actions
    
    def evaluate_layout_with_recipes(self, layout_data: Dict, recipe_combination: Dict) -> Dict:
        """Évalue un layout avec une combinaison de recettes spécifique"""
        
        layout_id = layout_data['layout_id']
        combination_id = recipe_combination['combination_id']
        
        # Décompresser la grille
        grid = decompress_grid(layout_data['grid'])
        
        # Convertir les recettes en objets Recipe
        recipes = []
        for recipe_data in recipe_combination['recipes']:
            recipe = Recipe(
                recipe_id=recipe_data['recipe_id'],
                ingredients=recipe_data['ingredients'],
                recipe_value=recipe_data['recipe_value'],
                cooking_time=recipe_data['cooking_time']
            )
            recipes.append(recipe)
        
        # Évaluations selon vos spécifications exactes
        solo_actions = self.evaluate_solo_actions(grid, recipes)
        coop_actions, exchanges_per_position = self.evaluate_coop_actions(grid, recipes)
        
        # Format de sortie exact selon vos spécifications
        # Convertir les clés tuple en strings pour la sérialisation JSON
        exchanges_str_keys = {f"{pos[0]},{pos[1]}": count for pos, count in exchanges_per_position.items()}
        
        return {
            'layout_id': layout_id,
            'recipe_combination_id': combination_id,
            'solo_actions': solo_actions,
            'coop_actions': coop_actions,
            'exchanges_per_position': exchanges_str_keys
        }

    def run_evaluation(self):
        """Exécute l'évaluation complète avec traitement parallèle et sauvegarde par lots"""
        print("\n🚀 DÉMARRAGE DE L'ÉVALUATION D'ACTIONS POUR RECETTES (PARALLÈLE)")
        print("="*70)
        
        # Charger les données
        layouts = self.load_layouts()
        recipe_combinations = self.load_recipe_combinations()
        
        if not layouts or not recipe_combinations:
            print("❌ Données insuffisantes pour l'évaluation")
            return
        
        # Calcul du nombre de processus optimal
        cpu_count = mp.cpu_count()
        num_processes = min(cpu_count - 1, 8)  # Laisser 1 CPU libre, max 8 processus
        
        print(f"\n📊 Évaluation: {len(layouts)} layouts × {len(recipe_combinations)} combinaisons")
        print(f"📈 Total d'évaluations: {len(layouts) * len(recipe_combinations)}")
        print(f"⚙️  Processus parallèles: {num_processes}/{cpu_count} CPU")
        print(f"💾 Sauvegarde par lots de 1000 pour optimiser la mémoire")
        
        # Générer toutes les combinaisons (layout, recipe_combination)
        all_combinations = []
        for layout_data in layouts:
            for recipe_combination in recipe_combinations:
                all_combinations.append((layout_data, recipe_combination))
        
        total_evaluations = len(all_combinations)
        batch_size = 1000
        batch_number = 1
        total_saved = 0
        
        start_time = time.time()
        
        # Traitement par chunks pour éviter la surcharge mémoire
        chunk_size = max(1, total_evaluations // (num_processes * 4))  # 4 chunks par processus
        
        print(f"🔄 Traitement par chunks de {chunk_size} évaluations")
        print()
        
        with mp.Pool(processes=num_processes) as pool:
            processed_count = 0
            batch_results = []
            
            # Traiter par chunks
            for i in range(0, total_evaluations, chunk_size):
                chunk = all_combinations[i:i + chunk_size]
                
                # Traitement parallèle du chunk
                chunk_results = pool.map(evaluate_single_combination, chunk)
                batch_results.extend(chunk_results)
                processed_count += len(chunk_results)
                
                # Sauvegarder par lots de 1000
                while len(batch_results) >= batch_size:
                    batch_to_save = batch_results[:batch_size]
                    batch_results = batch_results[batch_size:]
                    
                    batch_file = f"{self.output_file.replace('.ndjson', f'_batch_{batch_number:04d}.ndjson')}"
                    print(f"� Sauvegarde lot {batch_number}: {len(batch_to_save)} résultats → {batch_file}")
                    write_ndjson(batch_to_save, batch_file)
                    total_saved += len(batch_to_save)
                    batch_number += 1
                
                # Progression
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                progress_pct = (processed_count / total_evaluations) * 100
                print(f"📊 Progression: {processed_count}/{total_evaluations} ({progress_pct:.1f}%) - {rate:.1f} éval/s - {total_saved} sauvegardés")
        
        # Sauvegarder le dernier lot s'il reste des résultats
        if batch_results:
            batch_file = f"{self.output_file.replace('.ndjson', f'_batch_{batch_number:04d}.ndjson')}"
            print(f"💾 Sauvegarde lot final {batch_number}: {len(batch_results)} résultats → {batch_file}")
            write_ndjson(batch_results, batch_file)
            total_saved += len(batch_results)
        
        elapsed_total = time.time() - start_time
        print(f"\n✅ ÉVALUATION PARALLÈLE TERMINÉE!")
        print(f"📊 {total_saved} évaluations sauvegardées en {batch_number} lots")
        print(f"⏱️ Temps total: {elapsed_total:.2f}s")
        print(f"📈 Performance moyenne: {total_saved/elapsed_total:.1f} éval/s")
        print(f"🚀 Accélération: ~{num_processes}x avec {num_processes} processus")
        print(f"📁 Fichiers de sortie: {self.output_file.replace('.ndjson', '_batch_*.ndjson')}")


def evaluate_single_combination(args_tuple):
    """
    Fonction worker pour évaluation parallèle d'une combinaison layout+recette.
    Prend un tuple (layout_data, recipe_combination) et retourne le résultat.
    """
    layout_data, recipe_combination = args_tuple
    
    try:
        # Créer une instance temporaire de l'évaluateur pour ce worker
        evaluator = RecipeActionEvaluator()
        result = evaluator.evaluate_layout_with_recipes(layout_data, recipe_combination)
        return result
    
    except Exception as e:
        layout_id = layout_data.get('layout_id', 'unknown')
        combination_id = recipe_combination.get('combination_id', 'unknown')
        print(f"❌ Erreur worker {layout_id} + combinaison {combination_id}: {e}")
        
        # Retourner un résultat d'erreur
        return {
            'layout_id': layout_id,
            'recipe_combination_id': combination_id,
            'solo_actions': float('inf'),
            'coop_actions': float('inf'),
            'exchanges_per_position': {}
        }
    
    def run_evaluation(self):
        """Exécute l'évaluation complète avec traitement parallèle et sauvegarde par lots"""
        print("\n🚀 DÉMARRAGE DE L'ÉVALUATION D'ACTIONS POUR RECETTES (PARALLÈLE)")
        print("="*70)
        
        # Charger les données
        layouts = self.load_layouts()
        recipe_combinations = self.load_recipe_combinations()
        
        if not layouts or not recipe_combinations:
            print("❌ Données insuffisantes pour l'évaluation")
            return
        
        # Calcul du nombre de processus optimal
        cpu_count = mp.cpu_count()
        num_processes = min(cpu_count - 1, 8)  # Laisser 1 CPU libre, max 8 processus
        
        print(f"\n📊 Évaluation: {len(layouts)} layouts × {len(recipe_combinations)} combinaisons")
        print(f"📈 Total d'évaluations: {len(layouts) * len(recipe_combinations)}")
        print(f"�️  Processus parallèles: {num_processes}/{cpu_count} CPU")
        print(f"�💾 Sauvegarde par lots de 1000 pour optimiser la mémoire")
        
        # Générer toutes les combinaisons (layout, recipe_combination)
        all_combinations = []
        for layout_data in layouts:
            for recipe_combination in recipe_combinations:
                all_combinations.append((layout_data, recipe_combination))
        
        total_evaluations = len(all_combinations)
        batch_size = 1000
        batch_number = 1
        total_saved = 0
        
        start_time = time.time()
        
        # Traitement par chunks pour éviter la surcharge mémoire
        chunk_size = max(1, total_evaluations // (num_processes * 4))  # 4 chunks par processus
        
        print(f"🔄 Traitement par chunks de {chunk_size} évaluations")
        print()
        
        with mp.Pool(processes=num_processes) as pool:
            processed_count = 0
            batch_results = []
            
            # Traiter par chunks
            for i in range(0, total_evaluations, chunk_size):
                chunk = all_combinations[i:i + chunk_size]
                
                # Traitement parallèle du chunk
                chunk_results = pool.map(evaluate_single_combination, chunk)
                batch_results.extend(chunk_results)
                processed_count += len(chunk_results)
                
                # Sauvegarder par lots de 1000
                while len(batch_results) >= batch_size:
                    batch_to_save = batch_results[:batch_size]
                    batch_results = batch_results[batch_size:]
                    
                    batch_file = f"{self.output_file.replace('.ndjson', f'_batch_{batch_number:04d}.ndjson')}"
                    print(f"💾 Sauvegarde lot {batch_number}: {len(batch_to_save)} résultats → {batch_file}")
                    write_ndjson(batch_to_save, batch_file)
                    total_saved += len(batch_to_save)
                    batch_number += 1
                
                # Progression
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                progress_pct = (processed_count / total_evaluations) * 100
                print(f"📊 Progression: {processed_count}/{total_evaluations} ({progress_pct:.1f}%) - {rate:.1f} éval/s - {total_saved} sauvegardés")
        
        # Sauvegarder le dernier lot s'il reste des résultats
        if batch_results:
            batch_file = f"{self.output_file.replace('.ndjson', f'_batch_{batch_number:04d}.ndjson')}"
            print(f"💾 Sauvegarde lot final {batch_number}: {len(batch_results)} résultats → {batch_file}")
            write_ndjson(batch_results, batch_file)
            total_saved += len(batch_results)
        
        elapsed_total = time.time() - start_time
        print(f"\n✅ ÉVALUATION PARALLÈLE TERMINÉE!")
        print(f"📊 {total_saved} évaluations sauvegardées en {batch_number} lots")
        print(f"⏱️ Temps total: {elapsed_total:.2f}s")
        print(f"📈 Performance moyenne: {total_saved/elapsed_total:.1f} éval/s")
        print(f"🚀 Accélération: ~{num_processes}x avec {num_processes} processus")
        print(f"📁 Fichiers de sortie: {self.output_file.replace('.ndjson', '_batch_*.ndjson')}")


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Évaluateur d'actions pour recettes Overcooked")
    parser.add_argument('--layouts', default='layouts_with_objects.ndjson',
                       help='Fichier NDJSON des layouts (défaut: layouts_with_objects.ndjson)')
    parser.add_argument('--recipes', default='ensemble_recettes.json',
                       help='Fichier JSON des recettes (défaut: ensemble_recettes.json)')
    parser.add_argument('--output', default='recipe_evaluation_results.ndjson',
                       help='Fichier NDJSON de sortie (défaut: recipe_evaluation_results.ndjson)')
    parser.add_argument('--processes', type=int, default=None,
                       help='Nombre de processus parallèles (défaut: auto)')
    
    args = parser.parse_args()
    
    print("🍽️ ÉVALUATEUR D'ACTIONS POUR RECETTES - OVERCOOKED (PARALLÈLE)")
    print("Évaluation scientifique des stratégies solo vs coopératives")
    print("Spécialement conçu pour la recherche en sciences cognitives")
    print()
    
    # Créer et configurer l'évaluateur
    evaluator = RecipeActionEvaluator()
    
    # Convertir les chemins en absolus pour éviter les erreurs d'adressage
    evaluator.layouts_file = os.path.abspath(args.layouts)
    evaluator.recipes_file = os.path.abspath(args.recipes)
    evaluator.output_file = os.path.abspath(args.output)
    
    # Vérifier que les fichiers d'entrée existent
    if not os.path.exists(evaluator.layouts_file):
        print(f"❌ Erreur: Fichier layouts non trouvé: {evaluator.layouts_file}")
        return 1
        
    if not os.path.exists(evaluator.recipes_file):
        print(f"❌ Erreur: Fichier recettes non trouvé: {evaluator.recipes_file}")
        return 1
    
    # Exécuter l'évaluation parallèle
    evaluator.run_evaluation()


if __name__ == "__main__":
    main()
