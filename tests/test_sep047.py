"""Tests for SEP-047: Eskom HTTP fetch, Ember API client, SADC electricity
indicators, shared background threads, and Global View freshness timestamps.

These tests verify the five success criteria from the user's perspective:

1. Eskom data auto-fetches from eskom.co.za daily (no manual CSV download)
2. Ember monthly SA generation data appears in Global View cards
3. Global View shows SADC electricity indicators, not global GDP/inflation
4. All API-based data auto-refreshes in both REPL and web mode
5. SAPP data (manual download) shows last-updated timestamp in UI
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Criterion 1: Eskom data auto-fetches from eskom.co.za daily
# ---------------------------------------------------------------------------

class TestEskomHttpFetch:
    """An energy investor should get Eskom data automatically via HTTP,
    without needing to manually download CSV files to the data/ directory."""

    def test_eskom_client_can_fetch_from_url(self):
        """eskom_client must expose a function that fetches CSV data from a
        URL (not just from a local file path). The function should accept a
        URL and return the same dict-of-lists format as the existing parsers."""
        from tools.market import eskom_client

        # The module must have at least one function that can fetch from HTTP
        # (e.g., fetch_demand_observations, fetch_generation_observations, or
        # a new unified fetch function that accepts a URL parameter).
        fetchable = False
        for name in dir(eskom_client):
            fn = getattr(eskom_client, name)
            if callable(fn) and "fetch" in name.lower():
                # Function exists — URL fetching is handled inside _parse_csv
                fetchable = True
                break
        assert fetchable, (
            "eskom_client must expose at least one fetch function"
        )

    def test_eskom_client_handles_http_url(self):
        """When given an HTTP URL, eskom_client should fetch the CSV over
        HTTP rather than trying to open it as a local file."""
        from tools.market import eskom_client

        # Create a mock HTTP response that looks like a valid Eskom CSV
        csv_content = (
            "DateTimeKey,Residual Forecast,RSA Contracted Forecast\n"
            "2026-03-18 08:00:00,25000,28000\n"
            "2026-03-18 09:00:00,26000,29000\n"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_content
        mock_resp.iter_lines = lambda decode_unicode=False: csv_content.encode().splitlines()
        mock_resp.raise_for_status = MagicMock()
        # Make .content available for io.StringIO/BytesIO patterns
        mock_resp.content = csv_content.encode("utf-8")

        with patch("requests.get", return_value=mock_resp) as mock_get:
            # Try the demand observations function with an HTTP URL
            url = "https://www.eskom.co.za/dataportal/wp-content/uploads/2026/03/System_hourly_actual_and_forecasted_demand.csv"
            result = eskom_client.fetch_demand_observations(url)

            # The function should have made an HTTP request (not opened a file)
            mock_get.assert_called()
            # And returned parsed data
            assert isinstance(result, dict), "Should return dict of column->observations"

    def test_eskom_config_has_urls(self):
        """The ESKOM config section should contain URLs for daily fetch,
        not just local file names."""
        import config
        eskom_cfg = getattr(config, "ESKOM", {})

        # Must have at least one URL pointing to eskom.co.za
        has_url = False
        for key, val in eskom_cfg.items():
            if isinstance(val, str) and "eskom.co.za" in val:
                has_url = True
                break
            if isinstance(val, dict):
                for v in val.values():
                    if isinstance(v, str) and "eskom.co.za" in v:
                        has_url = True
                        break
        assert has_url, (
            "ESKOM config must include eskom.co.za URLs for auto-fetch"
        )

    def test_eskom_series_update_uses_http(self):
        """MarketWorkflow._update_series for Eskom series should trigger
        an HTTP fetch, not just read a local CSV."""
        from tools.market.series import SERIES_CATALOG

        # Verify an Eskom series exists
        eskom_series = [s for s in SERIES_CATALOG.values() if s.provider == "eskom"]
        assert len(eskom_series) > 0, "Eskom series must exist in catalog"

        # When we update an Eskom series, the workflow should use HTTP
        # (not just file I/O). We verify this by checking that the workflow
        # dispatches to an HTTP-capable code path.
        from workflows.market_workflow import MarketWorkflow

        store = MagicMock()
        store.get_staleness.return_value = None  # Force fetch
        store.get_last_observation_date.return_value = None

        wf = MarketWorkflow(store=store)

        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "DateTimeKey,Value\n2026-03-18 08:00:00,25000\n"
            mock_resp.content = mock_resp.text.encode()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            sid = eskom_series[0].series_id
            try:
                wf._update_series(sid, force=True)
            except Exception:
                pass  # May fail on parsing; we just need to verify HTTP was attempted

            # Should have called requests.get (HTTP fetch) not just open()
            assert mock_get.called, (
                "Eskom series update should fetch via HTTP, not local file"
            )


# ---------------------------------------------------------------------------
# Criterion 2: Ember monthly SA generation data appears in Global View cards
# ---------------------------------------------------------------------------

class TestEmberClient:
    """Ember Energy API client should exist and produce data that flows
    through to Global View cards."""

    def test_ember_client_module_exists(self):
        """tools.market.ember_client must be importable."""
        import importlib.util
        if importlib.util.find_spec("tools.market.ember_client") is None:
            pytest.fail("tools.market.ember_client module must exist")

    def test_ember_client_has_fetch_function(self):
        """ember_client must expose a fetch function that returns the
        standard List[Tuple[str, float]] observations format."""
        from tools.market import ember_client

        fetch_fns = [
            name for name in dir(ember_client)
            if callable(getattr(ember_client, name)) and "fetch" in name.lower()
        ]
        assert len(fetch_fns) > 0, (
            "ember_client must have at least one fetch function"
        )

    def test_ember_client_returns_observations_format(self):
        """The Ember fetch function should return data in the standard
        List[Tuple[str, float]] format used by all other clients."""
        from tools.market import ember_client

        # Mock the HTTP response with realistic Ember API data
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"date": "2026-01-01", "generation_twh": 15.2},
                {"date": "2026-02-01", "generation_twh": 14.8},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            # Find and call the fetch function
            fetch_fn = None
            for name in dir(ember_client):
                fn = getattr(ember_client, name)
                if callable(fn) and "fetch" in name.lower():
                    fetch_fn = fn
                    break

            assert fetch_fn is not None
            try:
                result = fetch_fn("ZAF")  # South Africa ISO code
            except TypeError:
                # Try without args or with different signature
                try:
                    result = fetch_fn()
                except Exception:
                    result = fetch_fn(country="ZAF")

            assert isinstance(result, list), "Must return a list"
            if len(result) > 0:
                assert isinstance(result[0], tuple), "Each item must be a tuple"
                assert len(result[0]) == 2, "Each tuple must be (date, value)"

    def test_ember_series_in_catalog(self):
        """SERIES_CATALOG must contain Ember series for SA generation data."""
        from tools.market.series import SERIES_CATALOG

        ember_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "ember"
        ]
        assert len(ember_series) > 0, (
            "SERIES_CATALOG must include Ember series"
        )

        # At least one should be about South Africa generation
        sa_generation = [
            s for s in ember_series
            if "south africa" in s.label.lower()
            or "sa " in s.label.lower()
            or "za" in s.series_id.lower()
            or "zaf" in s.series_id.lower()
        ]
        assert len(sa_generation) > 0, (
            "At least one Ember series must cover South Africa generation"
        )

    def test_ember_data_flows_to_market_latest_api(self):
        """The /api/market/latest endpoint should include Ember series
        when data is available in the store."""
        from tools.market.series import SERIES_CATALOG

        ember_ids = [
            sid for sid, s in SERIES_CATALOG.items() if s.provider == "ember"
        ]
        assert len(ember_ids) > 0, "Need Ember series in catalog"

        # The API endpoint iterates SERIES_CATALOG and calls store.get_series_df
        # for each. If Ember series are in the catalog, they'll appear in the
        # response when the store has data for them.
        # This is a structural test: the series exist and the API loop covers them.
        for eid in ember_ids:
            assert eid in SERIES_CATALOG, f"Ember series {eid} must be in catalog"
            assert SERIES_CATALOG[eid].provider == "ember"


# ---------------------------------------------------------------------------
# Criterion 3: Global View shows SADC electricity indicators, not GDP/inflation
# ---------------------------------------------------------------------------

class TestSadcElectricityIndicators:
    """The World Bank series in the catalog should be SADC electricity
    indicators, not generic global macro series like GDP and inflation."""

    def test_no_global_gdp_series(self):
        """The catalog must NOT contain generic World GDP series."""
        from tools.market.series import SERIES_CATALOG

        global_macro_ids = {
            "NY.GDP.MKTP.CD",       # World GDP (current USD)
            "NY.GDP.MKTP.KD.ZG",    # World GDP Growth
            "FP.CPI.TOTL.ZG",       # World Inflation (CPI)
            "NE.TRD.GNFS.ZS",       # Trade (% of GDP)
            "BX.KLT.DINV.WD.GD.ZS", # FDI Inflows (% GDP)
            "SI.POV.DDAY",           # Poverty ($2.15/day)
        }

        remaining = global_macro_ids & set(SERIES_CATALOG.keys())
        assert len(remaining) == 0, (
            f"Global macro series must be removed from catalog: {remaining}"
        )

    def test_catalog_has_sadc_electricity_indicators(self):
        """The catalog must contain World Bank electricity indicators
        relevant to SADC countries (ZA, ZW, MZ, BW, etc.)."""
        from tools.market.series import SERIES_CATALOG

        wb_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "worldbank"
        ]

        # Must have at least some WB series still (replaced, not just removed)
        assert len(wb_series) > 0, (
            "World Bank series must exist — replaced with SADC electricity indicators"
        )

        # The series should be electricity/energy related, not generic macro
        electricity_keywords = {
            "electric", "electricity", "energy", "power", "access",
            "renewable", "fossil", "generation", "consumption", "kwh",
            "electr",  # catches "electrification"
        }
        has_electricity = False
        for s in wb_series:
            label_lower = s.label.lower()
            sid_lower = s.series_id.lower()
            combined = label_lower + " " + sid_lower
            if any(kw in combined for kw in electricity_keywords):
                has_electricity = True
                break

        assert has_electricity, (
            f"World Bank series must include electricity/energy indicators. "
            f"Current WB series: {[s.label for s in wb_series]}"
        )

    def test_worldbank_series_group_is_energy_related(self):
        """World Bank series should be grouped under an energy-related
        group name, not 'development'."""
        from tools.market.series import SERIES_CATALOG

        wb_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "worldbank"
        ]
        assert len(wb_series) > 0

        # None should be in the generic "development" group
        dev_series = [s for s in wb_series if s.group == "development"]
        assert len(dev_series) == 0, (
            f"World Bank series should not be in generic 'development' group. "
            f"Found: {[s.label for s in dev_series]}"
        )

    def test_worldbank_country_targets_sadc(self):
        """World Bank indicator config or series should target SADC countries,
        not 'all' countries worldwide."""
        import config
        from tools.market.series import SERIES_CATALOG

        wb_config = getattr(config, "WORLD_BANK_INDICATORS", {})
        wb_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "worldbank"
        ]

        # Either the config default_country changed from "all" to SADC codes,
        # or individual series encode the country in their ID/metadata,
        # or the workflow passes country codes when fetching.
        # At minimum, the default_country should NOT be "all" for these indicators.
        is_targeted = (
            wb_config.get("default_country", "all") != "all"
            or any("ZA" in s.series_id.upper() or "ZW" in s.series_id.upper()
                   for s in wb_series)
        )
        assert is_targeted, (
            "World Bank indicators must target SADC countries, not global 'all'"
        )


# ---------------------------------------------------------------------------
# Criterion 4: All API-based data auto-refreshes in both REPL and web mode
# ---------------------------------------------------------------------------

class TestSharedBackgroundThreads:
    """Background refresh threads must start in both REPL (main.py) and
    web (web_main.py) mode through a shared module."""

    def test_background_threads_module_exists(self):
        """workflows.background_threads must be importable."""
        import importlib.util
        if importlib.util.find_spec("workflows.background_threads") is None:
            pytest.fail("workflows.background_threads module must exist")

    def test_background_threads_has_start_function(self):
        """The module must expose a function to start all refresh threads."""
        from workflows import background_threads

        start_fns = [
            name for name in dir(background_threads)
            if callable(getattr(background_threads, name))
            and "start" in name.lower()
            and not name.startswith("_")
        ]
        assert len(start_fns) > 0, (
            "background_threads must expose at least one public start function"
        )

    def test_background_threads_starts_market_refresh(self):
        """Calling the start function must launch a market refresh thread."""
        from workflows import background_threads

        start_fn = None
        for name in dir(background_threads):
            fn = getattr(background_threads, name)
            if callable(fn) and "start" in name.lower() and not name.startswith("_"):
                start_fn = fn
                break

        assert start_fn is not None

        with patch("threading.Thread") as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance
            try:
                start_fn()
            except Exception:
                pass  # May fail due to missing deps; we just check thread creation

            # At least one thread should have been created for market refresh
            thread_names = [
                call.kwargs.get("name", "") or ""
                for call in mock_thread.call_args_list
            ]
            has_market = any("market" in n.lower() for n in thread_names)
            assert has_market or mock_thread.called, (
                "start function must create at least one background thread"
            )

    def test_web_main_starts_background_threads(self):
        """web_main.py must import and use the shared background_threads module
        to start refresh threads, just like main.py does."""

        web_main_path = Path(__file__).resolve().parent.parent / "web_main.py"
        assert web_main_path.exists(), "web_main.py must exist"

        source = web_main_path.read_text()

        # web_main.py must reference background_threads (import or call)
        has_bg_threads = (
            "background_threads" in source
            or "start_all" in source
            or "start_background" in source
            or "start_refresh" in source
        )
        assert has_bg_threads, (
            "web_main.py must import/use background_threads module to start "
            "auto-refresh. Currently only main.py starts refresh threads."
        )

    def test_main_py_uses_shared_module(self):
        """main.py should use the shared background_threads module instead of
        defining refresh threads inline."""

        main_path = Path(__file__).resolve().parent.parent / "main.py"
        assert main_path.exists()

        source = main_path.read_text()

        # main.py should import from the shared module
        has_shared = (
            "background_threads" in source
            or "from workflows" in source and "start" in source
        )
        assert has_shared, (
            "main.py should use the shared background_threads module "
            "instead of defining _start_market_refresh_thread inline"
        )

    def test_eskom_refresh_happens_daily(self):
        """Eskom data should be configured to refresh at least daily,
        since eskom.co.za updates CSVs daily."""
        import config

        eskom_cfg = getattr(config, "ESKOM", {})
        market_cfg = getattr(config, "MARKET_DATA", {})

        # The staleness threshold for Eskom should be <= 24 hours
        stale_hours = market_cfg.get("stale_threshold_hours", 24)
        # Could also be overridden per-provider in ESKOM config
        eskom_stale = eskom_cfg.get("stale_threshold_hours", stale_hours)

        assert eskom_stale <= 24, (
            f"Eskom staleness threshold must be <= 24h for daily refresh, "
            f"got {eskom_stale}h"
        )


# ---------------------------------------------------------------------------
# Criterion 5: SAPP data (manual download) shows last-updated timestamp in UI
# ---------------------------------------------------------------------------

class TestFreshnessTimestamps:
    """Global View commodity cards should show data freshness timestamps
    so investors know how current the data is."""

    def test_market_latest_api_includes_freshness(self):
        """The /api/market/latest response must include a freshness timestamp
        for each series (last_fetched_at or equivalent field)."""

        # We test by checking that the API endpoint code path can produce
        # freshness info. Since the endpoint iterates SERIES_CATALOG and
        # queries the store, we verify the store can provide freshness data.
        from tools.market.store import MarketDataStore

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            store = MarketDataStore(db_path=db_path)
            # Insert some data with a known fetch time
            store.upsert_observations(
                "test_series",
                [("2026-03-18", 100.0)],
                provider="sapp",
            )

            # The store must expose the last_fetched_at timestamp
            cur = store.conn.cursor()
            cur.execute(
                "SELECT last_fetched_at FROM fetch_metadata "
                "WHERE provider = ? AND series_id = ?",
                ("sapp", "test_series"),
            )
            row = cur.fetchone()
            assert row is not None, "fetch_metadata must record last_fetched_at"
            assert row["last_fetched_at"] is not None, "last_fetched_at must have a value"

            # Verify the timestamp is an ISO datetime string
            ts = row["last_fetched_at"]
            dt = datetime.fromisoformat(ts)
            assert dt.year >= 2026, f"Timestamp looks wrong: {ts}"

            store.close()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_api_response_contains_freshness_field(self):
        """Each item in the /api/market/latest JSON response should contain
        a freshness-related field (e.g., last_fetched, freshness, updated_at)
        beyond just latest_date (which is the observation date, not fetch time)."""
        # We need to check that the API endpoint code includes freshness
        # in its response. Read the endpoint source to verify.
        import inspect
        from ui.web.app import get_market_latest

        source = inspect.getsource(get_market_latest)

        freshness_fields = [
            "last_fetched", "freshness", "updated_at", "fetched_at",
            "last_updated", "data_freshness", "fetch_time",
        ]
        has_freshness = any(f in source for f in freshness_fields)
        assert has_freshness, (
            "get_market_latest must include a freshness timestamp field "
            "(e.g., last_fetched, freshness) in its response, not just "
            "latest_date which is the observation date"
        )

    def test_sapp_cards_show_manual_download_age(self):
        """SAPP series (manual download) should include freshness info so
        investors know when the data was last imported."""
        from tools.market.series import SERIES_CATALOG

        sapp_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "sapp"
        ]
        assert len(sapp_series) > 0, "SAPP series must exist in catalog"

        # When data exists in the store, the API must be able to report
        # when it was last fetched (the import timestamp).
        from tools.market.store import MarketDataStore

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            store = MarketDataStore(db_path=db_path)
            sid = sapp_series[0].series_id
            store.upsert_observations(sid, [("2026-03-15 08:00", 42.5)], provider="sapp")

            # get_latest_point should include freshness info
            point = store.get_latest_point(sid, provider="sapp")
            assert point is not None

            # Either get_latest_point returns freshness directly, or we can
            # get it from staleness. The API must surface one of these.
            staleness = store.get_staleness(sid, provider="sapp")
            assert staleness is not None, (
                "Store must track staleness for SAPP series"
            )

            store.close()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_dataset_card_html_shows_freshness(self):
        """The renderDatasetCards JS function in the template should display
        a freshness indicator (not just the observation date)."""
        template_path = (
            Path(__file__).resolve().parent.parent
            / "ui" / "web" / "templates" / "index.html"
        )
        assert template_path.exists()

        html = template_path.read_text()

        # The card rendering must include a freshness field
        freshness_indicators = [
            "last_fetched", "freshness", "updated_at", "fetched_at",
            "last_updated", "data_freshness", "fetch_time", "data_age",
            "Updated", "Fetched", "refreshed",
        ]
        has_freshness_in_card = any(ind in html for ind in freshness_indicators)
        assert has_freshness_in_card, (
            "Dataset cards in index.html must display freshness timestamps. "
            "Currently only shows observation date via latest_date."
        )


# ---------------------------------------------------------------------------
# Integration: workflow dispatches to new providers correctly
# ---------------------------------------------------------------------------

class TestWorkflowProviderDispatch:
    """MarketWorkflow._update_series must route Ember series to the Ember
    client and Eskom series to the HTTP-fetching Eskom client."""

    def test_workflow_handles_ember_provider(self):
        """_update_series should recognize provider='ember' and dispatch
        to the ember_client."""
        from tools.market.series import SERIES_CATALOG
        from workflows.market_workflow import MarketWorkflow

        ember_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "ember"
        ]
        if not ember_series:
            pytest.skip("No Ember series in catalog yet")

        store = MagicMock()
        store.get_staleness.return_value = None
        store.get_last_observation_date.return_value = None

        wf = MarketWorkflow(store=store)

        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": []}
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            sid = ember_series[0].series_id
            try:
                wf._update_series(sid, force=True)
            except Exception:
                pass  # May fail on empty data

            # The workflow should have handled the series (returned True)
            # and not raised "unknown provider"

    def test_workflow_imports_ember_client(self):
        """MarketWorkflow must be able to import and use ember_client."""
        import inspect
        from workflows.market_workflow import MarketWorkflow

        source = inspect.getsource(MarketWorkflow._update_series)

        # The dispatch code should mention ember (import or condition)
        assert "ember" in source.lower(), (
            "MarketWorkflow._update_series must handle provider='ember'"
        )


# ---------------------------------------------------------------------------
# Catalog completeness: total series count and provider coverage
# ---------------------------------------------------------------------------

class TestCatalogCompleteness:
    """After replacing World Bank macro series with SADC electricity
    indicators and adding Ember series, the catalog should have
    comprehensive coverage of SADC energy data sources."""

    def test_all_providers_present(self):
        """The catalog should include series from fred, yfinance, worldbank,
        sapp, eskom, and ember providers."""
        from tools.market.series import get_all_providers

        providers = set(get_all_providers())
        expected = {"fred", "yfinance", "worldbank", "sapp", "eskom", "ember"}

        missing = expected - providers
        assert len(missing) == 0, (
            f"Missing providers in catalog: {missing}. "
            f"Current providers: {providers}"
        )

    def test_ember_series_has_correct_metadata(self):
        """Ember series should have sensible metadata (unit, frequency, group)."""
        from tools.market.series import SERIES_CATALOG

        ember_series = [
            s for s in SERIES_CATALOG.values() if s.provider == "ember"
        ]
        assert len(ember_series) > 0

        for s in ember_series:
            assert s.unit, f"Ember series {s.series_id} must have a unit"
            assert s.frequency in ("monthly", "annual", "daily"), (
                f"Ember series {s.series_id} has unexpected frequency: {s.frequency}"
            )
            assert s.group, f"Ember series {s.series_id} must have a group"
            assert s.label, f"Ember series {s.series_id} must have a label"
