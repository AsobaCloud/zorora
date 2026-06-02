"""Replacement for fetch_newsroom_api using S3 export instead of API."""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# S3 export URL - single file with all articles, updated hourly by Lambda
NEWSROOM_EXPORT_URL = "https://news-collection-website.s3.af-south-1.amazonaws.com/zorora-export/articles.json"

STOP_WORDS = frozenset({
    'why', 'did', 'does', 'how', 'what', 'when', 'where', 'who',
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'or', 'is', 'was', 'were', 'are', 'been', 'be', 'has', 'had',
    'do', 'with', 'from', 'about', 'that', 'this', 'it', 'not',
})


def _extract_keywords(query: str) -> List[str]:
    """Extract substantive keywords from a query, removing stop words."""
    return [w for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def _fetch_newsroom_export() -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles from S3 export file.
    
    Single HTTP request, returns all ~3000 articles in 2-3 seconds.
    No authentication required.
    
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
        
        logger.info(f"✓ Newsroom S3 export: {len(valid_articles)} articles")
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
