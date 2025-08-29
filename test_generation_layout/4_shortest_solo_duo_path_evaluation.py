#!/usr/bin/env python3
"""
Script d'évaluation des distances optimales en solo et coopération
pour l'environnement Overcooked GridWorld

Auteur: Agent IA (modifié)
Date: Août 2025
Modifs: ajout de l'état des comptoirs et des actions deposit/pickup réelles
"""

import json
import os
import heapq
import re
from collections import deque
import concurrent.futures
import multiprocessing
import time
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass


@dataclass
class Position:
    """Représente une position (x, y) dans la grille"""
    x: int
    y: int
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y
        return False
    
    def __repr__(self):
        return f"({self.x}, {self.y})"
    
    def manhattan_distance(self, other: 'Position') -> int:
        """Calcule la distance de Manhattan entre deux positions"""
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def get_adjacent_positions(self) -> List['Position']:
        """Retourne les positions adjacentes (haut, bas, gauche, droite)"""
        return [
            Position(self.x, self.y - 1),  # Haut
            Position(self.x, self.y + 1),  # Bas
            Position(self.x - 1, self.y),  # Gauche
            Position(self.x + 1, self.y)   # Droite
        ]


@dataclass
class GameState:
    """État du jeu incluant positions des joueurs et objets portés (non utilisé partout, mais conservé)"""
    player1_pos: Position
    player2_pos: Optional[Position]
    player1_holding: Optional[str]  # None, 'ingredient', 'dish', 'plate'
    player2_holding: Optional[str]
    pot_contents: List[str]  # Liste des ingrédients dans le pot
    pot_cooked: bool  # Si le pot contient un plat cuisiné
    completed_recipes: int  # Nombre de recettes terminées
    
    def __hash__(self):
        p2_pos = (self.player2_pos.x, self.player2_pos.y) if self.player2_pos else None
        return hash((
            (self.player1_pos.x, self.player1_pos.y),
            p2_pos,
            self.player1_holding,
            self.player2_holding,
            tuple(sorted(self.pot_contents)),
            self.pot_cooked,
            self.completed_recipes
        ))


class GridWorld:
    """Représente l'environnement de jeu Overcooked"""
    
    def __init__(self, grid_str: str):
        self.grid = self._parse_grid(grid_str)
        self.height = len(self.grid)
        self.width = len(self.grid[0]) if self.height > 0 else 0
        self.positions = self._find_special_positions()
    
    def _parse_grid(self, grid_str: str) -> List[List[str]]:
        """Parse la grille à partir d'une chaîne multi-lignes"""
        lines = [line.strip() for line in grid_str.strip().split('\n')]
        return [list(line) for line in lines]
    
    def _find_special_positions(self) -> Dict[str, List[Position]]:
        """Trouve toutes les positions spéciales dans la grille"""
        positions = {
            'onion': [], 'tomato': [], 'dish': [], 'pot': [], 'service': [],
            'player1': [], 'player2': [], 'empty': [], 'counter': []
        }
        
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                pos = Position(x, y)
                if cell == 'O':
                    positions['onion'].append(pos)
                elif cell == 'T':
                    positions['tomato'].append(pos)
                elif cell == 'D':
                    positions['dish'].append(pos)
                elif cell == 'P':
                    positions['pot'].append(pos)
                elif cell == 'S':
                    positions['service'].append(pos)
                elif cell == '1':
                    positions['player1'].append(pos)
                elif cell == '2':
                    positions['player2'].append(pos)
                elif cell == ' ':
                    positions['empty'].append(pos)
                elif cell == 'X':
                    positions['counter'].append(pos)
        
        return positions
    
    def is_valid_position(self, pos: Position) -> bool:
        """Vérifie si une position est valide et accessible"""
        if not (0 <= pos.x < self.width and 0 <= pos.y < self.height):
            return False
        
        cell = self.grid[pos.y][pos.x]
        # Dans notre cas, les 'X' représentent des comptoirs accessibles
        # On bloque seulement les vrais murs (si ils existent avec un autre symbole)
        return True  # Toutes les positions dans la grille sont accessibles
    
    def is_counter_position(self, pos: Position) -> bool:
        """Vérifie si une position est un comptoir (X)"""
        if not (0 <= pos.x < self.width and 0 <= pos.y < self.height):
            return False
        return self.grid[pos.y][pos.x] == 'X'
    
    def can_pass_through_wall(self, pos1: Position, pos2: Position) -> bool:
        """Vérifie si deux joueurs peuvent échanger à travers un mur de largeur 1"""
        if pos1.manhattan_distance(pos2) != 2:
            return False
        
        # Positions intermédiaires
        if pos1.x == pos2.x:  # Vertical
            mid_y = (pos1.y + pos2.y) // 2
            mid_pos = Position(pos1.x, mid_y)
        elif pos1.y == pos2.y:  # Horizontal
            mid_x = (pos1.x + pos2.x) // 2
            mid_pos = Position(mid_x, pos1.y)
        else:
            return False
        
        # Vérifier que la position intermédiaire est un mur
        if (0 <= mid_pos.x < self.width and 0 <= mid_pos.y < self.height):
            return self.grid[mid_pos.y][mid_pos.x] == 'X'
        
        return False
    
    def get_shortest_path(self, start: Position, end: Position) -> Tuple[List[Position], int]:
        """Calcule le plus court chemin entre deux positions avec BFS (ignore obstacles dynamiques)"""
        if start == end:
            return [start], 0
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current_pos, path = queue.popleft()
            
            for next_pos in current_pos.get_adjacent_positions():
                if next_pos == end:
                    final_path = path + [next_pos]
                    return final_path, len(final_path) - 1
                
                if next_pos not in visited and self._is_accessible(next_pos):
                    visited.add(next_pos)
                    queue.append((next_pos, path + [next_pos]))
        
        return [], float('inf')  # Pas de chemin trouvé
    
    def _is_accessible(self, pos: Position) -> bool:
        """Vérifie si une position est accessible (comptoirs compris)"""
        if not (0 <= pos.x < self.width and 0 <= pos.y < self.height):
            return False
        
        cell = self.grid[pos.y][pos.x]
        # Toutes les positions sont accessibles sauf les murs de type obstacle
        # Les comptoirs 'X' sont accessibles pour le pathfinding
        return True  # Permettre l'accès à toutes les positions dans la grille valide


