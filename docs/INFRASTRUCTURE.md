# Zorora Infrastructure Documentation

## A User's Journey Through Zorora

To understand Zorora's infrastructure, let's follow what happens when a user runs a research query. This journey will show you how all the pieces connect.

### Step 1: User Lands on Zorora

A user in Johannesburg opens their browser and navigates to Zorora. Their request hits **CloudFront CDN** (optional, for caching), which routes to the **ECS Fargate cluster** in Cape Town (`af-south-1`).

**Why ECS Fargate?** We chose serverless containers because they scale automatically without managing servers. When traffic spikes, AWS spins up more containers. When it's quiet, we pay for almost nothing.

### Step 2: The Application Wakes Up

The Flask application inside the ECS container needs to know how to authenticate users and which external APIs to call. It doesn't hardcode these secrets - that would be a security nightmare.

Instead, the container reaches out to **SSM Parameter Store** in the same region and fetches:
- API keys for EIA, OpenEI, Brave Search, Congress.gov
- JWT secrets for authentication
- HuggingFace tokens for AI models

**Why SSM?** Secrets management as a service. It encrypts secrets at rest, provides audit trails, and allows rotation without redeploying code.

### Step 3: User Authentication

Before the user can run research, Zorora needs to know who they are and whether they've paid. The application calls the **`ona-user-auth` Lambda function**, which:
- Validates the JWT token from the user's browser
- Looks up the user in **DynamoDB** (in `us-east-1`)
- Checks their subscription tier (Explorer, Professional, Enterprise)
- Returns their usage quota

**Why cross-region to us-east-1?** The ONA Platform (our parent system) already has all user data in Virginia. Rather than migrate everything, we accept the 150ms latency for these infrequent auth checks.

### Step 4: Research Query Execution

Now the user submits a query: "What's the current state of solar energy adoption in South Africa?"

The ECS container orchestrates a multi-source search:

1. **Newsroom data**: Pulls recent articles from `newsroom_articles` table in DynamoDB (us-east-1)
2. **Web search**: Uses the Brave Search API key (from SSM) to fetch current web results
3. **Regulatory data**: Calls EIA and OpenEI APIs using keys from SSM
4. **Synthesis**: Sends all sources to the reasoning model for synthesis

**Why DynamoDB for newsroom?** We need fast, indexed queries by date, topic, and source. DynamoDB's Global Secondary Indexes let us query articles from the last 90 days in under 100ms - far faster than scanning S3.

### Step 5: Background Data Refresh

While users sleep, the system keeps data fresh. Every 6 hours, an **EventBridge rule** triggers the **`ona-newsroom-sync-prod` Lambda**:

1. Scrapes news articles from RSS feeds
2. Tags articles with topics using ML
3. Writes to `newsroom_articles` in DynamoDB (us-east-1)
4. Exports a JSON file to S3 for legacy compatibility

**Why Lambda for background tasks?** We only pay when the function runs. A 5-minute execution every 6 hours costs pennies per month, compared to a 24/7 server.

### Step 6: Monitoring and Debugging

Every component logs to **CloudWatch Logs**:
- ECS container logs go to `/ecs/ona-zorora-prod`
- Lambda logs go to `/aws/lambda/function-name`
- We can search all logs for errors, trace request IDs across services, and set up alerts

**Why CloudWatch?** It's AWS-native, requires no setup, and integrates with everything. When something breaks, we have a single place to look.

---

Now that you've seen the journey, let's dive into each component in detail.

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

## The Compute Layer: ECS Fargate

The ECS Fargate cluster is the heart of Zorora - this is where the Flask web application runs, handling user requests, research queries, and API calls. When a user visits Zorora, they're hitting this cluster.

### How ECS Connects to Everything

The ECS container doesn't run in isolation - it reaches out to multiple AWS services:

1. **SSM Parameter Store** (same region): On startup, the container fetches API keys and secrets. This happens via the `_get_ssm_parameter()` function in `config.docker.py`, which pulls from `/zorora/prod/*` paths.
2. **DynamoDB** (us-east-1): Cross-region calls to fetch user data, news articles, and subscription info. The 150ms latency is acceptable for these read-heavy operations.
3. **S3** (af-south-1): Fetches the newsroom export file and stores any user-generated content.
4. **External APIs**: Uses the SSM-fetched keys to call EIA, OpenEI, Brave Search, and other external services.

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

### Troubleshooting ECS Issues

**Problem:** Container won't start
- Check CloudWatch logs: `/ecs/ona-zorora-prod`
- Verify SSM parameters are accessible
- Confirm ECR image exists and is accessible

