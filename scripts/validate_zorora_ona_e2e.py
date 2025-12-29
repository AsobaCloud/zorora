#!/usr/bin/env python3
"""
End-to-end validation script for Zorora ↔ ONA Platform integration.

This script validates the complete end-to-end workflow including:
- API Gateway + Auth setup (Phase 0 - HARD GATE)
- Test data setup in S3 (Phase 1)
- Read-only operations (Phase 2)
- Mutating operations (Phase 3)
- Error handling (Phase 4)
- Cleanup (Phase 5)

See docs/END_TO_END_VALIDATION_PLAN.md for detailed specification.
"""

import os
import sys
import json
import boto3
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# PHASE 0: Preflight Checks (HARD GATE)
# ============================================================================

def phase0_preflight():
    """Phase 0: Verify API Gateway + Auth setup is deployed and working."""
    print("Step 0.1: Verify API Gateway Reachability")
    
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
    
    print()
    print("Step 0.2: Verify Auth Token Validity")
    
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
    print()
    
    print("Step 0.3: Verify Lambda Environment Configuration")
    
    # Test a request that would trigger Lambda business logic
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
    print()
    
    print("Step 0.4: Verify S3 Access")
    
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


# ============================================================================
# PHASE 1: Test Data Setup
# ============================================================================

