"""Tests for deep research pipeline bugs (SEP-022, SEP-023).

Covers: reranker threshold/fallback, credibility scoring, newsroom AND-gate,
query decomposition suffixes, Brave endpoint config, validation hook,
variant keyword union scoring, and funnel logging.
"""

import os
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from engine.models import Source
from workflows.deep_research.reranker import score_relevance, filter_relevant
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


class TestRefinedIntentNormalization(unittest.TestCase):
    def test_decompose_query_collapses_empty_pipe_segments(self):
        """Refined query cleanup must remove empty pipe segments from core intent."""
        from engine.query_refiner import decompose_query

        intents = decompose_query("What are the historical price trends of lithium | | | ")
        self.assertGreaterEqual(len(intents), 1)
        self.assertEqual(intents[0].intent_query, "What are the historical price trends of lithium")

        for intent in intents:
            self.assertNotIn("| |", intent.intent_query)
            self.assertNotIn("||", intent.intent_query)

    def test_decompose_query_keeps_refinement_segments(self):
        """Selected refinement dimensions should still produce dedicated intents."""
        from engine.query_refiner import decompose_query

        query = (
            "What are the historical price trends of lithium"
            " | time period: Last 12 months | geography: Global | scope: All sectors"
        )
        intents = decompose_query(query)
        intent_text = [i.intent_query for i in intents]

        self.assertTrue(any("Last 12 months" in text for text in intent_text))
        self.assertTrue(any("Global" in text for text in intent_text))
        self.assertTrue(any("All sectors" in text for text in intent_text))


class TestVariantSanitization(unittest.TestCase):
    def test_clean_query_line_rejects_decomposition_preamble(self):
        """Model preambles like 'query can be decomposed...' must not become queries."""
        from engine.deep_research_service import _clean_query_line

        line = "The given research query can be decomposed into two distinct sub-topic searches as follows"
        self.assertIsNone(_clean_query_line(line))

    @patch("tools.registry.TOOL_FUNCTIONS", {
        "use_reasoning_model": lambda prompt: (
            "The given research query can be decomposed into two distinct sub-topic searches as follows\n"
            "Lithium carbonate historical price index trends 2024 2026"
        ),
    })
    def test_generate_query_variants_ignores_prose_and_keeps_topical_query(self):
        """Variant generation should discard prose lines and keep topical sub-queries."""
        from engine.deep_research_service import _generate_query_variants

        query = "What are the historical price trends of lithium"
        variants = _generate_query_variants(query, num_variants=2)
        self.assertEqual(variants[0], query)
        self.assertEqual(len(variants), 2)
        self.assertIn("lithium", variants[1].lower())
        self.assertNotIn("decomposed into", variants[1].lower())


class TestWebSourcesIsolation(unittest.TestCase):
    def test_web_search_sources_does_not_merge_academic(self):
        """Structured web source path should remain web-only (academic handled separately)."""
        import importlib
        web_search_module = importlib.import_module("tools.research.web_search")

        with patch.object(web_search_module, "_duckduckgo_search_raw") as mock_ddg:
            with patch.object(web_search_module, "_scholar_search_raw") as mock_scholar:
                with patch.object(web_search_module, "_pubmed_search_raw") as mock_pubmed:
                    mock_ddg.return_value = [
                        {
                            "title": "Lithium prices rise on supply constraints",
                            "url": "https://example.com/lithium-prices",
                            "description": "Spot prices increased amid tighter supply.",
                        }
                    ]

                    with patch.dict("config.BRAVE_SEARCH", {"enabled": False, "api_key": ""}, clear=False):
                        with patch.dict("config.WEB_SEARCH", {"parallel_enabled": False, "max_domain_results": 2}, clear=False):
                            sources = web_search_module.web_search_sources("lithium price trends", max_results=5)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_type, "web")
        mock_scholar.assert_not_called()
        mock_pubmed.assert_not_called()


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


# ---------------------------------------------------------------------------
# SEP-023 — Variant keyword union scoring
# ---------------------------------------------------------------------------
class TestVariantKeywordUnion(unittest.TestCase):
    def test_score_relevance_with_extra_keywords(self):
        """Source matching only variant keywords must get relevance_score > 0."""
        # "market supply" appears in snippet but NOT in original query keywords
        s = _make_source("Lithium market supply chain overview",
                         snippet="market supply demand analysis",
                         relevance=0.0,
                         url="https://example.com/variant-match")
        result = score_relevance("lithium price trends Zimbabwe mining",
                                 [s],
                                 extra_keywords=["market", "supply", "demand", "outlook"])
        self.assertGreater(result[0].relevance_score, 0.0)

    def test_extra_keywords_expand_denominator(self):
        """3 original + 3 extra (no overlap): matching 3/6 should score 0.50."""
        # Original query keywords (stemmed): "alpha", "beta", "gamma"
        # Extra keywords: "delta", "epsilon", "zeta"
        # Source matches: "alpha", "delta", "epsilon" → 3/6 = 0.50
        s = _make_source("alpha delta epsilon content",
                         snippet="alpha delta epsilon text",
                         relevance=0.0,
                         url="https://example.com/denom-test")
        result = score_relevance("alpha beta gamma",
                                 [s],
                                 extra_keywords=["delta", "epsilon", "zeta"])
        self.assertAlmostEqual(result[0].relevance_score, 3.0 / 6.0, places=2)

    def test_no_extra_keywords_unchanged(self):
        """Calling without extra_keywords must behave identically to before."""
        s = _make_source("lithium price trends in mining",
                         snippet="lithium mining price data",
                         relevance=0.0,
                         url="https://example.com/no-extra")
        result = score_relevance("lithium price trends Zimbabwe mining", [s])
        # Should score based on original keywords only — regression guard
        self.assertGreater(result[0].relevance_score, 0.0)


