"""Tests for SEP-073: Matplotlib charts from structured market data embedded
in deep research synthesis output as base64 PNG images.

Covers:
  1. generate_research_charts() exists in synthesizer and is callable.
  2. Signature accepts (query: str, market_summaries: dict) and returns a list.
  3. Each returned item is a 3-tuple of (section_hint, chart_title, data_uri).
  4. Returns empty list when market_summaries is empty or no query match.
  5. Returns non-empty list when query matches a known series group and
     summaries carry data for that group.
  6. data_uri values begin with "data:image/png;base64,".
  7. At most 4 charts are generated per query.
  8. _build_market_context_for_query returns a 2-tuple (str, dict), not a str.
  9. synthesize() accepts an optional market_summaries keyword parameter.

All tests are expected to FAIL until SEP-073 is implemented.
"""

from __future__ import annotations

import importlib.util
import inspect
import pathlib
import sys
from typing import Any

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Lazy module loaders — graceful skip when heavy deps are unavailable
# ---------------------------------------------------------------------------

_SYNTHESIZER_PATH = PROJECT_ROOT / "workflows" / "deep_research" / "synthesizer.py"
_SERVICE_PATH = PROJECT_ROOT / "engine" / "deep_research_service.py"

_synthesizer_module: Any = None
_service_module: Any = None
_synthesizer_import_error: Exception | None = None
_service_import_error: Exception | None = None


