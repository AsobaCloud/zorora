from __future__ import annotations

import importlib.util
import io
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRAPER_PATH = PROJECT_ROOT / "infra" / "lambda" / "newsroom_scraper" / "news_scraper.py"


class _ImportPaginator:
    def paginate(self, **kwargs):
        return []


class _ImportS3Client:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return _ImportPaginator()

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(b"{}")}


class _Response:
    def __init__(self, text: str):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = 200

    def raise_for_status(self):
        return None


class _Tracker:
    def __init__(self):
        self.incremented = 0
        self.completed_feeds = []
        self.completed_sources = []

    def is_feed_complete(self, _feed_url):
        return False

    def mark_feed_complete(self, feed_url):
        self.completed_feeds.append(feed_url)

    def is_source_complete(self, _source_url):
        return False

    def mark_source_complete(self, source_url):
        self.completed_sources.append(source_url)

    def increment_articles(self, count=1):
        self.incremented += count


def _load_scraper_module(monkeypatch):
    assert SCRAPER_PATH.exists(), f"expected imported scraper at {SCRAPER_PATH}"

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "unit-test-lambda")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: _ImportS3Client())

    module_name = f"newsroom_scraper_write_{id(monkeypatch)}"
    spec = importlib.util.spec_from_file_location(module_name, SCRAPER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module



def _runtime_article(title: str, article_date: str) -> dict:
    return {
        "headline": title,
        "date": article_date,
        "source": "Desk",
        "url": f"https://example.com/{title.lower().replace(' ', '-')}",
        "topic_tags": ["energy"],
        "geography_tags": ["Africa"],
        "country_tags": ["South Africa"],
        "description": "Short description",
        "full_content": "Body content",
    }



def test_rss_ingestion_uses_insert_article_with_full_content_and_no_s3_uploads(monkeypatch):
    module = _load_scraper_module(monkeypatch)
    tracker = _Tracker()
    inserted = []
    feed_xml = """
    <rss><channel><item>
      <title>Grid update</title>
      <link>https://example.com/articles/grid-update</link>
      <pubDate>Wed, 03 Jun 2026 10:00:00 GMT</pubDate>
      <description>Grid summary</description>
    </item></channel></rss>
    """

    monkeypatch.setattr(module, "progress_tracker", tracker)
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: _Response(feed_xml))
    monkeypatch.setattr(module, "extract_full_article_content", lambda _url: "Full body about grid bottlenecks")
    monkeypatch.setattr(module, "is_2025_article", lambda _date: True)
    monkeypatch.setattr(module, "matches_keywords", lambda _text: True)
    monkeypatch.setattr(
        module,
        "tag_article",
        lambda *_args, **_kwargs: {
            "core_topics": ["energy"],
            "matched_keywords": ["grid"],
            "continents": ["Africa"],
            "countries": ["South Africa"],
        },
    )
    monkeypatch.setattr(module, "insert_article", lambda metadata: inserted.append(metadata) or True, raising=False)
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    result = module.process_single_rss_feed("https://example.com/feed.xml")

    assert result == 1
    assert len(inserted) == 1
    assert inserted[0]["full_content"] == "Full body about grid bottlenecks"



def test_direct_ingestion_uses_insert_article_with_pub_date_and_no_s3_uploads(monkeypatch):
    module = _load_scraper_module(monkeypatch)
    tracker = _Tracker()
    inserted = []
    base_url = "https://example.com"
    article_url = "https://example.com/news/grid-market-update"
    base_html = '<html><body><a href="/news/grid-market-update">Story</a></body></html>'
    article_html = """
    <html>
      <head><title>Direct Grid Update</title></head>
      <body><time datetime="2026-06-03T10:00:00Z">2026-06-03</time></body>
    </html>
    """

    def _requests_get(url, **kwargs):
        if url == base_url:
            return _Response(base_html)
        if url == article_url:
            return _Response(article_html)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(module, "progress_tracker", tracker)
    monkeypatch.setattr(module.requests, "get", _requests_get)
    monkeypatch.setattr(module, "extract_full_article_content", lambda _url: "Full direct article body")
    monkeypatch.setattr(module, "matches_keywords", lambda _text: True)
    monkeypatch.setattr(module, "is_2025_article", lambda _date: True)
    monkeypatch.setattr(
        module,
        "tag_article",
        lambda *_args, **_kwargs: {
            "core_topics": ["energy"],
            "matched_keywords": ["grid"],
            "continents": ["Africa"],
            "countries": ["South Africa"],
        },
    )
    monkeypatch.setattr(module, "insert_article", lambda metadata: inserted.append(metadata) or True, raising=False)
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    result = module.scrape_website_articles(base_url, max_articles=5)

    assert result == 1
    assert len(inserted) == 1
    assert inserted[0]["pub_date"] == "2026-06-03T10:00:00Z"
    assert inserted[0]["full_content"] == "Full direct article body"



def test_duplicate_rss_article_skips_without_s3_uploads(monkeypatch):
    module = _load_scraper_module(monkeypatch)
    tracker = _Tracker()
    feed_xml = """
    <rss><channel><item>
      <title>Duplicate story</title>
      <link>https://example.com/articles/duplicate</link>
      <pubDate>Wed, 03 Jun 2026 10:00:00 GMT</pubDate>
      <description>Grid summary</description>
    </item></channel></rss>
    """

    monkeypatch.setattr(module, "progress_tracker", tracker)
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: _Response(feed_xml))
    monkeypatch.setattr(module, "extract_full_article_content", lambda _url: "Full body about duplicate")
    monkeypatch.setattr(module, "is_2025_article", lambda _date: True)
    monkeypatch.setattr(module, "matches_keywords", lambda _text: True)
    monkeypatch.setattr(
        module,
        "tag_article",
        lambda *_args, **_kwargs: {
            "core_topics": ["energy"],
            "matched_keywords": ["grid"],
            "continents": ["Africa"],
            "countries": ["South Africa"],
        },
    )
    monkeypatch.setattr(module, "insert_article", lambda _metadata: False, raising=False)
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    result = module.process_single_rss_feed("https://example.com/feed.xml")

    assert result == 0
    assert tracker.incremented == 0
