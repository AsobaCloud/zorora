# Zorora Newsroom Fix - Deployment Checklist

## Status: ✅ Ready for Deployment

All code changes are committed. This is a **critical fix** for the newsroom API issue.

## What Changed

1. **Newsroom data source**: API Gateway/S3 export → DynamoDB
2. **Authentication**: JWT token required → None required
3. **Fetch time**: ~28 seconds → ~2-3 seconds
4. **Cost**: ~$4.70/mo → ~$0.12/mo

## Pre-Deployment Verification

### 1. Verify Lambda is running
```bash
aws lambda get-function --function-name ona-newsroom-sync-prod --region af-south-1
```

### 2. Verify newsroom table is reachable
```bash
aws dynamodb scan \
  --table-name newsroom_articles \
  --region us-east-1 \
  --max-items 5 \
  --projection-expression 'PK,SK,title,pub_date'
```

### 3. Test DynamoDB-backed newsroom fetch
```bash
curl -s http://localhost:5000/api/news-intel/articles \
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
Edit `task-def-23.json`:
- Replace `prod-TBD` with the actual commit hash from Step 1
- Example: `"image": "905418405543.dkr.ecr.af-south-1.amazonaws.com/ona-zorora:prod-34d881f"`

### Step 3: Register Task Definition
```bash
cd /Users/shingi/Workbench/zorora
aws ecs register-task-definition --cli-input-json file://task-def-23.json --region af-south-1
```

Note the revision number output (e.g., `revision: 27`)

### Step 4: Update ECS Service
```bash
aws ecs update-service \
  --cluster ona-zorora-prod \
  --service ona-zorora-prod \
  --task-definition ona-zorora-prod:27 \
  --force-new-deployment \
  --region af-south-1
```

Replace `27` with the actual revision number from Step 3.

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
2. Check that newsroom loads without "API unavailable" warning
3. Verify articles appear in research context

## Rollback (if needed)

If issues occur, rollback to previous task definition:

```bash
aws ecs update-service \
  --cluster ona-zorora-prod \
  --service ona-zorora-prod \
  --task-definition ona-zorora-prod:26 \
  --force-new-deployment \
  --region af-south-1
```

## Post-Deployment Cleanup

After confirming success:

1. **Remove SSM parameter** (optional, keeps secrets clean):
   ```bash
   aws ssm delete-parameter \
     --name /zorora/prod/newsroom-jwt-token \
     --region af-south-1
   ```

2. **Delete old task definitions** (optional):
   - task-def-21.json (bad - empty JWT)
   - task-def-22.json (has JWT secret)

## Commits

- **platform**: `ae314d6` - feat: add newsroom-sync Lambda for Zorora S3 export
- **platform**: `1a2718f` - docs: add newsroom-sync architecture documentation
- **zorora**: `c87b4c0` - refactor(newsroom): fetch from S3 export instead of API
- **zorora**: `34d881f` - chore: remove NEWSROOM_JWT_TOKEN dependency

## Support

If deployment fails:
1. Check CloudWatch logs: `/ecs/ona-zorora-prod`
2. Verify Lambda is scraping: `aws logs tail /aws/lambda/ona-newsroom-sync-prod`
3. Verify DynamoDB has fresh articles: `aws dynamodb scan --table-name newsroom_articles --region us-east-1 --max-items 5`
