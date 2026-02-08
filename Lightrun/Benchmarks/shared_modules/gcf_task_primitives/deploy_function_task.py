"""Deploy task for Cloud Functions."""
import logging
import subprocess
import time
import random
import traceback
from abc import ABC
from datetime import datetime, timezone
from typing import List, Optional, Dict

from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.gcf_models.deploy_function_result import DeploymentResult, DeploymentSuccess, DeploymentFailure
from Lightrun.Benchmarks.shared_modules.gcf_models.gcf_deploy_extended_parameters import GCFDeployCommandParameters
from typing import Optional


class LabelClashException(Exception):
    pass


class CpuModelMismatchException(Exception):
    """Raised when the deployed function landed on wrong CPU hardware."""
    def __init__(self, required_model: str, actual_model: str):
        self.required_model = required_model
        self.actual_model = actual_model
        super().__init__(f"CPU model mismatch: required '{required_model}' but got '{actual_model}'")


# Maximum number of redeploy attempts when CPU pinning is enabled
MAX_CPU_PINNING_ATTEMPTS = 10


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
        logger.warning(f"Deployment attempt {attempt + 1}/{max_retries} failed. Reason: {reason}. Retrying.")
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


def _verify_cpu_model(url: str, required_cpu_model: str, logger: logging.Logger) -> None:
    """
    Verify the deployed function is running on the required CPU model.
    
    Sends a probe request to the function. If REQUIRED_CPU_MODEL env var is set
    in the function, it will throw CPU_MODEL_MISMATCH at module load time if
    the actual CPU doesn't match.
    
    Args:
        url: Function URL to probe
        required_cpu_model: The expected CPU model name
        logger: Logger instance
        
    Raises:
        CpuModelMismatchException: If CPU model doesn't match
    """
    import re
    import requests
    
    logger.info(f"Verifying CPU model (expecting: {required_cpu_model})...")
    
    try:
        response = requests.get(url, timeout=60)
        
        # Check for CPU mismatch in error response
        # The JS code throws at module load time, resulting in a 500 error
        if response.status_code != 200:
            error_text = response.text
            if 'CPU_MODEL_MISMATCH' in error_text:
                # Parse: CPU_MODEL_MISMATCH: Required "X" but got "Y"
                match = re.search(r'Required "([^"]+)" but got "([^"]+)"', error_text)
                if match:
                    required = match.group(1)
                    actual = match.group(2)
                    raise CpuModelMismatchException(required, actual)
                else:
                    raise CpuModelMismatchException(required_cpu_model, "unknown")
        
        logger.info(f"CPU model verified: {required_cpu_model}")
        
    except CpuModelMismatchException:
        raise
    except Exception as e:
        # If we can't probe, log warning but don't fail deployment
        logger.warning(f"Could not verify CPU model: {e}")


