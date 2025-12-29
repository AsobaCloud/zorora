# End-to-End Validation Plan: Zorora ↔ ONA Platform Integration

## Purpose

This document provides a **complete, one-shot implementable plan** for validating that the full end-to-end workflow between Zorora REPL and the ONA platform `globalTrainingService` Lambda works correctly. This goes beyond connectivity testing to validate actual business logic, state changes, and data consistency.

## ⚠️ Critical Pre-requisite: Phase 0 Hard Gate

**This plan includes Phase 0: Preflight Checks** which validates that the API Gateway + Auth setup is deployed and working.

**Phase 0 is a HARD GATE** - if it fails, the script exits immediately and does NOT proceed to end-to-end validation.

**Why**: End-to-end validation requires:
- API Gateway HTTP API deployed with routes
- Lambda bearer token authentication configured
- Lambda environment variables set correctly
- S3 bucket accessible

If these are not configured, Phase 0 will fail with **clear diagnostic messages** telling you exactly what to fix.

**Before running this plan**, ensure you have:
1. Deployed API Gateway HTTP API
2. Configured Lambda with `USE_BEARER_AUTH=true` and `INTERNAL_API_TOKEN`
3. Verified basic connectivity (run `scripts/validate_zorora_ona_integration.py` first)

**If Phase 0 passes**, then proceed with confidence - the infrastructure is correctly configured.

## Scope

This plan validates:
1. **Read-only operations** return correct data from S3
2. **Mutating operations** correctly modify S3 state
3. **State transitions** follow expected business rules
4. **Audit logging** captures all actions correctly
5. **Error handling** works for invalid inputs
6. **Data consistency** is maintained across operations

## Prerequisites

### Critical Dependency: API Gateway + Auth Setup

**⚠️ THIS PLAN REQUIRES THE API GATEWAY SETUP TO BE DEPLOYED AND WORKING**

Before running this validation, ensure:

1. **API Gateway HTTP API is deployed** with routes configured
2. **Lambda environment variables are set**:
   - `USE_BEARER_AUTH=true`
   - `INTERNAL_API_TOKEN` set from SSM Parameter Store (`/ona-platform/prod/global-training-api-token`)
   - `ENVIRONMENT` set appropriately
   - `OUTPUT_BUCKET` set to `sa-api-client-output`
3. **Lambda `check_authentication` function is active** and enforcing bearer token auth
4. **Basic connectivity validation passes** (see Phase 0 below)

**If these are not configured, Phase 0 will fail with clear diagnostic messages.**

**What Phase 0 Validates**:
- ✅ API Gateway endpoint is reachable (not 404)
- ✅ Bearer token authentication works (not 401/403)
- ✅ Lambda is invoked and processing requests (not routing failure)
- ✅ S3 bucket is accessible

**If Phase 0 Fails**:
1. Review the specific error message
2. Check the diagnostic output (it will tell you exactly what to check)
3. Fix the infrastructure issue
4. Re-run Phase 0
5. Only proceed when Phase 0 passes

**Reference**: The API Gateway setup should follow the deployment plan that configures:
- API Gateway HTTP API with `/prod/api/v1` stage
- Lambda integration with proxy configuration  
- Bearer token authentication enforced in Lambda via `check_authentication`
- Environment variables set from SSM Parameter Store

**Quick Check**: Run the basic connectivity validation script first:
```bash
python3 scripts/validate_zorora_ona_integration.py
```

If Gate 1 passes (endpoints exist), then Phase 0 of this plan should also pass.

### Required Environment Variables

```bash
# ONA Platform API Configuration
export ONA_API_BASE_URL="https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/prod/api/v1"
export ONA_API_TOKEN="<retrieved-from-ssm>"
export ONA_USE_IAM="false"

# AWS Configuration (for S3 setup/cleanup)
export AWS_REGION="af-south-1"
export AWS_ACCESS_KEY_ID="<required-for-s3-operations>"
export AWS_SECRET_ACCESS_KEY="<required-for-s3-operations>"

# S3 Bucket Configuration
export OUTPUT_BUCKET="sa-api-client-output"  # Must match Lambda OUTPUT_BUCKET env var

# Test Configuration
export TEST_CUSTOMER_ID="zorora-e2e-test-$(date +%s)"  # Unique per test run
export TEST_ACTOR="zorora-validation-bot"
```

### Required AWS Permissions

The AWS credentials must have:
- `s3:GetObject` on `sa-api-client-output` bucket
- `s3:PutObject` on `sa-api-client-output` bucket
- `s3:ListObjects` on `sa-api-client-output` bucket
- `s3:DeleteObject` on `sa-api-client-output` bucket (for cleanup)

### Required Python Packages

```bash
pip install boto3 requests python-dateutil
```

## Test Data Structure

### S3 Paths and Formats

All test data will be created in S3 with the following structure:

