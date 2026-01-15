"""Newsroom search tool - fetches articles from Asoba newsroom API."""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import config

logger = logging.getLogger(__name__)

# Newsroom API endpoint (production)
NEWSROOM_API_URL = "https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles"
NEWSROOM_API_TIMEOUT = 10

# Error messages for common issues
AUTH_ERROR_MSG = """⚠ Newsroom authentication failed (HTTP 401)

To access the newsroom, you need a valid JWT token:
1. Set NEWSROOM_JWT_TOKEN in config.py or as environment variable
2. Get the token from Ona platform authentication (data-admin portal)
3. Token format: Bearer <jwt_token>

See docs/TROUBLESHOOTING.md for details."""

FORBIDDEN_ERROR_MSG = """⚠ Newsroom access forbidden (HTTP 403)

Your JWT token is valid but lacks permission to access newsroom articles.
Contact the Ona platform admin to request newsroom access."""


def _get_auth_headers() -> Dict[str, str]:
    """Get authorization headers for newsroom API."""
    import os

    # Check config first, then environment variable
    jwt_token = getattr(config, 'NEWSROOM_JWT_TOKEN', None) or os.environ.get('NEWSROOM_JWT_TOKEN')

    if jwt_token:
        # Support both "Bearer xxx" and raw token formats
        if not jwt_token.startswith('Bearer '):
            jwt_token = f'Bearer {jwt_token}'
        return {'Authorization': jwt_token}

    return {}


def fetch_newsroom_api(query: str = None, days_back: int = 90, max_results: int = 25) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles via API and return structured data.

    This function returns structured data (List[Dict]) for use in deep research.
    The data will be converted to Source objects in Phase 3.

    Requires NEWSROOM_JWT_TOKEN in config.py or environment variable.

    Args:
        query: Search query (optional)
        days_back: Number of days to search back (default: 90)
        max_results: Max results to return (default: 25)

    Returns:
        List of article dictionaries with keys: headline, date, url, source, topic_tags, etc.
        Returns empty list on error, with specific logging for auth failures.
    """
    try:
        # Calculate date range
        date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        # Get auth headers
        headers = _get_auth_headers()
        if not headers:
            logger.warning("No NEWSROOM_JWT_TOKEN configured - newsroom will be unavailable")

        # Call newsroom API
        response = requests.get(
            NEWSROOM_API_URL,
            params={
                'search': query,
                'limit': max_results,
                'date_from': date_from
            },
            headers=headers,
            timeout=NEWSROOM_API_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])

            logger.info(f"✓ Newsroom: {len(articles)} articles (<500ms)")
            return articles
        elif response.status_code == 401:
            logger.error("Newsroom API returned 401 Unauthorized - check NEWSROOM_JWT_TOKEN")
            return []
        elif response.status_code == 403:
            logger.error("Newsroom API returned 403 Forbidden - token lacks newsroom access")
            return []
        else:
            logger.warning(f"Newsroom API returned {response.status_code}")
            return []

    except Exception as e:
        logger.warning(f"Newsroom API error: {e}")
        return []


def get_newsroom_headlines(query: str = None, days_back: int = None, max_results: int = None) -> str:
    """
    Fetch newsroom articles via API and return formatted string for REPL display.
    
    This function maintains backward compatibility with existing REPL commands.
    It calls fetch_newsroom_api() and formats the results as a string.
    
    Args:
        query: Search query to filter articles by relevance (optional)
        days_back: Number of days to search back (default from config)
        max_results: Max relevant articles to return (default from config)
        
    Returns:
        Formatted string with article headlines, sources, and URLs
    """
    # Get configuration
    if days_back is None:
        days_back = getattr(config, 'NEWSROOM_DAYS_BACK', 90)
    if max_results is None:
        max_results = getattr(config, 'NEWSROOM_MAX_RELEVANT', 25)
    
    try:
        # Check if authentication is configured
        headers = _get_auth_headers()
        if not headers:
            return AUTH_ERROR_MSG

        # Fetch articles from API
        articles = fetch_newsroom_api(query, days_back, max_results)

        if not articles:
            # Could be auth failure or genuinely no articles - check logs for details
            return f"No articles found in newsroom for last {days_back} days (check logs if unexpected)"
        
        logger.info(f"Processing {len(articles)} articles from newsroom API")
        
        # Convert API articles to headline format (for compatibility with existing code)
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
        
        # Filter by relevance if query provided (simplified - just keyword matching)
        if query:
            query_lower = query.lower()
            filtered = []
            for h in headlines:
                title_lower = h['title'].lower()
                # Simple keyword matching
                if any(word in title_lower for word in query_lower.split() if len(word) > 3):
                    filtered.append(h)
            headlines = filtered[:max_results]
            logger.info(f"Filtered to {len(headlines)} most relevant articles for query: {query[:60]}...")
        else:
            # No query - return most recent articles up to max_results
            headlines = sorted(headlines, key=lambda x: x.get('date', ''), reverse=True)[:max_results]
            logger.info(f"No query provided - returning {len(headlines)} most recent articles")
        
        if not headlines:
            return f"No articles found in newsroom for last {days_back} days"
        
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