def deploy_with_extended_gcf_parameters(extended_parameters: GCFDeployCommandParameters, deployment_timeout_seconds: int, retry_triggers: List[str], logger: logging.Logger, function_model: Optional[GCPFunction] = None, required_cpu_model: Optional[str] = None) -> DeploymentResult:
    """
    Execute the deployment task with retry logic for rate limiting.
    
    If required_cpu_model is set, after successful deployment we verify the function
    landed on the correct CPU hardware. If not, we redeploy (up to MAX_CPU_PINNING_ATTEMPTS
    times) until we get the requested hardware. Each redeploy overwrites the previous
    deployment, so no explicit deletion is needed.
    """
    ep = extended_parameters

    # CPU pinning: outer loop for CPU mismatch retries
    cpu_pinning_enabled = required_cpu_model is not None
    max_cpu_attempts = MAX_CPU_PINNING_ATTEMPTS if cpu_pinning_enabled else 1
    
    if cpu_pinning_enabled:
        logger.info(f"[{ep.function_name}] CPU pinning enabled: requiring '{required_cpu_model}'")
    
    for cpu_attempt in range(max_cpu_attempts):
        if cpu_pinning_enabled and cpu_attempt > 0:
            logger.info(f"[{ep.function_name}] CPU pinning attempt {cpu_attempt + 1}/{max_cpu_attempts}")
        
        logger.info(f"[{ep.function_name}] Deploying to {ep.region}")

        # Stagger deployments to avoid rate limits (only on first CPU attempt)
        if cpu_attempt == 0:
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
                    
                    # Attempt to find partial assets even on failure
                    partial_assets = []
                    if function_model:
                        partial_assets = function_model.discover_associated_assets()
                    
                    return DeploymentFailure(error=result.stderr, used_region=ep.region, partial_assets=partial_assets)

                # Deployment succeeded
                duration_sec = time.time() - attempt_start_time
                duration_ns = int(duration_sec * 1_000_000_000)
                deploy_time = datetime.now(timezone.utc).isoformat()

                url = _get_function_url(ep, logger)
                
                # CPU pinning verification
                if cpu_pinning_enabled and url:
                    try:
                        _verify_cpu_model(url, required_cpu_model, logger)
                    except CpuModelMismatchException as e:
                        logger.warning(f"CPU mismatch on attempt {cpu_attempt + 1}: got '{e.actual_model}', need '{e.required_model}'")
                        if cpu_attempt < max_cpu_attempts - 1:
                            # Small delay before redeploy
                            time.sleep(5)
                            break  # Break inner retry loop to trigger outer CPU pinning retry
                        else:
                            logger.error(f"Max CPU pinning attempts ({max_cpu_attempts}) reached without finding correct CPU")
                            return DeploymentFailure(
                                error=f"CPU pinning failed: required '{required_cpu_model}' but got '{e.actual_model}' after {max_cpu_attempts} attempts",
                                used_region=ep.region,
                                partial_assets=[]
                            )
                
                # Discover and label assets
                assets = []
                if function_model:
                    assets = function_model.discover_associated_assets()
                    if ep.update_labels:
                         for asset in assets:
                             asset.apply_labels(ep.update_labels, logger)

                return DeploymentSuccess(
                    url=url,
                    used_region=ep.region,
                    deployment_duration_seconds=duration_sec,
                    deployment_duration_nanoseconds=duration_ns,
                    deploy_time=deploy_time,
                    assets=assets
                )

            except subprocess.TimeoutExpired:
                _handle_retry_wait(attempt, max_retries, "TimeoutExpired", logger)
                if attempt == max_retries - 1:
                    partial_assets = []
                    if function_model:
                        partial_assets = function_model.discover_associated_assets()
                    return DeploymentFailure(
                        error='Deployment timed out after 5 minutes',
                        used_region=ep.region,
                        partial_assets=partial_assets
                    )

            except Exception as e:
                logger.exception(f"Encountered an exception during deployment: {e}")
                _handle_retry_wait(attempt, max_retries, str(e), logger)
                if attempt == max_retries - 1:
                    partial_assets = []
                    if function_model:
                        partial_assets = function_model.discover_associated_assets()
                    return DeploymentFailure(
                        error=str(e),
                        used_region=ep.region,
                        partial_assets=partial_assets
                    )
        else:
            # Inner loop completed without break (no CPU mismatch), so we're done
            # This should only be reached if all retries failed
            continue
        
        # Inner loop was broken (CPU mismatch), continue outer loop
        continue

    # Should be unreachable if logic is correct, but safe fallback
    partial_assets = []
    if function_model:
        partial_assets = function_model.discover_associated_assets()
    return DeploymentFailure(
        error="Max retries exceeded without specific error return",
        used_region=ep.region,
         partial_assets=partial_assets
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
        kwargs = self.f.kwargs if self.f.kwargs is not None else {}

        kwargs_build_labels = kwargs.get('update_build_env_vars', {})

        common_keys = kwargs_build_labels.keys() & self.f.labels.keys()
        for key in common_keys:
            kw_value = kwargs_build_labels[key]
            function_label_value = self.f.labels[key]
            if kw_value != function_label_value:
                raise LabelClashException(f"Label clash: key: '{key}' exists in the function's labels list with value: '{function_label_value}', but was also sent via the keyword argument 'update_build_env_vars' with value: '{kw_value}'")

        all_labels = {**kwargs_build_labels, **self.f.labels}
        combined_labels_str = " ".join([f"{k}={v}" for k, v in all_labels.items()])

        update_build_env_vars = kwargs.get('update_build_env_vars', {}).copy()
        update_build_env_vars['BP_IMAGE_LABELS'] = combined_labels_str
        
        # Prepare arguments, overriding update_build_env_vars from kwargs if we modified it
        create_kwargs = kwargs.copy()
        if update_build_env_vars:
            create_kwargs['update_build_env_vars'] = update_build_env_vars
        
        # Explicitly set docker repository to avoid gcloud crash (AttributeError: 'NoneType' object has no attribute 'service')
        if 'docker_repository' not in create_kwargs:
            create_kwargs['docker_repository'] = f'projects/{self.f.project}/locations/{self.f.region}/repositories/gcf-artifacts'

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
                                                               update_labels=self.f.labels,
                                                               **create_kwargs)

        return deploy_with_extended_gcf_parameters(command_parameters, self.deployment_timeout_seconds, DeployFunctionTask.RETRY_TRIGGERS, self.logger, function_model=self.f, required_cpu_model=self.f.required_cpu_model)