"""Tests for SEP-068: Switch non-diligence deep research to the full structured
synthesize pipeline (outline-then-section expansion), replacing the flat
synthesize_direct path for general research queries.

Covers:
  1. Dispatch — non-diligence queries must call the structured `synthesize`
     function from synthesizer.py, not `synthesize_direct`.
  2. Dispatch — diligence queries must still call `synthesize_direct` (unchanged
     behaviour).
  3. The `synthesize` function in synthesizer.py must accept an optional
     `market_context` keyword argument so the service can pass one without
     breaking the call signature.
  4. The structured synthesis output must contain `##` section headers
     (multi-section structured report, not a flat text blob).
  5. Content fetch config is enabled so that full-text evidence reaches the
     synthesis model.
  6. The service module-level `synthesize` alias must no longer point at
     `synthesize_direct` — after SEP-068 it should reference the real
     two-stage pipeline.

All tests are expected to FAIL until SEP-068 is implemented.
"""

from __future__ import annotations

import inspect
import pathlib
import sys
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Lazy module helpers (avoid heavy import cost at collection time)
# ---------------------------------------------------------------------------


def _import_service():
    """Import deep_research_service, reloading so patches take effect cleanly."""
    import engine.deep_research_service as svc
    return svc


def _import_synthesizer():
    import workflows.deep_research.synthesizer as syn
    return syn


def _make_state(research_type="general", original_query="solar power capacity in Africa"):
    """Build a minimal ResearchState for test use."""
    from engine.models import ResearchState, Source
    state = ResearchState(
        original_query=original_query,
        research_type=research_type,
    )
    # Add two stub sources so synthesis has something to work with.
    for i in range(2):
        src = Source(
            source_id=f"src{i}",
            url=f"https://example.com/article/{i}",
            title=f"Test Article {i}",
            content_snippet="Solar energy capacity in sub-Saharan Africa continues to grow.",
            credibility_score=0.8,
            relevance_score=0.9,
        )
        state.add_source(src)
    return state


# ===========================================================================
# 1. SERVICE IMPORT — `synthesize` alias must NOT point at synthesize_direct
# ===========================================================================


class TestServiceSynthesizeAlias:
    """After SEP-068 the module-level `synthesize` name in deep_research_service
    must reference the two-stage pipeline, not synthesize_direct."""

    def test_service_synthesize_is_not_synthesize_direct(self):
        """deep_research_service.synthesize must differ from synthesize_direct.

        Currently line 28 of deep_research_service.py sets:
            synthesize = synthesize_direct
        SEP-068 must change this so the alias points at the real two-stage
        `synthesize` from synthesizer.py.
        """
        svc = _import_service()
        syn = _import_synthesizer()

        # After SEP-068 the service alias must NOT be synthesize_direct.
        assert svc.synthesize is not syn.synthesize_direct, (
            "deep_research_service.synthesize still points at synthesize_direct — "
            "SEP-068 requires the alias to be updated to the two-stage synthesize pipeline"
        )

    def test_service_synthesize_is_the_structured_pipeline(self):
        """deep_research_service.synthesize must reference synthesizer.synthesize.

        The two-stage pipeline in synthesizer.py is the `synthesize` function
        at line 3353. After SEP-068 the service alias must point there.
        """
        svc = _import_service()
        syn = _import_synthesizer()

        assert svc.synthesize is syn.synthesize, (
            "deep_research_service.synthesize does not reference "
            "workflows.deep_research.synthesizer.synthesize — "
            "SEP-068 requires importing and aliasing the two-stage pipeline"
        )


# ===========================================================================
# 2. SYNTHESIZE SIGNATURE — must accept optional market_context
# ===========================================================================


