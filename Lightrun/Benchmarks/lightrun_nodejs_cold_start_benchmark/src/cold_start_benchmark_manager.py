"""Manager class for coordinating Cloud Function cold start tests."""

from typing import Optional
import argparse
from pathlib import Path

from shared_modules.base_manager import BaseBenchmarkManager
from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.wait_for_cold import ColdStartDetectionError


class ColdStartBenchmarkManager(BaseBenchmarkManager):
    """Specific manager for Cold Start benchmarks."""
    
    def __init__(self, config: argparse.Namespace, function_dir: Path):
        """Initialize with specific test name."""
        super().__init__(
            config, 
            function_dir, 
            test_name="Cloud Function Parallel Cold Start Performance Test"
        )

    def prepare_function(self, function: GCPFunction, deployment_start_time: float) -> Optional[float]:
        """
        Wait for function to become cold.
        
        Args:
            function: Deployed function object
            deployment_start_time: Timestamp when deployments started
            
        Returns:
            Time to cold in seconds
        """
        if getattr(self.config, 'skip_wait_for_cold', False):
            print(f"[{function.index:3d}] Skipping wait for cold...")
            return None

        # Call the specific wait logic
        # Note: wait_for_cold returns time_to_cold_seconds
        try:
            time_to_cold = function.wait_for_cold(self.config, deployment_start_time)
            
            # Step 2: Grace period (1 minute) after cold confirmation - specific to this benchmark
            print(f"[{function.index:3d}] Waiting 1 minute grace period before testing...")
            import time
            time.sleep(60)
            
            return time_to_cold
            
        except ColdStartDetectionError as e:
            # Re-raise to be caught by base class generic handler, or handle here if we want specific logging
            # The base class prints "Preparation failed: {e}" which is fine.
            raise e