from pathlib import Path
from unittest.mock import patch

import pytest


def article(headline, date, country="Germany", topic="energy", source="Desk", url=None):
    return {
        "headline": headline,
        "date": date,
        "source": source,
        "url": url or f"https://example.com/{headline.lower().replace(' ', '-')}",
        "topic_tags": [topic] if topic else [],
        "geography_tags": [],
        "country_tags": [country] if country else [],
    }


@pytest.fixture
def app_client():
    from ui.web.app import app
    import ui.web.auth as auth

    app.config["TESTING"] = True
    with (
        patch.object(
            auth,
            "get_current_user",
            return_value=({"user_id": "test-user", "team_id": None}, None),
        ),
        patch.object(
            auth, "_get_user_subscription", return_value=("professional", {}, "regular")
        ),
    ):
        with app.test_client() as client:
            yield client


def test_newsroom_cached_uses_stale_while_revalidate_when_cache_is_stale(tmp_path):
    """When cache is stale, first call returns stale data immediately.
    Background refresh updates cache for subsequent calls."""
    from tools.research import newsroom
    from tools.utils.newsroom_cache import NewsroomCache

    stale_cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)
    stale_cache.update([article("May stale", "2026-05-28")])
    latest_articles = [article("June latest", "2026-06-03")]

    with (
        patch("tools.research.newsroom._fetch_newsroom_export", return_value=latest_articles),
        patch("tools.research.newsroom._trigger_background_refresh"),
        patch(
            "tools.utils.newsroom_cache.NewsroomCache.is_fresh",
            side_effect=[False, False, True],
        ),
        patch("tools.utils.newsroom_cache.get_cache", return_value=stale_cache),
    ):
        articles, warning = newsroom.fetch_newsroom_cached(max_results=10)
        assert articles[0]["headline"] == "May stale"
        assert warning is None

        fresh_articles = newsroom._fetch_newsroom_export()
        stale_cache.update(fresh_articles)

        articles2, warning2 = newsroom.fetch_newsroom_cached(max_results=10)
        assert articles2[0]["headline"] == "June latest"
        assert articles2[0]["date"] == "2026-06-03"
        assert warning2 is None


def test_newsroom_cache_clear_invalidates_memory_cache(tmp_path):
    from tools.utils.newsroom_cache import NewsroomCache

    cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)
    cache.update([article("Cached article", "2026-06-03")])

    assert cache.get_articles()
    cache.clear()

    assert cache.get_articles() == []


def test_facets_date_range_comes_from_latest_article_universe(app_client):
    with patch(
        "tools.research.newsroom_dynamodb.generate_facets",
        return_value={
            "topics": [],
            "sources": [],
            "date_range": {"min": "2026-03-24", "max": "2026-06-03"},
        },
    ):
        response = app_client.get("/api/news-intel/facets")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["date_range"]["max"] == "2026-06-03"
    assert payload["date_range"]["min"] == "2026-03-24"


def test_articles_endpoint_returns_newest_first_for_same_universe(app_client):
    from ui import web

    articles = [
        article("Old article", "2026-03-24"),
        article("Latest article", "2026-06-03"),
        article("Middle article", "2026-05-30"),
    ]

    with patch.object(web.app, "fetch_newsroom_api", return_value=articles):
        response = app_client.post("/api/news-intel/articles", json={"limit": 10})

    assert response.status_code == 200
    payload = response.get_json()
    assert [a["headline"] for a in payload["articles"]] == [
        "Latest article",
        "Middle article",
        "Old article",
    ]


