"""Manager class for coordinating Cloud Function cold start tests."""

import json
import time
import os
import atexit
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from dataclasses import asdict

from shared_modules.send_request import SendRequestTask
from shared_modules.delete import DeleteTask
from shared_modules.wait_for_cold import ColdStartDetectionError
from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.region_allocator import RegionAllocator


class BenchmarkManager:
    """Manages the lifecycle of a benchmark run."""
    
    def __init__(self, config: argparse.Namespace, function_dir: Path):
        """
        Initialize the manager.
        
        Args:
            config: Configuration namespace with all test parameters
            function_dir: Directory containing the function source code
        """
        self.config = config
        self.function_dir = function_dir
        self.executor: Optional[ThreadPoolExecutor] = None
        self.deployed_functions: List[GCPFunction] = []
        self.cleanup_registered = False
        self.cleanup_stats = {'deleted': 0, 'failed': 0}
    
    def __enter__(self):
        """Context manager entry - create executor and register cleanup."""
        self.executor = ThreadPoolExecutor(max_workers=self.config.num_workers)
        
        # Register cleanup handlers (only in main thread)
        if not self.cleanup_registered:
            atexit.register(self.cleanup)
            # Only register signal handlers in main thread
            try:
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
            except ValueError:
                # Signal handlers can only be registered in main thread
                # This is fine if we're running in a worker thread
                pass
            self.cleanup_registered = True
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()
        return False  # Don't suppress exceptions
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals (Ctrl+C) and cleanup."""
        print("\n\nInterrupted! Cleaning up...")
        self.cleanup()
        os._exit(1)
    

    def wait_and_test_function(self, function: GCPFunction, deployment_start_time: float) -> tuple[GCPFunction, Optional[Dict[str, Any]], Optional[float]]:
        """
        Wait for cold and test a single function.

        Args:
            function: GCPFunction object that has already been deployed
            deployment_start_time: Timestamp when deployments started

        Returns:
            Tuple of (GCPFunction, test_result, time_to_cold_seconds)
            test_result and time_to_cold will be None if wait or test fails
        """



        time_to_cold = None
        
        if getattr(self.config, 'skip_wait_for_cold', False):
            print(f"[{function.index:3d}] Skipping wait for cold...")
        else:
            try:
                time_to_cold = function.wait_for_cold(self.config, deployment_start_time)
            except ColdStartDetectionError as e:
                print(f"[{function.index:3d}] ❌ Cold detection failed: {e}")
                return function, {
                    'function_index': function.index,
                    'function_name': function.name,
                    'error': True,
                    'error_message': str(e)
                }, None


            # Step 2: Grace period (1 minute) after cold confirmation
            print(f"[{function.index:3d}] Waiting 1 minute grace period before testing...")
            time.sleep(60)
            
        print(f"[{function.index:3d}] Testing now...")

        # Step 3: Test (multiple requests based on config)
        test_task = SendRequestTask(function, self.config)
        test_result = test_task.execute()

        if test_result.get('error'):
            print(f"[{function.index:3d}] ✗ Test failed")
        else:
            cold_duration = float(test_result.get('totalDurationForColdStarts', 0)) / 1_000_000_000
            warm_duration = float(test_result.get('totalDurationForWarmRequests', 0)) / 1_000_000_000
            num_requests = test_result.get('_num_requests', 1)
            print(f"[{function.index:3d}] ✓ Test complete: ColdDur={cold_duration:.3f}s, WarmDur={warm_duration:.3f}s, Requests={num_requests}")
            function.test_result = test_result

        # Save individual function results to file
        self._save_function_results(function, test_result)

        return function, test_result, time_to_cold

    def create_functions(self) -> List[GCPFunction]:
        """
        Create all GCPFunction objects with region allocation.

        Returns:
            List[GCPFunction]: List of created function objects with regions allocated
        """
        functions = []

        region_allocator = iter(RegionAllocator(self.config.max_allocations_per_region))

        # Create all functions with region allocation
        for i in range(1, self.config.num_functions + 1):
            region = next(region_allocator)
            function = GCPFunction(index=i, region=region, base_name=self.config.base_function_name)
            functions.append(function)
            print(f"[{function.index:3d}] Created function {function.index} for region {region}")

        return functions

    def deploy_wait_and_test_all_functions(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
        """
        Deploy, wait for cold, and test all functions in phases.
        Phase 1: Create functions with region allocation
        Phase 2: Deploy all functions in parallel
        Phase 3: Wait for cold and test each function in parallel

        Returns:
            Tuple of (deployments list, test_results list, cold_times dict)
        """
        print("=" * 80)
        print("Creating, Deploying and Testing Functions in Phases")
        print("=" * 80)
        print(f"Phase 1: Create {self.config.num_functions} functions with region allocation")
        print(f"Phase 2: Deploy all functions in parallel")
        print(f"Phase 3: Each function will: Wait 10s grace → Poll until cold → Wait 1min grace → Test")
        print()

        # Phase 1: Create all functions with region allocation
        functions = self.create_functions()
        print(f"Created {len(functions)} functions")
        print()

        # Phase 2: Deploy all functions in parallel
        print("Phase 2: Deploying all functions in parallel...")
        deployment_start_time = time.time()
        deployment_futures = {
            self.executor.submit(
                function.deploy,
                self.config.lightrun_secret,
                self.config,
                self.function_dir
            ): function
            for function in functions
        }

        deployments: List[GCPFunction] = []
        for future in as_completed(deployment_futures):
            function = deployment_futures[future]
            try:
                result = future.result()  # This is now DeploymentResult
                
                # Track function for cleanup (even if failed)
                self.deployed_functions.append(function)
                deployments.append(function)
                
                # Print success/failure status
                if result.success:
                    print(f"[{function.index:3d}] ✓ Deployed: {function.name} in {function.region}")
                else:
                    print(f"[{function.index:3d}] ✗ Deployment failed: {result.error[:50] if result.error else 'Unknown error'}...")
            except Exception as e:
                print(f"[{function.index:3d}] Deployment task failed with exception: {e}")

        successful_deployments = [f for f in deployments if f.is_deployed and f.url]
        print(f"Deployed {len(successful_deployments)}/{len(deployments)} functions successfully")
        print()

        # Phase 3: Wait for cold and test all successfully deployed functions in parallel
        print("Phase 3: Waiting for cold and testing functions in parallel...")
        test_results: List[Dict[str, Any]] = []
        cold_times: Dict[str, float] = {}

        # Only test functions that were successfully deployed
        testable_functions = [f for f in deployments if f.is_deployed and f.url]
        wait_test_futures = {}

        # Phase 3: Wait for cold and test successfully deployed functions
        if testable_functions:
            wait_test_futures = {
                self.executor.submit(
                    self.wait_and_test_function,
                    function,
                    deployment_start_time
                ): function.index
                for function in testable_functions
            }
            completed = 0
            for future in as_completed(wait_test_futures):
                function_index = wait_test_futures[future]
                completed += 1

                try:
                    function, test_result, time_to_cold = future.result()

                    if test_result:
                        test_results.append(test_result)

                    if time_to_cold is not None:
                        cold_times[function.name] = time_to_cold
                        function.time_to_cold_seconds = time_to_cold
                        function.time_to_cold_minutes = time_to_cold / 60

                    print(f"[{completed:3d}/{len(testable_functions)}] Function {function_index} test complete")

                except Exception as e:
                    print(f"[{completed:3d}/{len(testable_functions)}] Function {function_index} test failed with exception: {e}")
                    # Add error result
                    test_results.append({
                        'function_index': function_index,
                        'error': True,
                        'error_message': str(e)
                    })
        else:
            print("No functions were successfully deployed, skipping testing phase")
        
        # Determine successful deployments for stats
        successful_deployments = [f for f in deployments if f.is_deployed]
        
        # Save deployment info (convert objects to dicts)
        deployments_dict = [f.__dict__ for f in deployments]
        
        # Determine output directory - use config.output_dir if available, otherwise use results_file parent directory
        if hasattr(self.config, 'output_dir') and self.config.output_dir:
            output_dir = Path(self.config.output_dir)
        elif hasattr(self.config, 'results_file') and self.config.results_file:
            output_dir = Path(self.config.results_file).parent
        else:
            output_dir = Path('.')
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use variant-specific filename to avoid conflicts when running parallel tests
        base_name = getattr(self.config, 'base_function_name', 'deployments')
        deployments_file = output_dir / f'{base_name}_deployments.json'
        with open(deployments_file, 'w') as f:
            json.dump(deployments_dict, f, indent=2, default=str)

        print(f"\nSummary: {len(successful_deployments)}/{self.config.num_functions} functions deployed successfully")
        print(f"         {len(test_results)} test results collected")
        
        return deployments, test_results, cold_times
    
    def _save_function_results(self, function: GCPFunction, test_result: Dict[str, Any]):
        """Save individual function results to a file named by display_name."""
        # Determine output directory
        if hasattr(self.config, 'output_dir') and self.config.output_dir:
            output_dir = Path(self.config.output_dir)
        elif hasattr(self.config, 'results_file') and self.config.results_file:
            output_dir = Path(self.config.results_file).parent
        else:
            output_dir = Path('.')
        
        function_results_dir = output_dir / 'function_results'
        function_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Use display_name for filename (sanitize for filesystem)
        safe_name = function.display_name.replace('/', '_').replace('\\', '_')
        result_file = function_results_dir / f'{safe_name}.json'
        
        with open(result_file, 'w') as f:
            json.dump({
                'function': asdict(function),
                'test_result': test_result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, f, indent=2, default=str)
    
    def save_results(self, deployments: List[GCPFunction], test_results: List[Dict[str, Any]]):
        """Save test results to file."""
        # Convert GCPFunction objects to dicts for serialization
        deployments_dict = [asdict(f) if isinstance(f, GCPFunction) else f for f in deployments]
        
        # Ensure output directory exists
        results_path = Path(self.config.results_file)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config.results_file, 'w') as f:
            json.dump({
                'deployments': deployments_dict,
                'test_results': test_results,
                'test_timestamp': datetime.now(timezone.utc).isoformat()
            }, f, indent=2, default=str)
    
    def get_results(self) -> Dict[str, Any]:
        """Return test results as a dictionary."""
        # Ensure deployments are serializable
        deployments_list = getattr(self, 'deployments', [])
        deployments_dict = [asdict(f) if isinstance(f, GCPFunction) else f for f in deployments_list]
        
        return {
            'deployments': deployments_dict,
            'test_results': self.test_results if hasattr(self, 'test_results') else [],
            'cleanup_stats': self.cleanup_stats,
            'config': {
                'base_function_name': self.config.base_function_name,
                'num_functions': self.config.num_functions,
                'region': self.config.region,
                'project': self.config.project,
                'runtime': self.config.runtime,
                'entry_point': self.config.entry_point,
            },
            'test_timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def cleanup(self):
        """Delete all deployed Cloud Functions and shutdown executor."""
        if not self.deployed_functions or self.executor is None:
            return
        
        print("\n" + "=" * 80)
        print("CLEANUP: Deleting deployed functions...")
        print("=" * 80)
        
        deleted_count = 0
        failed_count = 0
        
        try:
            futures = {
                self.executor.submit(
                    lambda fn=func: DeleteTask(fn, self.config).execute()
                ): func.name
                for func in self.deployed_functions
            }
            
            for future in as_completed(futures):
                function_name = futures[future]
                result = future.result()
                if result['success']:
                    deleted_count += 1
                    print(f"  ✓ Deleted: {function_name}")
                else:
                    failed_count += 1
                    print(f"  ✗ Failed to delete: {function_name}")
        finally:
            # Shutdown executor after all deletions are complete
            self.executor.shutdown(wait=True)
            self.executor = None
        
        print(f"\nCleanup Summary: {deleted_count} deleted, {failed_count} failed")
        self.cleanup_stats = {'deleted': deleted_count, 'failed': failed_count}
        self.deployed_functions = []
    
    def run(self) -> Dict[str, Any]:
        """Run the complete test workflow and return results."""
        print("=" * 80)
        print("Cloud Function Parallel Cold Start Performance Test")
        print("=" * 80)
        print(f"Number of Functions: {self.config.num_functions}")
        print(f"Project: {self.config.project}")
        print(f"Base Function Name: {self.config.base_function_name}")
        print(f"Number of Worker Threads: {self.config.num_workers}")
        print(f"Max Allocations per Region: {self.config.max_allocations_per_region}")
        print("Note: Functions will be automatically cleaned up on exit")
        print()
        
        # Deploy, wait for cold, and test all functions in parallel
        deployments, test_results, cold_times = self.deploy_wait_and_test_all_functions()
        
        # Store results for later retrieval
        self.deployments = deployments
        self.test_results = test_results
        
        # Save results
        self.save_results(deployments, test_results)
        
        print("\n" + "=" * 80)
        print("Test completed! Functions will be cleaned up automatically on exit.")
        print("=" * 80)
        
        return self.get_results()