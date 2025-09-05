#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de sauvegarde au format final
"""

import json
import sys
import tempfile
from pathlib import Path

# Import du module
scripts_dir = Path(__file__).parent / "scripts"
sys.path.append(str(scripts_dir))

import importlib.util
spec = importlib.util.spec_from_file_location("final_selector", scripts_dir / "4_final_selector.py")
final_selector_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(final_selector_module)

FinalLayoutSelector = final_selector_module.FinalLayoutSelector

def test_format_layout():
    """Test la sauvegarde au format final."""
    print("🧪 Test de sauvegarde au format final...")
    
    selector = FinalLayoutSelector()
    
    # Données de test
    layout_content = {
        "grid": "\n                XXXXXXX\n                X     T\n                X YX  X\n                X  OX X\n                XX Y 2S\n                P  Y 1X\n                XXXXDXX",
        "start_all_orders": [
            {"ingredients": ["onion"]}, 
            {"ingredients": ["onion", "tomato"]}, 
            {"ingredients": ["tomato", "tomato"]}, 
            {"ingredients": ["onion", "onion", "tomato"]}, 
            {"ingredients": ["onion", "tomato", "tomato"]}, 
            {"ingredients": ["tomato", "tomato", "tomato"]}
        ],
        "counter_goals": [],
        "onion_value": 3,
        "tomato_value": 2,
        "onion_time": 9,
        "tomato_time": 6
    }
    
    # Sauvegarder dans un fichier temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.layout', delete=False) as f:
        selector.save_layout_with_multiline_grid(f, layout_content)
        temp_file = f.name
    
    # Lire et afficher le résultat
    with open(temp_file, 'r') as f:
        content = f.read()
    
    print("📄 Contenu généré:")
    print("-" * 40)
    print(content)
    print("-" * 40)
    
    # Nettoyer
    Path(temp_file).unlink()
    
    return True

if __name__ == "__main__":
    test_format_layout()
