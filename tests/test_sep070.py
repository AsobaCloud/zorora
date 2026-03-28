"""Tests for SEP-070 and SEP-071: Market context injection and newsroom ranking.

Covers:
  SEP-070 — Always inject market/regulatory data context into synthesis prompts
    for energy-domain queries:
    1. _build_market_context_for_query accepts a `force` keyword parameter.
    2. When force=True, market context is returned even for queries with no
       market keywords (e.g. "Southern Africa renewable opportunity").
    3. When force=False (default), the keyword gate still applies — non-market
       queries return an empty string (backward compatibility).

  SEP-071 — Boost newsroom source credibility and relevance scoring:
    4. newsroom: base credibility score is 0.85 (was 0.75).
    5. asoba.co/newsroom base credibility score is 0.85 (was 0.75).
    6. score_relevance in reranker applies a +0.10 relevance boost to sources
       with source_type='newsroom'.
    7. A newsroom source with the same keyword overlap as a generic web source
       ranks higher after the boost.
    8. A newsroom source with zero keyword overlap still gets the +0.10 boost
       applied to its base score (0.0 + 0.10 = 0.10).
    9. Non-newsroom sources are NOT boosted.

All tests are expected to FAIL until SEP-070 and SEP-071 are implemented.
"""

from __future__ import annotations

import pathlib
import sys
import unittest.mock as mock

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so engine/workflow imports resolve.
# ---------------------------------------------------------------------------
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# Helpers
# ===========================================================================


def _make_source(title: str, snippet: str = "", source_type: str = "web",
                 url: str = ""):
    from engine.models import Source
    url = url or f"https://example.com/{title.replace(' ', '_')}"
    src = Source(
        source_id=Source.generate_id(url),
        url=url,
        title=title,
        content_snippet=snippet,
        source_type=source_type,
    )
    return src


# ===========================================================================
# SEP-070 — _build_market_context_for_query force parameter
# ===========================================================================


class TestBuildMarketContextForQueryForceParam:
    """_build_market_context_for_query must accept and honour a force= kwarg."""

    def _import_fn(self):
        from engine.deep_research_service import _build_market_context_for_query
        return _build_market_context_for_query

    def test_function_accepts_force_keyword(self):
        """_build_market_context_for_query must accept a force keyword argument."""
        fn = self._import_fn()
        import inspect
        sig = inspect.signature(fn)
        assert "force" in sig.parameters, (
            "_build_market_context_for_query does not have a 'force' parameter. "
            "SEP-070 requires adding force=False as a keyword argument."
        )

    def test_force_false_is_default(self):
        """force must default to False so existing call-sites are unaffected."""
        fn = self._import_fn()
        import inspect
        sig = inspect.signature(fn)
        param = sig.parameters["force"]
        assert param.default is False, (
            f"Expected force default to be False, got {param.default!r}. "
            "This would break backward compatibility."
        )

    def test_force_true_returns_nonempty_string_for_non_market_query(self):
        """When force=True, market context is injected even without market keywords."""
        fn = self._import_fn()

        # Stub out heavy dependencies so the function can run in tests.
        fake_context = "STUBBED MARKET CONTEXT"

        with (
            mock.patch(
                "engine.deep_research_service.detect_market_intent",
                return_value=False,
            ),
            mock.patch("engine.deep_research_service.MarketWorkflow") as mock_wf_cls,
            mock.patch(
                "engine.deep_research_service.build_market_context",
                return_value=fake_context,
            ),
        ):
            mock_wf = mock_wf_cls.return_value
            mock_wf.compute_summary.return_value = {"oil": 75.0}

            result = fn("Southern Africa renewable opportunity", force=True)

        assert result != "", (
            "With force=True, _build_market_context_for_query must return a "
            "non-empty string even when detect_market_intent returns False."
        )
        assert result == fake_context, (
            f"Expected {fake_context!r}, got {result!r}."
        )

    def test_force_false_no_market_keywords_returns_empty(self):
        """When force=False (default), a non-market query must still return ''."""
        fn = self._import_fn()

        with mock.patch(
            "engine.deep_research_service.detect_market_intent",
            return_value=False,
        ):
            result = fn("Southern Africa renewable opportunity", force=False)

        assert result == "", (
            "With force=False, a query without market keywords must return '' "
            "(backward compatibility)."
        )

    def test_force_false_default_no_market_keywords_returns_empty(self):
        """The default call (no force arg) must behave identically to force=False."""
        fn = self._import_fn()

        with mock.patch(
            "engine.deep_research_service.detect_market_intent",
            return_value=False,
        ):
            result = fn("Southern Africa renewable opportunity")

        assert result == "", (
            "The default call must return '' for a non-market query (backward compat)."
        )

    def test_force_true_calls_market_workflow(self):
        """When force=True, the market workflow must be invoked even without intent."""
        fn = self._import_fn()

        with (
            mock.patch(
                "engine.deep_research_service.detect_market_intent",
                return_value=False,
            ),
            mock.patch("engine.deep_research_service.MarketWorkflow") as mock_wf_cls,
            mock.patch(
                "engine.deep_research_service.build_market_context",
                return_value="ctx",
            ),
        ):
            mock_wf = mock_wf_cls.return_value
            mock_wf.compute_summary.return_value = {"oil": 75.0}

            fn("Southern Africa renewable opportunity", force=True)

            mock_wf.update_all.assert_called_once(), (
                "MarketWorkflow.update_all() must be called when force=True."
            )
            mock_wf.compute_summary.assert_called_once(), (
                "MarketWorkflow.compute_summary() must be called when force=True."
            )

    def test_force_true_with_empty_summary_returns_empty(self):
        """If compute_summary returns nothing, force=True still returns '' gracefully."""
        fn = self._import_fn()

        with (
            mock.patch(
                "engine.deep_research_service.detect_market_intent",
                return_value=False,
            ),
            mock.patch("engine.deep_research_service.MarketWorkflow") as mock_wf_cls,
            mock.patch(
                "engine.deep_research_service.build_market_context",
                return_value="",
            ),
        ):
            mock_wf = mock_wf_cls.return_value
            mock_wf.compute_summary.return_value = {}

            result = fn("some query", force=True)

        # Either "" or the result of build_market_context("") — both falsy is fine.
        assert result == "", (
            "When compute_summary returns nothing, force=True must still return '' "
            "without raising an exception."
        )


