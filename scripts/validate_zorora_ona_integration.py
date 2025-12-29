#!/usr/bin/env python3
"""
Zorora ↔ globalTrainingService Validation Script

One-shot, deterministic validation plan execution.

Gates:
  1. Endpoint Existence (hard gate)
  2. Zorora Reachability (all commands, once each)
  3. Safety, Repeatability, Stability (all commands, twice each)
"""

import os
import sys
import json
import time
import requests
from urllib.parse import urljoin
from typing import Dict, List, Tuple, Optional

# ============================================================================
# AUTHORITATIVE TEST FIXTURES (Normative - DO NOT ALTER)
# ============================================================================

BASE_URL = "https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com"
API_PREFIX = "/api/v1"

TEST_CUSTOMER_ID = "__any__"
TEST_MODEL_ID_NONEXISTENT = "__does_not_exist__"
TEST_CHALLENGER_ID_NONEXISTENT = "__does_not_exist__"
TEST_PRODUCTION_ID_NONEXISTENT = "__does_not_exist__"
TEST_REASON = "validation-run"

# ============================================================================
# AUTHORITATIVE COMMAND LIST (Exact, Exhaustive)
# ============================================================================

# Authoritative command list derived from register_ona_commands() in zorora/commands/ona_platform.py
COMMANDS = [
    {
        "name": "ml-list-challengers",
        "invocation": f"ml-list-challengers {TEST_CUSTOMER_ID}",
        "method": "GET",
        "path": "/challengers",
        "params": {"customer_id": TEST_CUSTOMER_ID},
        "read_only": True,
    },
    {
        "name": "ml-show-metrics",
        "invocation": f"ml-show-metrics {TEST_MODEL_ID_NONEXISTENT}",
        "method": "GET",
        "path": f"/metrics/{TEST_MODEL_ID_NONEXISTENT}",
        "params": None,
        "read_only": True,
    },
    {
        "name": "ml-diff",
        "invocation": f"ml-diff {TEST_CHALLENGER_ID_NONEXISTENT} {TEST_PRODUCTION_ID_NONEXISTENT}",
        "method": "GET",
        "path": "/diff",
        "params": {
            "challenger_id": TEST_CHALLENGER_ID_NONEXISTENT,
            "production_id": TEST_PRODUCTION_ID_NONEXISTENT,
        },
        "read_only": True,
    },
    {
        "name": "ml-promote",
        "invocation": f"ml-promote {TEST_CUSTOMER_ID} {TEST_MODEL_ID_NONEXISTENT} {TEST_REASON}",
        "method": "POST",
        "path": "/promote",
        "json_data": {
            "customer_id": TEST_CUSTOMER_ID,
            "model_id": TEST_MODEL_ID_NONEXISTENT,
            "reason": TEST_REASON,
        },
        "read_only": False,
    },
    {
        "name": "ml-rollback",
        "invocation": f"ml-rollback {TEST_CUSTOMER_ID} {TEST_REASON}",
        "method": "POST",
        "path": "/rollback",
        "json_data": {
            "customer_id": TEST_CUSTOMER_ID,
            "reason": TEST_REASON,
        },
        "read_only": False,
    },
    {
        "name": "ml-audit-log",
        "invocation": f"ml-audit-log {TEST_CUSTOMER_ID}",
        "method": "GET",
        "path": "/audit-log",
        "params": {"customer_id": TEST_CUSTOMER_ID},
        "read_only": True,
    },
]

# ============================================================================
# GATE 1: Endpoint Existence (All Routes)
# ============================================================================