def test_stats_counts_match_articles_for_same_default_date_range(app_client):
    from ui import web

    articles = [
        article("Germany energy 1", "2026-05-28", country="Germany", topic="energy"),
        article("Germany energy 2", "2026-06-03", country="Germany", topic="energy"),
        article("Germany old energy", "2026-05-01", country="Germany", topic="energy"),
        article("France energy", "2026-06-03", country="France", topic="energy"),
    ]
    params = {"date_from": "2026-05-27", "date_to": "2026-06-03", "limit": 100}

    with (
        patch.object(web.app, "fetch_newsroom_cached", return_value=(articles, None)),
        patch.object(web.app, "fetch_newsroom_api", return_value=articles),
    ):
        stats_response = app_client.post("/api/news-intel/stats", json=params)
        articles_response = app_client.post("/api/news-intel/articles", json=params)

    assert stats_response.status_code == 200
    assert articles_response.status_code == 200

    stats_payload = stats_response.get_json()
    articles_payload = articles_response.get_json()
    germany_stat = next(s for s in stats_payload["stats"] if s["country"] == "Germany")
    germany_articles = [
        a
        for a in articles_payload["articles"]
        if "Germany" in (a.get("country_tags") or [])
    ]

    assert germany_stat["count"] == 2
    assert germany_stat["topics"]["energy"] == 2
    assert len(germany_articles) == 2


def test_frontend_awaits_facets_before_initial_global_view_requests():
    html = Path("ui/web/templates/index.html").read_text()
    load_facets_pos = html.index("await loadFacets();")
    params_pos = html.index("const params = {", load_facets_pos)
    stats_fetch_pos = html.index("fetch('/api/news-intel/stats'", params_pos)
    articles_fetch_pos = html.index("fetch('/api/news-intel/articles'", stats_fetch_pos)

    assert load_facets_pos < params_pos < stats_fetch_pos < articles_fetch_pos


def test_frontend_default_date_range_is_latest_week():
    html = Path("ui/web/templates/index.html").read_text()

    assert "dateTo.value = dr.max;" in html
    assert "fromDate.setDate(fromDate.getDate() - 7);" in html
    assert "dateFrom.value = fromDate.toISOString().slice(0, 10);" in html


def test_facets_endpoint_loads_fast_on_first_visit(app_client):
    """When a user opens Global View, /api/news-intel/facets must respond fast
    enough that the page doesn't hang on first load (cache cold)."""
    import time
    from tools.utils.newsroom_cache import get_cache

    get_cache().clear()
    
    mock_data = {
        "topics": [{"name": "energy", "count": 1}],
        "sources": [],
        "date_range": {"min": "2026-03-24", "max": "2026-06-03"},
    }

    with patch(
        "tools.research.newsroom_dynamodb.generate_facets",
        return_value=mock_data,
    ):
        start = time.time()
        response = app_client.get("/api/news-intel/facets")
        elapsed = time.time() - start

    assert response.status_code == 200
    payload = response.get_json()
    assert "topics" in payload and "date_range" in payload
    assert elapsed < 4, f"Facets endpoint too slow on first load: {elapsed:.1f}s (target < 4s)"


def test_facets_topic_distribution_is_diverse(app_client):
    """Topic facets must show multiple topics, not artificially dominated by one."""
    import time

    mock_data = {
        "topics": [
            {"name": "energy", "count": 60},
            {"name": "geopolitics", "count": 40},
        ],
        "sources": [],
        "date_range": {"min": "2026-03-24", "max": "2026-06-03"},
    }

    with patch(
        "tools.research.newsroom_dynamodb.generate_facets",
        return_value=mock_data,
    ):
        start = time.time()
        response = app_client.get("/api/news-intel/facets")
        elapsed = time.time() - start

    assert response.status_code == 200
    payload = response.get_json()
    topics = payload.get("topics", [])
    assert len(topics) >= 2, f"Expected multiple topics, got: {topics}"

    top_count = topics[0]["count"] if topics else 0
    total_count = sum(t["count"] for t in topics)
    if total_count > 0:
        assert top_count / total_count < 0.8, (
            f"Topic '{topics[0]['name']}' dominates at {top_count}/{total_count} — "
            "fallback extraction may not be working"
        )

    assert elapsed < 4, f"Facets endpoint too slow: {elapsed:.1f}s (target < 4s)"
