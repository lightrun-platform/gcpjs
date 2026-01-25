#!/usr/bin/env python3
"""
Latency testing entry point for GCP Cloud Functions.

Tests latency across all combinations of:
- isGCPFunctionWarm (cold vs warm)
- wasLightrunAgentInitializedBefore (yes/no)
- shouldWeTakeALightrunSnapshotDuringThisFunctionCall (yes/no)

This creates 8 possible combinations (2^3), though some are impossible in practice.
"""
import asyncio
import signal
import sys
import argparse
from pathlib import Path
from typing import Optional

# Import from package
sys.path.insert(0, str(Path(__file__).parent))
from gcp_function_tests.config import (
    REGION_PRECEDENCE, REGION, PROJECT_ID, LIGHTRUN_SECRET,
    FUNCTION_NAME_PREFIX, USERNAME, USERNAME_ERROR, 
    LIGHTRUN_API_KEY, LIGHTRUN_COMPANY_ID, LIGHTRUN_API_URL,
    RESULTS_DIR, TEST_FUNCTIONS_DIR
)
from gcp_function_tests.gcp_deployer import GCPDeployer
from gcp_function_tests.latency_function_creator import LatencyFunctionCreator
from gcp_function_tests.latency_tester import LatencyTester, LatencyTestResults
from gcp_function_tests.lightrun_tester import LightrunTester
from gcp_function_tests.result_handler import ResultHandler
import json
from datetime import datetime