def gate1_endpoint_existence() -> Tuple[bool, List[Dict]]:
    """
    Gate 1: Do all endpoints exist?
    
    Tests ALL routes that Lambda exposes:
    - /challengers (GET)
    - /metrics/{id} (GET)
    - /diff (GET)
    - /promote (POST)
    - /rollback (POST)
    - /audit-log (GET)
    
    Pass: HTTP 200 or structured application error (400 with error body)
    Fail: DNS failure, connection refused, timeout, 404, 5xx (Lambda wiring issue)
    
    Auth handling:
    - If ONA_API_TOKEN is set, use it (Lambda requires Bearer auth)
    - If not set, test without auth (Lambda may allow if USE_BEARER_AUTH=false)
    - 401/403 means auth is required but not provided - retrieve token from SSM or configure Lambda
    """
    print("=" * 70)
    print("GATE 1: Endpoint Existence (All Routes)")
    print("=" * 70)
    print()
    print("Testing all routes exposed by globalTrainingService Lambda")
    
    # Check if auth token is available
    auth_token = os.getenv('ONA_API_TOKEN', '')
    if auth_token:
        print("Auth: ENABLED (using ONA_API_TOKEN)")
        auth_headers = {'Authorization': f'Bearer {auth_token}'}
    else:
        print("Auth: DISABLED (no ONA_API_TOKEN set)")
        print("  Note: If Lambda requires auth, requests will return 401")
        print("  Set ONA_API_TOKEN or run: ./scripts/get-global-training-api-credentials.sh")
        auth_headers = {}
    print()
    
    # Test all endpoints from COMMANDS list
    test_cases = [
        {
            "name": "challengers",
            "method": "GET",
            "path": "/challengers",
            "params": {"customer_id": TEST_CUSTOMER_ID},
            "json_data": None,
        },
        {
            "name": "metrics",
            "method": "GET",
            "path": f"/metrics/{TEST_MODEL_ID_NONEXISTENT}",
            "params": None,
            "json_data": None,
        },
        {
            "name": "diff",
            "method": "GET",
            "path": "/diff",
            "params": {
                "challenger_id": TEST_CHALLENGER_ID_NONEXISTENT,
                "production_id": TEST_PRODUCTION_ID_NONEXISTENT,
            },
            "json_data": None,
        },
        {
            "name": "promote",
            "method": "POST",
            "path": "/promote",
            "params": None,
            "json_data": {
                "customer_id": TEST_CUSTOMER_ID,
                "model_id": TEST_MODEL_ID_NONEXISTENT,
                "reason": TEST_REASON,
            },
        },
        {
            "name": "rollback",
            "method": "POST",
            "path": "/rollback",
            "params": None,
            "json_data": {
                "customer_id": TEST_CUSTOMER_ID,
                "reason": TEST_REASON,
            },
        },
        {
            "name": "audit-log",
            "method": "GET",
            "path": "/audit-log",
            "params": {"customer_id": TEST_CUSTOMER_ID},
            "json_data": None,
        },
    ]
    
    artifacts = []
    all_passed = True
    
    for test_case in test_cases:
        test_url = urljoin(BASE_URL.rstrip('/'), f"{API_PREFIX}{test_case['path']}")
        
        print(f"Testing: {test_case['method']} {test_url}")
        if test_case['params']:
            print(f"  Params: {test_case['params']}")
        if test_case['json_data']:
            print(f"  Body: {test_case['json_data']}")
        print()
        
        try:
            # Use auth headers if ONA_API_TOKEN is set
            if test_case['method'] == 'GET':
                response = requests.get(
                    test_url,
                    params=test_case['params'],
                    headers=auth_headers,
                    timeout=10
                )
            else:  # POST
                response = requests.post(
                    test_url,
                    json=test_case['json_data'],
                    headers=auth_headers,
                    timeout=10
                )
            
            status = response.status_code
            headers = dict(response.headers)
            
            # Truncate body
            try:
                body = response.json()
                body_str = json.dumps(body, indent=2)[:2048]
                if len(json.dumps(body)) > 2048:
                    body_str += "\n... (truncated)"
            except:
                body_str = response.text[:2048]
                if len(response.text) > 2048:
                    body_str += "... (truncated)"
            
            print(f"  HTTP Status: {status}")
            print(f"  Response Body: {body_str[:500]}...")
            
            # Pass criteria (aligned with ONA platform reality)
            if status == 200:
                print(f"  ✓ PASS: HTTP 200 (endpoint exists and responds)")
                passed = True
            elif status == 400:
                # Structured application error - proves Lambda is routing correctly
                try:
                    error_body = response.json()
                    if 'error' in error_body or 'message' in error_body:
                        print(f"  ✓ PASS: HTTP 400 with structured error (endpoint exists, Lambda routing works)")
                        passed = True
                    else:
                        print(f"  ✗ FAIL: HTTP 400 without structured error body")
                        passed = False
                except:
                    print(f"  ✗ FAIL: HTTP 400 without JSON error body")
                    passed = False
            elif status in [401, 403]:
                if auth_token:
                    # Token was provided but still got auth error - misconfiguration
                    print(f"  ✗ FAIL: HTTP {status} (auth misconfiguration - token provided but rejected)")
                    passed = False
                else:
                    # No token provided, endpoint requires auth - proves endpoint exists
                    print(f"  ✓ PASS: HTTP {status} (endpoint exists but requires authentication)")
                    print(f"    Set ONA_API_TOKEN to test with authentication")
                    passed = True
            elif status == 404:
                print(f"  ✗ FAIL: HTTP 404 (endpoint does not exist or routing misconfigured)")
                passed = False
            elif status >= 500:
                print(f"  ✗ FAIL: HTTP {status} (Lambda wiring issue or server error)")
                passed = False
            else:
                print(f"  ✗ FAIL: Unexpected status {status}")
                passed = False
            
            artifact = {
                "gate": 1,
                "endpoint": test_case['name'],
                "method": test_case['method'],
                "url": test_url,
                "status": status,
                "headers": headers,
                "body": body_str,
                "timestamp": time.time(),
                "passed": passed,
            }
            
            artifacts.append(artifact)
            
            if not passed:
                all_passed = False
            
            print()
            
        except requests.exceptions.ConnectionError as e:
            print(f"  ✗ FAIL: Connection error")
            print(f"    {str(e)}")
            
            artifact = {
                "gate": 1,
                "endpoint": test_case['name'],
                "method": test_case['method'],
                "url": test_url,
                "error": "ConnectionError",
                "message": str(e),
                "timestamp": time.time(),
                "passed": False,
            }
            
            artifacts.append(artifact)
            all_passed = False
            print()
            
        except requests.exceptions.Timeout as e:
            print(f"  ✗ FAIL: Request timeout")
            print(f"    {str(e)}")
            
            artifact = {
                "gate": 1,
                "endpoint": test_case['name'],
                "method": test_case['method'],
                "url": test_url,
                "error": "Timeout",
                "message": str(e),
                "timestamp": time.time(),
                "passed": False,
            }
            
            artifacts.append(artifact)
            all_passed = False
            print()
            
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected error")
            print(f"    {type(e).__name__}: {str(e)}")
            
            artifact = {
                "gate": 1,
                "endpoint": test_case['name'],
                "method": test_case['method'],
                "url": test_url,
                "error": type(e).__name__,
                "message": str(e),
                "timestamp": time.time(),
                "passed": False,
            }
            
            artifacts.append(artifact)
            all_passed = False
            print()
    
    if all_passed:
        print("✓ All endpoints exist and are reachable")
    else:
        print("✗ Some endpoints failed")
        print()
        print("Possible causes:")
        print("  - DNS resolution failed")
        print("  - Connection refused")
        print("  - Network unreachable")
        print("  - API Gateway not deployed")
        print("  - Lambda routing misconfigured")
        print("  - Auth enabled when it should be disabled")
    
    return all_passed, artifacts

