# Endpoint Connection Verification Plan

## Document Purpose

This document provides a **one-shot executable plan** to verify that Zorora REPL commands can actually connect to and communicate with ONA platform `globalTrainingService` API endpoints.

**Goal**: Prove that Zorora can connect to the real backend. If it cannot, STOP and do not proceed.

---

## Phase Execution Rules

**CRITICAL**: Phase 0 is a **MANDATORY BLOCKING GATE**. 

- Phase 0 MUST succeed before proceeding to any other phase
- If Phase 0 fails, STOP ALL WORK
- Do not create documentation, tests, or any other artifacts if Phase 0 fails
- Phase 0 failure means the system does not work - fix that first

**No exceptions.**

---

## Phase 0: Reality Check - MANDATORY BLOCKING GATE

### Change 0: Create and Execute Endpoint Verification Script

**File**: `scripts/verify_ona_endpoints.py` (new)

**Current Issue**: Unknown if Zorora can actually connect to `globalTrainingService`.

**Implementation**:

1. **Create verification script**:

```python
#!/usr/bin/env python3
"""
Mandatory endpoint verification script.
Tests actual connection to globalTrainingService API.

Exit codes:
  0: At least one endpoint responds (success)
  1: No endpoints respond (failure - STOP ALL WORK)
  2: Configuration error (missing env vars)
"""

import os
import sys
import requests
from urllib.parse import urljoin

# Configuration
BASE_URL = os.getenv('ONA_API_BASE_URL', 'https://api.ona-platform.internal/api/v1')
AUTH_TOKEN = os.getenv('ONA_API_TOKEN', '')
USE_IAM = os.getenv('ONA_USE_IAM', 'false').lower() == 'true'

# Test endpoint (read-only, minimal, no side effects)
TEST_ENDPOINT = '/challengers'
TEST_PARAMS = {'customer_id': 'test'}

def get_auth_headers():
    """Get authentication headers."""
    headers = {}
    if USE_IAM:
        # IAM auth - check for AWS credentials
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            print("ERROR: USE_IAM=true but AWS credentials not found")
            return None
        # In production, would use boto3 to get credentials
        # For now, check environment
        session_token = os.getenv('AWS_SESSION_TOKEN')
        if session_token:
            headers['X-Amz-Security-Token'] = session_token
    elif AUTH_TOKEN:
        headers['Authorization'] = f'Bearer {AUTH_TOKEN}'
    else:
        print("ERROR: No authentication configured")
        print("  Set ONA_API_TOKEN or ONA_USE_IAM=true with AWS credentials")
        return None
    return headers

def test_endpoint():
    """Test single endpoint connection."""
    url = urljoin(BASE_URL.rstrip('/'), TEST_ENDPOINT.lstrip('/'))
    
    print(f"Testing endpoint: {url}")
    print(f"  Method: GET")
    print(f"  Params: {TEST_PARAMS}")
    print(f"  Auth: {'IAM' if USE_IAM else 'Bearer Token'}")
    print()
    
    headers = get_auth_headers()
    if headers is None:
        return False
    
    try:
        response = requests.get(
            url,
            params=TEST_PARAMS,
            headers=headers,
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        # Truncate response body for display
        try:
            body = response.json()
            body_str = str(body)[:500]
            if len(str(body)) > 500:
                body_str += "... (truncated)"
            print(f"Response Body: {body_str}")
        except:
            print(f"Response Body: {response.text[:500]}")
        
        print()
        
        # Success criteria:
        # - 2xx: Success
        # - 401/403: Auth issue but endpoint exists (partial success)
        # - 404: Endpoint doesn't exist (failure)
        # - 5xx: Server error but endpoint exists (partial success)
        # - Connection/DNS error: Failure
        
        if response.status_code >= 200 and response.status_code < 300:
            print("✓ SUCCESS: Endpoint responded with 2xx")
            return True
        elif response.status_code in [401, 403]:
            print("⚠ PARTIAL SUCCESS: Endpoint exists but authentication failed")
            print("  This proves the endpoint exists - authentication can be fixed")
            return True
        elif response.status_code == 404:
            print("✗ FAILURE: Endpoint not found (404)")
            print("  This means the URL path is incorrect or endpoint doesn't exist")
            return False
        elif response.status_code >= 500:
            print("⚠ PARTIAL SUCCESS: Endpoint exists but server error")
            print("  This proves the endpoint exists - server issue can be investigated")
            return True
        else:
            print(f"✗ FAILURE: Unexpected status code {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"✗ FAILURE: Connection error")
        print(f"  {str(e)}")
        print()
        print("Possible causes:")
        print("  - DNS resolution failed (api.ona-platform.internal not resolvable)")
        print("  - Network connectivity issue")
        print("  - API Gateway not deployed")
        print("  - Wrong base URL")
        return False
        
    except requests.exceptions.Timeout as e:
        print(f"✗ FAILURE: Request timeout")
        print(f"  {str(e)}")
        return False
        
    except Exception as e:
        print(f"✗ FAILURE: Unexpected error")
        print(f"  {type(e).__name__}: {str(e)}")
        return False

def main():
    """Main entry point."""
    print("=" * 70)
    print("Zorora → globalTrainingService Endpoint Verification")
    print("=" * 70)
    print()
    print(f"Base URL: {BASE_URL}")
    print(f"Test Endpoint: {TEST_ENDPOINT}")
    print()
    
    success = test_endpoint()
    
    print("=" * 70)
    if success:
        print("RESULT: ✓ VERIFICATION PASSED")
        print()
        print("At least one endpoint responded. Connection is working.")
        print("You may proceed with Phase 1 (static analysis) and Phase 2 (tests).")
        sys.exit(0)
    else:
        print("RESULT: ✗ VERIFICATION FAILED")
        print()
        print("CRITICAL: No endpoints responded.")
        print("STOP ALL WORK. Fix connection issues before proceeding.")
        print()
        print("Next steps:")
        print("  1. Verify ONA_API_BASE_URL is correct")
        print("  2. Verify network connectivity to api.ona-platform.internal")
        print("  3. Verify API Gateway is deployed and accessible")
        print("  4. Verify authentication credentials")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

2. **Make script executable**:
```bash
chmod +x scripts/verify_ona_endpoints.py
```

3. **Execute script**:
```bash
python scripts/verify_ona_endpoints.py
```

**Success Criteria**:
- Script exits with code 0
- At least one endpoint responds (2xx, 401/403, or 5xx - proves endpoint exists)
- Full URL printed matches expected ONA platform path

**Failure Criteria**:
- Script exits with code 1
- Connection error (DNS, network, routing)
- 404 Not Found (endpoint doesn't exist)
- Configuration error (missing auth)

**If Phase 0 Fails**:
- **STOP ALL WORK**
- Do not proceed to Phase 1 or Phase 2
- Fix connection issues first
- Re-run Phase 0 until it passes

**Validation**:
- Script runs without Python errors
- Makes actual HTTP request to real API
- Provides clear success/failure signal
- Exit code reflects connection status

**Rollback**: N/A - This is verification only, no code changes.

---

## Phase 1: Static Analysis (ONLY IF Phase 0 Passes)

### Change 1: Document URL Construction

**File**: `docs/ENDPOINT_URL_VERIFICATION.md` (new)

**Prerequisite**: Phase 0 must have passed.

**Implementation**:

1. **Create verification document** with:
   - Table mapping Zorora commands → paths → full URLs
   - Verification of `urljoin` behavior with examples
   - Confirmation that paths match ONA platform expected paths

**Content Structure**:

```markdown
# Endpoint URL Verification

