#!/usr/bin/env python3
"""
Final integration test for both recipe intention change and trial start slowdown systems.
"""

import sys
import os

# Add the project directory to the Python path
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice')

from game import PlanningGame

def test_combined_slowdown_systems():
    """Test that both slowdown systems work together correctly."""
    print("=== Testing Combined Slowdown Systems ===")
    
    config = {
        "blocs": {"0": ["tutorial_0"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,
        # Recipe intention change slowdown
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5,
        # Trial start slowdown
        "ai_trial_start_slowdown": True,
        "ai_trial_start_duration": 10,
        "ai_trial_start_first_only": False
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        print("Configuration:")
        print(f"  Recipe change slowdown: {game.ai_slowdown_enabled}")
        print(f"  Trial start slowdown: {config['ai_trial_start_slowdown']}")
        print(f"  Base speed: {game.base_ticks_per_ai_action}")
        print(f"  Slow speed: {game.slow_ticks_per_ai_action}")
        
        # Test 1: Trial start slowdown
        print("\n--- Test 1: Trial Start Activation ---")
        game.activate()
        
        assert game.slow_remaining_ticks == config['ai_trial_start_duration'], \
            f"Trial start slowdown not triggered"
        print("✅ Trial start slowdown triggered")
        
        # Test 2: Speed during trial start slowdown
        game._update_ai_speed()
        assert game.ticks_per_ai_action == game.slow_ticks_per_ai_action, \
            f"Speed not set to slow during trial start"
        print("✅ Speed correctly set to slow during trial start")
        
        # Test 3: Simulate some ticks
        print("\n--- Test 3: Simulating Trial Start Period ---")
        for tick in range(3):
            game._update_ai_speed()
            print(f"  Tick {tick+1}: speed={game.ticks_per_ai_action}, remaining={game.slow_remaining_ticks}")
        
        # Test 4: Simulate recipe intention change during trial start slowdown
        print("\n--- Test 4: Recipe Change During Trial Start ---")
        if hasattr(game, 'planning_agent_id') and game.planning_agent_id in game.npc_policies:
            # Simulate first recipe intention
            agent_policy = game.npc_policies[game.planning_agent_id]
            agent_policy.intentions = {'recipe': 'onion_soup', 'goal': 'cook', 'agent_name': 'greedy'}
            game._check_recipe_intention_change()
            print(f"  First recipe set: {game.last_recipe_intention}")
            
            # Simulate recipe change
            agent_policy.intentions = {'recipe': 'tomato_soup', 'goal': 'cook', 'agent_name': 'greedy'}
            initial_remaining = game.slow_remaining_ticks
            game._check_recipe_intention_change()
            game._update_ai_speed()
            
            print(f"  Recipe changed to: {game.last_recipe_intention}")
            print(f"  Remaining ticks before: {initial_remaining}")
            print(f"  Remaining ticks after: {game.slow_remaining_ticks}")
            
            # The recipe change should reset the slowdown duration (and _update_ai_speed decrements it by 1)
            expected_remaining = config['ai_slow_duration'] - 1  # -1 because _update_ai_speed was called
            assert game.slow_remaining_ticks == expected_remaining, \
                f"Recipe change should reset slowdown to {expected_remaining}, got {game.slow_remaining_ticks}"
            print("✅ Recipe intention change correctly resets slowdown")
        
        # Test 5: Complete slowdown cycle
        print("\n--- Test 5: Complete Slowdown Cycle ---")
        while game.slow_remaining_ticks > 0:
            game._update_ai_speed()
        
        # Make sure we call _update_ai_speed one more time to ensure speed is updated
        game._update_ai_speed()
        
        assert game.ticks_per_ai_action == game.base_ticks_per_ai_action, \
            f"Speed should return to normal after all slowdowns end, got {game.ticks_per_ai_action} expected {game.base_ticks_per_ai_action}"
        print("✅ Speed correctly returned to normal after all slowdowns")
        
        print("\n🎉 All combined system tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Combined systems test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Combined AI Slowdown Systems Integration Test")
    print("="*60)
    
    success = test_combined_slowdown_systems()
    
    print("\n" + "="*60)
    if success:
        print("🎯 SYSTÈME COMPLET VALIDÉ!")
        print("\n✅ Le système de ralentissement IA inclut maintenant :")
        print("   1. Ralentissement lors des changements d'intention de recette")
        print("   2. Ralentissement automatique au début de chaque essai")
        print("   3. Configuration flexible pour différents scénarios")
        print("   4. Compatibilité et interaction entre les deux systèmes")
        print("\n🚀 Le système est prêt pour utilisation en production!")
    else:
        print("❌ Des problèmes ont été détectés dans l'intégration des systèmes.")
