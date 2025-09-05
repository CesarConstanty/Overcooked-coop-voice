#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier la sélection finale des layouts
"""

import json
import sys
from pathlib import Path

# Ajouter le dossier scripts au path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.append(str(scripts_dir))

# Import en spécifiant le module avec underscore
import importlib.util
spec = importlib.util.spec_from_file_location("final_selector", scripts_dir / "4_final_selector.py")
final_selector_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(final_selector_module)

FinalLayoutSelector = final_selector_module.FinalLayoutSelector

def test_configuration():
    """Test la lecture de la configuration."""
    print("🧪 Test de la configuration...")
    
    selector = FinalLayoutSelector()
    config = selector.config
    
    final_count = config["pipeline_config"]["selection"]["final_layouts_count"]
    print(f"✅ Nombre de layouts finaux configuré: {final_count}")
    
    output_dir = config["pipeline_config"]["output"]["final_layouts_dir"]
    print(f"✅ Dossier de sortie: {output_dir}")
    
    return True

def test_final_selection():
    """Test la sélection finale avec des données fictives."""
    print("🧪 Test de la sélection finale...")
    
    selector = FinalLayoutSelector()
    
    # Créer des données fictives d'évaluation
    fake_evaluations = []
    for i in range(10):
        fake_eval = {
            "layout_id": f"test_layout_{i:03d}",
            "recipe_group_id": f"recipe_group_{i%3}",
            "combined_id": f"test_combined_{i:03d}",
            "layout_grid": f"XXXXXXX\nX   T X\nX XYX X\nX OXY X\nXX Y2SX\nP Y 1XX\nXXXDXXX",
            "estimated_metrics": {
                "cooperation_gain": 50 + i * 5,
                "connectivity_score": 0.7 + i * 0.02,
                "distance_efficiency": 0.3 + i * 0.05
            },
            "structural_analysis": {
                "total_cells": 49,
                "working_cells": 30
            },
            "recipe_group_info": {
                "recipe_count": 6
            }
        }
        fake_evaluations.append(fake_eval)
    
    # Test de conversion au format final
    test_eval = fake_evaluations[0]
    test_eval["selection_score"] = 85.5  # Ajouter un score fictif
    
    final_layout = selector.convert_to_final_format(test_eval)
    
    print(f"✅ Conversion au format final réussie")
    print(f"   Grid présente: {'grid' in final_layout}")
    print(f"   Start orders: {len(final_layout['start_all_orders'])} recettes")
    print(f"   Counter goals: {final_layout['counter_goals']}")
    print(f"   Valeurs: onion={final_layout['onion_value']}, tomato={final_layout['tomato_value']}")
    
    return True

def main():
    """Fonction principale de test."""
    print("🔬 TEST DE LA SÉLECTION FINALE DES LAYOUTS")
    print("="*60)
    
    try:
        test_configuration()
        print()
        test_final_selection()
        print()
        print("✅ Tous les tests sont passés avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors des tests: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
