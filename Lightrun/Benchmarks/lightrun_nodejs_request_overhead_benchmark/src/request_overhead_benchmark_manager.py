"""Manager class for Request Overhead Benchmark."""

import time
import requests
import argparse
from pathlib import Path
from typing import Optional

from shared_modules.base_manager import BaseBenchmarkManager
from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.lightrun_api import LightrunAPI


class RequestOverheadBenchmarkManager(BaseBenchmarkManager):
    """Specific manager for Request Overhead benchmarks."""
    
    def __init__(self, config: argparse.Namespace, function_dir: Path):
        """Initialize with specific test name."""
        super().__init__(
            config, 
            function_dir, 
            test_name="Lightrun Request Overhead Performance Test"
        )
        # Disable auto-snapshot in SendRequestTask since we manage actions manually
        self.config.skip_lightrun_action_setup = True

    def prepare_function(self, function: GCPFunction, deployment_start_time: float) -> Optional[float]:
        """
        Prepare function: Warmup -> Add Actions -> Wait.
        
        Args:
            function: Deployed function object
            deployment_start_time: Timestamp when deployments started
            
        Returns:
            Setup duration in seconds
        """
        start_time = time.time()
        
        # 1. Send 1 warmup request
        print(f"[{function.index:3d}] Sending warmup request...")
        try:
            response = requests.get(function.url, timeout=30)
            if response.status_code != 200:
                print(f"[{function.index:3d}] Warning: Warmup request returned {response.status_code}")
        except Exception as e:
            print(f"[{function.index:3d}] Warning: Warmup request failed: {e}")
            # We continue anyway, hoping it's alive enough to receive actions or just warm enough for test

        # 2. Add Lightrun actions (if it's a Lightrun function)
        # We determine this by checking if 'lightrun' is in the name, or checking config
        is_lightrun = 'lightrun' in function.name.lower()
        
        if is_lightrun:
            num_actions = getattr(self.config, 'number_of_lightrun_actions', 0)
            action_type = getattr(self.config, 'lightrun_action_type', 'snapshot')
            
            if num_actions > 0:
                print(f"[{function.index:3d}] Adding {num_actions} {action_type}s...")
                lightrun_api = LightrunAPI(
                    api_key=getattr(self.config, 'lightrun_api_key', ''),
                    company_id=getattr(self.config, 'lightrun_company_id', '')
                )
                
                agent_id = lightrun_api.get_agent_id(function.display_name)
                
                if agent_id:
                    for i in range(num_actions):
                        # Add action
                        # We use helloLightrun.js line 67 (inside the handler usually)
                        # Actually, looking at code_generator:
                        # The function body starts around line 20-30 depending on test-file-length
                        # We need a valid line number. 
                        # In code_generator, `func` definition line is stable-ish but depends on `dummy_functions` length.
                        # `helloLightrun.js` structure:
                        # ... imports ...
                        # lightrun.init ...
                        # dummy_functions (N blocks of ~8 lines)
                        # let func = ...
                        # 
                        # We should probably target the line inside `func`.
                        # Or just pick a high enough line number if the file is short, but code gen makes it variable.
                        # Wait, CodeGenerator puts `func` AT THE END.
                        # We can just target the line where `res.send` is called, or the start of `func`.
                        # Since we can't easily parse line numbers dynamically here without reading the file,
                        # AND `CodeGenerator` is creating the file...
                        # Maybe we should hardcode the line number in `CodeGenerator` or ask it?
                        # For now, let's assume `CodeGenerator` puts `func` at the bottom.
                        # 
                        # Let's try to add the action at the END of the file minus 3 lines (res.send).
                        # Or better: `CodeGenerator` generates the file. We are in the manager. We have `function_dir`.
                        # We can read `helloLightrun.js` and find "handlerRunTime".
                        
                        file_path = self.function_dir / "helloLightrun.js"
                        line_number = 50 # Fallback
                        try:
                            with open(file_path, 'r') as f:
                                lines = f.readlines()
                                for idx, line in enumerate(lines):
                                    if "handlerRunTime:" in line:
                                        line_number = idx + 1
                                        break
                        except Exception:
                            pass

                        if action_type == 'snapshot':
                            lightrun_api.add_snapshot(
                                agent_id=agent_id,
                                filename="helloLightrun.js",
                                line_number=line_number,
                                max_hit_count=getattr(self.config, 'num_requests_per_function', 10) + 10
                            )
                        elif action_type == 'log':
                            lightrun_api.add_log_action(
                                agent_id=agent_id,
                                filename="helloLightrun.js",
                                line_number=line_number,
                                message="Lightrun Benchmark Log {i}",
                                max_hit_count=getattr(self.config, 'num_requests_per_function', 10) + 10
                            )
                        
                        # Small delay to avoid API rate limits?
                        time.sleep(0.1)
                else:
                    print(f"[{function.index:3d}] ⚠ Could not find agent ID for {function.display_name}")

        # 3. Wait 15s grace period
        print(f"[{function.index:3d}] Waiting 15s grace period...")
        time.sleep(15)
        
        return time.time() - start_time
