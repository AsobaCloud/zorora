"""Caching system for web search queries."""

import hashlib
import time
import logging
from typing import Optional, Dict, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)


class SearchCache:
    """LRU cache for web search results."""
    
    def __init__(self, max_entries: int = 100, default_ttl_hours: int = 1, stable_ttl_hours: int = 24):
        """
        Initialize search cache.
        
        Args:
            max_entries: Maximum number of cached entries
            default_ttl_hours: TTL for general queries (hours)
            stable_ttl_hours: TTL for stable queries like documentation (hours)
        """
        self.max_entries = max_entries
        self.default_ttl = default_ttl_hours * 3600  # Convert to seconds
        self.stable_ttl = stable_ttl_hours * 3600
        
        # Use OrderedDict for LRU behavior
        self._cache: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        
        # Stable query patterns (documentation, reference materials)
        self._stable_patterns = [
            'documentation', 'docs', 'reference', 'api', 'guide', 'tutorial',
            'python', 'javascript', 'react', 'django', 'flask', 'nodejs'
        ]
    
    def _make_key(self, query: str, max_results: int) -> str:
        """Create cache key from query and max_results."""
        # Normalize query: lowercase, strip, remove extra spaces
        normalized = ' '.join(query.lower().strip().split())
        key_string = f"{normalized}:{max_results}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _is_stable_query(self, query: str) -> bool:
        """Check if query is for stable/reference content."""
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in self._stable_patterns)
    
    def get(self, query: str, max_results: int) -> Optional[str]:
        """
        Get cached result if available and not expired.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            Cached result string or None if not found/expired
        """
        key = self._make_key(query, max_results)
        
        if key not in self._cache:
            return None
        
        result, timestamp = self._cache[key]
        
        # Determine TTL based on query type
        ttl = self.stable_ttl if self._is_stable_query(query) else self.default_ttl
        
        # Check if expired
        if time.time() - timestamp > ttl:
            # Remove expired entry
            del self._cache[key]
            logger.debug(f"Cache expired for query: {query[:50]}...")
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit for query: {query[:50]}...")
        return result
    
    def set(self, query: str, max_results: int, result: str) -> None:
        """
        Cache a search result.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            result: Search result string to cache
        """
        key = self._make_key(query, max_results)
        timestamp = time.time()
        
        # Remove if already exists (will be re-added at end)
        if key in self._cache:
            del self._cache[key]
        
        # Add new entry
        self._cache[key] = (result, timestamp)
        
        # Evict oldest if cache is full
        if len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)  # Remove oldest (first item)
            logger.debug(f"Cache evicted oldest entry (cache full: {self.max_entries} entries)")
        
        logger.debug(f"Cached result for query: {query[:50]}... (cache size: {len(self._cache)})")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("Search cache cleared")
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_entries": self.max_entries,
            "usage_percent": int((len(self._cache) / self.max_entries) * 100) if self.max_entries > 0 else 0
        }
