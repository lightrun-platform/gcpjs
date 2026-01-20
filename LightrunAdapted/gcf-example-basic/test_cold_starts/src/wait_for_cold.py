"""Wait for cold start task for Cloud Functions."""

import subprocess
import time
import time
from typing import Optional
import argparse
from .models import GCPFunction


class ColdStartDetectionError(Exception):
    """Raised when we cannot confirm a function is cold within the timeout period."""
    pass


class WaitForColdTask:
    """Task to wait for a single Cloud Function to become cold."""
    
    def __init__(self, function: GCPFunction, config: argparse.Namespace):
        """
        Initialize wait for cold task for a single function.
        
        Args:
            function: GCPFunction object to wait for
            config: Configuration namespace with project settings.
        """
        self.function = function
        self.config = config
    
    def check_function_instances(self) -> int:
        """
        Check the number of active instances for this Cloud Function Gen2.
        Gen2 functions run on Cloud Run, so we check Cloud Run service instances.
        
        Returns:
            Number of active instances (0 if cold)
        """
        try:
            # For Gen2 functions, check Cloud Run service instances
            # Function names are already lowercase (set in DeployTask)
            result = subprocess.run(
                [
                    'gcloud', 'run', 'services', 'describe', self.function.name,
                    f'--region={self.function.region}',
                    f'--project={self.config.project}',
                    '--format=value(status.observedGeneration,status.conditions[0].status)',
                    '--platform=managed'
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # Service might not exist yet or we can't access it
                # Return 1 to indicate uncertainty (might still be warm)
                return 1
            
            # Try to get instance count from Cloud Monitoring using REST API
            import json
            import requests
            from datetime import datetime, timezone, timedelta
            from urllib.parse import quote
            
            # Query Cloud Monitoring API for CURRENT instance count
            # Use a 6-minute time window to get recent data
            # We only care about the CURRENT state, not historical instances
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=6)  # Look back 6 minutes for recent data
            
            # Format times for API
            end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Build filter - function name is already lowercase
            filter_str = (
                f'metric.type="run.googleapis.com/container/instance_count" '
                    f'AND resource.labels.service_name="{self.function.name}" '
                f'AND resource.labels.location="{self.function.region}"'
            )
            
            # Get access token
            token_result = subprocess.run(
                ['gcloud', 'auth', 'print-access-token'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if token_result.returncode != 0:
                # Can't get access token - return uncertainty (1) to keep polling
                return 1
            
            access_token = token_result.stdout.strip()
            filter_encoded = quote(filter_str)
            api_url = (
                f'https://monitoring.googleapis.com/v3/projects/{self.config.project}/'
                f'timeSeries?filter={filter_encoded}&interval.startTime={start_time_str}'
                f'&interval.endTime={end_time_str}'
            )
            
            # Query monitoring API
            try:
                response = requests.get(
                    api_url,
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10
                )
                response.raise_for_status()
                
                data = response.json()
                
                # IMPORTANT: The Monitoring API NEVER reports 0 explicitly.
                # When instances = 0, it returns {"unit": "1"} with NO timeSeries field.
                # When instances > 0, it returns timeSeries with data points.
                # When metrics haven't been collected yet (60-120s delay), it also returns no timeSeries.
                #
                # We CANNOT distinguish between "cold" and "no metrics yet" from a single check.
                # Strategy: If we see timeSeries with data, we know there ARE instances (warm).
                # If we see NO timeSeries, we need to wait longer to ensure metrics would have appeared
                # if instances existed. This is handled by requiring multiple consecutive checks.
                
                if 'timeSeries' not in data or len(data['timeSeries']) == 0:
                    # No timeSeries could mean:
                    # - Function is cold (0 instances) ✓
                    # - Metrics haven't been collected/visible yet (still warm) ✗
                    # Return uncertainty to keep polling - we'll require multiple consecutive "no data"
                    # checks before accepting cold (handled in execute() method)
                    return 1
                
                # We have timeSeries data - check if it's recent enough to trust
                # Cloud Run instance_count metric has states: "active" and "idle"
                # We consider the function warm if ANY instances exist (active or idle)
                total_instances = 0
                has_recent_data = False
                
                for time_series in data['timeSeries']:
                    state = time_series.get('metric', {}).get('labels', {}).get('state', 'unknown')
                    points = time_series.get('points', [])
                    if points:
                        # Get the MOST RECENT data point
                        latest_point = points[-1]
                        
                        # Check if this data point is recent (within last 2 minutes)
                        # Monitoring API can have delays, but we want current state
                        point_time_str = latest_point.get('interval', {}).get('endTime')
                        if point_time_str:
                            try:
                                # Parse the timestamp (format: "2026-01-18T09:00:00Z")
                                point_time = datetime.fromisoformat(point_time_str.replace('Z', '+00:00'))
                                point_age_seconds = (end_time - point_time.replace(tzinfo=timezone.utc)).total_seconds()
                                
                                # Only trust data from the last 6 minutes
                                # If data is older, it's stale and we should return uncertainty
                                if point_age_seconds <= 360:  # 6 minutes
                                    has_recent_data = True
                                    value = latest_point.get('value', {}).get('int64Value')
                                    if value is not None:
                                        count = int(value) if isinstance(value, (int, str)) else 0
                                        total_instances += count
                                        # Log unexpected states for debugging
                                        if state not in ('active', 'idle'):
                                            import logging
                                            logging.warning(
                                                f"Unexpected instance state '{state}' for function {self.function.name}. "
                                                f"Expected 'active' or 'idle'."
                                            )
                            except (ValueError, KeyError):
                                # Can't parse timestamp - assume it's recent and use it
                                has_recent_data = True
                                value = latest_point.get('value', {}).get('int64Value')
                                if value is not None:
                                    count = int(value) if isinstance(value, (int, str)) else 0
                                    total_instances += count
                
                # If we have recent data showing instances, return the count (warm)
                if has_recent_data and total_instances > 0:
                    return total_instances
                
                # If we have timeSeries but no recent data points, or all data is stale,
                # return uncertainty - the instances might have scaled down recently
                # The API never reports 0 in timeSeries - it just omits timeSeries entirely
                return 1
                
            except (requests.RequestException, requests.Timeout, json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
                # If API call fails or data is malformed, return uncertainty (1) to keep polling
                # Don't assume cold - we need actual confirmation
                return 1
            
            # Should never reach here, but if we do, return uncertainty
            return 1
            
        except Exception as e:
            # If we can't check, be conservative and assume it might still be warm
            # Return 1 to continue polling
            return 1
    
    def execute(self, deployment_start_time: float, initial_wait_minutes: int, max_poll_minutes: int = 30) -> float:
        """
        Execute the wait for cold task for this single function.
        
        Args:
            deployment_start_time: Timestamp when deployments started
            initial_wait_minutes: Initial wait period before polling
            max_poll_minutes: Maximum minutes to poll after initial wait
            
        Returns:
            time_to_cold_seconds: Time from deployment start to when function became cold
            
        Raises:
            ColdStartDetectionError: If function cannot be confirmed cold within timeout
        """
        # Initial wait period
        wait_seconds = initial_wait_minutes * 60
        for remaining in range(wait_seconds, 0, -60):
            minutes = remaining // 60
            print(f"[{self.function.index:3d}] Initial wait... {minutes} minutes remaining", end='\r')
            time.sleep(60)
        
        # Poll to confirm function is actually cold
        # The Monitoring API NEVER reports 0 - it just omits timeSeries when cold.
        # We need multiple consecutive "no data" checks over 4 minutes, polling every 15 seconds.
        # This ensures metrics would have appeared if instances existed (accounting for 60-120s delay).
        print(f"[{self.function.index:3d}] Verifying {self.function.name} is cold...")
        
        start_time = time.time()
        max_wait_seconds = max_poll_minutes * 60
        poll_interval = 15  # Check every 15 seconds
        required_cold_duration_seconds = 4 * 60  # Require 4 minutes (240 seconds) of consecutive "no data"
        required_cold_confirmations = required_cold_duration_seconds // poll_interval  # 16 checks
        cold_confirmation_count = 0
        
        while time.time() - start_time < max_wait_seconds:
            count = self.check_function_instances()
            
            # count == 1 means no timeSeries (uncertain - could be cold OR delayed metrics)
            # count > 1 means we have timeSeries showing instances exist (warm)
            # count == 0 shouldn't happen per API behavior, but handle it
            
            if count == 1:
                # No timeSeries data - could be cold OR metrics delayed
                # Increment confirmation counter
                cold_confirmation_count += 1
                elapsed_minutes = int((time.time() - start_time) / 60)
                elapsed_seconds = int(time.time() - start_time)
                
                if cold_confirmation_count >= required_cold_confirmations:
                    # 4 minutes of consecutive "no data" checks
                    # If instances existed, metrics would have appeared by now (60-120s delay)
                    # So this likely means cold
                current_time = time.time()
                time_to_cold = current_time - deployment_start_time
                print(f"[{self.function.index:3d}] ✓ {self.function.name} confirmed cold after {time_to_cold/60:.1f} minutes ({cold_confirmation_count} consecutive 'no data' checks over 4 minutes)")
                
                return time_to_cold
            else:
                    consecutive_duration = cold_confirmation_count * poll_interval
                    print(f"[{self.function.index:3d}] [{elapsed_minutes}m] No instance data: {consecutive_duration}s/{required_cold_duration_seconds}s ({cold_confirmation_count}/{required_cold_confirmations} checks)...", end='\r')
            elif count > 1:
                # We have explicit data showing instances exist - definitely warm
                cold_confirmation_count = 0
                elapsed_minutes = int((time.time() - start_time) / 60)
                print(f"[{self.function.index:3d}] [{elapsed_minutes}m] Still warm (instances: {count})", end='\r')
            else:
                # count == 0 shouldn't happen, but handle it
                cold_confirmation_count = 0
                elapsed_minutes = int((time.time() - start_time) / 60)
                print(f"[{self.function.index:3d}] [{elapsed_minutes}m] Unexpected count={count}, continuing...", end='\r')
            
            time.sleep(poll_interval)
        
        # Timeout - raise error
        elapsed_minutes = int((time.time() - start_time) / 60)
        raise ColdStartDetectionError(
            f"Could not confirm cold state for {self.function.name} after {elapsed_minutes} minutes. "
            f"Monitoring API may be unreliable. Cannot proceed with testing without cold start confirmation."
        )
