#!/usr/bin/env python3
"""
Script d'évaluation des distances optimales en solo et coopération
pour l'environnement Overcooked GridWorld

Auteur: Agent IA
Date: Août 2025
"""

import json
import os
import heapq
import re
from collections import deque
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
import time


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
    """État du jeu incluant positions des joueurs et objets portés"""
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
            'player1': [], 'player2': [], 'empty': []
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
        
        return positions
    
    def is_valid_position(self, pos: Position) -> bool:
        """Vérifie si une position est valide et accessible"""
        if not (0 <= pos.x < self.width and 0 <= pos.y < self.height):
            return False
        
        cell = self.grid[pos.y][pos.x]
        return cell != 'X'  # Tout sauf les murs
    
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
        """Calcule le plus court chemin entre deux positions avec BFS"""
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
                
                if next_pos not in visited and self.is_valid_position(next_pos):
                    visited.add(next_pos)
                    queue.append((next_pos, path + [next_pos]))
        
        return [], float('inf')  # Pas de chemin trouvé


class RecipeExecutor:
    """Gestionnaire d'exécution des recettes en solo et coopération"""
    
    def __init__(self, grid_world: GridWorld, recipes: List[Dict]):
        self.grid = grid_world
        self.recipes = recipes
        self.debug = True
    
    def calculate_solo_distance(self) -> Tuple[int, List[str]]:
        """Calcule la distance totale en mode solo avec contrainte d'un objet à la fois"""
        if not self.grid.positions['player1']:
            return float('inf'), ["Erreur: Pas de position joueur 1"]
        
        player_pos = self.grid.positions['player1'][0]
        total_distance = 0
        debug_log = ["=== MODE SOLO ==="]
        player_holding = None  # Suivi de ce que porte le joueur
        
        for recipe_idx, recipe in enumerate(self.recipes):
            ingredients = recipe['ingredients']
            debug_log.append(f"\nRecette {recipe_idx + 1}: {ingredients}")
            
            # 1. Collecter tous les ingrédients et les mettre dans le pot (UN PAR UN)
            for ingredient in ingredients:
                # Vérifier que le joueur n'a rien dans les mains
                if player_holding is not None:
                    debug_log.append(f"Erreur: Joueur porte déjà {player_holding}")
                    return float('inf'), debug_log
                
                # Trouver l'ingrédient le plus proche
                ingredient_positions = self.grid.positions['onion'] if ingredient == 'onion' else self.grid.positions['tomato']
                
                if not ingredient_positions:
                    debug_log.append(f"Erreur: Aucun {ingredient} disponible")
                    return float('inf'), debug_log
                
                closest_ingredient = min(ingredient_positions, 
                                       key=lambda pos: player_pos.manhattan_distance(pos))
                
                # Aller chercher l'ingrédient
                path_to_ingredient, dist_to_ingredient = self.grid.get_shortest_path(player_pos, closest_ingredient)
                debug_log.append(f"  Aller chercher {ingredient} en {closest_ingredient}: {dist_to_ingredient} cases")
                total_distance += dist_to_ingredient
                player_pos = closest_ingredient
                player_holding = ingredient  # Le joueur prend l'ingrédient
                
                # Aller au pot et déposer l'ingrédient
                pot_pos = self.grid.positions['pot'][0]
                path_to_pot, dist_to_pot = self.grid.get_shortest_path(player_pos, pot_pos)
                debug_log.append(f"  Apporter {ingredient} au pot {pot_pos}: {dist_to_pot} cases")
                total_distance += dist_to_pot
                player_pos = pot_pos
                player_holding = None  # Le joueur dépose l'ingrédient
            
            # 2. Prendre une assiette (vérifier que les mains sont libres)
            if player_holding is not None:
                debug_log.append(f"Erreur: Joueur porte encore {player_holding}")
                return float('inf'), debug_log
            
            dish_pos = self.grid.positions['dish'][0]
            path_to_dish, dist_to_dish = self.grid.get_shortest_path(player_pos, dish_pos)
            debug_log.append(f"  Aller chercher l'assiette en {dish_pos}: {dist_to_dish} cases")
            total_distance += dist_to_dish
            player_pos = dish_pos
            player_holding = 'plate'  # Le joueur prend l'assiette
            
            # 3. Retourner au pot pour prendre le plat cuisiné
            path_back_to_pot, dist_back_to_pot = self.grid.get_shortest_path(player_pos, pot_pos)
            debug_log.append(f"  Retourner au pot pour le plat: {dist_back_to_pot} cases")
            total_distance += dist_back_to_pot
            player_pos = pot_pos
            player_holding = 'cooked_dish'  # Le joueur échange l'assiette contre le plat cuisiné
            
            # 4. Aller au service
            service_pos = self.grid.positions['service'][0]
            path_to_service, dist_to_service = self.grid.get_shortest_path(player_pos, service_pos)
            debug_log.append(f"  Livrer le plat au service {service_pos}: {dist_to_service} cases")
            total_distance += dist_to_service
            player_pos = service_pos
            player_holding = None  # Le joueur livre le plat
            
            debug_log.append(f"  Distance pour recette {recipe_idx + 1}: {dist_to_ingredient + dist_to_pot + dist_to_dish + dist_back_to_pot + dist_to_service}")
        
        debug_log.append(f"\nDistance totale SOLO: {total_distance}")
        return total_distance, debug_log
    
    def calculate_coop_distance(self) -> Tuple[int, List[str]]:
        """Calcule la distance totale en mode coopération optimisée"""
        if not self.grid.positions['player1'] or not self.grid.positions['player2']:
            return float('inf'), ["Erreur: Positions joueurs manquantes pour le mode coop"]
        
        player1_pos = self.grid.positions['player1'][0]
        player2_pos = self.grid.positions['player2'][0]
        total_distance = 0
        debug_log = ["=== MODE COOPÉRATION ==="]
        
        for recipe_idx, recipe in enumerate(self.recipes):
            ingredients = recipe['ingredients']
            debug_log.append(f"\nRecette {recipe_idx + 1}: {ingredients}")
            
            # Stratégie coopérative: répartir les tâches optimalement
            recipe_distance = self._execute_coop_recipe(player1_pos, player2_pos, ingredients, debug_log)
            total_distance += recipe_distance
            
            # Après chaque recette, positionner les joueurs au service
            service_pos = self.grid.positions['service'][0]
            player1_pos = service_pos
            player2_pos = service_pos
        
        debug_log.append(f"\nDistance totale COOP: {total_distance}")
        return total_distance, debug_log
    
    def _execute_coop_recipe(self, player1_start: Position, player2_start: Position, 
                           ingredients: List[str], debug_log: List[str]) -> int:
        """Exécute une recette en mode coopération avec optimisation et échanges à travers les murs"""
        
        # Positions importantes
        pot_pos = self.grid.positions['pot'][0]
        dish_pos = self.grid.positions['dish'][0]
        service_pos = self.grid.positions['service'][0]
        onion_positions = self.grid.positions['onion']
        tomato_positions = self.grid.positions['tomato']
        
        player1_pos = player1_start
        player2_pos = player2_start
        
        # Évaluer différentes stratégies et choisir la meilleure
        strategies = [
            self._strategy_traditional(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions),
            self._strategy_wall_exchange(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions),
            self._strategy_parallel_optimized(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions)
        ]
        
        # Choisir la stratégie avec la distance minimale
        best_strategy = min(strategies, key=lambda s: s['total_distance'])
        
        # Ajouter les détails au debug log
        debug_log.extend(best_strategy['debug_steps'])
        debug_log.append(f"  Stratégie choisie: {best_strategy['name']}")
        debug_log.append(f"  Distance totale: {best_strategy['total_distance']}")
        
        return best_strategy['total_distance']
    
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
        
        return {
            'name': 'Traditionnelle',
            'total_distance': total_distance,
            'debug_steps': debug_steps
        }
    
    def _strategy_wall_exchange(self, player1_pos: Position, player2_pos: Position, 
                              ingredients: List[str], pot_pos: Position, dish_pos: Position, 
                              service_pos: Position, onion_positions: List[Position], 
                              tomato_positions: List[Position]) -> Dict:
        """Stratégie avec échange à travers les murs pour optimiser les distances"""
        
        debug_steps = ["  [STRATÉGIE ÉCHANGE MURS]"]
        player1_distance = 0
        player2_distance = 0
        p1_pos = player1_pos
        p2_pos = player2_pos
        p1_holding = None  # Initialiser le tracking des objets
        p2_holding = None  # Initialiser le tracking des objets
        
        # D'abord, J2 va chercher l'assiette
        _, dist_j2_to_dish = self.grid.get_shortest_path(p2_pos, dish_pos)
        player2_distance += dist_j2_to_dish
        p2_pos = dish_pos
        debug_steps.append(f"    J2: aller en {dish_pos} chercher l'assiette et la prendre: {dist_j2_to_dish} cases")
        
        # Pour chaque ingrédient, évaluer si un échange à travers un mur est avantageux
        for ingredient in ingredients:
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            
            best_option = self._find_best_ingredient_strategy(p1_pos, p2_pos, ingredient_positions, pot_pos)
            
            if best_option['type'] == 'wall_exchange':
                # Vérifier que J1 n'a rien dans les mains
                if p1_pos == player1_pos and len([i for i in ingredients[:ingredients.index(ingredient)]]) > 0:
                    # J1 a déjà manipulé des ingrédients, vérifier cohérence
                    pass
                
                # J1 va chercher l'ingrédient (mains libres requises)
                _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, best_option['ingredient_pos'])
                player1_distance += dist_j1_to_ingredient
                p1_pos = best_option['ingredient_pos']
                p1_holding = ingredient  # J1 prend l'ingrédient
                debug_steps.append(f"    J1: aller en {best_option['ingredient_pos']} chercher {ingredient} et le prendre: {dist_j1_to_ingredient} cases")
                
                # J1 va déposer l'ingrédient sur le mur
                _, dist_j1_to_wall = self.grid.get_shortest_path(p1_pos, best_option['exchange_pos_j1'])
                player1_distance += dist_j1_to_wall
                p1_pos = best_option['exchange_pos_j1']
                p1_holding = None  # J1 dépose l'ingrédient sur le mur
                debug_steps.append(f"    J1: aller au mur {best_option['exchange_pos_j1']} et déposer {ingredient}: {dist_j1_to_wall} cases")
                
                # J2 va au point d'échange (de l'autre côté du mur) - mains libres requises
                if p2_holding is not None:
                    debug_steps.append(f"    ERREUR: J2 porte déjà {p2_holding}")
                    return {
                        'name': 'Échange Murs',
                        'total_distance': float('inf'),
                        'debug_steps': debug_steps
                    }
                
                _, dist_j2_to_wall = self.grid.get_shortest_path(p2_pos, best_option['exchange_pos_j2'])
                player2_distance += dist_j2_to_wall
                p2_pos = best_option['exchange_pos_j2']
                debug_steps.append(f"    J2: aller au mur {best_option['exchange_pos_j2']} pour récupérer {ingredient}: {dist_j2_to_wall} cases")
                
                # Gérer le temps d'attente si nécessaire
                if 'wait_time' in best_option and best_option['wait_time'] > 0:
                    player2_distance += best_option['wait_time']
                    debug_steps.append(f"    J2: attendre que J1 dépose l'ingrédient: {best_option['wait_time']} cases")
                
                # J2 récupère l'ingrédient et va au pot
                p2_holding = ingredient  # J2 prend l'ingrédient du mur
                _, dist_j2_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
                player2_distance += dist_j2_to_pot
                p2_pos = pot_pos
                p2_holding = None  # J2 dépose l'ingrédient au pot
                debug_steps.append(f"    J2: prendre {ingredient} du mur et aller au pot {pot_pos} le déposer: {dist_j2_to_pot} cases")
                
            else:
                # Stratégie normale - J1 doit avoir les mains libres
                if p1_holding is not None:
                    debug_steps.append(f"    ERREUR: J1 porte déjà {p1_holding}")
                    return {
                        'name': 'Échange Murs',
                        'total_distance': float('inf'),
                        'debug_steps': debug_steps
                    }
                
                closest_ingredient = min(ingredient_positions, 
                                       key=lambda pos: p1_pos.manhattan_distance(pos))
                
                _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, closest_ingredient)
                player1_distance += dist_j1_to_ingredient
                p1_pos = closest_ingredient
                p1_holding = ingredient  # J1 prend l'ingrédient
                debug_steps.append(f"    J1: aller en {closest_ingredient} chercher {ingredient} et le prendre: {dist_j1_to_ingredient} cases")
                
                _, dist_j1_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
                player1_distance += dist_j1_to_pot
                p1_pos = pot_pos
                p1_holding = None  # J1 dépose l'ingrédient
                debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_j1_to_pot} cases")
        
        # J2 va au pot pour prendre le plat cuisiné (doit avoir une assiette)
        if p2_holding != 'plate':
            debug_steps.append(f"    ERREUR: J2 n'a pas d'assiette pour prendre le plat (porte: {p2_holding})")
            return {
                'name': 'Échange Murs',
                'total_distance': float('inf'),
                'debug_steps': debug_steps
            }
        
        _, dist_j2_to_pot_final = self.grid.get_shortest_path(p2_pos, pot_pos)
        player2_distance += dist_j2_to_pot_final
        p2_pos = pot_pos
        p2_holding = 'cooked_dish'  # J2 échange l'assiette contre le plat cuisiné
        debug_steps.append(f"    J2: aller au pot {pot_pos}, déposer l'assiette et prendre le plat final: {dist_j2_to_pot_final} cases")
        
        # J2 livre le plat
        _, dist_j2_to_service = self.grid.get_shortest_path(p2_pos, service_pos)
        player2_distance += dist_j2_to_service
        p2_holding = None  # J2 livre le plat
        debug_steps.append(f"    J2: livrer le plat au service {service_pos} et le déposer: {dist_j2_to_service} cases")
        
        total_distance = max(player1_distance, player2_distance)
        debug_steps.append(f"    Distances: J1={player1_distance}, J2={player2_distance}, Max={total_distance}")
        
        return {
            'name': 'Échange Murs',
            'total_distance': total_distance,
            'debug_steps': debug_steps
        }
    
    def _strategy_parallel_optimized(self, player1_pos: Position, player2_pos: Position, 
                                   ingredients: List[str], pot_pos: Position, dish_pos: Position, 
                                   service_pos: Position, onion_positions: List[Position], 
                                   tomato_positions: List[Position]) -> Dict:
        """Stratégie avec répartition optimale des tâches - contrainte un objet par joueur"""
        
        debug_steps = ["  [STRATÉGIE PARALLÈLE OPTIMISÉE]"]
        
        # Répartir les ingrédients entre les deux joueurs de manière optimale
        total_ingredients = len(ingredients)
        
        if total_ingredients == 1:
            # Un seul ingrédient: J1 s'en occupe, J2 prépare assiette
            return self._strategy_traditional(player1_pos, player2_pos, ingredients, pot_pos, dish_pos, service_pos, onion_positions, tomato_positions)
        
        # Pour plusieurs ingrédients, essayer de répartir
        mid_point = total_ingredients // 2
        j1_ingredients = ingredients[:mid_point] if mid_point > 0 else []
        j2_ingredients = ingredients[mid_point:]
        
        player1_distance = 0
        player2_distance = 0
        p1_pos = player1_pos
        p2_pos = player2_pos
        p1_holding = None
        p2_holding = None
        
        # J2 va d'abord chercher l'assiette (pour pouvoir prendre le plat final)
        _, dist_j2_to_dish = self.grid.get_shortest_path(p2_pos, dish_pos)
        player2_distance += dist_j2_to_dish
        p2_pos = dish_pos
        p2_holding = 'plate'  # J2 prend l'assiette
        debug_steps.append(f"    J2: aller en {dish_pos} chercher l'assiette et la prendre: {dist_j2_to_dish} cases")
        
        # J1 s'occupe de sa part d'ingrédients (UN PAR UN)
        for ingredient in j1_ingredients:
            if p1_holding is not None:
                debug_steps.append(f"    ERREUR: J1 porte déjà {p1_holding}")
                return {
                    'name': 'Parallèle Optimisée',
                    'total_distance': float('inf'),
                    'debug_steps': debug_steps
                }
            
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p1_pos.manhattan_distance(pos))
            
            _, dist_to_ingredient = self.grid.get_shortest_path(p1_pos, closest_ingredient)
            player1_distance += dist_to_ingredient
            p1_pos = closest_ingredient
            p1_holding = ingredient  # J1 prend l'ingrédient
            debug_steps.append(f"    J1: aller en {closest_ingredient} chercher {ingredient} et le prendre: {dist_to_ingredient} cases")
            
            _, dist_to_pot = self.grid.get_shortest_path(p1_pos, pot_pos)
            player1_distance += dist_to_pot
            p1_pos = pot_pos
            p1_holding = None  # J1 dépose l'ingrédient
            debug_steps.append(f"    J1: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_to_pot} cases")
        
        # J2 s'occupe de sa part d'ingrédients (APRÈS avoir pris l'assiette)
        # J2 doit d'abord poser l'assiette quelque part pour prendre les ingrédients
        temp_assiette_pos = None
        
        for ingredient in j2_ingredients:
            if p2_holding == 'plate':
                # J2 doit poser l'assiette temporairement
                # Chercher une position sûre (pot ou position vide adjacente)
                temp_assiette_pos = pot_pos  # Simplifié: on pose l'assiette au pot
                _, dist_to_temp_pos = self.grid.get_shortest_path(p2_pos, temp_assiette_pos)
                player2_distance += dist_to_temp_pos
                p2_pos = temp_assiette_pos
                p2_holding = None  # J2 pose l'assiette temporairement
                debug_steps.append(f"    J2: aller au pot {temp_assiette_pos} poser l'assiette temporairement: {dist_to_temp_pos} cases")
            
            ingredient_positions = onion_positions if ingredient == 'onion' else tomato_positions
            closest_ingredient = min(ingredient_positions, 
                                   key=lambda pos: p2_pos.manhattan_distance(pos))
            
            _, dist_to_ingredient = self.grid.get_shortest_path(p2_pos, closest_ingredient)
            player2_distance += dist_to_ingredient
            p2_pos = closest_ingredient
            p2_holding = ingredient  # J2 prend l'ingrédient
            debug_steps.append(f"    J2: aller en {closest_ingredient} chercher {ingredient} et le prendre: {dist_to_ingredient} cases")
            
            _, dist_to_pot = self.grid.get_shortest_path(p2_pos, pot_pos)
            player2_distance += dist_to_pot
            p2_pos = pot_pos
            p2_holding = None  # J2 dépose l'ingrédient
            debug_steps.append(f"    J2: apporter {ingredient} au pot {pot_pos} et le déposer: {dist_to_pot} cases")
        
        # J2 reprend l'assiette si nécessaire
        if temp_assiette_pos and p2_holding != 'plate':
            # L'assiette est au pot, J2 la reprend
            p2_holding = 'plate'  # J2 reprend l'assiette
            debug_steps.append(f"    J2: reprendre l'assiette au pot {temp_assiette_pos}")
        
        # J2 prend le plat et le livre (il a l'assiette)
        if p2_holding != 'plate':
            debug_steps.append(f"    ERREUR: J2 n'a pas d'assiette pour prendre le plat")
            return {
                'name': 'Parallèle Optimisée',
                'total_distance': float('inf'),
                'debug_steps': debug_steps
            }
        
        # J2 échange l'assiette contre le plat cuisiné (déjà au pot)
        p2_holding = 'cooked_dish'
        debug_steps.append(f"    J2: au pot {pot_pos}, déposer l'assiette et prendre le plat cuisiné")
        
        _, dist_j2_to_service = self.grid.get_shortest_path(p2_pos, service_pos)
        player2_distance += dist_j2_to_service
        p2_holding = None  # J2 livre le plat
        debug_steps.append(f"    J2: livrer le plat au service {service_pos} et le déposer: {dist_j2_to_service} cases")
        
        total_distance = max(player1_distance, player2_distance)
        debug_steps.append(f"    Distances: J1={player1_distance}, J2={player2_distance}, Max={total_distance}")
        
        return {
            'name': 'Parallèle Optimisée',
            'total_distance': total_distance,
            'debug_steps': debug_steps
        }
    
    def _find_best_ingredient_strategy(self, p1_pos: Position, p2_pos: Position, 
                                     ingredient_positions: List[Position], pot_pos: Position) -> Dict:
        """Trouve la meilleure stratégie pour récupérer un ingrédient (normal vs échange mur)"""
        
        best_normal_distance = float('inf')
        best_ingredient = None
        
        # Stratégie normale: J1 va chercher et apporte au pot
        for ingredient_pos in ingredient_positions:
            _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
            _, dist_ingredient_to_pot = self.grid.get_shortest_path(ingredient_pos, pot_pos)
            total_normal = dist_j1_to_ingredient + dist_ingredient_to_pot
            
            if total_normal < best_normal_distance:
                best_normal_distance = total_normal
                best_ingredient = ingredient_pos
        
        # Stratégie échange mur: J1 dépose sur mur, J2 récupère de l'autre côté
        best_wall_distance = float('inf')
        best_wall_option = None
        
        for ingredient_pos in ingredient_positions:
            # Chercher des positions d'échange possibles
            for x in range(self.grid.width):
                for y in range(self.grid.height):
                    pos1 = Position(x, y)
                    
                    # Essayer les 4 directions pour l'échange à travers un mur
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        pos2 = Position(x + dx, y + dy)
                        
                        if (self.grid.is_valid_position(pos1) and 
                            self.grid.is_valid_position(pos2) and 
                            self.grid.can_pass_through_wall(pos1, pos2)):
                            
                            # Calculer les distances pour cette option d'échange
                            # J1: va chercher l'ingrédient puis le dépose sur pos1
                            _, dist_j1_to_ingredient = self.grid.get_shortest_path(p1_pos, ingredient_pos)
                            _, dist_ingredient_to_wall_j1 = self.grid.get_shortest_path(ingredient_pos, pos1)
                            j1_total_time = dist_j1_to_ingredient + dist_ingredient_to_wall_j1
                            
                            # J2: va à pos2 puis récupère l'ingrédient et va au pot
                            _, dist_j2_to_wall = self.grid.get_shortest_path(p2_pos, pos2)
                            _, dist_wall_to_pot = self.grid.get_shortest_path(pos2, pot_pos)
                            j2_total_time = dist_j2_to_wall + dist_wall_to_pot
                            
                            # Le temps total est le maximum car ils agissent en parallèle
                            # MAIS J2 ne peut récupérer qu'après que J1 ait déposé
                            # Donc si J1 finit après J2 arrive au mur, alors temps = J1
                            # Sinon J2 doit attendre, donc temps = J2 + temps d'attente
                            j2_arrival_at_wall = dist_j2_to_wall
                            j1_deposit_time = j1_total_time
                            
                            if j1_deposit_time <= j2_arrival_at_wall:
                                # J2 arrive après que J1 ait déposé, pas d'attente
                                total_wall_time = j2_total_time
                            else:
                                # J2 doit attendre que J1 dépose
                                wait_time = j1_deposit_time - j2_arrival_at_wall
                                total_wall_time = j2_total_time + wait_time
                            
                            if total_wall_time < best_wall_distance:
                                best_wall_distance = total_wall_time
                                best_wall_option = {
                                    'ingredient_pos': ingredient_pos,
                                    'exchange_pos_j1': pos1,
                                    'exchange_pos_j2': pos2,
                                    'j1_time': j1_total_time,
                                    'j2_time': j2_total_time,
                                    'wait_time': max(0, j1_deposit_time - j2_arrival_at_wall)
                                }
        
        # Retourner la meilleure option
        if best_wall_option and best_wall_distance < best_normal_distance:
            return {
                'type': 'wall_exchange',
                **best_wall_option
            }
        else:
            return {
                'type': 'normal',
                'ingredient_pos': best_ingredient
            }


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


