"""
Contract tests for newsroom DynamoDB ingestion.
Verifies strict adherence to docs/INGESTION_CONTRACT.md.
"""

from unittest.mock import MagicMock, patch
from tools.research.newsroom_dynamodb import insert_article, _url_hash

def test_insert_article_populates_contract_attributes():
    """
    GIVEN an article metadata
    WHEN insert_article is called
    THEN it should populate PK, SK, and all GSI attributes exactly as per contract.
    """
    metadata = {
        'url': 'https://example.com/test-article',
        'title': 'Test Headline',
        'source': 'Test Source',
        'pub_date': '2026-06-09T10:00:00Z',
        'collection_date': '2026-06-09T12:00:00Z',
        'full_content': 'Test content body',
        'tags': {
            'core_topics': ['energy'],
            'continents': ['Africa'],
            'countries': ['South Africa'],
            'special_tags': []
        }
    }
    
    url_hash = _url_hash(metadata['url'])
    expected_pk = f"ARTICLE#{url_hash}"
    expected_sk = "DATE#2026-06-09"
    
    # Mock DynamoDB
    with patch('tools.research.newsroom_dynamodb._get_dynamodb') as mock_get:
        mock_table = MagicMock()
        mock_get.return_value.Table.return_value = mock_table
        
        insert_article(metadata)
        
        # Capture the item sent to put_item
        args, kwargs = mock_table.put_item.call_args
        item = kwargs['Item']
        
        assert item['PK'] == expected_pk
        assert item['SK'] == expected_sk
        assert item['date_key'] == "DATE#2026-06-09"
        assert item['pub_timestamp'].startswith("PUB#")
        assert item['collection_key'] == "COLLECTED#2026-06-09"
        assert item['topic_key'] == "TOPIC#energy"
        assert item['source_key'] == "SOURCE#Test Source"
        assert item['url'] == metadata['url']
        assert item['content_length'] > 0

def test_insert_article_legislation_routing():
    """
    GIVEN a legislation article
    WHEN insert_article is called
    THEN it should route topic_key to TOPIC#legislation.
    """
    metadata = {
        'url': 'https://example.com/bill-123',
        'title': 'New Bill',
        'source': 'Legislation Feed',
        'pub_date': '2026-06-09T10:00:00Z',
        'tags': {
            'special_tags': ['legislation'],
            'core_topics': ['energy'] # Should be overridden by legislation tag for topic_key
        }
    }
    
    with patch('tools.research.newsroom_dynamodb._get_dynamodb') as mock_get:
        mock_table = MagicMock()
        mock_get.return_value.Table.return_value = mock_table
        
        insert_article(metadata)
        
        args, kwargs = mock_table.put_item.call_args
        item = kwargs['Item']
        
        assert item['topic_key'] == "TOPIC#legislation"
        assert 'legislation' in item['special_tags']