async def test_latency_single_pair(
    deployer: GCPDeployer,
    function_creator: LatencyFunctionCreator,
    latency_tester: LatencyTester,
    lightrun_tester: LightrunTester,
    nodejs_version: int,
    gen_version: int,
    pair_index: int,
    num_cold_starts: int
) -> Optional[LatencyTestResults]:
    """Test latency for a single pair of functions (with/without Lightrun)."""
    base_name = f"{FUNCTION_NAME_PREFIX}latency-node{nodejs_version}-gen{gen_version}-pair{pair_index}"
    function_name_without = f"{base_name}-without-lightrun"
    function_name_with = f"{base_name}-with-lightrun"
    
    print(f"\n{'='*60}")
    print(f"Testing latency pair {pair_index}/{num_cold_starts}: {base_name}")
    print(f"{'='*60}")
    
    try:
        # Create function directories
        func_dir_without = function_creator.create_latency_test_function(
            nodejs_version, gen_version, use_lightrun=False
        )
        func_dir_with = function_creator.create_latency_test_function(
            nodejs_version, gen_version, use_lightrun=True
        )
        
        # Deploy both functions
        print(f"Deploying {function_name_without}...")
        deployment_without = await deployer.deploy_with_fallback(
            function_name_without, func_dir_without, nodejs_version, gen_version
        )
        
        if not deployment_without.success:
            print(f"  ❌ Failed to deploy {function_name_without}: {deployment_without.error}")
            return None
        
        print(f"Deploying {function_name_with}...")
        deployment_with = await deployer.deploy_with_fallback(
            function_name_with, func_dir_with, nodejs_version, gen_version
        )
        
        if not deployment_with.success:
            print(f"  ❌ Failed to deploy {function_name_with}: {deployment_with.error}")
            # Cleanup the first function
            await deployer.delete_function(function_name_without, deployment_without.used_region)
            return None
        
        print(f"  ✅ Both functions deployed successfully")
        print(f"    Without Lightrun: {deployment_without.url}")
        print(f"    With Lightrun: {deployment_with.url}")
        
        # Wait for functions to be ready
        await asyncio.sleep(10)
        
        # Note: We don't need agent_id initially because:
        # 1. For "agent not initialized before" scenarios, we use metadata tags
        # 2. Agent ID will be available after first useLightrun=true call
        # We'll try to get it, but it's OK if it's None initially
        print(f"  Waiting for Lightrun agent to potentially register...")
        await asyncio.sleep(5)  # Brief wait
        agent_id = lightrun_tester.get_agent_id(function_name_with)
        
        if not agent_id:
            print(f"  ℹ️  Agent ID not available yet (will be available after first useLightrun=true call)")
        
        # Run latency tests
        print(f"  Running latency matrix tests...")
        results = await latency_tester.test_latency_matrix(
            url_without_lightrun=deployment_without.url,
            url_with_lightrun=deployment_with.url,
            function_name_with_lightrun=function_name_with,
            agent_id=agent_id
        )
        
        return results
        
    except Exception as e:
        print(f"  ❌ Error during latency testing: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        # Cleanup
        print(f"  Cleaning up functions...")
        if deployment_without.success:
            await deployer.delete_function(function_name_without, deployment_without.used_region)
        if deployment_with.success:
            await deployer.delete_function(function_name_with, deployment_with.used_region)


async def main(
    nodejs_version: int,
    gen_version: int,
    num_cold_starts: int = 5,
    requests_per_scenario: int = 10,
    concurrency_limit: Optional[int] = None
):
    """Main latency test execution."""
    # Validate username
    if not USERNAME or not FUNCTION_NAME_PREFIX:
        if USERNAME_ERROR:
            print(f"ERROR: {USERNAME_ERROR}")
        else:
            print("ERROR: Username not configured")
        sys.exit(1)
    
    # Validate required environment variables
    if not LIGHTRUN_SECRET:
        print("ERROR: LIGHTRUN_SECRET environment variable is required")
        sys.exit(1)
    
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        print("ERROR: LIGHTRUN_API_KEY and LIGHTRUN_COMPANY_ID are required for latency testing")
        sys.exit(1)
    
    print("GCP Cloud Functions Latency Test Suite")
    print("="*80)
    print(f"Username: {USERNAME}")
    print(f"Function name prefix: {FUNCTION_NAME_PREFIX}")
    print(f"Node.js version: {nodejs_version}")
    print(f"Function generation: Gen{gen_version}")
    print(f"Number of cold starts: {num_cold_starts}")
    print(f"Requests per scenario: {requests_per_scenario}")
    print(f"Results directory: {RESULTS_DIR}")
    print("="*80)
    
    # Create directories
    TEST_FUNCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    deployer = GCPDeployer()
    function_creator = LatencyFunctionCreator()
    latency_tester = LatencyTester(
        requests_per_scenario=requests_per_scenario,
        api_url=LIGHTRUN_API_URL,
        api_key=LIGHTRUN_API_KEY,
        company_id=LIGHTRUN_COMPANY_ID
    )
    lightrun_tester = LightrunTester()
    
    # Set up signal handler for graceful shutdown
    shutdown_event = asyncio.Event()
    tasks = []
    
    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) gracefully."""
        print("\n\n⚠️  Interrupt received (Ctrl+C). Shutting down gracefully...")
        shutdown_event.set()
        for task in tasks:
            if not task.done():
                task.cancel()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(concurrency_limit) if concurrency_limit else None
    
    async def run_test_pair(pair_index: int):
        """Run a single test pair with optional semaphore."""
        if semaphore:
            async with semaphore:
                if shutdown_event.is_set():
                    return None
                return await test_latency_single_pair(
                    deployer, function_creator, latency_tester, lightrun_tester,
                    nodejs_version, gen_version, pair_index, num_cold_starts
                )
        else:
            if shutdown_event.is_set():
                return None
            return await test_latency_single_pair(
                deployer, function_creator, latency_tester, lightrun_tester,
                nodejs_version, gen_version, pair_index, num_cold_starts
            )
    
    # Create tasks for all cold start pairs
    print(f"\nStarting latency tests ({num_cold_starts} cold start pairs)...")
    print("Press Ctrl+C to cancel and cleanup...\n")
    
    for i in range(num_cold_starts):
        task = asyncio.create_task(run_test_pair(i + 1))
        tasks.append(task)
    
    # Execute all tests
    try:
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  KeyboardInterrupt received. Cleaning up...")
        shutdown_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        results_list = []
    
    # Process results
    valid_results = []
    for i, result in enumerate(results_list):
        if result is None or isinstance(result, Exception):
            if isinstance(result, asyncio.CancelledError):
                continue
            print(f"  ⚠️  Pair {i+1} failed or was cancelled")
            continue
        valid_results.append(result)
    
    if not valid_results:
        print("\n⚠️  No valid results collected.")
        return
    
    # Aggregate results
    print(f"\n{'='*60}")
    print(f"Aggregating results from {len(valid_results)} successful test pairs...")
    print(f"{'='*60}")
    
    aggregated = LatencyTestResults()
    
    # Aggregate all measurements
    for result in valid_results:
        aggregated.cold_no_lightrun_no_snapshot.extend(result.cold_no_lightrun_no_snapshot)
        aggregated.cold_no_lightrun_snapshot.extend(result.cold_no_lightrun_snapshot)
        aggregated.warm_no_lightrun_no_snapshot.extend(result.warm_no_lightrun_no_snapshot)
        aggregated.warm_no_lightrun_snapshot.extend(result.warm_no_lightrun_snapshot)
        aggregated.warm_lightrun_init_no_snapshot.extend(result.warm_lightrun_init_no_snapshot)
        aggregated.warm_lightrun_init_snapshot.extend(result.warm_lightrun_init_snapshot)
        aggregated.warm_lightrun_ready_no_snapshot.extend(result.warm_lightrun_ready_no_snapshot)
        aggregated.warm_lightrun_ready_snapshot.extend(result.warm_lightrun_ready_snapshot)
    
    # Compute metrics
    metrics = aggregated.compute_metrics()
    
    # Save results
    result_file = RESULTS_DIR / f"latency-node{nodejs_version}-gen{gen_version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    result_dict = aggregated.to_dict()
    result_dict["test_config"] = {
        "nodejs_version": nodejs_version,
        "gen_version": gen_version,
        "num_cold_starts": num_cold_starts,
        "requests_per_scenario": requests_per_scenario,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(result_file, "w") as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"\n✅ Results saved to: {result_file}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("LATENCY TEST SUMMARY")
    print(f"{'='*60}")
    print(f"\nRaw Averages (ms):")
    print(f"  1. Cold, no Lightrun, no snapshot:     {metrics['avg_cold_no_lightrun_no_snapshot']:.2f}")
    print(f"  2. Cold, no Lightrun, snapshot attempt: {metrics['avg_cold_no_lightrun_snapshot']:.2f}")
    print(f"  3. Warm, no Lightrun, no snapshot:     {metrics['avg_warm_no_lightrun_no_snapshot']:.2f}")
    print(f"  4. Warm, no Lightrun, snapshot attempt: {metrics['avg_warm_no_lightrun_snapshot']:.2f}")
    print(f"  5. Warm, Lightrun init, no snapshot:    {metrics['avg_warm_lightrun_init_no_snapshot']:.2f}")
    print(f"  6. Warm, Lightrun init, snapshot:       {metrics['avg_warm_lightrun_init_snapshot']:.2f}")
    print(f"  7. Warm, Lightrun ready, no snapshot:  {metrics['avg_warm_lightrun_ready_no_snapshot']:.2f}")
    print(f"  8. Warm, Lightrun ready, snapshot:     {metrics['avg_warm_lightrun_ready_snapshot']:.2f}")
    
    print(f"\nDerived Metrics (ms):")
    print(f"  GCP Cold Start Duration (no Lightrun):     {metrics['gcp_cold_start_duration']:.2f}")
    print(f"  Lightrun Initialization Duration:         {metrics['lightrun_init_duration']:.2f}")
    print(f"  Lightrun Overhead (excluding init):       {metrics['lightrun_overhead']:.2f}")
    print(f"  Snapshot Overhead (no Lightrun):           {metrics['snapshot_overhead_no_lightrun']:.2f}")
    print(f"  Snapshot Overhead (Lightrun ready):       {metrics['snapshot_overhead_lightrun_ready']:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='GCP Cloud Functions Latency Test Suite')
    parser.add_argument('--nodejs-version', type=int, required=True, help='Node.js version (18-24)')
    parser.add_argument('--gen-version', type=int, required=True, choices=[1, 2], help='GCP function generation (1 or 2)')
    parser.add_argument('--num-cold-starts', type=int, default=5, help='Number of cold starts to test (default: 5)')
    parser.add_argument('--requests-per-scenario', type=int, default=10, help='Number of requests per scenario (default: 10)')
    parser.add_argument('--concurrency-limit', type=int, default=None, help='Max concurrent deployments (default: unlimited)')
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(
            nodejs_version=args.nodejs_version,
            gen_version=args.gen_version,
            num_cold_starts=args.num_cold_starts,
            requests_per_scenario=args.requests_per_scenario,
            concurrency_limit=args.concurrency_limit
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(130)