**Problem:** High latency
- Check cross-region DynamoDB calls (should be <200ms)
- Verify external API response times
- Review CloudWatch metrics for CPU/memory throttling

---

With the compute layer established, let's look at the background processes that keep data fresh.

## Background Processing: Lambda Functions

While ECS handles user-facing requests, Lambda functions handle background tasks. These are event-driven - they only run when triggered, which makes them cost-effective for sporadic workloads.

### Zorora-Specific Lambdas

These functions directly support Zorora's research capabilities.

#### 1. `ona-newsroom-sync-prod` - The News Scraper

This is the most important Lambda for Zorora. Every 6 hours, it wakes up and:

1. Scrapes news articles from RSS feeds (energy, solar, policy sources)
2. Uses ML to tag articles with topics (energy, solar, policy, etc.)
3. Writes tagged articles to `newsroom_articles` in DynamoDB (us-east-1)
4. Exports a JSON file to S3 for legacy compatibility

**Why Lambda?** News scraping happens 4 times per day. Running a 24/7 server would cost ~$50/month. Lambda costs pennies.

**Configuration:**
- **Runtime:** Python 3.9
- **Handler:** `lambda_news_scraper.lambda_handler`
- **Role:** `news-scraper-role`
- **Trigger:** EventBridge rule `ona-newsroom-sync-prod` (scheduled)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-newsroom-sync-prod` (85 KB stored)
- **S3 Output:** `s3://news-collection-website/zorora-export/articles.json`
- **IAM Permissions:** S3 (read/write), DynamoDB (newsroom_articles table)

**Troubleshooting:**
- If articles aren't updating: Check EventBridge rule is active
- If DynamoDB writes fail: Verify IAM role has DynamoDB permissions
- If scraping is slow: Check RSS feed response times

### ONA Platform Lambdas (Shared Infrastructure)

These functions are shared across ONA Platform products, including Zorora. They handle user management, authentication, and platform-wide services.

#### Authentication & User Management

**2. `ona-user-auth`** - Validates JWT tokens and checks user permissions
- **Runtime:** Python 3.9
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-user-auth` (206 KB stored)
- **Purpose:** JWT token validation and user authentication
- **Environment:** `JWT_SECRET`, `USERS_TABLE`, `ROLES_TABLE`, `GROUPS_TABLE`

**3. `ona-user-management`** - User CRUD operations
- **Runtime:** Python 3.9
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-user-management` (527 KB stored)
- **Purpose:** User CRUD operations and profile management
- **Environment:** `USERS_TABLE`, `CUSTOMERS_TABLE`, `JWT_SECRET`

**4. `ona-customer-listing`** - Organization management
- **Runtime:** Python 3.9
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-customer-listing`
- **Purpose:** Customer listing and management
- **Environment:** `CUSTOMERS_TABLE`, `USERS_TABLE`, `ROLES_TABLE`, `GROUPS_TABLE`

**5. `ona-role-management`** - Permission management
- **Runtime:** Python 3.9
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-role-management` (237 KB stored)
- **Purpose:** Role and permission management
- **Environment:** `ROLES_TABLE`, `GROUPS_TABLE`, `JWT_SECRET`

**6. `ona-skin-management`** - UI theming
- **Runtime:** Python 3.9
- **Timeout:** 30 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-skin-management` (968 KB stored)
- **Purpose:** UI skin/theme management
- **Environment:** `SKINS_TABLE`, `JWT_SECRET`

**Why shared infrastructure?** These functions serve multiple ONA products. Centralizing them reduces duplication and ensures consistent user management across products.

### Data Processing Lambdas

These functions handle energy data processing for solar installations and weather forecasting. They're part of the broader ONA Platform but provide data that Zorora may reference.

#### Weather & Solar Data

**7. `ona-weatherCache-prod`** - Weather data caching
- **Runtime:** Docker (Image)
- **Trigger:** API Gateway
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-weatherCache-prod` (15 MB stored)
- **Dead Letter Queue:** `ona-weatherCache-dlq` (SQS)
- **Purpose:** Weather data caching and API proxy
- **Environment:** `WEATHER_CACHE_TABLE`, `LOCATIONS_TABLE`, `VISUAL_CROSSING_API_KEY`

**8. `globalTrainingService`** - ML model training
- **Runtime:** Docker (Image)
- **Timeout:** 900 seconds
- **Memory:** 3008 MB
- **Log Group:** `/aws/lambda/globalTrainingService`
- **Purpose:** ML model training and inference
- **Environment:** `INPUT_BUCKET`, `OUTPUT_BUCKET`, `WEATHER_BUCKET`