```
sa-api-client-output/
├── customer_tailored/
│   └── {TEST_CUSTOMER_ID}/
│       ├── latest_model.json          # Registry file
│       └── archived/                  # Archived production models
│           └── {model_id}_{timestamp}.json
├── model_metrics/
│   └── {TEST_CUSTOMER_ID}/
│       ├── {TEST_CUSTOMER_ID}/
│       │   └── challenger_{timestamp}/
│       │       └── backtest_results.json
│       └── production/
│           └── model_{timestamp}/
│               └── backtest_results.json
└── audit_logs/
    └── {TEST_CUSTOMER_ID}/
        └── events.json
```

### Registry File Format (`latest_model.json`)

```json
{
  "customer_id": "{TEST_CUSTOMER_ID}",
  "production": {
    "model_id": "{TEST_CUSTOMER_ID}/production/model_{timestamp}",
    "promoted_at": "2025-01-15T10:00:00Z",
    "promoted_by": "test-user",
    "model_path": "s3://sa-api-client-output/customer_tailored/{TEST_CUSTOMER_ID}/models/production_model.h5",
    "metrics_ref": "s3://sa-api-client-output/model_metrics/{TEST_CUSTOMER_ID}/production/model_{timestamp}/backtest_results.json",
    "feature_schema_version": "v2",
    "supports_quantiles": false,
    "health_status": "healthy",
    "health_check_timestamp": "2025-01-15T10:00:00Z"
  },
  "challengers": [
    {
      "model_id": "{TEST_CUSTOMER_ID}/challenger_{timestamp}",
      "trained_at": "2025-01-20T12:00:00Z",
      "status": "evaluated",
      "evaluated_at": "2025-01-20T12:30:00Z",
      "evaluation_summary": {
        "verdict": "eligible",
        "mae_improvement_pct": 8.4,
        "rmse_improvement_pct": 6.1,
        "seasonal_regressions": []
      },
      "model_path": "s3://sa-api-client-output/customer_tailored/{TEST_CUSTOMER_ID}/models/challenger_model.h5",
      "feature_schema_version": "v2",
      "supports_quantiles": false
    }
  ]
}
```

### Metrics File Format (`backtest_results.json`)

```json
{
  "backtest": {
    "mae": 41.2,
    "rmse": 58.9,
    "bias": -1.3,
    "windows": 12
  }
}
```

### Audit Log Format (`events.json`)

```json
{
  "customer_id": "{TEST_CUSTOMER_ID}",
  "events": [
    {
      "timestamp": "2025-01-20T13:00:00Z",
      "actor": "{TEST_ACTOR}",
      "action": "promote",
      "model_id": "{model_id}",
      "reason": "End-to-end validation test",
      "request_id": "test-request-id-12345"
    }
  ]
}
```

## Phase 0: Preflight Checks (CRITICAL GATE)

**Purpose**: Verify API Gateway + Auth setup is deployed and working before attempting end-to-end validation.

**This phase is a HARD GATE** - if it fails, stop and fix the infrastructure setup before proceeding.

### Step 0.1: Verify API Gateway Reachability

**Action**: Test that API Gateway endpoint is reachable

**Implementation**:
```python
import requests
import os

base_url = os.environ['ONA_API_BASE_URL']
auth_token = os.environ.get('ONA_API_TOKEN', '')

if not auth_token:
    print("✗ FAIL: ONA_API_TOKEN not set")
    print("  Run: source <(./scripts/get-global-training-api-credentials.sh)")
    sys.exit(1)

# Test basic endpoint with auth
test_url = f"{base_url}/challengers"
headers = {
    'Authorization': f'Bearer {auth_token}',
    'X-Actor': os.environ.get('TEST_ACTOR', 'test-user')
}

try:
    response = requests.get(
        test_url,
        params={'customer_id': 'test'},
        headers=headers,
        timeout=10
    )
    
    # Accept 200 (success), 400 (bad request - but endpoint exists), or 500 (Lambda error - but endpoint exists)
    # Reject 401/403 (auth failure) or 404 (endpoint doesn't exist)
    if response.status_code == 401 or response.status_code == 403:
        print(f"✗ FAIL: Authentication failed (HTTP {response.status_code})")
        print("  This indicates:")
        print("    1. API Gateway is reachable")
        print("    2. Lambda is invoked")
        print("    3. BUT: Bearer token authentication is not configured correctly")
        print()
        print("  Check:")
        print("    - Lambda environment variable USE_BEARER_AUTH=true")
        print("    - Lambda environment variable INTERNAL_API_TOKEN matches ONA_API_TOKEN")
        print("    - Lambda check_authentication function is enforcing bearer auth")
        sys.exit(1)
    
    if response.status_code == 404:
        print(f"✗ FAIL: Endpoint not found (HTTP 404)")
        print("  This indicates:")
        print("    1. API Gateway is reachable")
        print("    2. BUT: Route is not configured correctly")
        print()
        print("  Check:")
        print("    - API Gateway routes are deployed")
        print("    - Route path matches /prod/api/v1/challengers")
        print("    - Lambda integration is configured")
        sys.exit(1)
    
    if response.status_code >= 500:
        # 500 errors are acceptable here - they prove endpoint exists and Lambda is invoked
        # The actual error (e.g., "Could not extract customer_id") is a Lambda implementation issue
        # which we'll test in Phase 2
        print(f"✓ PASS: Endpoint reachable (HTTP {response.status_code} - Lambda invoked)")
        print(f"  Response: {response.text[:200]}")
    
    elif response.status_code in [200, 400]:
        print(f"✓ PASS: Endpoint reachable and responding (HTTP {response.status_code})")
    
except requests.exceptions.ConnectionError as e:
    print(f"✗ FAIL: Cannot connect to API Gateway")
    print(f"  Error: {str(e)}")
    print()
    print("  Check:")
    print("    - ONA_API_BASE_URL is correct")
    print("    - API Gateway is deployed")
    print("    - Network connectivity")
    sys.exit(1)

except requests.exceptions.Timeout:
    print(f"✗ FAIL: Request timeout")
    print("  Check:")
    print("    - API Gateway is deployed and healthy")
    print("    - Lambda function is not timing out")
    sys.exit(1)
```

