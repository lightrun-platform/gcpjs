"""GCPFunction model."""
import logging
from dataclasses import dataclass, field
from typing import Union, Dict, Optional, Any, List, ClassVar
from pathlib import Path
import subprocess
import json
from Lightrun.Benchmarks.shared_modules.cloud_assets import CloudAsset, GCSSourceObject, ArtifactRegistryImage

from . import DeploymentResult
from .delete_function_result import DeleteFunctionResult
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

MAX_GCP_FUNCTION_NAME_LENGTH = 63

@dataclass
class GCPFunction:
    """Represents a Google Cloud Function instance throughout its lifecycle."""

    logger: logging.Logger
    region: str
    name: str
    runtime: str
    function_source_code_dir: Path
    entry_point: str

    # commonly used parameters with sane defaults
    memory: str = "512Mi"
    cpu: str = "2"
    concurrency: int = 80
    max_instances: int = 1
    min_instances: int = 0
    timeout: int = 540
    project: str = "lightrun-temp"
    allow_unauthenticated: bool = True
    quiet: bool = True
    gen2: bool = True
    env_vars: Dict[str, str] = field(default_factory=dict)
    kwargs: Optional[Dict[str, Any]] = None
    labels: Dict[str, str] = field(default_factory=dict)

    test_result: Optional[Dict[str, Any]] = field(init=False, default=None)
    error: Optional[str] = field(init=False, default=None)
    deployment_result: Optional[DeploymentResult] = field(init=False, default=None)
    assets: Any = field(init=False, default_factory=list)  # List[CloudAsset]


    @property
    def url(self) -> Optional[str]:
        """Returns the function URL if deployment was successful."""
        if self.deployment_result and isinstance(self.deployment_result, DeploymentResult) and hasattr(self.deployment_result, 'url'):
            return self.deployment_result.url
        return None

    def discover_associated_assets(self) -> List[CloudAsset]:
        """
        Discovers cloud assets associated with this function.
        
        Returns:
            List of identified CloudAssets (GCS objects, AR images, etc.)
        """
        assets: List[CloudAsset] = []
        
        try:
            cmd = ['gcloud', 'functions', 'describe', self.name,
                   f'--region={self.region}',
                   f'--project={self.project}',
                   '--format=json']
            if self.gen2:
                cmd.append('--gen2')

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.warning(f"Could not describe function {self.name} to discover assets: {result.stderr.strip()}")
                return assets
            
            data = json.loads(result.stdout)
            
            # 1. Discover GCS Source Object
            source_url = None
            if self.gen2:
                try:
                    storage_source = data.get('buildConfig', {}).get('source', {}).get('storageSource', {})
                    bucket = storage_source.get('bucket')
                    obj = storage_source.get('object')
                    if bucket and obj:
                        source_url = f"gs://{bucket}/{obj}"
                except Exception:
                    pass
            else:
                source_url = data.get('sourceArchiveUrl')

            if source_url:
                self.logger.debug(f"Discovered associated GCS object: {source_url}")
                assets.append(GCSSourceObject(source_url))

            # 2. Discover Artifact Registry Image
            image_uri = None
            if self.gen2:
                image_uri = data.get('buildConfig', {}).get('imageUri')
            
            if image_uri:
                 self.logger.debug(f"Discovered associated Container Image: {image_uri}")
                 assets.append(ArtifactRegistryImage(image_uri))
                 
            return assets

        except Exception as e:
            self.logger.exception(f"Exception raised while discovering assets for '{self.name}': {e}")
            return assets

    @property
    def is_deployed(self) -> bool:
        return self.deployment_result and self.deployment_result.success

    def deploy(self, deployment_timeout_seconds=600) -> DeploymentResult:
        """
        Deploy this function. idempotent action - if the function was already deployed in the past it will not deploy
        again but return the previous result.

        Args:
            deployment_timeout_seconds: maximum time to wait for the function's deployment to complete successfully.
        Returns:
            DeploymentResult: Result of the deployment
        """

        if self.is_deployed:
            return self.deployment_result

        from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask
        task = DeployFunctionTask(self, deployment_timeout_seconds)
        self.deployment_result = task.deploy()
        return self.deployment_result


    def delete(self, delete_timeout_seconds=120) -> DeleteFunctionResult:
        from ..gcf_task_primitives.delete_function_task import DeleteFunctionTask
        return DeleteFunctionTask(self).execute(delete_timeout_seconds)

    def wait_for_cold(self, deployment_start_time, cold_check_delay, consecutive_cold_checks):
        """Wait for the function to become cold."""
        # Import here to avoid circular import
        from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.wait_for_cold_task import WaitForColdTask
        task = WaitForColdTask(self, cold_check_delay=cold_check_delay, consecutive_cold_checks=consecutive_cold_checks)
        return task.execute(deployment_start_time)