class RecipeExecutor:
    """Gestionnaire d'exécution des recettes en solo et coopération"""
    
    def __init__(self, grid_world: GridWorld, recipes: List[Dict], gain_threshold: int = 1):
        self.grid = grid_world
        self.recipes = recipes
        self.debug = False  # Désactiver le debug par défaut pour la performance
        # Initialiser l'état des comptoirs : chaque Position -> None (vide) ou string=item
        self.counters: Dict[Position, Optional[str]] = {pos: None for pos in self.grid.positions.get('counter', [])}
        # seuil de gain pour utiliser un comptoir (configurable)
        self.gain_threshold = gain_threshold
    
    # ---------------------------
    # Actions de comptoir (stateful)
    # ---------------------------
    def deposit(self, player_id: int, counter_pos: Position, item: str, debug_steps: List[str]) -> None:
        """Déposer un item sur un comptoir. Met à jour self.counters et écrit dans debug"""
        if item is None:
            raise ValueError("deposit(): pas d'objet à déposer")
        if counter_pos not in self.counters:
            raise ValueError(f"deposit(): position {counter_pos} n'est pas un comptoir connu")
        if self.counters[counter_pos] is not None:
            raise ValueError(f"deposit(): comptoir {counter_pos} déjà occupé par {self.counters[counter_pos]}")
        # Effectuer le dépôt
        self.counters[counter_pos] = item
        if self.debug:
            debug_steps.append(f"    t: J{player_id} dépose '{item}' sur le comptoir {counter_pos}")
    
    def pickup(self, player_id: int, counter_pos: Position, debug_steps: List[str]) -> str:
        """Prendre l'item d'un comptoir. Met à jour self.counters et écrit dans debug"""
        if counter_pos not in self.counters:
            raise ValueError(f"pickup(): position {counter_pos} n'est pas un comptoir connu")
        item = self.counters[counter_pos]
        if item is None:
            raise ValueError(f"pickup(): comptoir {counter_pos} vide")
        self.counters[counter_pos] = None
        if self.debug:
            debug_steps.append(f"    t: J{player_id} prend '{item}' sur le comptoir {counter_pos}")
        return item
    
    def is_counter_free(self, counter_pos: Position) -> bool:
        """Vérifie si un comptoir est libre (vide)"""
        return counter_pos in self.counters and self.counters[counter_pos] is None
    
    def record_movement(self, player_id: int, path: List[Position], action: str, item: str = None) -> Dict:
        """Enregistre un mouvement avec format ultra-compact"""
        if not path:
            return {}
        
        start_pos = path[0]
        end_pos = path[-1]
        distance = len(path) - 1 if len(path) > 1 else 0
        
        # Format ultra-compact avec seulement les données essentielles
        return {
            'joueur': player_id,
            'depart': f"{start_pos.x},{start_pos.y}",
            'arrivee': f"{end_pos.x},{end_pos.y}",
            'action': action,
            'objet': item,
            'distance': distance
        }

    # ---------------------------
    # Calcul solo
    # ---------------------------
    def calculate_solo_distance(self) -> Tuple[int, List[str], List[Dict]]:
        """Calcule la distance totale en mode solo avec contrainte d'un objet à la fois"""
        if not self.grid.positions['player1']:
            return float('inf'), ["Erreur: Pas de position joueur 1"], []
        
        player_pos = self.grid.positions['player1'][0]
        total_distance = 0
        debug_log = ["=== MODE SOLO ==="]
        detailed_movements = []
        player_holding = None  # Suivi de ce que porte le joueur
        
        for recipe_idx, recipe in enumerate(self.recipes):
            ingredients = recipe['ingredients']
            debug_log.append(f"\nRecette {recipe_idx + 1}: {ingredients}")
            
            # 1. Collecter tous les ingrédients et les mettre dans le pot (UN PAR UN)
            for ingredient in ingredients:
                # Vérifier que le joueur n'a rien dans les mains
                if player_holding is not None:
                    debug_log.append(f"Erreur: Joueur porte déjà {player_holding}")
                    return float('inf'), debug_log, detailed_movements
                
                # Trouver l'ingrédient le plus proche
                ingredient_positions = self.grid.positions['onion'] if ingredient == 'onion' else self.grid.positions['tomato']
                
                if not ingredient_positions:
                    debug_log.append(f"Erreur: Aucun {ingredient} disponible")
                    return float('inf'), debug_log, detailed_movements
                
                closest_ingredient = min(ingredient_positions, 
                                       key=lambda pos: player_pos.manhattan_distance(pos))
                
                # Aller chercher l'ingrédient
                path_to_ingredient, dist_to_ingredient = self.grid.get_shortest_path(player_pos, closest_ingredient)
                debug_log.append(f"  Aller chercher {ingredient} en {closest_ingredient}: {dist_to_ingredient} cases")
                detailed_movements.append(self.record_movement(1, path_to_ingredient, f"collect_{ingredient}", ingredient))
                total_distance += dist_to_ingredient
                player_pos = closest_ingredient
                player_holding = ingredient  # Le joueur prend l'ingrédient
                
                # Aller au pot et déposer l'ingrédient
                pot_pos = self.grid.positions['pot'][0]
                path_to_pot, dist_to_pot = self.grid.get_shortest_path(player_pos, pot_pos)
                debug_log.append(f"  Apporter {ingredient} au pot {pot_pos}: {dist_to_pot} cases")
                detailed_movements.append(self.record_movement(1, path_to_pot, f"deliver_{ingredient}", ingredient))
                total_distance += dist_to_pot
                player_pos = pot_pos
                player_holding = None  # Le joueur dépose l'ingrédient
            
            # 2. Prendre une assiette (vérifier que les mains sont libres)
            if player_holding is not None:
                debug_log.append(f"Erreur: Joueur porte encore {player_holding}")
                return float('inf'), debug_log, detailed_movements
            
            dish_pos = self.grid.positions['dish'][0]
            path_to_dish, dist_to_dish = self.grid.get_shortest_path(player_pos, dish_pos)
            debug_log.append(f"  Aller chercher l'assiette en {dish_pos}: {dist_to_dish} cases")
            detailed_movements.append(self.record_movement(1, path_to_dish, "collect_plate", "plate"))
            total_distance += dist_to_dish
            player_pos = dish_pos
            player_holding = 'plate'  # Le joueur prend l'assiette
            
            # 3. Retourner au pot pour prendre le plat cuisiné
            path_back_to_pot, dist_back_to_pot = self.grid.get_shortest_path(player_pos, pot_pos)
            debug_log.append(f"  Retourner au pot pour le plat: {dist_back_to_pot} cases")
            detailed_movements.append(self.record_movement(1, path_back_to_pot, "collect_cooked_dish", "cooked_dish"))
            total_distance += dist_back_to_pot
            player_pos = pot_pos
            player_holding = 'cooked_dish'  # Le joueur échange l'assiette contre le plat cuisiné
            
            # 4. Aller au service
            service_pos = self.grid.positions['service'][0]
            path_to_service, dist_to_service = self.grid.get_shortest_path(player_pos, service_pos)
            debug_log.append(f"  Livrer le plat au service {service_pos}: {dist_to_service} cases")
            detailed_movements.append(self.record_movement(1, path_to_service, "deliver_dish", "cooked_dish"))
            total_distance += dist_to_service
            player_pos = service_pos
            player_holding = None  # Le joueur livre le plat
            
            debug_log.append(f"  Distance pour recette {recipe_idx + 1}: {dist_to_ingredient + dist_to_pot + dist_to_dish + dist_back_to_pot + dist_to_service}")
        
        debug_log.append(f"\nDistance totale SOLO: {total_distance}")
        return total_distance, debug_log, detailed_movements
    
    # ---------------------------
    # Calcul coop (modifié pour déposer / récupérer réellement)
    # ---------------------------
    def calculate_coop_distance(self) -> Tuple[int, List[str], List[Dict]]:
        """Calcule la distance totale en mode coopération optimisée avec échanges via comptoirs"""
        if not self.grid.positions['player1'] or not self.grid.positions['player2']:
            return float('inf'), ["Erreur: Positions joueurs manquantes pour le mode coop"], []
        
        player1_pos = self.grid.positions['player1'][0]
        player2_pos = self.grid.positions['player2'][0]
        total_distance = 0
        debug_log = ["=== MODE COOPÉRATION AVEC ÉCHANGES COMPTOIRS ==="]
        detailed_movements = []
        
        # Ré-initialiser l'état des comptoirs pour chaque calcul coop (stateless per-run)
        self.counters = {pos: None for pos in self.grid.positions.get('counter', [])}
        
        for recipe_idx, recipe in enumerate(self.recipes):
            ingredients = recipe['ingredients']
            debug_log.append(f"\nRecette {recipe_idx + 1}: {ingredients}")
            
            # Stratégie coopérative optimisée avec échanges via comptoirs
            recipe_distance, recipe_movements = self._execute_coop_recipe_with_counters(
                player1_pos, player2_pos, ingredients, debug_log
            )
            total_distance += recipe_distance
            detailed_movements.extend(recipe_movements)
            
            # Après chaque recette, positionner les joueurs au service
            service_pos = self.grid.positions['service'][0]
            player1_pos = service_pos
            player2_pos = service_pos
        
        debug_log.append(f"\nDistance totale COOP: {total_distance}")
        return total_distance, debug_log, detailed_movements
    
    def _execute_coop_recipe_with_counters(self, player1_start: Position, player2_start: Position, 
                                         ingredients: List[str], debug_log: List[str]) -> Tuple[int, List[Dict]]:
        """Exécute une recette en mode coopération optimisée avec échanges via comptoirs"""
        
        # Positions importantes
        pot_pos = self.grid.positions['pot'][0]
        dish_pos = self.grid.positions['dish'][0]
        service_pos = self.grid.positions['service'][0]
        onion_positions = self.grid.positions['onion']
        tomato_positions = self.grid.positions['tomato']
        counter_positions = self.grid.positions['counter']
        
        player1_pos = player1_start
        player2_pos = player2_start
        
        # Évaluer différentes stratégies optimisées et choisir la meilleure
        strategies = [
            self._strategy_counter_exchange(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions, counter_positions),
            self._strategy_parallel_with_counters(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions, counter_positions),
            self._strategy_traditional(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions)
        ]
        
        # Choisir la stratégie avec la distance minimale
        best_strategy = min(strategies, key=lambda s: s['total_distance'])
        
        # Ajouter les détails au debug log
        debug_log.extend(best_strategy['debug_steps'])
        debug_log.append(f"  Stratégie choisie: {best_strategy['name']}")
        debug_log.append(f"  Distance totale: {best_strategy['total_distance']}")
        
        # Retourner distance et mouvements détaillés
        movements = best_strategy.get('movements', [])
        return best_strategy['total_distance'], movements
    
    def _strategy_counter_exchange(self, player1_pos: Position, player2_pos: Position, 
                                 ingredients: List[str], pot_pos: Position, dish_pos: Position, 
                                 service_pos: Position, onion_positions: List[Position], 
                                 tomato_positions: List[Position], counter_positions: List[Position]) -> Dict:
        """Stratégie optimisée avec échanges via comptoirs (X)
           -> utilise deposit/pickup pour modéliser réellement l'échange
        """
        
        debug_steps = ["  [STRATÉGIE ÉCHANGE COMPTOIRS OPTIMISÉE]"] if self.debug else []
        
        # Debug : état des comptoirs (seulement si debug activé)
        available_counters = [pos for pos in counter_positions if self.is_counter_free(pos)]
        if self.debug:
            debug_steps.append(f"    État comptoirs: {len(available_counters)}/{len(counter_positions)} libres")
            for pos in counter_positions:
                status = "LIBRE" if self.is_counter_free(pos) else f"OCCUPÉ({self.counters[pos]})"
                debug_steps.append(f"      - Comptoir {pos}: {status}")
        
        player1_distance = 0
        player2_distance = 0
        p1_pos = player1_pos
        p2_pos = player2_pos
        p1_holding = None
        p2_holding = None
        
        # Phase 1: J2 va chercher l'assiette en premier (optimisation)
        _, dist_j2_to_dish = self.grid.get_shortest_path(p2_pos, dish_pos)
        player2_distance += dist_j2_to_dish
        p2_pos = dish_pos
        p2_holding = 'plate'
        debug_steps.append(f"    J2: aller chercher l'assiette en {dish_pos}: {dist_j2_to_dish} cases")
        
        # Phase 2: Traiter chaque ingrédient avec stratégie optimale
        for ingredient_idx, ingredient in enumerate(ingredients):
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            
            debug_steps.append(f"    --- Traitement ingrédient {ingredient_idx + 1}: {ingredient} ---")
            
            # Analyser les options pour cet ingrédient
            best_strategy = self._find_best_counter_exchange(
                p1_pos, p2_pos, ingredient_positions, pot_pos, counter_positions
            )
            
            if best_strategy['use_counter']:
                # Utiliser l'échange via comptoir
                counter_pos = best_strategy['counter_pos']
                ingredient_pos = best_strategy['ingredient_pos']
                collector_player = best_strategy['collector_player']
                transporter_player = best_strategy['transporter_player']
                
                debug_steps.append(f"    → Stratégie comptoir sélectionnée (gain: {best_strategy.get('gain', 0)} cases) via {counter_pos}")
                debug_steps.append(f"    → J{collector_player} collecte, J{transporter_player} transporte via {counter_pos}")
                
                if collector_player == 1:
                    # J1 collecte l'ingrédient et le dépose au comptoir
                    _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
                    player1_distance += dist_j1_to_ingredient
                    p1_pos = ingredient_pos
                    p1_holding = ingredient
                    debug_steps.append(f"    J1: aller chercher {ingredient} en {ingredient_pos}: {dist_j1_to_ingredient} cases")
                    
                    _, dist_j1_to_counter = self.grid.get_shortest_path(p1_pos, counter_pos)
                    player1_distance += dist_j1_to_counter
                    p1_pos = counter_pos
                    # dépôt réel
                    try:
                        self.deposit(1, counter_pos, p1_holding, debug_steps)
                    except Exception as e:
                        debug_steps.append(f"    ERREUR dépôt J1 -> {e}")
                    p1_holding = None
                    debug_steps.append(f"    (J1 mains libres après dépôt)")
                    
                    # J2 doit gérer l'assiette et récupérer l'ingrédient
                    if p2_holding == 'plate':
                        # Poser temporairement l'assiette au pot (simplification)
                        safe_spot = pot_pos
                        _, dist_j2_to_safe = self.grid.get_shortest_path(p2_pos, safe_spot)
                        player2_distance += dist_j2_to_safe
                        p2_pos = safe_spot
                        p2_holding = None
                        debug_steps.append(f"    J2: poser temporairement l'assiette en {safe_spot}: {dist_j2_to_safe} cases")
                    
                    # J2 va au comptoir récupérer l'ingrédient (pickup réel)
                    _, dist_j2_to_counter = self.grid.get_shortest_path(p2_pos, counter_pos)
                    player2_distance += dist_j2_to_counter
                    p2_pos = counter_pos
                    try:
                        p2_holding = self.pickup(2, counter_pos, debug_steps)
                    except Exception as e:
                        debug_steps.append(f"    ERREUR pickup J2 -> {e}")
                        p2_holding = None
                    debug_steps.append(f"    J2 a maintenant: {p2_holding}")
                    
                    # J2 apporte l'ingrédient au pot
                    _, dist_j2_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
                    player2_distance += dist_j2_to_pot
                    p2_pos = pot_pos
                    p2_holding = None
                    debug_steps.append(f"    J2: apporter {ingredient} au pot {pot_pos}: {dist_j2_to_pot} cases")
                    
                    # J2 reprend l'assiette si elle était au pot
                    if safe_spot == pot_pos:
                        p2_holding = 'plate'
                        debug_steps.append(f"    J2: reprendre l'assiette au pot {pot_pos}")
                
                else:  # collector_player == 2
                    # J2 collecte et dépose au comptoir
                    if p2_holding == 'plate':
                        safe_spot = pot_pos
                        _, dist_j2_to_safe = self.grid.get_shortest_path(p2_pos, safe_spot)
                        player2_distance += dist_j2_to_safe
                        p2_pos = safe_spot
                        p2_holding = None
                        debug_steps.append(f"    J2: poser temporairement l'assiette en {safe_spot}: {dist_j2_to_safe} cases")
                    
                    # J2 va chercher l'ingrédient
                    _, dist_j2_to_ingredient = self.grid.get_shortest_path(p2_pos, ingredient_pos)
                    player2_distance += dist_j2_to_ingredient
                    p2_pos = ingredient_pos
                    p2_holding = ingredient
                    debug_steps.append(f"    J2: aller chercher {ingredient} en {ingredient_pos}: {dist_j2_to_ingredient} cases")
                    
                    # J2 va déposer au comptoir
                    _, dist_j2_to_counter = self.grid.get_shortest_path(p2_pos, counter_pos)
                    player2_distance += dist_j2_to_counter
                    p2_pos = counter_pos
                    try:
                        self.deposit(2, counter_pos, p2_holding, debug_steps)
                    except Exception as e:
                        debug_steps.append(f"    ERREUR dépôt J2 -> {e}")
                    p2_holding = None
                    debug_steps.append(f"    (J2 mains libres après dépôt)")
                    
                    # J1 va chercher l'ingrédient au comptoir (pickup réel)
                    _, dist_j1_to_counter = self.grid.get_shortest_path(p1_pos, counter_pos)
                    player1_distance += dist_j1_to_counter
                    p1_pos = counter_pos
                    try:
                        p1_holding = self.pickup(1, counter_pos, debug_steps)
                    except Exception as e:
                        debug_steps.append(f"    ERREUR pickup J1 -> {e}")
                        p1_holding = None
                    debug_steps.append(f"    J1 a maintenant: {p1_holding}")
                    
                    # J1 transporte au pot
                    _, dist_j1_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
                    player1_distance += dist_j1_to_pot
                    p1_pos = pot_pos
                    p1_holding = None
                    debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos}: {dist_j1_to_pot} cases")
                    
                    # J2 retourne récupérer l'assiette
                    _, dist_j2_back_to_safe = self.grid.get_shortest_path(p2_pos, safe_spot)
                    player2_distance += dist_j2_back_to_safe
                    p2_pos = safe_spot
                    p2_holding = 'plate'
                    debug_steps.append(f"    J2: retourner prendre l'assiette en {safe_spot}: {dist_j2_back_to_safe} cases")
            
            else:
                # Stratégie directe: le joueur optimal fait tout
                ingredient_pos = best_strategy['ingredient_pos']
                optimal_player = best_strategy.get('player', 1)
                
                debug_steps.append(f"    → Stratégie directe sélectionnée (J{optimal_player})")
                
                if optimal_player == 1:
                    # J1 fait tout
                    _, dist_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
                    player1_distance += dist_to_ingredient
                    p1_pos = ingredient_pos
                    p1_holding = ingredient
                    debug_steps.append(f"    J1: chercher {ingredient} en {ingredient_pos}: {dist_to_ingredient} cases")
                    
                    _, dist_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
                    player1_distance += dist_to_pot
                    p1_pos = pot_pos
                    p1_holding = None
                    debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos}: {dist_to_pot} cases")
                
                else:  # optimal_player == 2
                    # J2 doit gérer l'assiette
                    if p2_holding == 'plate':
                        safe_spot = pot_pos
                        _, dist_j2_to_safe = self.grid.get_shortest_path(p2_pos, safe_spot)
                        player2_distance += dist_j2_to_safe
                        p2_pos = safe_spot
                        p2_holding = None
                        debug_steps.append(f"    J2: poser temporairement l'assiette en {safe_spot}: {dist_j2_to_safe} cases")
                    
                    # J2 fait tout
                    _, dist_to_ingredient = self.grid.get_shortest_path(p2_pos, ingredient_pos)
                    player2_distance += dist_to_ingredient
                    p2_pos = ingredient_pos
                    p2_holding = ingredient
                    debug_steps.append(f"    J2: chercher {ingredient} en {ingredient_pos}: {dist_to_ingredient} cases")
                    
                    _, dist_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
                    player2_distance += dist_to_pot
                    p2_pos = pot_pos
                    p2_holding = None
                    debug_steps.append(f"    J2: apporter {ingredient} au pot {pot_pos}: {dist_to_pot} cases")
                    
                    # J2 reprend l'assiette
                    p2_holding = 'plate'
                    debug_steps.append(f"    J2: reprendre l'assiette au pot {pot_pos}")
        
        # Phase 3: J2 finalise avec le plat cuisiné
        if p2_holding != 'plate':
            # J2 doit récupérer l'assiette
            _, dist_j2_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
            player2_distance += dist_j2_to_pot
            p2_pos = pot_pos
            p2_holding = 'plate'
            debug_steps.append(f"    J2: aller récupérer l'assiette au pot {pot_pos}: {dist_j2_to_pot} cases")
        
        # J2 échange l'assiette contre le plat cuisiné
        if p2_pos != pot_pos:
            _, dist_j2_to_pot_final = self.grid.get_shortest_path(p2_pos, pot_pos)
            player2_distance += dist_j2_to_pot_final
            p2_pos = pot_pos
            debug_steps.append(f"    J2: aller au pot pour le plat {pot_pos}: {dist_j2_to_pot_final} cases")
        
        p2_holding = 'cooked_dish'
        debug_steps.append(f"    J2: échanger assiette contre plat cuisiné au pot {pot_pos}")
        
        # J2 livre le plat
        _, dist_j2_to_service = self.grid.get_shortest_path(p2_pos, service_pos)
        player2_distance += dist_j2_to_service
        p2_holding = None
        debug_steps.append(f"    J2: livrer le plat au service {service_pos}: {dist_j2_to_service} cases")
        
        total_distance = max(player1_distance, player2_distance)
        debug_steps.append(f"    Total: J1={player1_distance}, J2={player2_distance}, Max={total_distance}")
        
        return {
            'name': 'Échange Comptoirs Optimisé',
            'total_distance': total_distance,
            'debug_steps': debug_steps
        }
    
    def _strategy_parallel_with_counters(self, player1_pos: Position, player2_pos: Position, 
                                       ingredients: List[str], pot_pos: Position, dish_pos: Position, 
                                       service_pos: Position, onion_positions: List[Position], 
                                       tomato_positions: List[Position], counter_positions: List[Position]) -> Dict:
        """Stratégie parallèle optimisée avec usage intelligent des comptoirs (utilise les méthodes deposit/pickup)"""
        
        debug_steps = ["  [STRATÉGIE PARALLÈLE AVEC COMPTOIRS]"]
        
        # Si un seul ingrédient, utiliser la stratégie comptoir
        if len(ingredients) == 1:
            return self._strategy_counter_exchange(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions, counter_positions)
        
        # Pour plusieurs ingrédients, optimiser la répartition
        player1_distance = 0
        player2_distance = 0
        p1_pos = player1_pos
        p2_pos = player2_pos
        p1_holding = None
        p2_holding = None
        
        # J2 va chercher l'assiette en premier
        _, dist_j2_to_dish = self.grid.get_shortest_path(p2_pos, dish_pos)
        player2_distance += dist_j2_to_dish
        p2_pos = dish_pos
        p2_holding = 'plate'
        debug_steps.append(f"    J2: aller en {dish_pos} chercher l'assiette et la prendre: {dist_j2_to_dish} cases")
        
        # Répartir les ingrédients entre les joueurs
        mid_point = len(ingredients) // 2
        j1_ingredients = ingredients[:mid_point] if mid_point > 0 else []
        j2_ingredients = ingredients[mid_point:]
        
        # J1 s'occupe de ses ingrédients
        for ingredient in j1_ingredients:
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p1_pos.manhattan_distance(pos))
            
            _, dist_to_ingredient = self.grid.get_shortest_path(p1_pos, closest_ingredient)
            player1_distance += dist_to_ingredient
            p1_pos = closest_ingredient
            p1_holding = ingredient
            debug_steps.append(f"    J1: aller en {closest_ingredient} chercher {ingredient} et le prendre: {dist_to_ingredient} cases")
            
            _, dist_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
            player1_distance += dist_to_pot
            p1_pos = pot_pos
            p1_holding = None
            debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_to_pot} cases")
        
        # J2 s'occupe de ses ingrédients (en utilisant comptoirs si avantageux)
        for ingredient in j2_ingredients:
            # J2 doit poser l'assiette temporairement
            _, dist_j2_to_pot_temp = self.grid.get_shortest_path(p2_pos, pot_pos)
            player2_distance += dist_j2_to_pot_temp
            p2_pos = pot_pos
            p2_holding = None  # Poser l'assiette au pot
            debug_steps.append(f"    J2: aller au pot {pot_pos} et poser l'assiette temporairement: {dist_j2_to_pot_temp} cases")
            
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p2_pos.manhattan_distance(pos))
            
            _, dist_to_ingredient = self.grid.get_shortest_path(p2_pos, closest_ingredient)
            player2_distance += dist_to_ingredient
            p2_pos = closest_ingredient
            p2_holding = ingredient
            debug_steps.append(f"    J2: aller en {closest_ingredient} chercher {ingredient} et le prendre: {dist_to_ingredient} cases")
            
            # Essayer de trouver un comptoir avantageux ; sinon trajet direct
            best_counter = None
            best_gain = -float('inf')
            for counter_pos in counter_positions:
                # Distances simplifiées (j2 deposit then j1 pickup)
                _, d_j2_to_counter = self.grid.get_shortest_path(p2_pos, counter_pos)
                _, d_counter_to_pot = self.grid.get_shortest_path(counter_pos, pot_pos)
                _, d_j1_to_counter = self.grid.get_shortest_path(player1_pos, counter_pos)
                
                if float('inf') in (d_j2_to_counter, d_counter_to_pot, d_j1_to_counter):
                    continue
                direct = self.grid.get_shortest_path(closest_ingredient, pot_pos)[1]
                coop_est = d_j2_to_counter + d_j1_to_counter + d_counter_to_pot
                gain = direct - coop_est
                if gain > best_gain:
                    best_gain = gain
                    best_counter = counter_pos
            
            if best_counter and best_gain > 0:
                # J2 dépose, J1 récupère
                _, dist_j2_to_counter = self.grid.get_shortest_path(p2_pos, best_counter)
                player2_distance += dist_j2_to_counter
                p2_pos = best_counter
                try:
                    self.deposit(2, best_counter, p2_holding, debug_steps)
                except Exception as e:
                    debug_steps.append(f"    ERREUR dépôt J2 parall: {e}")
                p2_holding = None
                
                _, dist_j1_to_counter = self.grid.get_shortest_path(player1_pos, best_counter)
                player1_distance += dist_j1_to_counter
                player1_pos_before = player1_pos
                player1_pos = best_counter
                try:
                    item = self.pickup(1, best_counter, debug_steps)
                except Exception as e:
                    debug_steps.append(f"    ERREUR pickup J1 parall: {e}")
                    item = None
                if item:
                    _, d_to_pot = self.grid.get_shortest_path(player1_pos, pot_pos)
                    player1_distance += d_to_pot
                    player1_pos = pot_pos
                    debug_steps.append(f"    J1: apporter {item} au pot {pot_pos}: {d_to_pot} cases")
            else:
                # trajet direct J2->pot
                _, dist_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
                player2_distance += dist_to_pot
                p2_pos = pot_pos
                p2_holding = None
                debug_steps.append(f"    J2: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_to_pot} cases")
        
        # J2 reprend l'assiette et livre
        p2_holding = 'plate'
        debug_steps.append(f"    J2: reprendre l'assiette au pot {pot_pos}")
        
        p2_holding = 'cooked_dish'
        debug_steps.append(f"    J2: au pot {pot_pos}, déposer l'assiette et prendre le plat cuisiné")
        
        _, dist_j2_to_service = self.grid.get_shortest_path(p2_pos, service_pos)
        player2_distance += dist_j2_to_service
        p2_holding = None
        debug_steps.append(f"    J2: livrer le plat au service {service_pos} et le déposer: {dist_j2_to_service} cases")
        
        total_distance = max(player1_distance, player2_distance)
        debug_steps.append(f"    Distances: J1={player1_distance}, J2={player2_distance}, Max={total_distance}")
        
        return {
            'name': 'Parallèle avec Comptoirs',
            'total_distance': total_distance,
            'debug_steps': debug_steps
        }
    
    def _find_best_counter_exchange(self, p1_pos: Position, p2_pos: Position, 
                                  ingredient_positions: List[Position], pot_pos: Position, 
                                  counter_positions: List[Position]) -> Dict:
        """Trouve la meilleure stratégie d'échange pour un ingrédient (direct vs comptoir)
           NOTE: cette fonction retourne une estimation (distances statiques). La simulation
           réelle repose sur deposit/pickup dans les stratégies appelantes.
        """
        
        if not counter_positions:
            # Pas de comptoirs, utiliser la stratégie directe (J1 par défaut)
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p1_pos.manhattan_distance(pos))
            _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, closest_ingredient)
            _, dist_ingredient_to_pot = self.grid.get_shortest_path(closest_ingredient, pot_pos)
            direct_distance = dist_j1_to_ingredient + dist_ingredient_to_pot
            
            return {
                'use_counter': False,
                'distance': direct_distance,
                'ingredient_pos': closest_ingredient
            }
        
        # Évaluer la stratégie directe pour chaque joueur
        best_direct_distance = float('inf')
        best_direct_ingredient = None
        best_direct_player = 1
        
        # J1 fait tout directement
        for ingredient_pos in ingredient_positions:
            _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
            _, dist_ingredient_to_pot = self.grid.get_shortest_path(ingredient_pos, pot_pos)
            direct_distance = dist_j1_to_ingredient + dist_ingredient_to_pot
            
            if direct_distance < best_direct_distance:
                best_direct_distance = direct_distance
                best_direct_ingredient = ingredient_pos
                best_direct_player = 1
        
        # J2 fait tout directement
        for ingredient_pos in ingredient_positions:
            _, dist_j2_to_ingredient = self.grid.get_shortest_path(p2_pos, ingredient_pos)
            _, dist_ingredient_to_pot = self.grid.get_shortest_path(ingredient_pos, pot_pos)
            direct_distance = dist_j2_to_ingredient + dist_ingredient_to_pot
            
            if direct_distance < best_direct_distance:
                best_direct_distance = direct_distance
                best_direct_ingredient = ingredient_pos
                best_direct_player = 2
        
        # Évaluer la stratégie avec comptoir
        best_counter_distance = float('inf')
        best_counter_option = None
        
        # Filtrer uniquement les comptoirs libres
        available_counters = [pos for pos in counter_positions if self.is_counter_free(pos)]
        
        if not available_counters:
            # Aucun comptoir libre, utiliser la stratégie directe
            return {
                'use_counter': False,
                'distance': best_direct_distance,
                'ingredient_pos': best_direct_ingredient,
                'player': best_direct_player
            }
        
        for ingredient_pos in ingredient_positions:
            for counter_pos in available_counters:
                # Option 1: J1 collecte → comptoir, J2 comptoir → pot
                _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
                _, dist_ingredient_to_counter = self.grid.get_shortest_path(ingredient_pos, counter_pos)
                j1_total = dist_j1_to_ingredient + dist_ingredient_to_counter
                
                _, dist_j2_to_counter = self.grid.get_shortest_path(p2_pos, counter_pos)
                _, dist_counter_to_pot = self.grid.get_shortest_path(counter_pos, pot_pos)
                j2_total = dist_j2_to_counter + dist_counter_to_pot
                
                # Calcul séquentiel: J1 doit finir le dépôt avant que J2 puisse prendre
                counter_total_option1 = max(j1_total, j2_total)  # Temps parallèle, pas somme
                
                if counter_total_option1 < best_counter_distance:
                    best_counter_distance = counter_total_option1
                    best_counter_option = {
                        'ingredient_pos': ingredient_pos,
                        'counter_pos': counter_pos,
                        'j1_time': j1_total,
                        'j2_time': j2_total,
                        'collector_player': 1,
                        'transporter_player': 2
                    }
                
                # Option 2: J2 collecte → comptoir, J1 comptoir → pot
                _, dist_j2_to_ingredient = self.grid.get_shortest_path(p2_pos, ingredient_pos)
                _, dist_ingredient_to_counter2 = self.grid.get_shortest_path(ingredient_pos, counter_pos)
                j2_total_collect = dist_j2_to_ingredient + dist_ingredient_to_counter2
                
                _, dist_j1_to_counter = self.grid.get_shortest_path(p1_pos, counter_pos)
                j1_total_transport = dist_j1_to_counter + dist_counter_to_pot
                
                counter_total_option2 = max(j2_total_collect, j1_total_transport)  # Temps parallèle
                
                if counter_total_option2 < best_counter_distance:
                    best_counter_distance = counter_total_option2
                    best_counter_option = {
                        'ingredient_pos': ingredient_pos,
                        'counter_pos': counter_pos,
                        'j1_time': j1_total_transport,
                        'j2_time': j2_total_collect,
                        'collector_player': 2,
                        'transporter_player': 1
                    }
        
        # Retourner la meilleure option seulement si elle apporte un gain significatif
        if (best_counter_option and 
            best_counter_distance + self.gain_threshold < best_direct_distance):
            return {
                'use_counter': True,
                'distance': best_counter_distance,
                'gain': best_direct_distance - best_counter_distance,
                **best_counter_option
            }
        else:
            return {
                'use_counter': False,
                'distance': best_direct_distance,
                'ingredient_pos': best_direct_ingredient,
                'player': best_direct_player
            }

    def _strategy_traditional(self, player1_pos: Position, player2_pos: Position, 
                            ingredients: List[str], pot_pos: Position, dish_pos: Position, 
                            service_pos: Position, onion_positions: List[Position], 
                            tomato_positions: List[Position]) -> Dict:
        """Stratégie traditionnelle: J1 collecte ingrédients UN PAR UN, J2 s'occupe assiette/service"""
        
        debug_steps = ["  [STRATÉGIE TRADITIONNELLE]"]
        player1_distance = 0
        player2_distance = 0
        p1_pos = player1_pos
        p2_pos = player2_pos
        p1_holding = None
        p2_holding = None
        
        # Phase 1: J1 collecte tous les ingrédients UN PAR UN
        for ingredient in ingredients:
            # Vérifier que J1 n'a rien dans les mains
            if p1_holding is not None:
                debug_steps.append(f"    ERREUR: J1 porte déjà {p1_holding}")
                return {'name': 'Traditionnelle', 'total_distance': float('inf'), 'debug_steps': debug_steps}
            
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p1_pos.manhattan_distance(pos))
            
            # J1 va chercher l'ingrédient
            _, dist_to_ingredient = self.grid.get_shortest_path(p1_pos, closest_ingredient)
            player1_distance += dist_to_ingredient
            p1_pos = closest_ingredient
            p1_holding = ingredient  # J1 prend l'ingrédient
            debug_steps.append(f"    J1: chercher {ingredient} en {closest_ingredient} et le prendre: {dist_to_ingredient} cases")
            
            # J1 apporte l'ingrédient au pot
            _, dist_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
            player1_distance += dist_to_pot
            p1_pos = pot_pos
            p1_holding = None  # J1 dépose l'ingrédient
            debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_to_pot} cases")
        
        # Phase 2: J2 va chercher l'assiette (pendant que J1 travaille)
        if p2_holding is not None:
            debug_steps.append(f"    ERREUR: J2 porte déjà {p2_holding}")
            return {'name': 'Traditionnelle', 'total_distance': float('inf'), 'debug_steps': debug_steps}
        
        _, dist_j2_to_dish = self.grid.get_shortest_path(p2_pos, dish_pos)
        player2_distance += dist_j2_to_dish
        p2_pos = dish_pos
        p2_holding = 'plate'  # J2 prend l'assiette
        debug_steps.append(f"    J2: aller en {dish_pos} chercher l'assiette et la prendre: {dist_j2_to_dish} cases")
        
        # Phase 3: J2 va au pot pour prendre le plat cuisiné (SEULEMENT après que J1 ait fini)
        # J2 doit avoir une assiette pour prendre le plat
        if p2_holding != 'plate':
            debug_steps.append(f"    ERREUR: J2 n'a pas d'assiette (porte: {p2_holding})")
            return {'name': 'Traditionnelle', 'total_distance': float('inf'), 'debug_steps': debug_steps}
        
        _, dist_j2_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
        player2_distance += dist_j2_to_pot
        p2_pos = pot_pos
        p2_holding = 'cooked_dish'  # J2 échange l'assiette contre le plat cuisiné
        debug_steps.append(f"    J2: aller au pot {pot_pos}, déposer l'assiette et prendre le plat: {dist_j2_to_pot} cases")
        
        # Phase 4: J2 livre le plat
        _, dist_j2_to_service = self.grid.get_shortest_path(p2_pos, service_pos)
        player2_distance += dist_j2_to_service
        p2_holding = None  # J2 livre le plat
        debug_steps.append(f"    J2: livrer le plat au service {service_pos} et le déposer: {dist_j2_to_service} cases")
        
        # Le temps total est le maximum (actions en parallèle)
        total_distance = max(player1_distance, player2_distance)
        debug_steps.append(f"    Distances: J1={player1_distance}, J2={player2_distance}, Max={total_distance}")
        
        # Créer des mouvements basiques pour les deux joueurs
        movements = [
            {
                'joueur': 1,
                'depart': f"{player1_pos.x},{player1_pos.y}",
                'arrivee': f"{pot_pos.x},{pot_pos.y}",
                'action': 'collect_ingredients',
                'objet': 'ingredients',
                'distance': player1_distance
            },
            {
                'joueur': 2,
                'depart': f"{player2_pos.x},{player2_pos.y}",
                'arrivee': f"{service_pos.x},{service_pos.y}",
                'action': 'serve_dish',
                'objet': 'cooked_dish',
                'distance': player2_distance
            }
        ]
        
        return {
            'name': 'Traditionnelle',
            'total_distance': total_distance,
            'debug_steps': debug_steps,
            'movements': movements
        }


