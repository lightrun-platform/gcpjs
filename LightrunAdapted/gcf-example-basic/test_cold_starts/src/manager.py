"""Manager class for coordinating Cloud Function cold start tests."""

import json
import time
import os
import atexit
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

from .deploy import DeployTask
from .send_request import SendRequestTask
from .delete import DeleteTask
from .wait_for_cold import WaitForColdTask, ColdStartDetectionError


class ColdStartTestManager:
    """Manages the lifecycle of cold start testing."""
    
    def __init__(self, config: argparse.Namespace, function_dir: Path):
        """
        Initialize the test manager.
        
        Args:
            config: Configuration namespace with all test parameters
            function_dir: Directory containing the function source code
        """
        self.config = config
        self.function_dir = function_dir
        self.executor: Optional[ThreadPoolExecutor] = None
        self.deployed_functions: List[Dict[str, Any]] = []
        self.cleanup_registered = False
    
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
    
    def deploy_wait_and_test_function(self, function_index: int, deployment_start_time: float) -> tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[float]]:
        """
        Deploy, wait for cold, and test a single function.
        
        Args:
            function_index: Index of the function (1-based)
            deployment_start_time: Timestamp when deployments started
            
        Returns:
            Tuple of (deployment_result, test_result, time_to_cold_seconds)
            test_result and time_to_cold will be None if deployment or wait fails
        """
        # Step 1: Deploy
        deploy_task = DeployTask(function_index, self.config.lightrun_secret, self.config, self.function_dir)
        deployment = deploy_task.execute()
        
        if not deployment.get('deployed') or not deployment.get('url'):
            print(f"[{function_index:3d}] ✗ Deployment failed")
            return deployment, None, None
        
        print(f"[{function_index:3d}] ✓ Deployed: {deployment['function_name']}")
        
        # Step 2: Wait for cold
        wait_task = WaitForColdTask(
            deployment['function_name'],
            deployment['function_index'],
            self.config
        )
        
        try:
            time_to_cold = wait_task.execute(deployment_start_time, self.config.wait_minutes)
        except ColdStartDetectionError as e:
            print(f"[{function_index:3d}] ❌ Cold detection failed: {e}")
            return deployment, {
                'function_index': function_index,
                'function_name': deployment['function_name'],
                'error': True,
                'error_message': str(e)
            }, None
        
        # Step 3: Grace period (1 minute) after cold confirmation
        print(f"[{function_index:3d}] Waiting 1 minute grace period before testing...")
        time.sleep(60)
        print(f"[{function_index:3d}] Testing now...")
        
        # Step 4: Test
        test_task = SendRequestTask(deployment['url'], deployment['function_index'])
        test_result = test_task.execute()
        
        if test_result.get('error'):
            print(f"[{function_index:3d}] ✗ Test failed")
        else:
            is_cold = test_result.get('isColdStart', False)
            total_duration = float(test_result.get('totalDuration', 0)) / 1_000_000_000
            print(f"[{function_index:3d}] ✓ Test complete: Cold={is_cold}, Duration={total_duration:.3f}s")
        
        return deployment, test_result, time_to_cold
    
    def deploy_wait_and_test_all_functions(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
        """
        Deploy, wait for cold, and test all functions in parallel.
        Each function goes through: deploy -> wait -> grace period -> test
        
        Returns:
            Tuple of (deployments list, test_results list, cold_times dict)
        """
        print("=" * 80)
        print("Deploying, Waiting for Cold, and Testing Functions in Parallel")
        print("=" * 80)
        print(f"Each function will: Deploy → Wait {self.config.wait_minutes}min → Poll until cold → Wait 1min grace → Test")
        print()
        
        deployment_start_time = time.time()
        deployments = []
        test_results = []
        cold_times: Dict[str, float] = {}
        
        # Submit all functions in parallel
        futures = {
            self.executor.submit(
                self.deploy_wait_and_test_function,
                i,
                deployment_start_time
            ): i
            for i in range(1, self.config.num_functions + 1)
        }
        
        completed = 0
        for future in as_completed(futures):
            function_index = futures[future]
            completed += 1
            
            try:
                deployment, test_result, time_to_cold = future.result()
                deployments.append(deployment)
                
                if test_result:
                    test_results.append(test_result)
                
                if time_to_cold is not None:
                    cold_times[deployment['function_name']] = time_to_cold
                    deployment['time_to_cold_seconds'] = time_to_cold
                    deployment['time_to_cold_minutes'] = time_to_cold / 60
                
                print(f"[{completed:3d}/{self.config.num_functions}] Function {function_index} complete")
                
            except Exception as e:
                print(f"[{completed:3d}/{self.config.num_functions}] Function {function_index} failed with exception: {e}")
                # Add error result
                test_results.append({
                    'function_index': function_index,
                    'error': True,
                    'error_message': str(e)
                })
        
        # Track deployed functions for cleanup
        self.deployed_functions = [d for d in deployments if d.get('deployed')]
        
        # Save deployment info
        with open('deployments.json', 'w') as f:
            json.dump(deployments, f, indent=2)
        
        successful_deployments = [d for d in deployments if d.get('deployed') and d.get('url')]
        print(f"\nSummary: {len(successful_deployments)}/{self.config.num_functions} functions deployed successfully")
        print(f"         {len(test_results)} test results collected")
        
        return deployments, test_results, cold_times
    
    def save_results(self, deployments: List[Dict[str, Any]], test_results: List[Dict[str, Any]]):
        """Save test results to file."""
        with open(self.config.results_file, 'w') as f:
            json.dump({
                'deployments': deployments,
                'test_results': test_results,
                'test_timestamp': datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    
    def get_results(self) -> Dict[str, Any]:
        """Return test results as a dictionary."""
        return {
            'deployments': self.deployments if hasattr(self, 'deployments') else [],
            'test_results': self.test_results if hasattr(self, 'test_results') else [],
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
                    lambda fn=func['function_name']: DeleteTask(fn, self.config).execute()
                ): func['function_name']
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
        self.deployed_functions = []
    
    def run(self) -> Dict[str, Any]:
        """Run the complete test workflow and return results."""
        print("=" * 80)
        print("Cloud Function Parallel Cold Start Performance Test")
        print("=" * 80)
        print(f"Number of Functions: {self.config.num_functions}")
        print(f"Cold Start Wait Time: {self.config.wait_minutes} minutes")
        print(f"Region: {self.config.region}")
        print(f"Project: {self.config.project}")
        print(f"Base Function Name: {self.config.base_function_name}")
        print(f"Number of Worker Threads: {self.config.num_workers}")
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