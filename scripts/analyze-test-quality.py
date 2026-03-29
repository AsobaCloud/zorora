"""Analyze test file quality: detect mock-heavy patterns, dead mocks, and config overrides.

Usage:
    python scripts/analyze-test-quality.py tests/test_foo.py [tests/test_bar.py ...]

Outputs a JSON dict keyed by file path, each entry containing:
    test_count         - number of test_* functions/methods
    mock_counts        - dict with counts per mock pattern
    patch_targets      - list of dotted paths from @patch("...") decorators
    overridden_env_vars - list of env var names from monkeypatch.setenv(...)
    dead_mocks         - list of patch targets whose attribute doesn't exist
    flags              - list of quality flag strings

Flags:
    MOCK HEAVY        - total mock count > 3 * test_count (and test_count > 0)
    CONFIG OVERRIDDEN - all test functions (>=2) share a common patch target
    DEAD MOCKS        - at least one @patch target attribute doesn't exist
"""
from __future__ import annotations

import ast
import importlib
import json
import pathlib
import sys
from typing import Any


def _extract_patch_string(decorator: ast.expr) -> str | None:
    """Return the first string argument of a @patch(...) decorator, or None."""
    # @patch("some.target") → ast.Call with func being ast.Name or ast.Attribute
    if not isinstance(decorator, ast.Call):
        return None

    func = decorator.func

    # Check func is `patch` or `patch.object`
    is_patch_name = isinstance(func, ast.Name) and func.id == "patch"
    is_patch_attr = (
        isinstance(func, ast.Attribute)
        and func.attr == "object"
        and isinstance(func.value, ast.Name)
        and func.value.id == "patch"
    )
    is_patch_plain_attr = (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "patch"
        and func.attr not in ("object",)
    )

    if not (is_patch_name or is_patch_attr or is_patch_plain_attr):
        return None

    # For @patch.object we don't extract a string target
    if is_patch_attr:
        return None  # @patch.object — no dotted string to extract

    # For @patch("dotted.path") or @patch("dotted.path", value)
    if decorator.args:
        first = decorator.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _is_patch_call(decorator: ast.expr) -> bool:
    """Return True if the decorator is any form of @patch(...) or @patch.object(...)."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    if isinstance(func, ast.Name) and func.id == "patch":
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "patch"
    return False


def _analyze_file(path: pathlib.Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return {
            "test_count": 0,
            "mock_counts": {"patch": 0, "MagicMock": 0, "Mock": 0, "setattr": 0, "setenv": 0, "delenv": 0},
            "patch_targets": [],
            "overridden_env_vars": [],
            "dead_mocks": [],
            "flags": [],
        }

    mock_counts: dict[str, int] = {
        "patch": 0,
        "MagicMock": 0,
        "Mock": 0,
        "setattr": 0,
        "setenv": 0,
        "delenv": 0,
    }
    patch_targets: list[str] = []
    overridden_env_vars: list[str] = []
    test_count = 0

    # Per-test-function patch target sets, for CONFIG OVERRIDDEN detection
    # Maps test function name → set of patch targets on that function
    test_patch_targets: dict[str, set[str]] = {}
    # Per-test-function patch counts (all @patch calls), for MOCK HEAVY per-function check
    test_patch_counts: dict[str, int] = {}

    # Walk AST for all function definitions (module-level and inside classes)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            is_test = func_name.startswith("test_")

            if is_test:
                test_count += 1
                test_patch_targets[func_name] = set()
                test_patch_counts[func_name] = 0

            # Count @patch decorators on this function
            for dec in node.decorator_list:
                if _is_patch_call(dec):
                    mock_counts["patch"] += 1
                    if is_test:
                        test_patch_counts[func_name] += 1
                    target = _extract_patch_string(dec)
                    if target is not None:
                        if target not in patch_targets:
                            patch_targets.append(target)
                        if is_test:
                            test_patch_targets[func_name].add(target)

        # Count MagicMock() and Mock() calls anywhere in the tree
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id == "MagicMock":
                    mock_counts["MagicMock"] += 1
                elif func.id == "Mock":
                    mock_counts["Mock"] += 1
            # monkeypatch.setattr / setenv / delenv
            if isinstance(func, ast.Attribute):
                if func.attr == "setattr" and isinstance(func.value, ast.Name) and func.value.id == "monkeypatch":
                    mock_counts["setattr"] += 1
                elif func.attr == "setenv" and isinstance(func.value, ast.Name) and func.value.id == "monkeypatch":
                    mock_counts["setenv"] += 1
                    # Extract the env var name (first argument)
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        env_var = node.args[0].value
                        if env_var not in overridden_env_vars:
                            overridden_env_vars.append(env_var)
                elif func.attr == "delenv" and isinstance(func.value, ast.Name) and func.value.id == "monkeypatch":
                    mock_counts["delenv"] += 1

    # Dead mock detection: for each patch target, try to import module and check attr
    dead_mocks: list[str] = []
    for target in patch_targets:
        parts = target.rsplit(".", 1)
        if len(parts) < 2:
            continue
        module_path, attr_name = parts
        try:
            mod = importlib.import_module(module_path)
            if not hasattr(mod, attr_name):
                dead_mocks.append(target)
        except (ImportError, ModuleNotFoundError, Exception):
            dead_mocks.append(target)

    # Build flags
    flags: list[str] = []

    # MOCK HEAVY: total mock count > 3 * test_count (and test_count > 0),
    # OR any single test function carries more than 3 @patch decorators.
    total_mocks = sum(mock_counts.values())
    any_test_over_threshold = any(c > 3 for c in test_patch_counts.values())
    if test_count > 0 and (total_mocks > 3 * test_count or any_test_over_threshold):
        flags.append("MOCK HEAVY")

    # CONFIG OVERRIDDEN: all test functions (>= 2 tests) share a common patch target
    if test_count >= 2 and test_patch_targets:
        # Find targets that appear in ALL test functions that have at least one patch
        # Actually: a target must appear in ALL test functions (including those with no patches)
        # Check if any single target is present in every test function's patch set
        all_test_sets = list(test_patch_targets.values())
        if all_test_sets:
            # Intersect all sets
            common = set.intersection(*all_test_sets) if all_test_sets else set()
            if common:
                flags.append("CONFIG OVERRIDDEN")

    # DEAD MOCKS
    if dead_mocks:
        flags.append("DEAD MOCKS")

    return {
        "test_count": test_count,
        "mock_counts": mock_counts,
        "patch_targets": patch_targets,
        "overridden_env_vars": overridden_env_vars,
        "dead_mocks": dead_mocks,
        "flags": flags,
    }


def main() -> int:
    paths = [pathlib.Path(p) for p in sys.argv[1:]]

    if not paths:
        print(json.dumps({}))
        return 0

    # Validate all paths exist before processing
    for p in paths:
        if not p.exists():
            print(f"Error: file not found: {p}", file=sys.stderr)
            return 1

    results: dict[str, Any] = {}
    for p in paths:
        results[str(p)] = _analyze_file(p)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
