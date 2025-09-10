#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de compression et décompression des layouts Overcooked
"""

import json
import gzip
import base64
import zlib
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import hashlib

class LayoutDecompressor:
    """Décompresseur pour les layouts sauvegardés."""
    
    @staticmethod
    def decode_grid_from_base64(encoded_grid: str, width: int = 8, height: int = 8) -> List[List[str]]:
        """
        Décode une grille depuis sa représentation base64.
        
        Args:
            encoded_grid: Grille encodée en base64
            width: Largeur de la grille
            height: Hauteur de la grille
            
        Returns:
            Grille décodée sous forme de matrice 2D
        """
        # Décoder depuis base64
        decoded_bytes = base64.b64decode(encoded_grid)
        
        # Convertir en array numpy
        grid_array = np.frombuffer(decoded_bytes, dtype=np.uint8)
        
        # Mapping des codes vers les caractères
        CODE_TO_CHAR = {
            0: ' ',  # EMPTY
            1: 'X',  # COUNTER/WALL
            2: 'O',  # ONION_DISPENSER
            3: 'T',  # TOMATO_DISPENSER
            4: 'P',  # POT
            5: 'D',  # DISH_DISPENSER
            6: 'S'   # SERVING_LOC
        }
        
        # Créer la grille
        grid = []
        for i in range(height):
            row = []
            for j in range(width):
                if i * width + j < len(grid_array):
                    code = grid_array[i * width + j]
                    char = CODE_TO_CHAR.get(code, ' ')
                    row.append(char)
                else:
                    row.append(' ')
            grid.append(row)
        
        return grid
    
    @staticmethod
    def decompress_layout(compressed_layout: Dict[str, Any]) -> Dict[str, Any]:
        """
        Décompresse un layout depuis son format compressé.
        
        Args:
            compressed_layout: Layout compressé avec clés 'g', 'h', 'ne', 'nw', 'op'
            
        Returns:
            Layout décompressé avec 'grid' et 'objects'
        """
        # Décoder la grille
        grid = LayoutDecompressor.decode_grid_from_base64(compressed_layout['g'])
        
        # Extraire les positions des objets
        object_positions = compressed_layout.get('op', {})
        
        # Convertir les objets en format standard
        objects = {}
        for obj_type, positions in object_positions.items():
            if isinstance(positions, list) and len(positions) == 2:
                # Position unique
                objects[obj_type] = [(positions[0], positions[1])]
            elif isinstance(positions, list) and len(positions) > 2:
                # Multiples positions (par paires)
                obj_positions = []
                for i in range(0, len(positions), 2):
                    if i + 1 < len(positions):
                        obj_positions.append((positions[i], positions[i + 1]))
                objects[obj_type] = obj_positions
        
        return {
            'grid': grid,
            'objects': objects,
            'hash': compressed_layout.get('h', ''),
            'ne_count': compressed_layout.get('ne', 0),
            'nw_count': compressed_layout.get('nw', 0)
        }
    
    @staticmethod
    def load_layouts_from_batch(file_path: str) -> List[Dict[str, Any]]:
        """
        Charge tous les layouts depuis un fichier batch compressé.
        
        Args:
            file_path: Chemin vers le fichier batch .json.gz
            
        Returns:
            Liste des layouts décompressés
        """
        layouts = []
        
        with gzip.open(file_path, 'rt') as f:
            line = f.readline().strip()
            if not line:
                return layouts
                
            # Charger le niveau supérieur
            batch_data = json.loads(line)
            
            # Décompresser le contenu
            compressed_data = batch_data['data']
            decompressed = zlib.decompress(base64.b64decode(compressed_data))
            batch_content = json.loads(decompressed.decode('utf-8'))
            
            # Traiter chaque layout compressé
            compressed_layouts = batch_content.get('compressed_layouts', [])
            
            for compressed_layout in compressed_layouts:
                try:
                    decompressed_layout = LayoutDecompressor.decompress_layout(compressed_layout)
                    layouts.append(decompressed_layout)
                except Exception as e:
                    print(f"Erreur lors de la décompression d'un layout: {e}")
                    continue
        
        return layouts

# Classes factices pour compatibilité avec le générateur
class LayoutCompressor:
    """Compresseur factice pour compatibilité."""
    pass

class LayoutBatchManager:
    """Manager de batch factice pour compatibilité."""
    pass
