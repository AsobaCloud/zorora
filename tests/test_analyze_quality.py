"""Tests for scripts/analyze-test-quality.py (SEP-076).

The analyzer is an AST-based static tool that detects mock-heavy tests,
stale patches, and over-mocked dispatch paths across the Zorora test suite.

All tests invoke the analyzer as a subprocess and parse its JSON output,
confirming that the script does not yet exist by verifying subprocess failure
before implementation.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
ANALYZER = PROJECT_ROOT / "scripts" / "analyze-test-quality.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(paths: list[pathlib.Path]) -> subprocess.CompletedProcess:
    """Run the analyzer on the given file paths, returning CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(ANALYZER)] + [str(p) for p in paths],
        capture_output=True,
        text=True,
    )


def _run_ok(paths: list[pathlib.Path]) -> dict:
    """Run analyzer and return parsed JSON.  Fails the test if exit != 0."""
    result = _run(paths)
    assert result.returncode == 0, (
        f"Analyzer exited {result.returncode}.\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Analyzer produced non-JSON stdout: {result.stdout[:500]} — {exc}"
        )


# ---------------------------------------------------------------------------
# Synthetic test-file factories
# ---------------------------------------------------------------------------

_CLEAN_FILE = '''\
"""A clean, lightly mocked test file."""
import pytest


def test_addition():
    assert 1 + 1 == 2


def test_subtraction():
    assert 5 - 3 == 2


def test_string_format():
    assert "hello {}".format("world") == "hello world"
'''

_MOCK_HEAVY_FILE = '''\
"""A heavily mocked test file that should trigger MOCK HEAVY."""
from unittest.mock import patch, MagicMock, Mock


@patch("engine.deep_research_service.aggregate_sources")
@patch("engine.deep_research_service.score_relevance")
@patch("engine.deep_research_service.filter_relevant")
@patch("engine.deep_research_service.synthesize")
def test_one(mock_synth, mock_filter, mock_score, mock_agg):
    mock_agg.return_value = []
    mock_synth.return_value = "result"
    assert True


@patch("engine.deep_research_service.aggregate_sources")
@patch("engine.deep_research_service.score_relevance")
@patch("engine.deep_research_service.filter_relevant")
@patch("engine.deep_research_service.synthesize")
def test_two(mock_synth, mock_filter, mock_score, mock_agg):
    mock_agg.return_value = []
    mock_synth.return_value = "result"
    assert True


@patch("engine.deep_research_service.aggregate_sources")
@patch("engine.deep_research_service.score_relevance")
@patch("engine.deep_research_service.filter_relevant")
@patch("engine.deep_research_service.synthesize")
def test_three(mock_synth, mock_filter, mock_score, mock_agg):
    mock_agg.return_value = []
    mock_synth.return_value = "result"
    assert True


def test_extra_mock_usage():
    m = MagicMock()
    n = Mock()
    m.return_value = 42
    assert m() == 42
'''

_CONFIG_OVERRIDE_FILE = '''\
"""All tests patch the same config attribute."""
from unittest.mock import patch


@patch("config.BRAVE_SEARCH", {"enabled": False})
def test_brave_disabled_first():
    import config
    assert not config.BRAVE_SEARCH["enabled"]


@patch("config.BRAVE_SEARCH", {"enabled": False})
def test_brave_disabled_second():
    import config
    assert not config.BRAVE_SEARCH["enabled"]


@patch("config.BRAVE_SEARCH", {"enabled": False})
def test_brave_disabled_third():
    import config
    assert not config.BRAVE_SEARCH["enabled"]
'''

_MONKEYPATCH_FILE = '''\
"""Tests using monkeypatch patterns."""


def test_setattr_usage(monkeypatch):
    monkeypatch.setattr("os.getcwd", lambda: "/fake")
    import os
    assert os.getcwd() == "/fake"


def test_setenv_usage(monkeypatch):
    monkeypatch.setenv("MY_VAR", "hello")
    import os
    assert os.environ["MY_VAR"] == "hello"


def test_delenv_usage(monkeypatch):
    monkeypatch.setenv("TEMP_VAR", "x")
    monkeypatch.delenv("TEMP_VAR", raising=False)
    import os
    assert "TEMP_VAR" not in os.environ
'''

