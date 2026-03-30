"""Tests for SEP-072/SEP-077: Enable _cluster_findings for non-diligence queries.

Covers:
  1. _cluster_findings IS called for non-diligence queries (not skipped)
  2. state.findings is populated (non-empty) after clustering for non-diligence
  3. Diligence queries still have state.findings = [] (clustering remains skipped)
  4. Progress callback receives a clustering/cross_reference message that does NOT
     contain "Skipping"
  5. Each item in state.findings is a Finding with claim, sources, confidence attrs
  6. Fallback behavior: if clustering fails, state.findings gets 1:1 source-to-finding
     mapping (not empty)

All tests are expected to FAIL until SEP-072/SEP-077 is implemented.
"""

from __future__ import annotations

import pathlib
import sys
from typing import List



PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_service():
    import engine.deep_research_service as svc
    return svc


def _make_source(
    title: str,
    *,
    snippet: str,
    url: str,
    full: str = "",
    credibility: float = 0.75,
    relevance: float = 0.65,
    source_type: str = "web",
):
    from engine.models import Source
    return Source(
        source_id=Source.generate_id(url),
        url=url,
        title=title,
        source_type=source_type,
        credibility_score=credibility,
        relevance_score=relevance,
        content_snippet=snippet,
        content_full=full,
    )


def _make_three_sources() -> List:
    return [
        _make_source(
            "Solar capacity in Southern Africa rises sharply",
            snippet="Solar PV installations in the SAPP region grew 40% in 2024, "
                    "driven by falling panel costs and new IPP agreements.",
            url="https://example.com/solar-1",
        ),
        _make_source(
            "SAPP transmission constraints limit RE integration",
            snippet="Bottlenecks on cross-border SAPP lines continue to delay "
                    "renewable energy dispatch across member utilities.",
            url="https://example.com/sapp-2",
        ),
        _make_source(
            "Battery storage deployments accelerate in South Africa",
            snippet="South Africa's BESS pipeline doubled in 2024 following NERSA "
                    "approval of 1.2 GW of utility-scale storage projects.",
            url="https://example.com/bess-3",
        ),
    ]


def _minimal_clustering_response() -> str:
    """Return a valid clustering model response for three sources about solar/SAPP."""
    return (
        "FINDING: Solar PV installations in the SAPP region grew significantly in 2024 driven by falling costs.\n"
        "SOURCES: 1, 2\n"
        "CONFIDENCE: medium\n\n"
        "FINDING: Battery storage deployment in South Africa accelerated following regulatory approvals.\n"
        "SOURCES: 3\n"
        "CONFIDENCE: low\n"
    )


# ---------------------------------------------------------------------------
# 1. _cluster_findings IS called for non-diligence queries
# ---------------------------------------------------------------------------


