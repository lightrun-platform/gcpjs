import subprocess
from typing import Optional, List

from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult, DeleteSuccess, DeleteFailure
from Lightrun.Benchmarks.shared_modules.cloud_assets import CloudAsset, NoSuchAsset


class DeleteFunctionTask:
    """Task to delete a single Cloud Function."""
    
    def __init__(self, function: GCPFunction):
        """
        Initialize delete task.
        
        Args:
            function: GCPFunction object to delete
        """
        self.function = function
        self.logger = function.logger
        self.result = None

    @property
    def stderr(self) -> Optional[str]:
        return self.result.stderr if self.result and self.result.stderr else None

    def execute(self, timeout: int) -> DeleteFunctionResult:
        """Execute the deletion task."""
        self.logger.info(f"Deleting function {self.function.name} in {self.function.region}")
        
        # 1. Identify assets to clean up
        assets: List[CloudAsset] = self.function.assets
        if not assets:
            self.logger.debug("No assets tracked in function model. Attempting discovery")
            # Use method on function instance
            assets = self.function.discover_associated_assets()
        
        if assets:
            self.logger.info(f"Identified {len(assets)} assets to clean up.")

        try:
            # 2. Delete the function
            args = ['gcloud', 'functions', 'delete', self.function.name,
                   f'--region={self.function.region}',
                   f'--project={self.function.project}',
                   '--quiet',
                   ]
            if self.function.gen2:
                args.append('--gen2')
            
            self.logger.debug(f"Executing command: {' '.join(args)}")
            self.result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)

            # 3. Clean up assets (regardless of function deletion success, 
            # as failures might leave assets or function might be already gone)
            for asset in assets:
                try:
                    asset.delete(self.logger)
                    self.logger.info(f"Cleaned up asset: {asset.name}")
                except NoSuchAsset:
                     self.logger.info(f"Asset {asset.name} already gone (verified by exist check).")
                except Exception as e:
                     self.logger.exception(f"Failed to clean up asset {asset.name}. Exception: {e}")

            if self.result.returncode == 0:
                self.logger.info(f"Function {self.function.name} deleted successfully.")
                return DeleteSuccess(function_name=self.function.name)
            
            # If function not found, treat as success but warn
            if "not found" in self.result.stderr.lower():
                self.logger.warning(f"Function {self.function.name} not found (already deleted?).")
                return DeleteSuccess(function_name=self.function.name)

            self.logger.warning(f"Failed to delete function {self.function.name}: {self.result.stderr}")
            return DeleteFailure(
                function_name=self.function.name,
                error=Exception(f"Failed to delete function: {self.result.stderr}"),
                stderr=self.stderr
            )

        except Exception as e:
            self.logger.exception(f"Exception during deletion of {self.function.name}: {e}")
            return DeleteFailure(
                function_name=self.function.name,
                error=e,
                stderr=self.stderr
            )
