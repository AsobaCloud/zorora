# Zorora Infrastructure Documentation

## Overview

Zorora is deployed on AWS in the `af-south-1` (Cape Town) region with supporting infrastructure in `us-east-1` (N. Virginia). The system uses ECS Fargate for the main application, Lambda functions for background processing, DynamoDB for data persistence, and S3 for content storage.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS af-south-1                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │  CloudFront CDN  │─────▶│  ECS Fargate     │                │
│  │  (Optional)      │      │  ona-zorora-prod │                │
│  └──────────────────┘      │  (Flask App)     │                │
│                            └────────┬─────────┘                │
│                                     │                           │
│  ┌──────────────────┐              │                           │
│  │  SSM Parameters  │◀─────────────┘                           │
│  │  - API Keys      │                                          │
│  │  - JWT Secrets   │                                          │
│  └──────────────────┘                                          │
│                                     │                           │
│  ┌──────────────────┐              │                           │
│  │  DynamoDB        │◀─────────────┘                           │
│  │  (us-east-1)     │                                          │
│  │  - newsroom_     │                                          │
│  │    articles      │                                          │
│  │  - ona-platform  │                                          │
│  │    tables        │                                          │
│  └──────────────────┘                                          │
│                                     │                           │
│  ┌──────────────────┐              │                           │
│  │  S3 Buckets      │◀─────────────┘                           │
│  │  - news-         │                                          │
│  │    collection-   │                                          │
│  │    website       │                                          │
│  │  - ona-platform  │                                          │
│  └──────────────────┘                                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Lambda Functions (EventBridge Scheduled)        │          │
│  │  - ona-newsroom-sync-prod                        │          │
│  │  - ona-weatherCache-prod                         │          │
│  │  - globalTrainingService                         │          │
│  │  - ona-user-auth                                 │          │
│  │  - ona-user-management                           │          │
│  │  - ona-customer-listing                          │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         AWS us-east-1                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │  DynamoDB        │      │  S3 Buckets      │                │
│  │  - newsroom_     │      │  - visualcrossing│                │
│  │    articles      │      │    -city-database│                │
│  │  - ona-platform  │      │  - sa-api-client  │                │
│  │    tables        │      │    -input/output │                │
│  └──────────────────┘      └──────────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## ECS Fargate Deployment

### Cluster: `ona-zorora-prod`

**Service:** `ona-zorora-prod`

**Task Definition:** `ona-zorora-prod` (managed via task-def-*.json files)

**Container Image:** `905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora:prod-{commit}`

**Environment Variables:**
- `EIA_API_KEY`: Fetched from SSM `/zorora/prod/eia-api-key`
- `OPENEI_API_KEY`: Fetched from SSM `/zorora/prod/openei-api-key`
- `BRAVE_SEARCH_API_KEY`: Fetched from SSM `/zorora/prod/brave-search-api-key`
- `CONGRESS_GOV_API_KEY`: Fetched from SSM `/zorora/prod/congress-gov-api-key`
- `CORE_API_KEY`: Fetched from SSM `/zorora/prod/core-api-key`
- `FRED_API_KEY`: Fetched from SSM `/zorora/prod/fred-api-key`
- `HF_TOKEN`: Fetched from SSM `/zorora/prod/hf-token`
- `NEWSROOM_JWT_TOKEN`: Fetched from SSM `/zorora/prod/newsroom-jwt-token`
- `ONA_JWT_SECRET`: Fetched from SSM `/zorora/prod/ona-jwt-secret`

**Log Group:** `/ecs/ona-zorora-prod` (81 MB stored)

**Deployment:** Docker images built from `config.docker.py` and pushed to ECR

## Lambda Functions

### Zorora-Specific Lambdas

#### 1. `ona-newsroom-sync-prod`
- **Runtime:** Python 3.9
- **Handler:** `lambda_news_scraper.lambda_handler`
- **Role:** `news-scraper-role`
- **Trigger:** EventBridge rule `ona-newsroom-sync-prod` (scheduled)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-newsroom-sync-prod` (85 KB stored)
- **Purpose:** Scrapes news articles and exports to S3 for Zorora consumption
- **S3 Output:** `s3://news-collection-website/zorora-export/articles.json`
- **IAM Permissions:** S3 (read/write), DynamoDB (newsroom_articles table)

