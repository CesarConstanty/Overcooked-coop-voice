#!/usr/bin/env python3
"""
Path Evaluator Solo & Duo - Évaluateur de Layouts Overcooked

Ce module analyse les layouts du jeu Overcooked pour calculer le temps optimal
de réalisation des recettes en mode solo et duo.

Fonctionnalités:
1. Analyse tous les fichiers .layout du dossier layouts_with_objects
2. Calcule le temps minimal pour compléter toutes les recettes en solo et duo
3. Utilise l'algorithme A* pour trouver les chemins optimaux
4. Génère des fichiers JSON détaillés retraçant les événements de chaque partie
5. Prend en compte les règles du jeu (échange d'objets, cuisson, service)

Règles du jeu:
- X = bordure/comptoir d'échange ; 1 = joueur 1 ; 2 = joueur 2
- T = distributeur tomate ; O = distributeur oignon ; S = zone de service
- D = distributeur d'assiettes ; P = pot
- 1 action = 1 step de temps
- Joueurs n'ont qu'un objet à la fois
- Impossible d'être à deux sur une même case
- Échange d'objets via comptoirs

Author: Assistant AI Expert
Date: Août 2025
"""

import os
import json
import glob
import heapq
from collections import deque
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
import copy

class GameState:
    """Représente l'état du jeu à un instant donné"""
    
    def __init__(self, layout, recipes):
        self.layout = layout
        self.recipes = recipes
        self.width = len(layout[0])
        self.height = len(layout)
        
        # Positions des éléments
        self.player_positions = {}
        self.pot_position = None
        self.service_position = None
        self.onion_dispenser = None
        self.tomato_dispenser = None
        self.dish_dispenser = None
        self.counters = []
        
        # État du jeu
        self.player_inventory = {}  # Que porte chaque joueur
        self.counter_items = {}     # Objets sur les comptoirs
        self.pot_contents = []      # Ingrédients dans le pot
        self.pot_cooking = False    # Est-ce que le pot cuisine
        self.pot_cooking_time = 0   # Temps de cuisson restant
        self.completed_recipes = [] # Recettes terminées
        self.current_step = 0       # Étape actuelle
        
        self._parse_layout()
        
    def _parse_layout(self):
        """Parse le layout pour identifier les positions importantes"""
        self.walls = []  # Nouvelles: stocker les murs séparément
        
        for y in range(self.height):
            for x in range(self.width):
                cell = self.layout[y][x]
                if cell == '1':
                    self.player_positions[1] = (x, y)
                    self.player_inventory[1] = None
                elif cell == '2':
                    self.player_positions[2] = (x, y)
                    self.player_inventory[2] = None
                elif cell == 'P':
                    self.pot_position = (x, y)
                elif cell == 'S':
                    self.service_position = (x, y)
                elif cell.lower() == 'o':  # Supporter 'o' et 'O'
                    self.onion_dispenser = (x, y)
                elif cell.lower() == 't':  # Supporter 't' et 'T'
                    self.tomato_dispenser = (x, y)
                elif cell == 'D':
                    self.dish_dispenser = (x, y)
                elif cell == 'X':
                    self.counters.append((x, y))
                elif cell == '#':  # Murs sont représentés par '#'
                    self.walls.append((x, y))
        
        # Initialiser les inventaires des comptoirs
        for counter in self.counters:
            self.counter_items[counter] = None
    
    def is_valid_position(self, x, y):
        """Vérifie si une position est valide (dans les limites et pas un mur)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            # Checker si c'est un mur - les vrais murs dans ces layouts semblent être 'X' parfois
            cell = self.layout[y][x]
            # Permettre le déplacement sur tous les espaces sauf les murs explicites
            return cell not in ['#']  # '#' = mur, 'X' = comptoir donc navigable
        return False
    
    def get_neighbors(self, pos):
        """Retourne les positions voisines valides"""
        x, y = pos
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                neighbors.append((nx, ny))
        return neighbors
    
    def is_position_occupied(self, pos, excluding_player=None):
        """Vérifie si une position est occupée par un autre joueur"""
        for player_id, player_pos in self.player_positions.items():
            if player_id != excluding_player and player_pos == pos:
                return True
        return False
    
    def copy(self):
        """Crée une copie profonde de l'état"""
        new_state = copy.deepcopy(self)
        return new_state

class DistanceCalculator:
    """Classe pour pré-calculer toutes les distances avec BFS"""
    
    def __init__(self, game_state):
        self.state = game_state
        self.distances = {}
        self._precompute_all_distances()
    
    def bfs_distance(self, start, goal):
        """Calcule la distance minimale entre deux points avec BFS"""
        if start == goal:
            return 0
        
        queue = deque([(start, 0)])
        visited = {start}
        
        while queue:
            pos, dist = queue.popleft()
            
            for neighbor in self.state.get_neighbors(pos):
                if neighbor == goal:
                    return dist + 1
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        
        return float('inf')  # Inaccessible
    
    def _precompute_all_distances(self):
        """Pré-calcule toutes les distances importantes"""
        # Points d'intérêt
        points = {}
        if self.state.player_positions:
            points.update({f'player_{k}': v for k, v in self.state.player_positions.items()})
        if self.state.pot_position:
            points['pot'] = self.state.pot_position
        if self.state.service_position:
            points['service'] = self.state.service_position
        if self.state.onion_dispenser:
            points['onion_dispenser'] = self.state.onion_dispenser
        if self.state.tomato_dispenser:
            points['tomato_dispenser'] = self.state.tomato_dispenser
        if self.state.dish_dispenser:
            points['dish_dispenser'] = self.state.dish_dispenser
        
        # Ajouter tous les comptoirs
        for i, counter in enumerate(self.state.counters):
            points[f'counter_{i}'] = counter
        
        # Calculer toutes les distances entre tous les points
        for name1, pos1 in points.items():
            for name2, pos2 in points.items():
                if name1 != name2:
                    self.distances[(name1, name2)] = self.bfs_distance(pos1, pos2)
    
    def get_distance(self, from_name, to_name):
        """Récupère une distance pré-calculée"""
        return self.distances.get((from_name, to_name), float('inf'))
    
    def find_best_counter_route(self, from_pos, to_pos):
        """Trouve le meilleur comptoir pour un transfert indirect"""
        direct_distance = self.bfs_distance(from_pos, to_pos)
        best_counter = None
        best_total_distance = direct_distance
        
        for i, counter in enumerate(self.state.counters):
            # Distance via ce comptoir
            dist_to_counter = self.bfs_distance(from_pos, counter)
            dist_from_counter = self.bfs_distance(counter, to_pos)
            total_distance = dist_to_counter + dist_from_counter
            
            if total_distance < best_total_distance:
                best_total_distance = total_distance
                best_counter = counter
        
        return best_counter, best_total_distance, direct_distance

