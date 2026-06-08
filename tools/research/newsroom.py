"""Newsroom search tool - fetches articles from DynamoDB (fast, indexed queries)."""

import logging
import os
import requests
import threading
from typing import List, Dict, Any
from datetime import datetime
from collections import Counter, defaultdict

import config
from tools.research.newsroom_dynamodb import fetch_newsroom_dynamodb_raw

logger = logging.getLogger(__name__)

# Lock for coalescing concurrent fetches
_fetch_lock = threading.Lock()

STOP_WORDS = frozenset(
    {
        "why",
        "did",
        "does",
        "how",
        "what",
        "when",
        "where",
        "who",
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "is",
        "was",
        "were",
        "are",
        "been",
        "be",
        "has",
        "had",
        "do",
        "with",
        "from",
        "about",
        "that",
        "this",
        "it",
        "not",
    }
)

# S3 export URL - single file with all articles, updated hourly by Lambda
# Can be overridden via environment variable for quick fixes
NEWSROOM_EXPORT_URL = os.environ.get(
    "NEWSROOM_EXPORT_URL",
    "https://news-collection-website.s3.us-east-1.amazonaws.com/zorora-export/articles.json",
)


def _extract_keywords(query: str) -> List[str]:
    """Extract substantive keywords from a query, removing stop words."""
    return [w for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def _get_timeout() -> int:
    """Get timeout for newsroom fetch (S3 is fast)."""
    return getattr(config, "NEWSROOM_CONFIG", {}).get("timeout", 30)


# Background refresh tracking
_refresh_thread = None


def _trigger_background_refresh(cache):
    """Start a background thread to refresh stale cache without blocking requests."""
    global _refresh_thread
    if _refresh_thread is not None and _refresh_thread.is_alive():
        return

    def _refresh():
        try:
            with _fetch_lock:
                if cache.is_fresh():
                    return
                articles = _fetch_newsroom_export()
                if articles:
                    cache.update(articles)
        except Exception as e:
            logger.error(f"Background refresh failed: {e}", exc_info=True)

    _refresh_thread = threading.Thread(target=_refresh, daemon=True)
    _refresh_thread.start()


def fetch_newsroom_cached(max_results: int = 10000):
    """
    Fetch newsroom articles with caching (90-day rolling window).

    Stale-while-revalidate: if cache is stale, returns cached data immediately
    and refreshes in the background. First cold-start blocks until data is fetched.

    Args:
        max_results: Max articles to return

    Returns:
        Tuple of (articles_list, error_string_or_None).
    """
    from tools.utils.newsroom_cache import get_cache

    cache = get_cache()

    def _sorted(articles):
        articles = list(articles)
        articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        return articles

    # Fast path: cache is fresh
    if cache.is_fresh():
        articles = _sorted(cache.get_articles())
        return (articles[:max_results], None)

    # Stale-while-revalidate path
    with _fetch_lock:
        # Double-check after acquiring lock
        if cache.is_fresh():
            articles = _sorted(cache.get_articles())
            return (articles[:max_results], None)

        stale_articles = cache.get_articles()
        if stale_articles:
            # Return stale data immediately, refresh in background
            _trigger_background_refresh(cache)
            logger.info(
                f"Newsroom stale-while-revalidate: {len(stale_articles)} articles"
            )
            return (_sorted(stale_articles)[:max_results], None)

        # No cache at all — must block and fetch
        logger.info("Newsroom cache cold, fetching baseline...")
        articles = _fetch_newsroom_export()

        if articles:
            cache.update(articles)
            return (_sorted(articles)[:max_results], None)

    # Everything failed — return empty
    return ([], "Newsroom data unavailable and no cached data")


def _fetch_newsroom_export() -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles from DynamoDB (indexed queries).

    Uses DynamoDB for fast, indexed queries by date range.
    Replaces S3 date folder fetching.

    Returns:
        List of article dicts
    """
    try:
        articles = fetch_newsroom_dynamodb_raw(days_back=7, max_results=500)
        logger.info(f"Newsroom DynamoDB fetch: {len(articles)} articles")
        return articles
    except Exception as e:
        logger.error(f"Newsroom DynamoDB fetch error: {e}")
        return []


def _fetch_newsroom_export_fallback() -> List[Dict[str, Any]]:
    """
    Fallback: Fetch from S3 export file if date folder fetch fails.
    """
    try:
        response = requests.get(
            NEWSROOM_EXPORT_URL, timeout=30, headers={"Accept": "application/json"}
        )

        if response.status_code != 200:
            logger.error(f"Newsroom S3 export returned {response.status_code}")
            return []

        data = response.json()
        articles = data.get("articles", [])

        valid_articles = []
        for article in articles:
            if article.get("headline") and article.get("url"):
                valid_articles.append(article)

        logger.warning(f"⚠ Using stale export file: {len(valid_articles)} articles")
        return valid_articles

    except Exception as e:
        logger.error(f"Newsroom export fallback error: {e}")
        return []


def fetch_newsroom_api(
    query: str = None,
    days_back: int = 90,
    max_results: int = 25,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles and return structured data.
    Uses DynamoDB for indexed queries - no authentication required.

    Args:
        query: Search term for filtering (optional)
        days_back: Number of days to search back (default: 90)
        max_results: Max results to return (default: 25)

    Returns:
        List of article dictionaries with keys: headline, date, url, source, topic_tags, etc.
    """
    try:
        # Fetch from DynamoDB
        all_articles = fetch_newsroom_dynamodb_raw(
            days_back=days_back,
            max_results=1000,
            include_content=include_content,
        )

        if not all_articles:
            return []

        # Apply search filter if query provided
        articles = all_articles
        if query:
            keywords = _extract_keywords(query)
            if keywords:
                filtered = []
                for article in articles:
                    searchable = f"{article.get('headline', '')} {' '.join(article.get('topic_tags', []))}".lower()
                    if any(kw in searchable for kw in keywords):
                        filtered.append(article)
                articles = filtered

        logger.info(f"Newsroom: {len(articles)} articles from DynamoDB")
        return articles[:max_results]

    except Exception as e:
        logger.warning(f"Newsroom fetch error: {e}")
        return []


def get_newsroom_headlines(query: str = None, max_results: int = None) -> str:
    """
    Fetch newsroom articles from cache and return formatted string for REPL display.

    Uses 7-day rolling cache. For queries, does simple keyword filtering.
    For full semantic search, use /search which handles filtering at synthesis.

    Args:
        query: Optional keyword filter (simple matching, not semantic)
        max_results: Max articles to return (default from config)

    Returns:
        Formatted string with article headlines, sources, and URLs
    """
    if max_results is None:
        max_results = getattr(config, "NEWSROOM_MAX_RELEVANT", 25)

    try:
        # Fetch from cache (7-day rolling window)
        articles, _cache_error = fetch_newsroom_cached(max_results=200)

        if not articles:
            return "No articles found in newsroom cache (check logs if unexpected)"

        logger.info(f"Processing {len(articles)} articles from cache")

        # Convert to headline format
        headlines = []
        for article in articles:
            headline = {
                "title": article.get("headline", "No title"),
                "source": article.get("source", "Unknown"),
                "url": article.get("url", ""),
                "tags": {
                    "core_topics": article.get("topic_tags", []),
                    "geography": article.get("geography_tags", []),
                    "country": article.get("country_tags", []),
                },
                "date": article.get("date", ""),
            }
            headlines.append(headline)

        # Simple keyword filtering if query provided
        if query:
            query_words = [w.lower() for w in query.split() if len(w) >= 3]
            filtered = []
            for h in headlines:
                title_lower = h["title"].lower()
                # Match if any query word appears in title or topics
                topics_str = " ".join(str(t) for t in h["tags"].get("core_topics", []))
                searchable = f"{title_lower} {topics_str}".lower()
                if any(word in searchable for word in query_words):
                    filtered.append(h)
            headlines = filtered[:max_results]
            logger.info(f"Filtered to {len(headlines)} articles matching: {query[:50]}")
        else:
            # No query - return most recent
            headlines = sorted(
                headlines, key=lambda x: x.get("date", ""), reverse=True
            )[:max_results]
            logger.info(f"Returning {len(headlines)} most recent articles")

        if not headlines:
            return "No matching articles found in newsroom"

        # Calculate tag distribution for overview
        all_topics = []
        for h in headlines:
            if h["tags"] and isinstance(h["tags"], dict):
                core_topics = h["tags"].get("core_topics", [])
                if isinstance(core_topics, list):
                    all_topics.extend([str(t) for t in core_topics if t])
        topic_counts = Counter(all_topics)

        # Format output with topic distribution and ALL headlines
        today = datetime.now()
        formatted = [
            f"Newsroom Headlines for {today.strftime('%Y-%m-%d')} ({len(headlines)} articles)\n"
        ]
        formatted.append("=" * 80 + "\n")

        if topic_counts:
            formatted.append("\nTopic Distribution:")
            for topic, count in topic_counts.most_common(15):
                formatted.append(f"  • {topic}: {count} articles")
            formatted.append("\n" + "=" * 80 + "\n")

            # Group headlines by primary core_topic
            by_topic = defaultdict(list)
            for h in headlines:
                if h["tags"] and isinstance(h["tags"], dict):
                    core_topics = h["tags"].get("core_topics", [])
                    if (
                        core_topics
                        and isinstance(core_topics, list)
                        and len(core_topics) > 0
                    ):
                        primary_topic = str(core_topics[0])
                        by_topic[primary_topic].append(h)

            # Show ALL headlines grouped by topic
            formatted.append("\nRelevant Headlines by Topic:\n")
            for topic, count in topic_counts.most_common():
                if topic in by_topic:
                    formatted.append(f"\n{topic.upper()} ({count} articles):")
                    for h in by_topic[topic]:
                        date_str = h.get("date", "Unknown date")
                        formatted.append(f"  • {h['title']} [{date_str}]")
                        if h.get("url"):
                            formatted.append(f"    URL: {h['url']}")
                        formatted.append(f"    Source: {h['source']}")
        else:
            # Fallback: just list all headlines if no topics
            for idx, h in enumerate(headlines, 1):
                date_str = h.get("date", "Unknown date")
                formatted.append(f"\n{idx}. {h['title']} [{date_str}]")
                formatted.append(f"   Source: {h['source']}")
                if h.get("url"):
                    formatted.append(f"   URL: {h['url']}")

        return "\n".join(formatted)

    except Exception as e:
        logger.error(f"Newsroom headlines error: {e}")
        return f"⚠ Newsroom unavailable (using academic + web only): {str(e)}"
