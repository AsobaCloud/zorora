# Zorora Newsroom DynamoDB Migration - Deployment Checklist

## Status: ✅ Complete

Newsroom has been migrated from S3 to DynamoDB for article storage and serving.

## Architecture Changes

### Before (S3-based)
- Newsroom articles stored in S3 date folders (metadata/content files)
- Static HTML site hosted on S3
- Lambda scraped to S3, then exported to JSON file
- Fargate app fetched from S3 export JSON
- Idempotency via S3 manifest

### After (DynamoDB-based)
- Newsroom articles stored in DynamoDB (newsroom_articles table)
- Web app serves via DynamoDB indexed queries
- Scraper ingests directly to DynamoDB with full_content
- Fargate app fetches from web app's DynamoDB-backed API
- Idempotency via DynamoDB conditional writes
- Static HTML generation removed (local filesystem only)

## What Changed

1. **Newsroom data source**: S3 export JSON → DynamoDB indexed queries
2. **Scraper ingestion**: S3 metadata/content files → DynamoDB with full_content
3. **S3 usage**: Full S3 stack → DynamoDB-only (scraper has no S3 client)
4. **HTML generation**: S3 static site → Local filesystem (removed from serving path)
5. **Fargate integration**: S3 export URL → Web app DynamoDB-backed API endpoint
6. **Fetch time**: ~28 seconds (S3 export) → ~2-3 seconds (DynamoDB)
7. **Cost**: ~$4.70/mo (S3) → ~$0.12/mo (DynamoDB)

## Pre-Deployment Verification

### 1. Verify DynamoDB table exists
```bash
aws dynamodb describe-table \
  --table-name newsroom_articles \
  --region us-east-1
```

### 2. Verify table has articles
```bash
aws dynamodb scan \
  --table-name newsroom_articles \
  --region us-east-1 \
  --max-items 5 \
  --projection-expression 'PK,SK,title,pub_date'
```

### 3. Test DynamoDB-backed newsroom fetch
```bash
curl -s https://zorora-prod-321943930.af-south-1.elb.amazonaws.com/api/news-intel/articles \
  -H 'Content-Type: application/json' \
  -d '{}' | head -c 500
```

## Deployment Steps

### Step 1: Build Docker Image
```bash
cd /Users/shingi/Workbench/zorora

# Build
docker build -t ona-zorora:latest .

# Get ECR login
aws ecr get-login-password --region af-south-1 | \
  docker login --username AWS --password-stdin \
  905418405543.dkr.ecr.af-south-1.amazonaws.com

# Tag with commit hash
COMMIT=$(git rev-parse --short HEAD)
docker tag ona-zorora:latest 905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora:prod-${COMMIT}

# Push
docker push 905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora:prod-${COMMIT}
```

### Step 2: Update Task Definition
Update the task definition JSON with the new image tag and DynamoDB-backed API endpoint:
- Replace `prod-TBD` with the actual commit hash from Step 1
- Set `NEWSROOM_EXPORT_URL` to `https://zorora-prod-321943930.af-south-1.elb.amazonaws.com/api/news-intel/articles`

### Step 3: Register Task Definition
```bash
cd /Users/shingi/Workbench/zorora
aws ecs register-task-definition --cli-input-json file://task-def-updated.json --region af-south-1
```

Note the revision number output (e.g., `revision: 44`)

### Step 4: Update ECS Service
```bash
aws ecs update-service \
  --cluster ona-zorora-prod \
  --service ona-zorora-prod \
  --task-definition ona-zorora-prod:44 \
  --force-new-deployment \
  --region af-south-1
```

Replace `44` with the actual revision number from Step 3.

### Step 5: Verify Deployment
```bash
# Watch service events
aws ecs describe-services \
  --cluster ona-zorora-prod \
  --services ona-zorora-prod \
  --region af-south-1 \
  --query 'services[0].events[:3]'

# Check container logs
aws logs tail /ecs/ona-zorora-prod --region af-south-1 --follow
```

### Step 6: Test Newsroom in UI
1. Open Zorora web interface
2. Check that newsroom loads without errors
3. Verify articles appear in research context
4. Check that full_content is being used in synthesis

## Rollback (if needed)

If issues occur, rollback to previous task definition:

```bash
aws ecs update-service \
  --cluster ona-zorora-prod \
  --service ona-zorora-prod \
  --task-definition ona-zorora-prod:42 \
  --force-new-deployment \
  --region af-south-1
```

## Post-Deployment Cleanup

After confirming success:

1. **Remove S3 export Lambda** (optional, no longer needed):
   ```bash
   aws lambda delete-function \
     --function-name ona-newsroom-sync-prod \
     --region af-south-1
   ```

2. **Delete S3 export files** (optional, after verification):
   ```bash
   aws s3 rm s3://news-collection-website/zorora-export/articles.json --region us-east-1
   ```

## Migration Tooling

### S3 to DynamoDB Migration
To migrate existing S3 articles to DynamoDB:

```bash
# Test with 10 updates first
python tools/research/migrate_s3_to_dynamodb.py 90 --max-updates 10

# Full migration (last 90 days)
python tools/research/migrate_s3_to_dynamodb.py 90
```

### Topic Backfill
To add topic tags to existing DynamoDB articles:

```bash
python tools/research/backfill_topics.py
```

## Commits

- **platform**: `76f0ae2` - feat(newsroom): migrate from S3 to DynamoDB for article storage and serving
- **platform**: `99406b8` - docs: rewrite infrastructure documentation with narrative structure
- **platform**: `9a4f317` - docs: add comprehensive infrastructure documentation with AWS inventory

## Support

If deployment fails:
1. Check CloudWatch logs: `/ecs/ona-zorora-prod`
2. Verify DynamoDB has fresh articles: `aws dynamodb scan --table-name newsroom_articles --region us-east-1 --max-items 5`
3. Verify web app API is accessible: `curl https://zorora-prod-321943930.af-south-1.elb.amazonaws.com/api/news-intel/articles`