# ---------------------------
# Fonctions utilitaires de chargement/evaluation (inchangées, avec petites sécurités)
# ---------------------------
def parse_layout_manually(content: str) -> Dict:
    """Parse manuellement un fichier layout avec format spécial"""
    import re
    
    # Extraire la grille entre les triple quotes
    grid_match = re.search(r'"grid":\s*"""([^"]+)"""', content, re.DOTALL)
    if not grid_match:
        raise ValueError("Impossible de trouver la grille dans le fichier")
    
    grid_str = grid_match.group(1).strip()
    
    # Extraire les autres champs avec regex
    def extract_field(field_name, content):
        pattern = rf'"{field_name}":\s*([^,}}]+)'
        match = re.search(pattern, content)
        if match:
            value_str = match.group(1).strip()
            if value_str.startswith('['):
                return json.loads(value_str)
            else:
                try:
                    return int(value_str)
                except:
                    return value_str.strip('"')
        return None
    
    result = {
        'grid': grid_str,
        'start_all_orders': extract_field('start_all_orders', content),
        'counter_goals': extract_field('counter_goals', content),
        'onion_value': extract_field('onion_value', content),
        'tomato_value': extract_field('tomato_value', content),
        'onion_time': extract_field('onion_time', content),
        'tomato_time': extract_field('tomato_time', content),
    }
    
    return result