class TestClusterFindingsCalledForNonDiligence:
    """After SEP-077, _cluster_findings must be invoked in the non-diligence path."""

    def test_cluster_findings_called_once_for_general_query(self, monkeypatch):
        """_cluster_findings must be called exactly once for a non-diligence query.

        Currently the dispatch block sets state.findings = [] and emits a
        "Skipping finding clustering" message without ever calling the function.
        After SEP-077, it must call _cluster_findings with (query, sources).
        """
        svc = _import_service()
        sources = _make_three_sources()

        call_log = []

        def capture_cluster(query, srcs):
            call_log.append({"query": query, "sources": list(srcs)})
            # Return minimal valid findings so the pipeline continues.
            from engine.models import Finding
            return [
                Finding(
                    claim="Solar capacity grew in SAPP region.",
                    sources=[srcs[0].source_id],
                    confidence="low",
                    average_credibility=0.75,
                )
            ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", capture_cluster)
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nSynthesis result.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        svc.run_deep_research("solar capacity trends in southern Africa", depth=1)

        assert len(call_log) == 1, (
            f"_cluster_findings was called {len(call_log)} times, expected 1 — "
            "SEP-077 requires calling _cluster_findings for non-diligence queries"
        )

    def test_cluster_findings_receives_query_and_sources(self, monkeypatch):
        """_cluster_findings must be called with the research query and sources list.

        Verifies the arguments passed to the function are meaningful, not empty.
        """
        svc = _import_service()
        sources = _make_three_sources()

        captured = {}

        def capture_cluster(query, srcs):
            captured["query"] = query
            captured["sources"] = list(srcs)
            from engine.models import Finding
            return [
                Finding(
                    claim=f"Solar energy relevant to {query}.",
                    sources=[srcs[0].source_id],
                    confidence="low",
                    average_credibility=0.75,
                )
            ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", capture_cluster)
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        query = "solar capacity trends in southern Africa"
        svc.run_deep_research(query, depth=1)

        assert "query" in captured, "_cluster_findings was never called"
        assert captured["query"], "query passed to _cluster_findings was empty"
        assert len(captured["sources"]) > 0, (
            "sources passed to _cluster_findings was empty — "
            "must receive the ranked source list"
        )


# ---------------------------------------------------------------------------
# 2. state.findings is populated (non-empty) after clustering
# ---------------------------------------------------------------------------


class TestStateFindingsPopulated:
    """state.findings must be non-empty after a successful non-diligence run."""

    def test_state_findings_non_empty_after_non_diligence_run(self, monkeypatch):
        """state.findings must contain at least one Finding after clustering.

        Currently state.findings is set to [] unconditionally. After SEP-077
        the list must be populated with the result of _cluster_findings.
        """
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        stub_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id, sources[1].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
            Finding(
                claim="Battery storage deployment in South Africa accelerated.",
                sources=[sources[2].source_id],
                confidence="low",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(stub_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, (
            "state.findings is empty after a non-diligence run — "
            "SEP-077 requires populating findings from _cluster_findings output"
        )

    def test_state_findings_match_cluster_findings_output(self, monkeypatch):
        """state.findings must contain exactly the findings returned by _cluster_findings.

        Verifies that the findings returned by the clustering function are stored
        in state.findings, not discarded or replaced.
        """
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        expected_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(expected_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert state.findings == expected_findings, (
            f"state.findings={state.findings!r} does not match the findings returned by "
            "_cluster_findings — the findings must be stored, not discarded"
        )


# ---------------------------------------------------------------------------
# 3. Diligence queries still have state.findings = [] (clustering skipped)
# ---------------------------------------------------------------------------


class TestDiligenceSkipsClustering:
    """Diligence queries must NOT call _cluster_findings; findings stays []."""

    def test_diligence_does_not_call_cluster_findings(self, monkeypatch):
        """_cluster_findings must NOT be called for research_type='diligence'.

        Diligence follows a different synthesis path (synthesize_direct + context
        building). The clustering step must remain skipped for diligence.
        """
        svc = _import_service()
        sources = _make_three_sources()

        cluster_calls = []

        def fail_if_called(query, srcs):
            cluster_calls.append(1)
            raise AssertionError("_cluster_findings must not run for diligence queries")

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", fail_if_called)
        monkeypatch.setattr(svc, "_build_diligence_context", lambda meta: ("diligence ctx", {}))
        monkeypatch.setattr(svc, "synthesize_direct", lambda state, **kw: "## Summary\nDiligence result.")

        asset_meta = {
            "name": "Kathu Solar Park",
            "technology": "solar",
            "country": "ZA",
            "capacity_mw": 100,
        }
        svc.run_deep_research(
            "diligence on Kathu Solar Park",
            depth=1,
            research_type="diligence",
            asset_metadata=asset_meta,
        )

        assert len(cluster_calls) == 0, (
            "_cluster_findings was called for a diligence query — "
            "SEP-077 must only enable clustering for non-diligence queries"
        )

    def test_diligence_findings_remain_empty(self, monkeypatch):
        """state.findings must be [] after a diligence run.

        The current behavior (findings = []) must be preserved for diligence.
        """
        svc = _import_service()
        sources = _make_three_sources()

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_build_diligence_context", lambda meta: ("diligence ctx", {}))
        monkeypatch.setattr(svc, "synthesize_direct", lambda state, **kw: "## Summary\nDiligence result.")

        asset_meta = {
            "name": "Kathu Solar Park",
            "technology": "solar",
            "country": "ZA",
            "capacity_mw": 100,
        }
        result = svc.run_deep_research(
            "diligence on Kathu Solar Park",
            depth=1,
            research_type="diligence",
            asset_metadata=asset_meta,
        )

        assert result.findings == [], (
            f"state.findings={result.findings!r} should be [] for diligence queries, "
            "not populated — clustering must remain skipped for the diligence path"
        )


# ---------------------------------------------------------------------------
# 4. Progress callback does NOT receive "Skipping" for non-diligence
# ---------------------------------------------------------------------------


class TestProgressMessagesReflectClustering:
    """The cross_reference progress event must not say "Skipping" for non-diligence."""

    def test_cross_reference_message_does_not_say_skipping(self, monkeypatch):
        """For a non-diligence query the cross_reference progress event must NOT
        include the word 'Skipping'.

        The current code emits:
            'Skipping finding clustering; sending N ranked sources directly to synthesis.'
        After SEP-077 this message must be replaced with something that reflects
        the clustering step being active, e.g., 'Clustering findings...' or
        'Cross-referencing sources into thematic findings...'.
        """
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        emitted = []

        def capture_callback(status, phase, message):
            emitted.append({"status": status, "phase": phase, "message": message})

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(
            svc,
            "_cluster_findings",
            lambda q, s: [
                Finding(
                    claim="Solar capacity grew in SAPP region driven by policy.",
                    sources=[s[0].source_id],
                    confidence="low",
                    average_credibility=0.75,
                )
            ],
        )
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        svc.run_deep_research(
            "solar capacity in southern Africa",
            depth=1,
            progress_callback=capture_callback,
        )

        cross_ref_events = [e for e in emitted if e["phase"] == "cross_reference"]
        assert cross_ref_events, (
            "No cross_reference progress events were emitted — "
            "the service must emit a cross_reference event during the clustering step"
        )

        skipping_events = [e for e in cross_ref_events if "skipping" in e["message"].lower()]
        assert len(skipping_events) == 0, (
            f"cross_reference event still says 'Skipping': {skipping_events[0]['message']!r} — "
            "SEP-077 must update the progress message to reflect that clustering is active"
        )

    def test_cross_reference_message_mentions_clustering_or_findings(self, monkeypatch):
        """The cross_reference message must reference clustering or findings activity.

        After SEP-077, the message should confirm clustering is happening, e.g.,
        it should contain 'cluster', 'finding', 'cross-referenc', or 'thematic'.
        """
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        emitted = []

        def capture_callback(status, phase, message):
            emitted.append({"phase": phase, "message": message})

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(
            svc,
            "_cluster_findings",
            lambda q, s: [
                Finding(
                    claim="Solar capacity grew in SAPP region driven by policy.",
                    sources=[s[0].source_id],
                    confidence="low",
                    average_credibility=0.75,
                )
            ],
        )
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        svc.run_deep_research(
            "solar capacity in southern Africa",
            depth=1,
            progress_callback=capture_callback,
        )

        cross_ref_messages = [
            e["message"].lower()
            for e in emitted
            if e["phase"] == "cross_reference"
        ]
        assert cross_ref_messages, "No cross_reference events emitted"

        # Require at least one message that is NOT just a "Skipping" notice
        # and that actually references active clustering.
        # The current pre-SEP-077 message ('Skipping finding clustering...') would
        # pass a naive keyword check because it contains 'finding'. We explicitly
        # exclude messages that start with 'skipping'.
        active_cluster_keywords = ("cluster", "cross-referenc", "thematic", "grouping")
        non_skipping_messages = [
            msg for msg in cross_ref_messages if not msg.startswith("skipping")
        ]
        found_active_keyword = any(
            kw in msg
            for msg in non_skipping_messages
            for kw in active_cluster_keywords
        )
        assert found_active_keyword, (
            f"cross_reference message(s) {cross_ref_messages!r} have no non-skipping message "
            f"containing an active clustering keyword {active_cluster_keywords} — "
            "SEP-077 must replace the 'Skipping' message with one that confirms "
            "thematic clustering is being performed (e.g., 'Clustering findings...')"
        )


# ---------------------------------------------------------------------------
# 5. Each Finding has claim, sources, confidence attributes
# ---------------------------------------------------------------------------


class TestFindingObjectStructure:
    """Every item in state.findings must be a Finding with required attributes."""

    def test_findings_are_finding_instances(self, monkeypatch):
        """Each element of state.findings must be a Finding dataclass instance.

        Verifies the clustering output is properly typed, not raw dicts or strings.
        """
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        stub_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id, sources[1].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(stub_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, (
            "state.findings is empty — _cluster_findings output was not stored in state; "
            "cannot verify Finding type without at least one element"
        )
        for i, finding in enumerate(state.findings):
            assert isinstance(finding, Finding), (
                f"state.findings[{i}] is {type(finding).__name__!r}, expected Finding — "
                "all findings must be Finding dataclass instances"
            )

    def test_findings_have_claim_attribute(self, monkeypatch):
        """Each Finding must have a non-empty string .claim attribute."""
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        stub_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(stub_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, "state.findings is empty — no findings to check"
        for i, finding in enumerate(state.findings):
            assert hasattr(finding, "claim"), f"findings[{i}] has no .claim attribute"
            assert isinstance(finding.claim, str), (
                f"findings[{i}].claim is {type(finding.claim).__name__!r}, expected str"
            )
            assert finding.claim.strip(), f"findings[{i}].claim is empty"

    def test_findings_have_sources_attribute_as_list(self, monkeypatch):
        """Each Finding must have a .sources attribute that is a non-empty list."""
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        stub_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id, sources[1].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(stub_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, "state.findings is empty — no findings to check"
        for i, finding in enumerate(state.findings):
            assert hasattr(finding, "sources"), f"findings[{i}] has no .sources attribute"
            assert isinstance(finding.sources, list), (
                f"findings[{i}].sources is {type(finding.sources).__name__!r}, expected list"
            )
            assert len(finding.sources) > 0, f"findings[{i}].sources is an empty list"

    def test_findings_have_confidence_attribute(self, monkeypatch):
        """Each Finding must have a .confidence attribute of 'high', 'medium', or 'low'."""
        svc = _import_service()
        sources = _make_three_sources()

        from engine.models import Finding

        stub_findings = [
            Finding(
                claim="Solar PV installations in SAPP grew driven by falling costs.",
                sources=[sources[0].source_id],
                confidence="medium",
                average_credibility=0.75,
            ),
        ]

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: list(stub_findings))
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, "state.findings is empty — no findings to check"
        valid_confidence = {"high", "medium", "low"}
        for i, finding in enumerate(state.findings):
            assert hasattr(finding, "confidence"), f"findings[{i}] has no .confidence attribute"
            assert finding.confidence in valid_confidence, (
                f"findings[{i}].confidence={finding.confidence!r} is not one of "
                f"{valid_confidence}"
            )


# ---------------------------------------------------------------------------
# 6. Fallback: clustering failure yields 1:1 source-to-finding mapping
# ---------------------------------------------------------------------------


class TestClusteringFallback:
    """When _cluster_findings raises an exception, the fallback must still produce
    a non-empty findings list via 1:1 source-to-finding mapping."""

    def test_fallback_when_clustering_raises(self, monkeypatch):
        """If _cluster_findings raises an exception, state.findings must still be
        populated via the fallback 1:1 mapping, not left empty.

        The fallback (_fallback_findings) maps each source to exactly one Finding
        with confidence='low'.  After SEP-077, the dispatch block must call
        _cluster_findings; if that raises, it must catch the exception and
        fall back rather than leaving findings empty.
        """
        svc = _import_service()
        sources = _make_three_sources()

        def raise_on_cluster(query, srcs):
            raise RuntimeError("Clustering model unavailable")

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", raise_on_cluster)
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, (
            "state.findings is empty after a clustering failure — "
            "SEP-077 requires a fallback that produces 1:1 source-to-finding mappings "
            "when _cluster_findings raises an exception"
        )

    def test_fallback_findings_have_low_confidence(self, monkeypatch):
        """Fallback findings (produced when clustering fails) must have confidence='low'.

        This matches the behavior of _fallback_findings which sets each Finding
        to confidence='low' because only one source supports each claim.
        """
        svc = _import_service()
        sources = _make_three_sources()

        def raise_on_cluster(query, srcs):
            raise RuntimeError("Clustering model unavailable")

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        monkeypatch.setattr(svc, "_cluster_findings", raise_on_cluster)
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, "state.findings empty after fallback"
        for i, finding in enumerate(state.findings):
            assert finding.confidence == "low", (
                f"Fallback finding[{i}].confidence={finding.confidence!r}, expected 'low' — "
                "fallback findings are 1:1 source mappings with a single supporting source "
                "which corresponds to low confidence"
            )

    def test_fallback_when_clustering_returns_empty_list(self, monkeypatch):
        """If _cluster_findings returns [], the dispatch block must apply the fallback.

        An empty list from clustering is treated the same as a failure — the pipeline
        must not propagate an empty findings list when sources exist.
        """
        svc = _import_service()
        sources = _make_three_sources()

        monkeypatch.setattr(svc, "aggregate_sources", lambda *a, **kw: sources)
        monkeypatch.setattr(svc, "score_relevance", lambda q, s, extra_keywords=None: s)
        monkeypatch.setattr(svc, "filter_relevant", lambda s, min_score=0.15, max_sources=25: s[:max_sources])
        monkeypatch.setattr(svc, "score_source_credibility", lambda **kw: {"score": 0.8, "category": "High"})
        # Simulate clustering returning an empty list (parsing produced nothing).
        monkeypatch.setattr(svc, "_cluster_findings", lambda q, s: [])
        monkeypatch.setattr(svc, "synthesize", lambda state, **kw: "## Summary\nResult.")
        monkeypatch.setattr(svc, "_build_market_context_for_query", lambda q: ("", {}))

        state = svc.run_deep_research("solar capacity in southern Africa", depth=1)

        assert len(state.findings) > 0, (
            "state.findings is empty after _cluster_findings returned [] — "
            "SEP-077 requires a fallback to 1:1 mapping when clustering yields no findings"
        )


# ---------------------------------------------------------------------------
# 7. Structural / source-code checks
# ---------------------------------------------------------------------------


class TestDispatchBlockStructure:
    """Structural tests that inspect the source code of run_deep_research to verify
    the dispatch block is wired correctly after SEP-077."""

    def test_skipping_message_removed_from_non_diligence_path(self):
        """The 'Skipping finding clustering' message must not appear in the source.

        This checks that the old static skip message has been replaced.
        """
        import inspect
        svc = _import_service()
        source = inspect.getsource(svc)

        assert "Skipping finding clustering" not in source, (
            "'Skipping finding clustering' string is still present in "
            "deep_research_service.py — SEP-077 must replace this message with one "
            "that reflects the active clustering step"
        )

    def test_cluster_findings_called_in_dispatch_block(self):
        """The dispatch block (run_deep_research) must reference _cluster_findings.

        A simple source-level check: the function body must contain a call to
        _cluster_findings somewhere outside of the definition line.
        """
        import inspect
        svc = _import_service()
        fn = svc.run_deep_research
        source = inspect.getsource(fn)

        # The call site looks like: _cluster_findings(... or state.findings = _cluster_findings(
        # We just need to confirm _cluster_findings is invoked, not just defined.
        assert source.count("_cluster_findings") >= 1, (
            "_cluster_findings is not called inside run_deep_research — "
            "SEP-077 requires the dispatch block to call _cluster_findings "
            "for non-diligence queries"
        )
