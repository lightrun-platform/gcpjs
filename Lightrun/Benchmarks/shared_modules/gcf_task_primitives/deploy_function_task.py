"""Deploy task for Cloud Functions."""
import logging
import subprocess
import time
import random
import traceback
from datetime import datetime, timezone
from typing import List, Optional

from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.deploy_function_result import DeploymentResult, DeploymentSuccess, DeploymentFailure
from Lightrun.Benchmarks.shared_modules.gcf_models.gcf_deploy_extended_parameters import GCFDeployCommandParameters


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

def _execute_gcloud_command(cmd: List[str], deployment_timeout_seconds: int) -> subprocess.CompletedProcess:
    """Executes the gcloud command."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=deployment_timeout_seconds
    )

def _should_retry(retry_triggers, stderr: str) -> bool:
    """Determines if the error warrants a retry."""
    error_msg_lower = stderr.lower()
    return any(trigger in error_msg_lower for trigger in retry_triggers)

def _handle_retry_wait(attempt: int, max_retries: int, reason: str, logger: logging.Logger) -> None:
    """Logs and waits before retry."""
    if attempt < max_retries - 1:
        logger.warning(f"Deployment attempt {attempt + 1}/{max_retries} failed. Reason: {reason}. Retrying...")
        wait_time = wait_before_retry(attempt)
        logger.info(f"Waited {wait_time} seconds.")
    else:
        logger.error(f"Deployment attempt {attempt + 1}/{max_retries} failed. Reason: {reason}. Max retries reached.")

def _get_function_url(ep: GCFDeployCommandParameters, logger: logging.Logger) -> Optional[str]:
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
            logger.info(f"Function URL retrieved: {url}")
            return url
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve function URL: {e}")
        return None

def deploy_with_extended_gcf_parameters(extended_parameters: GCFDeployCommandParameters, deployment_timeout_seconds: int, retry_triggers: List[str], logger: logging.Logger) -> DeploymentResult:
    """Execute the deployment task with retry logic for rate limiting."""
    ep = extended_parameters
    logger.info(f"[{ep.function_name}] Deploying to {ep.region}")

    # Stagger deployments to avoid rate limits
    time.sleep(hash(ep.function_name) % 30)

    max_retries = 3

    for attempt in range(max_retries):
        attempt_start_time = time.time()
        try:
            cmd = ep.build_gcloud_command()
            result = _execute_gcloud_command(cmd, deployment_timeout_seconds)

            if result.returncode != 0:
                if _should_retry(retry_triggers, result.stderr):
                    clean_error = result.stderr.replace('\n', ' ').strip()
                    _handle_retry_wait(attempt, max_retries, clean_error, logger)
                    continue

                logger.error(f"Deployment failed with non-retriable error: {result.stderr}")
                return DeploymentFailure(error=result.stderr, used_region=ep.region)

            # Success
            duration_sec = time.time() - attempt_start_time
            duration_ns = int(duration_sec * 1_000_000_000)
            deploy_time = datetime.now(timezone.utc).isoformat()

            url = _get_function_url(ep, logger)

            return DeploymentSuccess(
                url=url,
                used_region=ep.region,
                deployment_duration_seconds=duration_sec,
                deployment_duration_nanoseconds=duration_ns,
                deploy_time=deploy_time
            )

        except subprocess.TimeoutExpired:
            _handle_retry_wait(attempt, max_retries, "TimeoutExpired", logger)
            if attempt == max_retries - 1:
                return DeploymentFailure(
                    error='Deployment timed out after 5 minutes',
                    used_region=ep.region
                )

        except Exception as e:
            logger.error(f"Exception during deployment: {e}")
            logger.debug(traceback.format_exc())
            _handle_retry_wait(attempt, max_retries, str(e), logger)
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


class DeployFunctionTask:
    """Task to deploy a single Cloud Function."""

    RETRY_TRIGGERS = [
        '429', 'quota exceeded', 'too many requests',
        '500', '502', '503', '504',
        'operationerror', 'internal', 'server error', 'unavailable',
        'failed to initialize'
    ]

    def __init__(self, function: GCPFunction, deployment_timeout_seconds: int = 600):
        self.deployment_timeout_seconds = deployment_timeout_seconds
        self.f = function
        self.logger = function.logger

    def deploy(self) -> DeploymentResult:
        command_parameters = GCFDeployCommandParameters.create(function_name=self.f.name,
                                                               region=self.f.region,
                                                               runtime=self.f.runtime,
                                                               entry_point=self.f.entry_point,
                                                               source_code_dir=self.f.function_source_code_dir,
                                                               memory=self.f.memory,
                                                               cpu=self.f.cpu,
                                                               concurrency=self.f.concurrency,
                                                               max_instances=self.f.max_instances,
                                                               min_instances=self.f.min_instances,
                                                               timeout=self.f.timeout,
                                                               project=self.f.project,
                                                               allow_unauthenticated=self.f.allow_unauthenticated,
                                                               deployment_timeout=self.deployment_timeout_seconds,
                                                               quiet=self.f.quiet,
                                                               gen2=self.f.gen2,
                                                               env_vars=self.f.env_vars,
                                                               **self.f.kwargs)

        return deploy_with_extended_gcf_parameters(command_parameters, self.deployment_timeout_seconds, DeployFunctionTask.RETRY_TRIGGERS, self.logger)