"""
DynamoDB client for newsroom article operations.
Replaces S3-based metadata storage with indexed DynamoDB queries.
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import Counter

try:
    import boto3
    from boto3.dynamodb.conditions import Key, Attr
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    ClientError = Exception

logger = logging.getLogger(__name__)

TABLE_NAME = "newsroom_articles"
MAX_FULL_CONTENT_BYTES = 380 * 1024


def _get_dynamodb():
    """Get DynamoDB resource."""
    if not HAS_BOTO3:
        raise RuntimeError("boto3 not installed, cannot access DynamoDB")
    return boto3.resource('dynamodb', region_name='us-east-1')


def _get_dynamodb_client():
    """Get DynamoDB client."""
    if not HAS_BOTO3:
        raise RuntimeError("boto3 not installed, cannot access DynamoDB")
    return boto3.client('dynamodb', region_name='us-east-1')


def _url_hash(url: str) -> str:
    """Generate MD5 hash of URL for deduplication."""
    return hashlib.md5(url.encode()).hexdigest()


def _parse_date_to_sort_key(date_str: str) -> str:
    """Parse date string to sortable format."""
    if not date_str:
        return "DATE#0000-00-00"
    
    # Try to parse and normalize
    try:
        from dateutil import parser
        parsed = parser.parse(date_str)
        return f"DATE#{parsed.strftime('%Y-%m-%d')}"
    except (ValueError, TypeError):
        # Return as-is if parsing fails
        return f"DATE#{date_str[:10]}" if len(date_str) >= 10 else "DATE#0000-00-00"


def _parse_timestamp(date_str: str) -> str:
    """Parse date string to timestamp for sorting."""
    if not date_str:
        return "PUB#0"
    
    try:
        from dateutil import parser
        parsed = parser.parse(date_str)
        timestamp = int(parsed.timestamp())
        return f"PUB#{timestamp}"
    except (ValueError, TypeError):
        return "PUB#0"


def _truncate_utf8(text: str, max_bytes: int) -> str:
    text = text or ""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def insert_article(metadata: Dict[str, Any]) -> bool:
    """
    Insert an article into DynamoDB.
    
    Args:
        metadata: Article metadata dict with keys:
            - url (required)
            - title
            - source
            - pub_date
            - collection_date
            - content_length
            - tags (dict with core_topics, special_tags, matched_keywords, continents, countries)
            - feed_url (optional)
            - base_url (optional)
    
    Returns:
        True if inserted, False if already exists or error
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return False
    
    try:
        table = _get_dynamodb().Table(TABLE_NAME)
        
        url = metadata.get('url', '')
        if not url:
            logger.warning("Article missing URL, skipping")
            return False
        
        url_hash = _url_hash(url)
        pub_date = metadata.get('pub_date', metadata.get('date', ''))
        collection_date = metadata.get('collection_date', datetime.now().isoformat())
        
        tags = metadata.get('tags', {})
        core_topics = tags.get('core_topics', [])
        special_tags = tags.get('special_tags', [])
        matched_keywords = tags.get('matched_keywords', [])
        continents = tags.get('continents', [])
        countries = tags.get('countries', [])
        full_content = _truncate_utf8(
            metadata.get('full_content', ''),
            MAX_FULL_CONTENT_BYTES,
        )
        content_length = metadata.get('content_length', 0)
        if metadata.get('full_content'):
            content_length = len(full_content)
        
        # Build item
        item = {
            'PK': f"ARTICLE#{url_hash}",
            'SK': _parse_date_to_sort_key(pub_date),
            'url': url,
            'title': metadata.get('title', ''),
            'source': metadata.get('source', 'Unknown'),
            'pub_date': pub_date,
            'collection_date': collection_date,
            'content_length': content_length,
            'core_topics': core_topics,
            'special_tags': special_tags,
            'matched_keywords': matched_keywords,
            'continents': continents,
            'countries': countries,
            
            # Content fields
            'description': metadata.get('description', ''),
            'full_content': full_content,
            
            # GSI keys
            'date_key': _parse_date_to_sort_key(pub_date),
            'pub_timestamp': _parse_timestamp(pub_date),
            'collection_key': f"COLLECTED#{collection_date[:10]}",
        }
        
        # Add source GSI key
        source = metadata.get('source', 'Unknown')
        item['source_key'] = f"SOURCE#{source}"
        
        # Add topic GSI keys (one per topic for multi-topic articles)
        if core_topics:
            item['topic_key'] = f"TOPIC#{core_topics[0]}"  # Primary topic
        
        # Optional fields
        if 'feed_url' in metadata:
            item['feed_url'] = metadata['feed_url']
        if 'base_url' in metadata:
            item['base_url'] = metadata['base_url']
        
        try:
            table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(PK) AND attribute_not_exists(SK)',
            )
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                logger.debug(f"Article already exists: {url[:50]}...")
                return False
            raise
        logger.debug(f"Inserted article: {url[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error inserting article: {e}")
        return False


