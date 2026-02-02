"""Delete task for Cloud Functions."""
import logging
import subprocess
from typing import Optional

from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult, DeleteSuccess, DeleteFailure


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

    def _get_resource_info(self) -> dict:
        """Retrieves function details including source storage and image."""
        try:
            cmd = ['gcloud', 'functions', 'describe', self.function.name,
                   f'--region={self.function.region}',
                   f'--project={self.function.project}',
                   '--format=json']
            if self.function.gen2:
                cmd.append('--gen2')

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.logger.warning(f"Could not describe function for cleanup: {result.stderr}")
                return {}
            
            import json
            data = json.loads(result.stdout)
            
            info = {}
            
            # Extract storage source
            # Gen 2: buildConfig.source.storageSource.bucket/object
            # Gen 1: sourceArchiveUrl
            if self.function.gen2:
                try:
                    storage_source = data.get('buildConfig', {}).get('source', {}).get('storageSource', {})
                    bucket = storage_source.get('bucket')
                    obj = storage_source.get('object')
                    if bucket and obj:
                        info['source_url'] = f"gs://{bucket}/{obj}"
                except Exception:
                    pass
            else:
                info['source_url'] = data.get('sourceArchiveUrl')

            # Extract image URI
            # Gen 2: buildConfig.imageUri
            # Gen 1: ? (Usually not managed by user in same way, often eu.gcr.io)
            if self.function.gen2:
                info['image_uri'] = data.get('buildConfig', {}).get('imageUri')
            
            return info
        except Exception as e:
            self.logger.warning(f"Failed to get resource info: {e}")
            return {}

    def _delete_resources(self, info: dict):
        """Deletes associated resources (source zip, container image)."""
        source_url = info.get('source_url')
        image_uri = info.get('image_uri')

        if source_url:
            try:
                self.logger.info(f"Deleting source archive: {source_url}")
                # Use gcloud storage rm for newer cli, or gsutil
                # Safe bet: gcloud storage rm
                res = subprocess.run(['gcloud', 'storage', 'rm', source_url, '--quiet'], 
                                   capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
                    self.logger.warning(f"Failed to delete source {source_url}: {res.stderr}")
            except Exception as e:
                self.logger.warning(f"Exception deleting source {source_url}: {e}")

        if image_uri:
            try:
                self.logger.info(f"Deleting container image: {image_uri}")
                # gcloud artifacts docker images delete IMAGE_URI --delete-tags --quiet
                # Image URI includes tag/digest. We probably want to delete the specific digest or tag deployed.
                # If image_uri is like ".../name@sha256:...", deleting it removes that specific digest.
                res = subprocess.run(['gcloud', 'artifacts', 'docker', 'images', 'delete', image_uri, 
                                    '--delete-tags', '--quiet'],
                                   capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
                    self.logger.warning(f"Failed to delete image {image_uri}: {res.stderr}")
            except Exception as e:
                self.logger.warning(f"Exception deleting image {image_uri}: {e}")

    def execute(self, timeout: int) -> DeleteFunctionResult:
        """Execute the deletion task."""
        self.logger.info(f"Deleting function {self.function.name} in {self.function.region}...")
        
        # Get resource info BEFORE deletion
        resource_info = self._get_resource_info()

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
                
                # Cleanup resources
                self._delete_resources(resource_info)
                
                return DeleteSuccess(function_name=self.function.name)

            self.logger.warning(f"Failed to delete function {self.function.name}: {self.result.stderr}")
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
