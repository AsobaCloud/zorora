"""Tests for SEP-035: direct question-answering in deep research synthesis."""

from __future__ import annotations

from typing import List

import pytest

from engine.models import ResearchState, Source


def _make_source(
    title: str,
    *,
    snippet: str,
    url: str,
    full: str = "",
    credibility: float = 0.7,
    relevance: float = 0.6,
    source_type: str = "web",
) -> Source:
    source = Source(
        source_id=Source.generate_id(url),
        url=url,
        title=title,
        source_type=source_type,
        credibility_score=credibility,
        relevance_score=relevance,
        content_snippet=snippet,
        content_full=full,
    )
    return source


def _make_state(sources: List[Source]) -> ResearchState:
    state = ResearchState(
        original_query="How did LNG shipping delays affect EU power prices in late 2025?",
        refined_query="LNG shipping delays EU power prices late 2025",
        research_type="trend_analysis",
    )
    state.sources_checked = list(sources)
    state.total_sources = len(sources)
    return state


def test_synthesize_direct_prompt_includes_question_all_sources_and_background_instruction(monkeypatch):
    from workflows.deep_research import synthesizer as mod

    sources = [
        _make_source(
            "Grid Operations Update",
            snippet="LNG shipping delays tightened gas balances and lifted day-ahead power prices in EU hubs.",
            url="https://example.com/grid",
        ),
        _make_source(
            "Regulatory Gazette",
            snippet="Emergency interventions capped some of the sharpest intraday spikes.",
            url="https://example.com/reg",
        ),
        _make_source(
            "Utility Earnings Call",
            snippet="Utilities described continued fuel-cost pass-through into retail tariffs.",
            url="https://example.com/utility",
        ),
    ]
    state = _make_state(sources)

    seen = {}

    def fake_call(prompt: str, system_prompt: str | None = None) -> str:
        seen["prompt"] = prompt
        seen["system_prompt"] = system_prompt
        return (
            "## Executive Summary\n"
            "LNG shipping delays raised EU power prices by tightening gas balances [Grid Operations Update].\n\n"
            "## Direct Answer\n"
            "Emergency caps reduced some spikes but did not remove pass-through [Regulatory Gazette].\n\n"
            "## Policy Spillovers\n"
            "Utilities still described fuel-cost pass-through into tariffs [Utility Earnings Call]."
        )

    monkeypatch.setattr(mod, "_call_research_synthesis_model", fake_call)

    synthesis = mod.synthesize_direct(state, market_context="TTF gas remained elevated.")

    assert "## Executive Summary" in synthesis
    prompt = seen["prompt"]
    assert "RESEARCH QUESTION" in prompt
    assert state.original_query in prompt
    assert "Answer the research question directly" in prompt
    assert "[Background Knowledge]" in prompt
    assert "TTF gas remained elevated." in prompt
    for source in sources:
        assert source.title in prompt
        assert source.url in prompt
    assert seen["system_prompt"] is not None
    assert "Background Knowledge" in seen["system_prompt"]


def test_synthesize_direct_returns_model_output_and_sets_provenance(monkeypatch):
    from workflows.deep_research import synthesizer as mod

    source = _make_source(
        "Grid Operations Update",
        snippet="LNG shipping delays tightened gas balances and lifted day-ahead power prices in EU hubs.",
        url="https://example.com/grid",
    )
    state = _make_state([source])

    model_output = (
        "## Executive Summary\n"
        "LNG shipping delays pushed EU hub power prices higher [Grid Operations Update].\n\n"
        "## Direct Answer\n"
        "Gas-linked dispatch costs rose because shipping delays tightened supply [Grid Operations Update].\n\n"
        "## Price Impact\n"
        "Power prices remained elevated as fuel procurement tightened [Grid Operations Update]."
    )
    monkeypatch.setattr(mod, "_call_research_synthesis_model", lambda prompt, system_prompt=None: model_output)

    synthesis = mod.synthesize_direct(state)

    assert synthesis == model_output
    assert state.synthesis == model_output
    assert state.synthesis_model == "direct"


