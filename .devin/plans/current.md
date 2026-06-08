# Plan Draft

## Objective
Remove all S3 usage from the imported newsroom scraper, making it DynamoDB-only by dropping HTML index generation to S3 and removing S3 client initialization and upload helpers.

## Scope
Files/functions to modify in this phase:
- `infra/lambda/newsroom_scraper/news_scraper.py` (remove S3 client init, upload helpers, and HTML index S3 writes; drop HTML index generation from main or redirect to local)

Functions expected to be modified:
- `s3_client` initialization (remove or comment)
- `upload_to_s3_if_not_exists` (remove or comment)
- `exists_in_s3` (remove or comment)
- `url_already_processed` (remove or comment)
- `add_processed_url` (remove or comment)
- `get_s3_manifest` (remove or comment)
- `generate_date_html_index` (remove S3 write calls; either remove function or redirect to local filesystem)
- `generate_master_html_index` (remove S3 write calls; either remove function or redirect to local filesystem)
- `main` (remove calls to HTML index generators or redirect to local filesystem)

Repo-local helpers expected to be reused, not duplicated:
- `tools.research.newsroom_dynamodb.insert_article`
- `tools.research.newsroom_dynamodb.fetch_articles_by_date_range`
- `tools.research.article_tagger.tag_article`

Out of scope for this phase unless separately approved:
- changing the web app to serve static HTML
- updating Lambda IAM permissions (that’s an infra task)
- updating ECS task definition environment variables (that’s an infra task)

## Success Criteria
- The imported scraper initializes no S3 client.
- The imported scraper contains no calls to `upload_to_s3_if_not_exists` or S3 `put_object`.
- `main()` no longer calls `generate_date_html_index` or `generate_master_html_index` (or they are redirected to local filesystem).
- The scraper still uses DynamoDB for article ingestion (no regression to write-path migration).
- Existing scraper write-path tests remain green.

## Justification
Option B was chosen: remove S3 entirely from the scraper. The scraper’s only remaining S3 usage is HTML index output, which is unnecessary since the web app serves newsroom data. Removing S3 entirely simplifies the scraper, removes S3 permissions from the Lambda IAM role, and aligns the scraper with the DynamoDB-only runtime serving already completed.

## Implementation Plan
1. Remove or comment the S3 client initialization (`s3_client = boto3.client(...)`).
2. Remove or comment the S3 upload helpers (`upload_to_s3_if_not_exists`, `exists_in_s3`, `url_already_processed`, `add_processed_url`, `get_s3_manifest`).
3. Remove the S3 `put_object` calls from `generate_date_html_index` and `generate_master_html_index`.
4. Either remove the HTML index generator functions from `main()` or redirect them to write to local filesystem (e.g., `/tmp/` for Lambda).
5. Validate the scraper write-path tests still pass (they already mock S3, so this should be green).
6. Run a quick import check to ensure the scraper still loads without boto3 S3 client errors.

## Validation
- Run `pytest tests/test_newsroom_scraper_write_contract.py -q` (should stay green; tests mock S3).
- Run a quick import check to ensure the scraper module loads without boto3 S3 client errors.
- Regression check: run the broader newsroom regression suite to ensure no side effects.

## Objective Verification
We will verify the objective by demonstrating that:
1. the imported scraper contains no S3 client initialization or S3 upload calls;
2. `main()` no longer calls HTML index generators that write to S3;
3. the scraper still uses DynamoDB for article ingestion (write-path tests stay green).
