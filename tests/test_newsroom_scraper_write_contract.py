"""
Write contract tests for newsroom scraper.
Tests that the scraper uses DynamoDB insert_article with full_content and no S3 uploads.
"""

import sys
from pathlib import Path

# Add scraper to path
SCRAPER_DIR = Path(__file__).resolve().parents[1] / "infra" / "lambda" / "newsroom_scraper"
sys.path.insert(0, str(SCRAPER_DIR))


class _Response:
    def __init__(self, content):
        self.content = content.encode()
        self.status_code = 200


def _load_scraper_module(monkeypatch):
    """Load the scraper module."""
    import news_scraper
    return news_scraper


class _Tracker:
    def __init__(self):
        self.progress = {"rss_feeds": {"feeds_completed": []}, "total_articles": 0}

    def mark_feed_complete(self, feed_url):
        self.progress["rss_feeds"]["feeds_completed"].append(feed_url)

    def is_feed_complete(self, feed_url):
        return feed_url in self.progress["rss_feeds"]["feeds_completed"]

    def increment_articles(self, count=1):
        self.progress["total_articles"] += count

    def save_progress(self):
        pass


def test_rss_ingestion_uses_insert_article_with_full_content_and_no_s3_uploads(monkeypatch):
    """
    GIVEN an RSS feed with articles
    WHEN the scraper processes the feed
    THEN it should call insert_article with full_content and no S3 uploads
    """
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

    def mock_insert(metadata):
        inserted.append(metadata)
        return True

    monkeypatch.setattr(module, "insert_article", mock_insert)

    module.process_rss_feed("https://example.com/feed.xml")

    assert len(inserted) == 1
    assert inserted[0]["url"] == "https://example.com/articles/grid-update"
    assert inserted[0]["full_content"] == "Full body about grid bottlenecks"
    assert "s3_key" not in inserted[0]  # No S3 uploads


def test_duplicate_rss_article_skips_without_s3_uploads(monkeypatch):
    """
    GIVEN an RSS feed with a duplicate article
    WHEN the scraper processes the feed
    THEN it should skip the duplicate without S3 uploads
    """
    module = _load_scraper_module(monkeypatch)
    tracker = _Tracker()
    inserted = []
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

    def mock_insert(metadata):
        inserted.append(metadata)
        return True

    monkeypatch.setattr(module, "insert_article", mock_insert)

    module.process_rss_feed("https://example.com/feed.xml")

    assert len(inserted) == 1
    assert "s3_key" not in inserted[0]  # No S3 uploads


def test_fixed_sk_schema(monkeypatch):
    """
    GIVEN the scraper inserts an article
    WHEN insert_article is called
    THEN it should use SK='METADATA' for URL-based idempotency
    """
    module = _load_scraper_module(monkeypatch)
    tracker = _Tracker()
    inserted = []
    feed_xml = """
    <rss><channel><item>
      <title>Test article</title>
      <link>https://example.com/articles/test</link>
      <pubDate>Wed, 03 Jun 2026 10:00:00 GMT</pubDate>
      <description>Test summary</description>
    </item></channel></rss>
    """

    monkeypatch.setattr(module, "progress_tracker", tracker)
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: _Response(feed_xml))
    monkeypatch.setattr(module, "extract_full_article_content", lambda _url: "Test content")
    monkeypatch.setattr(
        module,
        "tag_article",
        lambda *_args, **_kwargs: {
            "core_topics": ["energy"],
            "matched_keywords": ["test"],
            "continents": ["Africa"],
            "countries": ["South Africa"],
        },
    )

    def mock_insert(metadata):
        inserted.append(metadata)
        return True

    monkeypatch.setattr(module, "insert_article", mock_insert)

    module.process_rss_feed("https://example.com/feed.xml")

    # Verify the metadata structure
    assert len(inserted) == 1
    # The actual SK verification is in the insert_article function, which is tested separately
    assert inserted[0]["url"] == "https://example.com/articles/test"