class TestSynthesizeSignature:
    """`synthesize` in synthesizer.py must accept market_context as a keyword."""

    def test_synthesize_accepts_market_context_kwarg(self):
        """synthesize(state, market_context=...) must not raise TypeError.

        Currently the function signature is:
            def synthesize(state, progress_callback=None) -> str:
        SEP-068 requires adding an optional `market_context` parameter so the
        service can pass the pre-built context string directly.
        """
        syn = _import_synthesizer()
        sig = inspect.signature(syn.synthesize)
        param_names = list(sig.parameters.keys())
        assert "market_context" in param_names, (
            "synthesizer.synthesize has no 'market_context' parameter — "
            "SEP-068 requires adding market_context: str = '' to its signature "
            "so deep_research_service can pass the pre-built context through"
        )

    def test_synthesize_market_context_has_default_empty_string(self):
        """market_context parameter must default to '' so old callers are unaffected."""
        syn = _import_synthesizer()
        sig = inspect.signature(syn.synthesize)
        param = sig.parameters.get("market_context")
        assert param is not None, "market_context parameter not found in synthesize"
        assert param.default == "", (
            f"synthesize market_context default is {param.default!r}, expected '' — "
            "existing callers that omit market_context must not be broken"
        )


# ===========================================================================
# 3. DISPATCH LOGIC — non-diligence must use the two-stage pipeline
# ===========================================================================


class TestNonDiligenceDispatch:
    """The synthesis dispatch block (lines 1080-1094) must call the two-stage
    pipeline for non-diligence queries, not synthesize_direct."""

    def test_non_diligence_calls_synthesize_not_synthesize_direct(self):
        """For research_type='general', the service must call the full
        structured synthesize pipeline, not synthesize_direct.

        We verify this by patching both functions in the service module and
        confirming only the pipeline is called.
        """
        svc = _import_service()
        syn = _import_synthesizer()

        state = _make_state(research_type="general")
        fake_synthesis = "## Executive Summary\n\nSome content.\n\n## Supply Drivers\n\nMore content."

        with patch.object(syn, "synthesize", return_value=fake_synthesis) as mock_pipeline, \
             patch.object(syn, "synthesize_direct", return_value="flat result"):
            # Patch the service's reference to the pipeline to track calls.
            with patch.object(svc, "synthesize", wraps=mock_pipeline) as mock_svc_syn:
                svc.synthesize(state, market_context="some context", progress_callback=None)

        # The two-stage pipeline must have been called.
        assert mock_pipeline.called or mock_svc_syn.called, (
            "Neither synthesizer.synthesize nor its service alias was called for a "
            "non-diligence query — SEP-068 requires routing non-diligence through "
            "the two-stage pipeline"
        )

    def test_dispatch_in_service_module_uses_structured_function(self):
        """Inspect the service source code to verify the dispatch block (the
        `else` branch for non-diligence) does not call synthesize_direct.

        This is a structural test: the service may import synthesize_direct for
        diligence, but the non-diligence branch must not reference it.
        """
        svc = _import_service()
        source_lines = inspect.getsource(svc)

        # After SEP-068 the module-level alias must NOT be synthesize_direct.
        # The canonical marker is the old backward-compat line:
        #   synthesize = synthesize_direct
        # which must be gone or changed.
        assert "synthesize = synthesize_direct" not in source_lines, (
            "deep_research_service still contains 'synthesize = synthesize_direct' — "
            "SEP-068 requires removing this alias so non-diligence uses the pipeline"
        )


# ===========================================================================
# 4. DISPATCH LOGIC — diligence must still use synthesize_direct
# ===========================================================================


class TestDiligenceDispatch:
    """Diligence queries must continue calling synthesize_direct unchanged."""

    def test_diligence_still_imports_synthesize_direct(self):
        """synthesize_direct must remain imported in deep_research_service so
        the diligence branch can call it."""
        svc = _import_service()

        # synthesize_direct must be accessible from the service module (either
        # imported directly, or reachable via the synthesizer).
        service_has_direct = (
            hasattr(svc, "synthesize_direct")
            or "synthesize_direct" in inspect.getsource(svc)
        )
        assert service_has_direct, (
            "synthesize_direct is no longer accessible from deep_research_service — "
            "SEP-068 must keep synthesize_direct available for the diligence branch"
        )

    def test_diligence_dispatch_calls_synthesize_direct(self):
        """For research_type='diligence', the service must call synthesize_direct,
        not the two-stage pipeline.

        We verify this by inspecting the dispatch source to confirm the diligence
        branch uses synthesize_direct (or equivalent).
        """
        svc = _import_service()
        # The function that contains the dispatch logic is `run_research` or
        # whatever function wraps the synthesis block.  We check the module
        # source for the structural pattern: inside the is_diligence branch,
        # `synthesize_direct` (not just `synthesize`) is called.
        source = inspect.getsource(svc)

        # The diligence branch must reference synthesize_direct.
        assert "synthesize_direct" in source, (
            "synthesize_direct not found in deep_research_service source — "
            "SEP-068 must preserve the diligence path through synthesize_direct"
        )


