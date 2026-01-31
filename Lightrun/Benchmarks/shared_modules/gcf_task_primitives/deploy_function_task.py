"""Deploy task for Cloud Functions."""

import subprocess
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List

from Lightrun.Benchmarks.shared_modules.gcf_models.deployment_result import DeploymentResult
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



class DeployFunctionTask:
    """Task to deploy a single Cloud Function."""


    def __init__(self, deployment_timeout_seconds: int = 600):
        self.deployment_timeout_seconds = deployment_timeout_seconds

    def deploy_with_extended_gcf_parameters(self, extended_parameters: GCFDeployCommandParameters) -> DeploymentResult:
        """Execute the deployment task with retry logic for rate limiting.

        Returns:
            DeploymentResult: Immutable result of the deployment
        """

        ep = extended_parameters
        # env_vars = f"LIGHTRUN_SECRET={self.lightrun_secret},DISPLAY_NAME={self.display_name}"
        print(f"[{ep.function_name}] Deploying {ep.function_name} to {ep.region}...", end=" ", flush=True)

        # Add small delay to avoid hitting rate limits (stagger deployments)
        # Delay based on function index to spread out requests
        time.sleep(hash(ep.function_name) % 30)  # spreading out function deployments to avoid rate limits

        max_retries = 3
        deployment_duration_seconds = None
        deployment_duration_nanoseconds = None
        deploy_time = None

        for attempt in range(max_retries):
            # Track start time for this specific attempt
            attempt_start_time = time.time()

            try:
                # Build gcloud command with all parameters
                cmd = ep.build_gcloud_command()
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.deployment_timeout_seconds
                )

                if result.returncode != 0:
                    # Check for rate limits and transient server errors
                    error_msg_lower = result.stderr.lower()
                    retry_triggers = [
                        '429', 'quota exceeded', 'too many requests',
                        '500', '502', '503', '504',
                        'operationerror', 'internal', 'server error', 'unavailable',
                        'failed to initialize'
                    ]

                    if any(trigger in error_msg_lower for trigger in retry_triggers):
                        if attempt < max_retries - 1:
                            retry_means = [30, 90, 120]
                            # Clean up error message for inline printing
                            clean_error = result.stderr.replace('\n', ' ').replace('\r', '').strip()[:50]
                            print(f"TRANSIENT ERROR ({clean_error}...), retrying in ...", end=" ", flush=True)
                            wait_time = wait_before_retry(attempt)
                            print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                            continue

                    print(f"FAILED: {result.stderr[:100]}")
                    return DeploymentResult(
                        success=False,
                        error=result.stderr[:500],
                        used_region=ep.region
                    )

                # Success - record duration of this successful attempt only
                attempt_end_time = time.time()
                deployment_duration_seconds = attempt_end_time - attempt_start_time
                deployment_duration_nanoseconds = int(deployment_duration_seconds * 1_000_000_000)
                deploy_time = datetime.now(timezone.utc).isoformat()
                break

            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"TIMEOUT, retrying in ...", end=" ", flush=True)
                    wait_time = wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print("TIMEOUT")
                return DeploymentResult(
                    success=False,
                    error='Deployment timed out after 5 minutes',
                    used_region=ep.region
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"ERROR, retrying in ...", end=" ", flush=True)
                    wait_time = wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print(f"EXCEPTION: {str(e)}")
                return DeploymentResult(
                    success=False,
                    error=str(e),
                    used_region=ep.region
                )

        # Get the function URL (only if deployment succeeded)
        try:
            url_result = subprocess.run(
                [
                    'gcloud', 'functions', 'describe', ep.function_name,
                    f'--region={ep.region}',
                    f'--gen2',
                    f'--project={ep.params.project}',
                    '--format=value(serviceConfig.uri)'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            url = url_result.stdout.strip() if url_result.returncode == 0 else None

            print(f"OK - URL: {url[:50]}..." if url else "OK (no URL)")

            return DeploymentResult(
                success=True,
                url=url,
                used_region=ep.region,
                deployment_duration_seconds=deployment_duration_seconds,
                deployment_duration_nanoseconds=deployment_duration_nanoseconds,
                deploy_time=deploy_time
            )

        except Exception as e:
            print(f"ERROR getting URL: {str(e)[:50]}")
            return DeploymentResult(
                success=False,
                error=f'Failed to get URL: {str(e)}',
                used_region=ep.region
            )

    def deploy_gcp_function(
            # only commonly used parameters, the entire list can be found in GCFDeployCommandExtendedParameters
            self,
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
            deployment_timeout: int = 600,  # 10 minutes
            quiet: bool = True,
            gen2: bool = True,
            env_vars: Dict[str, str] = None,
            **kwargs
    ) -> DeploymentResult:

        return self.deploy_with_extended_gcf_parameters(GCFDeployCommandParameters.create(function_name,
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
                                                                                          **kwargs))