# ---------------------------------------------------------------------------
# SEP-023 — Funnel diagnostic logging
# ---------------------------------------------------------------------------
class TestFunnelLogging(unittest.TestCase):
    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    def test_funnel_logs_emitted(self, mock_agg, mock_xref, mock_cred,
                                  mock_score, mock_filter, mock_cluster,
                                  mock_synth):
        """Pipeline must emit INFO logs containing 'Funnel:' at each stage."""
        from engine.deep_research_service import run_deep_research

        # Setup mocks
        src1 = _make_source("Source 1", relevance=0.5, url="https://ex.com/1")
        src2 = _make_source("Source 2", relevance=0.6, url="https://ex.com/2")
        mock_agg.return_value = [src1, src2]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src1, src2]
        mock_filter.return_value = [src1, src2]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        with self.assertLogs("engine.deep_research_service", level="INFO") as cm:
            run_deep_research("test query", depth=1)

        funnel_logs = [line for line in cm.output if "Funnel:" in line]
        self.assertGreaterEqual(len(funnel_logs), 3,
                                f"Expected ≥3 Funnel: log lines, got {len(funnel_logs)}: {funnel_logs}")


# ---------------------------------------------------------------------------
# SEP-026 — Per-intent pipeline for compound queries
# ---------------------------------------------------------------------------
class TestPerIntentPipeline(unittest.TestCase):
    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_compound_query_per_intent_scoring(self, mock_decompose, mock_agg,
                                                mock_xref, mock_cred,
                                                mock_score, mock_filter,
                                                mock_cluster, mock_synth):
        """Compound query: score_relevance called once per intent with intent query."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="lithium price trends", parent_query="compound", is_primary=True),
            SearchIntent(intent_query="Zimbabwe mining impact on lithium", parent_query="compound", is_primary=False),
        ]
        src1 = _make_source("Lithium prices", relevance=0.5, url="https://ex.com/1")
        _make_source("Zimbabwe mining", relevance=0.6, url="https://ex.com/2")
        mock_agg.return_value = [src1]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.side_effect = lambda q, srcs, **kw: srcs
        mock_filter.side_effect = lambda srcs, **kw: srcs
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        run_deep_research("compound query", depth=1)

        # score_relevance must be called twice — once per intent
        self.assertEqual(mock_score.call_count, 2)
        # First call with first intent query
        self.assertEqual(mock_score.call_args_list[0][0][0], "lithium price trends")
        # Second call with second intent query
        self.assertEqual(mock_score.call_args_list[1][0][0], "Zimbabwe mining impact on lithium")

    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_single_intent_uses_existing_path(self, mock_decompose, mock_agg,
                                               mock_xref, mock_cred,
                                               mock_score, mock_filter,
                                               mock_cluster, mock_synth):
        """Single intent: existing variant generation path used, score_relevance called once."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="lithium price trends", parent_query="lithium price trends", is_primary=True),
        ]
        src1 = _make_source("Lithium prices", relevance=0.5, url="https://ex.com/1")
        mock_agg.return_value = [src1]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src1]
        mock_filter.return_value = [src1]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        run_deep_research("lithium price trends", depth=1)

        # Single intent — score_relevance called once with original query
        self.assertEqual(mock_score.call_count, 1)