**Success Criteria**:
- API Gateway endpoint is reachable
- HTTP status is NOT 401/403 (auth working) and NOT 404 (route exists)
- If 500, error message indicates Lambda was invoked (not routing failure)

**Failure Handling**: Exit immediately with diagnostic message. Do NOT proceed to Phase 1.

### Step 0.2: Verify Auth Token Validity

**Action**: Confirm bearer token is accepted by Lambda

**Implementation**:
```python
# Test with valid auth token
response = requests.get(
    f"{base_url}/challengers",
    params={'customer_id': 'test'},
    headers={'Authorization': f'Bearer {auth_token}', 'X-Actor': 'test-user'},
    timeout=10
)

if response.status_code == 401:
    print("✗ FAIL: Bearer token rejected by Lambda")
    print("  This indicates:")
    print("    - API Gateway routes to Lambda correctly")
    print("    - Lambda check_authentication is running")
    print("    - BUT: Token mismatch")
    print()
    print("  Check:")
    print("    - Lambda INTERNAL_API_TOKEN matches ONA_API_TOKEN")
    print("    - Token retrieved from SSM: /ona-platform/prod/global-training-api-token")
    print("    - Lambda environment variable is set correctly")
    sys.exit(1)

if response.status_code == 403:
    print("✗ FAIL: Bearer token forbidden")
    print("  Check Lambda IAM permissions and auth configuration")
    sys.exit(1)

# Any other status (200, 400, 500) means auth passed
print(f"✓ PASS: Bearer token accepted (HTTP {response.status_code})")
```

**Success Criteria**:
- HTTP status is NOT 401 or 403
- Lambda accepts the bearer token

**Failure Handling**: Exit immediately. Do NOT proceed.

### Step 0.3: Verify Lambda Environment Configuration

**Action**: Test that Lambda has correct environment variables by checking error messages

**Implementation**:
```python
# Test a request that would trigger Lambda business logic
# If we get structured errors about missing customer_id, that means Lambda is:
# 1. Receiving requests
# 2. Parsing events
# 3. Running business logic
# 4. Has OUTPUT_BUCKET configured (otherwise we'd get different errors)

response = requests.get(
    f"{base_url}/challengers",
    params={},  # Missing customer_id
    headers={'Authorization': f'Bearer {auth_token}', 'X-Actor': 'test-user'},
    timeout=10
)

if response.status_code == 400:
    try:
        error_body = response.json()
        if 'customer_id' in str(error_body).lower():
            print("✓ PASS: Lambda business logic is active")
            print("  Lambda is parsing requests and validating inputs")
        else:
            print("⚠ WARNING: Lambda returned 400 but error message unclear")
    except:
        print("⚠ WARNING: Lambda returned 400 but response not JSON")
elif response.status_code == 500:
    # Check if error indicates Lambda is running business logic
    error_text = response.text.lower()
    if 'customer_id' in error_text or 'extract' in error_text:
        print("✓ PASS: Lambda is invoked and processing requests")
        print("  (500 error indicates Lambda implementation issue, not config issue)")
    else:
        print("⚠ WARNING: Lambda returned 500 with unexpected error")
else:
    print(f"✓ PASS: Lambda responding (HTTP {response.status_code})")
```

**Success Criteria**:
- Lambda is processing requests (not just returning 404)
- Error messages indicate Lambda business logic is running

**Failure Handling**: Log warning but continue (non-critical check)

### Step 0.4: Verify S3 Access

**Action**: Confirm AWS credentials can access S3 bucket

**Implementation**:
```python
import boto3

s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'])
bucket = os.environ['OUTPUT_BUCKET']

try:
    # Test read access
    s3.head_bucket(Bucket=bucket)
    print(f"✓ PASS: S3 bucket accessible: {bucket}")
    
    # Test write access (create and delete a test object)
    test_key = f"zorora-validation-test-{int(time.time())}.txt"
    s3.put_object(Bucket=bucket, Key=test_key, Body=b"test")
    s3.delete_object(Bucket=bucket, Key=test_key)
    print("✓ PASS: S3 write/delete access confirmed")
    
except Exception as e:
    print(f"✗ FAIL: S3 access error: {str(e)}")
    print("  Check:")
    print("    - AWS credentials are configured")
    print("    - IAM permissions include s3:GetObject, s3:PutObject, s3:DeleteObject")
    print("    - Bucket name is correct")
    sys.exit(1)
```

