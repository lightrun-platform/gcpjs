"""Deploy task for Cloud Functions."""
import logging
import subprocess
import time
import random
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Lightrun.Benchmarks.shared_modules.gcf_models.deploy_function_result import DeploymentResult, DeploymentSuccess, DeploymentFailure
from Lightrun.Benchmarks.shared_modules.gcf_models.gcf_deploy_extended_parameters import GCFDeployCommandParameters
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory


def wait_before_retry(attempt: int) -> int:
    """
    Wait before retrying using a random delay from normal distribution.

    Args:
        attempt: Retry attempt number (0-indexed: 0, 1, 2)

    Returns:
        Wait time in seconds that was actually waited (minimum 20 seconds)
    """
    # Retry delay means: 30s, 90s, 120s for attempts 1, 2, 3
    retry_means = [30, 90, 120]  # seconds
    retry_std_dev = 60  # Standard deviation of 60 seconds
    mean = retry_means[attempt]

    # Redraw if wait time is less than 20 seconds
    while True:
        wait_time = random.normalvariate(mean, retry_std_dev)
        wait_time = max(1, int(wait_time))  # Ensure >= 1s and round to integer
        if wait_time >= 20:
            break

    # Sleep for the calculated wait time
    time.sleep(wait_time)
    return wait_time


class DeployFunctionTask:
    """Task to deploy a single Cloud Function."""

    RETRY_TRIGGERS = [
        '429', 'quota exceeded', 'too many requests',
        '500', '502', '503', '504',
        'operationerror', 'internal', 'server error', 'unavailable',
        'failed to initialize'
    ]

    def __init__(self, logger_factory: LoggerFactory, deployment_timeout_seconds: int = 600):
        self.deployment_timeout_seconds = deployment_timeout_seconds
        self.logger = logger_factory.get_logger(__name__)

    def _execute_gcloud_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Executes the gcloud command."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.deployment_timeout_seconds
        )

    def _should_retry(self, stderr: str) -> bool:
        """Determines if the error warrants a retry."""
        error_msg_lower = stderr.lower()
        return any(trigger in error_msg_lower for trigger in self.RETRY_TRIGGERS)

    def _handle_retry_wait(self, attempt: int, max_retries: int, reason: str):
        """Logs and waits before retry."""
        if attempt < max_retries - 1:
            self.logger.warning(f"Deployment attempt {attempt + 1}/{max_retries} failed. Reason: {reason}. Retrying...")
            wait_time = wait_before_retry(attempt)
            self.logger.info(f"Waited {wait_time} seconds.")
        else:
            self.logger.error(f"Deployment attempt {attempt + 1}/{max_retries} failed. Reason: {reason}. Max retries reached.")

    def _get_function_url(self, ep: GCFDeployCommandParameters) -> Optional[str]:
        """Retrieves the deployed function's URL."""
        try:
            url_result = subprocess.run(
                [
                    'gcloud', 'functions', 'describe', ep.function_name,
                    f'--region={ep.region}',
                    f'--gen2',
                    f'--project={ep.project}',
                    '--format=value(serviceConfig.uri)'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            if url_result.returncode == 0:
                url = url_result.stdout.strip()
                self.logger.info(f"Function URL retrieved: {url}")
                return url
            return None
        except Exception as e:
            self.logger.warning(f"Failed to retrieve function URL: {e}")
            return None

    def deploy_with_extended_gcf_parameters(self, extended_parameters: GCFDeployCommandParameters) -> DeploymentResult:
        """Execute the deployment task with retry logic for rate limiting."""
        ep = extended_parameters
        self.logger.info(f"[{ep.function_name}] Deploying to {ep.region}")

        # Stagger deployments to avoid rate limits
        time.sleep(hash(ep.function_name) % 30)

        max_retries = 3
        
        for attempt in range(max_retries):
            attempt_start_time = time.time()
            try:
                cmd = ep.build_gcloud_command()
                result = self._execute_gcloud_command(cmd)

                if result.returncode != 0:
                    if self._should_retry(result.stderr):
                        clean_error = result.stderr.replace('\n', ' ').strip()[:100]
                        self._handle_retry_wait(attempt, max_retries, clean_error)
                        continue
                    
                    self.logger.error(f"Deployment failed with non-retriable error: {result.stderr[:200]}")
                    return DeploymentFailure(
                        error=result.stderr[:500],
                        used_region=ep.region
                    )

                # Success
                duration_sec = time.time() - attempt_start_time
                duration_ns = int(duration_sec * 1_000_000_000)
                deploy_time = datetime.now(timezone.utc).isoformat()
                
                url = self._get_function_url(ep)
                
                return DeploymentSuccess(
                    url=url,
                    used_region=ep.region,
                    deployment_duration_seconds=duration_sec,
                    deployment_duration_nanoseconds=duration_ns,
                    deploy_time=deploy_time
                )

            except subprocess.TimeoutExpired:
                self._handle_retry_wait(attempt, max_retries, "TimeoutExpired")
                if attempt == max_retries - 1:
                    return DeploymentFailure(
                        error='Deployment timed out after 5 minutes',
                        used_region=ep.region
                    )

            except Exception as e:
                self.logger.error(f"Exception during deployment: {e}")
                self.logger.debug(traceback.format_exc())
                self._handle_retry_wait(attempt, max_retries, str(e))
                if attempt == max_retries - 1:
                     return DeploymentFailure(
                        error=str(e),
                        used_region=ep.region
                    )

        # Should be unreachable if logic is correct, but safe fallback
        return DeploymentFailure(
            error="Max retries exceeded without specific error return",
            used_region=ep.region
        )

    def deploy_gcp_function(
            self,
            # only commonly used parameters listed here, but **kwargs allows passing all possible arguments down the chain
            # the entire (long) list of possible arguments can be found in GCFDeployCommandExtendedParameters
            # p.s the * syntax in next line enforces named parameters only
            *,
            function_name: str,
            region: str,
            runtime: str,
            entry_point: str,
            source_code_dir: Path,

            # commonly used parameters with sane defaults
            memory: str = "512Mi",
            cpu: str = "2",
            concurrency: int = 80,
            max_instances: int = 1,
            min_instances: int = 0,
            timeout: int = 540,
            project: str = "lightrun-temp",
            allow_unauthenticated: bool = True,
            deployment_timeout: int = 600,
            quiet: bool = True,
            gen2: bool = True,
            env_vars: Dict[str, str] = None,
            **kwargs
    ) -> DeploymentResult:

        return self.deploy_with_extended_gcf_parameters(GCFDeployCommandParameters.create(function_name=function_name,
                                                                                          region=region,
                                                                                          runtime=runtime,
                                                                                          entry_point=entry_point,
                                                                                          source_code_dir=source_code_dir,
                                                                                          memory=memory,
                                                                                          cpu=cpu,
                                                                                          concurrency=concurrency,
                                                                                          max_instances=max_instances,
                                                                                          min_instances=min_instances,
                                                                                          timeout=timeout,
                                                                                          project=project,
                                                                                          allow_unauthenticated=allow_unauthenticated,
                                                                                          deployment_timeout=deployment_timeout,
                                                                                          quiet=quiet,
                                                                                          gen2=gen2,
                                                                                          env_vars=env_vars,
                                                                                          **kwargs))