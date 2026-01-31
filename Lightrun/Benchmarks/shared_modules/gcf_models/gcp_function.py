"""GCPFunction model."""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from .deployment_result import DeploymentResult
from ..cli_parser import ParsedCLIArguments
from ..gcf_task_primitives.delete_function_task import DeleteFunctionTask


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
    deployment_result: Optional[DeploymentResult] = None,

    runtime: str = None
    function_source_code_dir: Path = None
    entry_point = None

    # commonly used parameters with sane defaults
    memory: str = "512Mi",
    cpu: str = "2",
    concurrency: int = 80,
    max_instances: int = 1,
    min_instances: int = 0,
    timeout: int = 540,
    project: str = "lightrun-temp",
    allow_unauthenticated: bool = True,
    deployment_timeout: int = 600,  # 10 minutes
    quiet: bool = True,
    gen2: bool = True,
    env_vars: Dict[str, str] = None,
    kwargs: Dict[str, Any] = None,

    def deploy(self, deployment_timeout_seconds=600) -> DeploymentResult:
        """
        Deploy this function. idempotent action - if the function was already deployed in the past it will not deploy
        again but return the previous result.

        Args:
            deployment_timeout_seconds: maximum time to wait for the function's deployment to complete successfully.

        Returns:
            DeploymentResult: Result of the deployment
        """
        from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask

        if self.is_deployed:
            return DeploymentResult(
                success=True,
                url=self.url,
                deployment_duration_seconds=self.deployment_duration_seconds,
                deployment_duration_nanoseconds=self.deployment_duration_nanoseconds,
                deploy_time=self.deploy_time
            )   

        # Deploy the function
        result = DeployFunctionTask(deployment_timeout_seconds).deploy_gcp_function(
                                                                function_name,
                                                                region,
                                                                runtime,
                                                                entry_point,
                                                                source_code_dir,
                                                                memory,
                                                                cpu,
                                                                concurrency,
                                                                max_instances,
                                                                min_instances,
                                                                timeout,
                                                                project,
                                                                allow_unauthenticated,
                                                                deployment_timeout,
                                                                quiet,
                                                                gen2,
                                                                env_vars,
                                                                **self.kwargs)
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


    def delete(self):
        return DeleteFunctionTask(self).execute()

    def wait_for_cold(self, config, deployment_start_time):
        """Wait for the function to become cold."""
        # Import here to avoid circular import
        from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.wait_for_cold_task import WaitForColdTask
        return WaitForColdTask(
            function_name=self.name,
            region=self.region,
            config=config
        ).execute(deployment_start_time)
