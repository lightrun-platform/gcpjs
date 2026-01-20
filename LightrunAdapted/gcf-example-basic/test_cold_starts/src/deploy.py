"""Deploy task for Cloud Functions."""

import subprocess
import time
import random
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import argparse
from .models import GCPFunction


class DeployTask:
    """Task to deploy a single Cloud Function."""
    
    def __init__(self, function: GCPFunction, lightrun_secret: str, config: argparse.Namespace, function_dir: Path):
        """
        Initialize deploy task.
        
        Args:
            function: GCPFunction object containing deployment details
            lightrun_secret: Lightrun secret for environment variable
            config: Configuration namespace with deployment settings
            function_dir: Directory containing the function source code
        """
        self.function = function
        self.lightrun_secret = lightrun_secret
        self.config = config
        self.function_dir = function_dir
        # Ensure names are set
        if not self.function.name:
             self.function.set_names(config.base_function_name)
    
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
    
    def execute(self) -> GCPFunction:
        """Execute the deployment task with retry logic for rate limiting."""
        env_vars = f"LIGHTRUN_SECRET={self.lightrun_secret},DISPLAY_NAME={self.function.display_name}"
        
        print(f"[{self.function.index:3d}] Deploying {self.function.name} to {self.function.region}...", end=" ", flush=True)
        
        # Add small delay to avoid hitting rate limits (stagger deployments)
        # Delay based on function index to spread out requests
        time.sleep(self.function.index * 0.5)  # 0.5s delay per function index
        
        max_retries = 3
        
        for attempt in range(max_retries):
            # Track start time for this specific attempt
            attempt_start_time = time.time()
        
        try:
            # Deploy using gcloud
            result = subprocess.run(
                [
                    'gcloud', 'functions', 'deploy', self.function.name,
                    '--gen2',
                    f'--runtime={self.config.runtime}',
                    f'--region={self.function.region}',
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
                # Check for rate limits and transient server errors
                error_msg = result.stderr
                retry_triggers = [
                    '429', 'Quota exceeded', 'Too Many Requests',
                    '500', '502', '503', '504', 
                    'OperationError', 'Internal', 'server error', 'unavailable'
                ]
                
                if any(trigger in error_msg for trigger in retry_triggers):
                    if attempt < max_retries - 1:
                        retry_means = [30, 90, 120]
                        print(f"TRANSIENT ERROR ({error_msg[:50]}...), retrying in ...", end=" ", flush=True)
                        wait_time = self.wait_before_retry(attempt)
                        print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                        continue
                
                print(f"FAILED: {result.stderr[:100]}")
                self.function.deployed = False
                self.function.error = result.stderr[:500]
                return self.function
            
                # Success - record duration of this successful attempt only
                attempt_end_time = time.time()
                deployment_duration = attempt_end_time - attempt_start_time
                self.function.details['deployment_duration_seconds'] = deployment_duration
                self.function.details['deployment_duration_nanoseconds'] = int(deployment_duration * 1_000_000_000)
                break
                
            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"TIMEOUT, retrying in ...", end=" ", flush=True)
                    wait_time = self.wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print("TIMEOUT")
                self.function.deployed = False
                self.function.error = 'Deployment timed out after 5 minutes'
                return self.function
            except Exception as e:
                if attempt < max_retries - 1:
                    retry_means = [30, 90, 120]
                    print(f"ERROR, retrying in ...", end=" ", flush=True)
                    wait_time = self.wait_before_retry(attempt)
                    print(f"{wait_time}s (mean={retry_means[attempt]}s)...", end=" ", flush=True)
                    continue
                print(f"EXCEPTION: {str(e)}")
                self.function.deployed = False
                self.function.error = str(e)
                return self.function
        
        # Get the function URL (only if deployment succeeded)
        try:
            url_result = subprocess.run(
                [
                    'gcloud', 'functions', 'describe', self.function.name,
                    f'--region={self.function.region}',
                    f'--gen2',
                    f'--project={self.config.project}',
                    '--format=value(serviceConfig.uri)'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            url = url_result.stdout.strip() if url_result.returncode == 0 else None
            
            print(f"OK - URL: {url[:50]}..." if url else "OK (no URL)")
            
            self.function.deployed = True
            self.function.url = url
            self.function.details['deploy_time'] = datetime.now(timezone.utc).isoformat()
            
            return self.function
            
        except Exception as e:
            print(f"ERROR getting URL: {str(e)[:50]}")
            self.function.deployed = False
            self.function.error = f'Failed to get URL: {str(e)}'
            return self.function
