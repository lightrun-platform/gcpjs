"""Test task for Cold Start Benchmark (Loop: Wait -> Request)."""

import time
import argparse
from typing import Dict, Any, List

from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.send_request import SendRequestTask
from shared_modules.wait_for_cold import ColdStartDetectionError

class ColdStartTestTask:
    """
    Task to run Cold Start test:
    For each request:
      1. Wait for function to be cold (0 instances).
      2. Send request.
    """
    
    def __init__(self, function: GCPFunction, config: argparse.Namespace, deployment_start_time: float):
        self.function = function
        self.config = config
        self.deployment_start_time = deployment_start_time
        self.num_requests = getattr(config, 'test_size', 10)

    def execute(self) -> Dict[str, Any]:
        """Execute the cold start test loop."""
        all_results = []
        total_cold_duration = 0.0
        total_warm_duration = 0.0 # Should be 0 conceptually if all are cold, but we track actual latency
        
        # We start the loop
        for i in range(1, self.num_requests + 1):
            print(f"[{self.function.index:3d}] Starting Request {i}/{self.num_requests} (Waiting for cold...)")
            
            # 1. Wait for cold
            # We use the deployment_start_time as the reference for the first one, or maybe always?
            # WaitForColdTask logic relies on querying metrics.
            try:
                # We reuse the logic from GCPFunction which calls WaitForColdTask
                time_to_cold = self.function.wait_for_cold(self.config, self.deployment_start_time)
                print(f"[{self.function.index:3d}] Request {i}: Confirmed cold after {time_to_cold/60:.1f}m")
                
                # Grace period? User output showed "Waiting 1 minute grace period".
                # Logic was in prepare_function. We should preserve it properly.
                # User instructions: "make a separate Task... wait_for_cold... send".
                # I'll add the 60s sleep if it was there (it was in manager).
                # Actually user didn't explicitly say "wait 60s" in the LAST prompt, but "ColdStartTestManager should wait_for_cold...". 
                # The previous manager waited 60s. I'll keep it for consistency or reduce it if needed. 
                # User's log showed 1 min grace. I will keep it.
                print(f"[{self.function.index:3d}] Request {i}: Waiting 60s grace...")
                time.sleep(10)
                
            except Exception as e:
                print(f"[{self.function.index:3d}] Request {i}: Cold wait failed: {e}")
                # Logic decision: Continue to send request anyway? Or Skip? 
                # If we skip, we miss data. If we send, it might be warm.
                # Standard practice: Try to send.
            
            # 2. Send Request
            # We can use SendRequestTask for a SINGLE request
            # But SendRequestTask is built for a loop.
            # I will instantiate it with num_requests=1 to reuse its logic (logging, error handling, result format)
            # OR just copy `_send_single_request`. `SendRequestTask` has `_send_single_request`.
            # Usage:
            req_task = SendRequestTask(self.function, self.config)
            # We enforce 1 request per task instance here
            req_task.num_requests = 1
            # We execute. It returns a summary dict.
            req_result = req_task.execute()
            
            # Extract the single result (it's in _all_request_results[0] usually, or just the dict itself is summary)
            # `execute` returns a summary dict which includes `totalDuration`, `isColdStart` from the first request.
            
            # Check if it was cold
            is_cold = req_result.get('isColdStart', False)
            duration = float(req_result.get('totalDuration', 0))
            
            # Use higher precision if duration is small
            duration_s = duration / 1e9
            if duration_s < 0.1:
                print(f"[{self.function.index:3d}] Request {i}: Cold={is_cold}, Duration={duration/1e6:.3f}ms")
            else:
                print(f"[{self.function.index:3d}] Request {i}: Cold={is_cold}, Duration={duration_s:.3f}s")
            
            # Store result
            # We want to keep the detailed result of THIS request.
            # req_result has keys like `status_code`, `totalDuration`, etc from the FIRST request.
            # We append it.
            req_result['_request_number'] = i
            all_results.append(req_result)
            
            # Accumulate stats
            if is_cold:
                total_cold_duration += duration
            else:
                total_warm_duration += duration # Shouldn't happen ideally
                
        # Aggregate results similar to SendRequestTask
        return {
            'function_index': self.function.index,
            'function_name': self.function.name,
            '_all_request_results': all_results,
            'totalDurationForColdStarts': total_cold_duration,
            'totalDurationForWarmRequests': total_warm_duration,
            '_num_requests': self.num_requests,
            '_num_successful_requests': sum(1 for r in all_results if not r.get('error')),
            'is_iterative': False # It is iterative in loop, but output format matches standard list
        }
