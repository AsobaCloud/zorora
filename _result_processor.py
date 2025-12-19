"""Result processing utilities for web search: deduplication, ranking, and domain diversity."""

import logging
from typing import List, Dict, Any, Set
from urllib.parse import urlparse, parse_qs
import re

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Process, deduplicate, and rank search results."""
    
    def __init__(self, max_domain_results: int = 2):
        """
        Initialize result processor.
        
        Args:
            max_domain_results: Maximum number of results per domain
        """
        self.max_domain_results = max_domain_results
    
    def process_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Process results: deduplicate, rank, and apply domain diversity.
        
        Args:
            results: List of result dictionaries
            query: Original search query
            
        Returns:
            Processed and ranked results
        """
        if not results:
            return []
        
        # Step 1: Deduplicate by URL
        deduplicated = self._deduplicate_results(results)
        logger.debug(f"Deduplicated {len(results)} -> {len(deduplicated)} results")
        
        # Step 2: Rank by relevance
        ranked = self._rank_results(deduplicated, query)
        logger.debug(f"Ranked {len(ranked)} results")
        
        # Step 3: Apply domain diversity
        diversified = self._apply_domain_diversity(ranked)
        logger.debug(f"Applied domain diversity: {len(ranked)} -> {len(diversified)} results")
        
        return diversified
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate results by normalizing and comparing URLs.
        
        Args:
            results: List of result dictionaries
            
        Returns:
            Deduplicated list
        """
        seen_urls: Set[str] = set()
        deduplicated = []
        
        for result in results:
            url = result.get("url", "")
            if not url:
                # Keep results without URLs (shouldn't happen, but be safe)
                deduplicated.append(result)
                continue
            
            # Normalize URL
            normalized = self._normalize_url(url)
            
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                deduplicated.append(result)
            else:
                logger.debug(f"Deduplicated duplicate URL: {url[:60]}...")
        
        return deduplicated
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison (remove www, trailing slashes, fragments, etc.).
        
        Args:
            url: Original URL
            
        Returns:
            Normalized URL string
        """
        try:
            parsed = urlparse(url)
            
            # Normalize netloc (remove www.)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # Normalize path (remove trailing slash)
            path = parsed.path.rstrip("/")
            
            # Remove fragment
            # Keep query params for now (they might be meaningful)
            
            # Reconstruct normalized URL
            normalized = f"{parsed.scheme}://{netloc}{path}"
            if parsed.query:
                normalized += f"?{parsed.query}"
            
            return normalized.lower()
        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.lower()
    
    def _rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Rank results by relevance to query.
        
        Args:
            results: List of result dictionaries
            query: Original search query
            
        Returns:
            Ranked list (highest relevance first)
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        def calculate_score(result: Dict[str, Any]) -> float:
            """Calculate relevance score for a result."""
            title = result.get("title", "").lower()
            description = result.get("description", "").lower()
            url = result.get("url", "").lower()
            
            score = 0.0
            
            # Title matches are most important
            title_words = set(title.split())
            title_matches = len(query_words.intersection(title_words))
            if title_matches > 0:
                score += title_matches * 3.0  # Weight title matches heavily
            
            # Description matches
            desc_words = set(description.split())
            desc_matches = len(query_words.intersection(desc_words))
            if desc_matches > 0:
                score += desc_matches * 1.0
            
            # Exact phrase match in title (bonus)
            if query_lower in title:
                score += 5.0
            
            # Exact phrase match in description
            if query_lower in description:
                score += 2.0
            
            # URL domain match (small bonus)
            if url:
                try:
                    domain = urlparse(url).netloc.lower().replace("www.", "")
                    # Check if domain contains query words
                    for word in query_words:
                        if len(word) > 3 and word in domain:  # Only for longer words
                            score += 0.5
                            break
                except Exception:
                    pass
            
            return score
        
        # Calculate scores
        scored_results = [(result, calculate_score(result)) for result in results]
        
        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return results without scores
        return [result for result, score in scored_results]
    
    def _apply_domain_diversity(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply domain diversity: limit results per domain.
        
        Args:
            results: Ranked list of results
            
        Returns:
            Filtered list with domain diversity applied
        """
        if self.max_domain_results <= 0:
            return results  # No limit
        
        domain_counts: Dict[str, int] = {}
        diversified = []
        
        for result in results:
            url = result.get("url", "")
            if not url:
                diversified.append(result)
                continue
            
            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
            except Exception:
                # If URL parsing fails, allow it through
                diversified.append(result)
                continue
            
            # Count results from this domain
            count = domain_counts.get(domain, 0)
            
            if count < self.max_domain_results:
                domain_counts[domain] = count + 1
                diversified.append(result)
            else:
                logger.debug(f"Skipping result from {domain} (already have {self.max_domain_results} results)")
        
        return diversified
    
    def merge_results(self, result_sets: List[List[Dict[str, Any]]], query: str) -> List[Dict[str, Any]]:
        """
        Merge multiple result sets from different sources.
        
        Args:
            result_sets: List of result lists from different sources
            query: Original search query
            
        Returns:
            Merged, deduplicated, and ranked results
        """
        # Flatten all results
        all_results = []
        for results in result_sets:
            all_results.extend(results)
        
        # Process merged results
        return self.process_results(all_results, query)
