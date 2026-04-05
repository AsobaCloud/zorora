"""Cache for newsroom articles - 90-day rolling window."""

import json
import time
import logging
from collections import Counter
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache location
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "newsroom"
CACHE_FILE = CACHE_DIR / "articles.json"
FACETS_FILE = CACHE_DIR / "facets.json"
CACHE_TTL_SECONDS = 86400  # 24 hours
ROLLING_WINDOW_DAYS = 90


def compute_facets_payload(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build topics/sources/date_range for /api/news-intel/facets (O(n) once per cache write)."""
    topic_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    dates: List[str] = []
    for article in articles:
        for tag in article.get("topic_tags") or []:
            topic_counts[tag] += 1
        src = article.get("source")
        if src:
            source_counts[src] += 1
        d = (article.get("date") or "")[:10]
        if d:
            dates.append(d)
    topics = [{"name": name, "count": count} for name, count in topic_counts.most_common()]
    sources = [{"name": name, "count": count} for name, count in source_counts.most_common()]
    date_range = {
        "min": min(dates) if dates else None,
        "max": max(dates) if dates else None,
    }
    return {"topics": topics, "sources": sources, "date_range": date_range}


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
        self.facets_file = cache_dir / "facets.json"
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
        self._save_facets_file(pruned)
        logger.info(f"Newsroom cache updated: {len(pruned)} articles (merged from {len(existing)} existing + {len(articles)} new)")

    def _save_facets_file(
        self,
        articles: List[Dict[str, Any]],
        payload: Optional[Dict[str, Any]] = None,
    ):
        """Write precomputed facets for fast GET /api/news-intel/facets."""
        pl = payload if payload is not None else compute_facets_payload(articles)
        tmp = self.facets_file.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(pl, f, indent=2)
            tmp.replace(self.facets_file)
        except OSError as e:
            logger.error(f"Failed to write newsroom facets file: {e}")

    def get_facets(self) -> Optional[Dict[str, Any]]:
        """
        Return precomputed facets if present and readable.
        Shape matches /api/news-intel/facets JSON (topics, sources, date_range).
        If articles exist on disk but facets are missing (upgrade), compute once and persist.
        """
        if self.facets_file.exists():
            try:
                with open(self.facets_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load newsroom facets file: {e}")
                data = None
            if isinstance(data, dict) and "topics" in data and "sources" in data and "date_range" in data:
                return {
                    "topics": data["topics"],
                    "sources": data["sources"],
                    "date_range": data["date_range"],
                }
        if self.cache_file.exists():
            raw = self._load_cache()
            articles = self._prune_old_articles(raw.get("articles", []))
            if articles:
                pl = compute_facets_payload(articles)
                self._save_facets_file(articles, pl)
                return pl
        return None

    def get_age_seconds(self) -> float:
        """Get cache age in seconds."""
        cache = self._load_cache()
        last_fetch = cache.get("last_fetch", 0)
        return time.time() - last_fetch

    def clear(self):
        """Clear the cache."""
        cleared = False
        if self.cache_file.exists():
            self.cache_file.unlink()
            cleared = True
        if self.facets_file.exists():
            self.facets_file.unlink()
            cleared = True
        if cleared:
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
