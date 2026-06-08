"""
Create DynamoDB table for newsroom articles with required indexes.
Run this script to set up the DynamoDB table for the new architecture.
"""

import boto3
import logging
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TABLE_NAME = "newsroom_articles"

def create_newsroom_table():
    """Create DynamoDB table with GSIs for newsroom articles."""
    
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    # Check if table already exists
    try:
        existing_table = dynamodb.describe_table(TableName=TABLE_NAME)
        logger.info(f"Table {TABLE_NAME} already exists with status: {existing_table['Table']['TableStatus']}")
        return existing_table['Table']
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            logger.error(f"Error checking table: {e}")
            raise
    
    logger.info(f"Creating table {TABLE_NAME}...")
    
    try:
        response = dynamodb.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[
                # Primary key
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                
                # GSI: date-index
                {'AttributeName': 'date_key', 'AttributeType': 'S'},
                {'AttributeName': 'pub_timestamp', 'AttributeType': 'S'},
                
                # GSI: topic-index
                {'AttributeName': 'topic_key', 'AttributeType': 'S'},
                
                # GSI: source-index
                {'AttributeName': 'source_key', 'AttributeType': 'S'},
                
                # GSI: collection-date-index
                {'AttributeName': 'collection_key', 'AttributeType': 'S'},
            ],
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'date-index',
                    'KeySchema': [
                        {'AttributeName': 'date_key', 'KeyType': 'HASH'},
                        {'AttributeName': 'pub_timestamp', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'topic-index',
                    'KeySchema': [
                        {'AttributeName': 'topic_key', 'KeyType': 'HASH'},
                        {'AttributeName': 'SK', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'source-index',
                    'KeySchema': [
                        {'AttributeName': 'source_key', 'KeyType': 'HASH'},
                        {'AttributeName': 'SK', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'collection-date-index',
                    'KeySchema': [
                        {'AttributeName': 'collection_key', 'KeyType': 'HASH'},
                        {'AttributeName': 'pub_timestamp', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            },
            StreamSpecification={
                'StreamEnabled': False
            }
        )
        
        logger.info(f"Table creation initiated: {response['TableDescription']['TableArn']}")
        
        # Wait for table to be created
        logger.info("Waiting for table to become ACTIVE...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        logger.info(f"Table {TABLE_NAME} is now ACTIVE")
        
        # Describe the table to confirm
        table = dynamodb.describe_table(TableName=TABLE_NAME)
        return table['Table']
        
    except ClientError as e:
        logger.error(f"Error creating table: {e}")
        raise


def delete_table():
    """Delete the newsroom articles table (use with caution)."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    try:
        logger.info(f"Deleting table {TABLE_NAME}...")
        dynamodb.delete_table(TableName=TABLE_NAME)
        
        logger.info("Waiting for table to be deleted...")
        waiter = dynamodb.get_waiter('table_not_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        logger.info(f"Table {TABLE_NAME} deleted successfully")
    except ClientError as e:
        logger.error(f"Error deleting table: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--delete':
        delete_table()
    else:
        create_newsroom_table()