def _load_synthesizer():
    global _synthesizer_module, _synthesizer_import_error
    if _synthesizer_module is not None:
        return _synthesizer_module
    try:
        spec = importlib.util.spec_from_file_location(
            "synthesizer_sep073", _SYNTHESIZER_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["synthesizer_sep073"] = mod
        spec.loader.exec_module(mod)
        _synthesizer_module = mod
    except Exception as exc:
        _synthesizer_import_error = exc
    return _synthesizer_module


def _load_service():
    global _service_module, _service_import_error
    if _service_module is not None:
        return _service_module
    try:
        spec = importlib.util.spec_from_file_location(
            "deep_research_service_sep073", _SERVICE_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["deep_research_service_sep073"] = mod
        spec.loader.exec_module(mod)
        _service_module = mod
    except Exception as exc:
        _service_import_error = exc
    return _service_module


def _skip_if_no_synthesizer():
    if _load_synthesizer() is None:
        pytest.skip(f"synthesizer module unavailable: {_synthesizer_import_error}")


def _skip_if_no_service():
    if _load_service() is None:
        pytest.skip(f"deep_research_service module unavailable: {_service_import_error}")


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

# A minimal market_summaries dict that reflects what MarketWorkflow.compute_summary()
# returns.  Keys are series_id strings; values are summary dicts with at least a
# "last" numeric value.  We include examples from each major group so tests can
# match query terms against known groups.

_COMMODITIES_SUMMARIES = {
    "DCOILWTICO": {"last": 72.5, "label": "WTI Crude Oil", "group": "commodities"},
    "DCOILBRENTEU": {"last": 76.1, "label": "Brent Crude Oil", "group": "commodities"},
    "DHHNGSP": {"last": 2.3, "label": "Natural Gas (Henry Hub)", "group": "commodities"},
}

_SAPP_SUMMARIES = {
    "sapp_dam_rsan_usd": {"last": 51.0, "label": "SAPP DAM RSA-North (USD)", "group": "sapp_prices"},
    "sapp_dam_rsas_usd": {"last": 51.0, "label": "SAPP DAM RSA-South (USD)", "group": "sapp_prices"},
    "sapp_dam_zim_usd": {"last": 48.5, "label": "SAPP DAM Zimbabwe (USD)", "group": "sapp_prices"},
}

_ESKOM_RE_SUMMARIES = {
    "eskom_re_wind": {"last": 1820.0, "label": "Eskom Wind Generation", "group": "eskom_re_generation"},
    "eskom_re_pv": {"last": 930.0, "label": "Eskom PV Generation", "group": "eskom_re_generation"},
}

_WB_ELECTRICITY_SUMMARIES = {
    "wb_zaf_elc_renew": {"last": 7.4, "label": "SA Renewable Electricity", "group": "sadc_electricity"},
    "wb_zaf_elc_coal": {"last": 87.2, "label": "SA Electricity from Coal", "group": "sadc_electricity"},
}

_FULL_SUMMARIES = {
    **_COMMODITIES_SUMMARIES,
    **_SAPP_SUMMARIES,
    **_ESKOM_RE_SUMMARIES,
    **_WB_ELECTRICITY_SUMMARIES,
}


# ===========================================================================
# 1. Function existence
# ===========================================================================


class TestGenerateResearchChartsExists:
    """generate_research_charts must be importable from the synthesizer module."""

    def test_function_exists_in_synthesizer_module(self):
        """generate_research_charts must be a top-level name in synthesizer.py."""
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        assert hasattr(mod, "generate_research_charts"), (
            "synthesizer.py does not expose generate_research_charts — "
            "SEP-073 requires this function to be defined"
        )

    def test_function_is_callable(self):
        """generate_research_charts must be callable (not a constant or class)."""
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        assert callable(fn), (
            "generate_research_charts exists but is not callable"
        )


# ===========================================================================
# 2. Signature
# ===========================================================================


class TestGenerateResearchChartsSignature:
    """generate_research_charts(query, market_summaries) signature contract."""

    def _get_fn(self):
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        return fn

    def test_accepts_query_and_market_summaries_positional(self):
        """Function must accept (query: str, market_summaries: dict) positionally."""
        fn = self._get_fn()
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert "query" in params, (
            f"generate_research_charts must have a 'query' parameter; got {params}"
        )
        assert "market_summaries" in params, (
            f"generate_research_charts must have a 'market_summaries' parameter; got {params}"
        )

    def test_query_is_first_parameter(self):
        """'query' must be the first positional parameter."""
        fn = self._get_fn()
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert params[0] == "query", (
            f"First parameter of generate_research_charts must be 'query'; got '{params[0]}'"
        )

    def test_market_summaries_is_second_parameter(self):
        """'market_summaries' must be the second positional parameter."""
        fn = self._get_fn()
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert params[1] == "market_summaries", (
            f"Second parameter of generate_research_charts must be 'market_summaries'; "
            f"got '{params[1]}'"
        )

    def test_returns_list(self):
        """Calling with empty summaries must return a list (not raise, not return None)."""
        fn = self._get_fn()
        result = fn("test query", {})
        assert isinstance(result, list), (
            f"generate_research_charts must return a list; got {type(result).__name__}"
        )


# ===========================================================================
# 3. Return type — 3-tuple structure
# ===========================================================================


class TestGenerateResearchChartsReturnStructure:
    """Each item returned must be a (section_hint, chart_title, data_uri) 3-tuple."""

    def _get_charts(self, query: str, summaries: dict) -> list:
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        return fn(query, summaries)

    def test_items_are_tuples_of_length_3(self):
        """When charts are generated, each must be a 3-element tuple/sequence."""
        charts = self._get_charts("crude oil price outlook", _COMMODITIES_SUMMARIES)
        if not charts:
            pytest.skip(
                "No charts returned for commodity query — "
                "cannot validate tuple structure yet"
            )
        for i, item in enumerate(charts):
            assert len(item) == 3, (
                f"Chart {i} must be a 3-tuple (section_hint, chart_title, data_uri); "
                f"got length {len(item)}"
            )

    def test_section_hint_is_string(self):
        """First element of each chart tuple must be a non-empty string (section hint)."""
        charts = self._get_charts("crude oil price outlook", _COMMODITIES_SUMMARIES)
        if not charts:
            pytest.skip("No charts returned — cannot validate section_hint type")
        for i, (section_hint, _title, _uri) in enumerate(charts):
            assert isinstance(section_hint, str), (
                f"Chart {i}: section_hint must be str; got {type(section_hint).__name__}"
            )
            assert section_hint.strip(), (
                f"Chart {i}: section_hint must be non-empty"
            )

    def test_chart_title_is_string(self):
        """Second element of each chart tuple must be a non-empty string (chart title)."""
        charts = self._get_charts("crude oil price outlook", _COMMODITIES_SUMMARIES)
        if not charts:
            pytest.skip("No charts returned — cannot validate chart_title type")
        for i, (_hint, chart_title, _uri) in enumerate(charts):
            assert isinstance(chart_title, str), (
                f"Chart {i}: chart_title must be str; got {type(chart_title).__name__}"
            )
            assert chart_title.strip(), (
                f"Chart {i}: chart_title must be non-empty"
            )

    def test_data_uri_is_string(self):
        """Third element of each chart tuple must be a string (data URI)."""
        charts = self._get_charts("crude oil price outlook", _COMMODITIES_SUMMARIES)
        if not charts:
            pytest.skip("No charts returned — cannot validate data_uri type")
        for i, (_hint, _title, data_uri) in enumerate(charts):
            assert isinstance(data_uri, str), (
                f"Chart {i}: data_uri must be str; got {type(data_uri).__name__}"
            )


# ===========================================================================
# 4. Empty-input behaviour
# ===========================================================================


class TestGenerateResearchChartsEmptyInputs:
    """Function must return empty list for empty or irrelevant inputs."""

    def _fn(self):
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        return fn

    def test_empty_summaries_returns_empty_list(self):
        """Empty market_summaries dict must produce zero charts."""
        result = self._fn()("oil prices", {})
        assert result == [], (
            f"Expected [] for empty summaries; got {result}"
        )

    def test_empty_query_returns_empty_list(self):
        """Empty string query must produce zero charts."""
        result = self._fn()("", _FULL_SUMMARIES)
        assert result == [], (
            f"Expected [] for empty query; got {result}"
        )

    def test_none_summaries_returns_empty_list_or_raises_cleanly(self):
        """Passing None for market_summaries must return [] or raise TypeError (not crash unexpectedly)."""
        fn = self._fn()
        try:
            result = fn("oil prices", None)
            assert result == [], (
                f"Expected [] when summaries=None; got {result}"
            )
        except TypeError:
            pass  # Acceptable — function enforces dict type

    def test_unmatched_query_topic_returns_empty_list(self):
        """A query about an unrelated topic (no series group match) returns empty list."""
        result = self._fn()(
            "medieval European agricultural practices",
            _FULL_SUMMARIES,
        )
        assert result == [], (
            "Expected [] for query with no matching series group; "
            f"got {len(result)} chart(s)"
        )


# ===========================================================================
# 5. Non-empty output for matching queries
# ===========================================================================


class TestGenerateResearchChartsNonEmpty:
    """Function returns charts when query terms match a known series group."""

    def _fn(self):
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        return fn

    def test_commodity_query_produces_charts(self):
        """Query about oil prices with commodity summaries produces at least one chart."""
        result = self._fn()("crude oil price outlook for Africa", _COMMODITIES_SUMMARIES)
        assert len(result) >= 1, (
            "Expected at least 1 chart for commodity query with commodity summaries; "
            f"got {len(result)}"
        )

    def test_sapp_query_produces_charts(self):
        """Query about SAPP electricity prices produces at least one chart."""
        result = self._fn()(
            "SAPP day-ahead market electricity prices in southern Africa",
            _SAPP_SUMMARIES,
        )
        assert len(result) >= 1, (
            "Expected at least 1 chart for SAPP price query with SAPP summaries; "
            f"got {len(result)}"
        )

    def test_eskom_renewable_query_produces_charts(self):
        """Query about Eskom renewable generation produces at least one chart."""
        result = self._fn()(
            "Eskom wind and solar renewable energy generation capacity",
            _ESKOM_RE_SUMMARIES,
        )
        assert len(result) >= 1, (
            "Expected at least 1 chart for Eskom RE query; got {len(result)}"
        )

    def test_south_africa_electricity_query_produces_charts(self):
        """Query mentioning South Africa electricity with WB summaries produces charts."""
        result = self._fn()(
            "South Africa electricity generation coal versus renewables",
            _WB_ELECTRICITY_SUMMARIES,
        )
        assert len(result) >= 1, (
            "Expected at least 1 chart for SA electricity mix query; "
            f"got {len(result)}"
        )

    def test_full_summaries_with_commodity_query_produces_charts(self):
        """Full summaries dict with a commodity query produces charts."""
        result = self._fn()(
            "natural gas price trends and energy transition",
            _FULL_SUMMARIES,
        )
        assert len(result) >= 1, (
            "Expected at least 1 chart with full summaries and commodity query; "
            f"got {len(result)}"
        )


# ===========================================================================
# 6. data_uri format
# ===========================================================================


class TestDataUriFormat:
    """data_uri must conform to 'data:image/png;base64,<b64data>' format."""

    def _get_charts(self) -> list:
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        charts = fn("crude oil price outlook for Africa", _COMMODITIES_SUMMARIES)
        if not charts:
            pytest.skip("No charts returned — cannot validate data_uri format")
        return charts

    def test_data_uri_starts_with_png_prefix(self):
        """Every data_uri must start with 'data:image/png;base64,'."""
        charts = self._get_charts()
        for i, (_hint, _title, data_uri) in enumerate(charts):
            assert data_uri.startswith("data:image/png;base64,"), (
                f"Chart {i}: data_uri must start with 'data:image/png;base64,'; "
                f"got prefix: {data_uri[:40]!r}"
            )

    def test_data_uri_has_non_empty_base64_payload(self):
        """The base64 payload after the prefix must be non-empty."""
        import base64
        charts = self._get_charts()
        prefix = "data:image/png;base64,"
        for i, (_hint, _title, data_uri) in enumerate(charts):
            payload = data_uri[len(prefix):]
            assert payload, (
                f"Chart {i}: base64 payload is empty after prefix"
            )
            # Validate it decodes as real bytes (PNG magic bytes: \\x89PNG)
            try:
                decoded = base64.b64decode(payload)
            except Exception as exc:
                pytest.fail(
                    f"Chart {i}: base64 payload is not valid base64: {exc}"
                )
            assert decoded[:4] == b"\x89PNG", (
                f"Chart {i}: decoded bytes do not start with PNG magic bytes; "
                f"got {decoded[:4]!r}"
            )


# ===========================================================================
# 7. Max 4 charts per query
# ===========================================================================


class TestMaxChartsPerQuery:
    """At most 4 charts must be generated per call regardless of summaries size."""

    def test_max_4_charts_with_full_summaries(self):
        """Full summaries dict and broad query must still produce at most 4 charts."""
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        result = fn(
            "energy markets oil gas electricity renewables SAPP Eskom South Africa",
            _FULL_SUMMARIES,
        )
        assert len(result) <= 4, (
            f"generate_research_charts must return at most 4 charts; got {len(result)}"
        )

    def test_max_4_charts_with_repeated_calls(self):
        """Multiple calls on the same query also respect the 4-chart limit."""
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "generate_research_charts", None)
        if fn is None:
            pytest.skip("generate_research_charts not yet implemented")
        for _ in range(3):
            result = fn("oil and electricity prices Africa", _FULL_SUMMARIES)
            assert len(result) <= 4, (
                f"Repeated call returned {len(result)} charts; max is 4"
            )


# ===========================================================================
# 8. _build_market_context_for_query returns a 2-tuple
# ===========================================================================


class TestBuildMarketContextReturnType:
    """_build_market_context_for_query must return (str, dict), not just str."""

    def _get_fn(self):
        _skip_if_no_service()
        mod = _load_service()
        fn = getattr(mod, "_build_market_context_for_query", None)
        if fn is None:
            pytest.skip("_build_market_context_for_query not found in service module")
        return fn

    def test_function_is_visible_in_module(self):
        """_build_market_context_for_query must exist in deep_research_service.py."""
        _skip_if_no_service()
        mod = _load_service()
        assert hasattr(mod, "_build_market_context_for_query"), (
            "_build_market_context_for_query not found in deep_research_service"
        )

    def test_returns_tuple_not_string(self):
        """Return type must be tuple, not str."""
        fn = self._get_fn()
        # Use force=True to bypass detect_market_intent so we exercise the return path.
        # The function may fail to connect to live data stores — we catch those and
        # only assert on the structure of successful returns.
        try:
            result = fn("oil prices", force=True)
        except Exception:
            pytest.skip(
                "_build_market_context_for_query raised an exception (live deps unavailable); "
                "cannot validate return type"
            )
        assert isinstance(result, tuple), (
            f"_build_market_context_for_query must return a tuple (str, dict); "
            f"got {type(result).__name__}: {result!r}"
        )

    def test_returns_tuple_of_length_2(self):
        """The returned tuple must have exactly 2 elements."""
        fn = self._get_fn()
        try:
            result = fn("oil prices", force=True)
        except Exception:
            pytest.skip("Live deps unavailable — cannot validate tuple length")
        assert len(result) == 2, (
            f"_build_market_context_for_query must return a 2-tuple; got length {len(result)}"
        )

    def test_first_element_is_string(self):
        """First element of the returned tuple must be a str (context text)."""
        fn = self._get_fn()
        try:
            result = fn("oil prices", force=True)
        except Exception:
            pytest.skip("Live deps unavailable")
        context_text, _ = result
        assert isinstance(context_text, str), (
            f"First element must be str; got {type(context_text).__name__}"
        )

    def test_second_element_is_dict(self):
        """Second element of the returned tuple must be a dict (market summaries)."""
        fn = self._get_fn()
        try:
            result = fn("oil prices", force=True)
        except Exception:
            pytest.skip("Live deps unavailable")
        _, summaries = result
        assert isinstance(summaries, dict), (
            f"Second element must be dict; got {type(summaries).__name__}"
        )

    def test_non_market_query_returns_tuple_with_empty_string_and_dict(self):
        """Non-market query (force=False) must still return (str, dict), not just ''."""
        fn = self._get_fn()
        try:
            result = fn("medieval agricultural history in Europe")
        except Exception:
            pytest.skip("Module load or dep issue — cannot test non-market path")
        assert isinstance(result, tuple), (
            f"Even for non-market queries, must return tuple (str, dict); "
            f"got {type(result).__name__}"
        )
        assert len(result) == 2, (
            f"Non-market query result must be 2-tuple; got length {len(result)}"
        )
        context_text, summaries = result
        assert isinstance(context_text, str), (
            f"Non-market context_text must be str; got {type(context_text).__name__}"
        )
        assert isinstance(summaries, dict), (
            f"Non-market summaries must be dict; got {type(summaries).__name__}"
        )
        assert context_text == "", (
            f"Non-market context_text should be empty string; got {context_text!r}"
        )


# ===========================================================================
# 9. synthesize() accepts optional market_summaries keyword parameter
# ===========================================================================


class TestSynthesizeAcceptsMarketSummaries:
    """synthesize() must accept a market_summaries keyword argument."""

    def _get_synthesize(self):
        _skip_if_no_synthesizer()
        mod = _load_synthesizer()
        fn = getattr(mod, "synthesize", None)
        if fn is None:
            pytest.skip("synthesize not found in synthesizer module")
        return fn

    def test_synthesize_has_market_summaries_parameter(self):
        """synthesize() must include 'market_summaries' in its parameter list."""
        fn = self._get_synthesize()
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert "market_summaries" in params, (
            f"synthesize() must accept a 'market_summaries' keyword parameter; "
            f"current parameters: {params}"
        )

    def test_market_summaries_parameter_has_default_value(self):
        """market_summaries must have a default (None or {}) so existing callers are unaffected."""
        fn = self._get_synthesize()
        sig = inspect.signature(fn)
        param = sig.parameters.get("market_summaries")
        assert param is not None, (
            "market_summaries parameter not found in synthesize() signature"
        )
        assert param.default is not inspect.Parameter.empty, (
            "synthesize()'s market_summaries parameter must have a default value "
            "(None or {}) to maintain backward compatibility"
        )

    def test_market_summaries_default_does_not_break_existing_call_pattern(self):
        """Calling synthesize(state) with no market_summaries must not raise TypeError."""
        from engine.models import ResearchState
        fn = self._get_synthesize()
        state = ResearchState(original_query="test")
        sig = inspect.signature(fn)
        # We only inspect that the call can be bound without TypeError for the
        # market_summaries param being absent — we don't actually invoke the LLM.
        try:
            bound = sig.bind(state)
            bound.apply_defaults()
        except TypeError as exc:
            pytest.fail(
                f"synthesize(state) raises TypeError due to market_summaries: {exc}"
            )
        # market_summaries must be present in bound args after apply_defaults
        assert "market_summaries" in bound.arguments, (
            "market_summaries not present in bound arguments even after apply_defaults"
        )
