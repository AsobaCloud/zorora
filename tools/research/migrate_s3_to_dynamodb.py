"""
Migrate existing S3 metadata files to DynamoDB.
Scans all S3 metadata files and inserts them into the DynamoDB table.
"""

import boto3
import json
import logging
from datetime import datetime
from typing import Set, List, Dict
import os
import time

from tools.research.newsroom_dynamodb import _parse_date_to_sort_key, _url_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

S3_BUCKET_NAME = "news-collection-website"
S3_PREFIX = "news/"
TABLE_NAME = "newsroom_articles"
CHECKPOINT_FILE = "/tmp/migration_checkpoint.txt"
MAX_FULL_CONTENT_BYTES = 380 * 1024


def load_checkpoint() -> Set[str]:
    """Load processed URLs from checkpoint file."""
    if not os.path.exists(CHECKPOINT_FILE):
        return set()
    
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        logger.warning(f"Could not load checkpoint: {e}")
        return set()


def save_checkpoint(url: str):
    """Append URL to checkpoint file."""
    try:
        with open(CHECKPOINT_FILE, 'a') as f:
            f.write(url + '\n')
    except Exception as e:
        logger.error(f"Could not save checkpoint: {e}")


def truncate_content(content: str) -> str:
    """Truncate content to fit within DynamoDB item size limit."""
    if len(content.encode('utf-8')) <= MAX_FULL_CONTENT_BYTES:
        return content
    # Truncate to fit within limit (with some buffer for other fields)
    target_bytes = MAX_FULL_CONTENT_BYTES - 1024
    truncated = content.encode('utf-8')[:target_bytes].decode('utf-8', errors='ignore')
    logger.warning(f"Truncated content from {len(content)} to {len(truncated)} chars")
    return truncated


def execute_update_batch(updates: List[Dict[str, str]]) -> tuple[int, int, List[str]]:
    if not updates:
        return 0, 0, []

    statements = [
        {
            'Statement': f'UPDATE "{TABLE_NAME}" SET description=?, full_content=? WHERE PK=? AND SK=?',
            'Parameters': [
                {'S': update['description']},
                {'S': update['full_content']},
                {'S': update['pk']},
                {'S': update['sk']},
            ],
        }
        for update in updates
    ]

    for attempt in range(3):
        try:
            client = boto3.client('dynamodb', region_name='us-east-1')
            response = client.batch_execute_statement(Statements=statements)
            responses = response.get('Responses', [])
            successful_urls = []
            errors = 0

            for update, item_response in zip(updates, responses):
                if 'Error' in item_response:
                    logger.error(f"Batch update failed for {update['url'][:50]}...: {item_response['Error']}")
                    errors += 1
                else:
                    save_checkpoint(update['url'])
                    successful_urls.append(update['url'])

            if len(responses) < len(updates):
                missing = len(updates) - len(responses)
                logger.error(f"Batch response missing {missing} item responses")
                errors += missing

            return len(successful_urls), errors, successful_urls
        except Exception as e:
            if attempt == 2:
                logger.error(f"Batch update failed after retries: {e}")
                return 0, len(updates), []
            wait_seconds = 2 ** attempt
            logger.warning(f"Batch update attempt {attempt + 1} failed: {e}; retrying in {wait_seconds}s")
            time.sleep(wait_seconds)

    return 0, len(updates), []


def list_s3_keys(s3_client, prefix: str) -> Set[str]:
    keys = set()
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
        for obj in page.get('Contents', []):
            keys.add(obj['Key'])
    return keys


