"""Content extraction utilities for web search results."""

import logging
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract and clean content from web pages."""
    
    def __init__(self, enabled: bool = False, extract_top_n: int = 2, max_content_length: int = 2000):
        """
        Initialize content extractor.
        
        Args:
            enabled: Whether content extraction is enabled
            extract_top_n: Number of top results to extract content from
            max_content_length: Maximum length of extracted content per page
        """
        self.enabled = enabled
        self.extract_top_n = extract_top_n
        self.max_content_length = max_content_length
        self._bs4_available = False
        
        # Try to import BeautifulSoup
        if enabled:
            try:
                from bs4 import BeautifulSoup  # noqa: F401
                self._bs4_available = True
                logger.info("BeautifulSoup4 available for content extraction")
            except ImportError:
                logger.warning("BeautifulSoup4 not available. Install with: pip install beautifulsoup4")
                self.enabled = False
    
    def extract_from_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Extract content from top N results.
        
        Args:
            results: List of search result dictionaries
            query: Original search query
            
        Returns:
            Results with extracted content added
        """
        if not self.enabled or not self._bs4_available:
            return results
        
        if not results:
            return results
        
        # Extract from top N results
        top_results = results[:self.extract_top_n]
        extracted_count = 0
        
        for result in top_results:
            url = result.get("url", "")
            if not url:
                continue
            
            try:
                extracted_content = self._extract_from_url(url, query)
                if extracted_content:
                    result["extracted_content"] = extracted_content
                    extracted_count += 1
                    logger.debug(f"Extracted content from {url[:60]}... ({len(extracted_content)} chars)")
            except Exception as e:
                logger.warning(f"Failed to extract content from {url}: {e}")
                continue
        
        if extracted_count > 0:
            logger.info(f"Extracted content from {extracted_count} of {len(top_results)} top results")
        
        return results
    
    def _extract_from_url(self, url: str, query: str) -> Optional[str]:
        """
        Extract main content from a URL.
        
        Args:
            url: URL to extract content from
            query: Original search query (for context)
            
        Returns:
            Extracted content string or None
        """
        import requests
        from bs4 import BeautifulSoup
        
        try:
            # Fetch page with timeout
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Try to find main content
            # Strategy 1: Look for common content selectors
            content_selectors = [
                'article',
                'main',
                '[role="main"]',
                '.content',
                '.post-content',
                '.entry-content',
                '#content',
                '#main-content'
            ]
            
            content = None
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    # Use the largest element (likely main content)
                    content = max(elements, key=lambda e: len(e.get_text()))
                    break
            
            # Strategy 2: If no specific content found, use body
            if not content:
                content = soup.find('body')
            
            if not content:
                return None
            
            # Extract text
            text = content.get_text(separator=' ', strip=True)
            
            # Clean up text
            text = self._clean_text(text)
            
            # Truncate if too long (max_content_length=0 means no limit)
            if self.max_content_length and len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "..."
            
            return text
            
        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Failed to parse {url}: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Trim
        text = text.strip()
        
        return text
    
    def fetch_content_for_sources(
        self,
        sources,
        max_sources: int = 20,
        timeout_per_url: int = 10,
        skip_types: Optional[List[str]] = None,
        max_workers: int = 8,
    ) -> int:
        """
        Fetch full article text for a list of Source objects in parallel.

        Mutates each source in-place by setting ``content_full``.

        Args:
            sources: List of Source objects (engine.models.Source).
            max_sources: Maximum number of sources to fetch.
            timeout_per_url: Per-URL request timeout in seconds.
            skip_types: Source types to skip (e.g. ["academic"]).
            max_workers: ThreadPoolExecutor worker count.

        Returns:
            Number of sources successfully fetched.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self._bs4_available:
            try:
                from bs4 import BeautifulSoup  # noqa: F401
                self._bs4_available = True
            except ImportError:
                logger.warning("BeautifulSoup4 not available — skipping content fetch")
                return 0

        skip = set(skip_types or [])

        # Filter to fetchable sources: has URL, not skipped type, no existing content_full
        fetchable = [
            s for s in sources
            if s.url
            and s.source_type not in skip
            and not getattr(s, "content_full", "")
        ]

        # Sort by credibility descending, take top N
        fetchable.sort(key=lambda s: s.credibility_score, reverse=True)
        fetchable = fetchable[:max_sources]

        if not fetchable:
            return 0

        # Save and override instance settings for full extraction
        original_max_len = self.max_content_length
        self.max_content_length = 0  # no limit

        success_count = 0

        def _fetch_one(source):
            try:
                text = self._extract_from_url(source.url, query="")
                if text and len(text) >= 50:
                    return (source, text)
            except Exception as e:
                logger.debug(f"Content fetch failed for {source.url}: {e}")
            return (source, None)

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_one, s): s for s in fetchable}
                for future in as_completed(futures):
                    try:
                        src, text = future.result(timeout=timeout_per_url + 5)
                        if text:
                            src.content_full = text
                            success_count += 1
                    except Exception as e:
                        logger.debug(f"Content fetch future error: {e}")
        finally:
            self.max_content_length = original_max_len

        logger.info(f"Fetched full content for {success_count}/{len(fetchable)} sources")
        return success_count

    def format_with_content(self, result: Dict[str, Any]) -> str:
        """
        Format a result with extracted content.
        
        Args:
            result: Result dictionary with optional extracted_content
            
        Returns:
            Formatted string with content
        """
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "No description")
        extracted = result.get("extracted_content", "")
        
        formatted = f"{title}\nURL: {url}\n{description}"
        
        if extracted:
            formatted += f"\n\n[Extracted Content]\n{extracted}"
        
        return formatted
