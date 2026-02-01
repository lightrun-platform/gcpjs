"""Delete task for Cloud Functions."""

import subprocess
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult


class DeleteFunctionTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function: GCPFunction):
        """
        Initialize delete task.
        
        Args:
            function: GCPFunction object to delete
        """
        self.function = function
        self.result = None

    @property
    def stderr(self):
        return self.result.stderr[:200] if self.result.stderr else None

    def execute(self, timeout) -> DeleteFunctionResult:
        """Execute the deletion task."""
        try:

            args = ['gcloud', 'functions', 'delete', self.function.name,
                   f'--region={self.function.region}',
                   f'--project={self.function.project}',
                   '--quiet',
                   ]
            if self.function.gen2:
                args.append('--gen2')

            self.result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)

            if self.result.returncode == 0:
                return DeleteFunctionResult(function_name=self.function.name, success=True, error=None)

            return DeleteFunctionResult(function_name=self.function.name,
                                        success=False,
                                        error=Exception(f"Failed to delete function: {self.function.name}"),
                                        stderr=self.stderr)

        except Exception as e:
            return DeleteFunctionResult(function_name=self.function.name, success=False, error=e, stderr=self.stderr)
