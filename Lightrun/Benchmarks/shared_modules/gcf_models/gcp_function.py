"""GCPFunction model."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from .deployment_result import DeploymentResult

@dataclass
class GCPFunction:
    """Represents a Google Cloud Function instance throughout its lifecycle."""
    index: int
    region: str
    base_name: str
    url: Optional[str] = None
    is_deployed: bool = False
    deployment_duration_seconds: Optional[float] = None
    deployment_duration_nanoseconds: Optional[int] = None
    deploy_time: Optional[str] = None
    time_to_cold_seconds: Optional[float] = None
    time_to_cold_minutes: Optional[float] = None
    test_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    deployment_result: Optional[DeploymentResult] = None

    @property
    def name(self) -> str:
        """Computed function name in GCP format."""
        return f"{self.base_name}-{self.index:03d}".lower()

    @property
    def display_name(self) -> str:
        """Computed display name for the function."""
        return f"{self.base_name}-gcf-performance-test-{self.index:03d}"

    def deploy(self, lightrun_secret: str, config, function_dir):
        """
        Deploy this function.

        Args:
            lightrun_secret: Lightrun secret for environment variable
            config: Configuration namespace with deployment settings
            function_dir: Directory containing the function source code

        Returns:
            DeploymentResult: Result of the deployment
        """
        from ..deploy import DeployTask

        if self.is_deployed:
            return DeploymentResult(
                success=True,
                url=self.url,
                deployment_duration_seconds=self.deployment_duration_seconds,
                deployment_duration_nanoseconds=self.deployment_duration_nanoseconds,
                deploy_time=self.deploy_time
            )   

        # Deploy the function
        deploy_task = DeployTask(
            function_name=self.name,
            display_name=self.display_name,
            region=self.region,
            index=self.index,
            lightrun_secret=lightrun_secret,
            config=config,
            function_dir=function_dir
        )
        result = deploy_task.execute()
        if result.success:
            self.deployment_result = result
            self.is_deployed = True
            self.url = result.url
            self.deployment_duration_seconds = result.deployment_duration_seconds
            self.deployment_duration_nanoseconds = result.deployment_duration_nanoseconds
            self.deploy_time = result.deploy_time
        else:
            self.is_deployed = False
            self.error = result.error
        
        return result

    def wait_for_cold(self, config, deployment_start_time):
        """Wait for the function to become cold."""
        # Import here to avoid circular import
        from ..wait_for_cold import WaitForColdTask
        return WaitForColdTask(
            function_name=self.name,
            region=self.region,
            index=self.index,
            config=config
        ).execute(deployment_start_time)