# ---------------------------------------------------------------------------
# SEP-027 — Research type passthrough
# ---------------------------------------------------------------------------
class TestResearchTypePassthrough(unittest.TestCase):
    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_research_type_passed_to_pipeline(self, mock_decompose, mock_agg,
                                               mock_xref, mock_cred,
                                               mock_score, mock_filter,
                                               mock_cluster, mock_synth):
        """research_type='trend_analysis' must be stored in ResearchState."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="test query", parent_query="test query", is_primary=True),
        ]
        src = _make_source("Test", relevance=0.5, url="https://ex.com/1")
        mock_agg.return_value = [src]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src]
        mock_filter.return_value = [src]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        state = run_deep_research("test query", depth=1, research_type="trend_analysis")
        self.assertEqual(state.research_type, "trend_analysis")

    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_research_type_defaults_none(self, mock_decompose, mock_agg,
                                          mock_xref, mock_cred,
                                          mock_score, mock_filter,
                                          mock_cluster, mock_synth):
        """Calling without research_type must default to None (backward compat)."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="test query", parent_query="test query", is_primary=True),
        ]
        src = _make_source("Test", relevance=0.5, url="https://ex.com/1")
        mock_agg.return_value = [src]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src]
        mock_filter.return_value = [src]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        state = run_deep_research("test query", depth=1)
        self.assertIsNone(state.research_type)
        self.assertEqual(state.compare_subjects, [])

    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_comparative_type_with_subjects(self, mock_decompose, mock_agg,
                                             mock_xref, mock_cred,
                                             mock_score, mock_filter,
                                             mock_cluster, mock_synth):
        """research_type='comparative' with subjects must store both."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="test query", parent_query="test query", is_primary=True),
        ]
        src = _make_source("Test", relevance=0.5, url="https://ex.com/1")
        mock_agg.return_value = [src]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src]
        mock_filter.return_value = [src]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        state = run_deep_research("test query", depth=1,
                                   research_type="comparative",
                                   compare_subjects=["solar", "wind"])
        self.assertEqual(state.research_type, "comparative")
        self.assertEqual(state.compare_subjects, ["solar", "wind"])


# ---------------------------------------------------------------------------
# SEP-028 — Outline parser must handle normalized headers
# ---------------------------------------------------------------------------
class TestOutlineParserNormalization(unittest.TestCase):
    def test_parse_outline_with_quadruple_hash_headers(self):
        """Outline using #### headers must parse correctly after normalization."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers, _parse_outline
        raw = """#### Executive Summary
Lithium prices have fluctuated significantly due to supply and demand dynamics.

#### Historical Price Trends
- Price volatility driven by EV adoption
- Supply constraints from key producing regions

#### Supply Chain Impact
- Zimbabwe mining operations expanding
- Export policies affecting global supply

#### Demand Drivers
- Electric vehicle market growth
- Battery technology advancement

#### Future Outlook
- Price stabilization expected
- New mining projects coming online
"""
        normalized = _normalize_outline_headers(raw)
        result = _parse_outline(normalized, is_comparison=False, subjects=None)
        self.assertIsNotNone(result, "Outline with #### headers should parse after normalization")
        self.assertEqual(len(result.sections), 4)  # 4 theme sections (exec summary excluded)
        self.assertIn("Lithium prices", result.executive_summary)

    def test_normalize_preserves_double_hash(self):
        """## headers must pass through normalization unchanged."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "## Executive Summary\nSome text\n## Theme\n- bullet"
        self.assertEqual(_normalize_outline_headers(raw), raw)

    def test_normalize_converts_triple_hash(self):
        """### headers must be normalized to ##."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "### Executive Summary\nSome text"
        self.assertEqual(_normalize_outline_headers(raw), "## Executive Summary\nSome text")

    def test_parse_outline_accepts_partial_two_section_outline(self):
        """Outline with valid executive summary + 2 sections should still parse."""
        from workflows.deep_research.synthesizer import _parse_outline

        raw = """## Executive Summary
Regional markets saw short-term price dislocation after shipping disruptions.

## Price Transmission
- LNG shipping delays increased short-run basis volatility
- Rerouting raised freight-linked cost components

## Regulatory Response
- Emergency balancing measures were expanded
- Procurement guidance was updated for import reliability
"""
        result = _parse_outline(raw, is_comparison=False, subjects=None)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.sections), 2)


class TestOutlineBoldHeaderStripping(unittest.TestCase):
    """SEP-028: Bold markers in headers must be stripped during normalization."""

    def test_normalize_strips_bold_from_headers(self):
        """#### **Executive Summary** must normalize to ## Executive Summary."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "#### **Executive Summary**\nSome text"
        result = _normalize_outline_headers(raw)
        self.assertEqual(result, "## Executive Summary\nSome text")

    def test_normalize_strips_bold_from_theme_headers(self):
        """#### **Theme Title** must normalize to ## Theme Title."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "#### **Historical Price Trends**\n- bullet"
        result = _normalize_outline_headers(raw)
        self.assertEqual(result, "## Historical Price Trends\n- bullet")

    def test_normalize_strips_italic_from_headers(self):
        """#### *Italic Title* must normalize to ## Italic Title."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "### *Some Title*\ntext"
        result = _normalize_outline_headers(raw)
        self.assertEqual(result, "## Some Title\ntext")

    def test_outline_parses_bold_wrapped_headers(self):
        """Full outline with bold-wrapped #### headers must parse after normalization."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers, _parse_outline
        raw = """#### **Executive Summary**
Lithium prices have fluctuated significantly due to supply and demand dynamics.

#### **Historical Price Trends**
- Price volatility driven by EV adoption
- Supply constraints from key producing regions

#### **Supply Chain Impact**
- Zimbabwe mining operations expanding
- Export policies affecting global supply

#### **Demand Drivers**
- Electric vehicle market growth
- Battery technology advancement

#### **Future Outlook**
- Price stabilization expected
- New mining projects coming online
"""
        normalized = _normalize_outline_headers(raw)
        result = _parse_outline(normalized, is_comparison=False, subjects=None)
        self.assertIsNotNone(result, "Outline with bold #### headers should parse after normalization")
        self.assertEqual(len(result.sections), 4)
        self.assertIn("Lithium prices", result.executive_summary)
        # Verify bold markers are gone from section titles
        for section in result.sections:
            self.assertNotIn("**", section.title)

    def test_double_hash_bold_also_stripped(self):
        """## **Already Level 2** must also have bold stripped."""
        from workflows.deep_research.synthesizer import _normalize_outline_headers
        raw = "## **Executive Summary**\ntext"
        result = _normalize_outline_headers(raw)
        self.assertEqual(result, "## Executive Summary\ntext")


class TestClusteredFindingsParserTolerance(unittest.TestCase):
    def test_bold_finding_prefix(self):
        """**FINDING:** (bold markdown) must parse as FINDING:."""
        from engine.deep_research_service import _parse_clustered_findings
        text = (
            "**FINDING:** Lithium prices surged 40% in 2025.\n"
            "SOURCES: 1, 3\n"
            "CONFIDENCE: high\n"
        )
        src1 = _make_source("S1", url="https://ex.com/1")
        src2 = _make_source("S2", url="https://ex.com/2")
        src3 = _make_source("S3", url="https://ex.com/3")
        findings = _parse_clustered_findings(text, [src1, src2, src3])
        self.assertEqual(len(findings), 1)
        self.assertIn("Lithium prices surged", findings[0].claim)

    def test_mixed_case_finding_prefix(self):
        """Finding: (title case) must parse."""
        from engine.deep_research_service import _parse_clustered_findings
        text = (
            "Finding: Mining output declined.\n"
            "Sources: 2\n"
            "Confidence: medium\n"
        )
        src1 = _make_source("S1", url="https://ex.com/1")
        src2 = _make_source("S2", url="https://ex.com/2")
        findings = _parse_clustered_findings(text, [src1, src2])
        self.assertEqual(len(findings), 1)


