"""
Migration script to backfill description and full_content fields for existing articles.
This script reads from the S3 export and updates DynamoDB articles missing these fields.
"""

import boto3
import json
import logging
from typing import Dict, Any, List
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

S3_BUCKET = "news-collection-website"
S3_KEY = "zorora-export/articles.json"
DYNAMODB_TABLE = "newsroom_articles"
REGION = "us-east-1"


def fetch_s3_export() -> List[Dict[str, Any]]:
    """Fetch the newsroom export from S3."""
    try:
        s3 = boto3.client('s3', region_name='af-south-1')
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        content = response['Body'].read().decode('utf-8')
        articles = json.loads(content)
        logger.info(f"Fetched {len(articles)} articles from S3 export")
        return articles
    except Exception as e:
        logger.error(f"Error fetching S3 export: {e}")
        return []


def get_dynamodb_table():
    """Get DynamoDB table resource."""
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    return dynamodb.Table(DYNAMODB_TABLE)


def article_needs_migration(item: Dict[str, Any]) -> bool:
    """Check if an article needs migration (missing description or full_content)."""
    return 'description' not in item or 'full_content' not in item


def migrate_article(table, url: str, s3_articles: List[Dict[str, Any]]) -> bool:
    """
    Migrate a single article by finding its content in the S3 export.
    
    Args:
        table: DynamoDB table
        url: Article URL
        s3_articles: List of articles from S3 export
    
    Returns:
        True if migrated, False otherwise
    """
    # Find article in S3 export by URL
    s3_article = None
    for article in s3_articles:
        if article.get('url') == url:
            s3_article = article
            break
    
    if not s3_article:
        logger.warning(f"Article not found in S3 export: {url[:50]}...")
        return False
    
    # Get article's PK and SK from DynamoDB
    try:
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # Need to find the SK - we'll query by PK
        response = table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={':pk': f"ARTICLE#{url_hash}"}
        )
        
        if not response.get('Items'):
            logger.warning(f"Article not found in DynamoDB: {url[:50]}...")
            return False
        
        item = response['Items'][0]
        pk = item['PK']
        sk = item['SK']
        
        # Check if already has content
        if 'description' in item and 'full_content' in item:
            if item.get('description') or item.get('full_content'):
                return False  # Already migrated
        
        # Update with content from S3
        description = s3_article.get('description', '')
        full_content = s3_article.get('full_content', '')
        
        if not description and not full_content:
            logger.warning(f"No content in S3 export for: {url[:50]}...")
            return False
        
        # Update DynamoDB
        table.update_item(
            Key={'PK': pk, 'SK': sk},
            UpdateExpression='SET description = :desc, full_content = :content',
            ExpressionAttributeValues={
                ':desc': description,
                ':content': full_content
            }
        )
        
        logger.info(f"Migrated: {url[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error migrating article {url[:50]}...: {e}")
        return False


def main():
    """Main migration function."""
    logger.info("Starting migration for description and full_content fields...")
    
    # Fetch S3 export
    s3_articles = fetch_s3_export()
    if not s3_articles:
        logger.error("No articles found in S3 export, aborting")
        return
    
    # Get DynamoDB table
    table = get_dynamodb_table()
    
    # Scan DynamoDB for articles needing migration
    logger.info("Scanning DynamoDB for articles needing migration...")
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    # Scan in batches to avoid throttling
    scan_kwargs = {}
    done = False
    start_key = None
    
    with tqdm(total=0, desc="Migrating articles") as pbar:
        while not done:
            if start_key:
                scan_kwargs['ExclusiveStartKey'] = start_key
            
            try:
                response = table.scan(**scan_kwargs, ProjectionExpression='PK,SK,url,description,full_content')
            except Exception as e:
                logger.error(f"Error scanning table: {e}")
                # Wait and retry
                import time
                time.sleep(5)
                continue
            
            items = response.get('Items', [])
            
            # Update progress bar total estimate
            if pbar.total == 0 and response.get('ScannedCount'):
                pbar.total = response.get('ScannedCount')
            
            for item in items:
                url = item.get('url', '')
                if not url:
                    continue
                
                # Check if needs migration
                if article_needs_migration(item):
                    if migrate_article(table, url, s3_articles):
                        migrated_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
                
                pbar.update(1)
            
            start_key = response.get('LastEvaluatedKey')
            done = start_key is None
    
    logger.info(f"Migration complete: {migrated_count} migrated, {skipped_count} skipped, {error_count} errors")


if __name__ == '__main__':
    main()