def fetch_articles_by_date_range(
    date_from: str,
    date_to: str,
    limit: int = 500,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch articles by date range using date-index GSI.
    
    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Maximum articles to return
    
    Returns:
        List of article dicts
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table = _get_dynamodb().Table(TABLE_NAME)
        
        # Scan with filter for date range (date-index doesn't support range queries on partition key)
        response = table.scan(
            FilterExpression=Attr('date_key').between(
                f"DATE#{date_from}",
                f"DATE#{date_to}"
            ),
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        logger.info(f"Fetched {len(articles)} articles from {date_from} to {date_to}")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching articles by date range: {e}")
        return []


def fetch_articles_by_topic(
    topic: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch articles by topic using topic-index GSI.
    
    Args:
        topic: Topic name
        date_from: Optional start date filter
        date_to: Optional end date filter
        limit: Maximum articles to return
    
    Returns:
        List of article dicts
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table = _get_dynamodb().Table(TABLE_NAME)
        
        key_condition = Key('topic_key').eq(f"TOPIC#{topic}")
        
        response = table.query(
            IndexName='topic-index',
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            # Apply date filters if specified
            if date_from or date_to:
                pub_date = item.get('pub_date', '')
                if pub_date:
                    try:
                        from dateutil import parser
                        parsed = parser.parse(pub_date)
                        iso_date = parsed.strftime('%Y-%m-%d')
                        
                        if date_from and iso_date < date_from:
                            continue
                        if date_to and iso_date > date_to:
                            continue
                    except Exception:
                        pass
            
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        logger.info(f"Fetched {len(articles)} articles for topic: {topic}")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching articles by topic: {e}")
        return []


def fetch_articles_by_source(
    source: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch articles by source using source-index GSI.
    
    Args:
        source: Source name
        date_from: Optional start date filter
        date_to: Optional end date filter
        limit: Maximum articles to return
    
    Returns:
        List of article dicts
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table = _get_dynamodb().Table(TABLE_NAME)
        
        response = table.query(
            IndexName='source-index',
            KeyConditionExpression=Key('source_key').eq(f"SOURCE#{source}"),
            ScanIndexForward=False,
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            # Apply date filters if specified
            if date_from or date_to:
                pub_date = item.get('pub_date', '')
                if pub_date:
                    try:
                        from dateutil import parser
                        parsed = parser.parse(pub_date)
                        iso_date = parsed.strftime('%Y-%m-%d')
                        
                        if date_from and iso_date < date_from:
                            continue
                        if date_to and iso_date > date_to:
                            continue
                    except Exception:
                        pass
            
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        logger.info(f"Fetched {len(articles)} articles for source: {source}")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching articles by source: {e}")
        return []


def fetch_recent_articles(
    days_back: int = 7,
    limit: int = 500,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch recent articles using collection-date-index GSI.
    
    Args:
        days_back: Number of days to look back
        limit: Maximum articles to return
    
    Returns:
        List of article dicts
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        from datetime import timedelta
        
        table = _get_dynamodb().Table(TABLE_NAME)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        start_key = f"COLLECTED#{start_date.strftime('%Y-%m-%d')}"
        end_key = f"COLLECTED#{end_date.strftime('%Y-%m-%d')}"
        
        response = table.query(
            IndexName='collection-date-index',
            KeyConditionExpression=Key('collection_key').between(start_key, end_key),
            ScanIndexForward=False,
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        logger.info(f"Fetched {len(articles)} articles from last {days_back} days")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching recent articles: {e}")
        return []


def generate_facets(days_back: int = 90) -> Dict[str, Any]:
    """
    Generate facets (topic distribution, sources, date range) for UI.
    
    Args:
        days_back: Number of days to analyze
    
    Returns:
        Dict with topics, sources, and date_range
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return {"topics": [], "sources": [], "date_range": {}}
    
    try:
        from datetime import timedelta
        
        table = _get_dynamodb().Table(TABLE_NAME)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        start_key = f"COLLECTED#{start_date.strftime('%Y-%m-%d')}"
        end_key = f"COLLECTED#{end_date.strftime('%Y-%m-%d')}"
        
        # Scan with projection to get only needed attributes
        response = table.scan(
            FilterExpression=Attr('collection_key').between(start_key, end_key),
            ProjectionExpression='#topics, #src, #date',
            ExpressionAttributeNames={
                '#topics': 'core_topics',
                '#src': 'source',
                '#date': 'pub_date'
            },
            Limit=10000
        )
        
        # Count topics
        topic_counter = Counter()
        source_counter = Counter()
        dates = []
        
        for item in response.get('Items', []):
            # Count topics
            for topic in item.get('core_topics', []):
                topic_counter[topic] += 1
            
            # Count sources
            source = item.get('source', 'Unknown')
            source_counter[source] += 1
            
            # Collect dates
            pub_date = item.get('pub_date', '')
            if pub_date:
                try:
                    from dateutil import parser
                    parsed = parser.parse(pub_date)
                    dates.append(parsed.strftime('%Y-%m-%d'))
                except Exception:
                    pass
        
        # Build topic list
        topics = [
            {"name": topic, "count": count}
            for topic, count in topic_counter.most_common()
        ]
        
        # Build source list
        sources = [
            {"name": source, "count": count}
            for source, count in source_counter.most_common()
        ]
        
        # Build date range
        date_range = {}
        if dates:
            date_range = {
                "min": min(dates),
                "max": max(dates)
            }
        
        logger.info(f"Generated facets: {len(topics)} topics, {len(sources)} sources")
        return {
            "topics": topics,
            "sources": sources,
            "date_range": date_range
        }
        
    except Exception as e:
        logger.error(f"Error generating facets: {e}")
        return {"topics": [], "sources": [], "date_range": {}}


def _dynamodb_item_to_dict(item: Dict[str, Any], include_content: bool = False) -> Dict[str, Any]:
    """Convert DynamoDB item to article dict format."""
    article = {
        "headline": item.get('title', ''),
        "date": item.get('pub_date', ''),
        "topic_tags": item.get('core_topics', []),
        "geography_tags": item.get('continents', []),
        "country_tags": item.get('countries', []),
        "url": item.get('url', ''),
        "source": item.get('source', 'Unknown'),
    }
    if include_content:
        article["description"] = item.get('description', '')
        article["full_content"] = item.get('full_content', '')
    return article


def hydrate_articles_with_content(
    articles: List[Dict[str, Any]],
    max_articles: Optional[int] = 20,
) -> List[Dict[str, Any]]:
    if not articles or not HAS_BOTO3:
        return list(articles)

    try:
        table = _get_dynamodb().Table(TABLE_NAME)
    except Exception as e:
        logger.error(f"Error accessing DynamoDB for article hydration: {e}")
        return list(articles)

    hydrated = []
    for idx, article in enumerate(articles):
        enriched = dict(article)
        if (
            (max_articles is not None and idx >= max_articles)
            or enriched.get("full_content")
            or enriched.get("description")
        ):
            hydrated.append(enriched)
            continue

        url = enriched.get("url", "")
        article_date = enriched.get("date") or enriched.get("pub_date", "")
        if not url:
            hydrated.append(enriched)
            continue

        item = None
        try:
            pk = f"ARTICLE#{_url_hash(url)}"
            if article_date:
                response = table.get_item(
                    Key={"PK": pk, "SK": _parse_date_to_sort_key(article_date)}
                )
                item = response.get("Item")
            if item is None:
                response = table.query(
                    KeyConditionExpression=Key("PK").eq(pk),
                    ScanIndexForward=False,
                    Limit=1,
                )
                items = response.get("Items", [])
                item = items[0] if items else None
        except Exception as e:
            logger.debug(f"Error hydrating article content for {url[:50]}...: {e}")

        if item:
            enriched["description"] = item.get("description", enriched.get("description", ""))
            enriched["full_content"] = item.get("full_content", enriched.get("full_content", ""))
        hydrated.append(enriched)

    return hydrated


def fetch_newsroom_dynamodb_raw(
    days_back: int = 90,
    max_results: int = 10000,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch newsroom articles from DynamoDB (replaces S3 fetch).
    
    Args:
        days_back: Number of days to fetch
        max_results: Maximum articles to return
    
    Returns:
        List of article dictionaries
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        from datetime import timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        date_from = start_date.strftime('%Y-%m-%d')
        date_to = end_date.strftime('%Y-%m-%d')
        
        # Fetch by date range
        articles = fetch_articles_by_date_range(
            date_from=date_from,
            date_to=date_to,
            limit=max_results,
            include_content=include_content,
        )
        
        logger.info(f"Total articles from DynamoDB: {len(articles)}")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching from DynamoDB: {e}")
        return []