def migrate_s3_to_dynamodb(
    days_back: int = 90,
    dry_run: bool = False,
    max_updates: int | None = None,
    max_files: int | None = None,
):
    """
    Migrate S3 metadata files to DynamoDB.
    
    Args:
        days_back: Number of days to migrate (default: 90)
        dry_run: If True, only scan without inserting
    """
    s3_client = boto3.client('s3', region_name='us-east-1')
    
    # Calculate date range
    from datetime import timedelta
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    logger.info("Starting migration from S3 to DynamoDB")
    logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Max updates: {max_updates}")
    logger.info(f"Max files: {max_files}")
    
    # Load checkpoint
    processed_urls = load_checkpoint()
    if processed_urls:
        logger.info(f"Loaded checkpoint with {len(processed_urls)} processed URLs")
    else:
        logger.info("No checkpoint found, starting fresh")
    
    # List all date folders
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=S3_PREFIX,
            Delimiter="/"
        )
        
        date_folders = []
        for prefix in response.get("CommonPrefixes", []):
            folder = prefix.get("Prefix", "").replace(S3_PREFIX, "").rstrip("/")
            if len(folder) == 10 and folder[4] == "-" and folder[7] == "-":
                if (
                    start_date.strftime("%Y-%m-%d")
                    <= folder
                    <= end_date.strftime("%Y-%m-%d")
                ):
                    date_folders.append(folder)
        
        date_folders = sorted(date_folders, reverse=True)
        
        # TEST MODE: Only process first folder for testing
        if days_back == 1:
            date_folders = date_folders[:1]
            logger.info(f"TEST MODE: Processing only {len(date_folders)} date folder")
        
        logger.info(f"Found {len(date_folders)} date folders to migrate")
        
    except Exception as e:
        logger.error(f"Error listing S3 date folders: {e}")
        return
    
    # Process each date folder
    total_processed = 0
    total_skipped = 0
    total_updated = 0
    total_errors = 0
    total_files_seen = 0
    
    for date_folder in date_folders:
        updates_to_process = []
        logger.info(f"\nProcessing date folder: {date_folder}")
        
        # List metadata files in this folder
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=S3_BUCKET_NAME,
                Prefix=f"{S3_PREFIX}{date_folder}/metadata/",
                MaxKeys=1000
            )
            
            metadata_keys = []
            for page in page_iterator:
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        metadata_keys.append(obj['Key'])
            
            logger.info(f"Found {len(metadata_keys)} metadata files")
            
        except Exception as e:
            logger.error(f"Error listing metadata files for {date_folder}: {e}")
            continue

        try:
            content_keys = set()
            for path_suffix in ['content/rss/', 'content/direct/', 'content/']:
                content_keys.update(list_s3_keys(s3_client, f"{S3_PREFIX}{date_folder}/{path_suffix}"))
        except Exception as e:
            logger.error(f"Error listing content files for {date_folder}: {e}")
            content_keys = set()
        
        # Process each metadata file
        for key in metadata_keys:
            try:
                # Read metadata from S3
                obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                metadata = json.loads(obj['Body'].read().decode('utf-8'))
                
                url = metadata.get('url', '')
                
                # Skip if already processed (checkpoint)
                if url in processed_urls:
                    logger.debug(f"Skipping (already processed): {url[:50]}...")
                    total_skipped += 1
                    continue

                if max_files is not None and total_files_seen >= max_files:
                    break

                total_files_seen += 1
                
                # Transform to DynamoDB format
                tags = metadata.get('tags', {})
                if not tags and 'core_topics' in metadata:
                    # Handle legacy format where tags are at top level
                    tags = {
                        'core_topics': metadata.get('core_topics', []),
                        'special_tags': metadata.get('special_tags', []),
                        'matched_keywords': metadata.get('matched_keywords', []),
                        'continents': metadata.get('continents', []),
                        'countries': metadata.get('countries', []),
                    }
                
                url = metadata.get('url', '')
                dynamodb_metadata = {
                    'url': url,
                    'url_hash': _url_hash(url),
                    'title': metadata.get('title', metadata.get('headline', '')),
                    'source': metadata.get('source', 'Unknown'),
                    'pub_date': metadata.get('pub_date', metadata.get('date', '')),
                    'collection_date': metadata.get('collection_date', datetime.now().isoformat()),
                    'content_length': metadata.get('content_length', 0),
                    'tags': tags,
                }
                
                # Add optional fields
                if 'feed_url' in metadata:
                    dynamodb_metadata['feed_url'] = metadata['feed_url']
                if 'base_url' in metadata:
                    dynamodb_metadata['base_url'] = metadata['base_url']
                
                # Try to fetch content from S3
                try:
                    # Extract article_id from metadata key
                    article_id = key.split('/')[-1].replace('.json', '')
                    # Try different content paths
                    content_key = None
                    for path_suffix in ['content/rss/', 'content/direct/', 'content/']:
                        test_key = f"{S3_PREFIX}{date_folder}/{path_suffix}{article_id}.html"
                        if test_key in content_keys:
                            content_key = test_key
                            break
                    
                    if content_key:
                        content_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=content_key)
                        raw_content = content_obj['Body'].read().decode('utf-8')
                        dynamodb_metadata['full_content'] = truncate_content(raw_content)
                        dynamodb_metadata['description'] = metadata.get('description', '')
                        logger.debug(f"Fetched content for {article_id}")
                except Exception as e:
                    logger.debug(f"Could not fetch content for {key}: {e}")
                    dynamodb_metadata['full_content'] = ''
                    dynamodb_metadata['description'] = metadata.get('description', '')
                
                if dry_run:
                    logger.debug(f"[DRY RUN] Would insert/update: {dynamodb_metadata['url'][:50]}...")
                    total_processed += 1
                else:
                    url = dynamodb_metadata.get('url', '')
                    if not url:
                        logger.warning(f"Skipping metadata with missing URL: {key}")
                        total_errors += 1
                        continue

                    url_hash = _url_hash(url)
                    pub_date = dynamodb_metadata.get('pub_date', '')
                    sk = _parse_date_to_sort_key(pub_date)
                    pk = f"ARTICLE#{url_hash}"

                    updates_to_process.append({
                        'pk': pk,
                        'sk': sk,
                        'url': url,
                        'description': dynamodb_metadata.get('description', ''),
                        'full_content': truncate_content(dynamodb_metadata.get('full_content', ''))
                    })

                    batch_limit = 25
                    if max_updates is not None:
                        batch_limit = min(25, max_updates - total_updated)

                    if len(updates_to_process) >= batch_limit:
                        updated, errors, successful_urls = execute_update_batch(updates_to_process)
                        total_updated += updated
                        total_errors += errors
                        processed_urls.update(successful_urls)
                        updates_to_process = []

                        if total_updated and total_updated % 100 == 0:
                            logger.info(f"Progress: {total_updated} articles updated, checkpoint saved")

                        if max_updates is not None and total_updated >= max_updates:
                            logger.info(f"Reached max updates limit: {max_updates}")
                            logger.info(f"Total files seen: {total_files_seen}")
                            logger.info(f"Total updated (with content): {total_updated}")
                            logger.info(f"Total skipped (duplicates): {total_skipped}")
                            logger.info(f"Total errors: {total_errors}")
                            return

            except Exception as e:
                logger.error(f"Error processing {key}: {e}")
                total_errors += 1

        if updates_to_process and not dry_run:
            updated, errors, successful_urls = execute_update_batch(updates_to_process)
            total_updated += updated
            total_errors += errors
            processed_urls.update(successful_urls)
            if total_updated:
                logger.info(f"Progress: {total_updated} articles updated, checkpoint saved")
            if max_updates is not None and total_updated >= max_updates:
                logger.info(f"Reached max updates limit: {max_updates}")
                logger.info(f"Total files seen: {total_files_seen}")
                logger.info(f"Total updated (with content): {total_updated}")
                logger.info(f"Total skipped (duplicates): {total_skipped}")
                logger.info(f"Total errors: {total_errors}")
                return
        
        logger.info(f"Date folder {date_folder} complete: {len(metadata_keys)} files")

        if max_files is not None and total_files_seen >= max_files:
            logger.info(f"Reached max files limit: {max_files}")
            break
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Migration complete!")
    logger.info(f"Total files seen: {total_files_seen}")
    logger.info(f"Total processed: {total_processed}")
    logger.info(f"Total updated (with content): {total_updated}")
    logger.info(f"Total skipped (duplicates): {total_skipped}")
    logger.info(f"Total errors: {total_errors}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    import sys
    
    days_back = 90
    dry_run = False
    max_updates = None
    max_files = None
    
    if len(sys.argv) > 1:
        try:
            days_back = int(sys.argv[1])
        except ValueError:
            pass
    
    if '--dry-run' in sys.argv or '-n' in sys.argv:
        dry_run = True

    if '--max-updates' in sys.argv:
        idx = sys.argv.index('--max-updates')
        if idx + 1 < len(sys.argv):
            try:
                max_updates = int(sys.argv[idx + 1])
            except ValueError:
                pass

    if '--max-files' in sys.argv:
        idx = sys.argv.index('--max-files')
        if idx + 1 < len(sys.argv):
            try:
                max_files = int(sys.argv[idx + 1])
            except ValueError:
                pass
    
    migrate_s3_to_dynamodb(
        days_back=days_back,
        dry_run=dry_run,
        max_updates=max_updates,
        max_files=max_files,
    )