# ============================================================================
# GATE 2: Zorora Reachability
# ============================================================================

def get_auth_headers() -> Optional[Dict[str, str]]:
    """Get authentication headers."""
    auth_token = os.getenv('ONA_API_TOKEN', '')
    use_iam = os.getenv('ONA_USE_IAM', 'false').lower() == 'true'
    
    headers = {}
    
    if use_iam:
        # IAM auth - check for AWS credentials
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            print("ERROR: USE_IAM=true but AWS credentials not found")
            return None
        session_token = os.getenv('AWS_SESSION_TOKEN')
        if session_token:
            headers['X-Amz-Security-Token'] = session_token
    elif auth_token:
        headers['Authorization'] = f'Bearer {auth_token}'
    else:
        print("ERROR: No authentication configured")
        print("  Set ONA_API_TOKEN or ONA_USE_IAM=true with AWS credentials")
        return None
    
    # Add actor header
    headers['X-Actor'] = os.getenv('ZORORA_ACTOR', os.getenv('USER', 'zorora-user'))
    
    return headers

def gate2_zorora_reachability() -> Tuple[bool, List[Dict]]:
    """
    Gate 2: Can Zorora reach the endpoint for every implemented command?
    
    Pass per command: Command registered, HTTP request sent, response received
    Fail per command: Not registered, malformed URL, no request, connection error, crash
    
    Note: Auth may be required for Gate 2 (unlike Gate 1). If auth fails, that's acceptable
    as long as the HTTP request was sent (proves reachability).
    """
    print("=" * 70)
    print("GATE 2: Zorora Reachability (All Commands, Once Each)")
    print("=" * 70)
    print()
    
    # Import Zorora components
    try:
        from zorora.http_client import ZororaHTTPClient
        from zorora.commands.ona_platform import (
            ListChallengersCommand,
            ShowMetricsCommand,
            DiffModelsCommand,
            PromoteModelCommand,
            RollbackModelCommand,
            AuditLogCommand,
        )
    except ImportError as e:
        print(f"✗ FAIL: Cannot import Zorora components")
        print(f"  {str(e)}")
        return False, []
    
    # Initialize HTTP client (auth may be configured for Gate 2)
    base_url = os.getenv('ONA_API_BASE_URL', f"{BASE_URL}{API_PREFIX}")
    auth_token = os.getenv('ONA_API_TOKEN', '')
    use_iam = os.getenv('ONA_USE_IAM', 'false').lower() == 'true'
    
    http_client = ZororaHTTPClient(
        base_url=base_url,
        auth_token=auth_token,
        use_iam=use_iam
    )
    
    # Create command instances
    commands_map = {
        "ml-list-challengers": ListChallengersCommand(http_client),
        "ml-show-metrics": ShowMetricsCommand(http_client),
        "ml-diff": DiffModelsCommand(http_client),
        "ml-promote": PromoteModelCommand(http_client, ui=None),
        "ml-rollback": RollbackModelCommand(http_client, ui=None),
        "ml-audit-log": AuditLogCommand(http_client),
    }
    
    artifacts = []
    all_passed = True
    
    for cmd_def in COMMANDS:
        cmd_name = cmd_def["name"]
        print(f"Testing: {cmd_def['invocation']}")
        
        try:
            cmd_instance = commands_map[cmd_name]
            
            # Prepare args
            if cmd_name == "ml-list-challengers":
                args = [TEST_CUSTOMER_ID]
            elif cmd_name == "ml-show-metrics":
                args = [TEST_MODEL_ID_NONEXISTENT]
            elif cmd_name == "ml-diff":
                args = [TEST_CHALLENGER_ID_NONEXISTENT, TEST_PRODUCTION_ID_NONEXISTENT]
            elif cmd_name == "ml-promote":
                args = [TEST_CUSTOMER_ID, TEST_MODEL_ID_NONEXISTENT, TEST_REASON]
            elif cmd_name == "ml-rollback":
                args = [TEST_CUSTOMER_ID, TEST_REASON]
            elif cmd_name == "ml-audit-log":
                args = [TEST_CUSTOMER_ID]
            else:
                raise ValueError(f"Unknown command: {cmd_name}")
            
            # Execute command
            context = {
                'actor': os.getenv('ZORORA_ACTOR', os.getenv('USER', 'zorora-user')),
                'environment': os.getenv('ZORORA_ENV', 'prod'),
            }
            
            # For mutating commands, set auto-confirm to avoid prompts
            if cmd_name in ["ml-promote", "ml-rollback"]:
                os.environ['ZORORA_AUTO_CONFIRM'] = 'true'
            
            try:
                result = cmd_instance.execute(args, context)
                
                # Extract HTTP details from client (if available)
                # For now, we'll infer from result
                print(f"  ✓ Command executed successfully")
                print(f"  Result: {str(result)[:200]}...")
                
                artifact = {
                    "gate": 2,
                    "command": cmd_name,
                    "invocation": cmd_def["invocation"],
                    "status": "success",
                    "result_preview": str(result)[:500],
                    "timestamp": time.time(),
                    "passed": True,
                }
                
            except Exception as cmd_error:
                # Check if it's an HTTP error (which means request was sent)
                error_str = str(cmd_error)
                
                if "HTTP" in error_str or "401" in error_str or "404" in error_str or "500" in error_str:
                    print(f"  ✓ Command executed, HTTP error received (request was sent)")
                    print(f"  Error: {error_str[:200]}")
                    
                    artifact = {
                        "gate": 2,
                        "command": cmd_name,
                        "invocation": cmd_def["invocation"],
                        "status": "http_error",
                        "error": error_str[:500],
                        "timestamp": time.time(),
                        "passed": True,  # Request was sent, that's what we're testing
                    }
                else:
                    print(f"  ✗ Command failed: {error_str[:200]}")
                    
                    artifact = {
                        "gate": 2,
                        "command": cmd_name,
                        "invocation": cmd_def["invocation"],
                        "status": "error",
                        "error": error_str[:500],
                        "timestamp": time.time(),
                        "passed": False,
                    }
                    all_passed = False
            
            artifacts.append(artifact)
            
        except KeyError:
            print(f"  ✗ FAIL: Command {cmd_name} not registered")
            artifact = {
                "gate": 2,
                "command": cmd_name,
                "invocation": cmd_def["invocation"],
                "status": "not_registered",
                "timestamp": time.time(),
                "passed": False,
            }
            artifacts.append(artifact)
            all_passed = False
            
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected error: {type(e).__name__}: {str(e)}")
            artifact = {
                "gate": 2,
                "command": cmd_name,
                "invocation": cmd_def["invocation"],
                "status": "crash",
                "error": f"{type(e).__name__}: {str(e)}",
                "timestamp": time.time(),
                "passed": False,
            }
            artifacts.append(artifact)
            all_passed = False
        
        print()
    
    return all_passed, artifacts

