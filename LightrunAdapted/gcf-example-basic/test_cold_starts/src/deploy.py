"""Deploy task for Cloud Functions."""

import subprocess
import time
import random
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import argparse


class DeployTask:
    """Task to deploy a single Cloud Function."""
    
    def __init__(self, function_index: int, lightrun_secret: str, config: argparse.Namespace, function_dir: Path):
        """
        Initialize deploy task.
        
        Args:
            function_index: Index of the function (1-based)
            lightrun_secret: Lightrun secret for environment variable
            config: Configuration namespace with deployment settings
            function_dir: Directory containing the function source code
        """
        self.function_index = function_index
        self.lightrun_secret = lightrun_secret
        self.config = config
        self.function_dir = function_dir
        # Cloud Run service names must be lowercase, so use lowercase function names
        self.function_name = f"{config.base_function_name}-{function_index:03d}".lower()
        self.display_name = f"{config.base_function_name}-gcf-performance-test-{function_index:03d}"
    
    def wait_before_retry(self, attempt: int) -> int:
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
    
    def execute(self) -> Dict[str, Any]:
        """Execute the deployment task with retry logic for rate limiting."""
        env_vars = f"LIGHTRUN_SECRET={self.lightrun_secret},DISPLAY_NAME={self.display_name}"
        
        print(f"[{self.function_index:3d}] Deploying {self.function_name}...", end=" ", flush=True)
        
        # Add small delay to avoid hitting rate limits (stagger deployments)
        # Delay based on function index to spread out requests
        time.sleep(self.function_index * 0.5)  # 0.5s delay per function index
        
        max_retries = 3
        
        for attempt in range(max_retries):
            # Track start time for this specific attempt
            attempt_start_time = time.time()
            
            try:
                # Deploy using gcloud
                result = subprocess.run(
                    [
                        'gcloud', 'functions', 'deploy', self.function_name,
                        '--gen2',
                        f'--runtime={self.config.runtime}',
                        f'--region={self.config.region}',
                        f'--source={self.function_dir}',
                        f'--entry-point={self.config.entry_point}',
                        '--trigger-http',
                        '--allow-unauthenticated',
                        f'--set-env-vars={env_vars}',
                        '--min-instances=0',
                        '--max-instances=5',
                        '--timeout=540',
                        '--concurrency=80',
                        '--memory=512Mi',
                        '--cpu=2',
                        f'--project={self.config.project}',
                        '--quiet'
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per deployment
                )
                
                if result.returncode != 0:
                    # Check if it's a rate limit error (429)
                    if '429' in result.stderr or 'Quota exceeded' in result.stderr:
                        if attempt < max_retries - 1:
                            retry_means = [30, 90, 120]
                            print(f"RATE LIMITED, retrying in ...", end=" ", flush=True)
                            wait_time = self.wait_before_retry(attempt)
                            print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                            continue
                    
                    print(f"FAILED: {result.stderr[:100]}")
                    return {
                        'function_index': self.function_index,
                        'function_name': self.function_name,
                        'deployed': False,
                        'error': result.stderr[:500],
                        'url': None
                    }
                
                # Success - record duration of this successful attempt only
                attempt_end_time = time.time()
                deployment_duration = attempt_end_time - attempt_start_time
                break
                
            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"TIMEOUT, retrying in ...", end=" ", flush=True)
                    wait_time = self.wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print("TIMEOUT")
                return {
                    'function_index': self.function_index,
                    'function_name': self.function_name,
                    'deployed': False,
                    'error': 'Deployment timed out after 5 minutes',
                    'url': None
                }
            except Exception as e:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"ERROR, retrying in ...", end=" ", flush=True)
                    wait_time = self.wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print(f"EXCEPTION: {str(e)}")
                return {
                    'function_index': self.function_index,
                    'function_name': self.function_name,
                    'deployed': False,
                    'error': str(e),
                    'url': None
                }
        
        # Get the function URL (only if deployment succeeded)
        try:
            url_result = subprocess.run(
                [
                    'gcloud', 'functions', 'describe', self.function_name,
                    f'--region={self.config.region}',
                    f'--gen2',
                    f'--project={self.config.project}',
                    '--format=value(serviceConfig.uri)'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            url = url_result.stdout.strip() if url_result.returncode == 0 else None
            
            # deployment_duration was already calculated above for the successful attempt only
            print(f"OK - URL: {url[:50]}..." if url else "OK (no URL)")
            
            return {
                'function_index': self.function_index,
                'function_name': self.function_name,
                'display_name': self.display_name,
                'deployed': True,
                'url': url,
                'deploy_time': datetime.now(timezone.utc).isoformat(),
                'deployment_duration_seconds': deployment_duration,
                'deployment_duration_nanoseconds': int(deployment_duration * 1_000_000_000)
            }
        except Exception as e:
            print(f"ERROR getting URL: {str(e)[:50]}")
            return {
                'function_index': self.function_index,
                'function_name': self.function_name,
                'deployed': False,
                'error': f'Failed to get URL: {str(e)}',
                'url': None
            }