class TestClusteredFindingsQualityGates(unittest.TestCase):
    def test_parse_clustered_findings_rejects_generic_boilerplate_claim(self):
        """Generic report-style claims should be dropped from parsed findings."""
        from engine.deep_research_service import _parse_clustered_findings

        text = (
            "FINDING: The following thematic findings can be extracted from the provided sources.\n"
            "SOURCES: 1, 2\n"
            "CONFIDENCE: high\n"
        )
        src1 = _make_source("S1", url="https://ex.com/1")
        src2 = _make_source("S2", url="https://ex.com/2")

        findings = _parse_clustered_findings(text, [src1, src2], query="eu power prices")
        self.assertEqual(findings, [])

    def test_parse_clustered_findings_rejects_query_unrelated_claim(self):
        """Claims with no lexical overlap to query should be dropped."""
        from engine.deep_research_service import _parse_clustered_findings

        text = (
            "FINDING: Regional fisheries stocks improved after marine habitat restoration.\n"
            "SOURCES: 1\n"
            "CONFIDENCE: medium\n"
        )
        src1 = _make_source("S1", url="https://ex.com/1")

        findings = _parse_clustered_findings(text, [src1], query="european power prices shipping costs")
        self.assertEqual(findings, [])

    def test_parse_clustered_findings_rejects_all_sources_degeneration(self):
        """Claims citing the full source set should be treated as degenerate and dropped."""
        from engine.deep_research_service import _parse_clustered_findings

        text = (
            "FINDING: Shipping disruptions increased fuel freight premiums across Europe.\n"
            "SOURCES: 1, 2, 3, 4\n"
            "CONFIDENCE: high\n"
        )
        srcs = [
            _make_source("S1", url="https://ex.com/1"),
            _make_source("S2", url="https://ex.com/2"),
            _make_source("S3", url="https://ex.com/3"),
            _make_source("S4", url="https://ex.com/4"),
        ]

        findings = _parse_clustered_findings(text, srcs, query="europe power price shipping impact")
        self.assertEqual(findings, [])

    def test_parse_clustered_findings_keeps_query_grounded_fact_claim(self):
        """Specific, query-grounded claims with bounded citations should pass."""
        from engine.deep_research_service import _parse_clustered_findings

        text = (
            "FINDING: EU ETS maritime allowance costs increased freight premiums and raised gas-linked power prices in Europe.\n"
            "SOURCES: 1, 2\n"
            "CONFIDENCE: high\n"
        )
        src1 = _make_source("S1", url="https://ex.com/1")
        src2 = _make_source("S2", url="https://ex.com/2")

        findings = _parse_clustered_findings(
            text,
            [src1, src2],
            query="EU ETS maritime costs impact on European power prices",
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("EU ETS maritime allowance costs", findings[0].claim)


# ---------------------------------------------------------------------------
# SEP-027 — SSE race condition: pipeline must not emit status="completed"
# ---------------------------------------------------------------------------
class TestNoCompletedStatusFromPipeline(unittest.TestCase):
    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_progress_callback_never_emits_completed(self, mock_decompose, mock_agg,
                                                      mock_xref, mock_cred,
                                                      mock_score, mock_filter,
                                                      mock_cluster, mock_synth):
        """run_deep_research must never emit status='completed' via progress_callback.

        The caller (_run_research_with_progress) owns the completed signal because
        only it can attach the results payload. If the pipeline emits 'completed',
        the SSE client sees it without results and displayResults() never fires.
        """
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="test query", parent_query="test query", is_primary=True),
        ]
        src = _make_source("Test", relevance=0.5, url="https://ex.com/1")
        mock_agg.return_value = [src]
        mock_cred.return_value = {"score": 0.6, "category": "Standard"}
        mock_score.return_value = [src]
        mock_filter.return_value = [src]
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        # Collect all progress callback invocations
        progress_events = []

        def capture_progress(status, phase, message):
            progress_events.append({"status": status, "phase": phase, "message": message})

        run_deep_research("test query", depth=1, progress_callback=capture_progress)

        # Pipeline must never emit status="completed" — only "running"
        completed_events = [e for e in progress_events if e["status"] == "completed"]
        self.assertEqual(
            len(completed_events), 0,
            f"Pipeline emitted {len(completed_events)} 'completed' event(s), "
            f"but only the caller should signal completion. Events: {completed_events}"
        )