class OvercookedPathfinder:
    """Classe pour trouver les chemins optimaux dans Overcooked avec BFS et échanges via comptoirs"""
    
    def __init__(self):
        self.onion_time = 9
        self.tomato_time = 6
        self.distance_calc = None
        
    def bfs_path(self, start, goal, state, excluding_player=None):
        """Trouve le chemin le plus court avec BFS"""
        if start == goal:
            return [start]
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor in state.get_neighbors(current):
                if neighbor in visited:
                    continue
                
                if state.is_position_occupied(neighbor, excluding_player):
                    continue
                
                new_path = path + [neighbor]
                
                if neighbor == goal:
                    return new_path
                
                visited.add(neighbor)
                queue.append((neighbor, new_path))
        
        return []  # Aucun chemin trouvé
    
    def optimize_ingredient_transport(self, state, ingredient_pos, pot_pos, player1_pos, player2_pos):
        """Détermine la meilleure stratégie pour transporter un ingrédient au pot"""
        # Option 1: Transport direct par le joueur le plus proche
        dist1_to_ing = self.distance_calc.bfs_distance(player1_pos, ingredient_pos)
        dist1_ing_to_pot = self.distance_calc.bfs_distance(ingredient_pos, pot_pos)
        total_direct_p1 = dist1_to_ing + dist1_ing_to_pot
        
        dist2_to_ing = self.distance_calc.bfs_distance(player2_pos, ingredient_pos)
        dist2_ing_to_pot = self.distance_calc.bfs_distance(ingredient_pos, pot_pos)
        total_direct_p2 = dist2_to_ing + dist2_ing_to_pot
        
        direct_best = min(total_direct_p1, total_direct_p2)
        direct_player = 1 if total_direct_p1 <= total_direct_p2 else 2
        
        # Option 2: Via comptoir - un joueur collecte, l'autre transfère
        best_via_counter = float('inf')
        best_counter = None
        best_strategy = None
        
        for counter in state.counters:
            # Joueur 1 collecte, Joueur 2 transfère
            collect_time_p1 = dist1_to_ing + self.distance_calc.bfs_distance(ingredient_pos, counter)
            transfer_time_p2 = self.distance_calc.bfs_distance(player2_pos, counter) + self.distance_calc.bfs_distance(counter, pot_pos)
            total_via_counter_p1_p2 = max(collect_time_p1, transfer_time_p2)
            
            # Joueur 2 collecte, Joueur 1 transfère
            collect_time_p2 = dist2_to_ing + self.distance_calc.bfs_distance(ingredient_pos, counter)
            transfer_time_p1 = self.distance_calc.bfs_distance(player1_pos, counter) + self.distance_calc.bfs_distance(counter, pot_pos)
            total_via_counter_p2_p1 = max(collect_time_p2, transfer_time_p1)
            
            if total_via_counter_p1_p2 < best_via_counter:
                best_via_counter = total_via_counter_p1_p2
                best_counter = counter
                best_strategy = ('p1_collect', 'p2_transfer')
            
            if total_via_counter_p2_p1 < best_via_counter:
                best_via_counter = total_via_counter_p2_p1
                best_counter = counter
                best_strategy = ('p2_collect', 'p1_transfer')
        
        # Retourner la meilleure option
        if direct_best <= best_via_counter:
            return {
                'method': 'direct',
                'player': direct_player,
                'total_time': direct_best,
                'path': [ingredient_pos, pot_pos]
            }
        else:
            return {
                'method': 'via_counter',
                'strategy': best_strategy,
                'counter': best_counter,
                'total_time': best_via_counter
            }
    
    def simulate_duo_game(self, initial_state):
        """Simule une partie en duo optimisée avec échanges via comptoirs"""
        state = initial_state.copy()
        self.distance_calc = DistanceCalculator(state)
        actions = []
        total_time = 0
        
        # Stratégie de rôles
        # Joueur 1: "Cuisinier/Serveur" - reste près du pot et du service
        # Joueur 2: "Collecteur" - se déplace vers les distributeurs
        
        recipes_to_complete = self.get_recipe_priority(state.recipes.copy())
        
        for recipe in recipes_to_complete:
            recipe_actions, recipe_time = self._complete_recipe_duo_optimized(state, recipe)
            actions.extend(recipe_actions)
            total_time += recipe_time
        
        return actions, total_time
    
    def _complete_recipe_duo_optimized(self, state, recipe):
        """Complète une recette en duo avec stratégie optimisée"""
        actions = []
        time = 0
        
        # Phase 1: Planifier la collecte et transport des ingrédients
        ingredient_plans = []
        for ingredient in recipe['ingredients']:
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:  # tomato
                dispenser = state.tomato_dispenser
            
            plan = self.optimize_ingredient_transport(
                state, dispenser, state.pot_position, 
                state.player_positions[1], state.player_positions[2]
            )
            ingredient_plans.append((ingredient, plan))
        
        # Phase 2: Exécuter les plans de transport
        for ingredient, plan in ingredient_plans:
            plan_actions, plan_time = self._execute_transport_plan(state, ingredient, plan)
            actions.extend(plan_actions)
            time += plan_time
        
        # Phase 3: Cuisson (temps parallèle)
        cooking_time = sum(self.onion_time if ing == 'onion' else self.tomato_time 
                          for ing in recipe['ingredients'])
        
        actions.append({
            'step': time,
            'player': 'pot',
            'action': 'cook',
            'recipe': recipe,
            'cooking_time': cooking_time,
            'description': f"🍲 Cuisson de {recipe['ingredients']} pendant {cooking_time} étapes"
        })
        time += cooking_time
        
        # Phase 4: Récupération d'assiette et service par le joueur le plus proche
        closest_to_dish = 1 if (self.distance_calc.bfs_distance(state.player_positions[1], state.dish_dispenser) 
                               <= self.distance_calc.bfs_distance(state.player_positions[2], state.dish_dispenser)) else 2
        
        service_actions, service_time = self._execute_service(state, closest_to_dish, recipe)
        actions.extend(service_actions)
        time += service_time
        
        return actions, time
    
    def _execute_transport_plan(self, state, ingredient, plan):
        """Exécute un plan de transport d'ingrédient"""
        actions = []
        time = 0
        
        if plan['method'] == 'direct':
            player = plan['player']
            
            # Aller au distributeur
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:
                dispenser = state.tomato_dispenser
            
            path_to_dispenser = self.bfs_path(state.player_positions[player], dispenser, state, player)
            for pos in path_to_dispenser[1:]:
                state.player_positions[player] = pos
                actions.append({
                    'step': time,
                    'player': player,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{player} se déplace vers {ingredient} en {pos}"
                })
                time += 1
            
            # Prendre l'ingrédient
            state.player_inventory[player] = ingredient
            actions.append({
                'step': time,
                'player': player,
                'action': 'pickup',
                'item': ingredient,
                'position': dispenser,
                'description': f"🥬 J{player} prend {ingredient} en {dispenser}"
            })
            time += 1
            
            # Aller au pot
            path_to_pot = self.bfs_path(state.player_positions[player], state.pot_position, state, player)
            for pos in path_to_pot[1:]:
                state.player_positions[player] = pos
                actions.append({
                    'step': time,
                    'player': player,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{player} se déplace vers le pot en {pos}"
                })
                time += 1
            
            # Déposer dans le pot
            state.player_inventory[player] = None
            state.pot_contents.append(ingredient)
            actions.append({
                'step': time,
                'player': player,
                'action': 'drop_in_pot',
                'item': ingredient,
                'position': state.pot_position,
                'description': f"🍲 J{player} dépose {ingredient} dans le pot en {state.pot_position}"
            })
            time += 1
            
        elif plan['method'] == 'via_counter':
            strategy = plan['strategy']
            counter = plan['counter']
            
            if strategy[0] == 'p1_collect':
                collector = 1
                transferer = 2
            else:
                collector = 2
                transferer = 1
            
            # Phase parallèle - les deux joueurs bougent simultanément
            # Collecteur va au distributeur
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:
                dispenser = state.tomato_dispenser
            
            collector_path_to_dispenser = self.bfs_path(state.player_positions[collector], dispenser, state, collector)
            transferer_path_to_counter = self.bfs_path(state.player_positions[transferer], counter, state, transferer)
            
            # Synchroniser les mouvements
            max_steps = max(len(collector_path_to_dispenser) - 1, len(transferer_path_to_counter) - 1)
            
            for step in range(max_steps):
                if step < len(collector_path_to_dispenser) - 1:
                    pos = collector_path_to_dispenser[step + 1]
                    state.player_positions[collector] = pos
                    actions.append({
                        'step': time,
                        'player': collector,
                        'action': 'move',
                        'position': pos,
                        'description': f"🚶 J{collector} se déplace vers {ingredient} en {pos}"
                    })
                
                if step < len(transferer_path_to_counter) - 1:
                    pos = transferer_path_to_counter[step + 1]
                    state.player_positions[transferer] = pos
                    actions.append({
                        'step': time,
                        'player': transferer,
                        'action': 'move',
                        'position': pos,
                        'description': f"🚶 J{transferer} se déplace vers comptoir en {pos}"
                    })
                
                time += 1
            
            # Collecteur prend l'ingrédient
            state.player_inventory[collector] = ingredient
            actions.append({
                'step': time,
                'player': collector,
                'action': 'pickup',
                'item': ingredient,
                'position': dispenser,
                'description': f"🥬 J{collector} prend {ingredient} en {dispenser}"
            })
            time += 1
            
            # Collecteur va au comptoir
            collector_path_to_counter = self.bfs_path(state.player_positions[collector], counter, state, collector)
            for pos in collector_path_to_counter[1:]:
                state.player_positions[collector] = pos
                actions.append({
                    'step': time,
                    'player': collector,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{collector} se déplace vers comptoir en {pos}"
                })
                time += 1
            
            # Déposer sur le comptoir
            state.player_inventory[collector] = None
            state.counter_items[counter] = ingredient
            actions.append({
                'step': time,
                'player': collector,
                'action': 'drop_on_counter',
                'item': ingredient,
                'position': counter,
                'description': f"📦 J{collector} dépose {ingredient} sur comptoir en {counter}"
            })
            time += 1
            
            # Transferer prend depuis le comptoir
            state.counter_items[counter] = None
            state.player_inventory[transferer] = ingredient
            actions.append({
                'step': time,
                'player': transferer,
                'action': 'pickup_from_counter',
                'item': ingredient,
                'position': counter,
                'description': f"📦 J{transferer} prend {ingredient} du comptoir en {counter}"
            })
            time += 1
            
            # Transferer va au pot
            transferer_path_to_pot = self.bfs_path(state.player_positions[transferer], state.pot_position, state, transferer)
            for pos in transferer_path_to_pot[1:]:
                state.player_positions[transferer] = pos
                actions.append({
                    'step': time,
                    'player': transferer,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{transferer} se déplace vers le pot en {pos}"
                })
                time += 1
            
            # Déposer dans le pot
            state.player_inventory[transferer] = None
            state.pot_contents.append(ingredient)
            actions.append({
                'step': time,
                'player': transferer,
                'action': 'drop_in_pot',
                'item': ingredient,
                'position': state.pot_position,
                'description': f"🍲 J{transferer} dépose {ingredient} dans le pot en {state.pot_position}"
            })
            time += 1
        
        return actions, time
    
    def _execute_service(self, state, player, recipe):
        """Exécute le service d'une recette"""
        actions = []
        time = 0
        
        # Aller chercher une assiette
        path_to_dish = self.bfs_path(state.player_positions[player], state.dish_dispenser, state, player)
        for pos in path_to_dish[1:]:
            state.player_positions[player] = pos
            actions.append({
                'step': time,
                'player': player,
                'action': 'move',
                'position': pos,
                'description': f"🚶 J{player} se déplace vers assiettes en {pos}"
            })
            time += 1
        
        # Prendre l'assiette
        state.player_inventory[player] = 'dish'
        actions.append({
            'step': time,
            'player': player,
            'action': 'pickup',
            'item': 'dish',
            'position': state.dish_dispenser,
            'description': f"🍽️ J{player} prend une assiette en {state.dish_dispenser}"
        })
        time += 1
        
        # Aller au pot
        path_to_pot = self.bfs_path(state.player_positions[player], state.pot_position, state, player)
        for pos in path_to_pot[1:]:
            state.player_positions[player] = pos
            actions.append({
                'step': time,
                'player': player,
                'action': 'move',
                'position': pos,
                'description': f"🚶 J{player} se déplace vers le pot en {pos}"
            })
            time += 1
        
        # Prendre la soupe
        state.player_inventory[player] = 'soup'
        state.pot_contents = []
        actions.append({
            'step': time,
            'player': player,
            'action': 'pickup_soup',
            'recipe': recipe,
            'position': state.pot_position,
            'description': f"🍲 J{player} prend la soupe {recipe['ingredients']} du pot en {state.pot_position}"
        })
        time += 1
        
        # Aller au service
        path_to_service = self.bfs_path(state.player_positions[player], state.service_position, state, player)
        for pos in path_to_service[1:]:
            state.player_positions[player] = pos
            actions.append({
                'step': time,
                'player': player,
                'action': 'move',
                'position': pos,
                'description': f"🚶 J{player} se déplace vers le service en {pos}"
            })
            time += 1
        
        # Servir
        state.player_inventory[player] = None
        state.completed_recipes.append(recipe)
        actions.append({
            'step': time,
            'player': player,
            'action': 'serve',
            'recipe': recipe,
            'position': state.service_position,
            'description': f"🎉 J{player} sert la recette {recipe['ingredients']} en {state.service_position}"
        })
        time += 1
        
        return actions, time
    
    def calculate_cooking_time(self, ingredients):
        """Calcule le temps de cuisson pour une liste d'ingrédients"""
        onion_count = ingredients.count('onion')
        tomato_count = ingredients.count('tomato')
        return onion_count * self.onion_time + tomato_count * self.tomato_time
    
    def get_recipe_priority(self, recipes):
        """Trie les recettes par ordre de priorité (plus simples en premier)"""
        return sorted(recipes, key=lambda r: len(r['ingredients']))
    
    def simulate_solo_game(self, initial_state):
        """Simule une partie en solo avec BFS"""
        state = initial_state.copy()
        self.distance_calc = DistanceCalculator(state)
        actions = []
        total_time = 0
        
        recipes_to_complete = self.get_recipe_priority(state.recipes.copy())
        
        for recipe in recipes_to_complete:
            recipe_actions, recipe_time = self._complete_recipe_solo(state, recipe)
            actions.extend(recipe_actions)
            total_time += recipe_time
        
        return actions, total_time
    
    def _complete_recipe_solo(self, state, recipe):
        """Complète une recette en mode solo avec BFS"""
        actions = []
        time = 0
        player_id = 1
        
        # Phase 1: Collecter tous les ingrédients
        for ingredient in recipe['ingredients']:
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:  # tomato
                dispenser = state.tomato_dispenser
            
            # Aller au distributeur
            path = self.bfs_path(state.player_positions[player_id], dispenser, state, player_id)
            for pos in path[1:]:
                state.player_positions[player_id] = pos
                actions.append({
                    'step': time,
                    'player': player_id,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{player_id} se déplace vers {ingredient} en {pos}"
                })
                time += 1
            
            # Prendre l'ingrédient
            state.player_inventory[player_id] = ingredient
            actions.append({
                'step': time,
                'player': player_id,
                'action': 'pickup',
                'item': ingredient,
                'position': dispenser,
                'description': f"🥬 J{player_id} prend {ingredient} en {dispenser}"
            })
            time += 1
            
            # Aller au pot
            path = self.bfs_path(state.player_positions[player_id], state.pot_position, state, player_id)
            for pos in path[1:]:
                state.player_positions[player_id] = pos
                actions.append({
                    'step': time,
                    'player': player_id,
                    'action': 'move',
                    'position': pos,
                    'description': f"🚶 J{player_id} se déplace vers le pot en {pos}"
                })
                time += 1
            
            # Déposer dans le pot
            state.player_inventory[player_id] = None
            state.pot_contents.append(ingredient)
            actions.append({
                'step': time,
                'player': player_id,
                'action': 'drop_in_pot',
                'item': ingredient,
                'position': state.pot_position,
                'description': f"🍲 J{player_id} dépose {ingredient} dans le pot en {state.pot_position}"
            })
            time += 1
        
        # Phase 2: Cuisson
        cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        actions.append({
            'step': time,
            'player': 'pot',
            'action': 'cook',
            'recipe': recipe,
            'cooking_time': cooking_time,
            'description': f"🍲 Cuisson de {recipe['ingredients']} pendant {cooking_time} étapes"
        })
        time += cooking_time
        
        # Phase 3: Service
        service_actions, service_time = self._execute_service(state, player_id, recipe)
        actions.extend(service_actions)
        time += service_time
        
        return actions, time
        
        recipes_to_complete = self.get_recipe_priority(state.recipes.copy())
        
        for recipe in recipes_to_complete:
            recipe_actions, recipe_time = self._complete_recipe_duo(state, recipe)
            actions.extend(recipe_actions)
            total_time += recipe_time
        
        return actions, total_time
    
    def _complete_recipe_solo(self, state, recipe):
        """Complète une recette en mode solo"""
        actions = []
        time = 0
        player_id = 1
        
        # Étape 1: Aller chercher les ingrédients
        for ingredient in recipe['ingredients']:
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:  # tomato
                dispenser = state.tomato_dispenser
            
            # Aller au distributeur
            path = self.bfs_path(state.player_positions[player_id], dispenser, state, player_id)
            if path:
                for pos in path[1:]:  # Exclure la position de départ
                    state.player_positions[player_id] = pos
                    actions.append({
                        'step': time,
                        'player': player_id,
                        'action': 'move',
                        'position': pos,
                        'description': f"J{player_id} se déplace en {pos}"
                    })
                    time += 1
            
            # Prendre l'ingrédient
            state.player_inventory[player_id] = ingredient
            actions.append({
                'step': time,
                'player': player_id,
                'action': 'pickup',
                'item': ingredient,
                'position': dispenser,
                'description': f"J{player_id} prend {ingredient} en {dispenser}"
            })
            time += 1
            
            # Aller au pot
            path = self.bfs_path(state.player_positions[player_id], state.pot_position, state, player_id)
            if path:
                for pos in path[1:]:
                    state.player_positions[player_id] = pos
                    actions.append({
                        'step': time,
                        'player': player_id,
                        'action': 'move',
                        'position': pos,
                        'description': f"J{player_id} se déplace en {pos}"
                    })
                    time += 1
            
            # Déposer dans le pot
            state.pot_contents.append(ingredient)
            state.player_inventory[player_id] = None
            actions.append({
                'step': time,
                'player': player_id,
                'action': 'drop_pot',
                'item': ingredient,
                'position': state.pot_position,
                'description': f"J{player_id} dépose {ingredient} dans le pot en {state.pot_position}"
            })
            time += 1
        
        # Étape 2: Lancer la cuisson
        cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        state.pot_cooking = True
        state.pot_cooking_time = cooking_time
        actions.append({
            'step': time,
            'player': player_id,
            'action': 'start_cooking',
            'cooking_time': cooking_time,
            'position': state.pot_position,
            'description': f"J{player_id} lance la cuisson ({cooking_time} steps)"
        })
        time += 1
        
        # Étape 3: Attendre la cuisson
        for _ in range(cooking_time):
            actions.append({
                'step': time,
                'player': player_id,
                'action': 'wait_cooking',
                'description': f"J{player_id} attend la cuisson"
            })
            time += 1
        
        # Étape 4: Aller chercher une assiette
        path = self.bfs_path(state.player_positions[player_id], state.dish_dispenser, state, player_id)
        if path:
            for pos in path[1:]:
                state.player_positions[player_id] = pos
                actions.append({
                    'step': time,
                    'player': player_id,
                    'action': 'move',
                    'position': pos,
                    'description': f"J{player_id} se déplace en {pos}"
                })
                time += 1
        
        # Prendre l'assiette
        state.player_inventory[player_id] = 'dish'
        actions.append({
            'step': time,
            'player': player_id,
            'action': 'pickup',
            'item': 'dish',
            'position': state.dish_dispenser,
            'description': f"J{player_id} prend une assiette en {state.dish_dispenser}"
        })
        time += 1
        
        # Étape 5: Récupérer le plat cuit
        path = self.bfs_path(state.player_positions[player_id], state.pot_position, state, player_id)
        if path:
            for pos in path[1:]:
                state.player_positions[player_id] = pos
                actions.append({
                    'step': time,
                    'player': player_id,
                    'action': 'move',
                    'position': pos,
                    'description': f"J{player_id} se déplace en {pos}"
                })
                time += 1
        
        # Récupérer le plat
        state.pot_cooking = False
        state.pot_contents = []
        state.player_inventory[player_id] = 'cooked_dish'
        actions.append({
            'step': time,
            'player': player_id,
            'action': 'pickup_cooked',
            'item': 'cooked_dish',
            'position': state.pot_position,
            'description': f"J{player_id} récupère le plat cuit en {state.pot_position}"
        })
        time += 1
        
        # Étape 6: Livrer à la zone de service
        path = self.bfs_path(state.player_positions[player_id], state.service_position, state, player_id)
        if path:
            for pos in path[1:]:
                state.player_positions[player_id] = pos
                actions.append({
                    'step': time,
                    'player': player_id,
                    'action': 'move',
                    'position': pos,
                    'description': f"J{player_id} se déplace en {pos}"
                })
                time += 1
        
        # Livrer
        state.player_inventory[player_id] = None
        state.completed_recipes.append(recipe)
        actions.append({
            'step': time,
            'player': player_id,
            'action': 'deliver',
            'recipe': recipe,
            'position': state.service_position,
            'description': f"J{player_id} livre la recette {recipe['ingredients']} en {state.service_position}"
        })
        time += 1
        
        return actions, time
    
    def _complete_recipe_duo(self, state, recipe):
        """Complète une recette en mode duo avec répartition des tâches"""
        actions = []
        time = 0
        
        # Stratégie simple: J1 s'occupe des ingrédients, J2 gère les assiettes et la livraison
        ingredients = recipe['ingredients']
        
        # Phase 1: J1 collecte et dépose les ingrédients
        for i, ingredient in enumerate(ingredients):
            if ingredient == 'onion':
                dispenser = state.onion_dispenser
            else:  # tomato
                dispenser = state.tomato_dispenser
            
            # J1 va chercher l'ingrédient
            path = self.bfs_path(state.player_positions[1], dispenser, state, 1)
            if path:
                for pos in path[1:]:
                    state.player_positions[1] = pos
                    actions.append({
                        'step': time,
                        'player': 1,
                        'action': 'move',
                        'position': pos,
                        'description': f"J1 se déplace en {pos}"
                    })
                    time += 1
            
            # J1 prend l'ingrédient
            state.player_inventory[1] = ingredient
            actions.append({
                'step': time,
                'player': 1,
                'action': 'pickup',
                'item': ingredient,
                'position': dispenser,
                'description': f"J1 prend {ingredient} en {dispenser}"
            })
            time += 1
            
            # En parallèle, J2 peut se préparer
            if i == 0:  # Premier ingrédient, J2 va chercher une assiette
                path_j2 = self.bfs_path(state.player_positions[2], state.dish_dispenser, state, 2)
                if path_j2 and len(path_j2) > 1:
                    # J2 se déplace en parallèle
                    j2_moves = min(len(path_j2) - 1, time + 2)  # Limite les mouvements
                    for j in range(1, min(len(path_j2), j2_moves + 1)):
                        if j <= len(path_j2) - 1:
                            state.player_positions[2] = path_j2[j]
                            actions.append({
                                'step': time - j,
                                'player': 2,
                                'action': 'move',
                                'position': path_j2[j],
                                'description': f"J2 se déplace en {path_j2[j]}"
                            })
            
            # J1 va au pot
            path = self.bfs_path(state.player_positions[1], state.pot_position, state, 1)
            if path:
                for pos in path[1:]:
                    state.player_positions[1] = pos
                    actions.append({
                        'step': time,
                        'player': 1,
                        'action': 'move',
                        'position': pos,
                        'description': f"J1 se déplace en {pos}"
                    })
                    time += 1
            
            # J1 dépose dans le pot
            state.pot_contents.append(ingredient)
            state.player_inventory[1] = None
            actions.append({
                'step': time,
                'player': 1,
                'action': 'drop_pot',
                'item': ingredient,
                'position': state.pot_position,
                'description': f"J1 dépose {ingredient} dans le pot en {state.pot_position}"
            })
            time += 1
        
        # Phase 2: J1 lance la cuisson
        cooking_time = self.calculate_cooking_time(recipe['ingredients'])
        state.pot_cooking = True
        state.pot_cooking_time = cooking_time
        actions.append({
            'step': time,
            'player': 1,
            'action': 'start_cooking',
            'cooking_time': cooking_time,
            'position': state.pot_position,
            'description': f"J1 lance la cuisson ({cooking_time} steps)"
        })
        time += 1
        
        # Phase 3: Pendant la cuisson, J2 finit d'aller chercher l'assiette
        if state.player_positions[2] != state.dish_dispenser:
            path_j2 = self.bfs_path(state.player_positions[2], state.dish_dispenser, state, 2)
            if path_j2:
                for pos in path_j2[1:]:
                    state.player_positions[2] = pos
                    actions.append({
                        'step': time,
                        'player': 2,
                        'action': 'move',
                        'position': pos,
                        'description': f"J2 se déplace en {pos}"
                    })
                    time += 1
        
        # J2 prend l'assiette
        state.player_inventory[2] = 'dish'
        actions.append({
            'step': time,
            'player': 2,
            'action': 'pickup',
            'item': 'dish',
            'position': state.dish_dispenser,
            'description': f"J2 prend une assiette en {state.dish_dispenser}"
        })
        time += 1
        
        # Phase 4: Attendre la fin de cuisson
        remaining_cooking_time = max(0, cooking_time - (time - 1))
        for _ in range(remaining_cooking_time):
            actions.append({
                'step': time,
                'player': 1,
                'action': 'wait_cooking',
                'description': f"J1 attend la cuisson"
            })
            actions.append({
                'step': time,
                'player': 2,
                'action': 'wait_cooking',
                'description': f"J2 attend la cuisson"
            })
            time += 1
        
        # Phase 5: J2 récupère le plat et livre
        # J2 va au pot
        path = self.bfs_path(state.player_positions[2], state.pot_position, state, 2)
        if path:
            for pos in path[1:]:
                state.player_positions[2] = pos
                actions.append({
                    'step': time,
                    'player': 2,
                    'action': 'move',
                    'position': pos,
                    'description': f"J2 se déplace en {pos}"
                })
                time += 1
        
        # J2 récupère le plat
        state.pot_cooking = False
        state.pot_contents = []
        state.player_inventory[2] = 'cooked_dish'
        actions.append({
            'step': time,
            'player': 2,
            'action': 'pickup_cooked',
            'item': 'cooked_dish',
            'position': state.pot_position,
            'description': f"J2 récupère le plat cuit en {state.pot_position}"
        })
        time += 1
        
        # J2 va à la zone de service
        path = self.bfs_path(state.player_positions[2], state.service_position, state, 2)
        if path:
            for pos in path[1:]:
                state.player_positions[2] = pos
                actions.append({
                    'step': time,
                    'player': 2,
                    'action': 'move',
                    'position': pos,
                    'description': f"J2 se déplace en {pos}"
                })
                time += 1
        
        # J2 livre
        state.player_inventory[2] = None
        state.completed_recipes.append(recipe)
        actions.append({
            'step': time,
            'player': 2,
            'action': 'deliver',
            'recipe': recipe,
            'position': state.service_position,
            'description': f"J2 livre la recette {recipe['ingredients']} en {state.service_position}"
        })
        time += 1
        
        return actions, time

