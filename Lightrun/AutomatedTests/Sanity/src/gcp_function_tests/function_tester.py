"""Main function testing orchestration."""
import asyncio
import time
import shutil
from pathlib import Path
from typing import Optional
from .models import TestResult, DeploymentResult
from .config import REGION_PRECEDENCE, REGION, PROJECT_ID, FUNCTION_NAME_PREFIX
from .gcp_deployer import GCPDeployer
from .function_creator import FunctionCreator
from .performance_tester import PerformanceTester
from .lightrun_tester import LightrunTester
from .result_handler import ResultHandler


class FunctionTester:
    """Orchestrates testing of a single function."""
    
    def __init__(self):
        self.deployer = GCPDeployer()
        self.function_creator = FunctionCreator()
        self.performance_tester = PerformanceTester()
        self.lightrun_tester = LightrunTester()
        self.result_handler = ResultHandler()
    
    async def test_function(self, nodejs_version: int, gen_version: int) -> TestResult:
        """Test a single function deployment and execution."""
        function_name = f"{FUNCTION_NAME_PREFIX}node{nodejs_version}-gen{gen_version}"
        result = TestResult(
            function_name=function_name,
            gen_version=gen_version,
            nodejs_version=nodejs_version
        )
        
        print(f"\n{'='*60}")
        print(f"Testing: {function_name}")
        print(f"{'='*60}")
        
        # Create function directory
        func_dir = self.function_creator.create_test_function(nodejs_version, gen_version)
        
        try:
            # Deploy function (with region fallback)
            print(f"Deploying {function_name}...")
            deployment_result = await self.deployer.deploy_with_fallback(
                function_name, func_dir, nodejs_version, gen_version
            )
            # Store the immutable DeploymentResult object
            result.deployment_result = deployment_result
            # Set legacy fields for backward compatibility
            result.deployment_error = deployment_result.error
            result.function_url = deployment_result.url
            result.region_used = deployment_result.used_region
            
            if not deployment_result.success:
                print(f"  ❌ Deployment failed: {deployment_result.error}")
                return result
            
            print(f"  ✅ Deployed successfully: {deployment_result.url}")
            
            # Wait for function to be ready
            print("  Waiting for function to be ready...")
            await asyncio.sleep(10)
            
            # Test cold/warm starts
            print("Testing performance...")
            cold_avg, warm_avg, cold_success, warm_success = await self.performance_tester.test_cold_warm_starts(deployment_result.url)
            result.cold_start_avg_ms = cold_avg
            result.warm_start_avg_ms = warm_avg
            result.cold_start_requests = cold_success
            result.warm_start_requests = warm_success
            print(f"  Cold start avg: {cold_avg:.2f}ms ({cold_success}/{self.performance_tester.cold_start_requests} successful)")
            print(f"  Warm start avg: {warm_avg:.2f}ms ({warm_success}/{self.performance_tester.warm_start_requests} successful)")
            
            # Check logs for errors
            print("Checking logs for errors...")
            logs_ok, logs_error = await self.deployer.check_logs_for_errors(function_name, deployment_result.used_region)
            result.logs_error_check = logs_ok
            result.logs_error_message = logs_error
            if logs_ok:
                print("  ✅ No errors in logs")
            else:
                print(f"  ⚠️  Errors found in logs: {logs_error[:200] if logs_error else 'Unknown'}")
            
            # Wait for agent to register
            print("Waiting for Lightrun agent to register...")
            await asyncio.sleep(30)
            
            # Get agent ID
            agent_id = self.lightrun_tester.get_agent_id(function_name)
            if agent_id:
                print(f"  Found agent ID: {agent_id}")
            else:
                print("  ⚠️  Agent ID not found (Lightrun tests will be skipped)")
            
            # Test Lightrun features
            if agent_id and deployment_result.url:
                print("Testing Lightrun snapshot...")
                snapshot_ok, snapshot_error = await self.lightrun_tester.test_snapshot(function_name, deployment_result.url, agent_id)
                result.snapshot_test = snapshot_ok
                result.snapshot_error = snapshot_error
                if snapshot_ok:
                    print("  ✅ Snapshot test passed")
                else:
                    print(f"  ❌ Snapshot test failed: {snapshot_error}")
                
                print("Testing Lightrun counter...")
                counter_ok, counter_error = await self.lightrun_tester.test_counter(function_name, deployment_result.url, agent_id)
                result.counter_test = counter_ok
                result.counter_error = counter_error
                if counter_ok:
                    print("  ✅ Counter test passed")
                else:
                    print(f"  ❌ Counter test failed: {counter_error}")
                
                print("Testing Lightrun metric...")
                metric_ok, metric_error = await self.lightrun_tester.test_metric(function_name, deployment_result.url, agent_id)
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
    
    async def cleanup_function(self, result: TestResult) -> None:
        """Clean up a deployed function."""
        if result.deployment_result and result.deployment_result.success and result.deployment_result.used_region:
            print(f"Cleaning up {result.function_name}...")
            success, error = await self.deployer.delete_function(result.function_name, result.deployment_result.used_region)
            result.cleanup_error = error
            if success:
                print(f"  ✅ Cleaned up {result.function_name}")
            else:
                print(f"  ⚠️  Cleanup failed: {error}")
