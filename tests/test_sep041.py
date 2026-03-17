"""Tests for SEP-041: Global View Filter Discovery and Date Range.

Real integration tests — no mocking of implementation internals.
Mocks are only used for the external newsroom API (network boundary).

Tests cover:
1. Cache 90-day rolling window — real NewsroomCache on temp dirs
2. Cache merge dedup by URL — real disk I/O, real JSON round-trips
3. Facets endpoint — real Flask route, real counting logic (mocks only the API data source)
4. Cache→facets integration — real cache feeds real facets endpoint
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
from collections import Counter

from tools.utils.newsroom_cache import NewsroomCache


# ---------------------------------------------------------------------------
# 1. Cache rolling window is 90 days
# ---------------------------------------------------------------------------

class TestCacheRollingWindow:
    """Real cache instances on temp dirs — exercises actual pruning logic."""

    def test_articles_at_various_ages(self):
        """Articles within 90 days kept, beyond 90 days pruned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            now = datetime.now()
            articles = [
                {"url": f"https://example.com/{age}d", "date": (now - timedelta(days=age)).strftime('%Y-%m-%d'), "headline": f"{age} days old"}
                for age in [1, 30, 60, 85, 91, 100, 120]
            ]
            cache.update(articles)
            result = cache.get_articles()
            kept_ages = {a["headline"] for a in result}
            # Within 90 days — must be kept
            assert "1 days old" in kept_ages
            assert "30 days old" in kept_ages
            assert "60 days old" in kept_ages
            assert "85 days old" in kept_ages
            # Beyond 90 days — must be pruned
            assert "91 days old" not in kept_ages
            assert "100 days old" not in kept_ages
            assert "120 days old" not in kept_ages

    def test_60_day_old_article_survives_full_round_trip(self):
        """A 60-day-old article written to cache should survive read-back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            date_60d = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            cache.update([{"url": "https://example.com/old", "date": date_60d, "headline": "Sixty days"}])
            # Read from a fresh cache instance (proves disk persistence)
            cache2 = NewsroomCache(cache_dir=Path(tmpdir))
            result = cache2.get_articles()
            assert len(result) == 1
            assert result[0]["headline"] == "Sixty days"


# ---------------------------------------------------------------------------
# 2. Cache merge dedup by URL
# ---------------------------------------------------------------------------

class TestCacheMergeDedup:
    """Real cache on temp dirs — exercises actual merge + dedup on disk."""

    def test_successive_updates_accumulate_articles(self):
        """Two update() calls with different URLs should accumulate both."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            today = datetime.now().strftime('%Y-%m-%d')

            cache.update([{"url": "https://example.com/1", "date": today, "headline": "First"}])
            cache.update([{"url": "https://example.com/2", "date": today, "headline": "Second"}])

            result = cache.get_articles()
            urls = {a["url"] for a in result}
            assert urls == {"https://example.com/1", "https://example.com/2"}

    def test_duplicate_url_replaced_not_duplicated(self):
        """Same URL in two updates should keep latest, not create duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            today = datetime.now().strftime('%Y-%m-%d')

            cache.update([{"url": "https://example.com/1", "date": today, "headline": "V1"}])
            cache.update([{"url": "https://example.com/1", "date": today, "headline": "V2"}])

            result = cache.get_articles()
            assert len(result) == 1
            assert result[0]["headline"] == "V2"

    def test_merge_with_mixed_new_and_existing(self):
        """Update with mix of known and new URLs should merge correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            today = datetime.now().strftime('%Y-%m-%d')

            cache.update([
                {"url": "https://example.com/a", "date": today, "headline": "A"},
                {"url": "https://example.com/b", "date": today, "headline": "B"},
            ])
            cache.update([
                {"url": "https://example.com/b", "date": today, "headline": "B-updated"},
                {"url": "https://example.com/c", "date": today, "headline": "C"},
            ])

            result = cache.get_articles()
            by_url = {a["url"]: a["headline"] for a in result}
            assert len(by_url) == 3
            assert by_url["https://example.com/a"] == "A"
            assert by_url["https://example.com/b"] == "B-updated"
            assert by_url["https://example.com/c"] == "C"


# ---------------------------------------------------------------------------
# 3. Facets endpoint
# ---------------------------------------------------------------------------

SAMPLE_ARTICLES = [
    {
        "headline": "Solar boom",
        "date": "2026-03-10",
        "source": "Reuters",
        "url": "https://example.com/solar",
        "topic_tags": ["energy", "solar"],
        "geography_tags": ["Africa"],
        "country_tags": ["South Africa"],
    },
    {
        "headline": "Wind expansion",
        "date": "2026-02-15",
        "source": "Bloomberg",
        "url": "https://example.com/wind",
        "topic_tags": ["energy", "wind"],
        "geography_tags": ["Europe"],
        "country_tags": ["Germany"],
    },
    {
        "headline": "Gas prices rise",
        "date": "2026-01-20",
        "source": "Reuters",
        "url": "https://example.com/gas",
        "topic_tags": ["gas", "commodities"],
        "geography_tags": ["North America"],
        "country_tags": ["United States"],
    },
]