def load_layout_file(filepath: str) -> Dict:
    """Charge un fichier layout avec support des chaînes multi-lignes Python"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Traiter le contenu comme du code Python pour gérer les """
    # Mais d'abord, on va extraire la grid de manière plus robuste
    try:
        # Méthode sécurisée : eval avec un namespace limité
        safe_dict = {"__builtins__": {}}
        result = eval(content, safe_dict)
        return result
    except:
        # Fallback : parsing manuel
        return parse_layout_manually(content)


def evaluate_single_layout(layout_path: str, gain_threshold: Optional[int] = None, minimal_output: bool = True) -> Dict:
    """Évalue un seul layout en solo et coop avec tracking détaillé des mouvements"""
    try:
        layout_data = load_layout_file(layout_path)
        grid_world = GridWorld(layout_data['grid'])
        executor = RecipeExecutor(grid_world, layout_data['start_all_orders'], gain_threshold if gain_threshold is not None else 1)
        
        # Activer le debug seulement si pas de sortie minimale
        executor.debug = not minimal_output
        
        # Calcul solo avec tracking détaillé
        solo_result = executor.calculate_solo_distance()
        if isinstance(solo_result, tuple) and len(solo_result) >= 3:
            solo_distance, solo_debug, solo_movements = solo_result
        else:
            solo_distance, solo_debug, solo_movements = solo_result, [], []
        
        # Calcul coop avec gestion d'erreur
        try:
            coop_result = executor.calculate_coop_distance()
            if isinstance(coop_result, tuple) and len(coop_result) >= 3:
                coop_distance, coop_debug, coop_movements = coop_result
            else:
                coop_distance, coop_debug, coop_movements = coop_result, [], []
        except Exception as e:
            print(f"⚠️  Erreur calcul coop pour {os.path.basename(layout_path)}: {e}")
            coop_distance, coop_debug, coop_movements = solo_distance, [], []
        
        result = {
            'layout_path': layout_path,
            'solo_distance': solo_distance,
            'coop_distance': coop_distance,
            'improvement_ratio': (solo_distance - coop_distance) / solo_distance if (isinstance(solo_distance, (int,float)) and solo_distance > 0) else 0,
            'evaluation_time': time.time(),
            'solo_movements': solo_movements,
            'coop_movements': coop_movements
        }
        
        # Ajouter les logs seulement si pas de mode minimal
        if not minimal_output:
            result['solo_debug'] = solo_debug
            result['coop_debug'] = coop_debug
        
        # Ajouter les logs seulement si pas de mode minimal
        if not minimal_output:
            result['solo_debug'] = solo_debug
            result['coop_debug'] = coop_debug
        
        return result
        
    except Exception as e:
        return {
            'layout_path': layout_path,
            'error': str(e),
            'evaluation_time': time.time()
        }