**Success Criteria**:
- Can read bucket metadata
- Can write and delete objects

**Failure Handling**: Exit immediately. Do NOT proceed.

### Phase 0 Summary

**All checks must pass** before proceeding to Phase 1.

If Phase 0 fails:
1. **Stop execution**
2. **Review diagnostic messages**
3. **Fix infrastructure setup**
4. **Re-run Phase 0**
5. **Only proceed when Phase 0 passes**

**Phase 0 validates**:
- ✅ API Gateway is deployed and reachable
- ✅ Bearer token authentication is configured and working
- ✅ Lambda is invoked and processing requests
- ✅ S3 bucket is accessible

## Phase 1: Test Data Setup

### Step 1.1: Generate Test Timestamps

**Action**: Create deterministic timestamps for test data

**Implementation**:
```python
from datetime import datetime, timedelta
import time

# Base timestamp (current time)
base_time = datetime.now()

# Production model timestamp (7 days ago)
production_timestamp = (base_time - timedelta(days=7)).strftime("%Y%m%d_%H%M%S")

# Challenger timestamp (1 day ago, evaluated 30 minutes later)
challenger_trained = (base_time - timedelta(days=1)).strftime("%Y%m%d_%H%M%S")
challenger_evaluated = (base_time - timedelta(days=1) + timedelta(minutes=30)).isoformat() + 'Z'
```

**Success Criteria**: Timestamps are valid ISO format strings

### Step 1.2: Create Production Model Registry Entry

**Action**: Create initial registry with a production model

**S3 Key**: `customer_tailored/{TEST_CUSTOMER_ID}/latest_model.json`

**Implementation**:
```python
import boto3
import json
import os

s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'])
bucket = os.environ['OUTPUT_BUCKET']
customer_id = os.environ['TEST_CUSTOMER_ID']

production_model_id = f"{customer_id}/production/model_{production_timestamp}"

registry = {
    "customer_id": customer_id,
    "production": {
        "model_id": production_model_id,
        "promoted_at": (base_time - timedelta(days=7)).isoformat() + 'Z',
        "promoted_by": "test-setup",
        "model_path": f"s3://{bucket}/customer_tailored/{customer_id}/models/production_model.h5",
        "metrics_ref": f"s3://{bucket}/model_metrics/{customer_id}/production/model_{production_timestamp}/backtest_results.json",
        "feature_schema_version": "v2",
        "supports_quantiles": False,
        "health_status": "healthy",
        "health_check_timestamp": (base_time - timedelta(days=7)).isoformat() + 'Z'
    },
    "challengers": []
}

s3.put_object(
    Bucket=bucket,
    Key=f"customer_tailored/{customer_id}/latest_model.json",
    Body=json.dumps(registry, indent=2)
)
```

**Success Criteria**: 
- S3 object exists at expected key
- JSON is valid and parseable
- Registry structure matches expected format

### Step 1.3: Create Production Model Metrics

**Action**: Create metrics file for production model

**S3 Key**: `model_metrics/{TEST_CUSTOMER_ID}/production/model_{production_timestamp}/backtest_results.json`

**Implementation**:
```python
production_metrics = {
    "backtest": {
        "mae": 45.0,  # Higher MAE (worse) - challenger will improve
        "rmse": 62.7,
        "bias": -1.5,
        "windows": 12
    }
}

s3.put_object(
    Bucket=bucket,
    Key=f"model_metrics/{customer_id}/production/model_{production_timestamp}/backtest_results.json",
    Body=json.dumps(production_metrics, indent=2)
)
```

**Success Criteria**:
- S3 object exists at expected key
- Metrics file is valid JSON
- MAE/RMSE values are numeric

### Step 1.4: Create Challenger Model Entry

**Action**: Add challenger to registry with eligible evaluation summary

**Implementation**:
```python
challenger_model_id = f"{customer_id}/challenger_{challenger_trained}"

# Re-read registry
registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
registry = json.loads(registry_obj['Body'].read())

# Add challenger
registry['challengers'] = [
    {
        "model_id": challenger_model_id,
        "trained_at": (base_time - timedelta(days=1)).isoformat() + 'Z',
        "status": "evaluated",
        "evaluated_at": challenger_evaluated,
        "evaluation_summary": {
            "verdict": "eligible",
            "mae_improvement_pct": 8.4,  # >5% improvement
            "rmse_improvement_pct": 6.1,  # >5% improvement
            "seasonal_regressions": []
        },
        "model_path": f"s3://{bucket}/customer_tailored/{customer_id}/models/challenger_model.h5",
        "feature_schema_version": "v2",
        "supports_quantiles": False
    }
]

# Save updated registry
s3.put_object(
    Bucket=bucket,
    Key=f"customer_tailored/{customer_id}/latest_model.json",
    Body=json.dumps(registry, indent=2)
)
```