#### Terminal Device Management

These functions ingest data from solar inverters (Huawei, Enphase) for monitoring solar installations.

**9. `ona-terminalApi-prod`** - Terminal device API
- **Runtime:** Docker (Image)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-terminalApi-prod` (22 MB stored)
- **Purpose:** Terminal device API for solar installations
- **Environment:** Multiple terminal-related tables

**10. `ona-huaweiRealTime-prod`** - Huawei real-time data
- **Runtime:** Docker (Image)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-huaweiRealTime-prod` (398 MB stored)
- **Purpose:** Huawei inverter real-time data ingestion

**11. `ona-huaweiHistorical-prod`** - Huawei historical data
- **Runtime:** Docker (Image)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-huaweiHistorical-prod` (7.5 MB stored)
- **Purpose:** Huawei inverter historical data ingestion

**12. `ona-enphaseHistorical-prod`** - Enphase historical data
- **Runtime:** Docker (Image)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-enphaseHistorical-prod`
- **Purpose:** Enphase inverter historical data ingestion

**13. `ona-interpolationService-prod`** - Data interpolation
- **Runtime:** Docker (Image)
- **Timeout:** 300 seconds
- **Memory:** 512 MB
- **Log Group:** `/aws/lambda/ona-interpolationService-prod` (126 MB stored)
- **Purpose:** Data interpolation for missing readings

**Why Docker runtime for these?** These functions have complex dependencies (ML libraries, device drivers) that don't fit in the standard Lambda runtime. Docker allows us to package everything.

---

With background processing covered, let's examine where all this data lives.

## The Data Layer: DynamoDB

DynamoDB is our primary database. It's a NoSQL key-value store that scales horizontally and provides single-digit millisecond latency at any scale.

### Why DynamoDB in us-east-1?

You might wonder: if ECS is in Cape Town, why is DynamoDB in Virginia? The answer is history - the ONA Platform already had all user data in DynamoDB us-east-1. Rather than migrate terabytes of data, we accept the 150ms cross-region latency for these read-heavy operations.

For the newsroom, we chose DynamoDB over S3 because we need fast, indexed queries. S3 requires listing objects (slow) or maintaining a separate index (complex). DynamoDB's Global Secondary Indexes let us query by date, topic, or source in under 100ms.

### Zorora Tables (us-east-1)

#### `newsroom_articles` - The News Database

This table stores all news articles that the research system can reference. It's the backbone of Zorora's newsroom feature.

**Primary Key Design:**
- `PK` (Partition Key): `ARTICLE#{url_hash}` - MD5 hash of article URL for deduplication
- `SK` (Sort Key): `DATE#{date}` - Publication date for time-based sorting

**Why this key design?** The URL hash ensures we never store the same article twice (deduplication). The date sort key lets us quickly query "articles from the last 90 days" without scanning the entire table.

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

**Global Secondary Indexes (GSIs):**

These indexes enable different query patterns without duplicating data:

1. **`date-index`**: PK=`DATE#{date}`, SK=`PUB#{timestamp}`
   - Use case: "Show me articles from June 1-15, 2026"
   - Performance: ~50ms for 90-day range

2. **`topic-index`**: PK=`TOPIC#{topic}`, SK=`DATE#{date}`
   - Use case: "Show me all articles about solar energy"
   - Performance: ~30ms for topic query

3. **`source-index`**: PK=`SOURCE#{source}`, SK=`DATE#{date}`
   - Use case: "Show me articles from Reuters"
   - Performance: ~30ms for source query

4. **`collection-date-index`**: PK=`COLLECTED#{date}`, SK=`PUB#{timestamp}`
   - Use case: "Show me articles scraped today"
   - Performance: ~30ms for collection date query

**Data Contract:**
- All dates in ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- URL hashes use MD5 for deduplication
- Topic tags use controlled vocabulary from article_tagger
- Content stored directly in DynamoDB (no S3 dependency)

**Troubleshooting:**
- If queries are slow: Check GSI provisioned capacity (should be on-demand)
- If articles are missing: Verify Lambda has DynamoDB write permissions
- If duplicates appear: Check MD5 hash collision (extremely rare)

### ONA Platform Tables (us-east-1)

These tables are shared across ONA Platform products. Zorora reads from them but doesn't write.

#### `ona-platform-users` - User Authentication & Subscriptions

This table stores user accounts, subscriptions, and usage quotas. When a user logs in, Zorora queries this table to check their subscription tier and remaining queries.

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