### ONA Platform Lambdas (Shared Infrastructure)

#### 2. `ona-user-auth`
- **Runtime:** Python 3.9
- **Handler:** `auth.lambda_handler`
- **Role:** `ona-lambda-user-auth-role`
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-user-auth` (206 KB stored)
- **Purpose:** JWT token validation and user authentication
- **Environment:** `JWT_SECRET`, `USERS_TABLE`, `ROLES_TABLE`, `GROUPS_TABLE`

#### 3. `ona-user-management`
- **Runtime:** Python 3.9
- **Handler:** `users.lambda_handler`
- **Role:** `ona-user-management-prod-UsersFunctionRole`
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-user-management` (527 KB stored)
- **Purpose:** User CRUD operations and profile management
- **Environment:** `USERS_TABLE`, `CUSTOMERS_TABLE`, `JWT_SECRET`

#### 4. `ona-customer-listing`
- **Runtime:** Python 3.9
- **Handler:** `customers.lambda_handler`
- **Role:** `ona-user-management-prod-CustomersFunctionRole`
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-customer-listing`
- **Purpose:** Customer listing and management
- **Environment:** `CUSTOMERS_TABLE`, `USERS_TABLE`, `ROLES_TABLE`, `GROUPS_TABLE`

#### 5. `ona-role-management`
- **Runtime:** Python 3.9
- **Handler:** `roles.lambda_handler`
- **Role:** `ona-role-management-role`
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-role-management` (237 KB stored)
- **Purpose:** Role and permission management
- **Environment:** `ROLES_TABLE`, `GROUPS_TABLE`, `JWT_SECRET`

#### 6. `ona-skin-management`
- **Runtime:** Python 3.9
- **Handler:** `skins.lambda_handler`
- **Role:** `ona-skin-management-role`
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-skin-management` (968 KB stored)
- **Purpose:** UI skin/theme management
- **Environment:** `SKINS_TABLE`, `JWT_SECRET`

### Data Processing Lambdas

#### 7. `ona-weatherCache-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-weatherCache-role`
- **Trigger:** API Gateway
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-weatherCache-prod` (15 MB stored)
- **Dead Letter Queue:** `ona-weatherCache-dlq` (SQS)
- **Purpose:** Weather data caching and API proxy
- **Environment:** `WEATHER_CACHE_TABLE`, `LOCATIONS_TABLE`, `VISUAL_CROSSING_API_KEY`

#### 8. `globalTrainingService`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-globalTrainingService-role`
- **Timeout:** 900 seconds
- **Memory:** 3008 MB
- **Log Group:** `/aws/lambda/globalTrainingService`
- **Purpose:** ML model training and inference
- **Environment:** `INPUT_BUCKET`, `OUTPUT_BUCKET`, `WEATHER_BUCKET`

#### 9. `ona-terminalApi-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-terminalApi-role`
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-terminalApi-prod` (22 MB stored)
- **Purpose:** Terminal device API for solar installations
- **Environment:** Multiple terminal-related tables

#### 10. `ona-huaweiRealTime-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-huaweiRealTime-role`
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-huaweiRealTime-prod` (398 MB stored)
- **Purpose:** Huawei inverter real-time data ingestion

#### 11. `ona-huaweiHistorical-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-huaweiHistorical-role`
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-huaweiHistorical-prod` (7.5 MB stored)
- **Purpose:** Huawei inverter historical data ingestion

#### 12. `ona-enphaseHistorical-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-enphaseHistorical-role`
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-enphaseHistorical-prod`
- **Purpose:** Enphase inverter historical data ingestion

#### 13. `ona-interpolationService-prod`
- **Runtime:** Docker (Image)
- **Role:** `ona-lambda-interpolationService-role`
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-interpolationService-prod` (126 MB stored)
- **Purpose:** Data interpolation for missing readings

## DynamoDB Tables

### Zorora Tables (us-east-1)

#### `newsroom_articles`
**Primary Key:**
- `PK` (Partition Key): `ARTICLE#{url_hash}` - MD5 hash of article URL
- `SK` (Sort Key): `DATE#{date}` - Publication date

