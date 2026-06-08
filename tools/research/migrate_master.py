#!/usr/bin/env python3
"""
Master migration script - runs full content migration and tagging in one shot.
This script automates:
1. Increase DynamoDB capacity
2. Run content migration (S3 -> DynamoDB)
3. Restore DynamoDB capacity
4. Run article tagging (ML tagger)
5. Validate success with API calls

Run with: python tools/research/migrate_master.py
"""

import subprocess
import sys
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TABLE_NAME = "newsroom_articles"
REGION = "us-east-1"
ORIGINAL_WRITE_CAPACITY = 10
MIGRATION_WRITE_CAPACITY = 100


def run_command(cmd, description, check=True):
    """Run a shell command and log output."""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            logger.info(f"STDOUT: {result.stdout[:500]}")
        if result.stderr:
            logger.warning(f"STDERR: {result.stderr[:500]}")
        
        logger.info(f"✓ {description} completed")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed: {e}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout[:500]}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr[:500]}")
        return False


def increase_capacity():
    """Increase DynamoDB write capacity for migration."""
    cmd = (
        f"aws dynamodb update-table "
        f"--table-name {TABLE_NAME} "
        f"--region {REGION} "
        f"--provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits={MIGRATION_WRITE_CAPACITY}"
    )
    success = run_command(cmd, "Increasing DynamoDB write capacity")
    if success:
        logger.info("Waiting 60 seconds for capacity change to propagate...")
        time.sleep(60)
    return success


def restore_capacity():
    """Restore DynamoDB write capacity to original."""
    cmd = (
        f"aws dynamodb update-table "
        f"--table-name {TABLE_NAME} "
        f"--region {REGION} "
        f"--provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits={ORIGINAL_WRITE_CAPACITY}"
    )
    success = run_command(cmd, "Restoring DynamoDB write capacity")
    if success:
        logger.info("Waiting 60 seconds for capacity change to propagate...")
        time.sleep(60)
    return success


def run_content_migration():
    """Run the S3 to DynamoDB content migration."""
    cmd = "python tools/research/migrate_s3_to_dynamodb.py 90"
    return run_command(cmd, "Content migration (S3 -> DynamoDB)")


def run_article_tagging():
    """Run the article tagging backfill."""
    cmd = "python tools/research/backfill_topics.py"
    return run_command(cmd, "Article tagging (ML tagger)")


def validate_content_fields():
    """Validate that articles have description and full_content fields."""
    cmd = (
        f"aws dynamodb scan "
        f"--table-name {TABLE_NAME} "
        f"--region {REGION} "
        f"--filter-expression 'attribute_exists(description) AND attribute_exists(full_content)' "
        f"--max-items 10 "
        f"--projection-expression 'PK,SK,title,description,full_content'"
    )
    success = run_command(cmd, "Validating content fields exist", check=False)
    return success


def validate_no_empty_topics():
    """Count articles with empty core_topics."""
    cmd = (
        f"aws dynamodb scan "
        f"--table-name {TABLE_NAME} "
        f"--region {REGION} "
        f"--filter-expression 'attribute_not_exists(core_topics) OR size(core_topics) = 0' "
        f"--select COUNT"
    )
    success = run_command(cmd, "Counting articles with empty topics", check=False)
    return success


def main():
    """Run the full migration pipeline."""
    logger.info("=" * 80)
    logger.info("MASTER MIGRATION SCRIPT STARTED")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # Phase 1: Increase capacity
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: Increasing DynamoDB capacity")
    logger.info("=" * 80)
    if not increase_capacity():
        logger.error("Failed to increase capacity, aborting")
        return 1
    
    # Phase 2: Content migration
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: Running content migration")
    logger.info("=" * 80)
    if not run_content_migration():
        logger.error("Content migration failed, attempting to restore capacity...")
        restore_capacity()
        return 1
    
    # Phase 3: Restore capacity
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: Restoring DynamoDB capacity")
    logger.info("=" * 80)
    if not restore_capacity():
        logger.error("Failed to restore capacity")
        return 1
    
    # Phase 4: Article tagging
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 4: Running article tagging")
    logger.info("=" * 80)
    if not run_article_tagging():
        logger.error("Article tagging failed")
        return 1
    
    # Phase 5: Validation
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 5: Validating migration success")
    logger.info("=" * 80)
    validate_content_fields()
    validate_no_empty_topics()
    
    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 80)
    logger.info("MASTER MIGRATION SCRIPT COMPLETED")
    logger.info(f"Total time: {elapsed / 60:.1f} minutes")
    logger.info("=" * 80)
    
    logger.info("\nManual validation steps:")
    logger.info("1. Check Global View in browser for energy-focused articles")
    logger.info("2. Call /api/news-intel/facets to verify energy topics")
    logger.info("3. Call /api/news-intel/articles to verify proper data")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