def evaluate_single_layout(layout_path: str) -> Dict:
    """Évalue un seul layout en solo et coop"""
    try:
        layout_data = load_layout_file(layout_path)
        grid_world = GridWorld(layout_data['grid'])
        executor = RecipeExecutor(grid_world, layout_data['start_all_orders'])
        
        # Calculs
        solo_distance, solo_debug = executor.calculate_solo_distance()
        coop_distance, coop_debug = executor.calculate_coop_distance()
        
        result = {
            'layout_path': layout_path,
            'solo_distance': solo_distance,
            'coop_distance': coop_distance,
            'improvement_ratio': (solo_distance - coop_distance) / solo_distance if solo_distance > 0 else 0,
            'solo_debug': solo_debug,
            'coop_debug': coop_debug,
            'evaluation_time': time.time()
        }
        
        return result
        
    except Exception as e:
        return {
            'layout_path': layout_path,
            'error': str(e),
            'evaluation_time': time.time()
        }


def evaluate_all_layouts(base_path: str) -> None:
    """Évalue tous les layouts dans le dossier layouts_with_objects"""
    layouts_dir = os.path.join(base_path, 'layouts_with_objects')
    results_dir = os.path.join(base_path, 'path_evaluation_results')
    
    # Créer le dossier de résultats
    os.makedirs(results_dir, exist_ok=True)
    
    total_layouts = 0
    successful_evaluations = 0
    
    print("🚀 Début de l'évaluation des layouts...")
    
    # Parcourir tous les lots de recettes
    for recette_lot in sorted(os.listdir(layouts_dir)):
        lot_path = os.path.join(layouts_dir, recette_lot)
        if not os.path.isdir(lot_path):
            continue
        
        print(f"\n📁 Traitement du {recette_lot}...")
        lot_results = []
        
        # Parcourir toutes les combinaisons de layouts
        for combination in sorted(os.listdir(lot_path)):
            combination_path = os.path.join(lot_path, combination)
            if not os.path.isdir(combination_path):
                continue
            
            print(f"  🎯 {combination}...")
            
            # Parcourir toutes les versions
            for layout_file in sorted(os.listdir(combination_path)):
                if layout_file.endswith('.layout'):
                    layout_full_path = os.path.join(combination_path, layout_file)
                    total_layouts += 1
                    
                    print(f"    📊 {layout_file}...", end=' ')
                    
                    result = evaluate_single_layout(layout_full_path)
                    if 'error' not in result:
                        successful_evaluations += 1
                        print(f"✅ Solo: {result['solo_distance']}, Coop: {result['coop_distance']}")
                    else:
                        print(f"❌ {result['error']}")
                    
                    lot_results.append(result)
        
        # Sauvegarder les résultats du lot
        lot_results_file = os.path.join(results_dir, f'{recette_lot}_results.json')
        with open(lot_results_file, 'w', encoding='utf-8') as f:
            json.dump(lot_results, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 Résultats sauvegardés: {lot_results_file}")
    
    # Résumé global
    print(f"\n🎉 Évaluation terminée!")
    print(f"   📈 Layouts évalués: {successful_evaluations}/{total_layouts}")
    print(f"   📂 Résultats dans: {results_dir}")


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
    base_path = '/home/cesar/python-projects/Overcooked-coop-voice/test_generation_layout'
    
    print("🍳 ÉVALUATEUR DE CHEMINS OPTIMAUX OVERCOOKED")
    print("=" * 60)
    
    # Test avec le layout d'exemple
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
    response = input("\n🚀 Lancer l'évaluation complète de tous les layouts? (y/N): ")
    if response.lower() == 'y':
        evaluate_all_layouts(base_path)
        
        # Analyser les résultats
        results_dir = os.path.join(base_path, 'path_evaluation_results')
        analyze_results(results_dir)
    else:
        print("👋 Évaluation annulée")


if __name__ == "__main__":
    main()