**Query Pattern:**
- Get user by ID: `GetItem` (single read, ~5ms)
- Update usage counter: `UpdateItem` (atomic increment, ~10ms)
- Check subscription tier: Read from `subscriptions` list

#### Other ONA Tables

These tables support the broader ONA Platform ecosystem:

- `ona-platform-customers`: Customer organization data
- `ona-platform-roles`: Role definitions and permissions
- `ona-platform-groups`: User groups
- `ona-platform-skins`: UI theme configurations
- `ona-platform-locations`: Geographic location data
- `ona-platform-weather-cache`: Weather data cache
- `ona-platform-terminal-*`: Terminal device management tables
- `ona-platform-ml-*`: ML model registry and results

**Why read-only access?** Zorora doesn't manage these tables - they're owned by the ONA Platform. We only read user data for authentication and subscription checks.

---

With the database layer covered, let's look at object storage in S3.

## Object Storage: S3 Buckets

S3 (Simple Storage Service) is our object storage layer. It's used for files that don't need the indexed querying capabilities of DynamoDB - things like exports, static assets, and large datasets.

### Why S3?

S3 is incredibly cheap for storage ($0.023/GB/month) and provides 99.999999999% durability. It's perfect for:
- Static files that don't change often
- Large datasets that don't need indexing
- Exports and backups
- ML model artifacts

### Zorora Buckets (af-south-1)

#### `news-collection-website` - The News Export Bucket

This bucket serves two purposes: the primary news export file for Zorora, and legacy storage for the news scraper.

**Purpose:** News article storage and exports

**Key Prefixes:**
- `zorora-export/articles.json`: Zorora newsroom export file (primary)
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

**Why both S3 and DynamoDB?** We're in transition. Originally, news was stored only in S3. We migrated to DynamoDB for faster queries, but kept the S3 export for backward compatibility with systems that haven't migrated yet.

**Troubleshooting:**
- If export file is outdated: Check Lambda is writing to S3
- If file is inaccessible: Verify bucket policy allows public read
- If file is too large: Consider pagination or date range filtering

#### `ona-zorora-prod-user-state-migrate`
**Purpose:** User state migration (temporary)

This bucket was used during a migration and can be deleted once confirmed successful.

### ONA Platform Buckets (af-south-1)

These buckets support the broader ONA Platform ecosystem.

#### `ona-platform`
**Purpose:** ONA platform static assets and data

#### `ona-terminal`
**Purpose:** Terminal device data and logs

#### `ona-cloudfront-logs`
**Purpose:** CloudFront access logs

#### `ona-edge-compute`
**Purpose:** Edge computing artifacts

### Data Processing Buckets (us-east-1)

These buckets support ML training and solar analytics - part of the broader ONA Platform.

#### `visualcrossing-city-database`
**Purpose:** Weather data database

#### `sa-api-client-input`
**Purpose:** Solar analytics API input data

#### `sa-api-client-output`
**Purpose:** Solar analytics API output data

---

With storage covered, let's look at how we monitor and debug all these components.

## Monitoring: CloudWatch Logs

CloudWatch Logs is our centralized logging solution. Every component - ECS containers, Lambda functions, API Gateway - writes logs here. When something breaks, this is where we look.

### Why CloudWatch?

It's AWS-native, requires no setup, and integrates with everything. We can:
- Search all logs for errors across services
- Trace a single request ID through multiple components
- Set up metric filters for alerting
- Create dashboards for operational visibility

### ECS Log Groups

#### `/ecs/ona-zorora-prod` - The Application Logs
- **Region:** af-south-1
- **Stored Bytes:** 81 MB
- **Retention:** Default (never expire)
- **Purpose:** Zorora application logs
- **Streams:** Per-container instance logs

**What to look for:**
- Python exceptions and stack traces
- External API call failures (EIA, OpenEI, Brave)
- Cross-region DynamoDB timeouts
- User authentication errors

**Common issues:**
- `SSMParameterNotFound`: SSM parameter missing or misnamed
- `ProvisionedThroughputExceededException`: DynamoDB capacity exhausted
- `ConnectionError`: External API down or rate-limited

#### `/ecs/scraper` - Legacy Scraper Logs
- **Region:** af-south-1
- **Stored Bytes:** 5.9 MB
- **Retention:** 14 days
- **Purpose:** Legacy scraper logs

This can be deprecated once we fully migrate to Lambda-based scraping.

### Lambda Log Groups (af-south-1)

Lambda logs are grouped by function. Each invocation creates a log stream with the request ID.

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

