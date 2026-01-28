"""Manager class for coordinating Cloud Function cold start tests."""

from typing import Optional
from pathlib import Path

from shared_modules.base_manager import BaseBenchmarkManager
from shared_modules.gcf_models.gcp_function import GCPFunction
from shared_modules.wait_for_cold import ColdStartDetectionError
from .cold_start_test_task import ColdStartTestTask
from shared_modules.cli_parser import ParsedCLIArguments

class ColdStartBenchmarkManager(BaseBenchmarkManager):
    """Specific manager for Cold Start benchmarks."""
    
    def __init__(self, config: ParsedCLIArguments, function_dir: Path):
        """Initialize with specific test name."""
        super().__init__(
            config, 
            function_dir, 
            test_name="Cloud Function Parallel Cold Start Performance Test"
        )
        # Check for API key and disable action setup if missing to avoid repetitive warnings
        if not getattr(self.config, 'lightrun_api_key', None):
            print("Warning: Lightrun API key not provided. Snapshot insertion disabled for this run.")
            self.config.skip_lightrun_action_setup = True

    def get_test_task(self, function: GCPFunction, deployment_start_time: float):
        """Return cold start test task."""
        return ColdStartTestTask(function, self.config, deployment_start_time)

    def prepare_function(self, function: GCPFunction, deployment_start_time: float) -> Optional[float]:
        """
        Prepare function.
        Logic moved to ColdStartTestTask, so this is a no-op or placeholder.
        """
        # We can return None or 0.
        # BaseManager prints prep metric if returned.
        return 0.0