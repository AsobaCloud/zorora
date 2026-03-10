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
    """Test the /api/news-intel/stats endpoint uses cached data."""

    @patch("ui.web.app.fetch_newsroom_cached")
    def test_stats_endpoint_returns_aggregated_data(self, mock_cached):
        mock_cached.return_value = ([
            {"headline": "A", "date": "2026-03-01", "source": "Reuters",
             "url": "", "topic_tags": ["energy"], "geography_tags": [],
             "country_tags": ["US"]},
            {"headline": "B", "date": "2026-03-02", "source": "BBC",
             "url": "", "topic_tags": ["trade"], "geography_tags": [],
             "country_tags": ["USA"]},
            {"headline": "C", "date": "2026-03-02", "source": "FT",
             "url": "", "topic_tags": ["trade"], "geography_tags": [],
             "country_tags": ["Britain"]},
        ], None)
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

    @patch("ui.web.app.fetch_newsroom_cached")
    def test_stats_endpoint_empty_articles(self, mock_cached):
        mock_cached.return_value = ([], None)
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/stats",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_articles"] == 0
        assert data["stats"] == []

    @patch("ui.web.app.fetch_newsroom_cached")
    def test_stats_endpoint_returns_warning_on_stale_cache(self, mock_cached):
        mock_cached.return_value = (
            [{"headline": "X", "date": "2026-03-01", "source": "R",
              "url": "", "topic_tags": [], "geography_tags": [],
              "country_tags": ["US"]}],
            "Using cached data \u2014 newsroom API unavailable",
        )
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/stats",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["warning"] == "Using cached data \u2014 newsroom API unavailable"


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


class TestArticlesEndpointCached:
    """Test that /articles endpoint uses fetch_newsroom_cached and returns warning."""

    @patch("ui.web.app.fetch_newsroom_cached")
    def test_articles_endpoint_uses_cache(self, mock_cached):
        mock_cached.return_value = ([
            {"headline": "Cached Article", "date": "2026-03-01", "source": "AP",
             "url": "https://example.com", "topic_tags": ["energy"],
             "geography_tags": [], "country_tags": ["US"]},
        ], None)
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/articles",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["articles"][0]["headline"] == "Cached Article"
        assert "warning" not in data or data["warning"] is None

    @patch("ui.web.app.fetch_newsroom_cached")
    def test_articles_endpoint_returns_warning(self, mock_cached):
        mock_cached.return_value = (
            [{"headline": "Stale", "date": "2026-03-01", "source": "AP",
              "url": "", "topic_tags": [], "geography_tags": [],
              "country_tags": []}],
            "Using cached data \u2014 newsroom API unavailable",
        )
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.post("/api/news-intel/articles",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["warning"] == "Using cached data \u2014 newsroom API unavailable"


class TestSynthesizeWithStagedItems:
    """Test that synthesize endpoint accepts staged_articles."""

    @patch("ui.web.app.fetch_newsroom_cached")
    @patch("ui.web.app._news_intel_synthesis")
    def test_synthesize_accepts_staged_articles(self, mock_synth, mock_cached):
        mock_cached.return_value = ([], None)
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


class TestNewsroomCachedReturnsTuple:
    """Test that fetch_newsroom_cached returns (articles, error) tuple."""

    @patch("tools.utils.newsroom_cache.get_cache")
    def test_cache_hit_returns_tuple_with_none_error(self, mock_get_cache):
        cache = MagicMock()
        cache.is_fresh.return_value = True
        cache.get_articles.return_value = [{"headline": "A"}]
        cache.get_age_seconds.return_value = 100
        mock_get_cache.return_value = cache

        from tools.research.newsroom import fetch_newsroom_cached
        result = fetch_newsroom_cached(max_results=10)
        assert isinstance(result, tuple), "fetch_newsroom_cached must return a tuple"
        assert len(result) == 2
        articles, error = result
        assert len(articles) == 1
        assert error is None

    @patch("tools.research.newsroom._fetch_newsroom_api_raw")
    @patch("tools.utils.newsroom_cache.get_cache")
    def test_api_fail_stale_fallback_returns_warning(self, mock_get_cache, mock_raw):
        cache = MagicMock()
        cache.is_fresh.return_value = False
        cache.get_articles.return_value = [{"headline": "Stale"}]
        mock_get_cache.return_value = cache
        mock_raw.return_value = []  # API failed

        from tools.research.newsroom import fetch_newsroom_cached
        articles, error = fetch_newsroom_cached(max_results=10)
        assert len(articles) == 1
        assert error is not None
        assert "unavailable" in error.lower()

    @patch("tools.research.newsroom._fetch_newsroom_api_raw")
    @patch("tools.utils.newsroom_cache.get_cache")
    def test_api_fail_no_cache_returns_empty_with_error(self, mock_get_cache, mock_raw):
        cache = MagicMock()
        cache.is_fresh.return_value = False
        cache.get_articles.return_value = []
        mock_get_cache.return_value = cache
        mock_raw.return_value = []

        from tools.research.newsroom import fetch_newsroom_cached
        articles, error = fetch_newsroom_cached(max_results=10)
        assert articles == []
        assert error is not None
        assert "unavailable" in error.lower()


class TestNewsroomTimeout:
    """Test that NEWSROOM_API_TIMEOUT is 30s for Lambda cold-start tolerance."""

    def test_timeout_is_30(self):
        from tools.research.newsroom import NEWSROOM_API_TIMEOUT
        assert NEWSROOM_API_TIMEOUT == 30


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

    def test_template_has_coverage_indicator(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'gvMapCoverage' in html

    def test_template_has_warning_banner(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'gvWarningBanner' in html

    def test_template_has_rich_popup_function(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'TOPICS' in html
        assert 'SOURCES' in html

    def test_template_has_filter_by_topic_function(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'filterGvByTopic' in html

    def test_template_has_filter_by_source_function(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'filterGvBySource' in html

    def test_template_has_gv_all_articles_variable(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'gvAllArticles' in html

    def test_template_topic_rows_are_clickable(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert "filterGvByTopic(" in html

    def test_template_source_rows_are_clickable(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert "filterGvBySource(" in html

    def test_no_old_mode_tabs_in_search_section(self):
        mod = _import_app_module()
        client = mod.app.test_client()
        resp = client.get("/")
        html = resp.data.decode()
        assert 'data-mode="intel"' not in html
        assert 'id="newsIntelPanel"' not in html
