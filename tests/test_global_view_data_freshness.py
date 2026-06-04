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


def test_newsroom_cached_refreshes_when_cache_date_lags_latest_s3_folder(tmp_path):
    from tools.research import newsroom
    from tools.utils.newsroom_cache import NewsroomCache

    stale_cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)
    stale_cache.update([article("March stale", "2026-03-24")])
    latest_articles = [article("June latest", "2026-06-03")]

    with (
        patch(
            "tools.research.newsroom.fetch_newsroom_s3_raw",
            return_value=latest_articles,
        ),
        patch(
            "tools.utils.newsroom_cache.NewsroomCache._get_s3_max_date",
            return_value="2026-06-03",
        ),
        patch("tools.utils.newsroom_cache.get_cache", return_value=stale_cache),
    ):
        articles, warning = newsroom.fetch_newsroom_cached(max_results=10)

    assert warning is None
    assert articles[0]["headline"] == "June latest"
    assert articles[0]["date"] == "2026-06-03"


def test_newsroom_cache_clear_invalidates_memory_cache(tmp_path):
    from tools.utils.newsroom_cache import NewsroomCache

    cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)
    cache.update([article("Cached article", "2026-06-03")])

    assert cache.get_articles()
    cache.clear()

    assert cache.get_articles() == []


def test_facets_date_range_comes_from_latest_article_universe(app_client):
    from ui import web

    articles = [
        article("March stale", "2026-03-24"),
        article("June latest", "2026-06-03"),
    ]

    with patch.object(web.app, "fetch_newsroom_api", return_value=articles):
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


def test_s3_topic_fallback_uses_special_tags_when_core_topics_empty():
    """When core_topics is empty, topic_tags should fall back to special_tags."""
    from tools.research.newsroom_s3 import _fetch_articles_from_date
    import json
    from unittest.mock import Mock

    mock_metadata = {
        "title": "Test Article",
        "pub_date": "2026-06-03",
        "url": "https://example.com/test",
        "source": "TestSource",
        "tags": {
            "core_topics": [],
            "special_tags": ["economy_politics"],
            "matched_keywords": ["tax", "election"],
            "continents": ["Asia"],
            "countries": ["India"],
        },
    }

    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "news/2026-06-03/metadata/test.json"}]}
    mock_s3.get_object.return_value = {"Body": Mock(read=lambda: json.dumps(mock_metadata).encode())}

    articles = _fetch_articles_from_date(mock_s3, "2026-06-03", max_results=1)

    assert len(articles) == 1
    assert articles[0]["topic_tags"] == ["economy_politics"]


def test_s3_topic_fallback_uses_matched_keywords_when_special_tags_also_empty():
    """When both core_topics and special_tags are empty, use matched_keywords."""
    from tools.research.newsroom_s3 import _fetch_articles_from_date
    import json
    from unittest.mock import Mock

    mock_metadata = {
        "title": "Test Article",
        "pub_date": "2026-06-03",
        "url": "https://example.com/test",
        "source": "TestSource",
        "tags": {
            "core_topics": [],
            "special_tags": [],
            "matched_keywords": ["tariff", "trade"],
            "continents": ["Americas"],
            "countries": ["United States"],
        },
    }

    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "news/2026-06-03/metadata/test.json"}]}
    mock_s3.get_object.return_value = {"Body": Mock(read=lambda: json.dumps(mock_metadata).encode())}

    articles = _fetch_articles_from_date(mock_s3, "2026-06-03", max_results=1)

    assert len(articles) == 1
    assert articles[0]["topic_tags"] == ["tariff", "trade"]
