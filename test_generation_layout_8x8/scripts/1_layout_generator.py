#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur professionnel de layouts 8x8 pour Overcooked
- Génération massive de layouts avec contraintes configurables
- Détection des rotations et miroirs pour éviter les doublons
- Positionnement intelligent des objets avec dispersion
- Contraintes de qualité et connectivité
- Support multiprocessing pour millions de layouts
"""

import os
import json
import time
import logging
import multiprocessing as mp
from pathlib import Path
from itertools import combinations, product
import random
import hashlib
import argparse

# Import du système de compression et batch
from layout_compression import LayoutCompressor, LayoutBatchManager
import numpy as np
from collections import deque
import argparse
from typing import Dict, List, Tuple, Set, Optional, Any

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('layout_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LayoutCanonicalizer:
    """Classe pour détecter les rotations et miroirs de layouts."""
    
    @staticmethod
    def rotate_90(grid: List[List[str]]) -> List[List[str]]:
        """Effectue une rotation de 90° dans le sens horaire."""
        n = len(grid)
        return [[grid[n-1-j][i] for j in range(n)] for i in range(n)]
    
    @staticmethod
    def mirror_horizontal(grid: List[List[str]]) -> List[List[str]]:
        """Effectue un miroir horizontal."""
        return [row[::-1] for row in grid]
    
    @staticmethod
    def mirror_vertical(grid: List[List[str]]) -> List[List[str]]:
        """Effectue un miroir vertical."""
        return grid[::-1]
    
    @classmethod
    def get_all_transformations(cls, grid: List[List[str]]) -> List[List[List[str]]]:
        """Génère toutes les transformations possibles d'une grille."""
        transformations = []
        current = grid
        
        # 4 rotations
        for _ in range(4):
            transformations.append([row[:] for row in current])
            current = cls.rotate_90(current)
        
        # Miroir horizontal + 4 rotations
        mirrored = cls.mirror_horizontal(grid)
        current = mirrored
        for _ in range(4):
            transformations.append([row[:] for row in current])
            current = cls.rotate_90(current)
        
        return transformations
    
    @classmethod
    def get_canonical_form(cls, grid: List[List[str]]) -> str:
        """Retourne la forme canonique d'une grille (plus petite lexicographiquement)."""
        transformations = cls.get_all_transformations(grid)
        grid_strings = [''.join(''.join(row) for row in t) for t in transformations]
        return min(grid_strings)