class TestFacetsEndpoint:
    """Real Flask test client — only the data source (external API) is mocked."""

    @pytest.fixture
    def app_client(self):
        from ui.web.app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_facets_endpoint_returns_200(self, app_client):
        with patch('ui.web.app.fetch_newsroom_api', return_value=[]):
            resp = app_client.get('/api/news-intel/facets')
        assert resp.status_code == 200

    def test_facets_topic_counts_match_actual_data(self, app_client):
        """Topic counts should match what Counter would produce from the articles."""
        with patch('ui.web.app.fetch_newsroom_api', return_value=SAMPLE_ARTICLES):
            resp = app_client.get('/api/news-intel/facets')
        data = resp.get_json()

        # Compute expected counts from the raw data
        expected = Counter()
        for a in SAMPLE_ARTICLES:
            for t in a.get("topic_tags", []):
                expected[t] += 1

        actual = {t["name"]: t["count"] for t in data["topics"]}
        assert actual == dict(expected)

    def test_facets_source_counts_match_actual_data(self, app_client):
        with patch('ui.web.app.fetch_newsroom_api', return_value=SAMPLE_ARTICLES):
            resp = app_client.get('/api/news-intel/facets')
        data = resp.get_json()

        expected = Counter(a["source"] for a in SAMPLE_ARTICLES)
        actual = {s["name"]: s["count"] for s in data["sources"]}
        assert actual == dict(expected)

    def test_facets_topics_sorted_by_count_descending(self, app_client):
        with patch('ui.web.app.fetch_newsroom_api', return_value=SAMPLE_ARTICLES):
            resp = app_client.get('/api/news-intel/facets')
        counts = [t["count"] for t in resp.get_json()["topics"]]
        assert counts == sorted(counts, reverse=True)

    def test_facets_date_range_spans_all_articles(self, app_client):
        with patch('ui.web.app.fetch_newsroom_api', return_value=SAMPLE_ARTICLES):
            resp = app_client.get('/api/news-intel/facets')
        dr = resp.get_json()["date_range"]
        dates = sorted(a["date"][:10] for a in SAMPLE_ARTICLES)
        assert dr["min"] == dates[0]
        assert dr["max"] == dates[-1]

    def test_facets_empty_when_no_articles(self, app_client):
        with patch('ui.web.app.fetch_newsroom_api', return_value=[]):
            resp = app_client.get('/api/news-intel/facets')
        data = resp.get_json()
        assert data["topics"] == []
        assert data["sources"] == []
        assert data["date_range"]["min"] is None
        assert data["date_range"]["max"] is None


# ---------------------------------------------------------------------------
# 4. Cache → Facets integration (real cache feeds real endpoint)
# ---------------------------------------------------------------------------

class TestAllCachedArticlesAccessible:
    """Verify the UI endpoints don't artificially cap cached articles."""

    @pytest.fixture
    def app_client(self):
        from ui.web.app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_facets_counts_reflect_all_cached_articles(self, app_client):
        """Facets topic counts should sum to more than 500 if cache has >500 articles."""
        articles = []
        today = datetime.now().strftime('%Y-%m-%d')
        for i in range(800):
            articles.append({
                "url": f"https://example.com/{i}",
                "date": today,
                "source": "TestSource",
                "headline": f"Article {i}",
                "topic_tags": ["test_topic"],
            })
        with patch('ui.web.app.fetch_newsroom_api', return_value=articles):
            resp = app_client.get('/api/news-intel/facets')
        data = resp.get_json()
        test_topic = next(t for t in data["topics"] if t["name"] == "test_topic")
        assert test_topic["count"] == 800, f"Expected 800 but got {test_topic['count']} — articles are being capped"

    def test_articles_endpoint_returns_all_when_unfiltered(self, app_client):
        """Unfiltered articles request should return all cached articles, not cap at 200."""
        articles = []
        today = datetime.now().strftime('%Y-%m-%d')
        for i in range(600):
            articles.append({
                "url": f"https://example.com/{i}",
                "date": today,
                "source": "TestSource",
                "headline": f"Article {i}",
                "topic_tags": ["energy"],
            })
        with patch('ui.web.app.fetch_newsroom_api', return_value=articles):
            resp = app_client.post('/api/news-intel/articles',
                data='{"limit": 1000}',
                content_type='application/json')
        data = resp.get_json()
        assert data["count"] == 600, f"Expected 600 but got {data['count']} — articles are being capped"


class TestCacheFacetsIntegration:
    """End-to-end: populate a real cache, then hit the facets endpoint."""

    def test_facets_reflect_cached_articles(self):
        """Articles written to a real cache should appear in facets response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = NewsroomCache(cache_dir=Path(tmpdir))
            cache.update(SAMPLE_ARTICLES)

            # Patch the cache instance at its source (imported locally in fetch_newsroom_cached)
            with patch('tools.utils.newsroom_cache.get_cache', return_value=cache):
                from ui.web.app import app
                app.config['TESTING'] = True
                with app.test_client() as client:
                    resp = client.get('/api/news-intel/facets')

            data = resp.get_json()
            topic_names = {t["name"] for t in data["topics"]}
            assert "energy" in topic_names
            assert "solar" in topic_names
            source_names = {s["name"] for s in data["sources"]}
            assert "Reuters" in source_names
            assert "Bloomberg" in source_names
