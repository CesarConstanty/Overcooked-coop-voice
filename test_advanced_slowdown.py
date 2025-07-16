#!/usr/bin/env python3
"""
Advanced test to simulate a real game session and verify the slowdown system works during gameplay.
"""

import sys
import os
import time

# Add the project directory to the Python path
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice')

from game import PlanningGame

def test_real_game_simulation():
    """Test the slowdown system during a simulated game session."""
    print("=== Testing Real Game Simulation ===")
    
    config = {
        "blocs": {"0": ["tutorial_0"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,  # Short game for testing
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        print(f"Game initialized with slowdown enabled: {game.ai_slowdown_enabled}")
        print(f"Base speed: {game.base_ticks_per_ai_action}, Slow speed: {game.slow_ticks_per_ai_action}")
        
        # Activate the game
        game.activate()
        print("Game activated")
        
        # Simulate some game ticks
        print("\nSimulating game ticks...")
        for i in range(20):
            # Enqueue a dummy action for human player
            game.enqueue_action('player1', 'STAY')
            
            # Apply actions (this should call our slowdown methods)
            print(f"\n--- Tick {i+1} ---")
            print(f"Before apply_actions: speed={game.ticks_per_ai_action}, slow_remaining={game.slow_remaining_ticks}")
            
            # This will trigger apply_actions which calls our slowdown methods
            status = game.tick()
            
            print(f"After apply_actions: speed={game.ticks_per_ai_action}, slow_remaining={game.slow_remaining_ticks}")
            print(f"Status: {status}")
            
            # Stop if game is finished
            if game.is_finished():
                print("Game finished")
                break
                
            # Small delay to see the output
            time.sleep(0.1)
        
        print("\n✓ Game simulation completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Game simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_method_calls():
    """Test that our methods are actually being called."""
    print("\n=== Testing Method Calls ===")
    
    config = {
        "blocs": {"0": ["tutorial_0"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 3
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        # Add call counters
        original_update = game._update_ai_speed
        original_check = game._check_recipe_intention_change
        
        update_calls = 0
        check_calls = 0
        
        def counting_update():
            nonlocal update_calls
            update_calls += 1
            print(f"[CALL_COUNTER] _update_ai_speed called {update_calls} times")
            return original_update()
        
        def counting_check():
            nonlocal check_calls
            check_calls += 1
            print(f"[CALL_COUNTER] _check_recipe_intention_change called {check_calls} times")
            return original_check()
        
        # Replace methods with counting versions
        game._update_ai_speed = counting_update
        game._check_recipe_intention_change = counting_check
        
        # Activate and run a few ticks
        game.activate()
        
        for i in range(5):
            game.enqueue_action('player1', 'STAY')
            game.tick()
        
        print(f"\nMethod call summary:")
        print(f"  _update_ai_speed called: {update_calls} times")
        print(f"  _check_recipe_intention_change called: {check_calls} times")
        
        if update_calls > 0 and check_calls > 0:
            print("✓ Both methods are being called during gameplay")
            return True
        else:
            print("✗ Methods are not being called")
            return False
        
    except Exception as e:
        print(f"✗ Method call test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Advanced AI Slowdown System Test")
    print("="*50)
    
    tests = [
        test_method_calls,
        test_real_game_simulation
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
        print("✓ All advanced tests passed! The slowdown system is being called during gameplay.")
    else:
        print("✗ Some tests failed. Check the output above for details.")
        failed_tests = [test.__name__ for test, result in zip(tests, results) if not result]
        print(f"Failed tests: {', '.join(failed_tests)}")