**Attributes:**
- `url` (String): Original article URL
- `title` (String): Article headline
- `source` (String): Source name
- `pub_date` (String): Publication date (ISO format)
- `collection_date` (String): Collection timestamp
- `content_length` (Number): Character count
- `core_topics` (List<String>): Topic classifications
- `special_tags` (List<String>): Special tags
- `matched_keywords` (List<String>): Matched keywords
- `continents` (List<String>): Geographic continents
- `countries` (List<String>): Countries mentioned
- `feed_url` (String): RSS feed URL
- `base_url` (String): Base URL for scraping
- `description` (String): Article description
- `full_content` (String): Full article content

**Global Secondary Indexes:**
1. `date-index`: PK=`DATE#{date}`, SK=`PUB#{timestamp}` - Query by date range
2. `topic-index`: PK=`TOPIC#{topic}`, SK=`DATE#{date}` - Query by topic
3. `source-index`: PK=`SOURCE#{source}`, SK=`DATE#{date}` - Query by source
4. `collection-date-index`: PK=`COLLECTED#{date}`, SK=`PUB#{timestamp}` - Query by collection date

**Data Contract:**
- All dates in ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- URL hashes use MD5 for deduplication
- Topic tags use controlled vocabulary from article_tagger
- Content stored directly in DynamoDB (no S3 dependency)

### ONA Platform Tables (us-east-1)

#### `ona-platform-users`
**Primary Key:**
- `user_id` (String): UUID

**Key Attributes:**
- `email` (String): User email
- `subscriptions` (List<Object>): Subscription details
  - `product` (String): "zorora"
  - `tier` (String): "explorer" | "professional" | "enterprise"
  - `started_at` (String): ISO timestamp
  - `stripe_subscription_id` (String): Stripe subscription ID
- `usage` (Map<Object>): Usage tracking
  - `zorora_research_queries` (Number): Query count
  - `zorora_queries_reset_at` (String): Reset timestamp

**Data Contract:**
- User IDs are UUIDs
- Subscriptions list allows multi-product support
- Usage tracking enables tier-based quota enforcement

#### Other ONA Tables
- `ona-platform-customers`: Customer organization data
- `ona-platform-roles`: Role definitions and permissions
- `ona-platform-groups`: User groups
- `ona-platform-skins`: UI theme configurations
- `ona-platform-locations`: Geographic location data
- `ona-platform-weather-cache`: Weather data cache
- `ona-platform-terminal-*`: Terminal device management tables
- `ona-platform-ml-*`: ML model registry and results

## S3 Buckets

### Zorora Buckets (af-south-1)

#### `news-collection-website`
**Purpose:** News article storage and exports

**Key Prefixes:**
- `zorora-export/articles.json`: Zorora newsroom export file
- `{YYYY-MM-DD}/`: Daily article folders (legacy S3 metadata structure)

**Data Contract:**
- Export file format: JSON array of article objects
- Article object schema:
  ```json
  {
    "url": "https://example.com/article",
    "title": "Article Title",
    "source": "Source Name",
    "pub_date": "2026-06-05T00:00:00Z",
    "description": "Article description",
    "full_content": "Full article text...",
    "core_topics": ["energy", "solar"],
    "special_tags": [],
    "matched_keywords": ["solar", "energy"],
    "continents": ["Africa"],
    "countries": ["South Africa"],
    "feed_url": "https://example.com/feed",
    "collection_date": "2026-06-05T00:00:00Z"
  }
  ```

**Access:** Public read access for export file

#### `ona-zorora-prod-user-state-migrate`
**Purpose:** User state migration (temporary)

### ONA Platform Buckets (af-south-1)

#### `ona-platform`
**Purpose:** ONA platform static assets and data

#### `ona-terminal`
**Purpose:** Terminal device data and logs

#### `ona-cloudfront-logs`
**Purpose:** CloudFront access logs

#### `ona-edge-compute`
**Purpose:** Edge computing artifacts

### Data Processing Buckets (us-east-1)

#### `visualcrossing-city-database`
**Purpose:** Weather data database

#### `sa-api-client-input`
**Purpose:** Solar analytics API input data

#### `sa-api-client-output`
**Purpose:** Solar analytics API output data