**Success Criteria**:
- Registry updated with challenger entry
- Challenger has `status: "evaluated"`
- Evaluation summary shows `verdict: "eligible"`
- Improvement percentages are >= 5%

### Step 1.5: Create Challenger Model Metrics

**Action**: Create metrics file for challenger model

**S3 Key**: `model_metrics/{TEST_CUSTOMER_ID}/{TEST_CUSTOMER_ID}/challenger_{challenger_trained}/backtest_results.json`

**Implementation**:
```python
challenger_metrics = {
    "backtest": {
        "mae": 41.2,  # Lower MAE (better) - 8.4% improvement over production
        "rmse": 58.9,  # Lower RMSE (better) - 6.1% improvement over production
        "bias": -1.3,
        "windows": 12
    }
}

s3.put_object(
    Bucket=bucket,
    Key=f"model_metrics/{customer_id}/{customer_id}/challenger_{challenger_trained}/backtest_results.json",
    Body=json.dumps(challenger_metrics, indent=2)
)
```

**Success Criteria**:
- S3 object exists at expected key
- Metrics show improvement over production (lower MAE/RMSE)
- Metrics file is valid JSON

### Step 1.6: Initialize Audit Log

**Action**: Create empty audit log file

**S3 Key**: `audit_logs/{TEST_CUSTOMER_ID}/events.json`

**Implementation**:
```python
audit_log = {
    "customer_id": customer_id,
    "events": []
}

s3.put_object(
    Bucket=bucket,
    Key=f"audit_logs/{customer_id}/events.json",
    Body=json.dumps(audit_log, indent=2)
)
```

**Success Criteria**:
- Audit log file exists
- Initial event list is empty array

## Phase 2: Read-Only Operations Validation

### Step 2.1: Validate `ml-list-challengers`

**Command**: `ml-list-challengers {TEST_CUSTOMER_ID}`

**Expected Behavior**:
- Returns list of challenger models
- Includes exactly 1 challenger (the one we created)
- Challenger has correct `model_id`, `status`, `evaluated_at`

**Success Criteria**:
```python
# Execute command via Zorora HTTP client
from zorora.http_client import ZororaHTTPClient
from zorora.commands.ona_platform import ListChallengersCommand

http_client = ZororaHTTPClient(
    base_url=os.environ['ONA_API_BASE_URL'],
    auth_token=os.environ['ONA_API_TOKEN']
)
cmd = ListChallengersCommand(http_client)
result = cmd.execute([customer_id], {'actor': os.environ['TEST_ACTOR']})

# Parse result (may be formatted string)
import json
if isinstance(result, str):
    # Extract JSON from formatted string if needed
    result_data = json.loads(result)
else:
    result_data = result

assert result_data['customer_id'] == customer_id
assert result_data['count'] == 1
assert len(result_data['challengers']) == 1
assert result_data['challengers'][0]['model_id'] == challenger_model_id
assert result_data['challengers'][0]['status'] == 'evaluated'
```

**Failure Handling**: If command fails, log error and mark Phase 2 as failed

### Step 2.2: Validate `ml-show-metrics` (Challenger)

**Command**: `ml-show-metrics {challenger_model_id}`

**Expected Behavior**:
- Returns metrics for challenger model
- Metrics match what we created in Step 1.5

**Success Criteria**:
```python
from zorora.commands.ona_platform import ShowMetricsCommand

cmd = ShowMetricsCommand(http_client)
result = cmd.execute([challenger_model_id], {'actor': os.environ['TEST_ACTOR']})

# Parse result
result_data = json.loads(result) if isinstance(result, str) else result

assert result_data['model_id'] == challenger_model_id
assert 'metrics' in result_data
assert 'backtest' in result_data['metrics']
assert result_data['metrics']['backtest']['mae'] == 41.2
assert result_data['metrics']['backtest']['rmse'] == 58.9
```

**Failure Handling**: If command fails, log error and mark Phase 2 as failed

### Step 2.3: Validate `ml-show-metrics` (Production)

**Command**: `ml-show-metrics {production_model_id}`

**Expected Behavior**:
- Returns metrics for production model
- Metrics match what we created in Step 1.3

**Success Criteria**:
```python
result = cmd.execute([production_model_id], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

assert result_data['model_id'] == production_model_id
assert result_data['metrics']['backtest']['mae'] == 45.0
assert result_data['metrics']['backtest']['rmse'] == 62.7
```

**Failure Handling**: If command fails, log error and mark Phase 2 as failed

### Step 2.4: Validate `ml-diff`

**Command**: `ml-diff {challenger_model_id} {production_model_id}`

**Expected Behavior**:
- Returns comparison showing challenger is eligible
- Shows improvement percentages matching our test data
- Verdict is "eligible"