class TestTopicalGateInService(unittest.TestCase):
    @patch("engine.deep_research_service.synthesize")
    @patch("engine.deep_research_service._cluster_findings")
    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    @patch("engine.deep_research_service.score_source_credibility")
    @patch("engine.deep_research_service._count_cross_references", return_value=1)
    @patch("engine.deep_research_service.aggregate_sources")
    @patch("engine.deep_research_service.decompose_query")
    def test_zero_relevance_sources_are_dropped_even_if_filter_fallback_keeps_them(
        self,
        mock_decompose,
        mock_agg,
        mock_xref,
        mock_cred,
        mock_score,
        mock_filter,
        mock_cluster,
        mock_synth,
    ):
        """Service-level topical gate must drop 0.0 relevance fallback sources."""
        from engine.deep_research_service import run_deep_research
        from engine.query_refiner import SearchIntent

        mock_decompose.return_value = [
            SearchIntent(intent_query="test query", parent_query="test query", is_primary=True),
        ]
        src = _make_source("Irrelevant Source", relevance=0.0, url="https://ex.com/irrelevant")
        mock_agg.return_value = [src]
        mock_score.return_value = [src]
        mock_filter.return_value = [src]  # Simulate reranker fallback behavior
        mock_cluster.return_value = []
        mock_synth.return_value = "Test synthesis"

        state = run_deep_research("test query", depth=1)

        self.assertEqual(state.total_sources, 0)
        mock_cred.assert_not_called()

    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    def test_strict_topical_floor_drops_low_scoring_sources(self, mock_score, mock_filter):
        """Service topical gate should reject sources below the stricter final floor."""
        from engine.deep_research_service import _score_and_filter_intent_sources

        src = _make_source("Borderline source", relevance=0.20, url="https://ex.com/borderline")
        mock_score.return_value = [src]
        mock_filter.return_value = [src]

        result = _score_and_filter_intent_sources(
            intent_query="lithium price trends",
            sources=[src],
            variants=["lithium price trends"],
            max_sources=10,
            relevance_min=0.15,
        )
        self.assertEqual(result, [])

    @patch("engine.deep_research_service.filter_relevant")
    @patch("engine.deep_research_service.score_relevance")
    def test_strict_topical_floor_keeps_high_scoring_sources(self, mock_score, mock_filter):
        """Service topical gate should keep sources at/above strict topical floor."""
        from engine.deep_research_service import _score_and_filter_intent_sources

        src = _make_source("Strong source", relevance=0.30, url="https://ex.com/strong")
        mock_score.return_value = [src]
        mock_filter.return_value = [src]

        result = _score_and_filter_intent_sources(
            intent_query="lithium price trends",
            sources=[src],
            variants=["lithium price trends"],
            max_sources=10,
            relevance_min=0.15,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_id, src.source_id)