**Troubleshooting Lambda Logs:**
- If Lambda times out: Check duration vs timeout setting
- If Lambda fails to start: Check IAM role permissions
- If Lambda has cold starts: Consider provisioned concurrency

---

With monitoring covered, let's look at how we manage secrets and configuration.

## Secrets Management: SSM Parameters

SSM Parameter Store is our secrets vault. Instead of hardcoding API keys in code or environment variables, we fetch them at runtime from SSM. This is critical for security - if code is leaked, secrets aren't exposed.

### Why SSM Parameter Store?

- **Security**: Secrets are encrypted at rest using AWS KMS
- **Audit trail**: Every parameter access is logged
- **Rotation**: We can rotate secrets without redeploying code
- **Granular access**: IAM policies control who can read which parameters
- **Cross-service sharing**: Multiple services can share the same secret

### How It Works

When the ECS container starts, the `config.docker.py` file calls `_get_ssm_parameter()` for each secret:

```python
def _get_ssm_parameter(param_name: str, region: str = "af-south-1") -> str:
    client = boto3.client('ssm', region_name=region)
    response = client.get_parameter(Name=param_name, WithDecryption=True)
    return response['Parameter']['Value']
```

This happens once at startup, so there's no per-request overhead.

### Zorora Parameters (af-south-1)

#### API Keys - External Service Access

These keys enable Zorora to call external APIs for research data:

- `/zorora/prod/eia-api-key`: EIA Open Data API key (US energy statistics)
- `/zorora/prod/openei-api-key`: OpenEI Utility Rates API key (electricity rates)
- `/zorora/prod/brave-search-api-key`: Brave Search API key (web search)
- `/zorora/prod/congress-gov-api-key`: Congress.gov API key (US legislation)
- `/zorora/prod/core-api-key`: Core API key (internal service)
- `/zorora/prod/fred-api-key`: FRED Economic Data API key (economic indicators)
- `/zorora/prod/hf-token`: HuggingFace API token (AI models)

**What happens if a key is missing?** The application logs a warning and continues with empty values. The research system gracefully handles missing external data sources.

#### Secrets - Authentication

- `/zorora/prod/newsroom-jwt-token`: Newsroom JWT token (deprecated)
- `/zorora/prod/ona-jwt-secret`: ONA Platform JWT secret (shared with ONA Platform)

**Why shared JWT secret?** Zorora validates tokens issued by the ONA Platform. Both systems need the same secret to verify signatures.

### ONA Platform Parameters (af-south-1)

These parameters are shared across ONA Platform products:

- `/ona-platform/prod/global-training-api-endpoint`: Global training API endpoint
- `/ona-platform/prod/global-training-api-token`: Global training API token

**Troubleshooting:**
- If SSM fetch fails: Check IAM role has `ssm:GetParameter` permission
- If parameter is missing: Verify parameter name matches exactly
- If decryption fails: Check KMS key permissions

---

With secrets managed, let's look at how we schedule background tasks.

## Scheduling: EventBridge Rules

EventBridge (formerly CloudWatch Events) is our cron job scheduler. It triggers Lambda functions on schedules or in response to events.

### Why EventBridge?

- **Serverless**: No servers to manage
- **Reliable**: Built-in retry logic and dead-letter queues
- **Flexible**: Supports cron expressions, rate expressions, and event patterns
- **Global**: Can trigger cross-region Lambda functions

### Zorora Rules

#### `ona-newsroom-sync-prod` - The News Scraping Schedule

This rule triggers the news scraper Lambda every 6 hours to keep the newsroom fresh.

- **Schedule:** Rate-based (every 6 hours)
- **Target:** `ona-newsroom-sync-prod` Lambda
- **Purpose:** Trigger news scraping and export

**Why 6 hours?** News sources typically update 2-4 times per day. More frequent scraping wastes money; less frequent misses breaking news.

**Troubleshooting:**
- If Lambda isn't triggering: Check EventBridge rule is enabled
- If schedule is off: Verify timezone (EventBridge uses UTC)
- If Lambda fails: Check CloudWatch logs for Lambda errors

---

With scheduling covered, let's look at access control through IAM roles.

## Access Control: IAM Roles

IAM (Identity and Access Management) roles define what each component can do. The principle of least privilege applies - each role has only the permissions it needs.

### Why IAM Roles?

- **Security**: No long-term credentials needed
- **Auditability**: Every action is logged with the role identity
- **Rotation**: Temporary credentials automatically rotate
- **Granularity**: Different roles for different services

### Zorora Roles

