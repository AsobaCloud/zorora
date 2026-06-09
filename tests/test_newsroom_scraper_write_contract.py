"""
Write contract tests for restored newsroom scraper.
Verifies integration with the new DynamoDB ingestion contract.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add scraper and tools to path
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRAPER_DIR = REPO_ROOT / "infra" / "lambda" / "newsroom_scraper"
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(REPO_ROOT))

def test_rss_ingestion_uses_correct_contract(monkeypatch):
    """
    GIVEN an RSS feed with articles
    WHEN the scraper processes the feed
    THEN it should call insert_article with the expected metadata structure.
    """
    import news_scraper
    
    inserted = []
    feed_xml = """
    <rss><channel><item>
      <title>Grid update about electricity</title>
      <link>https://example.com/articles/grid-update</link>
      <pubDate>Wed, 03 Jun 2026 10:00:00 GMT</pubDate>
      <description>Electricity grid summary</description>
    </item></channel></rss>
    """

    # Mock dependencies
    monkeypatch.setattr(news_scraper, "PROGRESS_FILE", "/tmp/test_progress.json")
    monkeypatch.setattr(news_scraper.progress_tracker, "is_feed_complete", lambda _url: False)
    monkeypatch.setattr(news_scraper.requests, "get", lambda *args, **kwargs: MagicMock(content=feed_xml.encode(), status_code=200, raise_for_status=lambda: None))
    monkeypatch.setattr(news_scraper, "extract_full_article_content", lambda _url: "Full body content")
    
    def mock_insert(metadata):
        inserted.append(metadata)
        return True

    monkeypatch.setattr(news_scraper, "insert_article", mock_insert)

    # Run the processing logic
    news_scraper.process_single_rss_feed("https://example.com/feed.xml")

    assert len(inserted) == 1
    article = inserted[0]
    assert article["url"] == "https://example.com/articles/grid-update"
    assert article["source"] == "RSS Feed"
    assert "tags" in article
    assert "full_content" in article
    assert article["full_content"] == "Full body content"