def process_single_layout_file(args):
    """
    Traite un seul fichier layout de manière thread-safe avec sortie minimale
    Args: tuple (layout_full_path, layout_folder, layout_base_num, recipe_num, layout_file)
    Returns: tuple (result_dict, success_flag)
    """
    layout_full_path, layout_folder, layout_base_num, recipe_num, layout_file = args
    
    # Utiliser le mode minimal pour économiser la mémoire et accélérer le traitement
    result = evaluate_single_layout(layout_full_path, minimal_output=True)
    success = 'error' not in result
    
    if success:
        # Ajouter des métadonnées minimales au résultat
        result['layout_folder'] = layout_folder
        result['layout_base_num'] = int(layout_base_num)
        result['recipe_num'] = int(recipe_num)
        result['layout_file'] = layout_file
        
        # Extraire numéro de variation depuis le nom de fichier (LX_RYY_VZZ.layout)
        variation_match = re.match(r'L\d+_R\d+_V(\d+)\.layout', layout_file)
        if variation_match:
            result['variation_num'] = int(variation_match.group(1))
    else:
        result['layout_folder'] = layout_folder
        result['layout_file'] = layout_file
    
    return result, success


def process_single_layout_parallel(file_path: str, minimal_output: bool = True) -> Dict:
    """Traite un seul fichier layout et sauvegarde le résultat JSON épuré"""
    try:
        result = evaluate_single_layout(file_path, minimal_output=minimal_output)
        
        # Sauvegarder directement le fichier JSON épuré
        save_layout_result_json(file_path, result)
        
        return result
    except Exception as e:
        return {
            'layout_file': os.path.basename(file_path),
            'error': f"Erreur traitement: {str(e)}"
        }