**Success Criteria**:
```python
from zorora.commands.ona_platform import DiffModelsCommand

cmd = DiffModelsCommand(http_client)
result = cmd.execute([challenger_model_id, production_model_id], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

assert result_data['challenger_id'] == challenger_model_id
assert result_data['production_id'] == production_model_id
assert result_data['verdict'] == 'eligible'
assert 'improvement' in result_data
assert result_data['improvement']['mae_pct'] > 5.0  # Should be ~8.4%
assert result_data['improvement']['rmse_pct'] > 5.0  # Should be ~6.1%
assert result_data['regressions'] == []
```

**Failure Handling**: If command fails, log error and mark Phase 2 as failed

### Step 2.5: Validate `ml-audit-log` (Initial State)

**Command**: `ml-audit-log {TEST_CUSTOMER_ID}`

**Expected Behavior**:
- Returns audit log with 0 events (initial state)

**Success Criteria**:
```python
from zorora.commands.ona_platform import AuditLogCommand

cmd = AuditLogCommand(http_client)
result = cmd.execute([customer_id], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

assert result_data['customer_id'] == customer_id
assert result_data['count'] == 0
assert len(result_data['events']) == 0
```

**Failure Handling**: If command fails, log error and mark Phase 2 as failed

## Phase 3: Mutating Operations Validation

### Step 3.1: Validate `ml-promote` (Successful Promotion)

**Command**: `ml-promote {TEST_CUSTOMER_ID} {challenger_model_id} "End-to-end validation test promotion"`

**Expected Behavior**:
- Promotion succeeds (challenger meets all gates)
- Registry updated: challenger moved to production
- Previous production archived
- Audit log entry created

**Success Criteria**:
```python
from zorora.commands.ona_platform import PromoteModelCommand
import os

# Set auto-confirm to avoid prompts
os.environ['ZORORA_AUTO_CONFIRM'] = 'true'

cmd = PromoteModelCommand(http_client, ui=None)
reason = "End-to-end validation test promotion"
result = cmd.execute([customer_id, challenger_model_id, reason], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

# Verify API response
assert 'promoted_at' in result_data or 'message' in result_data

# Verify registry state change
registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
registry = json.loads(registry_obj['Body'].read())

# Production should now be the challenger
assert registry['production']['model_id'] == challenger_model_id
assert 'promoted_at' in registry['production']
assert registry['production']['promoted_by'] == os.environ['TEST_ACTOR']

# Challenger should be removed from challengers list
assert len(registry['challengers']) == 0

# Previous production should be archived
archive_prefix = f"customer_tailored/{customer_id}/archived/"
paginator = s3.get_paginator('list_objects_v2')
archives = []
for page in paginator.paginate(Bucket=bucket, Prefix=archive_prefix):
    if 'Contents' in page:
        archives.extend([obj['Key'] for obj in page['Contents']])

assert len(archives) == 1  # One archived production model
assert production_model_id in archives[0]

# Verify audit log
audit_obj = s3.get_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
audit_log = json.loads(audit_obj['Body'].read())

assert len(audit_log['events']) == 1
assert audit_log['events'][0]['action'] == 'promote'
assert audit_log['events'][0]['model_id'] == challenger_model_id
assert audit_log['events'][0]['actor'] == os.environ['TEST_ACTOR']
```

**Failure Handling**: If promotion fails, log error and mark Phase 3 as failed. Do NOT proceed to rollback test.

### Step 3.2: Validate `ml-audit-log` (After Promotion)

**Command**: `ml-audit-log {TEST_CUSTOMER_ID}`

**Expected Behavior**:
- Returns audit log with 1 event (the promotion)

**Success Criteria**:
```python
result = cmd.execute([customer_id], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

assert result_data['count'] == 1
assert len(result_data['events']) == 1
assert result_data['events'][0]['action'] == 'promote'
```

**Failure Handling**: If command fails, log error but continue (non-critical)

### Step 3.3: Validate `ml-rollback` (Successful Rollback)

**Command**: `ml-rollback {TEST_CUSTOMER_ID} "End-to-end validation test rollback"`

**Expected Behavior**:
- Rollback succeeds
- Registry updated: previous production restored
- Current production archived
- Audit log entry created

**Success Criteria**:
```python
from zorora.commands.ona_platform import RollbackModelCommand

cmd = RollbackModelCommand(http_client, ui=None)
reason = "End-to-end validation test rollback"
result = cmd.execute([customer_id, reason], {'actor': os.environ['TEST_ACTOR']})
result_data = json.loads(result) if isinstance(result, str) else result

# Verify API response
assert 'rollback_at' in result_data or 'message' in result_data

# Verify registry state change
registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
registry = json.loads(registry_obj['Body'].read())

# Production should be restored to original
assert registry['production']['model_id'] == production_model_id
assert 'rollback_at' in registry['production'] or 'promoted_at' in registry['production']

# Verify audit log has 2 events now
audit_obj = s3.get_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
audit_log = json.loads(audit_obj['Body'].read())

assert len(audit_log['events']) == 2
assert audit_log['events'][-1]['action'] == 'rollback'
assert audit_log['events'][-1]['actor'] == os.environ['TEST_ACTOR']
```