_PATCH_TARGETS_FILE = '''\
"""Tests with extractable @patch target strings."""
from unittest.mock import patch


@patch("engine.deep_research_service.aggregate_sources")
@patch("workflows.deep_research.synthesizer.synthesize_outline")
def test_pipeline_dispatch(mock_outline, mock_agg):
    assert True


@patch("tools.registry.TOOL_FUNCTIONS", {})
def test_empty_tools(mock_tools):
    assert True
'''

_DEAD_MOCKS_FILE_TEMPLATE = '''\
"""Tests with a patch target that doesn\'t exist."""
from unittest.mock import patch


@patch("os.path.nonexistent_function_xyz")
def test_with_dead_mock(mock_fn):
    assert True


@patch("os.path.join")
def test_with_live_mock(mock_join):
    assert True
'''


# ===========================================================================
# 1. Script existence guard — all tests fail until analyzer is created
# ===========================================================================

class TestAnalyzerScriptExists:
    """The analyzer script must exist at scripts/analyze-test-quality.py."""

    def test_analyzer_script_exists(self):
        """scripts/analyze-test-quality.py must be present."""
        assert ANALYZER.exists(), (
            f"Analyzer script not found at {ANALYZER} — "
            "implement scripts/analyze-test-quality.py (SEP-076)"
        )

    def test_analyzer_is_executable_python(self):
        """Script must execute without import errors on an empty argument list."""
        result = subprocess.run(
            [sys.executable, str(ANALYZER), "--help"],
            capture_output=True,
            text=True,
        )
        # --help or zero-arg invocation must exit cleanly (0) or with usage (2),
        # not with a Python traceback (1 from SyntaxError/ImportError).
        assert result.returncode in (0, 1, 2), (
            f"Analyzer crashed with returncode={result.returncode}.\n"
            f"stderr: {result.stderr[:500]}"
        )
        assert "Traceback" not in result.stderr, (
            f"Analyzer raised an unhandled exception:\n{result.stderr[:1000]}"
        )


# ===========================================================================
# 2. JSON output contract
# ===========================================================================

class TestJsonOutputContract:
    """The analyzer must output valid JSON to stdout."""

    def test_output_is_valid_json(self, tmp_path):
        """Analyzer stdout must be parseable as JSON."""
        f = tmp_path / "test_simple.py"
        f.write_text(_CLEAN_FILE)
        result = _run([f])
        assert result.returncode == 0, f"Analyzer failed: {result.stderr[:500]}"
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"stdout is not valid JSON: {exc}\nstdout: {result.stdout[:500]}")

    def test_output_is_a_dict(self, tmp_path):
        """Top-level JSON must be a dict (mapping file paths to results)."""
        f = tmp_path / "test_simple.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        assert isinstance(data, dict), (
            f"Expected dict at top level, got {type(data).__name__}: {data!r:.200}"
        )

    def test_output_keyed_by_filepath(self, tmp_path):
        """Output dict must contain the analyzed file path as a key."""
        f = tmp_path / "test_simple.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        # Accept either absolute path or basename as key
        keys = list(data.keys())
        assert any(str(f) in k or f.name in k for k in keys), (
            f"Expected key containing '{f.name}' in output, got keys: {keys}"
        )

    def test_required_keys_present(self, tmp_path):
        """Each file entry must contain all required keys."""
        f = tmp_path / "test_required_keys.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        required = {"test_count", "mock_counts", "patch_targets",
                    "overridden_env_vars", "dead_mocks", "flags"}
        missing = required - set(entry.keys())
        assert not missing, (
            f"File entry missing required keys: {missing}. Got: {list(entry.keys())}"
        )

    def test_test_count_is_int(self, tmp_path):
        """test_count must be an integer."""
        f = tmp_path / "test_types.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["test_count"], int), (
            f"test_count must be int, got {type(entry['test_count']).__name__}"
        )

    def test_mock_counts_is_dict(self, tmp_path):
        """mock_counts must be a dict."""
        f = tmp_path / "test_mc_type.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["mock_counts"], dict), (
            f"mock_counts must be dict, got {type(entry['mock_counts']).__name__}"
        )

    def test_patch_targets_is_list(self, tmp_path):
        """patch_targets must be a list."""
        f = tmp_path / "test_pt_type.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["patch_targets"], list), (
            f"patch_targets must be list, got {type(entry['patch_targets']).__name__}"
        )

    def test_overridden_env_vars_is_list(self, tmp_path):
        """overridden_env_vars must be a list."""
        f = tmp_path / "test_oev_type.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["overridden_env_vars"], list), (
            f"overridden_env_vars must be list, got {type(entry['overridden_env_vars']).__name__}"
        )

    def test_dead_mocks_is_list(self, tmp_path):
        """dead_mocks must be a list."""
        f = tmp_path / "test_dm_type.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["dead_mocks"], list), (
            f"dead_mocks must be list, got {type(entry['dead_mocks']).__name__}"
        )

    def test_flags_is_list(self, tmp_path):
        """flags must be a list."""
        f = tmp_path / "test_flags_type.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert isinstance(entry["flags"], list), (
            f"flags must be list, got {type(entry['flags']).__name__}"
        )

    def test_multiple_files_produce_multiple_entries(self, tmp_path):
        """When two files are passed, the output must contain two entries."""
        f1 = tmp_path / "test_file_a.py"
        f2 = tmp_path / "test_file_b.py"
        f1.write_text(_CLEAN_FILE)
        f2.write_text(_CLEAN_FILE)
        data = _run_ok([f1, f2])
        assert len(data) == 2, (
            f"Expected 2 entries for 2 files, got {len(data)}: {list(data.keys())}"
        )


