from datetime import date
from unittest.mock import patch

from tools.research import newsroom
from tools.utils.newsroom_cache import NewsroomCache
from workflows.deep_research.aggregator import parse_newsroom_results
from workflows.digest_synthesis import news_intel_synthesis


def _article(headline, article_date, **overrides):
    article = {
        "headline": headline,
        "date": article_date,
        "source": "Desk",
        "url": f"https://example.com/{headline.lower().replace(' ', '-')}",
        "topic_tags": ["energy"],
        "geography_tags": [],
        "country_tags": [],
        "description": "",
        "full_content": "",
    }
    article.update(overrides)
    return article


class _CapturingClient:
    def __init__(self):
        self.messages = None

    def chat_complete(self, messages, tools=None):
        self.messages = messages
        return {"choices": []}

    def extract_content(self, response):
        return "ok"


def test_fetch_newsroom_cached_returns_cached_articles_without_s3_recency_check(tmp_path):
    recent = date.today().isoformat()
    cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)
    cache.update([_article("Cached newsroom item", recent)])

    with patch("tools.utils.newsroom_cache.get_cache", return_value=cache), patch.object(
        NewsroomCache,
        "_get_s3_max_date",
        side_effect=AssertionError("runtime must not query S3 for newsroom freshness"),
    ):
        articles, warning = newsroom.fetch_newsroom_cached(max_results=10)

    assert warning is None
    assert [article["headline"] for article in articles] == ["Cached newsroom item"]



def test_fetch_newsroom_cached_does_not_fallback_to_s3_when_dynamodb_fails(tmp_path):
    cache = NewsroomCache(cache_dir=tmp_path, ttl_seconds=86400)

    with patch("tools.utils.newsroom_cache.get_cache", return_value=cache), patch(
        "tools.research.newsroom.fetch_newsroom_dynamodb_raw",
        side_effect=RuntimeError("dynamodb unavailable"),
    ), patch(
        "tools.research.newsroom_s3.fetch_newsroom_s3_raw",
        side_effect=AssertionError("runtime must not fall back to S3"),
    ):
        articles, error = newsroom.fetch_newsroom_cached(max_results=10)

    assert articles == []
    assert error



def test_news_intel_synthesis_includes_full_article_body_in_prompt():
    client = _CapturingClient()
    body = "Body fact: transformer bottlenecks forced curtailment in Northern Cape."
    articles = [
        _article(
            "Energy grid shifts",
            date.today().isoformat(),
            full_content=body,
            topic_tags=["energy", "grid"],
        )
    ]

    with patch("workflows.digest_synthesis.create_specialist_client", return_value=client):
        result = news_intel_synthesis(articles, topic="energy")

    assert result == "ok"
    assert body in client.messages[1]["content"]



def test_parse_newsroom_results_preserves_full_content_for_deep_research():
    body = "Body fact: utilities delayed interconnection work after storm damage."
    articles = [
        _article(
            "Energy grid shifts",
            date.today().isoformat(),
            full_content=body,
            topic_tags=["energy", "grid"],
        )
    ]

    sources = parse_newsroom_results(articles, query="energy grid")

    assert len(sources) == 1
    assert sources[0].content_full == body