#### `news-scraper-role` - News Scraper Permissions

This role allows the news scraper Lambda to write to S3 and DynamoDB.

- **Policies:** `news-scraper-policy`
- **Permissions:**
  - S3: `news-collection-website` (read/write)
  - DynamoDB: `newsroom_articles` (PutItem, GetItem, Query, Scan, UpdateItem)

**Why these permissions?** The scraper needs to read RSS feeds (not via SSM), write articles to DynamoDB, and export to S3. It doesn't need to delete or manage other resources.

### ONA Platform Roles

#### `ona-lambda-*-role` (various)

Each Lambda function has its own role with minimal permissions:

- **Policies:** Service-specific policies
- **Permissions:** DynamoDB, S3, SQS, CloudWatch Logs

**Why per-function roles?** If one Lambda is compromised, the attacker only has access to that function's resources, not the entire platform.

**Troubleshooting:**
- If Lambda fails with "AccessDenied": Check IAM role has required permissions
- If role can't assume: Check trust policy allows Lambda service
- If permissions are too broad: Review and restrict to least privilege

---

With access control covered, let's look at the API layer.

## The API Layer: API Gateway

API Gateway is the front door for our REST APIs. It handles authentication, rate limiting, and routing requests to the appropriate backend (ECS or Lambda).

### Why API Gateway?

- **Security**: Built-in authentication and authorization
- **Throttling**: Rate limiting prevents abuse
- **Caching**: Reduces backend load for repeated requests
- **Monitoring**: Built-in metrics and logging
- **Versioning**: Multiple API versions can coexist

### Zorora API

**Region:** af-south-1

**Endpoints:**
- `/api/research/*`: Deep research endpoints (ECS backend)
- `/api/auth/*`: Authentication endpoints (Lambda backend)
- `/api/regulatory/*`: Regulatory data endpoints (ECS backend)
- `/api/settings/*`: User settings endpoints (ECS backend)

**Authentication:** JWT tokens validated against ONA Platform secret

### ONA Platform API

**Region:** af-south-1

**Endpoints:** User management, terminal API, weather cache

**Authentication:** Shared JWT validation with Zorora

**Troubleshooting:**
- If API returns 401: Check JWT token is valid and not expired
- If API returns 403: Check user has required permissions
- If API returns 500: Check backend service logs

---

With the API layer covered, let's look at how we deploy code changes.

## Deployment: How Code Gets to Production

When we make changes to Zorora, we need a reliable way to get them to production without downtime. Our deployment pipeline uses Docker containers and ECS for zero-downtime deployments.

### Why This Deployment Strategy?

- **Zero downtime**: ECS gradually replaces old containers with new ones
- **Rollback capability**: We can instantly revert to the previous version
- **Immutable infrastructure**: Each deployment is a new container image
- **Audit trail**: Every deployment is tracked with commit hashes

### Build Process

1. **Code committed to GitHub**: Developer pushes changes to main branch
2. **Docker image built**: We build from `config.docker.py` which includes production configuration
3. **Image pushed to ECR**: `905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora:prod-{commit}`
4. **Task definition updated**: We create a new task definition with the new image tag
5. **ECS service updated**: ECS gradually replaces containers with the new task definition

### Deployment Artifacts

- `task-def-*.json`: ECS task definition templates
- `DEPLOYMENT_CHECKLIST.md`: Step-by-step deployment procedures
- `config.docker.py`: Production configuration with SSM integration

### Troubleshooting Deployments

**Problem:** Deployment fails to start
- Check ECR image exists and is accessible
- Verify task definition syntax is valid
- Review CloudWatch logs for container startup errors

**Problem:** Health checks failing
- Check if application binds to correct port
- Verify health check endpoint is responding
- Review resource limits (CPU/memory)

**Problem:** Need rollback
- Use previous task definition revision
- Force new deployment with old image
- Monitor rollback progress in ECS console

---

With deployment covered, let's look at how we monitor the system in production.

## Production Monitoring

Monitoring is how we know the system is healthy. We use CloudWatch for metrics, logs, and alerting.

### CloudWatch Metrics

We track these key metrics:

- **ECS CPU/Memory utilization**: Detect resource exhaustion
- **Lambda invocation counts and errors**: Monitor background task health
- **DynamoDB read/write capacity**: Catch throttling before it affects users
- **S3 request counts**: Track storage access patterns

### Log Analysis

- **ECS logs**: `/ecs/ona-zorora-prod` - Application errors and performance
- **Lambda logs**: `/aws/lambda/*` - Background task failures
- **Error patterns**: We set up metric filters to count specific errors

