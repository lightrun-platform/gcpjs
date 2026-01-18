#!/usr/bin/env python3
"""Check if a Cloud Function is warm or cold."""

import sys
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from wait_for_cold import WaitForColdTask


def main():
    """Check function state."""
    parser = argparse.ArgumentParser(description='Check if a Cloud Function is warm or cold')
    parser.add_argument('--function-name', type=str, required=True, help='Function name')
    parser.add_argument('--region', type=str, required=True, help='GCP region')
    parser.add_argument('--project', type=str, required=True, help='GCP project ID')
    
    args = parser.parse_args()
    
    # Create a config namespace
    config = argparse.Namespace(
        region=args.region,
        project=args.project
    )
    
    # Create WaitForColdTask instance
    task = WaitForColdTask(args.function_name, 1, config)
    
    print(f"Checking function: {args.function_name}")
    print(f"Region: {args.region}")
    print(f"Project: {args.project}")
    print()
    
    # Check instances with detailed diagnostics
    print("Step 1: Checking Cloud Run service...")
    import subprocess
    
    # First check if Cloud Run service exists
    describe_result = subprocess.run(
        [
            'gcloud', 'run', 'services', 'describe', args.function_name,
            f'--region={args.region}',
            f'--project={args.project}',
            '--format=value(status.observedGeneration,status.conditions[0].status)',
            '--platform=managed'
        ],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if describe_result.returncode != 0:
        print(f"  ✗ Cloud Run service check failed (returncode: {describe_result.returncode})")
        print(f"  stderr: {describe_result.stderr[:200]}")
        print()
        print("Status: UNCERTAIN")
        print("Reason: Could not access Cloud Run service. Check:")
        print(f"  - Function name: {args.function_name}")
        print(f"  - Region: {args.region}")
        print(f"  - Project: {args.project}")
        print("  - Your gcloud authentication and permissions")
        return
    
    print(f"  ✓ Cloud Run service exists")
    
    print("\nStep 2: Querying Cloud Monitoring for instance count...")
    
    # Get access token
    token_result = subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if token_result.returncode != 0:
        print(f"  ✗ Could not get access token")
        print()
        print("Status: UNCERTAIN")
        print("Reason: Authentication failed")
        return
    
    access_token = token_result.stdout.strip()
    print("  ✓ Access token obtained")
    
    # Query Monitoring API using requests library
    import json
    import requests
    from datetime import datetime, timezone, timedelta
    from urllib.parse import quote
    
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)
    end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    filter_str = (
        f'metric.type="run.googleapis.com/container/instance_count" '
        f'AND resource.labels.service_name="{args.function_name}" '
        f'AND resource.labels.location="{args.region}"'
    )
    
    filter_encoded = quote(filter_str)
    api_url = (
        f'https://monitoring.googleapis.com/v3/projects/{args.project}/'
        f'timeSeries?filter={filter_encoded}&interval.startTime={start_time_str}'
        f'&interval.endTime={end_time_str}'
    )
    
    try:
        response = requests.get(
            api_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        response.raise_for_status()
        
        if not response.text.strip():
            print("  ℹ No monitoring data available (no recent activity)")
            print()
            print("Status: COLD ✓")
            print("The function has no active or idle instances and is scaled to zero.")
            print("(No monitoring data means no recent requests)")
            return
        
        try:
            data = response.json()
            if 'timeSeries' in data and len(data['timeSeries']) > 0:
                # Sum up all instance counts (active, idle, and any other states)
                # Cloud Run instance_count metric typically has states: "active" and "idle"
                total_instances = 0
                active_count = 0
                idle_count = 0
                other_states = {}
                
                for time_series in data['timeSeries']:
                    state = time_series.get('metric', {}).get('labels', {}).get('state', 'unknown')
                    points = time_series.get('points', [])
                    if points:
                        # Value can be a string or int
                        value = points[-1].get('value', {}).get('int64Value')
                        if value is not None:
                            count = int(value) if isinstance(value, (int, str)) else 0
                            total_instances += count
                            if state == 'active':
                                active_count = count
                            elif state == 'idle':
                                idle_count = count
                            else:
                                # Track any unexpected states
                                other_states[state] = count
                
                print(f"  ✓ Monitoring data retrieved")
                print()
                print(f"Active instances: {active_count}")
                print(f"Idle instances: {idle_count}")
                if other_states:
                    for state, count in other_states.items():
                        print(f"{state.capitalize()} instances: {count} (unexpected state)")
                print(f"Total instances: {total_instances}")
                print()
                
                if total_instances == 0:
                    print("Status: COLD ✓")
                    print("The function has no instances (active or idle) and is scaled to zero.")
                else:
                    other_count = sum(other_states.values()) if other_states else 0
                    print(f"Status: WARM ✓")
                    print(f"The function has {total_instances} instance(s) (active: {active_count}, idle: {idle_count}, other states: {other_count}).")
                return
            
            print("  ℹ No instance count data in monitoring response")
            print()
            print("Status: COLD ✓")
            print("The function has no active or idle instances and is scaled to zero.")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"  ✗ Could not parse monitoring data: {str(e)}")
            print(f"  Response: {response.text[:500]}")
            print()
            print("Status: UNCERTAIN")
            print("Reason: Invalid monitoring data format")
    except requests.RequestException as e:
        print(f"  ✗ Monitoring API query failed")
        print(f"  Error: {str(e)}")
        print()
        print("Status: UNCERTAIN")
        print("Reason: Could not query Cloud Monitoring API")
        return


if __name__ == "__main__":
    main()