## CloudWatch Logs

### ECS Log Groups

#### `/ecs/ona-zorora-prod`
- **Region:** af-south-1
- **Stored Bytes:** 81 MB
- **Retention:** Default (never expire)
- **Purpose:** Zorora application logs
- **Streams:** Per-container instance logs

#### `/ecs/scraper`
- **Region:** af-south-1
- **Stored Bytes:** 5.9 MB
- **Retention:** 14 days
- **Purpose:** Legacy scraper logs

### Lambda Log Groups (af-south-1)

#### Zorora-Related
- `/aws/lambda/ona-newsroom-sync-prod` (85 KB)
- `/aws/lambda/partnerApi` (11 KB)

#### ONA Platform
- `/aws/lambda/ona-user-auth` (206 KB)
- `/aws/lambda/ona-user-management` (527 KB)
- `/aws/lambda/ona-customer-listing`
- `/aws/lambda/ona-role-management` (237 KB)
- `/aws/lambda/ona-skin-management` (968 KB)

#### Data Processing
- `/aws/lambda/ona-weatherCache-prod` (15 MB)
- `/aws/lambda/ona-terminalApi-prod` (22 MB)
- `/aws/lambda/ona-huaweiRealTime-prod` (398 MB)
- `/aws/lambda/ona-huaweiHistorical-prod` (7.5 MB)
- `/aws/lambda/ona-enphaseHistorical-prod`
- `/aws/lambda/ona-interpolationService-prod` (126 MB)

#### ML Services
- `/aws/lambda/globalTrainingService`
- `/aws/lambda/trainForecaster` (140 KB)
- `/aws/lambda/sa-generateForecast` (15 KB)
- `/aws/lambda/sa-generateForecastFreemium` (27 KB)
- `/aws/lambda/returnForecastingResults` (118 KB)

## SSM Parameters

### Zorora Parameters (af-south-1)

#### API Keys
- `/zorora/prod/eia-api-key`: EIA Open Data API key
- `/zorora/prod/openei-api-key`: OpenEI Utility Rates API key
- `/zorora/prod/brave-search-api-key`: Brave Search API key
- `/zorora/prod/congress-gov-api-key`: Congress.gov API key
- `/zorora/prod/core-api-key`: Core API key
- `/zorora/prod/fred-api-key`: FRED Economic Data API key
- `/zorora/prod/hf-token`: HuggingFace API token

#### Secrets
- `/zorora/prod/newsroom-jwt-token`: Newsroom JWT token (deprecated)
- `/zorora/prod/ona-jwt-secret`: ONA Platform JWT secret

### ONA Platform Parameters (af-south-1)

- `/ona-platform/prod/global-training-api-endpoint`: Global training API endpoint
- `/ona-platform/prod/global-training-api-token`: Global training API token

## EventBridge Rules

### Zorora Rules

#### `ona-newsroom-sync-prod`
- **Schedule:** Rate-based (e.g., every 6 hours)
- **Target:** `ona-newsroom-sync-prod` Lambda
- **Purpose:** Trigger news scraping and export

## IAM Roles

### Zorora Roles

#### `news-scraper-role`
- **Policies:** `news-scraper-policy`
- **Permissions:**
  - S3: `news-collection-website` (read/write)
  - DynamoDB: `newsroom_articles` (PutItem, GetItem, Query, Scan, UpdateItem)

### ONA Platform Roles

#### `ona-lambda-*-role` (various)
- **Policies:** Service-specific policies
- **Permissions:** DynamoDB, S3, SQS, CloudWatch Logs

## API Gateway

### Zorora API
- **Region:** af-south-1
- **Endpoints:**
  - `/api/research/*`: Deep research endpoints
  - `/api/auth/*`: Authentication endpoints
  - `/api/regulatory/*`: Regulatory data endpoints
  - `/api/settings/*`: User settings endpoints

### ONA Platform API
- **Region:** af-south-1
- **Endpoints:** User management, terminal API, weather cache

## Deployment Pipeline

### Build Process
1. Code committed to GitHub
2. Docker image built from `config.docker.py`
3. Image pushed to ECR: `905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora`
4. Task definition updated with new image tag
5. ECS service updated with new task definition

