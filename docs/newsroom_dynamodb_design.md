# Newsroom DynamoDB Architecture Design

## Overview
Replace S3 metadata file storage with DynamoDB for fast, indexed queries and efficient facet generation.

## Table Schema

### Table: `newsroom_articles`

**Primary Key:**
- `PK` (Partition Key): `ARTICLE#{url_hash}` - MD5 hash of article URL for deduplication
- `SK` (Sort Key): `DATE#{date}` - Publication date for time-based sorting

**Attributes:**
```
- url (String): Original article URL
- title (String): Article headline
- source (String): Source name (e.g., "RSS Feed", "Direct Scraping")
- pub_date (String): Publication date in ISO format
- collection_date (String): When article was collected
- content_length (Number): Character count of full content
- core_topics (List<String>): Primary topic classifications
- special_tags (List<String>): Special tags (e.g., "legislation", "prediction_market")
- matched_keywords (List<String>): Keywords matched during tagging
- continents (List<String>): Geographic continents
- countries (List<String>): Countries mentioned
- feed_url (String): RSS feed URL (if applicable)
- base_url (String): Base URL for direct scraping (if applicable)
```

**Global Secondary Indexes (GSI):**

1. **GSI: `date-index`**
   - PK: `DATE#{date}`
   - SK: `PUB#{timestamp}` (publication timestamp for sorting)
   - Use: Query articles by date range, sorted by publication time

2. **GSI: `topic-index`**
   - PK: `TOPIC#{core_topic}`
   - SK: `DATE#{date}`
   - Use: Query articles by topic, sorted by date

3. **GSI: `source-index`**
   - PK: `SOURCE#{source}`
   - SK: `DATE#{date}`
   - Use: Query articles by source, sorted by date

4. **GSI: `collection-date-index`**
   - PK: `COLLECTED#{collection_date}`
   - SK: `PUB#{timestamp}`
   - Use: Query articles by collection date (for rolling window cache)

## Query Patterns

### 1. Fetch articles by date range (UI default view)
```
Query: date-index
  PK: DATE#{start_date} to DATE#{end_date}
  Sort Key: ASC/DESC
  Filter: None
```

### 2. Fetch articles by topic
```
Query: topic-index
  PK: TOPIC#{topic_name}
  SK: DATE#{start_date} to DATE#{end_date}
  Sort Key: DESC
```

### 3. Fetch articles by source
```
Query: source-index
  PK: SOURCE#{source_name}
  SK: DATE#{start_date} to DATE#{end_date}
  Sort Key: DESC
```

### 4. Generate facets (topic distribution, sources, date range)
```
Scan with ProjectionExpression for specific attributes
  - core_topics (for topic counts)
  - source (for source counts)
  - pub_date (for date range)
```

### 5. Check deduplication
```
GetItem:
  PK: ARTICLE#{url_hash}
  SK: DATE#{date}
```

## Migration Strategy

### Phase 1: Create DynamoDB table
- Use CloudFormation or boto3 to create table with GSIs
- Set appropriate capacity modes (on-demand or provisioned)

### Phase 2: Migrate existing S3 data
- Scan S3 bucket for all metadata files
- Parse and insert into DynamoDB
- Verify data integrity

### Phase 3: Update scraper
- Modify scraper to write to DynamoDB instead of S3 metadata files
- Keep S3 for full article content storage
- Update idempotency checks to use DynamoDB

### Phase 4: Update newsroom API
- Replace S3 listing/fetching with DynamoDB queries
- Update caching layer to work with DynamoDB results
- Update facet generation to use DynamoDB scans

### Phase 5: Testing and validation
- Verify topic diversity
- Verify performance targets (<4s for 500 articles)
- Update tests

## Advantages

1. **Performance**: Indexed queries instead of full scans
2. **Scalability**: Automatic scaling, no listing overhead
3. **Cost**: Pay for read/write capacity, not storage operations
4. **Flexibility**: Easy to add new indexes for different query patterns
5. **Consistency**: Strong consistency options available

## Retained S3 Usage

- Full article content (HTML) still stored in S3
- S3 remains cost-effective for large text blobs
- Content accessed via URL from DynamoDB record