class ProfessionalLayoutGenerator:
    """Générateur professionnel de layouts avec validation complète."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise le générateur avec la configuration."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Paramètres de génération depuis la config
        gen_config = self.config["pipeline_config"]["generation"]
        self.grid_size = gen_config["grid_size"]
        self.target_total = gen_config["total_layouts_to_generate"]
        self.layouts_per_block = gen_config["block_size"]
        self.n_processes = gen_config["processes"]
        
        # Contraintes de layout
        constraints = gen_config["layout_constraints"]
        self.min_empty_cells = constraints["min_empty_cells"]
        self.max_empty_cells = constraints["max_empty_cells"]
        self.required_objects = constraints["required_objects"]
        self.max_counters = constraints["max_counters"]
        self.enforce_serving_on_edge = constraints["enforce_serving_on_edge"]
        self.enforce_object_dispersion = constraints["enforce_object_dispersion"]
        self.min_object_separation = constraints["min_object_separation"]
        self.detect_duplicates = constraints["detect_rotations_mirrors"]
        
        # Dossiers de sortie - création différée
        self.output_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_generated_dir"]
        
        # Cache pour éviter les doublons
        self.canonical_cache = set()
        
        # Gestionnaire de batch pour compression
        self.batch_manager = LayoutBatchManager(batch_size=gen_config.get("compression_batch_size", 10000))
        
        logger.info(f"🏗️  Générateur initialisé - Target: {self.target_total:,} layouts")
        logger.info(f"📁 Output: {self.output_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_base_grid(self) -> Optional[List[List[str]]]:
        """Génère une grille de base avec murs et espaces vides."""
        max_attempts = 100
        
        for attempt in range(max_attempts):
            # Initialiser la grille vide
            grid = [['.' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
            
            # Forcer les bordures à être des murs
            for i in range(self.grid_size):
                grid[0][i] = 'X'  # Bordure haute
                grid[self.grid_size-1][i] = 'X'  # Bordure basse
                grid[i][0] = 'X'  # Bordure gauche
                grid[i][self.grid_size-1] = 'X'  # Bordure droite
            
            # Calculer les positions intérieures disponibles
            inner_positions = []
            for i in range(1, self.grid_size-1):
                for j in range(1, self.grid_size-1):
                    inner_positions.append((i, j))
            
            # Déterminer le nombre de cases vides (entre min et max)
            n_empty = random.randint(self.min_empty_cells, 
                                   min(self.max_empty_cells, len(inner_positions)))
            n_walls = len(inner_positions) - n_empty
            
            if n_walls < 0:
                continue
            
            # Placer les murs en évitant les blocs 2x2
            wall_positions = self.place_walls_safely(inner_positions, n_walls)
            if wall_positions is None:
                continue
            
            for i, j in wall_positions:
                grid[i][j] = 'X'
            
            # Vérifier la connectivité complète
            if self.is_fully_connected(grid):
                return grid
        
        logger.warning("❌ Échec génération grille de base après max tentatives")
        return None
    
    def place_walls_safely(self, inner_positions: List[Tuple[int, int]], 
                          n_walls: int) -> Optional[List[Tuple[int, int]]]:
        """Place les murs en évitant les blocs 2x2 et les regroupements excessifs."""
        max_attempts = 100  # Revenir au nombre original
        
        for attempt in range(max_attempts):
            wall_positions = random.sample(inner_positions, n_walls)
            
            # Seulement vérifier les blocs 2x2 pour commencer
            if not self.has_2x2_wall_blocks(wall_positions):
                return wall_positions
        
        return None
    
    def has_excessive_wall_clustering(self, wall_positions: List[Tuple[int, int]]) -> bool:
        """Vérifie s'il y a trop de murs regroupés (plus de 2 murs adjacents)."""
        wall_set = set(wall_positions)
        
        for i, j in wall_positions:
            # Compter les murs adjacents
            adjacent_walls = 0
            for di, dj in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ni, nj = i + di, j + dj
                if (ni, nj) in wall_set:
                    adjacent_walls += 1
            
            # Éviter les regroupements de plus de 1 mur adjacent (autoriser au max 2 murs connectés)
            if adjacent_walls > 1:
                return True
        
        return False
    
    def has_good_wall_distribution(self, wall_positions: List[Tuple[int, int]]) -> bool:
        """Vérifie que les murs sont bien distribués dans la grille."""
        if not wall_positions:
            return True
        
        # Diviser la grille en quadrants et vérifier la répartition
        quadrants = [0, 0, 0, 0]  # top-left, top-right, bottom-left, bottom-right
        mid = self.grid_size // 2
        
        for i, j in wall_positions:
            if i < mid and j < mid:
                quadrants[0] += 1  # top-left
            elif i < mid and j >= mid:
                quadrants[1] += 1  # top-right
            elif i >= mid and j < mid:
                quadrants[2] += 1  # bottom-left
            else:
                quadrants[3] += 1  # bottom-right
        
        # Éviter que tous les murs soient concentrés dans un seul quadrant
        max_in_quadrant = max(quadrants)
        total_walls = len(wall_positions)
        
        # Maximum 70% des murs dans un seul quadrant
        return max_in_quadrant <= total_walls * 0.7
    
    def has_2x2_wall_blocks(self, wall_positions: List[Tuple[int, int]]) -> bool:
        """Vérifie s'il y a des blocs 2x2 de murs (incluant les bordures)."""
        wall_set = set(wall_positions)
        
        # Ajouter les bordures à la vérification
        for i in range(self.grid_size):
            wall_set.add((0, i))  # Bordure haute
            wall_set.add((self.grid_size-1, i))  # Bordure basse
            wall_set.add((i, 0))  # Bordure gauche
            wall_set.add((i, self.grid_size-1))  # Bordure droite
        
        # Vérifier tous les blocs 2x2 possibles
        for i in range(self.grid_size-1):
            for j in range(self.grid_size-1):
                block_2x2 = [(i, j), (i, j+1), (i+1, j), (i+1, j+1)]
                if all(pos in wall_set for pos in block_2x2):
                    return True
        
        return False
    
    def is_fully_connected(self, grid: List[List[str]]) -> bool:
        """Vérifie que toutes les cases vides sont connectées."""
        empty_cells = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == '.':
                    empty_cells.append((i, j))
        
        if len(empty_cells) < 2:
            return len(empty_cells) >= 1
        
        # BFS à partir de la première case vide
        start = empty_cells[0]
        reachable = self.bfs_reachable(grid, start)
        
        return len(reachable) == len(empty_cells)
    
    def bfs_reachable(self, grid: List[List[str]], start: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """BFS pour trouver toutes les cases accessibles."""
        queue = deque([start])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < self.grid_size and 0 <= nj < self.grid_size and
                    (ni, nj) not in visited and grid[ni][nj] != 'X'):
                    
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        return visited
    
    def get_edge_positions(self, grid: List[List[str]]) -> List[Tuple[int, int]]:
        """Retourne les positions vides sur les bords intérieurs."""
        edge_positions = []
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == '.':
                    # Vérifier si adjacent au bord
                    is_edge = (i == 1 or i == self.grid_size-2 or 
                              j == 1 or j == self.grid_size-2)
                    if is_edge:
                        edge_positions.append((i, j))
        
        return edge_positions
    
    def calculate_object_dispersion_score(self, positions: Dict[str, Tuple[int, int]]) -> float:
        """Calcule un score de dispersion des objets."""
        if len(positions) < 2:
            return 1.0
        
        distances = []
        pos_list = list(positions.values())
        
        for i in range(len(pos_list)):
            for j in range(i + 1, len(pos_list)):
                p1, p2 = pos_list[i], pos_list[j]
                dist = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])  # Distance Manhattan
                distances.append(dist)
        
        avg_distance = sum(distances) / len(distances)
        min_distance = min(distances)
        
        # Score basé sur distance moyenne et distance minimale
        score = min(1.0, (avg_distance / (self.grid_size * 0.7)) * (min_distance / self.min_object_separation))
        return score
    
    def place_objects_with_constraints(self, grid: List[List[str]]) -> Optional[Dict]:
        """Place les objets en respectant toutes les contraintes."""
        max_attempts = 50
        
        for attempt in range(max_attempts):
            layout_grid = [row[:] for row in grid]  # Copie
            
            # Trouver toutes les positions vides
            empty_positions = []
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    if layout_grid[i][j] == '.':
                        empty_positions.append((i, j))
            
            if len(empty_positions) < len(self.required_objects):
                continue
            
            # Positions pour objets requis
            object_positions = {}
            available_positions = empty_positions[:]
            
            # 1. Placer les joueurs (pas sur les bords)
            inner_positions = [(i, j) for i, j in available_positions 
                              if 1 < i < self.grid_size-2 and 1 < j < self.grid_size-2]
            
            if len(inner_positions) < 2:
                continue
            
            player_positions = random.sample(inner_positions, 2)
            object_positions['1'] = player_positions[0]
            object_positions['2'] = player_positions[1]
            
            # Retirer les positions des joueurs
            for pos in player_positions:
                available_positions.remove(pos)
            
            # 2. Placer la station de service (S) sur le bord si requis
            if self.enforce_serving_on_edge and 'S' in self.required_objects:
                edge_positions = self.get_edge_positions(grid)
                edge_available = [pos for pos in edge_positions if pos in available_positions]
                
                if not edge_available:
                    continue
                
                serving_pos = random.choice(edge_available)
                object_positions['S'] = serving_pos
                available_positions.remove(serving_pos)
            
            # 3. Placer les autres objets obligatoires
            remaining_objects = [obj for obj in self.required_objects 
                               if obj not in ['1', '2', 'S'] or ('S' not in object_positions)]
            
            if 'S' not in object_positions and 'S' in self.required_objects:
                remaining_objects.append('S')
            
            if len(available_positions) < len(remaining_objects):
                continue
            
            # Placement avec vérification de dispersion
            selected_positions = random.sample(available_positions, len(remaining_objects))
            
            for i, obj in enumerate(remaining_objects):
                object_positions[obj] = selected_positions[i]
            
            # Vérifier la dispersion si requise
            if self.enforce_object_dispersion:
                dispersion_score = self.calculate_object_dispersion_score(object_positions)
                if dispersion_score < 0.6:  # Seuil de dispersion
                    continue
            
            # Placer les objets sur la grille
            for obj, pos in object_positions.items():
                layout_grid[pos[0]][pos[1]] = obj
            
            # Ajouter quelques comptoirs optionnels
            remaining_available = [pos for pos in available_positions 
                                 if pos not in selected_positions]
            
            n_counters = min(self.max_counters, 
                           random.randint(0, min(3, len(remaining_available))))
            
            if n_counters > 0 and remaining_available:
                counter_positions = random.sample(remaining_available, n_counters)
                for pos in counter_positions:
                    layout_grid[pos[0]][pos[1]] = 'Y'
            
            # Vérifier que tous les objets sont accessibles
            if self.are_all_objects_accessible(layout_grid):
                return self.grid_to_layout_dict(layout_grid, object_positions)
        
        return None
    
    def are_all_objects_accessible(self, grid: List[List[str]]) -> bool:
        """Vérifie que tous les objets sont accessibles par les deux joueurs."""
        # Trouver les positions des joueurs et objets
        player_positions = []
        object_positions = []
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] in ['1', '2']:
                    player_positions.append((i, j))
                elif grid[i][j] in ['O', 'T', 'P', 'D', 'S']:
                    object_positions.append((i, j))
        
        if len(player_positions) != 2:
            return False
        
        # Vérifier que chaque joueur peut atteindre tous les objets
        for player_pos in player_positions:
            reachable = self.bfs_reachable(grid, player_pos)
            
            for obj_pos in object_positions:
                if obj_pos not in reachable:
                    return False
        
        return True
    
    def grid_to_layout_dict(self, grid: List[List[str]], 
                           object_positions: Dict[str, Tuple[int, int]]) -> Dict:
        """Convertit une grille en format brut pour génération massive."""
        # Format grid comme string simple pour génération massive
        grid_str = '\n'.join([''.join(row) for row in grid])
        
        # Calculer le hash canonique si détection des doublons activée
        if self.detect_duplicates:
            canonical_form = LayoutCanonicalizer.get_canonical_form(grid)
            layout_hash = hashlib.md5(canonical_form.encode()).hexdigest()[:16]
        else:
            layout_hash = hashlib.md5(grid_str.encode()).hexdigest()[:16]
        
        # Format brut optimisé pour génération massive (SANS recettes)
        layout_dict = {
            "grid": grid_str,
            "canonical_hash": layout_hash,
            "object_positions": object_positions,
            "generation_metadata": {
                "timestamp": time.time(),
                "n_empty": sum(row.count('.') for row in grid),
                "n_walls": sum(row.count('X') for row in grid),
                "dispersion_score": self.calculate_object_dispersion_score(object_positions)
            }
        }
        
        return layout_dict
        
        return layout_dict
    
    def generate_single_layout(self) -> Optional[Dict]:
        """Génère un seul layout valide."""
        max_attempts = 20
        
        for attempt in range(max_attempts):
            # Générer la grille de base
            base_grid = self.generate_base_grid()
            if base_grid is None:
                continue
            
            # Placer les objets
            layout = self.place_objects_with_constraints(base_grid)
            if layout is None:
                continue
            
            # Vérifier si c'est un doublon (si détection activée)
            if self.detect_duplicates:
                canonical_hash = layout['canonical_hash']
                if canonical_hash in self.canonical_cache:
                    continue  # Doublon détecté
                self.canonical_cache.add(canonical_hash)
            
            return layout
        
        return None
    
    def generate_block_worker(self, block_id: int, layouts_per_block: int) -> Dict:
        """Worker pour générer un bloc de layouts avec diversité garantie."""
        # Initialiser la randomisation avec une seed unique pour chaque worker
        import time
        unique_seed = int(time.time() * 1000000) % 2**32 + block_id * 1000
        random.seed(unique_seed)
        
        logger.info(f"🔄 Worker {block_id}: Génération de {layouts_per_block} layouts (seed: {unique_seed})")
        
        layouts = []
        attempts = 0
        max_total_attempts = layouts_per_block * 10  # Augmenter pour plus de diversité
        local_cache = set()  # Cache local pour éviter les doublons dans ce bloc
        
        while len(layouts) < layouts_per_block and attempts < max_total_attempts:
            attempts += 1
            layout = self.generate_single_layout()
            
            if layout is not None:
                # Vérifier les doublons locaux
                if self.detect_duplicates:
                    canonical_hash = layout['canonical_hash']
                    if canonical_hash in local_cache:
                        continue  # Doublon local détecté
                    local_cache.add(canonical_hash)
                
                layouts.append(layout)
                
                if len(layouts) % 10 == 0:  # Log plus fréquent pour voir la progression
                    logger.info(f"Worker {block_id}: {len(layouts)}/{layouts_per_block} layouts générés")
        
        success_rate = len(layouts) / attempts * 100 if attempts > 0 else 0
        
        result = {
            'block_id': block_id,
            'layouts': layouts,
            'total_attempts': attempts,
            'success_rate': success_rate,
            'timestamp': time.time()
        }
        
        logger.info(f"✅ Worker {block_id}: {len(layouts)} layouts générés (taux: {success_rate:.1f}%)")
        return result
    
    def run_massive_generation(self) -> bool:
        """Lance la génération massive de layouts."""
        start_time = time.time()
        
        # Calculer le nombre de blocs nécessaires
        n_blocks = (self.target_total + self.layouts_per_block - 1) // self.layouts_per_block
        
        logger.info(f"🚀 Démarrage génération massive")
        logger.info(f"📊 Target: {self.target_total:,} layouts en {n_blocks} blocs")
        logger.info(f"⚙️  Processus: {self.n_processes}")
        
        total_generated = 0
        
        # Si un seul processus, pas besoin de multiprocessing
        if self.n_processes == 1:
            logger.info("🔄 Mode single-process activé")
            
            for block_id in range(n_blocks):
                remaining = self.target_total - total_generated
                block_size = min(self.layouts_per_block, remaining)
                
                if block_size <= 0:
                    break
                
                # Génération directe sans multiprocessing
                result = self.generate_block_worker(block_id, block_size)
                
                # Ajouter les layouts au gestionnaire de batch compressé (SEUL stockage nécessaire)
                for layout in result['layouts']:
                    self.batch_manager.add_layout(layout, str(self.output_dir))
                
                total_generated += len(result['layouts'])
                
                logger.info(f"� Bloc {result['block_id']} traité: {len(result['layouts'])} layouts → batch compressé")
                logger.info(f"📈 Progression: {total_generated:,}/{self.target_total:,} ({total_generated/self.target_total*100:.1f}%)")
        
        else:
            # Traitement par blocs avec multiprocessing
            with mp.Pool(processes=self.n_processes) as pool:
                # Préparer les tâches
                tasks = []
                for block_id in range(n_blocks):
                    remaining = self.target_total - total_generated
                    block_size = min(self.layouts_per_block, remaining)
                    
                    if block_size <= 0:
                        break
                    
                    tasks.append((block_id, block_size))
                
                # Exécuter les tâches
                results = []
                for block_id, block_size in tasks:
                    result = pool.apply_async(self.generate_block_worker, (block_id, block_size))
                    results.append(result)
                
                # Collecter et sauvegarder les résultats avec compression
                for i, result_async in enumerate(results):
                    try:
                        result = result_async.get(timeout=3600)  # 1 heure max par bloc
                        
                        # Ajouter les layouts au gestionnaire de batch compressé (SEUL stockage nécessaire)
                        for layout in result['layouts']:
                            self.batch_manager.add_layout(layout, str(self.output_dir))
                        
                        total_generated += len(result['layouts'])
                        
                        logger.info(f"� Bloc {result['block_id']} traité: {len(result['layouts'])} layouts → batch compressé")
                        logger.info(f"📈 Progression: {total_generated:,}/{self.target_total:,} ({total_generated/self.target_total*100:.1f}%)")
                    
                    except Exception as e:
                        logger.error(f"❌ Erreur bloc {i}: {e}")
        
        # Finaliser le gestionnaire de batch
        compression_stats = self.batch_manager.finalize(str(self.output_dir))
        
        generation_time = time.time() - start_time
        
        # Rapport final
        logger.info(f"✅ Génération terminée!")
        logger.info(f"📊 Résultats: {total_generated:,} layouts générés en {generation_time:.1f}s")
        logger.info(f"⚡ Performance: {total_generated/generation_time:.1f} layouts/sec")
        logger.info(f"📦 Compression: {compression_stats['compression_ratio']:.1f}% gain d'espace")
        logger.info(f"🗂️ Batches créés: {compression_stats['total_batches']}")
        
        return total_generated > 0

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Générateur professionnel de layouts Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json", 
                       help="Fichier de configuration")
    parser.add_argument("--target", type=int, 
                       help="Nombre de layouts à générer (override config)")
    parser.add_argument("--processes", type=int,
                       help="Nombre de processus à utiliser (override config)")
    
    args = parser.parse_args()
    
    try:
        generator = ProfessionalLayoutGenerator(args.config)
        
        # Override du target si spécifié
        if args.target:
            generator.target_total = args.target
            logger.info(f"🎯 Target overridé: {args.target:,} layouts")
        
        # Override du nombre de processus si spécifié
        if args.processes:
            generator.n_processes = args.processes
            logger.info(f"⚙️  Processus overridé: {args.processes}")
        
        success = generator.run_massive_generation()
        
        if success:
            logger.info("🎉 Génération réussie!")
            return 0
        else:
            logger.error("❌ Échec de la génération")
            return 1
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
