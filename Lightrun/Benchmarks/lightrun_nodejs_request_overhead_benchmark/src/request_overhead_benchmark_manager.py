"""Manager class for Request Overhead Benchmark."""

import time
import requests
import argparse
from pathlib import Path
from typing import Optional

from shared_modules.base_manager import BaseBenchmarkManager
from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.lightrun_api import LightrunAPI
from .iterative_test_task import IterativeOverheadTestTask


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

    def get_test_task(self, function: GCPFunction, deployment_start_time: float):
        """Return iterative test task."""
        return IterativeOverheadTestTask(function, self.config, self.function_dir)

    def prepare_function(self, function: GCPFunction, deployment_start_time: float) -> Optional[float]:
        """
        Prepare function: Warmup only.
        (Actions are handled in IterativeOverheadTestTask).
        
        Args:
            function: Deployed function object
            deployment_start_time: Timestamp when deployments started
            
        Returns:
            Setup duration in seconds
        """
        start_time = time.time()
        
        # 1. Extended Warmup (V8 Optimization)
        print(f"[{function.index:3d}] Starting extended warmup (40s)...")
        warmup_end = time.time() + 40
        while time.time() < warmup_end:
            try:
                requests.get(function.url, timeout=5)
            except Exception:
                pass
            time.sleep(0.5)
            
        # Burst warmup
        print(f"[{function.index:3d}] Sending burst warmup (10 requests)...")
        for _ in range(10):
            try:
                requests.get(function.url, timeout=5)
            except Exception:
                pass

        return time.time() - start_time