def save_layout_result_json(layout_path: str, result: Dict) -> None:
    """Sauvegarde le résultat d'un layout dans un fichier JSON ultra-compact"""
    # Générer le nom du fichier de sortie
    layout_name = os.path.splitext(os.path.basename(layout_path))[0]
    directory = os.path.dirname(layout_path)
    results_dir = os.path.join(os.path.dirname(directory), 'path_evaluation_results')
    os.makedirs(results_dir, exist_ok=True)
    
    # Format ultra-compact avec seulement les données essentielles
    compact_result = {
        'fichier': os.path.basename(layout_path),
        'solo_distance': result['solo_distance'],
        'coop_distance': result['coop_distance'],
        'solo_mouvements': result.get('solo_movements', []),
        'coop_mouvements': result.get('coop_movements', [])
    }
    
    # Sauvegarder
    output_file = os.path.join(results_dir, f"{layout_name}.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(compact_result, f, ensure_ascii=False, separators=(',', ':'))
    
    print(f"💾 Sauvegardé: {os.path.basename(output_file)}")


def evaluate_all_layouts_parallel(base_path: str, max_workers: Optional[int] = None) -> None:
    """Évalue tous les layouts en parallèle pour accélérer le traitement"""
    layouts_dir = os.path.join(base_path, 'layouts_with_objects')
    results_dir = os.path.join(base_path, 'path_evaluation_results')
    
    # Créer le dossier de résultats
    os.makedirs(results_dir, exist_ok=True)
    
    # Déterminer le nombre de workers
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), 8)  # Limiter à 8 pour éviter la surcharge
    
    total_layouts = 0
    successful_evaluations = 0
    failed_evaluations = 0
    
    print("🚀 Début de l'évaluation des layouts en PARALLÈLE...")
    print(f"📂 Dossier source: {layouts_dir}")
    print(f"📂 Dossier résultats: {results_dir}")
    print(f"🔧 Nombre de workers: {max_workers}")
    
    # Obtenir tous les dossiers de layouts
    layout_folders = [d for d in os.listdir(layouts_dir) 
                     if os.path.isdir(os.path.join(layouts_dir, d)) 
                     and d.startswith('layout_')]
    
    if not layout_folders:
        print("❌ Aucun dossier de layout trouvé!")
        return
    
    print(f"Trouvé {len(layout_folders)} dossiers de layouts")
    
    start_time = time.time()
    
    # Traiter chaque dossier
    for layout_folder in sorted(layout_folders):
        layout_path = os.path.join(layouts_dir, layout_folder)
        
        # Extraire les numéros depuis le nom du dossier
        layout_match = re.match(r'layout_(\d+)_R_(\d+)', layout_folder)
        if not layout_match:
            print(f"⚠️  Format de dossier non reconnu: {layout_folder}")
            continue
        
        layout_base_num = layout_match.group(1)
        recipe_num = layout_match.group(2)
        
        print(f"\n📁 Traitement: {layout_folder}")
        
        # Obtenir tous les fichiers .layout dans ce dossier
        layout_files = [f for f in os.listdir(layout_path) if f.endswith('.layout')]
        
        if not layout_files:
            print(f"  ⚠️  Aucun fichier .layout trouvé dans {layout_folder}")
            continue
        
        print(f"💾 Layouts à traiter: {len(layout_files)} (parallélisation sur {max_workers} workers)")
        total_layouts += len(layout_files)
        
        # Préparer les chemins des fichiers
        file_paths = [os.path.join(layout_path, f) for f in sorted(layout_files)]
        
        # Traitement en parallèle
        folder_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Soumettre toutes les tâches
            future_to_file = {
                executor.submit(process_single_layout_parallel, file_path, True): file_path 
                for file_path in file_paths
            }
            
            # Collecter les résultats au fur et à mesure
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                file_name = os.path.basename(file_path)
                
                try:
                    result = future.result()
                    
                    if 'error' not in result:
                        successful_evaluations += 1
                        # Ajouter des métadonnées
                        result['layout_folder'] = layout_folder
                        result['layout_base_num'] = int(layout_base_num)
                        result['recipe_num'] = int(recipe_num)
                        result['layout_file'] = file_name
                        
                        # Extraire numéro de variation
                        variation_match = re.match(r'L\d+_R\d+_V(\d+)\.layout', file_name)
                        if variation_match:
                            result['variation_num'] = int(variation_match.group(1))
                        
                        print(f"    ✅ {file_name}: Solo={result['solo_distance']}, Coop={result['coop_distance']}")
                    else:
                        failed_evaluations += 1
                        result['layout_folder'] = layout_folder
                        result['layout_file'] = file_name
                        print(f"    ❌ {file_name}: {result['error']}")
                    
                    folder_results.append(result)
                    
                except Exception as e:
                    failed_evaluations += 1
                    print(f"    🚨 Erreur pour {file_name}: {str(e)}")
                    folder_results.append({
                        'layout_folder': layout_folder,
                        'layout_file': file_name,
                        'error': f"Exception: {str(e)}"
                    })
        
        # Sauvegarder les résultats de ce dossier
        if folder_results:
            folder_results_file = os.path.join(results_dir, f'{layout_folder}_results.json')
            with open(folder_results_file, 'w', encoding='utf-8') as f:
                json.dump(folder_results, f, indent=2, ensure_ascii=False)
            print(f"💾 Sauvegardé: {os.path.basename(folder_results_file)} ({len(folder_results)} layouts)")
            
            # Créer aussi un fichier texte lisible pour l'analyse
            text_file = os.path.join(results_dir, f'{layout_folder}_movements.txt')
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(f"=== ANALYSE DES MOUVEMENTS - {layout_folder} ===\n\n")
                
                for result in folder_results:
                    if 'error' not in result:
                        f.write(f"📄 Fichier: {result['layout_file']}\n")
                        f.write(f"🎯 Solo: {result['solo_distance']} pas, Coop: {result['coop_distance']} pas\n")
                        f.write(f"📈 Amélioration: {result.get('improvement_ratio', 0)*100:.1f}%\n\n")
                        
                        if 'solo_movements_summary' in result:
                            f.write("🔵 MOUVEMENTS SOLO:\n")
                            for line in result['solo_movements_summary']:
                                f.write(f"   {line}\n")
                            f.write("\n")
                        
                        if 'coop_movements_summary' in result and result['coop_movements_summary']:
                            f.write("🟡 MOUVEMENTS COOPÉRATION:\n")
                            for line in result['coop_movements_summary']:
                                f.write(f"   {line}\n")
                            f.write("\n")
                        
                        f.write("-" * 80 + "\n\n")
            
            print(f"📝 Rapport lisible: {os.path.basename(text_file)}")
        
        # Affichage de progression
        elapsed_time = time.time() - start_time
        layouts_per_second = total_layouts / elapsed_time if elapsed_time > 0 else 0
        print(f"📊 Vitesse: {layouts_per_second:.1f} layouts/seconde")
    
    # Rapport final
    elapsed_time = time.time() - start_time
    print(f"\n🎉 Évaluation terminée en {elapsed_time:.1f} secondes!")
    print(f"   📈 Layouts traités: {total_layouts}")
    print(f"   ✅ Évaluations réussies: {successful_evaluations}")
    print(f"   ❌ Évaluations échouées: {failed_evaluations}")
    if total_layouts > 0:
        print(f"   📊 Taux de succès: {successful_evaluations/total_layouts*100:.1f}%")
        print(f"   ⚡ Vitesse moyenne: {total_layouts/elapsed_time:.1f} layouts/seconde")
    print(f"   📂 Résultats sauvegardés dans: {results_dir}")