**Failure Handling**: If rollback fails, log error and mark Phase 3 as failed

## Phase 4: Error Handling Validation

### Step 4.1: Validate `ml-promote` (Invalid Challenger)

**Command**: `ml-promote {TEST_CUSTOMER_ID} nonexistent_model "Test error handling"`

**Expected Behavior**:
- Command fails with clear error message
- Registry unchanged
- No audit log entry created

**Success Criteria**:
```python
try:
    result = cmd.execute([customer_id, "nonexistent_model", "Test error handling"], {'actor': os.environ['TEST_ACTOR']})
    assert False, "Command should have raised an exception"
except Exception as e:
    error_msg = str(e)
    assert "not found" in error_msg.lower() or "challenger" in error_msg.lower()

# Verify registry unchanged
registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
registry = json.loads(registry_obj['Body'].read())
# Registry should still have production from rollback
assert registry['production']['model_id'] == production_model_id
```

**Failure Handling**: If command succeeds unexpectedly, mark Phase 4 as failed

### Step 4.2: Validate `ml-promote` (Short Reason)

**Command**: `ml-promote {TEST_CUSTOMER_ID} {challenger_model_id} "short"`

**Expected Behavior**:
- Command fails with error about reason length
- Registry unchanged

**Success Criteria**:
```python
try:
    result = cmd.execute([customer_id, challenger_model_id, "short"], {'actor': os.environ['TEST_ACTOR']})
    assert False, "Command should have raised an exception"
except Exception as e:
    error_msg = str(e)
    assert "reason" in error_msg.lower() and ("10" in error_msg or "length" in error_msg.lower())
```

**Failure Handling**: If command succeeds unexpectedly, mark Phase 4 as failed

## Phase 5: Cleanup

### Step 5.1: Delete Test Data from S3

**Action**: Remove all test data created during validation

**Implementation**:
```python
# Delete registry
s3.delete_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")

# Delete metrics files
s3.delete_object(Bucket=bucket, Key=f"model_metrics/{customer_id}/production/model_{production_timestamp}/backtest_results.json")
s3.delete_object(Bucket=bucket, Key=f"model_metrics/{customer_id}/{customer_id}/challenger_{challenger_trained}/backtest_results.json")

# Delete audit log
s3.delete_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")

# Delete archived files
for archive_key in archives:
    s3.delete_object(Bucket=bucket, Key=archive_key)
```

**Success Criteria**: All test S3 objects deleted

### Step 5.2: Verify Cleanup

**Action**: Confirm no test data remains

**Implementation**:
```python
# Verify registry deleted
try:
    s3.head_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
    assert False, "Registry should be deleted"
except s3.exceptions.ClientError as e:
    assert e.response['Error']['Code'] == '404'

# Verify audit log deleted
try:
    s3.head_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
    assert False, "Audit log should be deleted"
except s3.exceptions.ClientError as e:
    assert e.response['Error']['Code'] == '404'
```

**Success Criteria**: All test objects confirmed deleted

## Validation Script Structure

### Main Execution Flow

