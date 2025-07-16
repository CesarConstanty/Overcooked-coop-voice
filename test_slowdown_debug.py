#!/usr/bin/env python3
"""
Test script to debug the AI slowdown system.
This will help us verify that the slowdown logic is working correctly.
"""

import sys
import os

# Add the project directory to the Python path
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice')

from game import PlanningGame

def test_slowdown_initialization():
    """Test that the slowdown system initializes correctly."""
    print("=== Testing Slowdown Initialization ===")
    
    # Test configuration with slowdown enabled
    config = {
        "blocs": {"0": ["cramped_room"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 30,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 20
    }
    
    try:
        game = PlanningGame(config=config, step=0)
        
        # Check initialization
        print(f"✓ ai_slowdown_enabled: {game.ai_slowdown_enabled}")
        print(f"✓ base_ticks_per_ai_action: {game.base_ticks_per_ai_action}")
        print(f"✓ slow_ticks_per_ai_action: {game.slow_ticks_per_ai_action}")
        print(f"✓ slow_duration_ticks: {game.slow_duration_ticks}")
        print(f"✓ ticks_per_ai_action: {game.ticks_per_ai_action}")
        print(f"✓ slow_remaining_ticks: {game.slow_remaining_ticks}")
        print(f"✓ last_recipe_intention: {game.last_recipe_intention}")
        
        # Check that methods exist
        assert hasattr(game, '_update_ai_speed'), "Missing _update_ai_speed method"
        assert hasattr(game, '_check_recipe_intention_change'), "Missing _check_recipe_intention_change method"
        print("✓ Slowdown methods exist")
        
        return True
        
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False

def test_slowdown_methods():
    """Test the slowdown methods work correctly."""
    print("\n=== Testing Slowdown Methods ===")
    
    config = {
        "blocs": {"0": ["cramped_room"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 30,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5
    }
    
    try:
        game = PlanningGame(config=config, step=0)
        
        # Test manual slowdown trigger
        print("Testing manual slowdown trigger...")
        
        # Trigger slowdown manually
        game.slow_remaining_ticks = 5
        initial_speed = game.ticks_per_ai_action
        print(f"Initial speed: {initial_speed}")
        
        # Update speed (should be slow)
        game._update_ai_speed()
        slow_speed = game.ticks_per_ai_action
        print(f"Speed during slowdown: {slow_speed}")
        
        assert slow_speed == game.slow_ticks_per_ai_action, f"Expected {game.slow_ticks_per_ai_action}, got {slow_speed}"
        print("✓ AI speed correctly set to slow during slowdown")
        
        # Simulate ticks until slowdown ends
        for i in range(5):
            game._update_ai_speed()
            print(f"  Tick {i+1}: speed={game.ticks_per_ai_action}, remaining={game.slow_remaining_ticks}")
        
        # Check speed returns to normal
        final_speed = game.ticks_per_ai_action
        print(f"Final speed: {final_speed}")
        
        assert final_speed == game.base_ticks_per_ai_action, f"Expected {game.base_ticks_per_ai_action}, got {final_speed}"
        print("✓ AI speed correctly returned to normal after slowdown")
        
        return True
        
    except Exception as e:
        print(f"✗ Slowdown methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_disabled_slowdown():
    """Test behavior when slowdown is disabled."""
    print("\n=== Testing Disabled Slowdown ===")
    
    config = {
        "blocs": {"0": ["cramped_room"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 30,
        "ai_slowdown_enabled": False,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 20
    }
    
    try:
        game = PlanningGame(config=config, step=0)
        
        # Manually trigger slowdown (should be ignored)
        game.slow_remaining_ticks = 10
        initial_speed = game.ticks_per_ai_action
        
        # Update speed (should remain at base speed)
        game._update_ai_speed()
        final_speed = game.ticks_per_ai_action
        
        assert final_speed == game.base_ticks_per_ai_action, f"Expected {game.base_ticks_per_ai_action}, got {final_speed}"
        print("✓ AI speed remains at base speed when slowdown is disabled")
        
        return True
        
    except Exception as e:
        print(f"✗ Disabled slowdown test failed: {e}")
        return False

if __name__ == "__main__":
    print("Debugging AI Slowdown System")
    print("="*50)
    
    tests = [
        test_slowdown_initialization,
        test_slowdown_methods,
        test_with_disabled_slowdown
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "="*50)
    print("SUMMARY:")
    if all(results):
        print("✓ All tests passed! The slowdown system is working correctly.")
    else:
        print("✗ Some tests failed. Check the output above for details.")
        failed_tests = [test.__name__ for test, result in zip(tests, results) if not result]
        print(f"Failed tests: {', '.join(failed_tests)}")
