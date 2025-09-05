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

# Ajouter les répertoires nécessaires au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from layout_compression import LayoutDecompressor

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

@dataclass
class EvaluationMetrics:
    """Métriques d'évaluation pour une combinaison layout+recettes"""
    layout_id: str
    recipe_group_id: int
    solo_steps: int
    duo_steps: int
    exchanges_count: int
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
            decompressed = LayoutDecompressor.decompress_layout(layout_data)
            self.layout = decompressed["grid"]
            self.object_positions = decompressed.get("objects", {})
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
                        self.player_positions[1] = positions[0]
                        self.player_inventory[1] = None
                elif obj_type == '2':
                    if isinstance(positions, list) and len(positions) > 0:
                        self.player_positions[2] = positions[0]
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

class FastDistanceCalculator:
    """Calculateur de distances optimisé pour évaluation massive"""
    
    def __init__(self, game_state: OptimizedGameState):
        self.state = game_state
        self.distances = {}
        self._precompute_critical_distances()
    
    def bfs_distance(self, start: Tuple[int, int], goal: Tuple[int, int]) -> int:
        """Calcule la distance BFS entre deux points"""
        if start == goal:
            return 0
        
        # Vérifier le cache
        cache_key = (start, goal)
        if cache_key in self.distances:
            return self.distances[cache_key]
        
        queue = deque([(start, 0)])
        visited = {start}
        
        while queue:
            current, dist = queue.popleft()
            
            for neighbor in self.state.get_neighbors(current):
                if neighbor in visited:
                    continue
                
                if neighbor == goal:
                    distance = dist + 1
                    self.distances[cache_key] = distance
                    self.distances[(goal, start)] = distance  # Symétrique
                    return distance
                
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
        
        distance = float('inf')
        self.distances[cache_key] = distance
        return distance
    
    def _precompute_critical_distances(self):
        """Pré-calcule les distances critiques pour optimiser les évaluations"""
        critical_points = {}
        
        # Ajouter tous les points d'intérêt
        if self.state.player_positions:
            critical_points.update({f'player_{k}': v for k, v in self.state.player_positions.items()})
        if self.state.pot_position:
            critical_points['pot'] = self.state.pot_position
        if self.state.service_position:
            critical_points['service'] = self.state.service_position
        if self.state.onion_dispenser:
            critical_points['onion'] = self.state.onion_dispenser
        if self.state.tomato_dispenser:
            critical_points['tomato'] = self.state.tomato_dispenser
        if self.state.dish_dispenser:
            critical_points['dish'] = self.state.dish_dispenser
        
        # Ajouter les comptoirs
        for i, counter in enumerate(self.state.counters):
            critical_points[f'counter_{i}'] = counter
        
        # Pré-calculer toutes les distances entre points critiques
        points_list = list(critical_points.items())
        for i, (name1, pos1) in enumerate(points_list):
            for name2, pos2 in points_list[i:]:
                self.bfs_distance(pos1, pos2)

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
        return list(self.layouts_dir.glob("layouts_batch_*.gz"))
    
    def calculate_cooking_time(self, ingredients: List[str]) -> int:
        """Calcule le temps de cuisson total"""
        onion_count = ingredients.count('onion')
        tomato_count = ingredients.count('tomato')
        return onion_count * self.onion_time + tomato_count * self.tomato_time
    
    def bfs_path(self, start: Tuple[int, int], goal: Tuple[int, int], 
                 state: OptimizedGameState, excluding_player: Optional[int] = None) -> List[Tuple[int, int]]:
        """Trouve le chemin BFS entre deux points"""
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
    
    def evaluate_solo_mode(self, state: OptimizedGameState, recipes: List[Dict]) -> Tuple[int, List[Dict]]:
        """Évalue le mode solo pour un ensemble de recettes"""
        actions = []
        total_steps = 0
        player_id = 1
        
        # Calculateur de distances
        distance_calc = FastDistanceCalculator(state)
        
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
                
                # Aller au distributeur
                path = self.bfs_path(state.player_positions[player_id], dispenser, state, player_id)
                recipe_steps += len(path) - 1
                
                if path:
                    state.player_positions[player_id] = dispenser
                
                # Prendre l'ingrédient
                recipe_steps += 1
                
                # Aller au pot
                path = self.bfs_path(state.player_positions[player_id], state.pot_position, state, player_id)
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
            path = self.bfs_path(state.player_positions[player_id], state.dish_dispenser, state, player_id)
            recipe_steps += len(path) - 1
            if path:
                state.player_positions[player_id] = state.dish_dispenser
            recipe_steps += 1  # Prendre l'assiette
            
            # Retourner au pot
            path = self.bfs_path(state.player_positions[player_id], state.pot_position, state, player_id)
            recipe_steps += len(path) - 1
            if path:
                state.player_positions[player_id] = state.pot_position
            recipe_steps += 1  # Prendre la soupe
            
            # Aller au service
            path = self.bfs_path(state.player_positions[player_id], state.service_position, state, player_id)
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
    
    def evaluate_duo_mode(self, state: OptimizedGameState, recipes: List[Dict]) -> Tuple[int, List[Dict], int]:
        """Évalue le mode duo avec comptage des échanges"""
        actions = []
        total_steps = 0
        exchanges_count = 0
        
        # Calculateur de distances
        distance_calc = FastDistanceCalculator(state)
        
        for recipe in recipes:
            recipe_steps = 0
            recipe_exchanges = 0
            
            # Stratégie duo simple: J1 collecte, J2 s'occupe du service
            ingredients = recipe['ingredients']
            
            # Phase 1: Collection en parallèle
            collection_steps = 0
            for ingredient in ingredients:
                if ingredient == 'onion':
                    dispenser = state.onion_dispenser
                elif ingredient == 'tomato':
                    dispenser = state.tomato_dispenser
                else:
                    continue
                
                # J1 va chercher l'ingrédient
                path = self.bfs_path(state.player_positions[1], dispenser, state, 1)
                collection_steps = max(collection_steps, len(path) - 1 + 1)  # Move + pickup
                
                # J1 va au pot
                path = self.bfs_path(dispenser, state.pot_position, state, 1)
                collection_steps = max(collection_steps, collection_steps + len(path) - 1 + 1)  # Move + drop
                
                state.player_positions[1] = state.pot_position
                state.pot_contents.append(ingredient)
            
            # Phase 2: J2 prépare le service pendant la cuisson
            service_prep_steps = 0
            # J2 va chercher une assiette
            path = self.bfs_path(state.player_positions[2], state.dish_dispenser, state, 2)
            service_prep_steps = len(path) - 1 + 1  # Move + pickup
            state.player_positions[2] = state.dish_dispenser
            
            # Phase 3: Cuisson (temps parallèle)
            cooking_time = self.calculate_cooking_time(recipe['ingredients'])
            
            # Phase 4: Service coordonné
            service_steps = 0
            
            # J2 va au pot (si pas déjà fait)
            if state.player_positions[2] != state.pot_position:
                path = self.bfs_path(state.player_positions[2], state.pot_position, state, 2)
                service_steps += len(path) - 1
                state.player_positions[2] = state.pot_position
            
            service_steps += 1  # J2 prend la soupe
            
            # J2 va au service
            path = self.bfs_path(state.player_positions[2], state.service_position, state, 2)
            service_steps += len(path) - 1 + 1  # Move + serve
            state.player_positions[2] = state.service_position
            
            # Calcul du temps total de la recette (phases en parallèle)
            recipe_steps = max(collection_steps, service_prep_steps) + cooking_time + service_steps
            
            # Détection d'échanges via comptoirs (heuristique simple)
            # Si les joueurs doivent passer des objets, compter les échanges
            if len(state.counters) > 0 and len(ingredients) > 2:
                recipe_exchanges += 1  # Échange potentiel pour recettes complexes
            
            actions.append({
                'recipe': recipe,
                'steps': recipe_steps,
                'exchanges': recipe_exchanges,
                'phase_breakdown': {
                    'collection': collection_steps,
                    'cooking': cooking_time,
                    'service': service_steps
                }
            })
            
            total_steps += recipe_steps
            exchanges_count += recipe_exchanges
            state.completed_recipes.append(recipe)
            state.pot_contents = []
        
        return total_steps, actions, exchanges_count
    
    def evaluate_layout_recipe_combination(self, layout_data: Dict, recipe_group: Dict) -> EvaluationMetrics:
        """Évalue une combinaison layout + groupe de recettes"""
        start_time = time.time()
        
        # Créer l'état de jeu
        recipes = recipe_group["recipes"]
        state_solo = OptimizedGameState(layout_data, recipes)
        state_duo = OptimizedGameState(layout_data, recipes)
        
        # Génération des identifiants
        layout_id = layout_data.get("hash", f"layout_{id(layout_data)}")
        recipe_group_id = recipe_group["group_id"]
        
        # Hashes pour traçabilité
        grid_str = '\n'.join([''.join(row) for row in layout_data.get("grid", [])])
        layout_hash = hashlib.md5(grid_str.encode()).hexdigest()[:12]
        recipe_hash = hashlib.md5(json.dumps(recipes, sort_keys=True).encode()).hexdigest()[:12]
        
        try:
            # Évaluation solo
            solo_steps, solo_actions = self.evaluate_solo_mode(state_solo, recipes)
            
            # Évaluation duo
            duo_steps, duo_actions, exchanges_count = self.evaluate_duo_mode(state_duo, recipes)
            
            evaluation_time = time.time() - start_time
            
            return EvaluationMetrics(
                layout_id=layout_id,
                recipe_group_id=recipe_group_id,
                solo_steps=solo_steps,
                duo_steps=duo_steps,
                exchanges_count=exchanges_count,
                solo_actions=solo_actions,
                duo_actions=duo_actions,
                evaluation_time=evaluation_time,
                layout_hash=layout_hash,
                recipe_hash=recipe_hash
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur évaluation layout {layout_id} + recettes {recipe_group_id}: {e}")
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