#!/usr/bin/env python3
"""
Test script pour diagnostiquer les problèmes de layouts dans layout_evaluator.py
"""

import sys
import os

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, '/home/cesar/python-projects/Overcooked-coop-voice')

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from layout_evaluator import LayoutEvaluator

def test_layout_loading():
    """Test le chargement direct d'un layout."""
    print("=== TEST DE CHARGEMENT DE LAYOUT ===")
    
    # Test 1: Chargement direct via OvercookedGridworld
    try:
        layout_name = "generation_cesar/demo/V1_layout_combination_01"
        print(f"🧪 Test 1: Chargement direct de '{layout_name}'")
        mdp = OvercookedGridworld.from_layout_name(layout_name)
        print(f"✅ Succès! MDP créé avec dimensions {mdp.width}x{mdp.height}")
        print(f"   Positions joueurs: {mdp.start_player_positions}")
        print(f"   Commandes initiales: {len(mdp.start_all_orders) if hasattr(mdp, 'start_all_orders') else 'N/A'}")
    except Exception as e:
        print(f"❌ Échec chargement direct: {e}")
        print(f"   Type d'erreur: {type(e).__name__}")
        return False
    
    # Test 2: Via LayoutEvaluator.discover_layouts()
    print(f"\n🧪 Test 2: Découverte de layouts via LayoutEvaluator")
    try:
        evaluator = LayoutEvaluator(
            layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/demo",
            verbose=True
        )
        layouts = evaluator.discover_layouts()
        print(f"✅ {len(layouts)} layouts découverts: {layouts[:3]}...")
    except Exception as e:
        print(f"❌ Échec découverte: {e}")
        return False
    
    # Test 3: Création d'agents
    print(f"\n🧪 Test 3: Création d'agents")
    try:
        success, agent_group = evaluator.create_agent_group(mdp)
        if success:
            print(f"✅ Agents créés avec succès")
        else:
            print(f"❌ Échec création agents")
            return False
    except Exception as e:
        print(f"❌ Erreur création agents: {e}")
        return False
    
    # Test 4: Évaluation complète d'un layout
    print(f"\n🧪 Test 4: Évaluation d'un layout")
    try:
        result = evaluator.evaluate_single_layout("V1_layout_combination_01")
        print(f"Résultat évaluation:")
        print(f"  - Viable: {result.get('viable', 'N/A')}")
        print(f"  - Erreur: {result.get('error', 'Aucune')}")
        print(f"  - Parties jouées: {result.get('games_played', 'N/A')}")
        print(f"  - Taux complétion: {result.get('completion_rate', 'N/A')}")
        
        if not result.get('viable', False):
            print(f"❌ Layout considéré comme non viable!")
            return False
        else:
            print(f"✅ Layout viable!")
    except Exception as e:
        print(f"❌ Erreur évaluation: {e}")
        return False
    
    return True

def test_all_demo_layouts():
    """Test tous les layouts du répertoire demo."""
    print(f"\n=== TEST DE TOUS LES LAYOUTS DEMO ===")
    
    evaluator = LayoutEvaluator(
        layouts_directory="./overcooked_ai_py/data/layouts/generation_cesar/demo",
        num_games_per_layout=1,  # Juste 1 partie pour le test
        verbose=False  # Mode rapide
    )
    
    layouts = evaluator.discover_layouts()
    viable_count = 0
    
    for i, layout in enumerate(layouts[:5], 1):  # Test seulement les 5 premiers
        print(f"[{i}/5] Test {layout}...", end=" ")
        try:
            result = evaluator.evaluate_single_layout(layout)
            if result.get('viable', False):
                print("✅ VIABLE")
                viable_count += 1
            else:
                print(f"❌ NON VIABLE: {result.get('error', 'Raison inconnue')}")
        except Exception as e:
            print(f"❌ ERREUR: {e}")
    
    print(f"\n📊 Résultat: {viable_count}/5 layouts viables")
    return viable_count > 0

if __name__ == "__main__":
    print("🔍 DIAGNOSTIC LAYOUT_EVALUATOR")
    print("=" * 50)
    
    # Test le working directory
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Vérifier la structure des fichiers
    demo_path = "/home/cesar/python-projects/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar/demo"
    if os.path.exists(demo_path):
        layout_files = [f for f in os.listdir(demo_path) if f.endswith('.layout')]
        print(f"📄 {len(layout_files)} fichiers .layout trouvés dans demo/")
    else:
        print(f"❌ Répertoire demo non trouvé: {demo_path}")
        sys.exit(1)
    
    # Test unitaire
    success = test_layout_loading()
    
    if success:
        print(f"\n🎯 Test unitaire réussi, test en lot...")
        test_all_demo_layouts()
    else:
        print(f"\n💥 Test unitaire échoué - diagnostic nécessaire")