# ===========================================================================
# SEP-071 — Newsroom base credibility score = 0.85
# ===========================================================================


class TestNewsroomBaseCredibility:
    """Newsroom entries in BASE_CREDIBILITY must be 0.85."""

    def _import_catalog(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY
        return BASE_CREDIBILITY

    def test_newsroom_prefix_credibility_is_0_85(self):
        """'newsroom:' key must have score=0.85 (was 0.75 before SEP-071)."""
        catalog = self._import_catalog()
        entry = catalog.get("newsroom:")
        assert entry is not None, (
            "'newsroom:' key is missing from BASE_CREDIBILITY."
        )
        assert entry["score"] == 0.85, (
            f"newsroom: credibility score is {entry['score']}, expected 0.85. "
            "SEP-071 requires upgrading from 0.75 to 0.85."
        )

    def test_asoba_newsroom_url_credibility_is_0_85(self):
        """'asoba.co/newsroom' key must also be 0.85."""
        catalog = self._import_catalog()
        entry = catalog.get("asoba.co/newsroom")
        assert entry is not None, (
            "'asoba.co/newsroom' key is missing from BASE_CREDIBILITY."
        )
        assert entry["score"] == 0.85, (
            f"asoba.co/newsroom credibility score is {entry['score']}, expected 0.85."
        )

    def test_score_source_credibility_newsroom_url(self):
        """score_source_credibility must return base_score=0.85 for newsroom URLs."""
        from workflows.deep_research.credibility import score_source_credibility
        result = score_source_credibility("newsroom:article-123")
        assert result["base_score"] == 0.85, (
            f"score_source_credibility('newsroom:article-123') returned base_score="
            f"{result['base_score']}, expected 0.85."
        )

    def test_score_source_credibility_asoba_newsroom_url(self):
        """score_source_credibility must return base_score=0.85 for asoba newsroom URLs."""
        from workflows.deep_research.credibility import score_source_credibility
        result = score_source_credibility("https://asoba.co/newsroom/article-456")
        assert result["base_score"] == 0.85, (
            f"score_source_credibility for asoba newsroom returned base_score="
            f"{result['base_score']}, expected 0.85."
        )


# ===========================================================================
# SEP-071 — Newsroom +0.10 relevance boost in reranker
# ===========================================================================


class TestNewsroomRelevanceBoost:
    """score_relevance must apply a +0.10 boost to sources with source_type='newsroom'."""

    def _score(self, query: str, sources):
        from workflows.deep_research.reranker import score_relevance
        return score_relevance(query, sources)

    def test_newsroom_source_gets_plus_010_boost(self):
        """A newsroom source's relevance_score must be 0.10 higher than its raw overlap."""
        # Build two identical sources — same title, same snippet — differing only in type.
        query = "solar energy investment Africa"
        shared_title = "Solar energy investment opportunities in Africa"
        shared_snippet = "Growing solar investment across African markets"

        web_src = _make_source(shared_title, shared_snippet, source_type="web",
                               url="https://example.com/web")
        news_src = _make_source(shared_title, shared_snippet, source_type="newsroom",
                                url="newsroom:solar-africa-001")

        scored = self._score(query, [web_src, news_src])

        web_result = next(s for s in scored if s.source_type == "web")
        news_result = next(s for s in scored if s.source_type == "newsroom")

        assert news_result.relevance_score == pytest.approx(
            web_result.relevance_score + 0.10, abs=1e-6
        ), (
            f"newsroom relevance_score ({news_result.relevance_score:.4f}) must be "
            f"exactly 0.10 higher than the web score ({web_result.relevance_score:.4f}). "
            "SEP-071 requires a +0.10 boost for newsroom sources."
        )

    def test_newsroom_source_ranks_above_web_with_same_overlap(self):
        """After scoring, a newsroom source must rank above a web source with equal overlap."""
        query = "solar energy Africa"
        shared_title = "solar energy Africa market analysis"
        shared_snippet = "solar projects across Africa"

        web_src = _make_source(shared_title, shared_snippet, source_type="web",
                               url="https://generic.com/article")
        news_src = _make_source(shared_title, shared_snippet, source_type="newsroom",
                                url="newsroom:solar-africa-002")

        scored = self._score(query, [web_src, news_src])

        # After sorting, newsroom must appear first.
        assert scored[0].source_type == "newsroom", (
            f"Expected newsroom source to rank first, but got '{scored[0].source_type}'. "
            "The +0.10 boost must make newsroom outrank web with equal keyword overlap."
        )

    def test_non_newsroom_source_is_not_boosted(self):
        """Web, academic, and internal sources must NOT receive a newsroom boost."""
        query = "solar energy Africa"
        title = "solar energy Africa market analysis"
        snippet = "solar projects across Africa"

        web_src = _make_source(title, snippet, source_type="web",
                               url="https://web.example.com/a")
        academic_src = _make_source(title, snippet, source_type="academic",
                                    url="https://academic.example.com/a")
        # Score an identical newsroom source to get the boosted baseline.
        news_src = _make_source(title, snippet, source_type="newsroom",
                                url="newsroom:ref-003")

        scored_news = self._score(query, [news_src])
        scored_web = self._score(query, [web_src])
        scored_academic = self._score(query, [academic_src])

        boosted_score = scored_news[0].relevance_score
        web_score = scored_web[0].relevance_score
        academic_score = scored_academic[0].relevance_score

        assert web_score == pytest.approx(boosted_score - 0.10, abs=1e-6), (
            f"Web source score {web_score:.4f} should be exactly 0.10 below newsroom "
            f"score {boosted_score:.4f}. Web sources must not receive the newsroom boost."
        )
        assert academic_score == pytest.approx(boosted_score - 0.10, abs=1e-6), (
            f"Academic source score {academic_score:.4f} should be exactly 0.10 below "
            f"newsroom score {boosted_score:.4f}. Academic sources must not receive boost."
        )

    def test_newsroom_zero_overlap_gets_boost_applied(self):
        """A newsroom source with no keyword overlap still gets +0.10 (0.0 + 0.10 = 0.10)."""
        query = "solar energy Africa"
        # Title and snippet share zero keywords with the query.
        news_src = _make_source(
            "Completely unrelated topic about shipping containers",
            "Container logistics and port operations",
            source_type="newsroom",
            url="newsroom:unrelated-001",
        )

        scored = self._score(query, [news_src])

        assert scored[0].relevance_score == pytest.approx(0.10, abs=1e-6), (
            f"Newsroom source with 0 keyword overlap should have relevance_score=0.10, "
            f"got {scored[0].relevance_score:.4f}. "
            "The +0.10 boost must apply even when raw keyword overlap is zero."
        )

    def test_newsroom_boost_applied_before_sorting(self):
        """Ranking must reflect the boosted scores, not the pre-boost scores."""
        query = "energy storage battery"
        # Newsroom source has zero keyword overlap, web source has partial overlap.
        # After boost, newsroom (0 + 0.10 = 0.10) must beat web with 0 overlap (0.0).
        web_zero = _make_source(
            "Unrelated topic X",
            "Nothing relevant here",
            source_type="web",
            url="https://web.example.com/zero",
        )
        news_zero = _make_source(
            "Unrelated topic X",
            "Nothing relevant here",
            source_type="newsroom",
            url="newsroom:zero-004",
        )

        scored = self._score(query, [web_zero, news_zero])

        # Both have zero raw overlap, but newsroom should end up first.
        assert scored[0].source_type == "newsroom", (
            "Even with no keyword overlap, newsroom must rank above web after +0.10 boost. "
            f"Top source type was '{scored[0].source_type}'."
        )

    def test_newsroom_in_top_10_for_energy_query(self):
        """A newsroom source with relevant tags must appear in the top 10 results."""
        query = "Southern Africa renewable energy opportunity"

        # 15 generic web sources with decent overlap
        sources = [
            _make_source(
                f"Southern Africa energy market report {i}",
                f"renewable energy opportunities in Southern Africa report {i}",
                source_type="web",
                url=f"https://web.example.com/report-{i}",
            )
            for i in range(15)
        ]
        # One newsroom source with strong topic overlap
        newsroom_src = _make_source(
            "Southern Africa renewable energy investment outlook",
            "Renewable energy opportunities across Southern Africa",
            source_type="newsroom",
            url="newsroom:sa-renewable-005",
        )
        sources.append(newsroom_src)

        scored = self._score(query, sources)
        top_10_ids = {s.source_id for s in scored[:10]}

        assert newsroom_src.source_id in top_10_ids, (
            "Newsroom source with matching topic overlap must appear in the top 10 "
            "results after the +0.10 boost. It was not found in the top 10."
        )