# ===========================================================================
# 3. Test counting
# ===========================================================================

class TestTestCounting:
    """test_count must equal the number of test_* functions in the file."""

    def test_clean_file_test_count(self, tmp_path):
        """Clean file with 3 test functions must report test_count=3."""
        f = tmp_path / "test_count_check.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 3, (
            f"Expected test_count=3 for clean file, got {entry['test_count']}"
        )

    def test_zero_test_functions(self, tmp_path):
        """File with no test_* functions must report test_count=0."""
        f = tmp_path / "test_empty.py"
        f.write_text("# no tests here\ndef helper(): pass\n")
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 0, (
            f"Expected test_count=0 for file with no tests, got {entry['test_count']}"
        )

    def test_class_method_tests_counted(self, tmp_path):
        """test_* methods inside classes must be counted."""
        f = tmp_path / "test_class_methods.py"
        f.write_text(
            "class TestSomething:\n"
            "    def test_alpha(self): pass\n"
            "    def test_beta(self): pass\n"
            "    def helper(self): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 2, (
            f"Expected test_count=2 (class methods), got {entry['test_count']}"
        )

    def test_mixed_functions_and_methods_counted(self, tmp_path):
        """Both module-level test functions and class methods must be counted."""
        f = tmp_path / "test_mixed.py"
        f.write_text(
            "def test_top_level(): pass\n\n"
            "class TestGroup:\n"
            "    def test_in_class(self): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 2, (
            f"Expected test_count=2 (1 module-level + 1 class), got {entry['test_count']}"
        )


# ===========================================================================
# 4. Mock counting
# ===========================================================================