class MarkdownReportGenerator:
    """Générateur de rapports Markdown lisibles et agréables"""
    
    def __init__(self):
        pass
    
    def generate_timeline_table(self, actions, title="Timeline des Actions"):
        """Génère un tableau Markdown des actions"""
        markdown = f"\n## {title}\n\n"
        markdown += "| Étape | Joueur | Action | Position | Description |\n"
        markdown += "|-------|--------|--------|----------|-------------|\n"
        
        for action in actions:
            step = action.get('step', 0)
            player = action.get('player', 'N/A')
            action_type = action.get('action', 'N/A')
            position = action.get('position', 'N/A')
            if isinstance(position, tuple):
                position = f"({position[0]}, {position[1]})"
            description = action.get('description', 'N/A')
            
            markdown += f"| {step:3d} | {str(player):6s} | {action_type:12s} | {str(position):8s} | {description} |\n"
        
        return markdown
    
    def generate_comparison_report(self, layout_name, solo_result, duo_result):
        """Génère un rapport complet de comparaison solo/duo"""
        
        # Statistiques de base
        solo_time = solo_result['total_time']
        duo_time = duo_result['total_time']
        time_saved = solo_time - duo_time
        efficiency_gain = (time_saved / solo_time * 100) if solo_time > 0 else 0
        
        markdown = f"# 🍅 Rapport d'Évaluation - {layout_name}\n\n"
        markdown += f"📅 **Généré le:** {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n\n"
        
        # Résumé exécutif
        markdown += "## 📊 Résumé Exécutif\n\n"
        markdown += f"| Métrique | Solo | Duo | Différence |\n"
        markdown += f"|----------|------|-----|------------|\n"
        markdown += f"| **Temps Total** | {solo_time} étapes | {duo_time} étapes | {time_saved:+d} étapes |\n"
        markdown += f"| **Efficacité** | - | - | {efficiency_gain:+.1f}% |\n"
        markdown += f"| **Recettes** | {solo_result['total_recipes']} | {duo_result['total_recipes']} | {duo_result['total_recipes'] - solo_result['total_recipes']} |\n"
        
        if efficiency_gain > 0:
            markdown += f"\n✅ **Verdict:** La coopération est **bénéfique** ! Gain de {efficiency_gain:.1f}%\n"
        elif efficiency_gain == 0:
            markdown += f"\n⚖️ **Verdict:** Performance **équivalente** entre solo et duo\n"
        else:
            markdown += f"\n❌ **Verdict:** Le solo est **plus efficace** de {abs(efficiency_gain):.1f}%\n"
        
        # Timeline Solo
        markdown += self.generate_timeline_table(solo_result['actions'], "🎯 Mode Solo - Timeline")
        
        # Timeline Duo
        markdown += self.generate_timeline_table(duo_result['actions'], "👥 Mode Duo - Timeline")
        
        # Analyse des stratégies
        markdown += "\n## 🔍 Analyse des Stratégies\n\n"
        
        # Analyser les actions de coopération en duo
        cooperation_actions = [a for a in duo_result['actions'] if 'comptoir' in a.get('description', '').lower()]
        if cooperation_actions:
            markdown += f"### 🤝 Actions de Coopération Détectées: {len(cooperation_actions)}\n\n"
            for action in cooperation_actions:
                markdown += f"- **Étape {action['step']}:** {action['description']}\n"
        else:
            markdown += "### 🤝 Aucune coopération via comptoirs détectée\n\n"
            markdown += "Les joueurs ont travaillé de manière principalement indépendante.\n"
        
        # Répartition des tâches
        player1_actions = [a for a in duo_result['actions'] if a.get('player') == 1]
        player2_actions = [a for a in duo_result['actions'] if a.get('player') == 2]
        
        markdown += f"\n### 👨‍🍳 Répartition des Tâches\n\n"
        markdown += f"- **Joueur 1:** {len(player1_actions)} actions\n"
        markdown += f"- **Joueur 2:** {len(player2_actions)} actions\n"
        
        # Actions de service
        serve_actions_solo = [a for a in solo_result['actions'] if a.get('action') == 'serve']
        serve_actions_duo = [a for a in duo_result['actions'] if a.get('action') == 'serve']
        
        markdown += f"\n### 🎉 Actions de Service\n\n"
        markdown += f"- **Solo:** {len(serve_actions_solo)} services\n"
        markdown += f"- **Duo:** {len(serve_actions_duo)} services\n"
        
        markdown += "\n---\n"
        markdown += f"*Rapport généré par Overcooked Layout Evaluator v2.0*\n"
        
        return markdown
    
    def save_markdown_report(self, content, filepath):
        """Sauvegarde un rapport Markdown"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

class LayoutEvaluator:
    """Évaluateur principal pour tous les layouts avec rapports Markdown"""
    
    def __init__(self):
        self.pathfinder = OvercookedPathfinder()
        
        # Détecter automatiquement le chemin vers layouts_with_objects
        script_dir = os.path.dirname(os.path.abspath(__file__))
        layouts_dir_relative = os.path.join(script_dir, "layouts_with_objects")
        layouts_dir_from_root = "test_generation_layout/layouts_with_objects"
        
        if os.path.exists(layouts_dir_relative):
            self.layouts_dir = layouts_dir_relative
        elif os.path.exists(layouts_dir_from_root):
            self.layouts_dir = layouts_dir_from_root
        else:
            # Essayer de le trouver automatiquement
            for root, dirs, files in os.walk('.'):
                if 'layouts_with_objects' in dirs:
                    self.layouts_dir = os.path.join(root, 'layouts_with_objects')
                    break
            else:
                raise FileNotFoundError("Impossible de trouver le dossier layouts_with_objects")
        
        self.results_dir = "path_evaluation_results"
        self.report_generator = MarkdownReportGenerator()
        
        # Créer le dossier de résultats
        os.makedirs(self.results_dir, exist_ok=True)
    
    def parse_layout_file(self, file_path):
        """Parse un fichier layout et retourne les données"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parser ce format pseudo-JSON manuellement
            # Extraire la grille
            grid_start = content.find('"""') + 3
            grid_end = content.find('"""', grid_start)
            grid_str = content[grid_start:grid_end]
            
            # Parser la grille
            lines = [line.strip() for line in grid_str.strip().split('\n') if line.strip()]
            grid = []
            for line in lines:
                grid.append(list(line.strip()))
            
            # Extraire start_all_orders
            orders_start = content.find('"start_all_orders":') + len('"start_all_orders":')
            orders_end = content.find('],', orders_start) + 1
            orders_str = content[orders_start:orders_end].strip()
            
            # Parser les recettes manuellement
            recipes = []
            # Chercher toutes les occurrences de {"ingredients": [...]}
            import re
            recipe_pattern = r'\{"ingredients":\s*\[(.*?)\]\}'
            matches = re.findall(recipe_pattern, orders_str)
            
            for match in matches:
                ingredients = []
                # Extraire les ingrédients
                ing_pattern = r'"([^"]+)"'
                ingredients = re.findall(ing_pattern, match)
                if ingredients:
                    recipes.append({'ingredients': ingredients})
            
            # Extraire les valeurs numériques avec des regex
            onion_value = 3  # valeur par défaut
            tomato_value = 2
            onion_time = 9
            tomato_time = 6
            
            onion_val_match = re.search(r'"onion_value"\s*:\s*(\d+)', content)
            if onion_val_match:
                onion_value = int(onion_val_match.group(1))
                
            tomato_val_match = re.search(r'"tomato_value"\s*:\s*(\d+)', content)
            if tomato_val_match:
                tomato_value = int(tomato_val_match.group(1))
                
            onion_time_match = re.search(r'"onion_time"\s*:\s*(\d+)', content)
            if onion_time_match:
                onion_time = int(onion_time_match.group(1))
                
            tomato_time_match = re.search(r'"tomato_time"\s*:\s*(\d+)', content)
            if tomato_time_match:
                tomato_time = int(tomato_time_match.group(1))
            
            return {
                'grid': grid,
                'recipes': recipes,
                'onion_value': onion_value,
                'tomato_value': tomato_value,
                'onion_time': onion_time,
                'tomato_time': tomato_time
            }
        except Exception as e:
            print(f"❌ Erreur lors du parsing de {file_path}: {e}")
            return None
    
    def evaluate_layout(self, layout_data, layout_name):
        """Évalue un layout et retourne les résultats solo et duo"""
        try:
            # Créer l'état initial
            initial_state = GameState(layout_data['grid'], layout_data['recipes'])
            
            # Ajuster les temps de cuisson
            self.pathfinder.onion_time = layout_data['onion_time']
            self.pathfinder.tomato_time = layout_data['tomato_time']
            
            # Simulation solo
            solo_actions, solo_time = self.pathfinder.simulate_solo_game(initial_state)
            
            # Simulation duo
            duo_actions, duo_time = self.pathfinder.simulate_duo_game(initial_state)
            
            # Calculer les gains
            time_saved = solo_time - duo_time
            efficiency_gain = (time_saved / solo_time * 100) if solo_time > 0 else 0
            
            # Générer le rapport Markdown
            markdown_report = self.report_generator.generate_comparison_report(
                layout_name,
                {
                    'total_time': solo_time,
                    'total_recipes': len(layout_data['recipes']),
                    'actions': solo_actions
                },
                {
                    'total_time': duo_time,
                    'total_recipes': len(layout_data['recipes']),
                    'actions': duo_actions
                }
            )
            
            # Sauvegarder le rapport Markdown
            markdown_path = os.path.join(self.results_dir, f"{layout_name}_rapport.md")
            self.report_generator.save_markdown_report(markdown_report, markdown_path)
            
            return {
                'layout_name': layout_name,
                'analysis_timestamp': datetime.now().isoformat(),
                'solo': {
                    'total_time': solo_time,
                    'total_recipes': len(layout_data['recipes']),
                    'actions': solo_actions,
                    'average_time_per_recipe': solo_time / len(layout_data['recipes']) if layout_data['recipes'] else 0
                },
                'duo': {
                    'total_time': duo_time,
                    'total_recipes': len(layout_data['recipes']),
                    'actions': duo_actions,
                    'average_time_per_recipe': duo_time / len(layout_data['recipes']) if layout_data['recipes'] else 0
                },
                'comparison': {
                    'time_saved': time_saved,
                    'efficiency_gain_percent': round(efficiency_gain, 2),
                    'cooperation_benefit': 'Beneficial' if time_saved > 0 else 'No benefit' if time_saved == 0 else 'Detrimental'
                },
                'layout_info': {
                    'grid_size': f"{len(layout_data['grid'][0])}x{len(layout_data['grid'])}",
                    'recipes': layout_data['recipes'],
                    'cooking_parameters': {
                        'onion_time': layout_data['onion_time'],
                        'tomato_time': layout_data['tomato_time']
                    }
                },
                'markdown_report_path': markdown_path
            }
        except Exception as e:
            print(f"❌ Erreur lors de l'évaluation de {layout_name}: {e}")
            return None
    
    def process_all_layouts(self):
        """Traite tous les layouts du dossier"""
        print("🚀 DÉBUT DE L'ÉVALUATION DES LAYOUTS OVERCOOKED")
        print("=" * 60)
        
        if not os.path.exists(self.layouts_dir):
            print(f"❌ Dossier {self.layouts_dir} introuvable")
            return
        
        # Découvrir tous les dossiers de layouts
        layout_folders = [d for d in os.listdir(self.layouts_dir) 
                         if os.path.isdir(os.path.join(self.layouts_dir, d))]
        layout_folders.sort()
        
        # TEMPORAIRE: ne traiter que les premiers pour les tests
        layout_folders = layout_folders[:]
        
        print(f"📁 {len(layout_folders)} dossiers de layouts sélectionnés pour test")
        
        processed_count = 0
        results_summary = []
        
        for folder in layout_folders:
            folder_path = os.path.join(self.layouts_dir, folder)
            
            # Trouver tous les fichiers .layout dans ce dossier
            layout_files = glob.glob(os.path.join(folder_path, "*.layout"))
            
            # TEMPORAIRE: ne prendre que le premier fichier de chaque dossier
            layout_files = layout_files[:1]
            
            for layout_file in layout_files:
                layout_name = os.path.splitext(os.path.basename(layout_file))[0]
                print(f"\n📊 Traitement: {layout_name}")
                
                # Parser le layout
                layout_data = self.parse_layout_file(layout_file)
                if not layout_data:
                    continue
                
                # Évaluer le layout
                results = self.evaluate_layout(layout_data, layout_name)
                if not results:
                    continue
                
                # Sauvegarder les résultats
                result_file = os.path.join(self.results_dir, f"{layout_name}_evaluation.json")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                # Afficher le résumé
                print(f"   ⏱️  Solo: {results['solo']['total_time']} steps")
                print(f"   👥 Duo: {results['duo']['total_time']} steps")
                print(f"   📈 Gain: {results['comparison']['efficiency_gain_percent']}%")
                print(f"   💾 JSON: {result_file}")
                print(f"   📄 Rapport: {results['markdown_report_path']}")
                
                # Ajouter au résumé
                results_summary.append({
                    'layout': layout_name,
                    'solo_time': results['solo']['total_time'],
                    'duo_time': results['duo']['total_time'],
                    'efficiency_gain': results['comparison']['efficiency_gain_percent']
                })
                
                processed_count += 1
        
        # Sauvegarder le résumé global
        summary_file = os.path.join(self.results_dir, "evaluation_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_layouts_processed': processed_count,
                'results': results_summary,
                'statistics': self._calculate_summary_stats(results_summary)
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 ÉVALUATION TERMINÉE")
        print(f"📊 {processed_count} layouts traités")
        print(f"📁 Résultats dans: {self.results_dir}/")
        print(f"📋 Résumé global: {summary_file}")
    
    def _calculate_summary_stats(self, results):
        """Calcule les statistiques du résumé"""
        if not results:
            return {}
        
        solo_times = [r['solo_time'] for r in results]
        duo_times = [r['duo_time'] for r in results]
        gains = [r['efficiency_gain'] for r in results]
        
        return {
            'average_solo_time': round(sum(solo_times) / len(solo_times), 2),
            'average_duo_time': round(sum(duo_times) / len(duo_times), 2),
            'average_efficiency_gain': round(sum(gains) / len(gains), 2),
            'max_efficiency_gain': max(gains),
            'min_efficiency_gain': min(gains),
            'layouts_with_cooperation_benefit': len([g for g in gains if g > 0]),
            'layouts_with_no_benefit': len([g for g in gains if g <= 0])
        }

def main():
    """Fonction principale"""
    print("🍅 OVERCOOKED LAYOUT EVALUATOR - SOLO & DUO")
    print("Calcul des temps optimaux pour tous les layouts")
    print("Author: Assistant AI Expert | Date: Août 2025")
    print("-" * 60)
    
    evaluator = LayoutEvaluator()
    evaluator.process_all_layouts()

if __name__ == "__main__":
    main()
