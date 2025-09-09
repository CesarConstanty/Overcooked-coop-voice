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
        
        # Convertir en texte
        grid_text = decoded_bytes.decode('utf-8')
        
        # Séparer par lignes et nettoyer
        lines = grid_text.strip().split('\n')
        
        # Créer la grille
        grid = []
        for i in range(height):
            if i < len(lines):
                line = lines[i]
                # Assurer que la ligne fait exactement la bonne largeur
                if len(line) < width:
                    line += ' ' * (width - len(line))
                elif len(line) > width:
                    line = line[:width]
                grid.append(list(line))
            else:
                # Ligne vide si pas assez de données
                grid.append([' '] * width)
        
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
            if isinstance(positions, list) and len(positions) > 0:
                obj_positions = []
                for pos in positions:
                    if isinstance(pos, list) and len(pos) >= 2:
                        # Format [[x, y]] depuis le générateur
                        obj_positions.append((pos[0], pos[1]))
                    elif isinstance(pos, (tuple, list)) and len(pos) >= 2:
                        # Format (x, y) ou [x, y]
                        obj_positions.append((pos[0], pos[1]))
                objects[obj_type] = obj_positions
        
        return {
            'grid': grid,
            'objects': objects,
            'object_positions': objects,  # Compatibilité avec l'évaluateur
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
