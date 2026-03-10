"""Tests for SEP-033: Global View + Digest tabs."""

import json
from unittest.mock import patch, MagicMock


def _import_app_module():
    """Import app module lazily to avoid startup side-effects in CI."""
    import importlib
    mod = importlib.import_module("ui.web.app")
    return mod


class TestCountryNormalization:
    """Test COUNTRY_ALIASES and normalize_country in app.py."""

    def test_country_aliases_exist(self):
        mod = _import_app_module()
        assert hasattr(mod, "COUNTRY_ALIASES"), "COUNTRY_ALIASES must be defined"
        assert isinstance(mod.COUNTRY_ALIASES, dict)
        assert len(mod.COUNTRY_ALIASES) >= 10, "Should have at least 10 alias entries"

    def test_normalize_country_function(self):
        mod = _import_app_module()
        fn = mod.normalize_country
        assert fn("US") == "United States"
        assert fn("USA") == "United States"
        assert fn("Usa") == "United States"
        assert fn("America") == "United States"
        assert fn("United States") == "United States"

    def test_normalize_country_uk_variants(self):
        mod = _import_app_module()
        fn = mod.normalize_country
        assert fn("UK") == "United Kingdom"
        assert fn("Britain") == "United Kingdom"
        assert fn("Great Britain") == "United Kingdom"
        assert fn("United Kingdom") == "United Kingdom"

    def test_normalize_country_passthrough(self):
        mod = _import_app_module()
        fn = mod.normalize_country
        assert fn("Zimbabwe") == "Zimbabwe"
        assert fn("Japan") == "Japan"

    def test_normalize_country_uae(self):
        mod = _import_app_module()
        fn = mod.normalize_country
        assert fn("UAE") == "United Arab Emirates"
        assert fn("Uae") == "United Arab Emirates"


class TestNewsIntelStatsEndpoint:
    """Test the /api/news-intel/stats endpoint."""

    @patch("ui.web.app.fetch_newsroom_api")
    def test_stats_endpoint_returns_aggregated_data(self, mock_fetch):
        mock_fetch.return_value = [
            {"headline": "A", "date": "2026-03-01", "source": "Reuters",
             "url": "", "topic_tags": ["energy"], "geography_tags": [],
             "country_tags": ["US"]},
            {"headline": "B", "date": "2026-03-02", "source": "BBC",
             "url": "", "topic_tags": ["trade"], "geography_tags": [],
             "country_tags": ["USA"]},
            {"headline": "C", "date": "2026-03-02", "source": "FT",
             "url": "", "topic_tags": ["trade"], "geography_tags": [],
             "country_tags": ["Britain"]},
        ]
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/stats",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_articles" in data
        assert "stats" in data
        country_names = [s["country"] for s in data["stats"]]
        assert country_names.count("United States") == 1
        assert "United Kingdom" in country_names

    @patch("ui.web.app.fetch_newsroom_api")
    def test_stats_endpoint_empty_articles(self, mock_fetch):
        mock_fetch.return_value = []
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/stats",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_articles"] == 0
        assert data["stats"] == []


class TestMarketLatestEndpoint:
    """Test the /api/market/latest endpoint."""

    @patch("ui.web.app.MarketDataStore")
    def test_latest_returns_series_data(self, mock_store_cls):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        import pandas as pd
        df = pd.DataFrame({"value": [100.0, 102.0]},
                          index=pd.to_datetime(["2026-03-07", "2026-03-08"]))
        mock_store.get_series_df.return_value = df

        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/api/market/latest")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestSynthesizeWithStagedItems:
    """Test that synthesize endpoint accepts staged_articles."""

    @patch("ui.web.app.fetch_newsroom_api")
    @patch("ui.web.app._news_intel_synthesis")
    def test_synthesize_accepts_staged_articles(self, mock_synth, mock_fetch):
        mock_fetch.return_value = []
        mock_synth.return_value = "Test synthesis"

        mod = _import_app_module()
        client = mod.app.test_client()
        staged = [
            {"headline": "Staged Article", "date": "2026-03-08",
             "source": "Manual", "url": "https://example.com",
             "topic_tags": ["test"]},
        ]
        resp = client.post("/api/news-intel/synthesize",
                           data=json.dumps({
                               "topic": "test",
                               "staged_articles": staged,
                           }),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "synthesis" in data


class TestTemplateStructure:
    """Test that the rendered template contains required UI elements."""

    def test_template_has_mode_switcher(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'data-mode="deep"' in html
        assert 'data-mode="digest"' in html
        assert 'data-mode="global"' in html

    def test_template_has_global_view_panel(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'globalViewSection' in html
        assert 'global-map-container' in html

    def test_template_has_digest_panel(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'digestPanel' in html
        assert 'digestHolding' in html

    def test_template_has_leaflet_cdn(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'leaflet' in html.lower()

    def test_template_has_country_aliases_js(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'COUNTRY_ALIASES' in html

    def test_template_has_staged_badge(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'stagedBadge' in html

    def test_no_old_mode_tabs_in_search_section(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'data-mode="intel"' not in html
        assert 'id="newsIntelPanel"' not in html