### Alerting Strategy

We don't have automated alerts configured yet, but we should set up:
- Error rate thresholds (e.g., >5% error rate triggers alert)
- Latency thresholds (e.g., >2s average response time)
- Resource exhaustion (e.g., >80% CPU utilization)

---

With monitoring covered, let's look at cost optimization.

## Cost Optimization

AWS costs can spiral if not managed. We use serverless services to pay only for what we use, but we still need to optimize.

### Current Cost Structure

- **ECS Fargate**: Pay per vCPU-hour (~$0.04/vCPU-hour)
- **Lambda**: Pay per invocation + duration (~$0.0000002/100ms)
- **DynamoDB**: On-demand capacity (~$1.25/million read units)
- **S3**: Storage + request costs (~$0.023/GB/month)
- **CloudWatch Logs**: Ingestion + storage costs (~$0.50/GB ingested)

### Optimization Strategies

**Lambda cold start optimization:**
- Keep functions warm with provisioned concurrency (if needed)
- Optimize package size to reduce initialization time
- Use appropriate memory allocation (not too high, not too low)

**DynamoDB query optimization:**
- Use GSIs instead of scans
- Filter at the server side with QueryFilter
- Consider caching frequently accessed items

**S3 lifecycle policies:**
- Move old logs to Glacier after 30 days
- Delete temporary files after 7 days
- Use intelligent tiering for infrequently accessed data

**CloudWatch log retention:**
- Set 7-day retention for debug logs
- Set 30-day retention for audit logs
- Archive old logs to S3 for long-term storage

---

With costs covered, let's look at security.

## Security

Security is paramount - we handle user data, API keys, and sensitive research data. Our security strategy uses defense in depth.

### Authentication

**JWT-based authentication via ONA Platform:**
- Users receive JWT tokens from ONA Platform
- Zorora validates tokens using shared secret from SSM
- Tokens include user ID, subscription tier, and expiration

**Shared secret in SSM:** `/zorora/prod/ona-jwt-secret`

**Tier-based subscription gating:**
- Explorer: 10 queries/month
- Professional: Unlimited queries
- Enterprise: Unlimited queries + priority support

### Authorization

**DynamoDB-based user lookups:**
- User data stored in `ona-platform-users` table
- Subscription tier determines feature access
- Usage counters enforce quota limits

**Role-based access control (RBAC):**
- IAM roles define what each component can do
- Lambda functions have minimal required permissions
- ECS containers have least-privilege access

**API key validation for external services:**
- Each external API has its own key in SSM
- Keys are rotated periodically
- Compromised keys can be revoked without redeployment

### Data Protection

**SSM parameters for secrets (encrypted):**
- All secrets use AWS KMS encryption
- Encryption keys use customer-managed CMKs
- Access to secrets is logged

**S3 bucket policies for access control:**
- Public read only for export file
- Private write access for Lambda functions
- Bucket policies restrict by IP and IAM role

**DynamoDB encryption at rest:**
- All tables use AWS-managed encryption keys
- Point-in-time recovery enabled for critical tables
- Encryption is transparent to applications

**TLS in transit for all API calls:**
- All API Gateway endpoints use HTTPS
- DynamoDB connections use TLS
- S3 connections use TLS

---

With security covered, let's look at disaster recovery.

## Disaster Recovery

What happens when things go wrong? We have backup and failover strategies to minimize downtime.

### Backups

**DynamoDB: Point-in-time recovery (PITR) enabled**
- Continuous backups to S3
- Can restore to any point in last 35 days
- No performance impact on production

**S3: Versioning enabled on critical buckets**
- Every write creates a new version
- Can restore deleted or overwritten objects
- Useful for recovering from accidental deletions

**ECR: Image retention policies**
- Keep last 10 image versions
- Allows rollback to previous container images
- Automatic cleanup of old images

### Failover

**Multi-AZ deployment in af-south-1:**
- ECS spans multiple availability zones
- If one AZ fails, others continue serving
- Data is replicated across AZs automatically

**Cross-region replication for critical data (us-east-1):**
- DynamoDB global tables for user data
- S3 cross-region replication for backups
- Can failover to us-east-1 if af-south-1 fails

**Blue-green deployment strategy:**
- Deploy new version alongside old version
- Route traffic gradually to new version
- Instant rollback if issues detected

---

With disaster recovery covered, let's look at our regional architecture.

## Regional Architecture

We use multiple AWS regions for different purposes. This is a deliberate choice based on latency, compliance, and existing infrastructure.