## Verification Status
- Phase 0: ✅ PASSED (endpoint connection verified)
- Date: [execution date]

## URL Construction Logic

Base URL: `https://api.ona-platform.internal/api/v1`
URL Join Logic: `urljoin(base_url.rstrip('/'), path.lstrip('/'))`

## Command → Path → Full URL Mapping

| Command | Path | Full URL | ONA Platform Path | Match |
|---------|------|----------|-------------------|-------|
| ml-list-challengers | /challengers | https://api.ona-platform.internal/api/v1/challengers | /api/v1/challengers | ✅ |
| ml-show-metrics | /metrics/{model_id} | https://api.ona-platform.internal/api/v1/metrics/{model_id} | /api/v1/metrics/{model_id} | ✅ |
| ml-diff | /diff | https://api.ona-platform.internal/api/v1/diff | /api/v1/diff | ✅ |
| ml-promote | /promote | https://api.ona-platform.internal/api/v1/promote | /api/v1/promote | ✅ |
| ml-rollback | /rollback | https://api.ona-platform.internal/api/v1/rollback | /api/v1/rollback | ✅ |
| ml-audit-log | /audit-log | https://api.ona-platform.internal/api/v1/audit-log | /api/v1/audit-log | ✅ |

## Verification Results
[Results from Phase 0 execution]
```

**Validation**:
- Document created only after Phase 0 passes
- All command paths documented
- URL construction verified correct
- Matches ONA platform expected paths

**Rollback**: Remove document if Phase 0 fails.

---

## Phase 2: Integration Test Enhancement (ONLY IF Phase 0 Passes)

### Change 2: Add URL Verification to Tests

**File**: `/Users/shingi/Workbench/platform/tests/services/test_zorora_integration.py`

**Prerequisite**: Phase 0 must have passed.

**Implementation**:

1. **Add URL construction test**:

```python
def test_url_construction():
    """Verify URL construction matches expected endpoints."""
    from zorora.http_client import ZororaHTTPClient
    from urllib.parse import urljoin
    
    base_url = 'https://api.ona-platform.internal/api/v1'
    client = ZororaHTTPClient(base_url=base_url)
    
    # Test urljoin behavior
    test_cases = [
        ('/challengers', '/api/v1/challengers'),
        ('/metrics/test-model', '/api/v1/metrics/test-model'),
        ('/diff', '/api/v1/diff'),
        ('/promote', '/api/v1/promote'),
        ('/rollback', '/api/v1/rollback'),
        ('/audit-log', '/api/v1/audit-log'),
    ]
    
    for path, expected_suffix in test_cases:
        full_url = urljoin(base_url.rstrip('/'), path.lstrip('/'))
        assert full_url.endswith(expected_suffix), \
            f"URL construction failed: {full_url} does not end with {expected_suffix}"
