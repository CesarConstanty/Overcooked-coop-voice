#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur MASSIF de layouts 8x8 CORRIGÉ pour Overcooked
Vérifie la connectivité complète et l'accessibilité des objets
"""

import os
import json
import time
import multiprocessing as mp
from pathlib import Path
from itertools import combinations, product
import random
import hashlib
from collections import deque
import argparse

class ValidatedLayoutGenerator8x8:
    """Générateur de layouts 8x8 avec validation complète."""
    
    def __init__(self, target_millions=1, layouts_per_block=10000):
        """Initialise le générateur avec validation."""
        self.target_millions = target_millions
        self.target_total = target_millions * 1_000_000
        self.layouts_per_block = layouts_per_block
        
        self.base_dir = Path(__file__).parent.parent
        self.output_dir = self.base_dir / "outputs" / "validated_layouts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration pour la génération
        self.grid_size = 8
        self.wall_char = 'X'
        self.empty_char = '.'
        
        # Types d'objets Overcooked
        self.objects = {
            'player1': '1',
            'player2': '2', 
            'onion_dispenser': 'O',
            'tomato_dispenser': 'T',
            'pot': 'P',
            'dish_dispenser': 'D',
            'serving_station': 'S',
            'counter': 'Y'
        }
        
        # Paramètres de densité
        self.n_empty_ranges = {
            'sparse': (20, 24),   # Grilles très denses
            'medium': (25, 29),   # Grilles moyennes
            'open': (30, 34),     # Grilles ouvertes
            'very_open': (35, 39) # Grilles très ouvertes
        }
        
        print(f"🚀 Générateur VALIDÉ initialisé")
        print(f"🎯 Objectif: {target_millions} millions de layouts")
        print(f"📦 Blocs de: {layouts_per_block:,} layouts")
        print(f"📁 Sortie: {self.output_dir}")
    
    def generate_valid_grid(self, n_empty, max_attempts=100):
        """
        Génère une grille valide avec vérification de connectivité complète.
        
        Args:
            n_empty: Nombre de cases vides requises
            max_attempts: Nombre maximum de tentatives
            
        Returns:
            grid: Grille valide ou None si échec
        """
        total_cells = self.grid_size * self.grid_size
        n_walls = total_cells - n_empty
        
        for attempt in range(max_attempts):
            # Créer une grille vide
            grid = [[self.empty_char for _ in range(self.grid_size)] 
                   for _ in range(self.grid_size)]
            
            # Forcer les bordures à être des murs
            for i in range(self.grid_size):
                grid[0][i] = self.wall_char  # Bordure haute
                grid[self.grid_size-1][i] = self.wall_char  # Bordure basse
                grid[i][0] = self.wall_char  # Bordure gauche
                grid[i][self.grid_size-1] = self.wall_char  # Bordure droite
            
            # Compter les murs de bordure déjà placés
            border_walls = 4 * self.grid_size - 4  # Périmètre
            remaining_walls = n_walls - border_walls
            
            if remaining_walls < 0:
                continue  # Impossible avec ce n_empty
            
            # Placer les murs restants aléatoirement à l'intérieur
            inner_positions = [(i, j) for i in range(1, self.grid_size-1) 
                              for j in range(1, self.grid_size-1)]
            
            if remaining_walls > len(inner_positions):
                continue  # Impossible
            
            # Éviter les blocs 2x2 de murs
            wall_positions = self.place_walls_safely(inner_positions, remaining_walls)
            if wall_positions is None:
                continue
            
            for i, j in wall_positions:
                grid[i][j] = self.wall_char
            
            # Vérification COMPLÈTE de connectivité
            if self.is_fully_connected(grid):
                return grid
        
        return None  # Échec après max_attempts
    
    def place_walls_safely(self, inner_positions, n_walls):
        """Place les murs en évitant les blocs 2x2."""
        max_attempts = 50
        
        for attempt in range(max_attempts):
            wall_positions = random.sample(inner_positions, n_walls)
            
            # Vérifier qu'il n'y a pas de blocs 2x2 de murs
            if not self.has_2x2_wall_blocks(wall_positions):
                return wall_positions
        
        return None
    
    def has_2x2_wall_blocks(self, wall_positions):
        """Vérifie s'il y a des blocs 2x2 de murs."""
        wall_set = set(wall_positions)
        
        for i, j in wall_positions:
            # Vérifier le bloc 2x2 avec (i,j) en haut-gauche
            block_2x2 = [(i, j), (i, j+1), (i+1, j), (i+1, j+1)]
            if all(pos in wall_set for pos in block_2x2):
                return True
        
        return False
    
    def is_fully_connected(self, grid):
        """
        Vérifie que TOUTES les cases vides sont connectées.
        
        Args:
            grid: Grille à vérifier
            
        Returns:
            bool: True si toutes les cases vides sont connectées
        """
        # Trouver toutes les cellules vides
        empty_cells = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == self.empty_char:
                    empty_cells.append((i, j))
        
        if len(empty_cells) < 2:
            return len(empty_cells) == 1  # Acceptable si une seule case vide
        
        # BFS à partir de la première case vide
        start = empty_cells[0]
        reachable = self.bfs_all_reachable(grid, start)
        
        # Vérifier que TOUTES les cases vides sont accessibles
        return len(reachable) == len(empty_cells)
    
    def bfs_all_reachable(self, grid, start):
        """
        BFS pour trouver toutes les cases accessibles depuis start.
        
        Returns:
            set: Ensemble de toutes les positions accessibles
        """
        queue = deque([start])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < self.grid_size and 0 <= nj < self.grid_size and
                    (ni, nj) not in visited and grid[ni][nj] == self.empty_char):
                    
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        return visited
    
    def place_objects_safely(self, grid):
        """
        Place les objets sur la grille en vérifiant l'accessibilité.
        
        Args:
            grid: Grille de base (avec seulement murs et espaces vides)
            
        Returns:
            dict: Layout complet avec objets placés ou None si échec
        """
        # Copier la grille
        layout_grid = [row[:] for row in grid]
        
        # Trouver toutes les positions vides disponibles
        empty_positions = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if layout_grid[i][j] == self.empty_char:
                    empty_positions.append((i, j))
        
        if len(empty_positions) < 8:  # Minimum requis pour objets essentiels
            return None
        
        # Objets obligatoires
        required_objects = [
            'player1', 'player2', 'onion_dispenser', 'tomato_dispenser',
            'pot', 'dish_dispenser', 'serving_station'
        ]
        
        # Placer les joueurs d'abord (pas sur les bordures)
        inner_positions = [(i, j) for i, j in empty_positions 
                          if 1 < i < self.grid_size-2 and 1 < j < self.grid_size-2]
        
        if len(inner_positions) < 2:
            return None
        
        # Placer les joueurs
        player_positions = random.sample(inner_positions, 2)
        layout_grid[player_positions[0][0]][player_positions[0][1]] = '1'
        layout_grid[player_positions[1][0]][player_positions[1][1]] = '2'
        
        # Retirer les positions des joueurs des positions disponibles
        available_positions = [pos for pos in empty_positions 
                             if pos not in player_positions]
        
        # Placer les autres objets obligatoires
        if len(available_positions) < len(required_objects) - 2:
            return None
        
        object_positions = random.sample(available_positions, len(required_objects) - 2)
        
        for i, obj_type in enumerate(['onion_dispenser', 'tomato_dispenser', 
                                    'pot', 'dish_dispenser', 'serving_station']):
            pos = object_positions[i]
            layout_grid[pos[0]][pos[1]] = self.objects[obj_type]
        
        # Placer quelques comptoirs sur les positions restantes
        remaining_positions = [pos for pos in available_positions 
                             if pos not in object_positions]
        
        n_counters = min(len(remaining_positions), random.randint(1, 3))
        counter_positions = random.sample(remaining_positions, n_counters)
        
        for pos in counter_positions:
            layout_grid[pos[0]][pos[1]] = self.objects['counter']
        
        # Vérifier que tous les objets sont accessibles
        if self.are_all_objects_accessible(layout_grid):
            return self.grid_to_layout_dict(layout_grid)
        
        return None
    
    def are_all_objects_accessible(self, grid):
        """
        Vérifie que tous les objets importants sont accessibles par les deux joueurs.
        
        Args:
            grid: Grille avec objets placés
            
        Returns:
            bool: True si tous les objets sont accessibles
        """
        # Trouver les positions des joueurs
        player1_pos = None
        player2_pos = None
        object_positions = []
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if grid[i][j] == '1':
                    player1_pos = (i, j)
                elif grid[i][j] == '2':
                    player2_pos = (i, j)
                elif grid[i][j] in ['O', 'T', 'P', 'D', 'S']:  # Objets essentiels
                    object_positions.append((i, j))
        
        if not player1_pos or not player2_pos:
            return False
        
        # Vérifier que chaque joueur peut atteindre tous les objets essentiels
        for player_pos in [player1_pos, player2_pos]:
            reachable = self.bfs_all_reachable_with_objects(grid, player_pos)
            
            for obj_pos in object_positions:
                if obj_pos not in reachable:
                    return False
        
        return True
    
    def bfs_all_reachable_with_objects(self, grid, start):
        """BFS modifié pour les grilles avec objets."""
        queue = deque([start])
        visited = {start}
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        while queue:
            current = queue.popleft()
            
            for di, dj in directions:
                ni, nj = current[0] + di, current[1] + dj
                
                if (0 <= ni < self.grid_size and 0 <= nj < self.grid_size and
                    (ni, nj) not in visited and grid[ni][nj] != self.wall_char):
                    
                    visited.add((ni, nj))
                    queue.append((ni, nj))
        
        return visited
    
    def grid_to_layout_dict(self, grid):
        """Convertit une grille en dictionnaire de layout."""
        grid_str = '\n'.join([''.join(row) for row in grid])
        
        return {
            'grid': grid_str,
            'n_empty': sum(row.count(self.empty_char) for row in grid),
            'hash': self.grid_to_hash(grid)
        }
    
    def grid_to_hash(self, grid):
        """Génère un hash unique pour une grille."""
        grid_str = ''.join(''.join(row) for row in grid)
        return hashlib.md5(grid_str.encode()).hexdigest()[:16]
    
    def generate_layout_block(self, block_id, layouts_count, density_mix=None):
        """
        Génère un bloc de layouts validés avec diversité de densités.
        
        Args:
            block_id: ID du bloc
            layouts_count: Nombre de layouts à générer
            density_mix: Mix de densités (None = automatique)
        """
        if density_mix is None:
            # Mix automatique équilibré
            density_mix = {
                'sparse': 0.2,
                'medium': 0.4, 
                'open': 0.3,
                'very_open': 0.1
            }
        
        print(f"📦 Génération bloc {block_id}: {layouts_count} layouts")
        for density_type, ratio in density_mix.items():
            target_count = int(layouts_count * ratio)
            print(f"  🎯 {density_type}: {target_count} layouts (n_empty {self.n_empty_ranges[density_type][0]}-{self.n_empty_ranges[density_type][1]})")
        
        layouts = []
        generated_hashes = set()
        
        for density_type, ratio in density_mix.items():
            target_count = int(layouts_count * ratio)
            n_empty_min, n_empty_max = self.n_empty_ranges[density_type]
            
            generated_for_density = 0
            attempts = 0
            max_attempts = target_count * 10  # Limite pour éviter les boucles infinies
            
            while generated_for_density < target_count and attempts < max_attempts:
                attempts += 1
                
                # Choisir n_empty aléatoirement dans la plage
                n_empty = random.randint(n_empty_min, n_empty_max)
                
                # Générer grille de base
                base_grid = self.generate_valid_grid(n_empty)
                if base_grid is None:
                    continue
                
                # Placer les objets
                layout = self.place_objects_safely(base_grid)
                if layout is None:
                    continue
                
                # Vérifier l'unicité
                layout_hash = layout['hash']
                if layout_hash in generated_hashes:
                    continue
                
                # Ajouter le layout
                layout['density_type'] = density_type
                layout['block_id'] = block_id
                layout['layout_id'] = f"B{block_id:04d}_L{len(layouts):06d}"
                
                layouts.append(layout)
                generated_hashes.add(layout_hash)
                generated_for_density += 1
        
        return layouts
    
    def save_layout_block(self, layouts, block_id):
        """Sauvegarde un bloc de layouts."""
        if not layouts:
            return None
        
        filename = f"validated_block_{block_id:06d}.json"
        filepath = self.output_dir / filename
        
        block_data = {
            'block_id': block_id,
            'timestamp': time.time(),
            'total_layouts': len(layouts),
            'density_distribution': self.get_density_distribution(layouts),
            'layouts': layouts
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(block_data, f, indent=2, ensure_ascii=False)
        
        file_size = filepath.stat().st_size / (1024 * 1024)  # MB
        print(f"💾 Bloc sauvé: {filename} ({file_size:.1f} MB)")
        
        return filepath
    
    def get_density_distribution(self, layouts):
        """Calcule la distribution des densités."""
        distribution = {}
        for layout in layouts:
            density_type = layout.get('density_type', 'unknown')
            distribution[density_type] = distribution.get(density_type, 0) + 1
        return distribution
    
    def generate_worker(self, args):
        """Worker pour génération parallèle."""
        block_id, layouts_per_block, density_mix = args
        
        # Réinitialiser le seed pour chaque processus
        random.seed()
        
        layouts = self.generate_layout_block(block_id, layouts_per_block, density_mix)
        
        if layouts:
            self.save_layout_block(layouts, block_id)
            return len(layouts)
        
        return 0
    
    def run_massive_generation(self, processes=None):
        """Lance la génération massive."""
        if processes is None:
            processes = min(mp.cpu_count() - 1, 8)  # Limiter pour éviter surcharge
        
        # Calculer les blocs nécessaires
        total_layouts = int(self.target_total)
        num_blocks = max(1, total_layouts // self.layouts_per_block)
        
        if total_layouts % self.layouts_per_block > 0:
            num_blocks += 1
        
        print(f"🚀 Génération VALIDÉE avec {processes} processus")
        print(f"📊 Configuration:")
        print(f"   - Objectif: {total_layouts:,} layouts")
        print(f"   - Blocs: {num_blocks}")
        print(f"   - Layouts par bloc: {self.layouts_per_block:,}")
        print(f"   - Processus: {processes}")
        
        # Préparer les arguments pour chaque bloc
        block_args = []
        for block_id in range(num_blocks):
            # Calculer le nombre de layouts pour ce bloc
            if block_id == num_blocks - 1:
                # Dernier bloc : prendre le reste
                layouts_for_block = total_layouts - (block_id * self.layouts_per_block)
            else:
                layouts_for_block = self.layouts_per_block
            
            block_args.append((block_id, layouts_for_block, None))
        
        start_time = time.time()
        total_generated = 0
        
        if processes == 1:
            # Mode séquentiel pour debug
            for args in block_args:
                generated = self.generate_worker(args)
                total_generated += generated
        else:
            # Mode parallèle
            with mp.Pool(processes) as pool:
                results = pool.map(self.generate_worker, block_args)
                total_generated = sum(results)
        
        duration = time.time() - start_time
        
        print(f"\n🎉 GÉNÉRATION VALIDÉE TERMINÉE!")
        print(f"📊 Résultats:")
        print(f"   - Layouts générés: {total_generated:,}")
        print(f"   - Blocs créés: {num_blocks}")
        print(f"   - Durée: {duration:.1f}s ({duration/60:.1f} min)")
        if duration > 0:
            print(f"   - Vitesse: {total_generated/duration:.0f} layouts/seconde")
        
        return total_generated > 0

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(
        description='Générateur VALIDÉ de layouts 8x8 pour Overcooked'
    )
    
    parser.add_argument(
        '--millions',
        type=float,
        default=0.001,
        help='Nombre de millions de layouts à générer (défaut: 0.001)'
    )
    
    parser.add_argument(
        '--block-size',
        type=int,
        default=5000,
        help='Nombre de layouts par bloc (défaut: 5000)'
    )
    
    parser.add_argument(
        '--processes',
        type=int,
        default=None,
        help='Nombre de processus (défaut: auto)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialiser le générateur
        generator = ValidatedLayoutGenerator8x8(
            target_millions=args.millions,
            layouts_per_block=args.block_size
        )
        
        # Lancer la génération
        success = generator.run_massive_generation(processes=args.processes)
        
        if success:
            print("✅ Génération validée réussie!")
        else:
            print("❌ Échec de la génération")
            exit(1)
            
    except Exception as e:
        print(f"💥 Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