# Alias pour compatibilité
def evaluate_all_layouts(base_path: str, max_workers: Optional[int] = None) -> None:
    """Version séquentielle conservée pour compatibilité - maintenant utilise la parallélisation"""
    return evaluate_all_layouts_parallel(base_path, max_workers)
    layouts_dir = os.path.join(base_path, 'layouts_with_objects')
    results_dir = os.path.join(base_path, 'path_evaluation_results')
    
    # Créer le dossier de résultats
    os.makedirs(results_dir, exist_ok=True)
    
    total_layouts = 0
    successful_evaluations = 0
    failed_evaluations = 0
    processed_layouts = 0
    
    print("🚀 Début de l'évaluation des layouts...")
    print(f"📂 Dossier source: {layouts_dir}")
    print(f"📂 Dossier résultats: {results_dir}")
    
    # Obtenir tous les dossiers de layouts (format: layout_X_combination_YY)
    layout_folders = [d for d in os.listdir(layouts_dir) 
                     if os.path.isdir(os.path.join(layouts_dir, d)) 
                     and d.startswith('layout_')]
    
    if not layout_folders:
        print("❌ Aucun dossier de layout trouvé!")
        return
    
    print(f"Trouvé {len(layout_folders)} dossiers de layouts")
    
    # Parcourir tous les dossiers de layouts
    for layout_folder in sorted(layout_folders):
        layout_path = os.path.join(layouts_dir, layout_folder)
        
        # Extraire le numéro de layout de base depuis le nom du dossier
        # Format: layout_X_R_YY
        layout_match = re.match(r'layout_(\d+)_R_(\d+)', layout_folder)
        if not layout_match:
            print(f"⚠️  Format de dossier non reconnu: {layout_folder}")
            continue
        
        layout_base_num = layout_match.group(1)
        recipe_num = layout_match.group(2)
        
        print(f"\n📁 Traitement: {layout_folder}")
        
        # Obtenir tous les fichiers .layout dans ce dossier
        layout_files = [f for f in os.listdir(layout_path) if f.endswith('.layout')]
        
        if not layout_files:
            print(f"  ⚠️  Aucun fichier .layout trouvé dans {layout_folder}")
            continue
        
        print(f"  📄 Trouvé {len(layout_files)} fichiers layout")
        
        # Traiter chaque fichier layout
        folder_results = []
        for i, layout_file in enumerate(sorted(layout_files), 1):
            layout_full_path = os.path.join(layout_path, layout_file)
            total_layouts += 1
            
            print(f"    [{i}/{len(layout_files)}] {layout_file}...", end=' ')
            
            result = evaluate_single_layout(layout_full_path, minimal_output=True)
            
            if 'error' not in result:
                successful_evaluations += 1
                # Ajouter des métadonnées minimales
                result['layout_folder'] = layout_folder
                result['layout_base_num'] = int(layout_base_num)
                result['recipe_num'] = int(recipe_num)
                result['layout_file'] = layout_file
                
                # Extraire numéro de variation depuis le nom de fichier (LX_RYY_VZZ.layout)
                variation_match = re.match(r'L\d+_R\d+_V(\d+)\.layout', layout_file)
                if variation_match:
                    result['variation_num'] = int(variation_match.group(1))
                
                print(f"✅ Solo: {result['solo_distance']}, Coop: {result['coop_distance']}")
            else:
                failed_evaluations += 1
                result['layout_folder'] = layout_folder
                result['layout_file'] = layout_file
                print(f"❌ {result['error']}")
            
            folder_results.append(result)
        
        processed_layouts += len(layout_files)
        
        # Sauvegarder les résultats de ce dossier immédiatement
        if folder_results:
            folder_results_file = os.path.join(results_dir, f'{layout_folder}_results.json')
            with open(folder_results_file, 'w', encoding='utf-8') as f:
                json.dump(folder_results, f, indent=2, ensure_ascii=False)
            print(f"💾 Sauvegardé: {os.path.basename(folder_results_file)} ({len(folder_results)} layouts)")
        
        # Affichage de progression
        progress = (processed_layouts / max(total_layouts, 1) * 100)
        print(f"📊 Progression: {progress:.1f}% ({processed_layouts} traités)")
    
    # Génération du rapport de synthèse final
    print(f"\n🎉 Évaluation terminée!")
    print(f"   📈 Layouts traités: {total_layouts}")
    print(f"   ✅ Évaluations réussies: {successful_evaluations}")
    print(f"   ❌ Évaluations échouées: {failed_evaluations}")
    if total_layouts > 0:
        print(f"   📊 Taux de succès: {successful_evaluations/total_layouts*100:.1f}%")
    print(f"   📂 Résultats sauvegardés dans: {results_dir}")
    
    # Optionnel: générer un fichier de synthèse globale si nécessaire
    print(f"   � Chaque dossier a son fichier de résultats pour un traitement optimisé")


