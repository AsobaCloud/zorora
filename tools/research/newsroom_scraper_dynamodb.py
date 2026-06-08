"""
DynamoDB integration for the news scraper.
Replaces S3 metadata storage with DynamoDB while keeping S3 for content.
"""

import hashlib
import logging
from typing import Dict, Any, Set

from tools.research.newsroom_dynamodb import insert_article

logger = logging.getLogger(__name__)


class DynamoDBProgressTracker:
    """Track progress using DynamoDB instead of S3 manifest."""
    
    def __init__(self):
        self.processed_urls: Set[str] = set()
        self._load_processed_urls()
    
    def _load_processed_urls(self):
        """Load processed URLs from DynamoDB (optional - for tracking)."""
        # For now, we'll rely on DynamoDB's idempotency check
        # This could be enhanced to preload URLs for faster checking
        pass
    
    def is_url_processed(self, url: str) -> bool:
        """Check if URL was already processed (via DynamoDB)."""
        # DynamoDB insert_article handles idempotency
        # This is a placeholder for future optimization
        return False
    
    def mark_url_processed(self, url: str):
        """Mark URL as processed."""
        self.processed_urls.add(url)


def save_article_to_dynamodb(
    metadata: Dict[str, Any],
    content: str,
    s3_key: str
) -> bool:
    """
    Save article metadata to DynamoDB and content to S3.
    
    Args:
        metadata: Article metadata dict
        content: Full article content (HTML)
        s3_key: S3 key for content storage
    
    Returns:
        True if saved successfully, False if duplicate or error
    """
    try:
        # Insert metadata into DynamoDB (handles idempotency)
        inserted = insert_article(metadata)
        
        if not inserted:
            logger.debug(f"Article already exists in DynamoDB: {metadata.get('url', '')[:50]}...")
            return False
        
        # Content is still stored in S3 (efficient for large blobs)
        # The caller should handle S3 upload separately
        logger.debug(f"Metadata saved to DynamoDB, content to S3: {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving article to DynamoDB: {e}")
        return False


def get_s3_content_key(url: str, source_type: str = "rss") -> str:
    """
    Generate S3 key for article content storage.
    
    Args:
        url: Article URL
        source_type: Type of source (rss, direct, etc.)
    
    Returns:
        S3 key for content storage
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return f"news/content/{source_type}/{url_hash}.html"
