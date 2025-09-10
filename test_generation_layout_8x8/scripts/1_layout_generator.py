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
import signal
import multiprocessing as mp
from pathlib import Path
from itertools import combinations, product
import random
import hashlib
import argparse

import numpy as np
import gzip
import base64
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

class LayoutCompressor:
    """Compresse les layouts pour le stockage optimisé"""
    
    def __init__(self):
        self.symbol_map = {
            'X': 'X',  # Wall
            ' ': ' ',  # Empty space
            '1': '1',  # Player 1
            '2': '2',  # Player 2
            'O': 'O',  # Onion dispenser
            'T': 'T',  # Tomato dispenser
            'P': 'P',  # Pot
            'D': 'D',  # Dish dispenser
            'S': 'S',  # Serving area
            'Y': 'Y'   # Counter
        }
    
    def encode_grid_to_base64(self, grid: List[List[str]]) -> str:
        """Encode une grille en base64"""
        # Convertir la grille en string simple
        grid_str = '\n'.join([''.join(row) for row in grid])
        # Encoder en base64
        return base64.b64encode(grid_str.encode('utf-8')).decode('ascii')
    
    def compress_layout(self, layout: Dict) -> Dict:
        """Compresse un layout"""
        grid_str = layout.get('grid', '')
        
        # Convertir string grid en liste si nécessaire
        if isinstance(grid_str, str):
            lines = grid_str.strip().split('\n')
            grid = [list(line) for line in lines]
        else:
            grid = grid_str
        
        # Encoder la grille
        compressed_grid = self.encode_grid_to_base64(grid)
        
        # Calculer le hash
        if isinstance(grid_str, str):
            layout_hash = hashlib.md5(grid_str.encode()).hexdigest()[:16]
        else:
            grid_str_calc = '\n'.join([''.join(row) for row in grid])
            layout_hash = hashlib.md5(grid_str_calc.encode()).hexdigest()[:16]
        
        # Extraire les positions des objets depuis la grille
        object_positions = {}
        for i, row in enumerate(grid):
            for j, cell in enumerate(row):
                if cell in ['O', 'T', 'P', 'D', 'S', '1', '2']:
                    if cell not in object_positions:
                        object_positions[cell] = []
                    object_positions[cell].append([i, j])
        
        return {
            'g': compressed_grid,  # grid compressed
            'h': layout_hash,      # hash
            'op': object_positions # object positions
        }

