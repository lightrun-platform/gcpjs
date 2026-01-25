"""Delete task for Cloud Functions."""

import subprocess
from typing import Dict, Any, Optional
import argparse
from .models import GCPFunction


class DeleteTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function: GCPFunction, config: argparse.Namespace):
        """
        Initialize delete task.
        
        Args:
            function: GCPFunction object to delete
            config: Configuration namespace with region and project
        """
        self.function = function
        self.config = config
    
    def execute(self) -> Dict[str, Any]:
        """Execute the deletion task."""
        try:
            result = subprocess.run(
                [
                    'gcloud', 'functions', 'delete', self.function.name,
                    f'--region={self.function.region}',
                    '--gen2',
                    f'--project={self.config.project}',
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