class TestDeterministicSynthesisFallback(unittest.TestCase):
    @patch("workflows.deep_research.synthesizer.synthesize_outline", return_value=None)
    def test_outline_failure_still_returns_structured_synthesis(self, _mock_outline):
        """If outline generation fails, synthesizer should still produce structured output."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize

        src = _make_source("Market Signal Source", relevance=0.6, url="https://ex.com/signal")
        state = ResearchState(original_query="test market query")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Power prices increased due to tighter LNG supply",
                sources=[src.source_id],
                confidence="medium",
                average_credibility=0.7,
            )
        ]

        result = synthesize(state)

        self.assertIn("## Executive Summary", result)
        self.assertIn("## Evidence Highlights", result)
        self.assertIn("[Market Signal Source]", result)
        self.assertNotIn("# Research Synthesis:", result)


class TestFindingFallbackQuality(unittest.TestCase):
    def test_fallback_findings_skip_low_signal_marketing_noise(self):
        """Fallback findings should prioritize concise evidence and skip ad-like noise."""
        from engine.deep_research_service import _fallback_findings

        noisy = _make_source(
            title="Bitget: Ranked top 4 in global daily trading volume",
            snippet="Welcome gift package for new users worth 6200 USDT. Claim now.",
            relevance=0.5,
            url="https://example.com/noisy",
        )
        good = _make_source(
            title="Lithium Carbonate Price Trend Q4 2025",
            snippet="Prices rose in Q4 2025 due to supply constraints in China.",
            relevance=0.6,
            url="https://example.com/good",
        )

        findings = _fallback_findings([noisy, good])
        claims = [f.claim.lower() for f in findings]

        self.assertTrue(any("lithium carbonate price trend" in c for c in claims))
        self.assertFalse(any("welcome gift package" in c for c in claims))


class TestSynthesisQualityGuards(unittest.TestCase):
    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            "I cannot guarantee the accuracy of this summary. "
            "The market changed materially over the period."
        ),
    )
    def test_synthesize_section_requires_inline_citations(self, _mock_call_model):
        """Section expansion without inline citations must be rejected."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection

        section = OutlineSection(title="Price Dynamics", bullets=["Track major moves"])
        src = _make_source(
            title="Lithium Price Report",
            snippet="Lithium prices rose 18% in Q4 2025 due to supply constraints.",
            relevance=0.6,
            url="https://example.com/lithium-report",
        )

        result = synthesize_section(
            section=section,
            sources=[src],
            findings=[],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )
        self.assertIsNone(result)

    def test_route_findings_prefers_supported_claims_when_overlap_ties(self):
        """When overlap ties, route_findings should prefer stronger support/confidence."""
        from workflows.deep_research.synthesizer import route_findings, OutlineSection
        from engine.models import Finding

        section = OutlineSection(title="Price trend analysis", bullets=["market trend"])
        low_support = Finding(
            claim="Lithium price trend moved modestly across the year",
            sources=["s1"],
            confidence="low",
            average_credibility=0.4,
        )
        high_support = Finding(
            claim="Lithium price trend moved modestly across the year",
            sources=["s1", "s2", "s3"],
            confidence="high",
            average_credibility=0.7,
        )

        routed = route_findings(section, [low_support, high_support], max_findings=1)
        self.assertEqual(routed[0].confidence, "high")

    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            "Firstly, the following is a summary of findings [Grid Evidence]. "
            + " ".join(["This paragraph repeats generic framing instead of focused synthesis."] * 40)
        ),
    )
    def test_synthesize_section_rejects_low_quality_report_like_output(self, _mock_call_model):
        """Overlong, report-like section text should be rejected by quality gate."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection
        from engine.models import Finding

        section = OutlineSection(title="Cost Drivers", bullets=["Explain pass-through"])
        src = _make_source(
            title="Grid Evidence",
            snippet="Power prices rose after fuel costs increased.",
            relevance=0.6,
            url="https://example.com/grid-evidence",
        )
        finding = Finding(
            claim="Fuel costs drove higher power prices in the period.",
            sources=[src.source_id],
            confidence="medium",
            average_credibility=0.7,
        )

        result = synthesize_section(
            section=section,
            sources=[src],
            findings=[finding],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )
        self.assertIsNone(result)

    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            "The provided evidence indicates regulatory pressure in power markets [Policy Source]. "
            "Here are the key findings and insights: 1. Interventions capped pass-through in selected hubs."
        ),
    )
    def test_synthesize_section_rejects_list_style_findings_dump(self, _mock_call_model):
        """List-style report framing should fail section quality and fall back deterministically."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection

        section = OutlineSection(title="Regulatory Response", bullets=["Assess intervention impact"])
        src = _make_source(
            title="Policy Source",
            snippet="Regulatory interventions capped pass-through in selected hubs.",
            relevance=0.65,
            url="https://example.com/policy-source",
        )

        result = synthesize_section(
            section=section,
            sources=[src],
            findings=[],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )
        self.assertIsNone(result)

    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            "Price climb in market as outage widens spreads and volatility rises [Grid Source]."
        ),
    )
    def test_synthesize_section_accepts_morphology_variant_overlap(self, _mock_call_model):
        """Grounding gate should tolerate singular/plural and tense variants across evidence."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection

        section = OutlineSection(title="Price Dynamics", bullets=["Track market pricing shifts"])
        src = _make_source(
            title="Grid Source",
            snippet="Prices climbed in markets as outages widened spreads.",
            relevance=0.7,
            url="https://example.com/grid-source",
        )

        paragraph = synthesize_section(
            section=section,
            sources=[src],
            findings=[],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )
        self.assertIsNotNone(paragraph)
        self.assertIn("[Grid Source]", paragraph)


class TestSynthesisProvenanceAndSalvage(unittest.TestCase):
    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value="Power prices rose as freight detours tightened LNG delivery windows across EU hubs.",
    )
    def test_synthesize_section_salvages_missing_inline_citation(self, _mock_call_model):
        """Section expansion should salvage missing inline citations from routed evidence."""
        from engine.models import Finding
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection

        section = OutlineSection(title="Price Impact", bullets=["Quantify pass-through to power prices"])
        src = _make_source(
            title="EU Power Price Monitor",
            snippet="Day-ahead prices increased as shipping delays tightened gas supply.",
            relevance=0.7,
            url="https://example.com/power-monitor",
        )
        fnd = Finding(
            claim="Power prices rose as freight disruptions tightened LNG balances.",
            sources=[src.source_id],
            confidence="high",
            average_credibility=0.8,
        )

        paragraph = synthesize_section(
            section=section,
            sources=[src],
            findings=[fnd],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )

        self.assertIsNotNone(paragraph)
        self.assertIn("[EU Power Price Monitor]", paragraph)

    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            " ".join(["market"] * 190) + " [EU Power Price Monitor]."
        ),
    )
    def test_synthesize_section_readds_citation_after_truncation(self, _mock_call_model):
        """If truncation strips the only citation, salvage should re-add inline citations."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection

        section = OutlineSection(title="Price Impact", bullets=["Assess market pass-through"])
        src = _make_source(
            title="EU Power Price Monitor",
            snippet="Market conditions tightened after LNG delays in Europe.",
            relevance=0.7,
            url="https://example.com/power-monitor",
        )

        paragraph = synthesize_section(
            section=section,
            sources=[src],
            findings=[],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )

        self.assertIsNotNone(paragraph)
        self.assertIn("[EU Power Price Monitor]", paragraph)

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section")
    @patch("workflows.deep_research.synthesizer._deterministic_section_paragraph")
    def test_synthesize_marks_mixed_when_some_sections_fallback(
        self,
        mock_det_section,
        mock_synth_section,
        mock_outline,
    ):
        """Synthesis provenance must reflect mixed model+deterministic section output."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src = _make_source("Grid Update", relevance=0.6, url="https://example.com/grid")
        state = ResearchState(original_query="power market impacts")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Power prices rose due to tighter gas supply.",
                sources=[src.source_id],
                confidence="medium",
                average_credibility=0.7,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary="Summary",
            sections=[
                OutlineSection(title="Drivers", bullets=["fuel and logistics"]),
                OutlineSection(title="Regulatory", bullets=["policy effects"]),
            ],
            is_comparison=False,
            subjects=None,
        )
        mock_synth_section.side_effect = [
            "Freight detours increased fuel costs [Grid Update].",
            None,
        ]
        mock_det_section.return_value = "Fallback sentence [Grid Update]."

        _ = synthesize(state)
        self.assertEqual(state.synthesis_model, "mixed")

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section", return_value=None)
    @patch("workflows.deep_research.synthesizer._deterministic_section_paragraph", return_value="Fallback sentence")
    def test_synthesize_marks_deterministic_when_all_sections_fallback(
        self,
        _mock_det_section,
        _mock_synth_section,
        mock_outline,
    ):
        """If every section expansion fails, model provenance must be deterministic."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src = _make_source("Policy Note", relevance=0.5, url="https://example.com/policy")
        state = ResearchState(original_query="policy impact")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Policy adjustments altered dispatch economics.",
                sources=[src.source_id],
                confidence="low",
                average_credibility=0.6,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary="Summary",
            sections=[OutlineSection(title="Policy", bullets=["rule changes"])],
            is_comparison=False,
            subjects=None,
        )

        _ = synthesize(state)
        self.assertEqual(state.synthesis_model, "deterministic")

    def test_deterministic_section_prefers_more_credible_excerpt(self):
        """Deterministic section paragraphs should lead with highest-credibility relevant excerpt."""
        from workflows.deep_research.synthesizer import _deterministic_section_paragraph, OutlineSection

        section = OutlineSection(title="Regulatory Impact", bullets=["price cap mechanism"])
        high_cred = _make_source(
            title="Council Policy Brief",
            snippet="EU price cap mechanism reduced extreme gas transaction spikes in winter auctions.",
            relevance=0.55,
            url="https://example.com/high-cred",
        )
        low_cred = _make_source(
            title="Market Blog",
            snippet="Analysts discussed a price cap mechanism but offered limited supporting data.",
            relevance=0.9,
            url="https://example.com/low-cred",
        )
        high_cred.credibility_score = 0.92
        low_cred.credibility_score = 0.35

        paragraph = _deterministic_section_paragraph(
            section=section,
            routed_sources=[low_cred, high_cred],
            routed_findings=[],
            source_lookup={},
        )

        self.assertIn("[Council Policy Brief]", paragraph)
        self.assertIn("[Market Blog]", paragraph)
        self.assertIn('"', paragraph)
        self.assertLess(
            paragraph.find("[Council Policy Brief]"),
            paragraph.find("[Market Blog]"),
        )

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section", return_value=None)
    def test_all_section_deterministic_uses_source_excerpts(self, _mock_synth_section, mock_outline):
        """All-section deterministic mode should include quoted source excerpts with citations."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src_a = _make_source(
            title="Grid Operations Update",
            snippet="LNG delivery delays tightened balancing markets and lifted day-ahead prices in EU hubs.",
            relevance=0.65,
            url="https://example.com/grid-update",
        )
        src_b = _make_source(
            title="Regulatory Gazette",
            snippet="Temporary intervention capped exceptional gas trades but pass-through remained elevated.",
            relevance=0.62,
            url="https://example.com/reg-gazette",
        )
        src_a.credibility_score = 0.88
        src_b.credibility_score = 0.84

        state = ResearchState(original_query="eu hub pricing dynamics")
        state.sources_checked = [src_a, src_b]
        state.total_sources = 2
        state.findings = [
            Finding(
                claim="LNG delays tightened EU balancing markets.",
                sources=[src_a.source_id],
                confidence="high",
                average_credibility=0.88,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary="Summary [Grid Operations Update]",
            sections=[OutlineSection(title="Market Effects", bullets=["balancing and pass-through"])],
            is_comparison=False,
            subjects=None,
        )

        synthesis = synthesize(state)
        self.assertEqual(state.synthesis_model, "deterministic")
        self.assertIn("## Market Effects", synthesis)
        self.assertIn("[Grid Operations Update]", synthesis)
        self.assertIn('"', synthesis)

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section", return_value=None)
    @patch(
        "workflows.deep_research.synthesizer._deterministic_section_paragraph",
        return_value="Deterministic section synthesis [Policy Note].",
    )
    def test_all_section_fallback_keeps_outline_structure(
        self,
        _mock_det_section,
        _mock_synth_section,
        mock_outline,
    ):
        """When all model sections fail, keep outline assembly with deterministic sections."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src = _make_source("Policy Note", relevance=0.5, url="https://example.com/policy")
        state = ResearchState(original_query="policy impact")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Policy adjustments altered dispatch economics.",
                sources=[src.source_id],
                confidence="low",
                average_credibility=0.6,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary="Summary [Policy Note]",
            sections=[OutlineSection(title="Policy", bullets=["rule changes"])],
            is_comparison=False,
            subjects=None,
        )

        synthesis = synthesize(state)

        self.assertEqual(state.synthesis_model, "deterministic")
        self.assertIn("## Policy", synthesis)
        self.assertIn("Deterministic section synthesis [Policy Note].", synthesis)
        self.assertNotIn("## Evidence Highlights", synthesis)

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section")
    def test_rewrites_low_quality_executive_summary(
        self,
        mock_synth_section,
        mock_outline,
    ):
        """Low-quality model executive summaries should be replaced with evidence-grounded summary."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src = _make_source(
            title="EU Power Price Monitor",
            snippet="Day-ahead prices increased as gas shipping delays tightened supply.",
            relevance=0.7,
            url="https://example.com/eu-power",
        )
        state = ResearchState(original_query="power market effects")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Power prices increased as gas shipping delays tightened supply.",
                sources=[src.source_id],
                confidence="high",
                average_credibility=0.8,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary=(
                "The following are key insights from the documents: "
                "1. costs rose 2. trade shifted 3. policy changed."
            ),
            sections=[OutlineSection(title="Drivers", bullets=["shipping and policy"])],
            is_comparison=False,
            subjects=None,
        )
        mock_synth_section.return_value = "Shipping delays pushed gas-linked power costs higher [EU Power Price Monitor]."

        synthesis = synthesize(state)

        self.assertNotIn("The following are key insights", synthesis)
        self.assertIn("[EU Power Price Monitor]", synthesis)

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section")
    def test_rewrites_uncited_executive_summary(self, mock_synth_section, mock_outline):
        """Executive summaries without citations should be rewritten from evidence."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        src = _make_source(
            title="Regional Grid Bulletin",
            snippet="Power prices rose after pipeline maintenance constrained fuel supply.",
            relevance=0.8,
            url="https://example.com/grid-bulletin",
        )
        state = ResearchState(original_query="regional power market pressure")
        state.sources_checked = [src]
        state.total_sources = 1
        state.findings = [
            Finding(
                claim="Power prices rose after pipeline maintenance constrained fuel supply.",
                sources=[src.source_id],
                confidence="high",
                average_credibility=0.75,
            )
        ]

        mock_outline.return_value = OutlineResult(
            executive_summary="Power markets tightened during the period due to fuel bottlenecks.",
            sections=[OutlineSection(title="Drivers", bullets=["fuel constraints"])],
            is_comparison=False,
            subjects=None,
        )
        mock_synth_section.return_value = (
            "Fuel bottlenecks tightened dispatch economics and lifted spot prices "
            "[Regional Grid Bulletin]."
        )

        synthesis = synthesize(state)

        exec_summary = synthesis.split("## Drivers")[0]
        self.assertIn("[Regional Grid Bulletin]", exec_summary)