```

**Validation**:
- Test added only after Phase 0 passes
- Test verifies URL construction logic
- Test fails if paths don't match expected endpoints

**Rollback**: Remove test if Phase 0 fails.

---

## Execution Order

**MANDATORY ORDER**:

1. **Phase 0**: Execute `scripts/verify_ona_endpoints.py`
   - If fails: **STOP** - Fix connection issues
   - If passes: Continue to Phase 1

2. **Phase 1**: Create `docs/ENDPOINT_URL_VERIFICATION.md`
   - Only if Phase 0 passed

3. **Phase 2**: Add URL verification test
   - Only if Phase 0 passed

**No phase may be skipped or reordered.**

---

## Success Criteria

**Overall Success**:
- ✅ Phase 0 passes (at least one endpoint responds)
- ✅ Phase 1 documents URL construction correctly
- ✅ Phase 2 test verifies URL construction

**If Phase 0 Fails**:
- ❌ Do not proceed
- ❌ Do not create documentation
- ❌ Do not add tests
- ✅ Fix connection issues first

---

## Troubleshooting

### Phase 0 Fails with Connection Error

**Possible causes**:
- DNS resolution failed (`api.ona-platform.internal` not resolvable)
- Network connectivity issue
- API Gateway not deployed
- Wrong base URL

**Fix steps**:
1. Verify `ONA_API_BASE_URL` environment variable
2. Test DNS: `nslookup api.ona-platform.internal`
3. Test connectivity: `curl -v https://api.ona-platform.internal/api/v1/challengers`
4. Verify API Gateway deployment

### Phase 0 Fails with 404

**Possible causes**:
- URL path incorrect
- API Gateway routing misconfigured
- Endpoint not deployed

**Fix steps**:
1. Verify API Gateway routes match `/api/v1/*`
2. Check Lambda function routing logic
3. Verify endpoint paths in `globalTrainingService/app.py`

### Phase 0 Fails with 401/403

**This is PARTIAL SUCCESS** - endpoint exists, auth needs fixing:
1. Verify `ONA_API_TOKEN` is set correctly
2. Verify IAM credentials if using `ONA_USE_IAM=true`
3. Check API Gateway authorizer configuration

---

**Document Status**: One-Shot Ready  
**Last Updated**: 2025-01-23  
**Author**: AI Coding Assistant  
**Review Status**: Awaiting approval
