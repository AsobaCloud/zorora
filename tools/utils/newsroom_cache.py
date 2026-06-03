"""Cache for newsroom articles - 90-day rolling window."""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Data freshness tolerance - cache is stale if behind S3 by more than this
DATA_LAG_TOLERANCE_SECONDS = 3600  # 1 hour

# Cache location
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "newsroom"
CACHE_FILE = CACHE_DIR / "articles.json"
CACHE_TTL_SECONDS = 86400  # 24 hours
ROLLING_WINDOW_DAYS = 90


class NewsroomCache:
    """
    Cache for newsroom articles with 90-day rolling window.

    - Caches articles locally to avoid repeated API calls
    - Refreshes daily (24-hour TTL) since newsroom updates ~400 articles/day
    - Merges new articles with existing cache (dedup by URL)
    - Prunes articles older than 90 days
    """

    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "articles.json"
        self.ttl_seconds = ttl_seconds
        self._ensure_cache_dir()
        self._memory_cache = None  # (timestamp, data_dict)

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk, with in-memory buffering."""
        # Use memory cache if valid (short TTL for consistency)
        if self._memory_cache:
            m_time, m_data = self._memory_cache
            if time.time() - m_time < 60:  # 60 second memory buffer
                return m_data

        if not self.cache_file.exists():
            return {"last_fetch": 0, "articles": []}

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self._memory_cache = (time.time(), data)
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load newsroom cache: {e}")
            return {"last_fetch": 0, "articles": []}

    def _save_cache(self, data: Dict[str, Any]):
        """Save cache to disk and update memory buffer."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            self._memory_cache = (time.time(), data)
        except IOError as e:
            logger.error(f"Failed to save newsroom cache: {e}")

    def _prune_old_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove articles older than rolling window."""
        cutoff = datetime.now() - timedelta(days=ROLLING_WINDOW_DAYS)
        cutoff_str = cutoff.strftime('%Y-%m-%d')

        pruned = []
        for article in articles:
            article_date = article.get('date', '')[:10]  # Get YYYY-MM-DD
            if article_date >= cutoff_str:
                pruned.append(article)

        if len(pruned) < len(articles):
            logger.info(f"Pruned {len(articles) - len(pruned)} old articles from cache")

        return pruned

    def _get_cached_max_date(self) -> Optional[str]:
        """Get the most recent article date in cache."""
        articles = self.get_articles()
        if not articles:
            return None
        dates = [a.get('date', '')[:10] for a in articles if a.get('date')]
        return max(dates) if dates else None

    def _get_s3_max_date(self) -> Optional[str]:
        """Get the most recent date available in S3 (lightweight check)."""
        try:
            # Import here to avoid circular imports and allow test mocking
            from tools.research.newsroom_s3 import _list_date_folders, _get_s3_client
            s3_client = _get_s3_client()
            folders = _list_date_folders(s3_client, days_back=90)
            return folders[0] if folders else None
        except Exception as e:
            logger.debug(f"Could not check S3 max date: {e}")
            return None

    def is_fresh(self) -> bool:
        """Check if cache is fresh (within TTL and data recency)."""
        # First check: timestamp-based freshness
        cache = self._load_cache()
        last_fetch = cache.get("last_fetch", 0)
        age = time.time() - last_fetch
        if age >= self.ttl_seconds:
            return False

        # Second check: data recency (cached articles match S3 availability)
        cached_max = self._get_cached_max_date()
        s3_max = self._get_s3_max_date()

        if cached_max is None or s3_max is None:
            # Can't determine data recency - fall back to timestamp only
            return True

        # Cache is stale if behind S3 by more than tolerance
        if s3_max > cached_max:
            logger.info(f"Cache data stale: cached={cached_max}, s3={s3_max}")
            return False

        return True

    def get_articles(self) -> List[Dict[str, Any]]:
        """
        Get cached articles.

        Returns:
            List of article dicts, or empty list if no cache
        """
        cache = self._load_cache()
        articles = cache.get("articles", [])
        return self._prune_old_articles(articles)

    def update(self, articles: List[Dict[str, Any]]):
        """
        Merge new articles into the cache, deduplicating by URL.

        New articles overwrite existing ones with the same URL.
        After merging, prunes articles older than the rolling window.

        Args:
            articles: List of article dicts from API
        """
        existing = self._load_cache().get("articles", [])

        # Build lookup from existing articles keyed by URL
        by_url = {a["url"]: a for a in existing if a.get("url")}

        # Merge: new articles overwrite existing with same URL
        for article in articles:
            url = article.get("url")
            if url:
                by_url[url] = article

        merged = list(by_url.values())
        pruned = self._prune_old_articles(merged)

        cache = {
            "last_fetch": time.time(),
            "articles": pruned
        }
        self._save_cache(cache)
        logger.info(f"Newsroom cache updated: {len(pruned)} articles (merged from {len(existing)} existing + {len(articles)} new)")

    def get_age_seconds(self) -> float:
        """Get cache age in seconds."""
        cache = self._load_cache()
        last_fetch = cache.get("last_fetch", 0)
        return time.time() - last_fetch

    def clear(self):
        """Clear the cache."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.info("Newsroom cache cleared")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache = self._load_cache()
        articles = cache.get("articles", [])
        last_fetch = cache.get("last_fetch", 0)

        return {
            "article_count": len(articles),
            "last_fetch": datetime.fromtimestamp(last_fetch).isoformat() if last_fetch else None,
            "age_seconds": int(time.time() - last_fetch) if last_fetch else None,
            "is_fresh": self.is_fresh()
        }


# Global cache instance
_cache: Optional[NewsroomCache] = None


def get_cache() -> NewsroomCache:
    """Get global newsroom cache instance."""
    global _cache
    if _cache is None:
        _cache = NewsroomCache()
    return _cache
