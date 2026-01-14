#!/usr/bin/env python3
"""
Main entry point for GCP Cloud Functions testing.

Test script for deploying and testing GCP Cloud Functions (Gen1 and Gen2)
across different Node.js versions with Lightrun integration.
"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

# Import from package
sys.path.insert(0, str(Path(__file__).parent))
from gcp_function_tests.config import (
    REGION_PRECEDENCE, REGION, PROJECT_ID, LIGHTRUN_SECRET,
    NODEJS_VERSIONS, FUNCTION_VERSIONS, RESULTS_DIR, TEST_FUNCTIONS_DIR,
    FUNCTION_NAME_PREFIX, USERNAME, USERNAME_ERROR, LIGHTRUN_API_KEY, LIGHTRUN_COMPANY_ID
)
from gcp_function_tests.function_tester import FunctionTester
from gcp_function_tests.result_handler import ResultHandler
from gcp_function_tests.models import TestResult


async def main(concurrency_limit: Optional[int] = None):
    """Main test execution.
    
    Args:
        concurrency_limit: Optional limit on concurrent deployments. If None, no limit is applied.
    """
    # Validate username (required for function naming)
    if not USERNAME or not FUNCTION_NAME_PREFIX:
        if USERNAME_ERROR:
            print(f"ERROR: {USERNAME_ERROR}")
        else:
            print("ERROR: Username not configured")
        sys.exit(1)
    
    # Validate required environment variables
    if not LIGHTRUN_SECRET:
        print("ERROR: LIGHTRUN_SECRET environment variable is required")
        print("Please set it with: export LIGHTRUN_SECRET='your-secret'")
        sys.exit(1)
    
    # Optional: Check if Lightrun API credentials are set (for API tests)
    if not LIGHTRUN_API_KEY or not LIGHTRUN_COMPANY_ID:
        print("WARNING: LIGHTRUN_API_KEY and/or LIGHTRUN_COMPANY_ID not set.")
        print("Lightrun API tests (snapshots, counters, metrics) will be skipped.")
        print("Set them with:")
        print("  export LIGHTRUN_API_KEY='your-api-key'")
        print("  export LIGHTRUN_COMPANY_ID='your-company-id'")
    
    print("GCP Cloud Functions Test Suite")
    print("="*80)
    print(f"Username: {USERNAME}")
    print(f"Function name prefix: {FUNCTION_NAME_PREFIX}")
    print(f"Region precedence: {' > '.join(REGION_PRECEDENCE)}")
    print(f"Default region: {REGION}")
    print(f"Project: {PROJECT_ID}")
    print(f"Node.js versions: {NODEJS_VERSIONS}")
    print(f"Function generations: {FUNCTION_VERSIONS}")
    print(f"Results directory: {RESULTS_DIR}")
    print("="*80)
    
    # Create directories
    TEST_FUNCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    tester = FunctionTester()
    result_handler = ResultHandler()
    
    # Generate all test combinations
    test_tasks = []
    for gen_version in FUNCTION_VERSIONS:
        for nodejs_version in NODEJS_VERSIONS:
            test_tasks.append((nodejs_version, gen_version))
    
    print(f"\nTotal test combinations: {len(test_tasks)}")
    if concurrency_limit:
        print(f"Starting parallel test execution (max {concurrency_limit} concurrent)...")
    else:
        print("Starting parallel test execution (unlimited concurrency)...")
    print("Press Ctrl+C to cancel and cleanup...\n")
    
    # Set up signal handler for graceful shutdown
    shutdown_event = asyncio.Event()
    tasks = []
    
    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) gracefully."""
        print("\n\n⚠️  Interrupt received (Ctrl+C). Shutting down gracefully...")
        shutdown_event.set()
        # Cancel all running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create semaphore only if concurrency limit is specified
    semaphore = asyncio.Semaphore(concurrency_limit) if concurrency_limit else None
    
    async def run_test(nodejs_version, gen_version):
        """Run a single test, optionally with semaphore limiting."""
        # Use semaphore if provided, otherwise run without limit
        if semaphore:
            async with semaphore:
                # Check if shutdown was requested
                if shutdown_event.is_set():
                    return None
                try:
                    return await tester.test_function(nodejs_version, gen_version)
                except asyncio.CancelledError:
                    print(f"  ⚠️  Test node{nodejs_version}-gen{gen_version} was cancelled")
                    raise
        else:
            # No semaphore - run directly
            if shutdown_event.is_set():
                return None
            try:
                return await tester.test_function(nodejs_version, gen_version)
            except asyncio.CancelledError:
                print(f"  ⚠️  Test node{nodejs_version}-gen{gen_version} was cancelled")
                raise
    
    # Create all tasks explicitly so we can cancel them
    for nv, gv in test_tasks:
        task = asyncio.create_task(run_test(nv, gv))
        tasks.append(task)
    
    # Execute all tests with cancellation support
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  KeyboardInterrupt received. Cleaning up...")
        shutdown_event.set()
        # Cancel all tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        # Wait for cancellation to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        results = []
    
    # Handle exceptions and None results (from cancellation)
    processed_results = []
    for i, result in enumerate(results):
        if result is None:
            # Task was cancelled or skipped
            continue
        if isinstance(result, Exception):
            if isinstance(result, asyncio.CancelledError):
                # Task was cancelled, skip it
                continue
            print(f"\n❌ Exception in test {test_tasks[i]}: {result}")
            # Create error result
            nv, gv = test_tasks[i]
            from gcp_function_tests.models import DeploymentResult
            error_result = TestResult(
                function_name=f"{FUNCTION_NAME_PREFIX}node{nv}-gen{gv}",
                gen_version=gv,
                nodejs_version=nv,
                deployment_result=DeploymentResult(
                    success=False,
                    error=str(result)
                ),
                deployment_error=str(result)
            )
            processed_results.append(error_result)
        else:
            processed_results.append(result)
    
    if shutdown_event.is_set():
        print("\n⚠️  Tests were interrupted. Saving partial results...")
    
    # Save all results
    if processed_results:
        print("\nSaving results...")
        for result in processed_results:
            result_handler.save_result(result)
            print(f"  💾 Result saved for {result.function_name}")
    
    # Cleanup all functions
    if processed_results:
        print("\nCleaning up deployed functions...")
        cleanup_tasks = [tester.cleanup_function(r) for r in processed_results if r.deployment_result and r.deployment_result.success]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    
    # Print summary
    if processed_results:
        result_handler.print_summary(processed_results)
    else:
        print("\n⚠️  No test results to summarize.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='GCP Cloud Functions Test Suite')
    parser.add_argument(
        '--concurrency-limit',
        type=int,
        default=None,
        help='Maximum number of concurrent deployments (default: unlimited)'
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(concurrency_limit=args.concurrency_limit))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(130)  # Standard exit code for SIGINT