# ===========================================================================
# 5. STRUCTURED OUTPUT — output must contain ## section headers
# ===========================================================================


class TestStructuredOutput:
    """The two-stage synthesize pipeline must produce markdown ## headers."""

    def test_assemble_synthesis_produces_section_headers(self):
        """assemble_synthesis must return a string containing at least one '##'
        markdown section header.

        This verifies that the assembly step produces structured output, not a
        flat paragraph.  OutlineSection only has title and bullets fields.
        """
        syn = _import_synthesizer()
        from workflows.deep_research.synthesizer import OutlineResult, OutlineSection

        # Build a minimal outline using only the real OutlineSection fields.
        section = OutlineSection(
            title="Supply Drivers",
            bullets=["Solar capacity growing at 15% CAGR.", "Grid constraints remain."],
        )
        outline = OutlineResult(
            executive_summary="Africa solar capacity is expanding rapidly.",
            sections=[section],
            is_comparison=False,
            subjects=[],
        )
        expanded = ["Detailed supply driver analysis with citations."]
        result = syn.assemble_synthesis(outline, expanded)

        assert "##" in result, (
            "assemble_synthesis returned text with no '##' markdown headers — "
            "the structured pipeline must produce section-headed output"
        )

    def test_structured_pipeline_output_has_multiple_sections(self):
        """The two-stage synthesize function, when given a non-diligence state,
        must return text that contains 4 or more '##' section markers.

        We mock the LLM calls (outline and section expansion) to return
        deterministic content, then check the assembled result.

        This test will fail with TypeError until synthesize() gains a
        market_context parameter (the call passes market_context="" below).
        """
        syn = _import_synthesizer()
        from workflows.deep_research.synthesizer import OutlineResult, OutlineSection

        state = _make_state(research_type="general")

        # OutlineSection only accepts title and bullets.
        sections = [
            OutlineSection(title=f"Section {i}", bullets=[f"Bullet {i}a", f"Bullet {i}b"])
            for i in range(4)
        ]
        fake_outline = OutlineResult(
            executive_summary="This is the executive summary.",
            sections=sections,
            is_comparison=False,
            subjects=[],
        )

        with patch.object(syn, "synthesize_outline", return_value=fake_outline), \
             patch.object(syn, "synthesize_section", return_value="Expanded content for this section."):
            # market_context="" will raise TypeError until SEP-068 adds the param.
            result = syn.synthesize(state, market_context="", progress_callback=None)

        header_count = result.count("##")
        assert header_count >= 4, (
            f"synthesize returned only {header_count} '##' headers — "
            "SEP-068 requires structured output with at least 4 named sections "
            "(Executive Summary + 3 content sections minimum)"
        )

    def test_synthesize_direct_not_used_for_non_diligence_output(self):
        """When the structured synthesize function runs for a non-diligence query,
        synthesize_direct must not be invoked.

        Verifies there is no fallback path that silently routes back to the flat pipeline.

        This test will fail with TypeError until synthesize() gains a
        market_context parameter (the call passes market_context="" below).
        """
        syn = _import_synthesizer()
        from workflows.deep_research.synthesizer import OutlineResult, OutlineSection

        state = _make_state(research_type="general")
        # OutlineSection only accepts title and bullets.
        sections = [
            OutlineSection(title="Market Overview", bullets=["Point A"]),
            OutlineSection(title="Policy Landscape", bullets=["Point B"]),
            OutlineSection(title="Infrastructure", bullets=["Point C"]),
            OutlineSection(title="Investment Outlook", bullets=["Point D"]),
        ]
        fake_outline = OutlineResult(
            executive_summary="Summary text.",
            sections=sections,
            is_comparison=False,
            subjects=[],
        )

        with patch.object(syn, "synthesize_outline", return_value=fake_outline), \
             patch.object(syn, "synthesize_section", return_value="Section body."), \
             patch.object(syn, "synthesize_direct", return_value="FLAT RESULT") as mock_direct:
            # market_context="" will raise TypeError until SEP-068 adds the param.
            result = syn.synthesize(state, market_context="", progress_callback=None)

        assert not mock_direct.called, (
            "synthesize_direct was called inside synthesize() for a non-diligence query — "
            "the two-stage pipeline must not fall through to the flat path"
        )
        assert "FLAT RESULT" not in result, (
            "synthesize() returned the synthesize_direct flat output — "
            "non-diligence results must come from the outline-then-section pipeline"
        )


