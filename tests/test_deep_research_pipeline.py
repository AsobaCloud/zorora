"""Tests for deep research pipeline bugs (SEP-022).

Covers: reranker threshold/fallback, credibility scoring, newsroom AND-gate,
query decomposition suffixes, Brave endpoint config, and validation hook.
"""

import os
import subprocess
import unittest

from engine.models import Source
from workflows.deep_research.reranker import filter_relevant
from workflows.deep_research.credibility import BASE_CREDIBILITY


def _make_source(title="Test", snippet="", relevance=0.0, url="https://example.com"):
    """Helper to create a Source with a relevance score."""
    s = Source(
        source_id=Source.generate_id(url + title),
        url=url,
        title=title,
        content_snippet=snippet,
    )
    s.relevance_score = relevance
    return s


# ---------------------------------------------------------------------------
# Bug #3 / #4 — Reranker threshold and fallback
# ---------------------------------------------------------------------------
class TestRerankerThreshold(unittest.TestCase):
    def test_single_keyword_match_below_threshold(self):
        """1/5 keyword match (score 0.20) must be excluded at threshold 0.40."""
        sources = [_make_source(f"s{i}", relevance=0.20) for i in range(5)]
        result = filter_relevant(sources, min_score=0.40)
        # All score 0.20 — none should pass the 0.40 threshold via the
        # primary filter, so result comes from fallback (top 5 cap).
        for s in result:
            self.assertAlmostEqual(s.relevance_score, 0.20)
        # Fallback should cap at 5
        self.assertLessEqual(len(result), 5)

    def test_two_keyword_match_passes_threshold(self):
        """2/5 keyword match (score 0.40) must pass threshold 0.40."""
        good = _make_source("good", relevance=0.40)
        bad = _make_source("bad", relevance=0.10)
        result = filter_relevant([good, bad], min_score=0.40)
        self.assertIn(good, result)

    def test_fallback_caps_at_five(self):
        """When nothing passes threshold, fallback returns at most 5 sources."""
        sources = [_make_source(f"s{i}", relevance=0.05, url=f"https://ex.com/{i}") for i in range(20)]
        result = filter_relevant(sources, min_score=0.40)
        self.assertEqual(len(result), 5)

    def test_filter_uses_gte_not_gt(self):
        """Score exactly equal to min_score must pass (>=, not >)."""
        exact = _make_source("exact", relevance=0.40)
        result = filter_relevant([exact], min_score=0.40)
        self.assertIn(exact, result)


# ---------------------------------------------------------------------------
# Bug #5 — Credibility scoring for .gov / .edu
# ---------------------------------------------------------------------------
class TestCredibilityScoring(unittest.TestCase):
    def test_gov_base_score_below_reuters(self):
        """.gov base score must be <= 0.65 (not 0.85)."""
        self.assertLessEqual(BASE_CREDIBILITY[".gov"]["score"], 0.65)

    def test_edu_base_score(self):
        """.edu base score must be <= 0.60 (not 0.75)."""
        self.assertLessEqual(BASE_CREDIBILITY[".edu"]["score"], 0.60)

    def test_gov_still_above_unknown(self):
        """.gov score must still be > 0.50 (unknown source baseline)."""
        self.assertGreater(BASE_CREDIBILITY[".gov"]["score"], 0.50)


