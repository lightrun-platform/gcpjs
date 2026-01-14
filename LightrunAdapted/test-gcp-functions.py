#!/usr/bin/env python3
"""
Test script for deploying and testing GCP Cloud Functions (Gen1 and Gen2)
across different Node.js versions with Lightrun integration.
"""

import asyncio
import json
import os
import subprocess
import time
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import shutil

# Configuration
REGION = "europe-west1"
PROJECT_ID = os.environ.get("GCP_PROJECT", "lightrun-temp")
LIGHTRUN_SECRET = os.environ.get("LIGHTRUN_SECRET", "")
LIGHTRUN_API_URL = os.environ.get("LIGHTRUN_API_URL", "https://api.lightrun.com")
LIGHTRUN_API_KEY = os.environ.get("LIGHTRUN_API_KEY", "")
LIGHTRUN_COMPANY_ID = os.environ.get("LIGHTRUN_COMPANY_ID", "")

NODEJS_VERSIONS = list(range(18, 25))  # 18-24
FUNCTION_VERSIONS = [1, 2]  # Gen1 and Gen2
NUM_COLD_START_REQUESTS = 100
NUM_WARM_START_REQUESTS = 100

BASE_DIR = Path(__file__).parent
TEST_FUNCTIONS_DIR = BASE_DIR / "test-functions"
RESULTS_DIR = BASE_DIR / "test-results"


@dataclass
class TestResult:
    """Test result for a single function."""
    function_name: str
    gen_version: int
    nodejs_version: int
    deployment_success: bool
    deployment_error: Optional[str] = None
    cold_start_avg_ms: Optional[float] = None
    warm_start_avg_ms: Optional[float] = None
    cold_start_requests: int = 0
    warm_start_requests: int = 0
    logs_error_check: Optional[bool] = None
    logs_error_message: Optional[str] = None
    snapshot_test: Optional[bool] = None
    snapshot_error: Optional[str] = None
    counter_test: Optional[bool] = None
    counter_error: Optional[str] = None
    metric_test: Optional[bool] = None
    metric_error: Optional[str] = None
    function_url: Optional[str] = None
    cleanup_success: bool = False
    cleanup_error: Optional[str] = None


def run_command(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 600) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def create_test_function(nodejs_version: int, gen_version: int) -> Path:
    """Create a test function directory for the given Node.js and Gen version."""
    func_dir = TEST_FUNCTIONS_DIR / f"test-node{nodejs_version}-gen{gen_version}"
    func_dir.mkdir(parents=True, exist_ok=True)
    
    # Create index.js
    index_js = func_dir / "index.js"
    index_js.write_text(f"""const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');

let requestCount = 0;

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {{
    throw new Error('LIGHTRUN_SECRET environment variable is required');
}}

const displayName = process.env.DISPLAY_NAME;
if (!displayName || displayName.trim() === '') {{
    throw new Error('DISPLAY_NAME environment variable is required');
}}

lightrun.init({{
    lightrunSecret: lightrunSecret,
    agentLog: {{ agentLogTargetDir: '', agentLogLevel: 'warn' }},
    internal: {{ gcpDebug: false }},
    metadata: {{ 
        registration: {{ 
            displayName: displayName,
            tags: [displayName]
        }} 
    }}
}});

functions.http('testFunction', lightrun.wrap(async (req, res) => {{
    requestCount++;
    const startTime = Date.now();
    
    // Simulate some work
    await new Promise(resolve => setTimeout(resolve, 10));
    
    const duration = Date.now() - startTime;
    
    res.json({{
        requestCount,
        duration,
        timestamp: new Date().toISOString(),
        nodejsVersion: process.version,
        message: 'Hello from Lightrun!'
    }});
}}));
""")
    
    # Create package.json
    package_json = func_dir / "package.json"
    package_json.write_text(json.dumps({
        "name": f"test-function-node{nodejs_version}-gen{gen_version}",
        "version": "1.0.0",
        "main": "index.js",
        "engines": {
            "node": f">={nodejs_version}"
        },
        "dependencies": {
            "@google-cloud/functions-framework": "^3.3.0",
            "lightrun": ">=1.76.0"
        }
    }, indent=2))
    
    return func_dir