class TestResearchStateCompatibility(unittest.TestCase):
    def test_init_research_state_supports_legacy_constructor(self):
        """Shared service must work with legacy ResearchState signatures."""
        from engine.deep_research_service import _init_research_state

        class LegacyResearchState:
            def __init__(self, original_query, max_depth=3, max_iterations=5):
                self.original_query = original_query
                self.max_depth = max_depth
                self.max_iterations = max_iterations

        state = _init_research_state(
            original_query="test query",
            depth=2,
            refined_query="refined query",
            research_type="trend_analysis",
            compare_subjects=["a", "b"],
            state_cls=LegacyResearchState,
        )

        self.assertEqual(state.original_query, "test query")
        self.assertEqual(state.max_depth, 2)
        self.assertEqual(state.max_iterations, 1)
        self.assertFalse(hasattr(state, "refined_query"))


class TestSynthesizeSectionHeaderStripping(unittest.TestCase):
    """SEP-028: synthesize_section must strip ALL markdown header levels."""

    @patch(
        "workflows.deep_research.synthesizer._call_research_synthesis_model",
        return_value=(
            "#### Sub-heading leaked\n"
            "Some body text with a citation [Test Source].\n"
            "##### Another leaked header\n"
            "###### Deep header\n"
            "## Expected stripped\n"
            "# Also stripped\n"
            "### Mid-level header\n"
            "Final paragraph [Test Source]."
        ),
    )
    def test_all_header_levels_stripped(self, _mock_call_model):
        """Headers # through ###### must be stripped from section output."""
        from workflows.deep_research.synthesizer import synthesize_section, OutlineSection
        from engine.models import Finding

        section = OutlineSection(title="Test Section", bullets=["Q?"])
        src = _make_source(
            title="Test Source",
            snippet="Final paragraph references test source evidence for market section.",
            relevance=0.6,
            url="https://example.com/test-source",
        )
        finding = Finding(
            claim="Final paragraph references test source evidence.",
            sources=[src.source_id],
            confidence="medium",
            average_credibility=0.6,
        )
        result = synthesize_section(
            section=section,
            sources=[src],
            findings=[finding],
            state=MagicMock(),
            is_comparison=False,
            subjects=None,
        )
        self.assertIsNotNone(result)
        for line in result.split("\n"):
            self.assertFalse(
                line.strip().startswith("#"),
                f"Header leaked into output: {line!r}",
            )