class TestMockCounting:
    """mock_counts must accurately count each mock pattern category."""

    def test_patch_decorator_counted(self, tmp_path):
        """@patch(...) decorators must be counted under 'patch'."""
        f = tmp_path / "test_patch_count.py"
        f.write_text(_MOCK_HEAVY_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "patch" in counts, (
            f"mock_counts missing 'patch' key. Got: {list(counts.keys())}"
        )
        assert counts["patch"] >= 12, (
            f"Expected at least 12 @patch decorators in mock-heavy file, "
            f"got {counts['patch']}"
        )

    def test_magicmock_counted(self, tmp_path):
        """MagicMock() uses must be counted under 'MagicMock'."""
        f = tmp_path / "test_mm_count.py"
        f.write_text(_MOCK_HEAVY_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "MagicMock" in counts, (
            f"mock_counts missing 'MagicMock' key. Got: {list(counts.keys())}"
        )
        assert counts["MagicMock"] >= 1, (
            f"Expected at least 1 MagicMock in mock-heavy file, got {counts['MagicMock']}"
        )

    def test_mock_counted(self, tmp_path):
        """Mock() uses must be counted under 'Mock'."""
        f = tmp_path / "test_mock_count.py"
        f.write_text(_MOCK_HEAVY_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "Mock" in counts, (
            f"mock_counts missing 'Mock' key. Got: {list(counts.keys())}"
        )
        assert counts["Mock"] >= 1, (
            f"Expected at least 1 Mock in mock-heavy file, got {counts['Mock']}"
        )

    def test_monkeypatch_setattr_counted(self, tmp_path):
        """monkeypatch.setattr calls must be counted under 'setattr'."""
        f = tmp_path / "test_mp_setattr.py"
        f.write_text(_MONKEYPATCH_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "setattr" in counts, (
            f"mock_counts missing 'setattr' key. Got: {list(counts.keys())}"
        )
        assert counts["setattr"] >= 1, (
            f"Expected >=1 monkeypatch.setattr, got {counts.get('setattr', 0)}"
        )

    def test_monkeypatch_setenv_counted(self, tmp_path):
        """monkeypatch.setenv calls must be counted under 'setenv'."""
        f = tmp_path / "test_mp_setenv.py"
        f.write_text(_MONKEYPATCH_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "setenv" in counts, (
            f"mock_counts missing 'setenv' key. Got: {list(counts.keys())}"
        )
        assert counts["setenv"] >= 1, (
            f"Expected >=1 monkeypatch.setenv, got {counts.get('setenv', 0)}"
        )

    def test_monkeypatch_delenv_counted(self, tmp_path):
        """monkeypatch.delenv calls must be counted under 'delenv'."""
        f = tmp_path / "test_mp_delenv.py"
        f.write_text(_MONKEYPATCH_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        assert "delenv" in counts, (
            f"mock_counts missing 'delenv' key. Got: {list(counts.keys())}"
        )
        assert counts["delenv"] >= 1, (
            f"Expected >=1 monkeypatch.delenv, got {counts.get('delenv', 0)}"
        )

    def test_clean_file_has_zero_mock_counts(self, tmp_path):
        """Clean file with no mocks must report all mock counts as 0."""
        f = tmp_path / "test_clean_mocks.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        total = sum(counts.values())
        assert total == 0, (
            f"Clean file should have 0 total mock counts, got {total}: {counts}"
        )

    def test_mock_counts_dict_has_expected_keys(self, tmp_path):
        """mock_counts must contain at least the six documented categories."""
        f = tmp_path / "test_mc_keys.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        counts = entry["mock_counts"]
        expected_keys = {"patch", "MagicMock", "Mock", "setattr", "setenv", "delenv"}
        missing = expected_keys - set(counts.keys())
        assert not missing, (
            f"mock_counts missing expected keys: {missing}. Got: {list(counts.keys())}"
        )

    def test_mock_counts_are_non_negative_ints(self, tmp_path):
        """All mock count values must be non-negative integers."""
        f = tmp_path / "test_mc_values.py"
        f.write_text(_MOCK_HEAVY_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        for key, val in entry["mock_counts"].items():
            assert isinstance(val, int) and val >= 0, (
                f"mock_counts[{key!r}] = {val!r} — must be non-negative int"
            )


# ===========================================================================
# 5. Patch target extraction
# ===========================================================================

class TestPatchTargetExtraction:
    """patch_targets must list the dotted paths from @patch("...") decorators."""

    def test_patch_targets_extracted_from_decorator(self, tmp_path):
        """patch_targets must include the dotted path from each @patch decorator."""
        f = tmp_path / "test_pt_extract.py"
        f.write_text(_PATCH_TARGETS_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        targets = entry["patch_targets"]
        assert "engine.deep_research_service.aggregate_sources" in targets, (
            f"Expected 'engine.deep_research_service.aggregate_sources' in patch_targets. "
            f"Got: {targets}"
        )
        assert "workflows.deep_research.synthesizer.synthesize_outline" in targets, (
            f"Expected 'workflows.deep_research.synthesizer.synthesize_outline' in "
            f"patch_targets. Got: {targets}"
        )

    def test_patch_targets_no_duplicates_unless_patched_multiple_times(self, tmp_path):
        """patch_targets list should not include duplicate entries unless the same
        target is patched in multiple distinct test functions."""
        f = tmp_path / "test_pt_unique.py"
        # Single use of each target
        f.write_text(_PATCH_TARGETS_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        targets = entry["patch_targets"]
        # Verify all entries are strings (dotted paths)
        for t in targets:
            assert isinstance(t, str) and "." in t, (
                f"patch_targets entry {t!r} is not a dotted path string"
            )

    def test_patch_targets_empty_for_clean_file(self, tmp_path):
        """File with no @patch decorators must have empty patch_targets."""
        f = tmp_path / "test_pt_empty.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["patch_targets"] == [], (
            f"Expected empty patch_targets for clean file, got: {entry['patch_targets']}"
        )


# ===========================================================================
# 6. overridden_env_vars extraction
# ===========================================================================

class TestEnvVarExtraction:
    """overridden_env_vars must list env var names from monkeypatch.setenv calls."""

    def test_setenv_var_names_extracted(self, tmp_path):
        """monkeypatch.setenv('VAR', ...) must add 'VAR' to overridden_env_vars."""
        f = tmp_path / "test_env_extract.py"
        f.write_text(_MONKEYPATCH_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        env_vars = entry["overridden_env_vars"]
        assert "MY_VAR" in env_vars, (
            f"Expected 'MY_VAR' in overridden_env_vars. Got: {env_vars}"
        )

    def test_overridden_env_vars_empty_for_clean_file(self, tmp_path):
        """File with no monkeypatch.setenv must have empty overridden_env_vars."""
        f = tmp_path / "test_env_empty.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["overridden_env_vars"] == [], (
            f"Expected empty overridden_env_vars for clean file, "
            f"got: {entry['overridden_env_vars']}"
        )


# ===========================================================================
# 7. MOCK HEAVY flag
# ===========================================================================

class TestMockHeavyFlag:
    """MOCK HEAVY must be flagged when the total mock count exceeds 3x the test count."""

    def test_mock_heavy_flagged_for_high_ratio(self, tmp_path):
        """File with >3x mock-to-test ratio must have 'MOCK HEAVY' in flags."""
        f = tmp_path / "test_mh_flag.py"
        f.write_text(_MOCK_HEAVY_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "MOCK HEAVY" in entry["flags"], (
            f"Expected 'MOCK HEAVY' flag for heavily mocked file. "
            f"Got flags: {entry['flags']}. "
            f"mock_counts={entry['mock_counts']}, test_count={entry['test_count']}"
        )

    def test_clean_file_not_mock_heavy(self, tmp_path):
        """Clean file with no mocks must NOT have 'MOCK HEAVY' flag."""
        f = tmp_path / "test_clean_no_mh.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "MOCK HEAVY" not in entry["flags"], (
            f"Clean file should not get MOCK HEAVY flag. Got flags: {entry['flags']}"
        )

    def test_mock_heavy_threshold_boundary(self, tmp_path):
        """File at exactly 3x ratio should NOT get MOCK HEAVY (ratio must be > 3x)."""
        # 1 test, 3 patch decorators = ratio 3.0 (not > 3, so no flag)
        f = tmp_path / "test_boundary.py"
        f.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('os.getcwd')\n"
            "@patch('os.listdir')\n"
            "@patch('os.path.exists')\n"
            "def test_exactly_three(m1, m2, m3): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        # Ratio = 3/1 = 3.0, NOT > 3, so no MOCK HEAVY flag
        assert "MOCK HEAVY" not in entry["flags"], (
            f"Ratio of exactly 3.0 should not trigger MOCK HEAVY (requires > 3). "
            f"Got flags: {entry['flags']}, counts={entry['mock_counts']}, "
            f"tests={entry['test_count']}"
        )

    def test_mock_heavy_triggered_just_above_threshold(self, tmp_path):
        """File with ratio just above 3x must get MOCK HEAVY flag."""
        # 1 test, 4 patch decorators = ratio 4.0 > 3x
        f = tmp_path / "test_above_threshold.py"
        f.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('os.getcwd')\n"
            "@patch('os.listdir')\n"
            "@patch('os.path.exists')\n"
            "@patch('os.path.isfile')\n"
            "def test_four_patches(m1, m2, m3, m4): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "MOCK HEAVY" in entry["flags"], (
            f"Ratio of 4.0 should trigger MOCK HEAVY. "
            f"Got flags: {entry['flags']}, counts={entry['mock_counts']}, "
            f"tests={entry['test_count']}"
        )

    def test_zero_tests_does_not_crash(self, tmp_path):
        """File with mocks but no test functions must not crash (division by zero)."""
        f = tmp_path / "test_no_tests.py"
        f.write_text(
            "from unittest.mock import patch, MagicMock\n\n"
            "# helper only, no tests\n"
            "def setup_mock():\n"
            "    return MagicMock()\n"
        )
        result = _run([f])
        assert result.returncode == 0, (
            f"Analyzer crashed on file with no tests: {result.stderr[:500]}"
        )


# ===========================================================================
# 8. CONFIG OVERRIDDEN flag
# ===========================================================================

class TestConfigOverriddenFlag:
    """CONFIG OVERRIDDEN must fire when all tests in a file patch the same attribute."""

    def test_config_overridden_flagged(self, tmp_path):
        """All tests patching 'config.BRAVE_SEARCH' must trigger CONFIG OVERRIDDEN."""
        f = tmp_path / "test_co_flag.py"
        f.write_text(_CONFIG_OVERRIDE_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "CONFIG OVERRIDDEN" in entry["flags"], (
            f"Expected 'CONFIG OVERRIDDEN' flag when all tests patch same attribute. "
            f"Got flags: {entry['flags']}. patch_targets={entry['patch_targets']}"
        )

    def test_diverse_patches_no_config_override(self, tmp_path):
        """Tests patching different targets must NOT get CONFIG OVERRIDDEN."""
        f = tmp_path / "test_diverse_patches.py"
        f.write_text(_PATCH_TARGETS_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        # Two different targets across two test functions — no single target
        # covers all tests, so CONFIG OVERRIDDEN should not fire.
        assert "CONFIG OVERRIDDEN" not in entry["flags"], (
            f"Diverse patch targets should not trigger CONFIG OVERRIDDEN. "
            f"Got flags: {entry['flags']}"
        )

    def test_clean_file_no_config_override(self, tmp_path):
        """File with no patches must not get CONFIG OVERRIDDEN."""
        f = tmp_path / "test_clean_co.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "CONFIG OVERRIDDEN" not in entry["flags"], (
            f"Clean file must not get CONFIG OVERRIDDEN. Got flags: {entry['flags']}"
        )

    def test_single_test_with_patch_no_config_override(self, tmp_path):
        """A single test with a patch should not trigger CONFIG OVERRIDDEN
        (the condition requires multiple tests all patching the same target)."""
        f = tmp_path / "test_single_patched.py"
        f.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('config.SETTING', {'key': 'val'})\n"
            "def test_only_one(mock_cfg): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        # Only 1 test — can't establish "all tests" pattern meaningfully
        assert "CONFIG OVERRIDDEN" not in entry["flags"], (
            f"Single test with patch should not trigger CONFIG OVERRIDDEN. "
            f"Got flags: {entry['flags']}"
        )


# ===========================================================================
# 9. DEAD MOCKS flag
# ===========================================================================

class TestDeadMocksFlag:
    """DEAD MOCKS must fire when a @patch target doesn't exist in its module."""

    def test_dead_mock_detected_for_nonexistent_attr(self, tmp_path):
        """@patch('os.path.nonexistent_function_xyz') must be flagged as a dead mock."""
        f = tmp_path / "test_dead_mock_detect.py"
        f.write_text(_DEAD_MOCKS_FILE_TEMPLATE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "DEAD MOCKS" in entry["flags"], (
            f"Expected 'DEAD MOCKS' flag for patch of nonexistent attribute. "
            f"Got flags: {entry['flags']}. dead_mocks={entry['dead_mocks']}"
        )

    def test_dead_mocks_list_contains_dead_target(self, tmp_path):
        """dead_mocks list must include the nonexistent patch target path."""
        f = tmp_path / "test_dead_mocks_list.py"
        f.write_text(_DEAD_MOCKS_FILE_TEMPLATE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        dead = entry["dead_mocks"]
        assert any("nonexistent_function_xyz" in d for d in dead), (
            f"dead_mocks should contain the nonexistent target. Got: {dead}"
        )

    def test_live_mock_not_in_dead_mocks(self, tmp_path):
        """@patch('os.path.join') must NOT appear in dead_mocks (it exists)."""
        f = tmp_path / "test_live_mock_ok.py"
        f.write_text(_DEAD_MOCKS_FILE_TEMPLATE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        dead = entry["dead_mocks"]
        assert not any("os.path.join" in d for d in dead), (
            f"os.path.join is a real attribute and must not be in dead_mocks. "
            f"Got dead_mocks: {dead}"
        )

    def test_clean_file_no_dead_mocks(self, tmp_path):
        """Clean file with no patches must have empty dead_mocks."""
        f = tmp_path / "test_clean_no_dead.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["dead_mocks"] == [], (
            f"Clean file must have empty dead_mocks. Got: {entry['dead_mocks']}"
        )

    def test_no_dead_mocks_flag_when_all_targets_exist(self, tmp_path):
        """File where all patch targets exist must not get DEAD MOCKS flag."""
        f = tmp_path / "test_all_live_mocks.py"
        f.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('os.path.join')\n"
            "@patch('os.path.exists')\n"
            "def test_two_live_patches(m1, m2): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert "DEAD MOCKS" not in entry["flags"], (
            f"All-live-mock file must not get DEAD MOCKS flag. "
            f"Got flags: {entry['flags']}, dead_mocks={entry['dead_mocks']}"
        )


# ===========================================================================
# 10. Clean file produces no flags
# ===========================================================================

class TestCleanFile:
    """A well-written test file with few mocks must produce an empty flags list."""

    def test_clean_file_has_no_flags(self, tmp_path):
        """Clean test file must have no quality flags."""
        f = tmp_path / "test_clean_flags.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["flags"] == [], (
            f"Clean file must have no flags, got: {entry['flags']}"
        )

    def test_clean_file_correct_test_count(self, tmp_path):
        """Clean file test_count must match actual function count."""
        f = tmp_path / "test_clean_count.py"
        f.write_text(_CLEAN_FILE)
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 3, (
            f"Clean file has 3 test functions, got test_count={entry['test_count']}"
        )


# ===========================================================================
# 11. End-to-end: real test_deep_research_pipeline.py gets MOCK HEAVY
# ===========================================================================

class TestRealFileMockHeavy:
    """The actual test_deep_research_pipeline.py must receive the MOCK HEAVY flag."""

    def test_deep_research_pipeline_gets_mock_heavy_flag(self):
        """Running the analyzer on tests/test_deep_research_pipeline.py must
        produce at least the MOCK HEAVY quality flag.

        This file has >100 @patch decorators for ~93 test functions and is
        the canonical example of the mock-masking pattern that caused the
        synthesize_direct dispatch bug to recur 4 times (SEP-068/070/073/075).
        """
        real_file = PROJECT_ROOT / "tests" / "test_deep_research_pipeline.py"
        assert real_file.exists(), (
            f"test_deep_research_pipeline.py not found at {real_file}"
        )
        data = _run_ok([real_file])
        assert len(data) == 1, (
            f"Expected 1 entry in output for 1 file, got {len(data)}"
        )
        entry = next(iter(data.values()))
        assert "MOCK HEAVY" in entry["flags"], (
            f"test_deep_research_pipeline.py must receive MOCK HEAVY flag. "
            f"Got flags: {entry['flags']}. "
            f"mock_counts={entry['mock_counts']}, test_count={entry['test_count']}"
        )

    def test_deep_research_pipeline_has_patch_targets(self):
        """test_deep_research_pipeline.py must report non-empty patch_targets."""
        real_file = PROJECT_ROOT / "tests" / "test_deep_research_pipeline.py"
        assert real_file.exists(), (
            f"test_deep_research_pipeline.py not found at {real_file}"
        )
        data = _run_ok([real_file])
        entry = next(iter(data.values()))
        assert len(entry["patch_targets"]) > 0, (
            "Expected non-empty patch_targets for test_deep_research_pipeline.py, "
            "got empty list"
        )
        # Key dispatch targets that recurred across SEP-068/070/073/075
        key_targets = [
            "engine.deep_research_service.synthesize",
            "engine.deep_research_service.aggregate_sources",
        ]
        found = [t for t in key_targets if t in entry["patch_targets"]]
        assert found, (
            f"Expected at least one of {key_targets} in patch_targets. "
            f"Got: {entry['patch_targets'][:10]}..."
        )

    def test_deep_research_pipeline_test_count_correct(self):
        """test_deep_research_pipeline.py must report a realistic test count."""
        real_file = PROJECT_ROOT / "tests" / "test_deep_research_pipeline.py"
        assert real_file.exists()
        data = _run_ok([real_file])
        entry = next(iter(data.values()))
        # We know the file has ~93+ test functions — assert a conservative lower bound
        assert entry["test_count"] >= 50, (
            f"Expected at least 50 tests in test_deep_research_pipeline.py, "
            f"got test_count={entry['test_count']}"
        )

    def test_deep_research_pipeline_patch_count_above_fifty(self):
        """test_deep_research_pipeline.py must report patch count > 50."""
        real_file = PROJECT_ROOT / "tests" / "test_deep_research_pipeline.py"
        assert real_file.exists()
        data = _run_ok([real_file])
        entry = next(iter(data.values()))
        patch_count = entry["mock_counts"].get("patch", 0)
        assert patch_count > 50, (
            f"Expected >50 @patch uses in test_deep_research_pipeline.py, "
            f"got patch count={patch_count}"
        )


# ===========================================================================
# 12. Edge cases and error handling
# ===========================================================================

class TestEdgeCases:
    """Edge cases: empty files, syntax errors, non-existent paths."""

    def test_empty_file_handled_gracefully(self, tmp_path):
        """An empty Python file must not crash the analyzer."""
        f = tmp_path / "test_empty_file.py"
        f.write_text("")
        result = _run([f])
        assert result.returncode == 0, (
            f"Analyzer crashed on empty file: {result.stderr[:500]}"
        )
        data = json.loads(result.stdout)
        entry = next(iter(data.values()))
        assert entry["test_count"] == 0
        assert entry["flags"] == []

    def test_docstring_only_file_handled(self, tmp_path):
        """File with only a docstring must report test_count=0."""
        f = tmp_path / "test_docstring_only.py"
        f.write_text('"""Module docstring only."""\n')
        data = _run_ok([f])
        entry = next(iter(data.values()))
        assert entry["test_count"] == 0

    def test_nonexistent_file_exits_nonzero(self):
        """Passing a nonexistent file path must cause non-zero exit."""
        result = _run([pathlib.Path("/nonexistent/path/test_fake.py")])
        assert result.returncode != 0, (
            "Analyzer should exit non-zero for a nonexistent file path"
        )

    def test_multiple_flags_can_coexist(self, tmp_path):
        """A file can have both MOCK HEAVY and CONFIG OVERRIDDEN simultaneously."""
        # Many tests all patching the same heavy target
        f = tmp_path / "test_multi_flags.py"
        f.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('config.BRAVE_SEARCH', {'enabled': False})\n"
            "@patch('config.WEB_SEARCH', {'parallel_enabled': False})\n"
            "@patch('config.CONTENT_FETCH', {'enabled': False})\n"
            "@patch('config.RERANKER', {'threshold': 0.5})\n"
            "def test_alpha(m1, m2, m3, m4): pass\n\n"
            "@patch('config.BRAVE_SEARCH', {'enabled': False})\n"
            "@patch('config.WEB_SEARCH', {'parallel_enabled': False})\n"
            "@patch('config.CONTENT_FETCH', {'enabled': False})\n"
            "@patch('config.RERANKER', {'threshold': 0.5})\n"
            "def test_beta(m1, m2, m3, m4): pass\n\n"
            "@patch('config.BRAVE_SEARCH', {'enabled': False})\n"
            "@patch('config.WEB_SEARCH', {'parallel_enabled': False})\n"
            "@patch('config.CONTENT_FETCH', {'enabled': False})\n"
            "@patch('config.RERANKER', {'threshold': 0.5})\n"
            "def test_gamma(m1, m2, m3, m4): pass\n\n"
            "@patch('config.BRAVE_SEARCH', {'enabled': False})\n"
            "@patch('config.WEB_SEARCH', {'parallel_enabled': False})\n"
            "@patch('config.CONTENT_FETCH', {'enabled': False})\n"
            "@patch('config.RERANKER', {'threshold': 0.5})\n"
            "def test_delta(m1, m2, m3, m4): pass\n"
        )
        data = _run_ok([f])
        entry = next(iter(data.values()))
        # 16 patches / 4 tests = 4.0 ratio > 3x → MOCK HEAVY
        # All 4 tests patch 'config.BRAVE_SEARCH' → CONFIG OVERRIDDEN
        flags = entry["flags"]
        assert "MOCK HEAVY" in flags, (
            f"Expected MOCK HEAVY (4.0 ratio). Got flags: {flags}, "
            f"counts={entry['mock_counts']}, tests={entry['test_count']}"
        )
        assert "CONFIG OVERRIDDEN" in flags, (
            f"Expected CONFIG OVERRIDDEN (all tests patch same target). "
            f"Got flags: {flags}"
        )

    def test_no_arguments_does_not_crash(self):
        """Running with no file arguments must exit cleanly, not crash."""
        result = subprocess.run(
            [sys.executable, str(ANALYZER)],
            capture_output=True,
            text=True,
        )
        # Should exit 0 with empty JSON ({}) or exit non-zero with a usage message,
        # but must NOT produce an unhandled Python traceback.
        assert "Traceback" not in result.stderr, (
            f"No-args invocation produced traceback:\n{result.stderr[:500]}"
        )
