"""Delete task for Cloud Functions."""

import subprocess
from typing import Dict, Any, Optional
import argparse
from shared_modules.cli_parser import ParsedCLIArguments
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction


class DeleteFunctionTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function: GCPFunction):
        """
        Initialize delete task.
        
        Args:
            function: GCPFunction object to delete
        """
        self.function = function
    
    def execute(self) -> Dict[str, Any]:
        """Execute the deletion task."""
        try:
            result = subprocess.run(
                [
                    'gcloud', 'functions', 'delete', self.function.name,
                    f'--region={self.function.region}',
                    {'--gen2' if function.gen2 else ''},
                    f'--project={self.function.project}',
                    '--quiet'
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                'function_name': self.function.name,
                'success': result.returncode == 0,
                'error': result.stderr[:200] if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'function_name': self.function.name,
                'success': False,
                'error': str(e)
            }