# ---------------------------------------------------------------------------
# Bug #6 — Newsroom AND-gate
# ---------------------------------------------------------------------------
class TestNewsroomAndGate(unittest.TestCase):
    def _filter(self, articles, query):
        from workflows.deep_research.aggregator import parse_newsroom_results
        return parse_newsroom_results(articles, query)

    def test_single_keyword_match_rejected_with_three_keywords(self):
        """Query 'lithium price Zimbabwe', article with only 'mining' → excluded."""
        articles = [{"headline": "Mining operations expand", "topic_tags": ["mining"], "url": "https://ex.com/1"}]
        result = self._filter(articles, "lithium price Zimbabwe")
        self.assertEqual(len(result), 0)

    def test_two_keyword_match_passes_with_three_keywords(self):
        """Article mentioning 'lithium' and 'Zimbabwe' passes."""
        articles = [{"headline": "Lithium mining in Zimbabwe", "topic_tags": ["lithium"], "url": "https://ex.com/2"}]
        result = self._filter(articles, "lithium price Zimbabwe")
        self.assertEqual(len(result), 1)

    def test_single_keyword_sufficient_with_two_keywords(self):
        """With only 2 keywords, 1 match is enough."""
        articles = [{"headline": "Lithium prices surge", "topic_tags": [], "url": "https://ex.com/3"}]
        result = self._filter(articles, "lithium prices")
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# Bug #7 — Query decomposition fallback suffixes
# ---------------------------------------------------------------------------
class TestQueryDecomposition(unittest.TestCase):
    def _get_suffixes(self):
        """Extract fallback_suffixes from deep_research_service source."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1] / "engine" / "deep_research_service.py").read_text()
        # Find the fallback_suffixes list literal
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "fallback_suffixes":
                        return [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]
        self.fail("Could not find fallback_suffixes in deep_research_service.py")

    def test_fallback_suffixes_no_political_humanitarian(self):
        """Fallback suffixes must not contain political/humanitarian terms."""
        bad_words = {"political", "humanitarian", "social", "diplomatic"}
        suffixes = self._get_suffixes()
        for suffix in suffixes:
            words = set(suffix.lower().split())
            overlap = words & bad_words
            self.assertFalse(overlap, f"Suffix '{suffix}' contains banned words: {overlap}")

    def test_fallback_produces_two_variants(self):
        """With num_variants=3, fallback should produce exactly 2 suffixed variants."""
        suffixes = self._get_suffixes()
        self.assertEqual(len(suffixes), 2, f"Expected 2 fallback suffixes, got {len(suffixes)}: {suffixes}")


# ---------------------------------------------------------------------------
# Bug #1 — Brave Search endpoint config
# ---------------------------------------------------------------------------
class TestBraveEndpointConfig(unittest.TestCase):
    def test_brave_endpoint_is_brave_api(self):
        """Brave endpoint must point to Brave API, not Railway."""
        import config
        endpoint = config.BRAVE_SEARCH["endpoint"]
        self.assertTrue(
            endpoint.startswith("https://api.search.brave.com/"),
            f"Brave endpoint is '{endpoint}', expected Brave API URL",
        )

    def test_brave_endpoint_not_railway(self):
        """Brave endpoint must not contain railway.app."""
        import config
        endpoint = config.BRAVE_SEARCH["endpoint"]
        self.assertNotIn("railway.app", endpoint)


# ---------------------------------------------------------------------------
# Validation hook (record_validation.sh)
# ---------------------------------------------------------------------------
class TestRecordValidationScript(unittest.TestCase):
    SCRIPT = os.path.expanduser("~/.claude/scripts/record_validation.sh")

    @unittest.skipUnless(os.path.isfile(os.path.expanduser("~/.claude/scripts/record_validation.sh")),
                         "record_validation.sh not found")
    def test_bare_invocation_blocked(self):
        """Running without flags must be blocked (exit != 0)."""
        result = subprocess.run(
            ["bash", self.SCRIPT, "arbitrary string"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0, "Bare invocation should be blocked")

    @unittest.skipUnless(os.path.isfile(os.path.expanduser("~/.claude/scripts/record_validation.sh")),
                         "record_validation.sh not found")
    def test_command_flag_requires_log_match(self):
        """--command flag must verify the command appears in validation_log."""
        result = subprocess.run(
            ["bash", self.SCRIPT, "--command", "pytest"],
            capture_output=True, text=True,
            env={**os.environ, "CLAUDE_TEST_PERSIST_DIR": "/tmp/zorora_test_validate"},
        )
        self.assertNotEqual(result.returncode, 0, "--command should fail when command not in log")

    @unittest.skipUnless(os.path.isfile(os.path.expanduser("~/.claude/scripts/record_validation.sh")),
                         "record_validation.sh not found")
    def test_manual_flag_sets_pending_marker(self):
        """--manual flag must create validate_pending, NOT clear dirty."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dirty marker
            dirty_path = os.path.join(tmpdir, "dirty")
            with open(dirty_path, "w") as f:
                f.write("dirty")

            result = subprocess.run(
                ["bash", self.SCRIPT, "--manual", "visual check of output"],
                capture_output=True, text=True,
                env={**os.environ, "CLAUDE_TEST_PERSIST_DIR": tmpdir},
            )
            self.assertEqual(result.returncode, 0, f"--manual should succeed: {result.stderr}")
            # dirty should NOT be cleared
            self.assertTrue(os.path.exists(dirty_path), "dirty flag should not be cleared by --manual")
            # validate_pending should exist
            pending_path = os.path.join(tmpdir, "validate_pending")
            self.assertTrue(os.path.exists(pending_path), "validate_pending marker should be created")


if __name__ == "__main__":
    unittest.main()
