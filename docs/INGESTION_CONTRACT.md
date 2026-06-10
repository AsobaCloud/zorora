# Newsroom Ingestion Contract (V1)

## Overview
This document defines the strict architectural and data contracts for all Zorora news scrapers. Agents (including SWE 1.6) MUST follow these specifications exactly. No architectural deviations are permitted without explicit human approval.

## 1. Infrastructure Requirements
- **DynamoDB Table**: `newsroom_articles`
- **AWS Region**: `us-east-1`
- **S3 Bucket (Overflow)**: `news-collection-website` (used for articles > 380KB)

## 2. DynamoDB Single-Table Schema

### Primary Keys
- **PK** (Partition Key): `ARTICLE#{url_hash}` 
  - `url_hash` is the MD5 hex digest of the normalized article URL.
- **SK** (Sort Key): `METADATA`
  - Fixed string used to ensure URL-based uniqueness (idempotency) across the table.

### Global Secondary Indexes (GSI)
Every item MUST populate these attributes to enable correct GSI routing:

| Index Name | Partition Key (Attribute) | Sort Key (Attribute) | Purpose |
| :--- | :--- | :--- | :--- |
| **date-index** | `date_key` (`DATE#YYYY-MM-DD`) | `pub_timestamp` (`PUB#{unix_time}`) | Time-based browsing |
| **topic-index** | `topic_key` (`TOPIC#{topic_name}`) | `SK` (`DATE#YYYY-MM-DD`) | Topic-based filtering |
| **source-index** | `source_key` (`SOURCE#{source_name}`) | `SK` (`DATE#YYYY-MM-DD`) | Source-based filtering |
| **collection-date-index** | `collection_key` (`COLLECTED#YYYY-MM-DD`) | `pub_timestamp` (`PUB#{unix_time}`) | Freshness/Cache tracking |

## 3. Mandatory Attributes
Scrapers must provide these fields to the `insert_article` utility:

| Attribute | Type | Format/Example |
| :--- | :--- | :--- |
| `url` | String | `https://example.com/article` |
| `title` | String | `Headline of the article` |
| `source` | String | `Reuters`, `RSS Feed`, `Legislation` |
| `pub_date` | String | `2026-06-09T10:00:00Z` |
| `collection_date` | String | `2026-06-09T15:00:00Z` |
| `core_topics` | List | `["energy", "ai"]` |
| `continents` | List | `["Africa"]` |
| `full_content` | String | Full text or HTML (auto-truncated if > 380KB) |

## 4. Special Tagging (GSI Routing)
- **Legislation**: Articles from legislative feeds MUST have `special_tags: ["legislation"]`. The `topic_key` will be set to `TOPIC#legislation`.
- **Economy/Politics**: Articles from these feeds MUST have `special_tags: ["economy_politics"]`.

## 5. Deployment Checklist (Zero-Thought)
1.  Verify `DYNAMODB_TABLE_NAME` is set to `newsroom_articles`.
2.  Verify `AWS_REGION` is set to `us-east-1`.
3.  Ensure `tools.research.newsroom_dynamodb.insert_article()` is used for all writes.
4.  NEVER use `article_id` as a primary key name.
5.  NEVER write directly to S3 metadata folders; metadata belongs in DynamoDB.
