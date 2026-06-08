"""
Standardized test suite for newsroom scrapers.
Every scraper must satisfy this interface before deployment.
"""

from unittest.mock import Mock, patch


class TestScraperContract:
    """Contract tests that all scrapers must satisfy."""

    def test_deduplication(self):
        """
        GIVEN an article URL already exists in DynamoDB
        WHEN the scraper attempts to insert it again
        THEN insert_article returns False AND no duplicate record is created
        """
        from tools.research.newsroom_dynamodb import insert_article
        from botocore.exceptions import ClientError

        # Mock DynamoDB to simulate existing record
        mock_resource = Mock()
        mock_table = Mock()
        mock_resource.Table.return_value = mock_table
        error_response = {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'The conditional request failed'}}
        mock_table.put_item.side_effect = ClientError(error_response, 'PutItem')

        with patch("tools.research.newsroom_dynamodb.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_resource

            metadata = {
                "url": "https://example.com/article",
                "title": "Test Article",
                "source": "Test Source",
                "pub_date": "2026-06-08",
                "full_content": "Test content",
            }
            result = insert_article(metadata)

        assert result is False, "Should return False for duplicate URL"

    def test_full_content_integrity(self):
        """
        GIVEN an article with 400KB of text
        WHEN ingested
        THEN the DynamoDB record contains a truncated preview AND an s3_overflow_key
        """
        from tools.research.newsroom_dynamodb import insert_article, MAX_FULL_CONTENT_BYTES

        # Create content larger than 380KB
        large_content = "x" * (MAX_FULL_CONTENT_BYTES + 20000)

        mock_resource = Mock()
        mock_table = Mock()
        mock_resource.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        mock_s3_client = Mock()

        with patch("tools.research.newsroom_dynamodb.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_resource
            mock_boto3.client.return_value = mock_s3_client

            metadata = {
                "url": "https://example.com/large-article",
                "title": "Large Article",
                "source": "Test Source",
                "pub_date": "2026-06-08",
                "full_content": large_content,
            }
            result = insert_article(metadata)

        assert result is True, "Should return True for successful insert"

        # Verify S3 upload was called for overflow
        assert mock_s3_client.put_object.called, "Should upload overflow to S3"

        # Verify the call to put_item
        call_args = mock_table.put_item.call_args
        item = call_args[1]["Item"]
        assert "s3_overflow_key" in item, "Should have s3_overflow_key"
        assert len(item["full_content"]) <= MAX_FULL_CONTENT_BYTES, "Content should be truncated"

    def test_tagging_consistency(self):
        """
        GIVEN a raw article body
        WHEN processed
        THEN core_topics contains at least one valid category (energy, ai, blockchain)
        """
        from tools.research.article_tagger import tag_article

        # Test article with energy content
        article_body = """
        The new solar energy project in South Africa will generate 500MW of power.
        Renewable energy investments are increasing across the continent.
        """

        keywords = ["energy", "solar", "renewable", "power"]
        tags = tag_article(article_body, keywords)

        assert "core_topics" in tags, "Should have core_topics"
        assert len(tags["core_topics"]) > 0, "Should have at least one topic"
        # Verify at least one valid category
        valid_categories = {"energy", "ai", "blockchain"}
        has_valid_category = any(
            topic.lower() in valid_categories for topic in tags["core_topics"]
        )
        assert has_valid_category, "Should have at least one valid category"

    def test_fixed_sk_schema(self):
        """
        GIVEN an article metadata
        WHEN inserted into DynamoDB
        THEN the record uses SK='METADATA' for URL-based idempotency
        """
        from tools.research.newsroom_dynamodb import insert_article

        mock_resource = Mock()
        mock_table = Mock()
        mock_resource.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        with patch("tools.research.newsroom_dynamodb.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_resource

            metadata = {
                "url": "https://example.com/article",
                "title": "Test Article",
                "source": "Test Source",
                "pub_date": "2026-06-08",
                "full_content": "Test content",
            }
            insert_article(metadata)

        # Verify the schema
        call_args = mock_table.put_item.call_args
        item = call_args[1]["Item"]
        assert item["SK"] == "METADATA", "SK should be fixed to METADATA"
        assert "PK" in item, "Should have PK"
        assert item["PK"].startswith("ARTICLE#"), "PK should start with ARTICLE#"

    def test_environment_variable_table_name(self):
        """
        GIVEN DYNAMODB_TABLE_NAME environment variable is set
        WHEN insert_article is called
        THEN it uses the specified table name
        """
        import os
        from tools.research.newsroom_dynamodb import insert_article

        mock_resource = Mock()
        mock_table = Mock()
        mock_resource.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        with patch.dict(os.environ, {"DYNAMODB_TABLE_NAME": "custom_table"}):
            with patch("tools.research.newsroom_dynamodb.boto3") as mock_boto3:
                mock_boto3.resource.return_value = mock_resource

                metadata = {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "source": "Test Source",
                    "pub_date": "2026-06-08",
                    "full_content": "Test content",
                }
                insert_article(metadata)

        # Verify the custom table name was used
        mock_resource.Table.assert_called_with("custom_table")