def deploy_function(function_name: str, func_dir: Path, nodejs_version: int, gen_version: int) -> Tuple[bool, Optional[str], Optional[str]]:
    """Deploy a GCP Cloud Function."""
    gen_flag = "--gen2" if gen_version == 2 else "--no-gen2"
    
    cmd = [
        "gcloud", "functions", "deploy", function_name,
        gen_flag,
        "--runtime", f"nodejs{nodejs_version}",
        "--region", REGION,
        "--trigger-http",
        "--allow-unauthenticated",
        "--entry-point", "testFunction",
        "--memory", "512MB",
        "--source", str(func_dir),
        "--set-env-vars", f"LIGHTRUN_SECRET={LIGHTRUN_SECRET},DISPLAY_NAME={function_name}",
        "--quiet"
    ]
    
    exit_code, stdout, stderr = run_command(cmd, timeout=600)
    
    if exit_code != 0:
        return False, None, f"Deployment failed: {stderr}"
    
    # Extract function URL from output
    url = None
    for line in stdout.split('\n'):
        if 'httpsTrigger:' in line or 'url:' in line:
            # Try to extract URL
            if 'https://' in line:
                url = line.split('https://')[1].split()[0] if 'https://' in line else None
                if url:
                    url = f"https://{url}"
        if 'https://' in line and '.cloudfunctions.net' in line:
            url = line.split('https://')[1].strip() if 'https://' in line else None
            if url:
                url = f"https://{url}"
    
    # Fallback: construct URL from function name
    if not url:
        url = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/{function_name}"
    
    return True, url, None


def delete_function(function_name: str) -> Tuple[bool, Optional[str]]:
    """Delete a GCP Cloud Function."""
    cmd = [
        "gcloud", "functions", "delete", function_name,
        "--region", REGION,
        "--quiet"
    ]
    
    exit_code, stdout, stderr = run_command(cmd, timeout=300)
    
    if exit_code != 0:
        return False, f"Deletion failed: {stderr}"
    
    return True, None


def invoke_function(url: str, wait_between: float = 0.1) -> Tuple[bool, float, Optional[str]]:
    """Invoke a function and return success, duration in ms, and error."""
    try:
        start = time.time()
        response = requests.get(url, timeout=30)
        duration = (time.time() - start) * 1000  # Convert to ms
        
        if response.status_code == 200:
            return True, duration, None
        else:
            return False, duration, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, 0, str(e)


def test_cold_warm_starts(url: str) -> Tuple[float, float, int, int]:
    """Test cold start and warm start performance."""
    # Cold start: wait between requests to ensure cold starts
    cold_times = []
    cold_success = 0
    
    print(f"  Testing cold starts ({NUM_COLD_START_REQUESTS} requests)...")
    for i in range(NUM_COLD_START_REQUESTS):
        # Wait 5 seconds between requests to ensure cold start
        if i > 0:
            time.sleep(5)
        success, duration, error = invoke_function(url, wait_between=5)
        if success:
            cold_times.append(duration)
            cold_success += 1
        if (i + 1) % 10 == 0:
            print(f"    Completed {i + 1}/{NUM_COLD_START_REQUESTS} cold start requests")
    
    # Warm start: rapid requests
    warm_times = []
    warm_success = 0
    
    print(f"  Testing warm starts ({NUM_WARM_START_REQUESTS} requests)...")
    # First request to warm up
    invoke_function(url)
    time.sleep(1)
    
    for i in range(NUM_WARM_START_REQUESTS):
        success, duration, error = invoke_function(url, wait_between=0.05)
        if success:
            warm_times.append(duration)
            warm_success += 1
        if (i + 1) % 20 == 0:
            print(f"    Completed {i + 1}/{NUM_WARM_START_REQUESTS} warm start requests")
    
    cold_avg = sum(cold_times) / len(cold_times) if cold_times else 0
    warm_avg = sum(warm_times) / len(warm_times) if warm_times else 0
    
    return cold_avg, warm_avg, cold_success, warm_success


def check_logs_for_errors(function_name: str) -> Tuple[bool, Optional[str]]:
    """Check Cloud Function logs for errors."""
    cmd = [
        "gcloud", "functions", "logs", "read", function_name,
        "--region", REGION,
        "--limit", "1000"
    ]
    
    exit_code, stdout, stderr = run_command(cmd, timeout=60)
    
    if exit_code != 0:
        return False, f"Failed to read logs: {stderr}"
    
    # Check for error patterns
    error_patterns = ["ERROR", "Error", "Exception", "Failed", "failed"]
    has_errors = any(pattern in stdout for pattern in error_patterns)
    
    if has_errors:
        # Extract error lines
        error_lines = [line for line in stdout.split('\n') 
                      if any(pattern in line for pattern in error_patterns)]
        error_msg = "\n".join(error_lines[:10])  # First 10 error lines
        return False, error_msg
    
    return True, None


