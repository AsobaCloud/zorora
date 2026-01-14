"""
Web image search tool using Brave Image Search API.
"""

import logging
import requests

logger = logging.getLogger(__name__)


def web_image_search(query: str, max_results: int = 5) -> str:
    """
    Search images using Brave Image Search API.

    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)

    Returns:
        Formatted image search results with image URLs
    """
    import config

    logger.info(f"Brave Image Search: {query[:100]}...")

    # Brave Image API endpoint
    image_endpoint = config.BRAVE_SEARCH.get("image_endpoint", "https://api.search.brave.com/res/v1/images/search")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }

    params = {
        "q": query,
        "count": min(max_results, 20),  # Max 20 for free tier
        "search_lang": "en",
        "safesearch": "moderate"
    }

    try:
        response = requests.get(
            image_endpoint,
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()

        data = response.json()
        image_results = data.get("results", [])

        if not image_results:
            return f"No images found for: {query}"

        # Format image results
        formatted = [f"Image search results for: {query} [Brave Images]\n"]

        for i, result in enumerate(image_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            thumbnail = result.get("thumbnail", {}).get("src", "") if isinstance(result.get("thumbnail"), dict) else ""
            source = result.get("source", "")

            formatted.append(f"\n{i}. {title}")
            if thumbnail:
                formatted.append(f"   Thumbnail: {thumbnail}")
            formatted.append(f"   Image URL: {url}")
            if source:
                formatted.append(f"   Source: {source}")

        return "\n".join(formatted)

    except requests.exceptions.RequestException as e:
        logger.error(f"Brave Image Search API error: {e}")
        raise