class LayoutBatchManager:
    """Gestionnaire des batchs de layouts"""
    
    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size
        self.compressor = LayoutCompressor()
        self.current_batch = []
        self.batch_count = 0
        self.total_layouts = 0
    
    def add_layout(self, layout: Dict, output_dir: str):
        """Ajoute un layout au batch actuel"""
        compressed = self.compressor.compress_layout(layout)
        self.current_batch.append(compressed)
        self.total_layouts += 1
        
        # Sauvegarder si le batch est plein
        if len(self.current_batch) >= self.batch_size:
            self._save_current_batch(output_dir)
    
    def _save_current_batch(self, output_dir: str) -> str:
        """Sauvegarde le batch actuel"""
        if not self.current_batch:
            return None
        
        # Créer le répertoire s'il n'existe pas
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        self.batch_count += 1
        batch_file = f"{output_dir}/layout_batch_{self.batch_count}.jsonl.gz"
        
        with gzip.open(batch_file, 'wt', encoding='utf-8') as f:
            for layout in self.current_batch:
                f.write(json.dumps(layout) + '\n')
        
        logger.info(f"Batch {self.batch_count} sauvegardé: {len(self.current_batch)} layouts dans {batch_file}")
        self.current_batch = []
        return batch_file
    
    def finalize(self, output_dir: str) -> Dict:
        """Finalise et sauvegarde le dernier batch"""
        # Sauvegarder le batch restant
        if self.current_batch:
            self._save_current_batch(output_dir)
        
        # Créer un fichier de résumé
        summary = {
            "total_layouts": self.total_layouts,
            "total_batches": self.batch_count,
            "compression_format": "jsonl.gz",
            "timestamp": time.time()
        }
        
        # S'assurer que le répertoire de sortie existe
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        summary_file = f"{output_dir}/generation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Génération finalisée: {self.total_layouts} layouts dans {self.batch_count} batches")
        return summary

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
        
        # Mode exhaustif si target = 0
        self.is_exhaustive_mode = (self.target_total == 0)
        
        # Contraintes de layout
        constraints = gen_config["layout_constraints"]
        self.empty_cells = constraints["empty_cells"]  # Nombre exact de cellules vides
        self.required_objects = [obj for obj in constraints["required_objects"] if obj != "Y"]  # Exclure Y de la génération
        self.enforce_object_dispersion = constraints["enforce_object_dispersion"]
        self.min_object_separation = constraints["min_object_separation"]
        self.detect_duplicates = constraints["detect_rotations_mirrors"]
        
        # Dossiers de sortie - création différée
        self.output_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_generated_dir"]
        
        # Cache pour éviter les doublons
        self.canonical_cache = set()
        
        # Compteur pour limiter les logs d'échecs en mode exhaustif
        self.failure_log_count = 0
        self.max_failure_logs = 10 if self.is_exhaustive_mode else 100
        
        # Gestionnaire de batch pour compression
        self.batch_manager = LayoutBatchManager(batch_size=gen_config.get("compression_batch_size", 100))
        
        # Gestionnaire d'interruption pour sauvegardes en cas d'arrêt forcé
        self._setup_signal_handlers()
        
        logger.info(f"🏗️  Générateur initialisé - Target: {self.target_total:,} layouts")
        logger.info(f"📁 Output: {self.output_dir}")
    
    def _setup_signal_handlers(self):
        """Configure la gestion d'interruption gracieuse"""
        def signal_handler(signum, frame):
            logger.info("🛑 Interruption détectée - Sauvegarde du batch courant...")
            if hasattr(self, 'batch_manager') and self.batch_manager.current_batch:
                self.batch_manager.finalize(str(self.output_dir))
                logger.info(f"✅ {len(self.batch_manager.current_batch)} layouts sauvegardés avant arrêt")
            logger.info("🔚 Arrêt gracieux terminé")
            exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Terminate
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Valider la faisabilité de la configuration
        self.validate_config_feasibility(config)
        return config
    
    def validate_config_feasibility(self, config: Dict) -> None:
        """Valide si la configuration est mathématiquement possible selon la nouvelle logique."""
        gen_config = config["pipeline_config"]["generation"]
        constraints = gen_config["layout_constraints"]
        
        grid_size = gen_config["grid_size"]
        empty_cells = constraints["empty_cells"]
        required_objects = [obj for obj in constraints["required_objects"] if obj not in ["Y", "1", "2"]]
        
        # Calculs selon la nouvelle logique
        total_cells = grid_size * grid_size  # 64 pour 8x8
        inner_cells = (grid_size - 2) * (grid_size - 2)  # 36 pour 8x8 (intérieur 6x6)
        
        # Vérification 1: Les cellules vides ne peuvent pas dépasser l'intérieur
        if empty_cells > inner_cells:
            error_msg = f"""
🚨 CONFIGURATION IMPOSSIBLE !

La configuration demande {empty_cells} cellules vides, mais c'est impossible :

📐 Analyse du grid {grid_size}x{grid_size} :
   • Total de cellules : {total_cells}
   • Cases intérieures disponibles : {inner_cells}
   • Cellules vides demandées : {empty_cells}

💡 Maximum de cellules vides possible : {inner_cells}

🔧 Solution : Réduire empty_cells à {inner_cells} ou moins
"""
            logger.error(error_msg)
            raise ValueError("Configuration impossible - trop de cellules vides demandées")
        
        # Calcul des murs intérieurs nécessaires
        walls_needed = inner_cells - empty_cells
        
        # Les objets O, T, P, D remplacent des murs X
        # S remplace un mur de bordure
        # Les joueurs 1, 2 sont placés sur les cellules vides
        
        logger.info(f"✅ Configuration validée :")
        logger.info(f"   📐 Grille {grid_size}x{grid_size} avec {inner_cells} cases intérieures")
        logger.info(f"   🕳️ {empty_cells} cellules vides")
        logger.info(f"   🧱 {walls_needed} murs intérieurs")
        logger.info(f"   🎯 {len(required_objects)} objets remplaceront des murs")
        logger.info(f"   👥 2 joueurs seront placés sur les cellules vides")
    
    def save_layouts_to_file(self):
        """Sauvegarde tous les layouts générés dans un fichier JSON."""
        if not self.generated_layouts:
            logger.warning("Aucun layout à sauvegarder")
            return
        
        # Créer le répertoire de sortie s'il n'existe pas
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Fichier de sortie
        output_file = self.output_dir / "generated_layouts.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.generated_layouts, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 {len(self.generated_layouts)} layouts sauvegardés dans {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {e}")
    
    def generate_base_grid(self) -> Optional[List[List[str]]]:
        """Génère une grille de base avec murs et espaces vides."""
        max_attempts = 100
        
        for attempt in range(max_attempts):
            # Initialiser la grille vide avec des espaces
            grid = [[' ' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
            
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
            
            # Calculer le nombre exact de cases vides requises
            # Note: une position de bordure sera remplacée par S, donc on doit compenser
            total_inner_positions = len(inner_positions)
            
            # Vérifier si c'est possible de générer avec ce nombre de cellules vides
            # On ajoute 1 car la station S remplacera un mur de bordure
            required_positions = self.empty_cells + len(self.required_objects) - 1  # -1 car S remplace un X
            
            if required_positions > total_inner_positions:
                raise ValueError(f"Impossible de générer un layout avec {self.empty_cells} cellules vides et {len(self.required_objects)} objets. "
                               f"Maximum possible: {total_inner_positions} positions intérieures (grille {self.grid_size}x{self.grid_size})")
            
            # Calculer le nombre de murs nécessaires à l'intérieur
            # Objets à placer dans l'intérieur (tous sauf S qui va sur la bordure, et sans les joueurs qui vont sur les cases vides)
            objects_interior = [obj for obj in self.required_objects if obj not in ['S', '1', '2']]
            
            # STRATÉGIE CORRECTE : placer assez de murs pour qu'après remplacement par objets, on ait le bon nombre de cases vides
            # Cases finales = cases vides (20) + objets (4) + murs finaux
            # Donc: murs finaux = 36 - 20 - 4 = 12
            # Mais on doit placer initialement: murs finaux + objets qui remplaceront des murs = 12 + 4 = 16
            n_walls = total_inner_positions - self.empty_cells
            
            logger.debug(f"📊 Calcul: {total_inner_positions} positions - {self.empty_cells} vides finales = {n_walls} murs à placer (dont {len(objects_interior)} seront remplacés)")
            
            if n_walls < 0:
                raise ValueError(f"Configuration impossible: {self.empty_cells} cellules vides + {len(objects_interior)} objets > {total_inner_positions} positions")
            
            # Placer exactement n_walls murs
            wall_positions = self.place_walls_safely(inner_positions, n_walls)
            if wall_positions is None:
                continue
            
            logger.debug(f"🧱 Murs placés: {len(wall_positions)}/{n_walls}")
            
            for i, j in wall_positions:
                grid[i][j] = 'X'
            
            # Vérifier la connectivité complète avant de placer les objets
            if self.is_fully_connected_for_all_positions(grid) and self.are_all_empty_cells_connected(grid):
                return grid
        
        # Limiter les logs en mode exhaustif pour éviter le spam
        if self.failure_log_count < self.max_failure_logs:
            if self.is_exhaustive_mode:
                logger.debug("❌ Échec génération grille de base après max tentatives")
            else:
                logger.warning("❌ Échec génération grille de base après max tentatives")
            self.failure_log_count += 1
        elif self.failure_log_count == self.max_failure_logs:
            logger.info(f"ℹ️  Mode silencieux activé: plus de logs d'échecs après {self.max_failure_logs} occurrences")
            self.failure_log_count += 1
        
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
                if grid[i][j] == ' ':
                    empty_cells.append((i, j))
        
        if len(empty_cells) < 2:
            return len(empty_cells) >= 1
        
        # BFS à partir de la première case vide
        start = empty_cells[0]
        reachable = self.bfs_reachable(grid, start)
        
        return len(reachable) == len(empty_cells)
    
    def are_all_empty_cells_connected(self, grid: List[List[str]]) -> bool:
        """Vérifie que toutes les cases vides ' ' sont connectées entre elles."""
        # Trouver toutes les cases vides
        empty_positions = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == ' ':
                    empty_positions.append((i, j))
        
        if len(empty_positions) < 2:
            return len(empty_positions) >= 1
        
        # Vérifier que toutes les cases vides sont mutuellement accessibles
        start = empty_positions[0]
        reachable = self.bfs_reachable_empty_only(grid, start)
        
        return len(reachable) == len(empty_positions)
    
    def is_fully_connected_for_all_positions(self, grid: List[List[str]]) -> bool:
        """Vérifie que toutes les positions non-murs sont mutuellement accessibles."""
        # Trouver toutes les positions non-murs
        non_wall_positions = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] != 'X':
                    non_wall_positions.append((i, j))
        
        if len(non_wall_positions) < 2:
            return len(non_wall_positions) >= 1
        
        # Vérifier que toutes les positions sont mutuellement accessibles
        start = non_wall_positions[0]
        reachable = self.bfs_reachable(grid, start)
        
        return len(reachable) == len(non_wall_positions)
    
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

    def bfs_reachable_empty_only(self, grid: List[List[str]], start: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """BFS pour trouver toutes les cases vides ' ' accessibles depuis le point de départ."""
        queue = deque([start])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < self.grid_size and 0 <= nj < self.grid_size and
                    (ni, nj) not in visited and grid[ni][nj] == ' '):
                    
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        return visited
    
    def are_all_empty_cells_connected(self, grid: List[List[str]]) -> bool:
        """Vérifie que toutes les cases vides ' ' sont connectées entre elles."""
        # Trouver toutes les cases vides
        empty_positions = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == ' ':
                    empty_positions.append((i, j))
        
        # S'il n'y a pas de cases vides, retourner True
        if not empty_positions:
            return True
        
        # Vérifier que toutes les cases vides sont accessibles depuis la première
        start = empty_positions[0]
        reachable_empty = self.bfs_reachable_empty_only(grid, start)
        
        return len(reachable_empty) == len(empty_positions)

    def get_edge_positions(self, grid: List[List[str]]) -> List[Tuple[int, int]]:
        """Retourne les positions vides sur les bordures extérieures (positions 0 et grid_size-1)."""
        edge_positions = []
        
        # Bordure haute (ligne 0) et basse (ligne grid_size-1)
        for j in range(self.grid_size):
            if grid[0][j] == ' ':
                edge_positions.append((0, j))
            if grid[self.grid_size-1][j] == ' ':
                edge_positions.append((self.grid_size-1, j))
        
        # Bordure gauche (colonne 0) et droite (colonne grid_size-1)
        for i in range(1, self.grid_size-1):  # Éviter les coins déjà traités
            if grid[i][0] == ' ':
                edge_positions.append((i, 0))
            if grid[i][self.grid_size-1] == ' ':
                edge_positions.append((i, self.grid_size-1))
        
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

    def select_dispersed_positions(self, available_positions: List[Tuple[int, int]], 
                                 count: int) -> Optional[List[Tuple[int, int]]]:
        """Sélectionne des positions en maximisant la dispersion."""
        if count <= 0:
            return []
        if count == 1:
            return [random.choice(available_positions)]
        if len(available_positions) < count:
            return None
            
        best_positions = None
        best_score = -1
        max_attempts = 50  # Limite pour éviter les boucles infinies
        
        for attempt in range(max_attempts):
            # Sélection aléatoire
            positions = random.sample(available_positions, count)
            
            # Calculer le score de dispersion
            distances = []
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    p1, p2 = positions[i], positions[j]
                    dist = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])  # Distance Manhattan
                    distances.append(dist)
            
            if not distances:
                continue
                
            min_distance = min(distances)
            avg_distance = sum(distances) / len(distances)
            
            # Score privilégiant la distance minimale (éviter les objets trop proches)
            score = min_distance + (avg_distance * 0.5)
            
            # Vérifier que les objets respectent la distance minimale
            if min_distance >= self.min_object_separation and score > best_score:
                best_score = score
                best_positions = positions
        
        return best_positions if best_positions else random.sample(available_positions, count)
    
    def place_objects_with_constraints(self, grid: List[List[str]]) -> Optional[Dict]:
        """Place les objets en remplaçant des X par les objets spécifiques."""
        max_attempts = 100
        
        for attempt in range(max_attempts):
            # Copier la grille de base
            layout_grid = [row[:] for row in grid]
            object_positions = {}
            
            # 1. Placer S sur une bordure (remplacer un X de bordure par S)
            edge_positions = []
            for i in [0, self.grid_size-1]:  # Bordures haute et basse
                for j in range(self.grid_size):
                    if layout_grid[i][j] == 'X':
                        edge_positions.append((i, j))
            for i in range(self.grid_size):  # Bordures gauche et droite
                for j in [0, self.grid_size-1]:
                    if layout_grid[i][j] == 'X':
                        edge_positions.append((i, j))
            
            if not edge_positions:
                continue
            
            # Choisir une position pour S
            border_pos = random.choice(edge_positions)
            layout_grid[border_pos[0]][border_pos[1]] = 'S'
            object_positions['S'] = border_pos
            
            # 2. Placer les joueurs sur des cases vides (jamais sur les bordures)
            empty_positions = []
            for i in range(1, self.grid_size-1):  # Exclure les bordures
                for j in range(1, self.grid_size-1):
                    if layout_grid[i][j] == ' ':
                        empty_positions.append((i, j))
            
            if len(empty_positions) < 2:
                continue
            
            player_positions = random.sample(empty_positions, 2)
            layout_grid[player_positions[0][0]][player_positions[0][1]] = '1'
            layout_grid[player_positions[1][0]][player_positions[1][1]] = '2'
            object_positions['1'] = player_positions[0]
            object_positions['2'] = player_positions[1]
            
            # Retirer les positions des joueurs des cases vides disponibles
            for pos in player_positions:
                empty_positions.remove(pos)
            
            # 3. Placer les autres objets (O, T, P, D) en remplaçant des X
            remaining_objects = [obj for obj in self.required_objects 
                               if obj not in ['1', '2', 'S']]
            
            # Trouver TOUTES les positions X disponibles (bordures ET intérieur)
            wall_positions = []
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    if layout_grid[i][j] == 'X':
                        wall_positions.append((i, j))
            
            if len(wall_positions) < len(remaining_objects):
                continue
            
            # Sélectionner des positions X pour les remplacer par des objets
            # Avec dispersion forcée si activée
            if self.enforce_object_dispersion:
                selected_wall_positions = self.select_dispersed_positions(wall_positions, len(remaining_objects))
                if selected_wall_positions is None:
                    continue  # Pas réussi à trouver des positions bien dispersées
            else:
                selected_wall_positions = random.sample(wall_positions, len(remaining_objects))
            
            for i, obj in enumerate(remaining_objects):
                pos = selected_wall_positions[i]
                layout_grid[pos[0]][pos[1]] = obj
                object_positions[obj] = pos
            
            # 4. Vérifier que toutes les cases vides restent connectées
            if not self.are_all_empty_cells_connected(layout_grid):
                continue
            
            # 5. Vérifier que tous les objets sont mutuellement accessibles
            if self.are_all_objects_accessible_strict(layout_grid):
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
    
    def are_all_objects_accessible_strict(self, grid: List[List[str]]) -> bool:
        """Vérification stricte: tous les objets doivent être mutuellement accessibles."""
        # Trouver toutes les positions d'objets et de joueurs
        all_important_positions = []
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] in ['1', '2', 'O', 'T', 'P', 'D', 'S']:
                    all_important_positions.append((i, j))
        
        if len(all_important_positions) < 2:
            return False
        
        # Vérifier que chaque position importante peut atteindre toutes les autres
        for start_pos in all_important_positions:
            reachable = self.bfs_reachable(grid, start_pos)
            
            for target_pos in all_important_positions:
                if target_pos not in reachable:
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
                "n_empty": sum(row.count(' ') for row in grid),
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
        
        # Mode exhaustif si target_total = 0
        if self.target_total == 0:
            logger.info(f"🚀 Démarrage génération EXHAUSTIVE")
            logger.info(f"🔄 Mode: Génération de tous les layouts possibles")
            logger.info(f"⚙️  Processus: {self.n_processes}")
            return self._run_exhaustive_generation(start_time)
        
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
                
                # Ajouter les layouts au gestionnaire de batch compressé
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
                        
                        # Ajouter les layouts au gestionnaire de batch compressé
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
        logger.info(f"� Layouts sauvegardés dans: {self.output_dir}")
        
        return total_generated > 0

    def _run_exhaustive_generation(self, start_time: float) -> bool:
        """Mode exhaustif: génère tous les layouts possibles."""
        total_generated = 0
        block_id = 0
        consecutive_empty_blocks = 0
        max_empty_blocks = 5  # Arrêter après 5 blocs vides consécutifs
        
        logger.info("🔄 Début génération exhaustive...")
        logger.info("ℹ️  Mode optimisé: logs d'échecs réduits en mode exhaustif")
        
        while consecutive_empty_blocks < max_empty_blocks:
            try:
                # Générer un bloc
                result = self.generate_block_worker(block_id, self.layouts_per_block)
                
                # Ajouter les layouts au gestionnaire de batch compressé (avec sauvegarde automatique)
                for layout in result['layouts']:
                    self.batch_manager.add_layout(layout, str(self.output_dir))
                
                layouts_in_block = len(result['layouts'])
                total_generated += layouts_in_block
                
                if layouts_in_block == 0:
                    consecutive_empty_blocks += 1
                    logger.debug(f"Bloc {block_id} vide ({consecutive_empty_blocks}/{max_empty_blocks})")
                else:
                    consecutive_empty_blocks = 0
                    # Logging optimisé : seulement tous les 10 blocs ou si > 1000 layouts dans le bloc
                    if block_id % 10 == 0 or layouts_in_block > 1000:
                        logger.info(f"✅ Bloc {block_id}: {layouts_in_block} layouts → Total: {total_generated:,}")
                
                block_id += 1
                
                # Sécurité : arrêter si trop de layouts générés (éviter l'explosion)
                if total_generated > 1000000:  # 1M layouts max
                    logger.warning(f"🛑 Arrêt de sécurité: {total_generated:,} layouts générés")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Erreur bloc {block_id}: {e}")
                consecutive_empty_blocks += 1
                block_id += 1
                continue
        
        # Finaliser le gestionnaire de batch
        compression_stats = self.batch_manager.finalize(str(self.output_dir))
        
        generation_time = time.time() - start_time
        
        # Rapport final
        logger.info(f"✅ Génération exhaustive terminée!")
        logger.info(f"📊 Résultats: {total_generated:,} layouts générés en {generation_time:.1f}s")
        if generation_time > 0:
            logger.info(f"⚡ Performance: {total_generated/generation_time:.1f} layouts/sec")
        logger.info(f"🏁 Arrêt: {consecutive_empty_blocks} blocs vides consécutifs")
        logger.info(f"💾 Layouts sauvegardés dans: {self.output_dir}")
        
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
