"""Newsroom search tool - fetches articles from S3 export (fast, no auth required)."""

import logging
import requests
import threading
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import config

logger = logging.getLogger(__name__)

# Lock for coalescing concurrent fetches
_fetch_lock = threading.Lock()

STOP_WORDS = frozenset({
    'why', 'did', 'does', 'how', 'what', 'when', 'where', 'who',
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'or', 'is', 'was', 'were', 'are', 'been', 'be', 'has', 'had',
    'do', 'with', 'from', 'about', 'that', 'this', 'it', 'not',
})

# S3 export URL - single file with all articles, updated hourly by Lambda
NEWSROOM_EXPORT_URL = "https://news-collection-website.s3.us-east-1.amazonaws.com/zorora-export/articles.json"


def _extract_keywords(query: str) -> List[str]:
    """Extract substantive keywords from a query, removing stop words."""
    return [w for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def _get_timeout() -> int:
    """Get timeout for newsroom fetch (S3 is fast)."""
    return getattr(config, 'NEWSROOM_CONFIG', {}).get('timeout', 30)


def fetch_newsroom_cached(max_results: int = 100):
    """
    Fetch newsroom articles with caching (90-day rolling window).

    Uses local cache to avoid repeated API calls. Cache refreshes
    daily (24-hour TTL) since newsroom updates ~400 articles/day.
    New articles are merged with existing cache, deduplicated by URL.

    Args:
        max_results: Max articles to return (default: 100)

    Returns:
        Tuple of (articles_list, error_string_or_None).
        error is None on success, a warning message on stale-cache fallback,
        or an error message when no data is available.
    """
    from tools.utils.newsroom_cache import get_cache

    cache = get_cache()

    # Fast path: cache is fresh
    if cache.is_fresh():
        articles = cache.get_articles()
        logger.info(f"Newsroom cache hit: {len(articles)} articles (age: {int(cache.get_age_seconds())}s)")
        return (articles[:max_results], None)

    # Slow path: cache is stale, acquire lock to refresh
    with _fetch_lock:
        # Double-check freshness after acquiring lock
        if cache.is_fresh():
            articles = cache.get_articles()
            logger.info(f"Newsroom cache hit (after lock): {len(articles)} articles")
            return (articles[:max_results], None)

        logger.info("Newsroom cache stale, fetching from S3 export...")
        articles = _fetch_newsroom_export()

        if articles:
            cache.update(articles)
            return (articles[:max_results], None)

    # Lock released and API failed - try to use stale cache as fallback
    stale_articles = cache.get_articles()
    if stale_articles:
        logger.warning(f"API failed, using stale cache: {len(stale_articles)} articles")
        return (stale_articles[:max_results], "Using cached data \u2014 newsroom API unavailable")

    return ([], "Newsroom API unavailable and no cached data")


def _fetch_newsroom_export() -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles from S3 export file.
    
    Single HTTP request, returns all ~3000 articles in 2-3 seconds.
    No authentication required - S3 bucket is public-read for this path.
    
    Returns:
        List of article dicts
    """
    try:
        response = requests.get(
            NEWSROOM_EXPORT_URL,
            timeout=30,
            headers={'Accept': 'application/json'}
        )
        
        if response.status_code != 200:
            logger.error(f"Newsroom S3 export returned {response.status_code}")
            return []
        
        data = response.json()
        articles = data.get('articles', [])
        
        # Validate article format
        valid_articles = []
        for article in articles:
            if article.get('headline') and article.get('url'):
                valid_articles.append(article)
        
        logger.info(f"✓ Newsroom S3 export: {len(valid_articles)} articles (exported at {data.get('exported_at', 'unknown')})")
        return valid_articles
        
    except requests.exceptions.Timeout:
        logger.error("Newsroom S3 export timed out after 30s")
        return []
    except Exception as e:
        logger.error(f"Newsroom S3 export error: {e}")
        return []


def fetch_newsroom_api(query: str = None, days_back: int = 90, max_results: int = 25) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles and return structured data.
    Uses S3 export - no authentication required.

    Args:
        query: Search term for filtering (optional)
        days_back: Number of days to search back (default: 90)
        max_results: Max results to return (default: 25)

    Returns:
        List of article dictionaries with keys: headline, date, url, source, topic_tags, etc.
    """
    try:
        # Calculate date cutoff
        date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Fetch all articles from S3 export
        all_articles = _fetch_newsroom_export()
        
        if not all_articles:
            return []
        
        # Filter by date
        articles = [a for a in all_articles if a.get('date', '') >= date_cutoff]
        
        # Apply search filter if query provided
        if query:
            keywords = _extract_keywords(query)
            if keywords:
                filtered = []
                for article in articles:
                    searchable = f"{article.get('headline', '')} {' '.join(article.get('topic_tags', []))}".lower()
                    if any(kw in searchable for kw in keywords):
                        filtered.append(article)
                articles = filtered
        
        logger.info(f"Newsroom: {len(articles)} articles from S3 export")
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
        max_results = getattr(config, 'NEWSROOM_MAX_RELEVANT', 25)

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
                    "country": article.get("country_tags", [])
                },
                "date": article.get("date", "")
            }
            headlines.append(headline)

        # Simple keyword filtering if query provided
        if query:
            query_words = [w.lower() for w in query.split() if len(w) >= 3]
            filtered = []
            for h in headlines:
                title_lower = h['title'].lower()
                # Match if any query word appears in title or topics
                topics_str = ' '.join(str(t) for t in h['tags'].get('core_topics', []))
                searchable = f"{title_lower} {topics_str}".lower()
                if any(word in searchable for word in query_words):
                    filtered.append(h)
            headlines = filtered[:max_results]
            logger.info(f"Filtered to {len(headlines)} articles matching: {query[:50]}")
        else:
            # No query - return most recent
            headlines = sorted(headlines, key=lambda x: x.get('date', ''), reverse=True)[:max_results]
            logger.info(f"Returning {len(headlines)} most recent articles")
        
        if not headlines:
            return "No matching articles found in newsroom"
        
        # Calculate tag distribution for overview
        all_topics = []
        for h in headlines:
            if h['tags'] and isinstance(h['tags'], dict):
                core_topics = h['tags'].get('core_topics', [])
                if isinstance(core_topics, list):
                    all_topics.extend([str(t) for t in core_topics if t])
        topic_counts = Counter(all_topics)
        
        # Format output with topic distribution and ALL headlines
        today = datetime.now()
        formatted = [f"Newsroom Headlines for {today.strftime('%Y-%m-%d')} ({len(headlines)} articles)\n"]
        formatted.append("=" * 80 + "\n")
        
        if topic_counts:
            formatted.append("\nTopic Distribution:")
            for topic, count in topic_counts.most_common(15):
                formatted.append(f"  • {topic}: {count} articles")
            formatted.append("\n" + "=" * 80 + "\n")
            
            # Group headlines by primary core_topic
            by_topic = defaultdict(list)
            for h in headlines:
                if h['tags'] and isinstance(h['tags'], dict):
                    core_topics = h['tags'].get('core_topics', [])
                    if core_topics and isinstance(core_topics, list) and len(core_topics) > 0:
                        primary_topic = str(core_topics[0])
                        by_topic[primary_topic].append(h)
            
            # Show ALL headlines grouped by topic
            formatted.append("\nRelevant Headlines by Topic:\n")
            for topic, count in topic_counts.most_common():
                if topic in by_topic:
                    formatted.append(f"\n{topic.upper()} ({count} articles):")
                    for h in by_topic[topic]:
                        date_str = h.get('date', 'Unknown date')
                        formatted.append(f"  • {h['title']} [{date_str}]")
                        if h.get('url'):
                            formatted.append(f"    URL: {h['url']}")
                        formatted.append(f"    Source: {h['source']}")
        else:
            # Fallback: just list all headlines if no topics
            for idx, h in enumerate(headlines, 1):
                date_str = h.get('date', 'Unknown date')
                formatted.append(f"\n{idx}. {h['title']} [{date_str}]")
                formatted.append(f"   Source: {h['source']}")
                if h.get('url'):
                    formatted.append(f"   URL: {h['url']}")
        
        return "\n".join(formatted)
        
    except Exception as e:
        logger.error(f"Newsroom headlines error: {e}")
        return f"⚠ Newsroom unavailable (using academic + web only): {str(e)}"
