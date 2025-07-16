#!/usr/bin/env python3
"""
Test script to verify the triple slowdown system:
1. Trial start slowdown with ai_trial_start_speed
2. Asset change slowdown with ai_asset_slow_speed  
3. Recipe change slowdown with ai_slow_speed
"""

import json
import sys
import os

def test_asset_slowdown_config():
    """Test that all asset slowdown parameters are configured correctly."""
    print("=== Testing Asset Slowdown Configuration ===")
    
    try:
        with open('/home/cesar/python-projects/Overcooked-coop-voice/config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config.json: {e}")
        return False
    
    # Check that all required parameters are present
    required_params = {
        'ai_slowdown_enabled': bool,
        'ai_base_speed': int, 
        'ai_slow_speed': int,
        'ai_trial_start_speed': int,
        'ai_asset_slow_speed': int,
        'ai_slow_duration': int,
        'ai_trial_start_duration': int,
        'ai_asset_slow_duration': int,
        'ai_trial_start_slowdown': bool,
        'ai_trial_start_first_only': bool,
        'ai_asset_slowdown_enabled': bool
    }
    
    missing = []
    type_errors = []
    
    for param, expected_type in required_params.items():
        if param not in config:
            missing.append(param)
        else:
            value = config[param]
            if not isinstance(value, expected_type):
                type_errors.append(f"{param}: expected {expected_type.__name__}, got {type(value).__name__}")
    
    if missing:
        print(f"❌ Missing configuration parameters: {missing}")
        return False
    
    if type_errors:
        print(f"❌ Type errors: {type_errors}")
        return False
    
    print(f"✅ All required parameters present with correct types")
    print(f"   ai_base_speed: {config['ai_base_speed']} (normal speed)")
    print(f"   ai_slow_speed: {config['ai_slow_speed']} (recipe change slowdown)")
    print(f"   ai_trial_start_speed: {config['ai_trial_start_speed']} (trial start slowdown)")
    print(f"   ai_asset_slow_speed: {config['ai_asset_slow_speed']} (asset change slowdown)")
    print(f"   ai_slow_duration: {config['ai_slow_duration']} (recipe change duration)")
    print(f"   ai_trial_start_duration: {config['ai_trial_start_duration']} (trial start duration)")
    print(f"   ai_asset_slow_duration: {config['ai_asset_slow_duration']} (asset change duration)")
    print(f"   ai_slowdown_enabled: {config['ai_slowdown_enabled']}")
    print(f"   ai_trial_start_slowdown: {config['ai_trial_start_slowdown']}")
    print(f"   ai_asset_slowdown_enabled: {config['ai_asset_slowdown_enabled']}")
    print(f"   ai_trial_start_first_only: {config['ai_trial_start_first_only']}")
    
    return True

def test_code_structure():
    """Test that the code contains the expected triple slowdown structure."""
    print("\n=== Testing Code Structure ===")
    
    try:
        with open('/home/cesar/python-projects/Overcooked-coop-voice/game.py', 'r') as f:
            code = f.read()
    except Exception as e:
        print(f"❌ Failed to load game.py: {e}")
        return False
    
    # Check for required variables and methods
    required_elements = [
        'trial_start_ticks_per_ai_action',
        'trial_start_slow_remaining_ticks',
        'asset_slow_ticks_per_ai_action',
        'asset_slow_remaining_ticks', 
        'last_asset_intention',
        'ai_asset_slowdown_enabled',
        'ai_asset_slow_speed',
        'ai_asset_slow_duration',
        '_check_asset_intention_change',
        'TRIAL START SLOW',
        'ASSET CHANGE SLOW',
        'RECIPE CHANGE SLOW'
    ]
    
    missing = []
    for element in required_elements:
        if element not in code:
            missing.append(element)
    
    if missing:
        print(f"❌ Missing code elements: {missing}")
        return False
    
    print("✅ All required code elements found")
    print("   - trial_start_ticks_per_ai_action variable")
    print("   - asset_slow_ticks_per_ai_action variable")
    print("   - trial_start_slow_remaining_ticks variable") 
    print("   - asset_slow_remaining_ticks variable")
    print("   - last_asset_intention variable")
    print("   - _check_asset_intention_change method")
    print("   - ai_asset_slowdown_enabled configuration usage")
    print("   - Separate log messages for all three slowdown types")
    
    return True

def test_speed_values():
    """Test that the speed values make sense."""
    print("\n=== Testing Speed Value Logic ===")
    
    try:
        with open('/home/cesar/python-projects/Overcooked-coop-voice/config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config.json: {e}")
        return False
    
    base_speed = config['ai_base_speed']
    recipe_slow_speed = config['ai_slow_speed']
    trial_start_speed = config['ai_trial_start_speed']
    asset_slow_speed = config['ai_asset_slow_speed']
    
    issues = []
    
    # Check that slowdown speeds are actually slower (higher values = slower)
    if recipe_slow_speed <= base_speed:
        issues.append(f"Recipe slowdown speed ({recipe_slow_speed}) should be higher than base speed ({base_speed})")
    
    if trial_start_speed <= base_speed:
        issues.append(f"Trial start speed ({trial_start_speed}) should be higher than base speed ({base_speed})")
    
    if asset_slow_speed <= base_speed:
        issues.append(f"Asset slowdown speed ({asset_slow_speed}) should be higher than base speed ({base_speed})")
    
    # Check that speeds are reasonable values
    if base_speed < 1 or base_speed > 50:
        issues.append(f"Base speed ({base_speed}) seems unreasonable (should be 1-50)")
    
    if recipe_slow_speed < 1 or recipe_slow_speed > 500:
        issues.append(f"Recipe slow speed ({recipe_slow_speed}) seems unreasonable (should be 1-500)")
    
    if trial_start_speed < 1 or trial_start_speed > 500:
        issues.append(f"Trial start speed ({trial_start_speed}) seems unreasonable (should be 1-500)")
    
    if asset_slow_speed < 1 or asset_slow_speed > 500:
        issues.append(f"Asset slow speed ({asset_slow_speed}) seems unreasonable (should be 1-500)")
    
    if issues:
        for issue in issues:
            print(f"⚠️  {issue}")
        return False
    
    print("✅ Speed values are logical")
    print(f"   Normal speed: {base_speed} (faster)")
    print(f"   Recipe change slowdown: {recipe_slow_speed} (slower)")
    print(f"   Trial start slowdown: {trial_start_speed} (slower)")
    print(f"   Asset change slowdown: {asset_slow_speed} (slower)")
    
    return True

def test_priority_system():
    """Test the expected priority system."""
    print("\n=== Testing Priority System ===")
    
    try:
        with open('/home/cesar/python-projects/Overcooked-coop-voice/game.py', 'r') as f:
            code = f.read()
    except Exception as e:
        print(f"❌ Failed to load game.py: {e}")
        return False
    
    # Check the order in _update_ai_speed method
    update_method_start = code.find('def _update_ai_speed(self):')
    if update_method_start == -1:
        print("❌ _update_ai_speed method not found")
        return False
    
    # Find the next method to limit our search
    next_method = code.find('def ', update_method_start + 1)
    if next_method == -1:
        method_code = code[update_method_start:]
    else:
        method_code = code[update_method_start:next_method]
    
    # Check priority order in the if-elif chain
    trial_start_pos = method_code.find('trial_start_slow_remaining_ticks > 0')
    asset_pos = method_code.find('asset_slow_remaining_ticks > 0')  
    recipe_pos = method_code.find('elif self.slow_remaining_ticks > 0')
    
    if trial_start_pos == -1 or asset_pos == -1 or recipe_pos == -1:
        print("❌ Could not find all slowdown conditions")
        return False
    
    if not (trial_start_pos < asset_pos < recipe_pos):
        print("❌ Priority order is incorrect")
        print(f"   Expected: trial_start < asset < recipe")
        print(f"   Found: trial_start({trial_start_pos}) < asset({asset_pos}) < recipe({recipe_pos})")
        return False
    
    print("✅ Priority system is correct")
    print("   1. Trial start slowdown (highest priority)")
    print("   2. Asset change slowdown (medium priority)")
    print("   3. Recipe change slowdown (lowest priority)")
    print("   4. Normal speed (default)")
    
    return True

def main():
    """Run all tests."""
    print("Testing Triple Slowdown System (Trial Start + Asset + Recipe)")
    print("=" * 70)
    
    tests = [
        test_asset_slowdown_config,
        test_code_structure,
        test_speed_values,
        test_priority_system
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("🎉 All tests passed! Triple slowdown system is properly configured.")
        print("\nSummary:")
        print("- Three separate slowdown speeds are now configured")
        print("- Trial start slowdown uses 'ai_trial_start_speed' parameter")
        print("- Asset change slowdown uses 'ai_asset_slow_speed' parameter")
        print("- Recipe change slowdown uses 'ai_slow_speed' parameter")
        print("- Priority: trial start > asset change > recipe change > normal")
        print("- All configuration parameters are present and valid")
    else:
        print("⚠️  Some tests failed. Please check the output above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
