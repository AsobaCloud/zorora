#!/usr/bin/env python3
"""Verification script for zorora routing improvements."""

import sys
import importlib

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("TESTING MODULE IMPORTS")
    print("=" * 60)

    modules = [
        'config',
        'router',
        'planner',
        'tool_executor',
        'tool_registry',
        'turn_processor',
        'repl',
        'llm_client',
        'conversation',
        'ui',
    ]

    all_passed = True
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            all_passed = False

    print()
    return all_passed

def test_config():
    """Test that routing config is set correctly."""
    print("=" * 60)
    print("TESTING ROUTING CONFIGURATION")
    print("=" * 60)

    import config

    required_attrs = [
        'USE_JSON_ROUTING',
        'USE_HEURISTIC_ROUTER',
        'ENABLE_CONFIDENCE_FALLBACK',
        'CONFIDENCE_THRESHOLD_HIGH',
        'CONFIDENCE_THRESHOLD_LOW',
        'FALLBACK_MODEL_ENDPOINT',
    ]

    all_passed = True
    for attr in required_attrs:
        if hasattr(config, attr):
            value = getattr(config, attr)
            print(f"✓ {attr}: {value}")
        else:
            print(f"✗ {attr}: NOT FOUND")
            all_passed = False

    # Validate threshold values
    if hasattr(config, 'CONFIDENCE_THRESHOLD_HIGH') and hasattr(config, 'CONFIDENCE_THRESHOLD_LOW'):
        if config.CONFIDENCE_THRESHOLD_HIGH >= config.CONFIDENCE_THRESHOLD_LOW:
            print(f"✓ Thresholds valid (HIGH >= LOW)")
        else:
            print(f"✗ Thresholds invalid (HIGH < LOW)")
            all_passed = False

    print()
    return all_passed

def test_heuristic_router():
    """Test HeuristicRouter functionality."""
    print("=" * 60)
    print("TESTING HEURISTIC ROUTER")
    print("=" * 60)

    from router import HeuristicRouter

    router = HeuristicRouter()

    test_cases = [
        ("search for Python news", "web_search"),
        ("write a function to validate emails", "use_codestral"),
        ("read config.py", "read_file"),
        ("list files in src", "list_files"),
        ("run npm install", "run_shell"),
        ("generate an image of a sunset", "generate_image"),
    ]

    all_passed = True
    for input_text, expected_tool in test_cases:
        result = router.route(input_text)
        if result and result["tool"] == expected_tool:
            print(f"✓ '{input_text[:30]}...' → {expected_tool}")
        elif result:
            print(f"✗ '{input_text[:30]}...' → {result['tool']} (expected {expected_tool})")
            all_passed = False
        else:
            print(f"✗ '{input_text[:30]}...' → No match (expected {expected_tool})")
            all_passed = False

    print()
    return all_passed

def test_json_parser():
    """Test JSON tool call parser."""
    print("=" * 60)
    print("TESTING JSON PARSER")
    print("=" * 60)

    from tool_executor import ToolExecutor
    from tool_registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    test_cases = [
        (
            '{"tool": "web_search", "input": "latest news", "confidence": 0.95}',
            "web_search",
            0.95
        ),
        (
            '{"tool": "use_codestral", "input": "write function", "confidence": 0.88}',
            "use_codestral",
            0.88
        ),
    ]

    all_passed = True
    for json_text, expected_tool, expected_conf in test_cases:
        result = executor.parse_json_tool_call(json_text)
        if result and result["tool"] == expected_tool and result["confidence"] == expected_conf:
            print(f"✓ Parsed {expected_tool} (confidence: {expected_conf})")
        elif result:
            print(f"✗ Parsed {result.get('tool')} (confidence: {result.get('confidence')}) - expected {expected_tool} ({expected_conf})")
            all_passed = False
        else:
            print(f"✗ Failed to parse JSON")
            all_passed = False

    print()
    return all_passed

def test_planner():
    """Test TaskPlanner can be instantiated."""
    print("=" * 60)
    print("TESTING TASK PLANNER")
    print("=" * 60)

    from planner import TaskPlanner

    # Test multi-step detection
    test_cases = [
        ("research React hooks and create a custom hook", True),
        ("read config.py and suggest improvements", True),
        ("write a function to parse JSON", False),
        ("analyze the code then implement changes", True),
    ]

    # We can't fully test planner without LLM, but we can test detection
    print("Testing multi-step detection:")

    # Create a mock planner (without LLM)
    class MockLLM:
        pass

    class MockExecutor:
        pass

    planner = TaskPlanner(MockLLM(), MockExecutor())

    all_passed = True
    for input_text, should_plan in test_cases:
        result = planner.should_plan(input_text)
        if result == should_plan:
            print(f"✓ '{input_text[:40]}...' → {result}")
        else:
            print(f"✗ '{input_text[:40]}...' → {result} (expected {should_plan})")
            all_passed = False

    print()
    return all_passed

def test_file_existence():
    """Test that all required files exist."""
    print("=" * 60)
    print("TESTING FILE EXISTENCE")
    print("=" * 60)

    from pathlib import Path

    required_files = [
        'config.py',
        'router.py',
        'planner.py',
        'tool_executor.py',
        'turn_processor.py',
        'repl.py',
        'system_prompt.txt',
        'system_prompt_legacy.txt',
    ]

    all_passed = True
    for filename in required_files:
        path = Path(filename)
        if path.exists():
            print(f"✓ {filename}")
        else:
            print(f"✗ {filename}: NOT FOUND")
            all_passed = False

    print()
    return all_passed

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ZORORA ROUTING IMPROVEMENTS - VERIFICATION SCRIPT")
    print("=" * 60 + "\n")

    results = []

    results.append(("File Existence", test_file_existence()))
    results.append(("Module Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Heuristic Router", test_heuristic_router()))
    results.append(("JSON Parser", test_json_parser()))
    results.append(("Task Planner", test_planner()))

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("🎉 All tests passed! Zorora is ready to run.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