class TestResearchSynthesisModelCaller(unittest.TestCase):
    @patch("tools.specialist.client.create_specialist_client")
    def test_prefers_specialist_client_with_analyst_system_prompt(self, mock_create_client):
        """Deep research synthesis caller should use specialist client with analyst persona."""
        from workflows.deep_research.synthesizer import _call_research_synthesis_model

        fake_client = MagicMock()
        fake_client.chat_complete.return_value = {"choices": [{"message": {"content": "Analyst synthesis"}}]}
        fake_client.extract_content.return_value = "Analyst synthesis"
        mock_create_client.return_value = fake_client

        result = _call_research_synthesis_model("Explain price impacts.")

        self.assertEqual(result, "Analyst synthesis")
        fake_client.chat_complete.assert_called_once()
        messages = fake_client.chat_complete.call_args[0][0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("energy and electricity market research analyst", messages[0]["content"])

    @patch("tools.specialist.client.create_specialist_client", side_effect=RuntimeError("boom"))
    @patch("tools.registry.TOOL_FUNCTIONS", {"use_reasoning_model": lambda prompt: "Fallback synthesis"})
    def test_falls_back_to_tool_function_when_client_fails(self, _mock_create_client):
        """Caller should fallback to use_reasoning_model for compatibility when client path fails."""
        from workflows.deep_research.synthesizer import _call_research_synthesis_model

        result = _call_research_synthesis_model("Explain policy drivers.")
        self.assertEqual(result, "Fallback synthesis")


if __name__ == "__main__":
    unittest.main()
