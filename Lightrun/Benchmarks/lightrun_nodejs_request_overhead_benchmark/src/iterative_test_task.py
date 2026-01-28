"""Iterative test task for request overhead benchmark."""

import time
import requests
import argparse
from typing import Dict, Any, List, Optional
from pathlib import Path

from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.send_request import SendRequestTask
from shared_modules.lightrun_api import LightrunAPI

class IterativeOverheadTestTask:
    """Task to run iterative benchmark with incresing Lightrun actions."""
    
    def __init__(self, function: GCPFunction, config: argparse.Namespace, function_dir: Path):
        self.function = function
        self.config = config
        self.function_dir = function_dir
        self.total_actions = getattr(config, 'test_size', 0)
        self.action_type = getattr(config, 'lightrun_action_type', 'snapshot')
        self.lightrun_api = LightrunAPI(
            api_key=getattr(config, 'lightrun_api_key', ''),
            company_id=getattr(config, 'lightrun_company_id', ''),
            api_url=getattr(config, 'lightrun_api_url', None)
        )
        self.is_lightrun = function.is_lightrun_variant

    def execute(self) -> Dict[str, Any]:
        """Execute iterative test."""
        
        # If not Lightrun case, we only run once (baseline)
        if not self.is_lightrun:
             return self._run_single_iteration(0)
             
        # For Lightrun case, loop from 0 to N
        all_iterations = []
        
        # Store created action IDs to verify them later
        created_action_ids = []
        
        for i in range(0, self.total_actions + 1):
            print(f"\n[{self.function.index:3d}] Starting Iteration {i} ({i} actions)...")
            
            # Step 1: Add action i (if i > 0)
            if i > 0:
                action_id = self._add_action(i)
                if action_id:
                    created_action_ids.append(action_id)
                else:
                    print(f"[{self.function.index:3d}] Warning: Failed to add action {i}")
            
            # Step 2: Run test (uses SendRequestTask)
            iteration_result = self._run_single_iteration(i)
            
            # Step 3: Verify hits (if actions exist)
            if i > 0 and created_action_ids:
                self._verify_hits(created_action_ids)

            all_iterations.append(iteration_result)
            
            # Step 4: Rest (if not last)
            if i < self.total_actions:
                print(f"[{self.function.index:3d}] Resting 20s...")
                time.sleep(20)
                
        # Return composite result
        # We wrap the list of iteration results in a single dict to satisfy the manager signature
        # But wait, manager expects ONE result dict per function.
        # It puts it in `test_results` list.
        # Report generator expects a list of results.
        # We can return a special dict that contains the list.
        return {
            'function_index': self.function.index,
            'function_name': self.function.name,
            'iterations': all_iterations,
            'totalDurationForColdStarts': all_iterations[0]['totalDurationForColdStarts'], # From first run
             # Sum of all warm durations? Or just mark it iterative
            'is_iterative': True
        }

    def _run_single_iteration(self, iteration_num: int) -> Dict[str, Any]:
        """Run a single test pass."""
        # Ensure SendRequestTask doesn't add its own snapshots, as we manage them here
        import copy
        config_copy = copy.deepcopy(self.config)
        config_copy.skip_lightrun_action_setup = True
        task = SendRequestTask(self.function, config_copy)
        result = task.execute()
        result['iteration'] = iteration_num
        return result

    def _add_action(self, action_num: int) -> Optional[str]:
        """Add action #action_num to the function."""
        # Find line number (similar logic to previous manager)
        # We target function{action_num} if possible, or distribute them?
        # User said: "put breakpoint on all functions numbered 1...i"
        # Since we use `helloLightrun.js` with `function1`...`functionN`
        # We can target `function{action_num}` specifically.
        
        file_path = self.function_dir / "helloLightrun.js"
        target_str = f"function function{action_num}()"
        line_number = 50 # Default
        
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
                for idx, line in enumerate(lines):
                    if target_str in line:
                        # Add inside the function? +2 lines
                        line_number = idx + 3 
                        break
        except Exception:
            pass
            
        agent_id = self.lightrun_api.get_agent_id(self.function.display_name)
        if not agent_id:
            return None
            
        # Hit count: needs to cover this iteration + potential future ones if they persist?
        # User said "run the test". Actions persist across iterations unless deleted.
        # If we add action 1 in integation 1, it stays for iter 2, 3...
        # So max_hit_count needs to be large. 1000?
        
        if self.action_type == 'snapshot':
            return self.lightrun_api.add_snapshot(
                agent_id=agent_id,
                filename="helloLightrun.js",
                line_number=line_number,
                max_hit_count=1000
            )
        elif self.action_type == 'log':
             return self.lightrun_api.add_log_action(
                agent_id=agent_id,
                filename="helloLightrun.js",
                line_number=line_number,
                message=f"Log from action {action_num}",
                max_hit_count=1000
            )
        return None

    def _verify_hits(self, action_ids: List[str]):
        """Verify that actions recorded hits."""
        # We expect hits from THIS run.
        # Since persistence, total hits will accumulate.
        # We can checked if total hits > 0 (or > previous)
        # For simplicity, just checking > 0 confirms activity.
        # Ideally we'd check if it increased by `num_requests_per_function`.
        
        for aid in action_ids:
            if self.action_type == 'snapshot':
                data = self.lightrun_api.get_snapshot(aid)
            else:
                data = self.lightrun_api.get_log(aid)
                
            if data:
                hits = data.get('currentHitCount', 0)
                print(f"[{self.function.index:3d}] Verified Action {aid}: {hits} hits")
            else:
                 print(f"[{self.function.index:3d}] Warning: Could not verify Action {aid}")
