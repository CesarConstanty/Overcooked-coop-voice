#!/usr/bin/env python3
"""
Final validation test for AI slowdown system.

This script tests:
1. PlanningGame AI slowdown functionality
2. OvercookedTutorial remains unaffected 
3. Config key compatibility
4. No KeyError exceptions
"""

import sys
import json
from time import time
from game import OvercookedGame, PlanningGame, OvercookedTutorial

def test_config_loading():
    """Test that config loads correctly."""
    print("Testing config loading...")
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Check slowdown keys exist
        required_keys = ['ai_slowdown_enabled', 'ai_base_speed', 'ai_slow_speed', 'ai_slow_duration']
        for key in required_keys:
            if key not in config:
                print(f"❌ Missing config key: {key}")
                return False
        
        print("✅ Config loading successful")
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False

def test_planning_game_init():
    """Test PlanningGame initialization with slowdown."""
    print("\nTesting PlanningGame initialization...")
    try:
        # Create a minimal config for testing
        test_config = {
            "ai_slowdown_enabled": True,
            "ai_base_speed": 5,
            "ai_slow_speed": 20,
            "ai_slow_duration": 10,
            "layouts": ["asymmetric_advantages"],
            "ai_types": ["PP"],
            "trials": 1,
            "blocs": {"0": ["asymmetric_advantages"]},
            "conditions": {"0": "test"},
            "agent": "Greedy",
            "gameTime": 120,
            "mechanic": "recipe"
        }
        
        game = PlanningGame(
            step=0,
            player_uid="test",
            config=test_config
        )
        
        # Check slowdown attributes
        assert hasattr(game, 'ticks_per_ai_action'), "Missing ticks_per_ai_action"
        assert hasattr(game, 'base_ticks_per_ai_action'), "Missing base_ticks_per_ai_action"
        assert hasattr(game, 'slow_ticks_per_ai_action'), "Missing slow_ticks_per_ai_action"
        assert hasattr(game, 'slow_duration_ticks'), "Missing slow_duration_ticks"
        assert hasattr(game, '_update_ai_speed'), "Missing _update_ai_speed method"
        assert hasattr(game, '_check_recipe_intention_change'), "Missing _check_recipe_intention_change method"
        
        # Check values
        assert game.base_ticks_per_ai_action == 5, f"Expected base speed 5, got {game.base_ticks_per_ai_action}"
        assert game.slow_ticks_per_ai_action == 20, f"Expected slow speed 20, got {game.slow_ticks_per_ai_action}"
        assert game.slow_duration_ticks == 10, f"Expected slow duration 10, got {game.slow_duration_ticks}"
        
        print("✅ PlanningGame initialization successful")
        return True
    except Exception as e:
        print(f"❌ PlanningGame initialization failed: {e}")
        return False

def test_tutorial_init():
    """Test OvercookedTutorial initialization remains unchanged."""
    print("\nTesting OvercookedTutorial initialization...")
    try:
        tutorial = OvercookedTutorial(
            participant_uid="test",
            trial_id=0
        )
        
        # Check that tutorial doesn't have slowdown attributes
        slowdown_attrs = ['_update_ai_speed', '_check_recipe_intention_change']
        for attr in slowdown_attrs:
            if hasattr(tutorial, attr):
                print(f"❌ Tutorial should not have {attr}")
                return False
        
        # Check that tutorial has fixed ticks_per_ai_action
        assert hasattr(tutorial, 'ticks_per_ai_action'), "Tutorial missing ticks_per_ai_action"
        assert tutorial.ticks_per_ai_action == 5, f"Expected tutorial AI speed 5, got {tutorial.ticks_per_ai_action}"
        
        print("✅ OvercookedTutorial initialization successful")
        return True
    except Exception as e:
        print(f"❌ OvercookedTutorial initialization failed: {e}")
        return False

def test_get_data_compatibility():
    """Test that get_data() returns config key for both game types."""
    print("\nTesting get_data() compatibility...")
    try:
        # Test PlanningGame
        test_config = {
            "ai_slowdown_enabled": True,
            "ai_base_speed": 5,
            "ai_slow_speed": 20,
            "ai_slow_duration": 10,
            "layouts": ["asymmetric_advantages"],
            "ai_types": ["PP"],
            "trials": 1,
            "blocs": {"0": ["asymmetric_advantages"]},
            "conditions": {"0": "test"},
            "agent": "Greedy",
            "gameTime": 120,
            "mechanic": "recipe"
        }
        
        planning_game = PlanningGame(
            step=0,
            player_uid="test",
            config=test_config
        )
        
        # Initialize some required attributes for get_data()
        planning_game.trajectory = [{"time_elapsed": 0, "score": 0, "human_action_count": 0, "agent_action_count": 0, "agent_stuck_loop": 0, "hl_switch": 0, "achieved_orders_len": 0}]
        planning_game.infos = [{}]
        planning_game.curr_layout = "test"
        planning_game.curr_trial_in_game = 0
        planning_game.trial_id = "test_trial_0"  # Initialize trial_id for testing
        
        data = planning_game.get_data()
        assert "config" in data, "PlanningGame get_data() missing 'config' key"
        
        # Test OvercookedTutorial
        tutorial = OvercookedTutorial(
            participant_uid="test",
            trial_id=0
        )
        
        # Initialize required attributes
        tutorial.trajectory = [{"time_elapsed": 0, "score": 0}]
        tutorial.curr_layout = "test"
        tutorial.step = 0
        
        data = tutorial.get_data()
        assert "config" in data, "OvercookedTutorial get_data() missing 'config' key"
        
        print("✅ get_data() compatibility successful")
        return True
    except Exception as e:
        print(f"❌ get_data() compatibility failed: {e}")
        return False

def test_slowdown_disabled():
    """Test that slowdown can be disabled via config."""
    print("\nTesting slowdown disabled configuration...")
    try:
        test_config = {
            "ai_slowdown_enabled": False,
            "ai_base_speed": 5,
            "ai_slow_speed": 20,
            "ai_slow_duration": 10,
            "layouts": ["asymmetric_advantages"],
            "ai_types": ["PP"],
            "trials": 1,
            "blocs": {"0": ["asymmetric_advantages"]},
            "conditions": {"0": "test"},
            "agent": "Greedy",
            "gameTime": 120,
            "mechanic": "recipe"
        }
        
        game = PlanningGame(
            step=0,
            player_uid="test",
            config=test_config
        )
        
        # When disabled, should use base speed
        assert game.ticks_per_ai_action == game.base_ticks_per_ai_action, \
            f"Expected ticks_per_ai_action to equal base speed when disabled"
        
        print("✅ Slowdown disabled configuration successful")
        return True
    except Exception as e:
        print(f"❌ Slowdown disabled configuration failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🚀 Running final validation tests for AI slowdown system...")
    print("=" * 60)
    
    tests = [
        test_config_loading,
        test_planning_game_init,
        test_tutorial_init,
        test_get_data_compatibility,
        test_slowdown_disabled,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! AI slowdown system is working correctly.")
        print("\nSUMMARY:")
        print("- PlanningGame has configurable AI slowdown")
        print("- OvercookedTutorial uses fixed AI speed (no slowdown)")
        print("- Config compatibility maintained")
        print("- No KeyError exceptions")
        print("- Slowdown can be enabled/disabled via config")
        return True
    else:
        print("❌ Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
