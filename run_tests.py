#!/usr/bin/env python3
"""
Test runner for BluetoothStreamer Audio Player
Runs all unit tests and integration tests.
"""

import unittest
import sys
import os

# Add tests directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run all tests."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test modules
    test_modules = [
        'tests.test_audio_player',
        'tests.test_stream_cleanup',
        'tests.test_latency',
        'tests.test_integration',
        'tests.test_round8_components',
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            print(f"Loaded tests from {module_name}")
        except ImportError as e:
            print(f"Warning: Could not import {module_name}: {e}")
        except Exception as e:
            print(f"Error loading {module_name}: {e}")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)

