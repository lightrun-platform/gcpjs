"""Delete task for Cloud Functions."""

import subprocess
from typing import Dict, Any
import argparse


class DeleteTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function_name: str, config: argparse.Namespace):
        """
        Initialize delete task.
        
        Args:
            function_name: Name of the function to delete
            config: Configuration namespace with region and project
        """
        self.function_name = function_name
        self.config = config
    
    def execute(self) -> Dict[str, Any]:
        """Execute the deletion task."""
        try:
            result = subprocess.run(
                [
                    'gcloud', 'functions', 'delete', self.function_name,
                    f'--region={self.config.region}',
                    '--gen2',
                    f'--project={self.config.project}',
                    '--quiet'
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                'function_name': self.function_name,
                'success': result.returncode == 0,
                'error': result.stderr[:200] if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'function_name': self.function_name,
                'success': False,
                'error': str(e)
            }