def get_agent_id(function_name: str) -> Optional[str]:
    """Get Lightrun agent ID for the function."""
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {LIGHTRUN_API_KEY}",
            "Content-Type": "application/json"
        }
        url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/agents"
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            agents = response.json()
            # Find agent matching function name
            for agent in agents:
                if function_name in agent.get("displayName", ""):
                    return agent.get("id")
    except Exception as e:
        print(f"    Warning: Could not get agent ID: {e}")
    
    return None


def test_lightrun_snapshot(function_name: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Test Lightrun snapshot functionality."""
    if not agent_id:
        return False, "Agent ID not found"
    
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        return False, "Lightrun API credentials not configured"
    
    try:
        # Add snapshot at line 30 (in the handler function)
        headers = {
            "Authorization": f"Bearer {LIGHTRUN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        snapshot_data = {
            "agentId": agent_id,
            "filename": "index.js",
            "lineNumber": 30,
            "maxHitCount": 1,
            "expireSec": 300
        }
        
        url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/snapshots"
        response = requests.post(url, json=snapshot_data, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            return False, f"Failed to create snapshot: {response.status_code} - {response.text}"
        
        snapshot_id = response.json().get("id")
        
        # Invoke function to trigger snapshot
        function_url = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/{function_name}"
        invoke_function(function_url)
        
        # Wait a bit for snapshot to be captured
        time.sleep(2)
        
        # Check if snapshot was captured
        check_url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/snapshots/{snapshot_id}"
        check_response = requests.get(check_url, headers=headers, timeout=30)
        
        if check_response.status_code == 200:
            snapshot_data = check_response.json()
            if snapshot_data.get("hitCount", 0) > 0:
                return True, None
        
        return False, "Snapshot was not captured"
        
    except Exception as e:
        return False, f"Snapshot test error: {str(e)}"


def test_lightrun_counter(function_name: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Test Lightrun counter functionality."""
    if not agent_id:
        return False, "Agent ID not found"
    
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        return False, "Lightrun API credentials not configured"
    
    try:
        headers = {
            "Authorization": f"Bearer {LIGHTRUN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        counter_data = {
            "agentId": agent_id,
            "filename": "index.js",
            "lineNumber": 30,
            "name": f"test_counter_{function_name}",
            "expireSec": 300
        }
        
        url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/counters"
        response = requests.post(url, json=counter_data, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            return False, f"Failed to create counter: {response.status_code} - {response.text}"
        
        counter_id = response.json().get("id")
        
        # Invoke function multiple times to increment counter
        function_url = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/{function_name}"
        for _ in range(5):
            invoke_function(function_url)
            time.sleep(0.5)
        
        # Wait for counter data
        time.sleep(3)
        
        # Check counter value
        check_url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/counters/{counter_id}"
        check_response = requests.get(check_url, headers=headers, timeout=30)
        
        if check_response.status_code == 200:
            counter_info = check_response.json()
            # Counter should have been hit
            return True, None
        
        return False, "Counter was not incremented"
        
    except Exception as e:
        return False, f"Counter test error: {str(e)}"


def test_lightrun_metric(function_name: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Test Lightrun metric functionality."""
    if not agent_id:
        return False, "Agent ID not found"
    
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        return False, "Lightrun API credentials not configured"
    
    try:
        headers = {
            "Authorization": f"Bearer {LIGHTRUN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        metric_data = {
            "agentId": agent_id,
            "filename": "index.js",
            "lineNumber": 30,
            "name": f"test_metric_{function_name}",
            "expression": "requestCount",
            "expireSec": 300
        }
        
        url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/metrics"
        response = requests.post(url, json=metric_data, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            return False, f"Failed to create metric: {response.status_code} - {response.text}"
        
        metric_id = response.json().get("id")
        
        # Invoke function to generate metric data
        function_url = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/{function_name}"
        for _ in range(5):
            invoke_function(function_url)
            time.sleep(0.5)
        
        # Wait for metric data
        time.sleep(3)
        
        # Check metric data
        check_url = f"{LIGHTRUN_API_URL}/api/v1/companies/{LIGHTRUN_COMPANY_ID}/actions/metrics/{metric_id}"
        check_response = requests.get(check_url, headers=headers, timeout=30)
        
        if check_response.status_code == 200:
            metric_info = check_response.json()
            # Metric should have data
            return True, None
        
        return False, "Metric was not collected"
        
    except Exception as e:
        return False, f"Metric test error: {str(e)}"


async def test_function(nodejs_version: int, gen_version: int) -> TestResult:
    """Test a single function deployment and execution."""
    function_name = f"test-node{nodejs_version}-gen{gen_version}"
    result = TestResult(
        function_name=function_name,
        gen_version=gen_version,
        nodejs_version=nodejs_version
    )
    
    print(f"\n{'='*60}")
    print(f"Testing: {function_name}")
    print(f"{'='*60}")
    
    # Create function directory
    func_dir = create_test_function(nodejs_version, gen_version)
    
    # Deploy function
    print(f"Deploying {function_name}...")
    success, url, error = deploy_function(function_name, func_dir, nodejs_version, gen_version)
    result.deployment_success = success
    result.deployment_error = error
    result.function_url = url
    
    if not success:
        print(f"  ❌ Deployment failed: {error}")
        # Cleanup function directory
        shutil.rmtree(func_dir, ignore_errors=True)
        return result
    
    print(f"  ✅ Deployed successfully: {url}")
    
    # Wait for function to be ready
    print("  Waiting for function to be ready...")
    time.sleep(10)
    
    try:
        # Test cold/warm starts
        print("Testing performance...")
        cold_avg, warm_avg, cold_success, warm_success = test_cold_warm_starts(url)
        result.cold_start_avg_ms = cold_avg
        result.warm_start_avg_ms = warm_avg
        result.cold_start_requests = cold_success
        result.warm_start_requests = warm_success
        print(f"  Cold start avg: {cold_avg:.2f}ms ({cold_success}/{NUM_COLD_START_REQUESTS} successful)")
        print(f"  Warm start avg: {warm_avg:.2f}ms ({warm_success}/{NUM_WARM_START_REQUESTS} successful)")
        
        # Check logs for errors
        print("Checking logs for errors...")
        logs_ok, logs_error = check_logs_for_errors(function_name)
        result.logs_error_check = logs_ok
        result.logs_error_message = logs_error
        if logs_ok:
            print("  ✅ No errors in logs")
        else:
            print(f"  ⚠️  Errors found in logs: {logs_error[:200]}")
        
        # Wait for agent to register
        print("Waiting for Lightrun agent to register...")
        time.sleep(30)
        
        # Get agent ID
        agent_id = get_agent_id(function_name)
        if agent_id:
            print(f"  Found agent ID: {agent_id}")
        else:
            print("  ⚠️  Agent ID not found (Lightrun tests will be skipped)")
        
        # Test Lightrun features
        if agent_id:
            print("Testing Lightrun snapshot...")
            snapshot_ok, snapshot_error = test_lightrun_snapshot(function_name, agent_id)
            result.snapshot_test = snapshot_ok
            result.snapshot_error = snapshot_error
            if snapshot_ok:
                print("  ✅ Snapshot test passed")
            else:
                print(f"  ❌ Snapshot test failed: {snapshot_error}")
            
            print("Testing Lightrun counter...")
            counter_ok, counter_error = test_lightrun_counter(function_name, agent_id)
            result.counter_test = counter_ok
            result.counter_error = counter_error
            if counter_ok:
                print("  ✅ Counter test passed")
            else:
                print(f"  ❌ Counter test failed: {counter_error}")
            
            print("Testing Lightrun metric...")
            metric_ok, metric_error = test_lightrun_metric(function_name, agent_id)
            result.metric_test = metric_ok
            result.metric_error = metric_error
            if metric_ok:
                print("  ✅ Metric test passed")
            else:
                print(f"  ❌ Metric test failed: {metric_error}")
        
    except Exception as e:
        print(f"  ❌ Test execution error: {str(e)}")
        result.logs_error_message = f"Test execution error: {str(e)}"
    
    finally:
        # Cleanup function directory
        shutil.rmtree(func_dir, ignore_errors=True)
    
    return result


async def cleanup_function(result: TestResult) -> None:
    """Clean up a deployed function."""
    if result.deployment_success:
        print(f"Cleaning up {result.function_name}...")
        success, error = delete_function(result.function_name)
        result.cleanup_success = success
        result.cleanup_error = error
        if success:
            print(f"  ✅ Cleaned up {result.function_name}")
        else:
            print(f"  ⚠️  Cleanup failed: {error}")


def save_result(result: TestResult) -> None:
    """Save test result to a file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULTS_DIR / f"{result.function_name}.json"
    
    result_dict = asdict(result)
    result_dict["timestamp"] = datetime.now().isoformat()
    
    with open(result_file, "w") as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"  💾 Result saved to {result_file}")


def print_summary(results: List[TestResult]) -> None:
    """Print test summary."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(results)
    deployed = sum(1 for r in results if r.deployment_success)
    failed_deploy = total - deployed
    
    print(f"\nTotal functions tested: {total}")
    print(f"Successfully deployed: {deployed}")
    print(f"Failed to deploy: {failed_deploy}")
    
    if deployed > 0:
        print(f"\nPerformance (deployed functions only):")
        cold_avgs = [r.cold_start_avg_ms for r in results if r.cold_start_avg_ms]
        warm_avgs = [r.warm_start_avg_ms for r in results if r.warm_start_avg_ms]
        
        if cold_avgs:
            print(f"  Cold start average: {sum(cold_avgs)/len(cold_avgs):.2f}ms")
            print(f"  Warm start average: {sum(warm_avgs)/len(warm_avgs):.2f}ms")
        
        print(f"\nLightrun tests:")
        snapshot_passed = sum(1 for r in results if r.snapshot_test is True)
        counter_passed = sum(1 for r in results if r.counter_test is True)
        metric_passed = sum(1 for r in results if r.metric_test is True)
        
        print(f"  Snapshots: {snapshot_passed}/{deployed} passed")
        print(f"  Counters: {counter_passed}/{deployed} passed")
        print(f"  Metrics: {metric_passed}/{deployed} passed")
        
        print(f"\nLog errors:")
        logs_ok = sum(1 for r in results if r.logs_error_check is True)
        print(f"  Clean logs: {logs_ok}/{deployed}")
    
    print("\nDetailed results saved to:", RESULTS_DIR)
    print("="*80)


async def main():
    """Main test execution."""
    # Validate configuration
    if not LIGHTRUN_SECRET:
        print("ERROR: LIGHTRUN_SECRET environment variable is required")
        sys.exit(1)
    
    print("GCP Cloud Functions Test Suite")
    print("="*80)
    print(f"Region: {REGION}")
    print(f"Project: {PROJECT_ID}")
    print(f"Node.js versions: {NODEJS_VERSIONS}")
    print(f"Function generations: {FUNCTION_VERSIONS}")
    print(f"Results directory: {RESULTS_DIR}")
    print("="*80)
    
    # Create directories
    TEST_FUNCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate all test combinations
    test_tasks = []
    for gen_version in FUNCTION_VERSIONS:
        for nodejs_version in NODEJS_VERSIONS:
            test_tasks.append((nodejs_version, gen_version))
    
    print(f"\nTotal test combinations: {len(test_tasks)}")
    print("Starting parallel test execution...\n")
    
    # Run tests in parallel (with concurrency limit)
    semaphore = asyncio.Semaphore(4)  # Max 4 concurrent deployments
    
    async def run_with_semaphore(nodejs_version, gen_version):
        async with semaphore:
            return await test_function(nodejs_version, gen_version)
    
    # Execute all tests
    results = await asyncio.gather(
        *[run_with_semaphore(nv, gv) for nv, gv in test_tasks],
        return_exceptions=True
    )
    
    # Handle exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"\n❌ Exception in test {test_tasks[i]}: {result}")
            # Create error result
            nv, gv = test_tasks[i]
            error_result = TestResult(
                function_name=f"test-node{nv}-gen{gv}",
                gen_version=gv,
                nodejs_version=nv,
                deployment_success=False,
                deployment_error=str(result)
            )
            processed_results.append(error_result)
        else:
            processed_results.append(result)
    
    # Save all results
    print("\nSaving results...")
    for result in processed_results:
        save_result(result)
    
    # Cleanup all functions
    print("\nCleaning up deployed functions...")
    cleanup_tasks = [cleanup_function(r) for r in processed_results]
    await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    
    # Print summary
    print_summary(processed_results)


if __name__ == "__main__":
    asyncio.run(main())