### Deployment Artifacts
- `task-def-*.json`: ECS task definition templates
- `DEPLOYMENT_CHECKLIST.md`: Deployment procedures
- `config.docker.py`: Production configuration

## Monitoring and Alerting

### CloudWatch Metrics
- ECS CPU/Memory utilization
- Lambda invocation counts and errors
- DynamoDB read/write capacity
- S3 request counts

### Log Analysis
- ECS logs: `/ecs/ona-zorora-prod`
- Lambda logs: `/aws/lambda/*`
- Error patterns and exception tracking

## Cost Optimization

### Current Costs
- ECS Fargate: Pay per vCPU-hour
- Lambda: Pay per invocation + duration
- DynamoDB: On-demand capacity (pay per request)
- S3: Storage + request costs
- CloudWatch Logs: Ingestion + storage costs

### Optimization Strategies
- Lambda cold start optimization
- DynamoDB query pattern optimization
- S3 lifecycle policies for old data
- CloudWatch log retention policies

## Security

### Authentication
- JWT-based authentication via ONA Platform
- Shared secret in SSM: `/zorora/prod/ona-jwt-secret`
- Tier-based subscription gating

### Authorization
- DynamoDB-based user lookups
- Role-based access control (RBAC)
- API key validation for external services

### Data Protection
- SSM parameters for secrets (encrypted)
- S3 bucket policies for access control
- DynamoDB encryption at rest
- TLS in transit for all API calls

## Disaster Recovery

### Backups
- DynamoDB: Point-in-time recovery (PITR) enabled
- S3: Versioning enabled on critical buckets
- ECR: Image retention policies

### Failover
- Multi-AZ deployment in af-south-1
- Cross-region replication for critical data (us-east-1)
- Blue-green deployment strategy

## Regional Architecture

### Primary Region: af-south-1 (Cape Town)
- ECS Fargate cluster
- Lambda functions
- S3 buckets
- CloudWatch logs
- SSM parameters

### Secondary Region: us-east-1 (N. Virginia)
- DynamoDB tables (newsroom_articles, ONA platform)
- S3 buckets (weather data, analytics)
- ML model training infrastructure

### Cross-Region Dependencies
- ECS af-south-1 → DynamoDB us-east-1
- Lambda af-south-1 → S3 us-east-1
- Global training service → us-east-1 resources

## Data Contracts Summary

### Newsroom Article Schema
```json
{
  "url": "string (required)",
  "title": "string (required)",
  "source": "string (required)",
  "pub_date": "ISO8601 timestamp (required)",
  "collection_date": "ISO8601 timestamp (required)",
  "content_length": "number (required)",
  "core_topics": ["string"] (required)",
  "special_tags": ["string"] (optional)",
  "matched_keywords": ["string"] (optional)",
  "continents": ["string"] (optional)",
  "countries": ["string"] (optional)",
  "feed_url": "string (optional)",
  "base_url": "string (optional)",
  "description": "string (optional)",
  "full_content": "string (optional)"
}
```

### User Subscription Schema
```json
{
  "user_id": "UUID (required)",
  "email": "string (required)",
  "subscriptions": [
    {
      "product": "zorora",
      "tier": "explorer|professional|enterprise",
      "started_at": "ISO8601 timestamp",
      "stripe_subscription_id": "string"
    }
  ],
  "usage": {
    "zorora_research_queries": "number",
    "zorora_queries_reset_at": "ISO8601 timestamp"
  }
}
```

## Maintenance

### Regular Tasks
- Monitor CloudWatch logs for errors
- Review Lambda cold start metrics
- Check DynamoDB capacity usage
- Verify SSM parameter rotation
- Update task definitions for deployments

### On-Call Procedures
- ECS service rollback
- Lambda function rollback
- DynamoDB table scaling
- S3 bucket access troubleshooting
- SSM parameter updates

## Related Documentation

- `ARCHITECTURE.md`: Application architecture and design
- `DEPLOYMENT_CHECKLIST.md`: Deployment procedures
- `docs/newsroom_dynamodb_design.md`: DynamoDB schema details
- `docs/newsroom_lambda_iam_update.md`: Lambda IAM policies
- `docs/newsroom_scraper_dynamodb_update.md`: Scraper integration