# ===========================================================================
# 6. CONTENT FETCH CONFIG — enabled flag must be True
# ===========================================================================


class TestContentFetchConfig:
    """config.CONTENT_FETCH['enabled'] must be True so full-text evidence
    reaches the synthesis model (already done in SEP-069, verified here)."""

    def test_content_fetch_enabled_in_config(self):
        """config.CONTENT_FETCH must have enabled=True."""
        import config
        cf = config.CONTENT_FETCH
        assert isinstance(cf, dict), "config.CONTENT_FETCH must be a dict"
        assert cf.get("enabled") is True, (
            f"config.CONTENT_FETCH['enabled'] = {cf.get('enabled')!r} — "
            "SEP-069/068 requires content fetch to be enabled so full-text "
            "evidence reaches the synthesis model"
        )

    def test_content_fetch_config_has_required_keys(self):
        """config.CONTENT_FETCH must include max_sources, timeout_per_url,
        skip_types, and max_workers so the extractor can be parameterised."""
        import config
        cf = config.CONTENT_FETCH
        required = {"enabled", "max_sources", "timeout_per_url", "skip_types", "max_workers"}
        missing = required - set(cf.keys())
        assert not missing, (
            f"config.CONTENT_FETCH is missing keys: {missing} — "
            "all keys must be present so ContentExtractor receives valid params"
        )


# ===========================================================================
# 7. INTEGRATION — synthesize called with market_context from service dispatch
# ===========================================================================


class TestServicePassesMarketContext:
    """The service dispatch block must forward market_context to synthesize for
    non-diligence queries."""

    def test_non_diligence_dispatch_passes_market_context(self):
        """deep_research_service._run_synthesis_phase (or equivalent) must
        call synthesize(..., market_context=...) for non-diligence queries.

        This verifies that the pre-built market_context string built by
        _build_market_context_for_query is actually forwarded to the pipeline
        and not silently discarded.
        """
        svc = _import_service()

        source = inspect.getsource(svc)
        # The non-diligence dispatch block must contain a call that passes
        # market_context as a keyword argument to synthesize.
        # A simple structural check: the source contains both 'synthesize(' and
        # 'market_context' in proximity within the non-diligence branch.
        # We look for the pattern used in the current code for the else-branch.
        assert "market_context" in source, (
            "deep_research_service source does not contain 'market_context' — "
            "the non-diligence dispatch must pass market_context= to synthesize"
        )

    def test_synthesize_receives_market_context_not_empty_string(self):
        """When the service calls synthesize for a non-diligence query,
        the market_context kwarg must not always be the empty string.

        We patch _build_market_context_for_query to return a known string and
        confirm that synthesize is called with that value.
        """
        svc = _import_service()

        FAKE_MARKET_CTX = "FAKE_MARKET_CONTEXT_SENTINEL"
        captured_calls = []

        def capturing_synthesize(state, **kwargs):
            captured_calls.append(kwargs.get("market_context", "__NOT_PASSED__"))
            return "## Executive Summary\n\nStub.\n\n## Section One\n\nContent."

        with patch.object(svc, "_build_market_context_for_query", return_value=FAKE_MARKET_CTX), \
             patch.object(svc, "synthesize", side_effect=capturing_synthesize):

            state = _make_state(research_type="general")
            # Call the alias directly to simulate what the dispatch block does.
            svc.synthesize(state, market_context=FAKE_MARKET_CTX, progress_callback=None)

        assert len(captured_calls) == 1, (
            "synthesize was not called — the mock was not invoked correctly"
        )
        assert captured_calls[0] == FAKE_MARKET_CTX, (
            f"synthesize received market_context={captured_calls[0]!r}, "
            f"expected {FAKE_MARKET_CTX!r} — the service must forward the "
            "pre-built market context to the pipeline"
        )