def test_synthesize_direct_falls_back_to_deterministic_when_model_returns_none(monkeypatch):
    from workflows.deep_research import synthesizer as mod

    source = _make_source(
        "Grid Operations Update",
        snippet="LNG shipping delays tightened gas balances and lifted day-ahead power prices in EU hubs.",
        url="https://example.com/grid",
    )
    state = _make_state([source])

    monkeypatch.setattr(mod, "_call_research_synthesis_model", lambda prompt, system_prompt=None: None)

    synthesis = mod.synthesize_direct(state)

    assert "## Executive Summary" in synthesis
    assert state.synthesis_model == "deterministic"
    assert "[Grid Operations Update]" in synthesis


def test_deterministic_direct_fallback_adds_background_definition_when_sources_do_not_define(monkeypatch):
    from workflows.deep_research import synthesizer as mod

    sources = [
        _make_source(
            "Energy Security Brief",
            snippet="After Russia reduced pipeline gas flows, Europe increased seaborne LNG imports to replace lost volumes and diversify supply away from a single pipeline corridor.",
            url="https://example.com/eu1",
        ),
        _make_source(
            "Power Market Note",
            snippet="European buyers turned to LNG cargoes because they could be redirected globally, helping offset pipeline shortages even though prices were volatile.",
            url="https://example.com/eu2",
        ),
    ]
    state = ResearchState(
        original_query="What is LNG, and why did Europe rely on it more after Russia cut pipeline gas? If the sources do not define LNG, explain it in plain language.",
        refined_query="Europe LNG reliance after Russian pipeline cuts",
        research_type="trend_analysis",
    )
    state.sources_checked = list(sources)
    state.total_sources = len(sources)

    monkeypatch.setattr(mod, "_call_research_synthesis_model", lambda prompt, system_prompt=None: None)

    synthesis = mod.synthesize_direct(state)

    assert state.synthesis_model == "deterministic"
    assert "[Background Knowledge]" in synthesis
    assert "liquefied natural gas" in mod._extract_markdown_section(synthesis, "Direct Answer").lower()


def test_synthesize_direct_repairs_near_miss_model_output_and_keeps_direct_path(monkeypatch):
    from workflows.deep_research import synthesizer as mod

    sources = [
        _make_source(
            "Energy Security Brief",
            snippet="After Russia reduced pipeline gas flows, Europe increased seaborne LNG imports to replace lost volumes and diversify supply away from a single pipeline corridor.",
            url="https://example.com/eu1",
        ),
        _make_source(
            "Power Market Note",
            snippet="European buyers turned to LNG cargoes because they could be redirected globally, helping offset pipeline shortages even though prices were volatile.",
            url="https://example.com/eu2",
        ),
    ]
    state = ResearchState(
        original_query="What is LNG, and why did Europe rely on it more after Russia cut pipeline gas? If the sources do not define LNG, explain it in plain language.",
        refined_query="Europe LNG reliance after Russian pipeline cuts",
        research_type="trend_analysis",
    )
    state.sources_checked = list(sources)
    state.total_sources = len(sources)

    raw_output = (
        "#### Executive Summary\n"
        "Liquefied natural gas (LNG) is a form of natural gas that has been cooled to liquid state, allowing it to be transported via ship. "
        "This was crucial for Europe after Russia cut pipeline gas flows, as LNG imports helped mitigate supply disruptions.\n\n"
        "#### Direct Answer\n"
        "After Russia reduced pipeline gas flows, Europe increased seaborne LNG imports to replace lost volumes and diversify supply away from a single pipeline corridor. "
        "This shift improved supply flexibility but exposed Europe to global competition for cargoes.\n\n"
        "#### Thematic Section: Understanding LNG\n"
        "The documents do not specifically define LNG, so we must understand its basic properties and how it is produced. "
        "LNG is primarily composed of methane, which makes up about 90% of its content.\n\n"
        "#### Thematic Section: LNG Imports and Supply Diversification\n"
        "Europe's reliance on LNG imports increased significantly after Russia cut pipeline gas flows. "
        "The documents suggest that Europe's LNG imports rose to address the supply gap left by the reduction in pipeline gas.\n\n"
        "#### Sources:\n"
        "1. Energy Security Brief\n\n"
        "#### Caveats:\n"
        "Further research may reveal additional insights."
    )
    monkeypatch.setattr(mod, "_call_research_synthesis_model", lambda prompt, system_prompt=None: raw_output)

    synthesis = mod.synthesize_direct(state)

    assert state.synthesis_model == "direct"
    assert "## Direct Answer" in synthesis
    assert "## Sources" not in synthesis
    assert "## Caveats" not in synthesis
    assert "[Background Knowledge]" in synthesis
    assert "[Energy Security Brief]" in synthesis or "[Power Market Note]" in synthesis
    direct_answer = mod._extract_markdown_section(synthesis, "Direct Answer").lower()
    assert "[background knowledge]" in direct_answer
    assert "liquefied natural gas" in direct_answer


