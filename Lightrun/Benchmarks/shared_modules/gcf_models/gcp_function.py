"""GCPFunction model."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from .deployment_result import DeploymentResult
from ..cli_parser import ParsedCLIArguments


@dataclass
class GCPFunction:
    """Represents a Google Cloud Function instance throughout its lifecycle."""
    region: str
    name: str
    is_lightrun_variant: bool = False
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

    def deploy(self, lightrun_secret: str, config: ParsedCLIArguments, function_dir: Path):
        """
        Deploy this function.

        Args:
            lightrun_secret: Lightrun secret for environment variable
            config: Configuration namespace with deployment settings
            function_dir: Directory containing the function source code

        Returns:
            DeploymentResult: Result of the deployment
        """
        from ..deploy_function_task import DeployFunctionTask

        if self.is_deployed:
            return DeploymentResult(
                success=True,
                url=self.url,
                deployment_duration_seconds=self.deployment_duration_seconds,
                deployment_duration_nanoseconds=self.deployment_duration_nanoseconds,
                deploy_time=self.deploy_time
            )   

        # Deploy the function
        deploy_task = DeployFunctionTask(
            function_name=self.name,
            display_name=self.display_name,
            region=self.region,
            lightrun_secret=lightrun_secret,
            config=config,
            source_code_dir=function_dir
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
            config=config
        ).execute(deployment_start_time)