```python
#!/usr/bin/env python3
"""
End-to-end validation script for Zorora ↔ ONA Platform integration.
"""

import os
import sys
import json
import boto3
import requests
import time
from datetime import datetime, timedelta

def phase0_preflight():
    """Phase 0: Verify API Gateway + Auth setup is deployed and working."""
    # Implementation of Step 0.1-0.4 above
    # This is a HARD GATE - exits on failure
    pass

def main():
    """Execute all validation phases."""
    print("=" * 70)
    print("Zorora ↔ ONA Platform End-to-End Validation")
    print("=" * 70)
    print()
    
    # Validate prerequisites
    required_env_vars = [
        'ONA_API_BASE_URL', 'ONA_API_TOKEN', 'AWS_REGION',
        'OUTPUT_BUCKET', 'TEST_CUSTOMER_ID', 'TEST_ACTOR'
    ]
    missing = [var for var in required_env_vars if not os.getenv(var)]
    if missing:
        print(f"✗ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Initialize S3 client
    s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'])
    bucket = os.environ['OUTPUT_BUCKET']
    customer_id = os.environ['TEST_CUSTOMER_ID']
    
    results = {
        'phase0_preflight': False,
        'phase1_setup': False,
        'phase2_readonly': False,
        'phase3_mutating': False,
        'phase4_errors': False,
        'phase5_cleanup': False
    }
    
    try:
        # Phase 0: Preflight checks (HARD GATE)
        print("Phase 0: Preflight Checks (CRITICAL GATE)")
        print("-" * 70)
        print("⚠️  This phase validates API Gateway + Auth setup is deployed")
        print("⚠️  If this fails, STOP and fix infrastructure before proceeding")
        print()
        phase0_preflight()
        results['phase0_preflight'] = True
        print("✓ Phase 0 completed - Infrastructure validated\n")
        
        # Phase 1: Setup
        print("Phase 1: Test Data Setup")
        print("-" * 70)
        phase1_setup(s3, bucket, customer_id)
        results['phase1_setup'] = True
        print("✓ Phase 1 completed\n")
        
        # Phase 2: Read-only operations
        print("Phase 2: Read-Only Operations Validation")
        print("-" * 70)
        phase2_readonly(customer_id)
        results['phase2_readonly'] = True
        print("✓ Phase 2 completed\n")
        
        # Phase 3: Mutating operations
        print("Phase 3: Mutating Operations Validation")
        print("-" * 70)
        phase3_mutating(s3, bucket, customer_id)
        results['phase3_mutating'] = True
        print("✓ Phase 3 completed\n")
        
        # Phase 4: Error handling
        print("Phase 4: Error Handling Validation")
        print("-" * 70)
        phase4_errors(s3, bucket, customer_id)
        results['phase4_errors'] = True
        print("✓ Phase 4 completed\n")
        
    finally:
        # Phase 5: Cleanup (always run)
        print("Phase 5: Cleanup")
        print("-" * 70)
        phase5_cleanup(s3, bucket, customer_id)
        results['phase5_cleanup'] = True
        print("✓ Phase 5 completed\n")
    
    # Final summary
    print("=" * 70)
    print("Validation Summary")
    print("=" * 70)
    for phase, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {phase}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All phases passed - End-to-end validation successful!")
        sys.exit(0)
    else:
        print("\n✗ Some phases failed - See errors above")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Success Criteria Summary

### Overall Validation Success

All phases must pass for validation to be considered successful:

0. **Phase 0 (Preflight)**: API Gateway + Auth setup is deployed and working ⚠️ **HARD GATE**
1. **Phase 1 (Setup)**: All test data created in S3
2. **Phase 2 (Read-only)**: All read commands return correct data
3. **Phase 3 (Mutating)**: Promotion and rollback work correctly, state changes persist
4. **Phase 4 (Errors)**: Invalid inputs are rejected with clear errors
5. **Phase 5 (Cleanup)**: All test data removed

**Critical**: Phase 0 is a **hard gate**. If it fails, the script exits immediately and does NOT proceed to Phase 1. This prevents wasting time on end-to-end validation when infrastructure is not properly configured.

### Critical Validations

- **State Persistence**: Registry changes must persist in S3
- **Audit Logging**: All mutating operations must create audit log entries
- **Data Consistency**: Registry, metrics, and audit logs must be consistent
- **Error Handling**: Invalid operations must fail gracefully without side effects

## Ambiguity Resolution

### Timestamp Format
- **Format**: `YYYYMMDD_HHMMSS` (e.g., `20250120_123000`)
- **Timezone**: UTC
- **ISO Format**: `YYYY-MM-DDTHH:MM:SSZ` for datetime fields

### Model ID Format
- **Challenger**: `{customer_id}/challenger_{timestamp}`
- **Production**: `{customer_id}/production/model_{timestamp}`

### S3 Path Construction
- **Registry**: `customer_tailored/{customer_id}/latest_model.json`
- **Metrics**: `model_metrics/{customer_id}/{model_id}/backtest_results.json`
- **Audit Log**: `audit_logs/{customer_id}/events.json`

### Command Execution Context
- **Actor**: From `TEST_ACTOR` environment variable
- **Auto-confirm**: Set `ZORORA_AUTO_CONFIRM=true` for mutating commands
- **Error Handling**: Commands raise exceptions on failure (don't return error strings)

### HTTP Client Configuration
- **Base URL**: From `ONA_API_BASE_URL` environment variable
- **Auth Token**: From `ONA_API_TOKEN` environment variable
- **Headers**: Include `Authorization: Bearer {token}` and `X-Actor: {actor}`

## Notes

### Critical Dependencies

- **API Gateway Setup**: This plan **requires** the API Gateway HTTP API to be deployed with:
  - Routes configured for all endpoints (`/challengers`, `/metrics/{id}`, `/diff`, `/promote`, `/rollback`, `/audit-log`)
  - Lambda integration configured
  - `/prod` stage deployed
  
- **Lambda Auth Configuration**: Lambda must have:
  - `USE_BEARER_AUTH=true` environment variable
  - `INTERNAL_API_TOKEN` environment variable set from SSM
  - `check_authentication` function enforcing bearer token auth
  
- **Phase 0 Hard Gate**: Phase 0 validates these dependencies. If Phase 0 fails, **do not proceed**. Fix the infrastructure setup first.

### Implementation Notes

- This plan assumes the Lambda's event parsing issue ("Could not extract customer_id from event") has been fixed
- Test data uses deterministic values to enable predictable validation
- All S3 operations use the same bucket and region as the Lambda
- Cleanup always runs, even if validation fails partway through
- Each phase is independent and can be run separately for debugging
- Phase 0 can be run standalone to verify infrastructure setup before attempting full validation

---

**Document Status**: Ready for Implementation  
**Last Updated**: 2025-01-29  
**Version**: 1.0.0