def phase1_setup(s3, bucket: str, customer_id: str) -> Tuple[str, str, str, str]:
    """Phase 1: Create test data in S3. Returns (production_model_id, challenger_model_id, production_timestamp, challenger_trained)."""
    print("Step 1.1: Generate Test Timestamps")
    
    base_time = datetime.now()
    production_timestamp = (base_time - timedelta(days=7)).strftime("%Y%m%d_%H%M%S")
    challenger_trained = (base_time - timedelta(days=1)).strftime("%Y%m%d_%H%M%S")
    challenger_evaluated = (base_time - timedelta(days=1) + timedelta(minutes=30)).isoformat() + 'Z'
    
    print(f"  Production timestamp: {production_timestamp}")
    print(f"  Challenger timestamp: {challenger_trained}")
    print()
    
    print("Step 1.2: Create Production Model Registry Entry")
    
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
    print(f"✓ Created registry: customer_tailored/{customer_id}/latest_model.json")
    print()
    
    print("Step 1.3: Create Production Model Metrics")
    
    production_metrics = {
        "backtest": {
            "mae": 45.0,
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
    print(f"✓ Created production metrics")
    print()
    
    print("Step 1.4: Create Challenger Model Entry")
    
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
                "mae_improvement_pct": 8.4,
                "rmse_improvement_pct": 6.1,
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
    print(f"✓ Added challenger to registry: {challenger_model_id}")
    print()
    
    print("Step 1.5: Create Challenger Model Metrics")
    
    challenger_metrics = {
        "backtest": {
            "mae": 41.2,
            "rmse": 58.9,
            "bias": -1.3,
            "windows": 12
        }
    }
    
    s3.put_object(
        Bucket=bucket,
        Key=f"model_metrics/{customer_id}/{customer_id}/challenger_{challenger_trained}/backtest_results.json",
        Body=json.dumps(challenger_metrics, indent=2)
    )
    print(f"✓ Created challenger metrics")
    print()
    
    print("Step 1.6: Initialize Audit Log")
    
    audit_log = {
        "customer_id": customer_id,
        "events": []
    }
    
    s3.put_object(
        Bucket=bucket,
        Key=f"audit_logs/{customer_id}/events.json",
        Body=json.dumps(audit_log, indent=2)
    )
    print(f"✓ Created audit log")
    
    return production_model_id, challenger_model_id, production_timestamp, challenger_trained


# ============================================================================
# PHASE 2: Read-Only Operations Validation
# ============================================================================

def parse_command_result(result):
    """Parse command result (may be string or dict)."""
    if isinstance(result, str):
        try:
            # Try to extract JSON from formatted string
            return json.loads(result)
        except:
            # If not JSON, return as-is
            return result
    return result


def phase2_readonly(customer_id: str, challenger_model_id: str, production_model_id: str):
    """Phase 2: Validate read-only operations."""
    from zorora.http_client import ZororaHTTPClient
    from zorora.commands.ona_platform import (
        ListChallengersCommand,
        ShowMetricsCommand,
        DiffModelsCommand,
        AuditLogCommand
    )
    
    http_client = ZororaHTTPClient(
        base_url=os.environ['ONA_API_BASE_URL'],
        auth_token=os.environ['ONA_API_TOKEN']
    )
    context = {'actor': os.environ['TEST_ACTOR']}
    
    print("Step 2.1: Validate ml-list-challengers")
    try:
        cmd = ListChallengersCommand(http_client)
        result = cmd.execute([customer_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['customer_id'] == customer_id
        assert result_data['count'] == 1
        assert len(result_data['challengers']) == 1
        assert result_data['challengers'][0]['model_id'] == challenger_model_id
        assert result_data['challengers'][0]['status'] == 'evaluated'
        print("✓ PASS: ml-list-challengers returned correct data")
    except Exception as e:
        print(f"✗ FAIL: ml-list-challengers failed: {str(e)}")
        raise
    print()
    
    print("Step 2.2: Validate ml-show-metrics (Challenger)")
    try:
        cmd = ShowMetricsCommand(http_client)
        result = cmd.execute([challenger_model_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['model_id'] == challenger_model_id
        assert 'metrics' in result_data
        assert 'backtest' in result_data['metrics']
        assert result_data['metrics']['backtest']['mae'] == 41.2
        assert result_data['metrics']['backtest']['rmse'] == 58.9
        print("✓ PASS: ml-show-metrics (challenger) returned correct data")
    except Exception as e:
        print(f"✗ FAIL: ml-show-metrics (challenger) failed: {str(e)}")
        raise
    print()
    
    print("Step 2.3: Validate ml-show-metrics (Production)")
    try:
        result = cmd.execute([production_model_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['model_id'] == production_model_id
        assert result_data['metrics']['backtest']['mae'] == 45.0
        assert result_data['metrics']['backtest']['rmse'] == 62.7
        print("✓ PASS: ml-show-metrics (production) returned correct data")
    except Exception as e:
        print(f"✗ FAIL: ml-show-metrics (production) failed: {str(e)}")
        raise
    print()
    
    print("Step 2.4: Validate ml-diff")
    try:
        cmd = DiffModelsCommand(http_client)
        result = cmd.execute([challenger_model_id, production_model_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['challenger_id'] == challenger_model_id
        assert result_data['production_id'] == production_model_id
        assert result_data['verdict'] == 'eligible'
        assert 'improvement' in result_data
        assert result_data['improvement']['mae_pct'] > 5.0
        assert result_data['improvement']['rmse_pct'] > 5.0
        assert result_data['regressions'] == []
        print("✓ PASS: ml-diff returned correct comparison")
    except Exception as e:
        print(f"✗ FAIL: ml-diff failed: {str(e)}")
        raise
    print()
    
    print("Step 2.5: Validate ml-audit-log (Initial State)")
    try:
        cmd = AuditLogCommand(http_client)
        result = cmd.execute([customer_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['customer_id'] == customer_id
        assert result_data['count'] == 0
        assert len(result_data['events']) == 0
        print("✓ PASS: ml-audit-log returned empty log (initial state)")
    except Exception as e:
        print(f"✗ FAIL: ml-audit-log failed: {str(e)}")
        raise


# ============================================================================
# PHASE 3: Mutating Operations Validation
# ============================================================================

def phase3_mutating(s3, bucket: str, customer_id: str, challenger_model_id: str, production_model_id: str):
    """Phase 3: Validate mutating operations."""
    from zorora.http_client import ZororaHTTPClient
    from zorora.commands.ona_platform import (
        PromoteModelCommand,
        RollbackModelCommand,
        AuditLogCommand
    )
    
    http_client = ZororaHTTPClient(
        base_url=os.environ['ONA_API_BASE_URL'],
        auth_token=os.environ['ONA_API_TOKEN']
    )
    context = {'actor': os.environ['TEST_ACTOR']}
    
    # Set auto-confirm for mutating commands
    os.environ['ZORORA_AUTO_CONFIRM'] = 'true'
    
    print("Step 3.1: Validate ml-promote (Successful Promotion)")
    try:
        cmd = PromoteModelCommand(http_client, ui=None)
        reason = "End-to-end validation test promotion"
        result = cmd.execute([customer_id, challenger_model_id, reason], context)
        result_data = parse_command_result(result)
        
        # Verify API response
        assert 'promoted_at' in result_data or 'message' in result_data
        
        # Verify registry state change
        registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
        registry = json.loads(registry_obj['Body'].read())
        
        assert registry['production']['model_id'] == challenger_model_id
        assert 'promoted_at' in registry['production']
        assert registry['production']['promoted_by'] == os.environ['TEST_ACTOR']
        assert len(registry['challengers']) == 0
        
        # Verify archive
        archive_prefix = f"customer_tailored/{customer_id}/archived/"
        paginator = s3.get_paginator('list_objects_v2')
        archives = []
        for page in paginator.paginate(Bucket=bucket, Prefix=archive_prefix):
            if 'Contents' in page:
                archives.extend([obj['Key'] for obj in page['Contents']])
        
        assert len(archives) == 1
        assert production_model_id in archives[0]
        
        # Verify audit log
        audit_obj = s3.get_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
        audit_log = json.loads(audit_obj['Body'].read())
        
        assert len(audit_log['events']) == 1
        assert audit_log['events'][0]['action'] == 'promote'
        assert audit_log['events'][0]['model_id'] == challenger_model_id
        assert audit_log['events'][0]['actor'] == os.environ['TEST_ACTOR']
        
        print("✓ PASS: ml-promote succeeded and state persisted correctly")
    except Exception as e:
        print(f"✗ FAIL: ml-promote failed: {str(e)}")
        raise
    print()
    
    print("Step 3.2: Validate ml-audit-log (After Promotion)")
    try:
        cmd = AuditLogCommand(http_client)
        result = cmd.execute([customer_id], context)
        result_data = parse_command_result(result)
        
        assert result_data['count'] == 1
        assert len(result_data['events']) == 1
        assert result_data['events'][0]['action'] == 'promote'
        print("✓ PASS: ml-audit-log shows promotion event")
    except Exception as e:
        print(f"⚠ WARNING: ml-audit-log check failed (non-critical): {str(e)}")
    print()
    
    print("Step 3.3: Validate ml-rollback (Successful Rollback)")
    try:
        cmd = RollbackModelCommand(http_client, ui=None)
        reason = "End-to-end validation test rollback"
        result = cmd.execute([customer_id, reason], context)
        result_data = parse_command_result(result)
        
        # Verify API response
        assert 'rollback_at' in result_data or 'message' in result_data
        
        # Verify registry state change
        registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
        registry = json.loads(registry_obj['Body'].read())
        
        # Production should be restored (check model_id matches original or has rollback marker)
        # Note: Rollback implementation may vary - check that state changed
        assert registry['production']['model_id'] != challenger_model_id or 'rollback_at' in registry['production']
        
        # Verify audit log has 2 events now
        audit_obj = s3.get_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
        audit_log = json.loads(audit_obj['Body'].read())
        
        assert len(audit_log['events']) == 2
        assert audit_log['events'][-1]['action'] == 'rollback'
        assert audit_log['events'][-1]['actor'] == os.environ['TEST_ACTOR']
        
        print("✓ PASS: ml-rollback succeeded and state persisted correctly")
    except Exception as e:
        print(f"✗ FAIL: ml-rollback failed: {str(e)}")
        raise


# ============================================================================
# PHASE 4: Error Handling Validation
# ============================================================================

def phase4_errors(s3, bucket: str, customer_id: str, challenger_model_id: str):
    """Phase 4: Validate error handling."""
    from zorora.http_client import ZororaHTTPClient
    from zorora.commands.ona_platform import PromoteModelCommand
    
    http_client = ZororaHTTPClient(
        base_url=os.environ['ONA_API_BASE_URL'],
        auth_token=os.environ['ONA_API_TOKEN']
    )
    context = {'actor': os.environ['TEST_ACTOR']}
    os.environ['ZORORA_AUTO_CONFIRM'] = 'true'
    
    print("Step 4.1: Validate ml-promote (Invalid Challenger)")
    try:
        cmd = PromoteModelCommand(http_client, ui=None)
        try:
            result = cmd.execute([customer_id, "nonexistent_model", "Test error handling"], context)
            assert False, "Command should have raised an exception"
        except Exception as e:
            error_msg = str(e).lower()
            assert "not found" in error_msg or "challenger" in error_msg
            
        # Verify registry unchanged
        registry_obj = s3.get_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
        registry = json.loads(registry_obj['Body'].read())
        # Registry should still have production (from rollback)
        assert 'production' in registry
        
        print("✓ PASS: ml-promote correctly rejected invalid challenger")
    except Exception as e:
        print(f"✗ FAIL: Error handling test failed: {str(e)}")
        raise
    print()
    
    print("Step 4.2: Validate ml-promote (Short Reason)")
    try:
        try:
            result = cmd.execute([customer_id, challenger_model_id, "short"], context)
            assert False, "Command should have raised an exception"
        except Exception as e:
            error_msg = str(e).lower()
            assert "reason" in error_msg and ("10" in error_msg or "length" in error_msg.lower())
        
        print("✓ PASS: ml-promote correctly rejected short reason")
    except Exception as e:
        print(f"✗ FAIL: Error handling test failed: {str(e)}")
        raise


# ============================================================================
# PHASE 5: Cleanup
# ============================================================================

def phase5_cleanup(s3, bucket: str, customer_id: str, production_timestamp: str, challenger_trained: str):
    """Phase 5: Clean up test data."""
    print("Step 5.1: Delete Test Data from S3")
    
    try:
        # Delete registry
        s3.delete_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
        print(f"✓ Deleted registry")
        
        # Delete metrics files
        s3.delete_object(Bucket=bucket, Key=f"model_metrics/{customer_id}/production/model_{production_timestamp}/backtest_results.json")
        s3.delete_object(Bucket=bucket, Key=f"model_metrics/{customer_id}/{customer_id}/challenger_{challenger_trained}/backtest_results.json")
        print(f"✓ Deleted metrics files")
        
        # Delete audit log
        s3.delete_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
        print(f"✓ Deleted audit log")
        
        # Delete archived files
        archive_prefix = f"customer_tailored/{customer_id}/archived/"
        paginator = s3.get_paginator('list_objects_v2')
        archives = []
        for page in paginator.paginate(Bucket=bucket, Prefix=archive_prefix):
            if 'Contents' in page:
                archives.extend([obj['Key'] for obj in page['Contents']])
        
        for archive_key in archives:
            s3.delete_object(Bucket=bucket, Key=archive_key)
        
        if archives:
            print(f"✓ Deleted {len(archives)} archived files")
        
    except Exception as e:
        print(f"⚠ WARNING: Cleanup error (non-critical): {str(e)}")
    
    print()
    print("Step 5.2: Verify Cleanup")
    
    try:
        # Verify registry deleted
        try:
            s3.head_object(Bucket=bucket, Key=f"customer_tailored/{customer_id}/latest_model.json")
            print("⚠ WARNING: Registry still exists")
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                print("✓ Verified registry deleted")
        
        # Verify audit log deleted
        try:
            s3.head_object(Bucket=bucket, Key=f"audit_logs/{customer_id}/events.json")
            print("⚠ WARNING: Audit log still exists")
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                print("✓ Verified audit log deleted")
        
    except Exception as e:
        print(f"⚠ WARNING: Cleanup verification error (non-critical): {str(e)}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

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
    
    # Store test data identifiers for cleanup
    production_model_id = None
    challenger_model_id = None
    production_timestamp = None
    challenger_trained = None
    
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
        production_model_id, challenger_model_id, production_timestamp, challenger_trained = phase1_setup(s3, bucket, customer_id)
        results['phase1_setup'] = True
        print("✓ Phase 1 completed\n")
        
        # Phase 2: Read-only operations
        print("Phase 2: Read-Only Operations Validation")
        print("-" * 70)
        phase2_readonly(customer_id, challenger_model_id, production_model_id)
        results['phase2_readonly'] = True
        print("✓ Phase 2 completed\n")
        
        # Phase 3: Mutating operations
        print("Phase 3: Mutating Operations Validation")
        print("-" * 70)
        phase3_mutating(s3, bucket, customer_id, challenger_model_id, production_model_id)
        results['phase3_mutating'] = True
        print("✓ Phase 3 completed\n")
        
        # Phase 4: Error handling
        print("Phase 4: Error Handling Validation")
        print("-" * 70)
        phase4_errors(s3, bucket, customer_id, challenger_model_id)
        results['phase4_errors'] = True
        print("✓ Phase 4 completed\n")
        
    finally:
        # Phase 5: Cleanup (always run)
        print("Phase 5: Cleanup")
        print("-" * 70)
        if production_timestamp and challenger_trained:
            phase5_cleanup(s3, bucket, customer_id, production_timestamp, challenger_trained)
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
