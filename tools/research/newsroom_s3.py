"""Newsroom search tool - fetches articles directly from S3 (no API auth required)."""

import json
import logging
import threading
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter, defaultdict

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

import config

logger = logging.getLogger(__name__)

# Lock for coalescing concurrent fetches
_fetch_lock = threading.Lock()

# S3 Configuration
NEWSROOM_BUCKET = "news-collection-website"
NEWSROOM_PREFIX = "news/"

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


def _extract_keywords(query: str) -> List[str]:
    """Extract substantive keywords from a query, removing stop words."""
    return [w for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def _get_s3_client():
    """Get S3 client (region-agnostic for public buckets)."""
    if not HAS_BOTO3:
        raise RuntimeError("boto3 not installed, cannot access S3")
    return boto3.client("s3", region_name="us-east-1")


def _list_date_folders(s3_client, days_back: int = 90) -> List[str]:
    """List date folders in S3 for the specified range."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # List all date prefixes
        response = s3_client.list_objects_v2(
            Bucket=NEWSROOM_BUCKET, Prefix=NEWSROOM_PREFIX, Delimiter="/"
        )

        date_folders = []
        for prefix in response.get("CommonPrefixes", []):
            folder = prefix.get("Prefix", "").replace(NEWSROOM_PREFIX, "").rstrip("/")
            # Filter to YYYY-MM-DD format and date range
            if len(folder) == 10 and folder[4] == "-" and folder[7] == "-":
                if (
                    start_date.strftime("%Y-%m-%d")
                    <= folder
                    <= end_date.strftime("%Y-%m-%d")
                ):
                    date_folders.append(folder)

        return sorted(date_folders, reverse=True)  # Newest first
    except Exception as e:
        logger.error(f"Error listing S3 date folders: {e}")
        return []


def _fetch_articles_from_date(
    s3_client, date_folder: str, max_results: int = 500
) -> List[Dict]:
    """Fetch all articles from a specific date folder."""
    articles = []

    try:
        # List metadata.json files for this date (in metadata/ subfolder)
        prefix = f"{NEWSROOM_PREFIX}{date_folder}/metadata/"
        response = s3_client.list_objects_v2(
            Bucket=NEWSROOM_BUCKET, Prefix=prefix, MaxKeys=1000
        )

        # Files are named {hash}.json, not metadata.json
        keys = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".json")
        ]

        # Batch fetch metadata files
        for key in keys[:max_results]:
            try:
                obj = s3_client.get_object(Bucket=NEWSROOM_BUCKET, Key=key)
                metadata = json.loads(obj["Body"].read().decode("utf-8"))

                # Normalize to standard format
                tags = metadata.get("tags", {})
                topic_tags = tags.get("core_topics", []) or []
                if not topic_tags:
                    # Fallback: use special_tags and matched_keywords when core_topics is empty
                    topic_tags = tags.get("special_tags", []) or []
                    if not topic_tags:
                        topic_tags = tags.get("matched_keywords", []) or []

                article = {
                    "headline": metadata.get("title", ""),
                    "date": _parse_date(metadata.get("pub_date", "")),
                    "topic_tags": topic_tags,
                    "geography_tags": tags.get("continents", []),
                    "country_tags": tags.get("countries", []),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", "Unknown"),
                }
                articles.append(article)
            except Exception as e:
                logger.warning(f"Error reading {key}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error fetching from {date_folder}: {e}")

    return articles


def _parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str:
        return ""

    # Try common formats
    formats = ["%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z", "%d %b %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(
                date_str[: len(fmt.replace("%", "YY"))], fmt
            ).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

    # Return as-is if parsing fails
    return date_str[:10] if len(date_str) >= 10 else date_str


def fetch_newsroom_s3_raw(
    days_back: int = 90, max_results: int = 10000
) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles directly from S3 (no API auth required).

    Args:
        days_back: Number of days to fetch (default: 90)
        max_results: Maximum articles to return

    Returns:
        List of article dictionaries
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available, cannot fetch from S3")
        return []

    try:
        s3_client = _get_s3_client()

        # Get date folders
        date_folders = _list_date_folders(s3_client, days_back)
        logger.info(f"Found {len(date_folders)} date folders to scan")

        if not date_folders:
            logger.warning("No date folders found in S3")
            return []

        # Fetch articles from each date
        all_articles = []
        seen_urls = set()

        for date_folder in date_folders:
            if len(all_articles) >= max_results:
                break

            articles = _fetch_articles_from_date(
                s3_client, date_folder, max_results - len(all_articles)
            )

            # Deduplicate by URL
            for article in articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    all_articles.append(article)
                    seen_urls.add(url)

            logger.info(f"Fetched {len(articles)} articles from {date_folder}")

        # Sort by date (newest first)
        all_articles.sort(key=lambda x: x.get("date", ""), reverse=True)

        logger.info(f"Total unique articles from S3: {len(all_articles)}")
        return all_articles[:max_results]

    except Exception as e:
        logger.error(f"Error fetching from S3: {e}")
        return []


# Backwards compatibility: use S3 as primary source
fetch_newsroom_api_raw = fetch_newsroom_s3_raw


def fetch_newsroom_cached(max_results: int = 100):
    """
    Fetch newsroom articles with caching (90-day rolling window).
    Uses S3 as the source (no API authentication required).
    """
    from tools.utils.newsroom_cache import get_cache

    cache = get_cache()

    # Fast path: cache is fresh
    if cache.is_fresh():
        articles = cache.get_articles()
        logger.info(
            f"Newsroom cache hit: {len(articles)} articles (age: {int(cache.get_age_seconds())}s)"
        )
        return (articles[:max_results], None)

    # Slow path: cache is stale, acquire lock to refresh
    with _fetch_lock:
        # Double-check freshness after acquiring lock
        if cache.is_fresh():
            articles = cache.get_articles()
            logger.info(f"Newsroom cache hit (after lock): {len(articles)} articles")
            return (articles[:max_results], None)

        logger.info("Newsroom cache stale, fetching fresh data from S3...")
        articles = fetch_newsroom_s3_raw(days_back=90, max_results=3000)

        if articles:
            cache.update(articles)
            return (articles[:max_results], None)

    # Lock released and fetch failed - try to use stale cache as fallback
    stale_articles = cache.get_articles()
    if stale_articles:
        logger.warning(
            f"S3 fetch failed, using stale cache: {len(stale_articles)} articles"
        )
        return (
            stale_articles[:max_results],
            "Using cached data — newsroom data refresh unavailable",
        )

    return ([], "Newsroom data unavailable and no cached data")


def fetch_newsroom_api(
    query: str = None, days_back: int = 90, max_results: int = 25
) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles and return structured data.
    Uses S3 as source - no authentication required.
    """
    try:
        articles = fetch_newsroom_s3_raw(days_back=days_back, max_results=1000)

        if not articles:
            return []

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

        logger.info(f"Newsroom: {len(articles)} articles from S3")
        return articles[:max_results]

    except Exception as e:
        logger.warning(f"Newsroom fetch error: {e}")
        return []


def get_newsroom_headlines(query: str = None, max_results: int = None) -> str:
    """Fetch newsroom articles from cache and return formatted string for REPL display."""
    if max_results is None:
        max_results = getattr(config, "NEWSROOM_MAX_RELEVANT", 25)

    try:
        # Fetch from cache
        articles, _cache_error = fetch_newsroom_cached(max_results=200)

        if not articles:
            return "No articles found in newsroom cache"

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
                topics_str = " ".join(str(t) for t in h["tags"].get("core_topics", []))
                searchable = f"{title_lower} {topics_str}".lower()
                if any(word in searchable for word in query_words):
                    filtered.append(h)
            headlines = filtered[:max_results]
            logger.info(f"Filtered to {len(headlines)} articles matching: {query[:50]}")
        else:
            headlines = sorted(
                headlines, key=lambda x: x.get("date", ""), reverse=True
            )[:max_results]
            logger.info(f"Returning {len(headlines)} most recent articles")

        if not headlines:
            return "No matching articles found in newsroom"

        # Calculate tag distribution
        all_topics = []
        for h in headlines:
            if h["tags"] and isinstance(h["tags"], dict):
                core_topics = h["tags"].get("core_topics", [])
                if isinstance(core_topics, list):
                    all_topics.extend([str(t) for t in core_topics if t])
        topic_counts = Counter(all_topics)

        # Format output
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

            # Group by primary topic
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
            for idx, h in enumerate(headlines, 1):
                date_str = h.get("date", "Unknown date")
                formatted.append(f"\n{idx}. {h['title']} [{date_str}]")
                formatted.append(f"   Source: {h['source']}")
                if h.get("url"):
                    formatted.append(f"   URL: {h['url']}")

        return "\n".join(formatted)

    except Exception as e:
        logger.error(f"Newsroom headlines error: {e}")
        return f"⚠ Newsroom unavailable: {str(e)}"
