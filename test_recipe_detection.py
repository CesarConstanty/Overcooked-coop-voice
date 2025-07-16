#!/usr/bin/env python3
"""
Test to check if the recipe intention change detection is working properly.
"""

import sys
import os

# Add the project directory to the Python path
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice')

from game import PlanningGame

def test_recipe_intention_detection():
    """Test if the recipe intention change detection is working."""
    print("=== Testing Recipe Intention Detection ===")
    
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
        
        print(f"Game initialized. Checking state...")
        print(f"  ai_slowdown_enabled: {game.ai_slowdown_enabled}")
        print(f"  planning_agent_id exists: {hasattr(game, 'planning_agent_id')}")
        
        if hasattr(game, 'planning_agent_id'):
            print(f"  planning_agent_id: {game.planning_agent_id}")
            print(f"  planning_agent_id in npc_policies: {game.planning_agent_id in game.npc_policies}")
        
        print(f"  npc_policies keys: {list(game.npc_policies.keys())}")
        print(f"  last_recipe_intention: {game.last_recipe_intention}")
        
        # Test the method manually
        print("\nTesting _check_recipe_intention_change manually...")
        
        # Call with current state
        game._check_recipe_intention_change()
        print(f"After first call: last_recipe_intention = {game.last_recipe_intention}")
        
        # Let's try to understand what get_intentions returns
        if hasattr(game, 'planning_agent_id') and game.planning_agent_id in game.npc_policies:
            print(f"\nTesting get_intentions...")
            intentions = game.get_intentions(game.planning_agent_id)
            print(f"Current intentions: {intentions}")
            
            if intentions:
                print(f"  Type: {type(intentions)}")
                print(f"  Keys: {list(intentions.keys()) if isinstance(intentions, dict) else 'Not a dict'}")
                if isinstance(intentions, dict) and 'recipe' in intentions:
                    print(f"  Recipe: {intentions['recipe']}")
        else:
            print("Cannot test get_intentions - planning_agent_id not available")
        
        return True
        
    except Exception as e:
        print(f"✗ Recipe intention detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_activated_game():
    """Test with an activated game to see if the agent gets properly initialized."""
    print("\n=== Testing with Activated Game ===")
    
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
        
        print("Before activation:")
        print(f"  planning_agent_id exists: {hasattr(game, 'planning_agent_id')}")
        print(f"  npc_policies: {list(game.npc_policies.keys())}")
        
        # Activate the game
        print("\nActivating game...")
        game.activate()
        
        print("After activation:")
        print(f"  planning_agent_id exists: {hasattr(game, 'planning_agent_id')}")
        if hasattr(game, 'planning_agent_id'):
            print(f"  planning_agent_id: {game.planning_agent_id}")
        print(f"  npc_policies: {list(game.npc_policies.keys())}")
        
        # Add players to see if that helps
        print("\nAdding players...")
        game.add_player("human_player", is_human=True)
        game.add_player("ai_player", is_human=False)
        
        print("After adding players:")
        print(f"  players: {game.players}")
        print(f"  human_players: {game.human_players}")
        print(f"  npc_players: {game.npc_players}")
        print(f"  npc_policies: {list(game.npc_policies.keys())}")
        
        if hasattr(game, 'planning_agent_id'):
            print(f"  planning_agent_id: {game.planning_agent_id}")
            if game.planning_agent_id in game.npc_policies:
                print("  ✓ planning_agent_id is in npc_policies")
                
                # Test intentions
                intentions = game.get_intentions(game.planning_agent_id)
                print(f"  intentions: {intentions}")
                
                # Test the recipe change detection
                print("\nTesting recipe intention change detection...")
                game._check_recipe_intention_change()
                print(f"  last_recipe_intention after first call: {game.last_recipe_intention}")
                
            else:
                print("  ✗ planning_agent_id is NOT in npc_policies")
        else:
            print("  ✗ planning_agent_id does not exist")
        
        return True
        
    except Exception as e:
        print(f"✗ Activated game test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Recipe Intention Detection Test")
    print("="*50)
    
    tests = [
        test_recipe_intention_detection,
        test_with_activated_game
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
        print("✓ All recipe intention tests completed.")
    else:
        print("✗ Some tests failed.")
        failed_tests = [test.__name__ for test, result in zip(tests, results) if not result]
        print(f"Failed tests: {', '.join(failed_tests)}")
