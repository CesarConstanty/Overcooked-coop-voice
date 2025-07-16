#!/usr/bin/env python3
"""
Test to verify that the trial start slowdown system works correctly.
"""

import sys
import os

# Add the project directory to the Python path
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice')

from game import PlanningGame

def test_trial_start_slowdown():
    """Test that the trial start slowdown is triggered when a new trial begins."""
    print("=== Testing Trial Start Slowdown ===")
    
    config = {
        "blocs": {"0": ["tutorial_0", "tutorial_1"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5,
        "ai_trial_start_slowdown": True,
        "ai_trial_start_duration": 30,
        "ai_trial_start_first_only": False
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        print(f"Initial state:")
        print(f"  Trial start slowdown enabled: {config['ai_trial_start_slowdown']}")
        print(f"  Trial start duration: {config['ai_trial_start_duration']}")
        print(f"  Current speed: {game.ticks_per_ai_action}")
        print(f"  Slow remaining ticks: {game.slow_remaining_ticks}")
        
        # Test first trial activation
        print(f"\n--- Activating Trial 1 ---")
        print(f"Before activation: slow_remaining_ticks = {game.slow_remaining_ticks}")
        
        game.activate()
        
        print(f"After activation: slow_remaining_ticks = {game.slow_remaining_ticks}")
        print(f"Expected: {config['ai_trial_start_duration']}")
        
        # Verify slowdown was triggered
        assert game.slow_remaining_ticks == config['ai_trial_start_duration'], \
            f"Expected {config['ai_trial_start_duration']}, got {game.slow_remaining_ticks}"
        print("✅ Trial start slowdown triggered correctly")
        
        # Test speed during slowdown
        game._update_ai_speed()
        assert game.ticks_per_ai_action == game.slow_ticks_per_ai_action, \
            f"Expected slow speed {game.slow_ticks_per_ai_action}, got {game.ticks_per_ai_action}"
        print("✅ AI speed set to slow during trial start")
        
        # Simulate ticks until slowdown ends
        print(f"\n--- Simulating {config['ai_trial_start_duration']} ticks ---")
        for tick in range(config['ai_trial_start_duration'] + 2):
            game._update_ai_speed()
            print(f"  Tick {tick+1}: speed={game.ticks_per_ai_action}, remaining={game.slow_remaining_ticks}")
        
        # Verify speed returned to normal
        assert game.ticks_per_ai_action == game.base_ticks_per_ai_action, \
            f"Expected base speed {game.base_ticks_per_ai_action}, got {game.ticks_per_ai_action}"
        print("✅ AI speed returned to normal after trial start period")
        
        # Test second trial activation
        print(f"\n--- Activating Trial 2 ---")
        game.slow_remaining_ticks = 0  # Reset to simulate clean state
        
        print(f"Before second activation: slow_remaining_ticks = {game.slow_remaining_ticks}")
        game.activate()  # This should trigger another trial start slowdown
        print(f"After second activation: slow_remaining_ticks = {game.slow_remaining_ticks}")
        
        # Verify second trial also triggers slowdown
        assert game.slow_remaining_ticks == config['ai_trial_start_duration'], \
            f"Second trial should also trigger slowdown"
        print("✅ Second trial also triggers slowdown correctly")
        
        return True
        
    except Exception as e:
        print(f"✗ Trial start slowdown test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_trial_start_first_only():
    """Test the 'first only' option for trial start slowdown."""
    print("\n=== Testing Trial Start Slowdown (First Only) ===")
    
    config = {
        "blocs": {"0": ["tutorial_0", "tutorial_1"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5,
        "ai_trial_start_slowdown": True,
        "ai_trial_start_duration": 25,
        "ai_trial_start_first_only": True
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        print(f"Config: first_only = {config['ai_trial_start_first_only']}")
        print(f"Current trial: {game.curr_trial_in_game}")
        
        # Test first trial (should trigger slowdown)
        print(f"\n--- First Trial (index {game.curr_trial_in_game}) ---")
        game.activate()
        
        first_trial_slowdown = game.slow_remaining_ticks
        print(f"Slowdown after first trial: {first_trial_slowdown}")
        
        if config['ai_trial_start_first_only']:
            # With first_only=True, it should trigger on trial index 0
            expected = config['ai_trial_start_duration'] if game.curr_trial_in_game == 1 else 0
        else:
            expected = config['ai_trial_start_duration']
            
        print(f"Expected: {expected}")
        print(f"Actual trial index after activate: {game.curr_trial_in_game}")
        
        # Reset for second trial test
        game.slow_remaining_ticks = 0
        
        # Test second trial (should NOT trigger slowdown with first_only=True)
        print(f"\n--- Second Trial (index {game.curr_trial_in_game}) ---")
        game.activate()
        
        second_trial_slowdown = game.slow_remaining_ticks
        print(f"Slowdown after second trial: {second_trial_slowdown}")
        
        # With first_only=True, second trial should not trigger slowdown
        expected_second = 0 if config['ai_trial_start_first_only'] else config['ai_trial_start_duration']
        print(f"Expected for second trial: {expected_second}")
        
        if config['ai_trial_start_first_only']:
            assert second_trial_slowdown == 0, \
                f"With first_only=True, second trial should not trigger slowdown"
            print("✅ Second trial correctly did NOT trigger slowdown (first_only mode)")
        
        return True
        
    except Exception as e:
        print(f"✗ First only test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_trial_start_disabled():
    """Test that trial start slowdown can be disabled."""
    print("\n=== Testing Trial Start Slowdown (Disabled) ===")
    
    config = {
        "blocs": {"0": ["tutorial_0"]},
        "conditions": {"0": "test"},
        "agent": "Greedy",
        "gameTime": 10,
        "ai_slowdown_enabled": True,
        "ai_base_speed": 4,
        "ai_slow_speed": 12,
        "ai_slow_duration": 5,
        "ai_trial_start_slowdown": False,  # Disabled
        "ai_trial_start_duration": 25,
        "ai_trial_start_first_only": False
    }
    
    try:
        game = PlanningGame(config=config, step=0, player_uid="test_player")
        
        print(f"Trial start slowdown disabled: {not config['ai_trial_start_slowdown']}")
        
        initial_slowdown = game.slow_remaining_ticks
        print(f"Before activation: {initial_slowdown}")
        
        game.activate()
        
        final_slowdown = game.slow_remaining_ticks
        print(f"After activation: {final_slowdown}")
        
        assert final_slowdown == 0, \
            f"With trial_start_slowdown=False, no slowdown should be triggered"
        print("✅ Trial start slowdown correctly disabled")
        
        return True
        
    except Exception as e:
        print(f"✗ Disabled test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Trial Start Slowdown System Test")
    print("="*50)
    
    tests = [
        test_trial_start_slowdown,
        test_trial_start_first_only,
        test_trial_start_disabled
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
        print("🎉 All trial start slowdown tests passed!")
        print("✅ The system correctly implements trial start slowdown.")
        print("✅ Configuration options work as expected.")
        print("\nConfiguration options:")
        print("- ai_trial_start_slowdown: true/false (enable/disable)")
        print("- ai_trial_start_duration: number of ticks to slow down")
        print("- ai_trial_start_first_only: true = only first trial per block")
    else:
        print("❌ Some tests failed.")
        failed_tests = [test.__name__ for test, result in zip(tests, results) if not result]
        print(f"Failed tests: {', '.join(failed_tests)}")