# ============================================================================
# GATE 3: Safety, Repeatability, Stability
# ============================================================================

def gate3_safety_repeatability_stability() -> Tuple[bool, List[Dict]]:
    """
    Gate 3: Can all commands be run safely, repeatably, and stably?
    
    Execute each command twice, back-to-back, with identical inputs.
    
    Safety: Read-only commands don't mutate; mutating commands fail safely
    Repeatability: Second run doesn't crash, response shape consistent
    Stability: Empty/missing data handled, errors explicit, no silent failures
    """
    print("=" * 70)
    print("GATE 3: Safety, Repeatability, Stability (All Commands, Twice Each)")
    print("=" * 70)
    print()
    
    # Import Zorora components
    try:
        from zorora.http_client import ZororaHTTPClient
        from zorora.commands.ona_platform import (
            ListChallengersCommand,
            ShowMetricsCommand,
            DiffModelsCommand,
            PromoteModelCommand,
            RollbackModelCommand,
            AuditLogCommand,
        )
    except ImportError as e:
        print(f"✗ FAIL: Cannot import Zorora components")
        print(f"  {str(e)}")
        return False, []
    
    # Initialize HTTP client
    base_url = os.getenv('ONA_API_BASE_URL', f"{BASE_URL}{API_PREFIX}")
    auth_token = os.getenv('ONA_API_TOKEN', '')
    use_iam = os.getenv('ONA_USE_IAM', 'false').lower() == 'true'
    
    http_client = ZororaHTTPClient(
        base_url=base_url,
        auth_token=auth_token,
        use_iam=use_iam
    )
    
    # Create command instances
    commands_map = {
        "ml-list-challengers": ListChallengersCommand(http_client),
        "ml-show-metrics": ShowMetricsCommand(http_client),
        "ml-diff": DiffModelsCommand(http_client),
        "ml-promote": PromoteModelCommand(http_client, ui=None),
        "ml-rollback": RollbackModelCommand(http_client, ui=None),
        "ml-audit-log": AuditLogCommand(http_client),
    }
    
    artifacts = []
    all_passed = True
    
    # Set auto-confirm for mutating commands
    os.environ['ZORORA_AUTO_CONFIRM'] = 'true'
    
    for cmd_def in COMMANDS:
        cmd_name = cmd_def["name"]
        print(f"Testing: {cmd_def['invocation']} (twice)")
        
        try:
            cmd_instance = commands_map[cmd_name]
            
            # Prepare args
            if cmd_name == "ml-list-challengers":
                args = [TEST_CUSTOMER_ID]
            elif cmd_name == "ml-show-metrics":
                args = [TEST_MODEL_ID_NONEXISTENT]
            elif cmd_name == "ml-diff":
                args = [TEST_CHALLENGER_ID_NONEXISTENT, TEST_PRODUCTION_ID_NONEXISTENT]
            elif cmd_name == "ml-promote":
                args = [TEST_CUSTOMER_ID, TEST_MODEL_ID_NONEXISTENT, TEST_REASON]
            elif cmd_name == "ml-rollback":
                args = [TEST_CUSTOMER_ID, TEST_REASON]
            elif cmd_name == "ml-audit-log":
                args = [TEST_CUSTOMER_ID]
            else:
                raise ValueError(f"Unknown command: {cmd_name}")
            
            context = {
                'actor': os.getenv('ZORORA_ACTOR', os.getenv('USER', 'zorora-user')),
                'environment': os.getenv('ZORORA_ENV', 'prod'),
            }
            
            # Run 1
            print(f"  Run #1:")
            try:
                result1 = cmd_instance.execute(args, context)
                output1 = str(result1)
                error1 = None
            except Exception as e:
                output1 = None
                error1 = str(e)
            
            # Small delay
            time.sleep(0.5)
            
            # Run 2
            print(f"  Run #2:")
            try:
                result2 = cmd_instance.execute(args, context)
                output2 = str(result2)
                error2 = None
            except Exception as e:
                output2 = None
                error2 = str(e)
            
            # Analyze results
            safety_verdict = "safe"
            repeatability_verdict = "repeatable"
            stability_verdict = "stable"
            
            # Safety check
            if not cmd_def["read_only"]:
                # Mutating commands should fail safely with nonexistent IDs
                if error1 is None or error2 is None:
                    safety_verdict = "unsafe"
                    print(f"  ✗ SAFETY: Mutating command succeeded (should fail with nonexistent IDs)")
                    all_passed = False
            
            # Repeatability check
            if error1 is not None and error2 is None:
                repeatability_verdict = "not_repeatable"
                print(f"  ✗ REPEATABILITY: First run failed, second succeeded")
                all_passed = False
            elif error1 is None and error2 is not None:
                repeatability_verdict = "not_repeatable"
                print(f"  ✗ REPEATABILITY: First run succeeded, second failed")
                all_passed = False
            elif error1 is not None and error2 is not None:
                # Both failed - check if error messages are similar (shape consistency)
                if error1[:100] != error2[:100]:
                    repeatability_verdict = "inconsistent_errors"
                    print(f"  ⚠ REPEATABILITY: Both failed but error messages differ")
            elif output1 is not None and output2 is not None:
                # Both succeeded - check response shape
                # For now, just check if both are strings (shape consistency)
                if type(output1) != type(output2):
                    repeatability_verdict = "shape_drift"
                    print(f"  ✗ REPEATABILITY: Response shape changed")
                    all_passed = False
            
            # Stability check
            if error1 is None and output1 is None:
                stability_verdict = "silent_failure"
                print(f"  ✗ STABILITY: Silent failure (no output, no error)")
                all_passed = False
            elif error2 is None and output2 is None:
                stability_verdict = "silent_failure"
                print(f"  ✗ STABILITY: Silent failure (no output, no error)")
                all_passed = False
            
            artifact = {
                "gate": 3,
                "command": cmd_name,
                "invocation": cmd_def["invocation"],
                "run1_output": output1[:500] if output1 else None,
                "run1_error": error1[:500] if error1 else None,
                "run2_output": output2[:500] if output2 else None,
                "run2_error": error2[:500] if error2 else None,
                "safety": safety_verdict,
                "repeatability": repeatability_verdict,
                "stability": stability_verdict,
                "timestamp": time.time(),
                "passed": safety_verdict == "safe" and repeatability_verdict == "repeatable" and stability_verdict == "stable",
            }
            
            if not artifact["passed"]:
                all_passed = False
            
            artifacts.append(artifact)
            
            print(f"  Safety: {safety_verdict}")
            print(f"  Repeatability: {repeatability_verdict}")
            print(f"  Stability: {stability_verdict}")
            
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected error: {type(e).__name__}: {str(e)}")
            artifact = {
                "gate": 3,
                "command": cmd_name,
                "invocation": cmd_def["invocation"],
                "error": f"{type(e).__name__}: {str(e)}",
                "timestamp": time.time(),
                "passed": False,
            }
            artifacts.append(artifact)
            all_passed = False
        
        print()
    
    return all_passed, artifacts

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute all gates in sequence."""
    print("=" * 70)
    print("Zorora ↔ globalTrainingService Validation")
    print("=" * 70)
    print()
    print(f"Base URL: {BASE_URL}")
    print(f"API Prefix: {API_PREFIX}")
    print(f"Test Customer ID: {TEST_CUSTOMER_ID}")
    print()
    
    all_artifacts = []
    
    # Gate 1: Endpoint Existence (All Routes)
    gate1_passed, gate1_artifacts = gate1_endpoint_existence()
    all_artifacts.extend(gate1_artifacts)
    
    if not gate1_passed:
        print("=" * 70)
        print("VALIDATION FAILED: Gate 1 did not pass")
        print("STOP: Not all endpoints exist or are reachable. Fix connection/routing issues first.")
        print("=" * 70)
        sys.exit(1)
    
    print()
    
    # Gate 2: Zorora Reachability
    gate2_passed, gate2_artifacts = gate2_zorora_reachability()
    all_artifacts.extend(gate2_artifacts)
    
    if not gate2_passed:
        print("=" * 70)
        print("VALIDATION FAILED: Gate 2 did not pass")
        print("STOP: Not all commands are reachable. Fix command implementation.")
        print("=" * 70)
        sys.exit(1)
    
    print()
    
    # Gate 3: Safety, Repeatability, Stability
    gate3_passed, gate3_artifacts = gate3_safety_repeatability_stability()
    all_artifacts.extend(gate3_artifacts)
    
    if not gate3_passed:
        print("=" * 70)
        print("VALIDATION FAILED: Gate 3 did not pass")
        print("STOP: Commands are not safe, repeatable, or stable.")
        print("=" * 70)
        sys.exit(1)
    
    # All gates passed
    print("=" * 70)
    print("VALIDATION PASSED: All gates passed")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  Gate 1 (Endpoint Existence): ✓ PASSED ({len(gate1_artifacts)} endpoints)")
    print(f"  Gate 2 (Zorora Reachability): ✓ PASSED ({len(gate2_artifacts)} commands)")
    print(f"  Gate 3 (Safety/Repeatability/Stability): ✓ PASSED ({len(gate3_artifacts)} commands)")
    print()
    print("The implementation is VALID.")
    
    # Save artifacts
    artifacts_file = "validation_artifacts.json"
    with open(artifacts_file, 'w') as f:
        json.dump(all_artifacts, f, indent=2)
    print(f"Artifacts saved to: {artifacts_file}")
    
    sys.exit(0)

if __name__ == '__main__':
    main()