### Primary Region: af-south-1 (Cape Town)

**Why Cape Town?**
- Low latency for African users (our primary market)
- Data residency compliance for South African data
- Closer to energy data sources (Eskom, NERSA, etc.)

**What's here:**
- ECS Fargate cluster (user-facing application)
- Lambda functions (background processing)
- S3 buckets (content storage)
- CloudWatch logs (monitoring)
- SSM parameters (secrets)

### Secondary Region: us-east-1 (N. Virginia)

**Why Virginia?**
- Existing ONA Platform infrastructure
- Better ML training infrastructure (more GPU instances)
- Lower cost for data processing

**What's here:**
- DynamoDB tables (newsroom_articles, ONA platform)
- S3 buckets (weather data, analytics)
- ML model training infrastructure

### Cross-Region Dependencies

**ECS af-south-1 → DynamoDB us-east-1:**
- User authentication and subscription checks
- Newsroom article queries
- Latency: ~150ms (acceptable for these operations)

**Lambda af-south-1 → S3 us-east-1:**
- ML model artifacts for training
- Weather data for forecasting
- Latency: ~200ms (acceptable for background tasks)

**Global training service → us-east-1 resources:**
- ML model training uses us-east-1 GPU instances
- Training data stored in us-east-1 S3
- Models deployed to af-south-1 for inference

---

With regional architecture covered, let's look at our data contracts.

## Data Contracts

Data contracts define the shape of data exchanged between components. They ensure compatibility and prevent breaking changes.

### Newsroom Article Schema

This schema defines what a news article looks like when stored in DynamoDB or exported to S3.

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

**Validation rules:**
- All dates must be ISO 8601 format
- URL must be valid and accessible
- At least one core topic is required
- Content length must be > 0

### User Subscription Schema

This schema defines user subscription data in the ONA Platform.

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

**Validation rules:**
- user_id must be valid UUID
- email must be valid email format
- tier must be one of the three allowed values
- usage counters must be non-negative

---

With data contracts covered, let's look at maintenance procedures.

## Maintenance

Running a production system requires regular maintenance to keep it healthy and secure.

### Regular Tasks

**Daily:**
- Monitor CloudWatch logs for errors
- Check Lambda cold start metrics
- Review DynamoDB capacity usage

**Weekly:**
- Verify SSM parameter rotation
- Review cost anomalies
- Check for security vulnerabilities

**Monthly:**
- Update task definitions for deployments
- Review and optimize CloudWatch log retention
- Audit IAM role permissions

### On-Call Procedures

**ECS service rollback:**
```bash
aws ecs update-service \
  --cluster ona-zorora-prod \
  --service ona-zorora-prod \
  --task-definition ona-zorora-prod:26 \
  --force-new-deployment \
  --region af-south-1
```

**Lambda function rollback:**
- Revert to previous function version in Lambda console
- Or deploy previous code from Git

**DynamoDB table scaling:**
- If on-demand: AWS handles automatically
- If provisioned: Update capacity in console or CLI

**S3 bucket access troubleshooting:**
- Check bucket policy allows required access
- Verify IAM role has S3 permissions
- Test with AWS CLI: `aws s3 ls s3://bucket-name`

**SSM parameter updates:**
```bash
aws ssm put-parameter \
  --name /zorora/prod/eia-api-key \
  --value "new-key-value" \
  --type SecureString \
  --region af-south-1
```

---

## Related Documentation

This document focuses on infrastructure. For other aspects of Zorora, see:

- `ARCHITECTURE.md`: Application architecture and design patterns
- `DEPLOYMENT_CHECKLIST.md`: Step-by-step deployment procedures
- `docs/newsroom_dynamodb_design.md`: DynamoDB schema details and query patterns
- `docs/newsroom_lambda_iam_update.md`: Lambda IAM policies and permissions
- `docs/newsroom_scraper_dynamodb_update.md`: News scraper integration details

---

## Summary

Zorora's infrastructure is designed for:
- **Reliability**: Multi-AZ deployment, automated backups, zero-downtime deployments
- **Security**: Secrets management, encryption at rest and in transit, least-privilege IAM
- **Cost-efficiency**: Serverless services, pay-per-use pricing, optimization strategies
- **Scalability**: Auto-scaling ECS, on-demand DynamoDB, Lambda event-driven processing
- **Observability**: Centralized logging, metrics, and alerting

The multi-region architecture balances latency for African users with existing ONA Platform infrastructure in us-east-1. Every component has a clear purpose, and the data flows are designed to minimize cross-region latency while maintaining data consistency.
