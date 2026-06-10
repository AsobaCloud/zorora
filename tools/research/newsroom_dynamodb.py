"""
DynamoDB client for newsroom article operations.
Replaces S3-based metadata storage with indexed DynamoDB queries.
Strict adherence to docs/INGESTION_CONTRACT.md.
"""

import os
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
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.resource('dynamodb', region_name=region)


def _get_dynamodb_client():
    """Get DynamoDB client."""
    if not HAS_BOTO3:
        raise RuntimeError("boto3 not installed, cannot access DynamoDB")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client('dynamodb', region_name=region)


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
    Insert an article into DynamoDB using the production single-table schema.
    Strictly follows docs/INGESTION_CONTRACT.md.
    
    Args:
        metadata: Article metadata dict with keys:
            - url (required)
            - title
            - source
            - pub_date
            - collection_date
            - full_content
            - tags (dict with core_topics, continents, countries, special_tags)
    
    Returns:
        True if inserted, False if already exists or error
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return False
    
    try:
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        url = metadata.get('url', '')
        if not url:
            logger.warning("Article missing URL, skipping")
            return False
        
        # Primary Keys
        url_hash = _url_hash(url)
        pk = f"ARTICLE#{url_hash}"
        
        pub_date_raw = metadata.get('pub_date', metadata.get('date', ''))
        sk = _parse_date_to_sort_key(pub_date_raw)
        
        # GSI Attributes
        date_key = sk
        pub_timestamp = _parse_timestamp(pub_date_raw)
        
        collection_date_raw = metadata.get('collection_date', datetime.now().isoformat())
        collection_key = f"COLLECTED#{collection_date_raw[:10]}"
        
        source = metadata.get('source', 'Unknown')
        source_key = f"SOURCE#{source}"
        
        tags = metadata.get('tags', {})
        core_topics = tags.get('core_topics', [])
        special_tags = tags.get('special_tags', [])
        continents = tags.get('continents', [])
        countries = tags.get('countries', [])
        
        # topic_key logic: priority to special tags (e.g. legislation), then first core topic
        topic_key = None
        if 'legislation' in special_tags:
            topic_key = "TOPIC#legislation"
        elif 'economy_politics' in special_tags:
            topic_key = "TOPIC#economy_politics"
        elif core_topics:
            topic_key = f"TOPIC#{core_topics[0]}"
        
        full_content = metadata.get('full_content', '')
        content_length = len(full_content.encode('utf-8')) if full_content else 0
        
        # Handle content overflow to S3
        s3_overflow_key = None
        if content_length > MAX_FULL_CONTENT_BYTES:
            try:
                region = os.environ.get("AWS_REGION", "us-east-1")
                s3_client = boto3.client('s3', region_name=region)
                content_hash = hashlib.md5(full_content.encode()).hexdigest()
                s3_overflow_key = f"content/overflow/{content_hash}.html"
                
                s3_client.put_object(
                    Bucket="news-collection-website",
                    Key=s3_overflow_key,
                    Body=full_content.encode('utf-8'),
                    ContentType='text/html'
                )
                
                # Truncate for DynamoDB
                full_content = _truncate_utf8(full_content, MAX_FULL_CONTENT_BYTES)
                logger.info(f"Content overflow to S3: {s3_overflow_key}")
            except Exception as e:
                logger.error(f"Failed to upload overflow to S3: {e}")
                # Continue with truncated content
        
        # Build item using production schema
        item = {
            'PK': pk,
            'SK': sk,
            'url': url,
            'title': metadata.get('title', ''),
            'source': source,
            'source_key': source_key,
            'pub_date': pub_date_raw,
            'date_key': date_key,
            'pub_timestamp': pub_timestamp,
            'collection_date': collection_date_raw,
            'collection_key': collection_key,
            'content_length': content_length,
            'core_topics': core_topics,
            'special_tags': special_tags,
            'continents': continents,
            'countries': countries,
            
            # Content fields
            'description': metadata.get('description', ''),
            'full_content': full_content,
        }
        
        if topic_key:
            item['topic_key'] = topic_key
        
        # Add S3 overflow key if content was too large
        if s3_overflow_key:
            item['s3_overflow_key'] = s3_overflow_key
        
        # Add optional fields
        if 'feed_url' in metadata:
            item['feed_url'] = metadata['feed_url']
        if 'base_url' in metadata:
            item['base_url'] = metadata['base_url']
        
        try:
            table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(PK)',
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
    Uses efficient queries per date instead of a scan to avoid throttling.
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        # Calculate all dates in the range
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(date_from, '%Y-%m-%d')
        end_dt = datetime.strptime(date_to, '%Y-%m-%d')
        
        delta = end_dt - start_dt
        dates_to_query = []
        for i in range(delta.days + 1):
            day = start_dt + timedelta(days=i)
            dates_to_query.append(day.strftime('%Y-%m-%d'))
        
        # Query each date (newest first)
        articles = []
        for date_str in reversed(dates_to_query):
            if len(articles) >= limit:
                break
                
            response = table.query(
                IndexName='date-index',
                KeyConditionExpression=Key('date_key').eq(f"DATE#{date_str}"),
                ScanIndexForward=False, # Newest first within the date
                Limit=limit - len(articles)
            )
            
            for item in response.get('Items', []):
                articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        logger.info(f"Fetched {len(articles)} articles across {len(dates_to_query)} days")
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
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        key_condition = Key('topic_key').eq(f"TOPIC#{topic}")
        if date_from and date_to:
            key_condition &= Key('SK').between(f"DATE#{date_from}", f"DATE#{date_to}")
        elif date_from:
            key_condition &= Key('SK').gte(f"DATE#{date_from}")
        
        response = table.query(
            IndexName='topic-index',
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
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
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        key_condition = Key('source_key').eq(f"SOURCE#{source}")
        if date_from and date_to:
            key_condition &= Key('SK').between(f"DATE#{date_from}", f"DATE#{date_to}")
        
        response = table.query(
            IndexName='source-index',
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
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
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return []
    
    try:
        from datetime import timedelta
        
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        start_key = f"COLLECTED#{start_date.strftime('%Y-%m-%d')}"
        end_key = f"COLLECTED#{end_date.strftime('%Y-%m-%d')}"
        
        # This is a scan across collection_key values in the index
        response = table.scan(
            IndexName='collection-date-index',
            FilterExpression=Attr('collection_key').between(start_key, end_key),
            Limit=limit
        )
        
        articles = []
        for item in response.get('Items', []):
            articles.append(_dynamodb_item_to_dict(item, include_content=include_content))
        
        articles.sort(key=lambda x: x.get('date', ''), reverse=True)
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching recent articles: {e}")
        return []


def generate_facets(days_back: int = 90) -> Dict[str, Any]:
    """
    Generate facets for UI.
    """
    if not HAS_BOTO3:
        logger.error("boto3 not available")
        return {"topics": [], "sources": [], "date_range": {}}
    
    try:
        from datetime import timedelta
        
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        start_key = f"COLLECTED#{start_date.strftime('%Y-%m-%d')}"
        end_key = f"COLLECTED#{end_date.strftime('%Y-%m-%d')}"
        
        response = table.scan(
            FilterExpression=Attr('collection_key').between(start_key, end_key),
            ProjectionExpression='core_topics, #src, pub_date',
            ExpressionAttributeNames={
                '#src': 'source'
            },
            Limit=10000
        )
        
        topic_counter = Counter()
        source_counter = Counter()
        dates = []
        
        for item in response.get('Items', []):
            for topic in item.get('core_topics', []):
                topic_counter[topic] += 1
            source = item.get('source', 'Unknown')
            source_counter[source] += 1
            pub_date = item.get('pub_date', '')
            if pub_date:
                dates.append(pub_date[:10])
        
        topics = [{"name": topic, "count": count} for topic, count in topic_counter.most_common()]
        sources = [{"name": source, "count": count} for source, count in source_counter.most_common()]
        date_range = {"min": min(dates), "max": max(dates)} if dates else {}
        
        return {"topics": topics, "sources": sources, "date_range": date_range}
        
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
        "special_tags": item.get('special_tags', []),
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
        table_name = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
        table = _get_dynamodb().Table(table_name)
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
        
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching from DynamoDB: {e}")
        return []
