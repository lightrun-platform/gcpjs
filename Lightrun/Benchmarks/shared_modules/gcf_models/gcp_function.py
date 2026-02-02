"""GCPFunction model."""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, ClassVar
from pathlib import Path

from . import DeploymentResult
from .delete_function_result import DeleteFunctionResult
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

MAX_GCP_FUNCTION_NAME_LENGTH = 63

@dataclass
class GCPFunction:
    """Represents a Google Cloud Function instance throughout its lifecycle."""

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
    env_vars: Dict[str, str] = None
    kwargs: Dict[str, Any] = None

    logger: logging.Logger = None

    # other properties - internal state, excluded from init
    url: Optional[str] = field(init=False, default=None)
    deployment_duration_seconds: Optional[float] = field(init=False, default=None)
    deployment_duration_nanoseconds: Optional[int] = field(init=False, default=None)
    deploy_time: Optional[str] = field(init=False, default=None)
    time_to_cold_seconds: Optional[float] = field(init=False, default=None)
    time_to_cold_minutes: Optional[float] = field(init=False, default=None)
    test_result: Optional[Dict[str, Any]] = field(init=False, default=None)
    error: Optional[str] = field(init=False, default=None)
    deployment_result: Optional[DeploymentResult] = field(init=False, default=None)


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