def test_run_deep_research_uses_direct_synthesis_and_skips_clustering(monkeypatch):
    from engine import deep_research_service as svc

    source = _make_source(
        "Grid Operations Update",
        snippet="LNG shipping delays tightened gas balances and lifted day-ahead power prices in EU hubs.",
        url="https://example.com/grid",
    )

    monkeypatch.setattr(svc, "aggregate_sources", lambda *args, **kwargs: [source])
    monkeypatch.setattr(svc, "score_relevance", lambda query, sources, extra_keywords=None: sources)
    monkeypatch.setattr(svc, "filter_relevant", lambda sources, min_score=0.15, max_sources=25: sources[:max_sources])
    monkeypatch.setattr(svc, "score_source_credibility", lambda **kwargs: {"score": 0.88, "category": "High"})

    cluster_calls = {"count": 0}

    def fake_cluster_findings(query, sources):
        cluster_calls["count"] += 1
        from engine.models import Finding
        return [Finding(claim="Test finding", sources=["s1"], confidence="medium", average_credibility=0.75)]

    monkeypatch.setattr(svc, "_cluster_findings", fake_cluster_findings)

    direct_calls = {}

    def fake_synthesize_direct(state, market_context="", progress_callback=None, **kwargs):
        direct_calls["market_context"] = market_context
        direct_calls["findings"] = list(state.findings)
        state.synthesis = "## Executive Summary\nDirect answer [Grid Operations Update]."
        state.synthesis_model = "direct"
        return state.synthesis

    monkeypatch.setattr(svc, "synthesize", fake_synthesize_direct)

    state = svc.run_deep_research("test query", depth=1)

    assert cluster_calls["count"] >= 1, "clustering must be called for non-diligence queries"
    assert len(direct_calls["findings"]) >= 1, "findings must be populated after clustering"
    assert state.synthesis_model == "direct"
    assert state.synthesis.startswith("## Executive Summary")


def _skip_if_reasoning_endpoint_unavailable(exc: Exception) -> None:
    message = str(exc).lower()
    if any(token in message for token in ("timed out", "timeout", "connection", "503", "service_unavailable")):
        pytest.skip(f"Reasoning endpoint unavailable: {exc}")
    raise exc


@pytest.mark.integration
def test_synthesize_direct_live_reasoning_endpoint():
    from workflows.deep_research.synthesizer import synthesize_direct

    sources = [
        _make_source(
            "Grid Operations Update",
            snippet="LNG shipping delays tightened gas balances and lifted day-ahead power prices in EU hubs.",
            url="https://example.com/grid",
            credibility=0.88,
            relevance=0.84,
        ),
        _make_source(
            "Regulatory Gazette",
            snippet="Emergency caps reduced some intraday spikes but did not eliminate fuel-cost pass-through.",
            url="https://example.com/reg",
            credibility=0.82,
            relevance=0.79,
        ),
    ]
    state = _make_state(sources)

    try:
        synthesis = synthesize_direct(state)
    except Exception as exc:  # pragma: no cover - network-dependent
        _skip_if_reasoning_endpoint_unavailable(exc)
        raise

    assert "## Executive Summary" in synthesis
    assert "[Grid Operations Update]" in synthesis or "[Regulatory Gazette]" in synthesis
    assert "LNG" in synthesis or "shipping" in synthesis.lower()
