# Lambda IAM Policy Update for DynamoDB

## Current Lambda Configuration

**Function:** `news-scraper`
**Runtime:** Python 3.9
**Handler:** `lambda_news_scraper.lambda_handler`
**Role:** `news-scraper-role`
**Trigger:** EventBridge rule `ona-newsroom-sync-prod`

## Current IAM Policy

The `news-scraper-policy` currently only has S3 permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::news-collection-website",
                "arn:aws:s3:::news-collection-website/*"
            ]
        }
    ]
}
```

## Required IAM Policy Update

Add DynamoDB permissions to the existing policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::news-collection-website",
                "arn:aws:s3:::news-collection-website/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:905418405543:table/newsroom_articles",
                "arn:aws:dynamodb:us-east-1:905418405543:table/newsroom_articles/index/*"
            ]
        }
    ]
}
```

## Deployment Steps

### 1. Update IAM Policy
```bash
aws iam create-policy-version \
  --policy-arn arn:aws:iam::905418405543:policy/news-scraper-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::news-collection-website",
                "arn:aws:s3:::news-collection-website/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:905418405543:table/newsroom_articles",
                "arn:aws:dynamodb:us-east-1:905418405543:table/newsroom_articles/index/*"
            ]
        }
    ]
}' \
  --set-as-default
```

### 2. Update Lambda Code (separate repo)
Apply the patches documented in `docs/newsroom_scraper_dynamodb_patch.py` to the Lambda code.

### 3. Deploy Updated Lambda
Upload the updated Lambda code with the DynamoDB integration.

### 4. Create DynamoDB Table
```bash
python tools/research/newsroom_dynamodb_setup.py
```

### 5. Migrate Existing Data
```bash
python tools/research/migrate_s3_to_dynamodb.py 90 --dry-run
python tools/research/migrate_s3_to_dynamodb.py 90
```

### 6. Verify
- Check CloudWatch logs for Lambda execution
- Verify new articles appear in DynamoDB
- Verify topic diversity in newsroom UI

## EventBridge Trigger

The EventBridge rule `ona-newsroom-sync-prod` triggers the Lambda on a schedule. No changes needed to the trigger - it will continue to work once the Lambda code is updated.