def analyze_results(results_dir: str) -> None:
    """Analyse les résultats et génère un rapport de synthèse"""
    if not os.path.exists(results_dir):
        print("❌ Dossier de résultats introuvable")
        return
    
    all_results = []
    
    # Charger tous les résultats
    for file in os.listdir(results_dir):
        if file.endswith('_results.json'):
            with open(os.path.join(results_dir, file), 'r') as f:
                results = json.load(f)
                all_results.extend([r for r in results if 'error' not in r])
    
    if not all_results:
        print("❌ Aucun résultat valide trouvé")
        return
    
    # Statistiques
    solo_distances = [r['solo_distance'] for r in all_results if r['solo_distance'] != float('inf')]
    coop_distances = [r['coop_distance'] for r in all_results if r['coop_distance'] != float('inf')]
    improvements = [r['improvement_ratio'] for r in all_results if r['improvement_ratio'] > 0]
    
    print("\n📊 ANALYSE DES RÉSULTATS")
    print("=" * 50)
    print(f"Layouts analysés: {len(all_results)}")
    print(f"Distance solo moyenne: {sum(solo_distances)/len(solo_distances):.1f}")
    print(f"Distance coop moyenne: {sum(coop_distances)/len(coop_distances):.1f}")
    print(f"Amélioration moyenne: {sum(improvements)/len(improvements)*100:.1f}%")
    print(f"Meilleure amélioration: {max(improvements)*100:.1f}%")
    
    # Sauvegarder le rapport
    summary_file = os.path.join(results_dir, 'summary_analysis.json')
    summary = {
        'total_layouts': len(all_results),
        'solo_avg': sum(solo_distances)/len(solo_distances),
        'coop_avg': sum(coop_distances)/len(coop_distances),
        'improvement_avg': sum(improvements)/len(improvements),
        'best_improvement': max(improvements),
        'analysis_time': time.time()
    }
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📄 Rapport détaillé: {summary_file}")


def main():
    """Fonction principale"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    print("🍳 ÉVALUATEUR DE CHEMINS OPTIMAUX OVERCOOKED")
    print("=" * 60)
    
    # Test avec le layout d'exemple (path interne si présent)
    example_layout = os.path.join(base_path, 'layouts_with_objects', 'recette_lot_1', 
                                 'layout_combination_01', 'V1_layout_combination_01.layout')
    
    if os.path.exists(example_layout):
        print(f"🧪 Test avec layout d'exemple: {example_layout}")
        result = evaluate_single_layout(example_layout)
        
        if 'error' not in result:
            print(f"✅ Test réussi!")
            print(f"   Solo: {result['solo_distance']} cases")
            print(f"   Coop: {result['coop_distance']} cases")
            print(f"   Amélioration: {result['improvement_ratio']*100:.1f}%")
            
            # Afficher les détails en mode debug
            print("\n🔍 DÉTAILS SOLO:")
            for line in result['solo_debug']:
                print(f"   {line}")
            
            print("\n🔍 DÉTAILS COOP:")
            for line in result['coop_debug']:
                print(f"   {line}")
        else:
            print(f"❌ Erreur lors du test: {result['error']}")
            return
    
    # Demander confirmation pour l'évaluation complète
    try:
        response = input("\n🚀 Lancer l'évaluation complète de tous les layouts? (y/N): ")
    except Exception:
        response = 'n'
    if response.lower() == 'y':
        evaluate_all_layouts(base_path)
        
        # Analyser les résultats
        results_dir = os.path.join(base_path, 'path_evaluation_results')
        analyze_results(results_dir)
    else:
        print("👋 Évaluation annulée")


if __name__ == "__main__":
    main()
