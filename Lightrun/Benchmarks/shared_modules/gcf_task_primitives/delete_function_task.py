"""Delete task for Cloud Functions."""

import subprocess
import logging
from typing import Optional

from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult, DeleteSuccess, DeleteFailure
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory


class DeleteFunctionTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function: GCPFunction, logger_factory: LoggerFactory):
        """
        Initialize delete task.
        
        Args:
            function: GCPFunction object to delete
            logger_factory: Factory to create logger
        """
        self.function = function
        self.logger = logger_factory.get_logger(self.__class__.__name__)
        self.result = None

    @property
    def stderr(self) -> Optional[str]:
        return self.result.stderr[:200] if self.result and self.result.stderr else None

    def execute(self, timeout: int) -> DeleteFunctionResult:
        """Execute the deletion task."""
        self.logger.info(f"Deleting function {self.function.name} in {self.function.region}...")
        
        try:
            args = ['gcloud', 'functions', 'delete', self.function.name,
                   f'--region={self.function.region}',
                   f'--project={self.function.project}',
                   '--quiet',
                   ]
            if self.function.gen2:
                args.append('--gen2')
            
            self.logger.debug(f"Executing command: {' '.join(args)}")
            self.result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)

            if self.result.returncode == 0:
                self.logger.info(f"Function {self.function.name} deleted successfully.")
                return DeleteSuccess(function_name=self.function.name)

            self.logger.warning(f"Failed to delete function {self.function.name}: {self.result.stderr[:200]}")
            return DeleteFailure(
                function_name=self.function.name,
                error=Exception(f"Failed to delete function: {self.function.name}"),
                stderr=self.stderr
            )

        except Exception as e:
            self.logger.error(f"Exception during deletion of {self.function.name}: {e}")
            return DeleteFailure(
                function_name=self.function.name,
                error=e,
                stderr=self.stderr
            )
