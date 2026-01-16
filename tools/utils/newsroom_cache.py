"""Cache for newsroom articles - 7-day rolling window."""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache location
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "newsroom"
CACHE_FILE = CACHE_DIR / "articles.json"
CACHE_TTL_SECONDS = 86400  # 24 hours
ROLLING_WINDOW_DAYS = 7


class NewsroomCache:
    """
    Cache for newsroom articles with 7-day rolling window.

    - Caches articles locally to avoid repeated API calls
    - Refreshes daily (24-hour TTL) since newsroom updates ~400 articles/day
    - Prunes articles older than 7 days
    """

    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "articles.json"
        self.ttl_seconds = ttl_seconds
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return {"last_fetch": 0, "articles": []}

        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load newsroom cache: {e}")
            return {"last_fetch": 0, "articles": []}

    def _save_cache(self, data: Dict[str, Any]):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
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

    def is_fresh(self) -> bool:
        """Check if cache is fresh (within TTL)."""
        cache = self._load_cache()
        last_fetch = cache.get("last_fetch", 0)
        age = time.time() - last_fetch
        return age < self.ttl_seconds

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
        Update cache with fresh articles.

        Args:
            articles: List of article dicts from API
        """
        # Prune old articles before saving
        pruned = self._prune_old_articles(articles)

        cache = {
            "last_fetch": time.time(),
            "articles": pruned
        }
        self._save_cache(cache)
        logger.info(f"Newsroom cache updated: {len(pruned)} articles")

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
