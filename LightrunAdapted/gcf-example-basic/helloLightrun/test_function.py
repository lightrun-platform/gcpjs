#!/usr/bin/env python3
"""
Script to test Cloud Function and generate performance statistics.
Sends 100 requests with 20 second intervals and generates a report.
"""

import requests
import json
import time
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

FUNCTION_URL = "https://europe-west3-lightrun-temp.cloudfunctions.net/helloLightrun"
NUM_REQUESTS = 100
WAIT_SECONDS = 20
RESULTS_FILE = "test_results.json"
REPORT_FILE = "test_report.txt"

def send_request() -> Dict[str, Any]:
    """Send a request to the Cloud Function and return the response."""
    try:
        start_time = time.time()
        response = requests.get(FUNCTION_URL, timeout=60)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            data['_request_latency'] = (end_time - start_time) * 1_000_000_000  # Convert to nanoseconds
            data['_timestamp'] = datetime.utcnow().isoformat()
            return data
        else:
            return {
                'error': True,
                'status_code': response.status_code,
                'message': response.text,
                '_timestamp': datetime.utcnow().isoformat()
            }
    except Exception as e:
        return {
            'error': True,
            'exception': str(e),
            '_timestamp': datetime.utcnow().isoformat()
        }

def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate statistics for a list of values."""
    if not values:
        return {}
    
    return {
        'count': len(values),
        'min': min(values),
        'max': max(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'stdev': statistics.stdev(values) if len(values) > 1 else 0.0
    }

def format_duration(nanoseconds: float) -> str:
    """Format nanoseconds to human-readable duration."""
    ns = int(nanoseconds)
    seconds = ns // 1_000_000_000
    milliseconds = (ns % 1_000_000_000) // 1_000_000
    microseconds = (ns % 1_000_000) // 1_000
    remaining_ns = ns % 1_000
    
    parts = []
    if seconds > 0:
        parts.append(f"{seconds}s")
    if milliseconds > 0:
        parts.append(f"{milliseconds}ms")
    if microseconds > 0:
        parts.append(f"{microseconds}µs")
    if remaining_ns > 0 or not parts:
        parts.append(f"{remaining_ns}ns")
    
    return ", ".join(parts)

def generate_report(results: List[Dict[str, Any]]) -> str:
    """Generate a statistics report from the results."""
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("Cloud Function Performance Test Report")
    report_lines.append("=" * 80)
    report_lines.append(f"Function URL: {FUNCTION_URL}")
    report_lines.append(f"Total Requests: {len(results)}")
    report_lines.append(f"Test Duration: {results[-1]['_timestamp']} to {results[0]['_timestamp']}")
    report_lines.append("")
    
    # Filter out errors
    successful_results = [r for r in results if not r.get('error', False)]
    error_count = len(results) - len(successful_results)
    
    report_lines.append(f"Successful Requests: {len(successful_results)}")
    report_lines.append(f"Failed Requests: {error_count}")
    report_lines.append("")
    
    if not successful_results:
        report_lines.append("No successful requests to analyze.")
        return "\n".join(report_lines)
    
    # Extract metrics
    metrics = {
        'isColdStart': [1 if r.get('isColdStart') else 0 for r in successful_results],
        'totalDuration': [float(r.get('totalDuration', 0)) for r in successful_results],
        'totalImportsDuration': [float(r.get('totalImportsDuration', 0)) for r in successful_results],
        'lightrunImportDuration': [float(r.get('lightrunImportDuration', 0)) for r in successful_results],
        'gcfImportDuration': [float(r.get('gcfImportDuration', 0)) for r in successful_results],
        'envCheckDuration': [float(r.get('envCheckDuration', 0)) for r in successful_results],
        'lightrunInitDuration': [float(r.get('lightrunInitDuration', 0)) for r in successful_results],
        'totalSetupDuration': [float(r.get('totalSetupDuration', 0)) for r in successful_results],
        'functionInvocationOverhead': [float(r.get('functionInvocationOverhead', 0)) for r in successful_results],
        'requestLatency': [r.get('_request_latency', 0) for r in successful_results]
    }
    
    # Calculate statistics for each metric
    report_lines.append("METRICS STATISTICS")
    report_lines.append("-" * 80)
    
    for metric_name, values in metrics.items():
        if not values or all(v == 0 for v in values):
            continue
            
        stats = calculate_stats(values)
        report_lines.append(f"\n{metric_name}:")
        report_lines.append(f"  Count: {stats['count']}")
        report_lines.append(f"  Min:   {format_duration(stats['min'])}")
        report_lines.append(f"  Max:   {format_duration(stats['max'])}")
        report_lines.append(f"  Mean:  {format_duration(stats['mean'])}")
        report_lines.append(f"  Median: {format_duration(stats['median'])}")
        report_lines.append(f"  StdDev: {format_duration(stats['stdev'])}")
    
    # Cold start analysis
    cold_starts = sum(metrics['isColdStart'])
    warm_starts = len(successful_results) - cold_starts
    report_lines.append("\n" + "-" * 80)
    report_lines.append("COLD START ANALYSIS")
    report_lines.append("-" * 80)
    report_lines.append(f"Cold Starts: {cold_starts} ({cold_starts/len(successful_results)*100:.1f}%)")
    report_lines.append(f"Warm Starts: {warm_starts} ({warm_starts/len(successful_results)*100:.1f}%)")
    
    # Compare cold vs warm start performance
    if cold_starts > 0 and warm_starts > 0:
        cold_durations = [float(r.get('totalDuration', 0)) for r in successful_results if r.get('isColdStart')]
        warm_durations = [float(r.get('totalDuration', 0)) for r in successful_results if not r.get('isColdStart')]
        
        if cold_durations and warm_durations:
            cold_stats = calculate_stats(cold_durations)
            warm_stats = calculate_stats(warm_durations)
            
            report_lines.append("\nCold Start Performance:")
            report_lines.append(f"  Mean Duration: {format_duration(cold_stats['mean'])}")
            report_lines.append(f"  Median Duration: {format_duration(cold_stats['median'])}")
            
            report_lines.append("\nWarm Start Performance:")
            report_lines.append(f"  Mean Duration: {format_duration(warm_stats['mean'])}")
            report_lines.append(f"  Median Duration: {format_duration(warm_stats['median'])}")
            
            overhead = cold_stats['mean'] - warm_stats['mean']
            report_lines.append(f"\nCold Start Overhead: {format_duration(overhead)}")
    
    report_lines.append("\n" + "=" * 80)
    
    return "\n".join(report_lines)

def main():
    """Main test execution."""
    print(f"Starting performance test...")
    print(f"Function URL: {FUNCTION_URL}")
    print(f"Requests: {NUM_REQUESTS}")
    print(f"Wait between requests: {WAIT_SECONDS} seconds")
    print(f"Results will be saved to: {RESULTS_FILE}")
    print(f"Report will be saved to: {REPORT_FILE}")
    print()
    
    results = []
    
    for i in range(1, NUM_REQUESTS + 1):
        print(f"[{i}/{NUM_REQUESTS}] Sending request...", end=" ", flush=True)
        result = send_request()
        results.append(result)
        
        if result.get('error'):
            print(f"ERROR: {result.get('exception', result.get('status_code', 'Unknown'))}")
        else:
            is_cold = result.get('isColdStart', False)
            total_duration = float(result.get('totalDuration', 0)) / 1_000_000_000  # Convert to seconds
            print(f"OK - Cold Start: {is_cold}, Duration: {total_duration:.3f}s")
        
        # Save results after each request
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Wait before next request (except after last request)
        if i < NUM_REQUESTS:
            print(f"Waiting {WAIT_SECONDS} seconds...")
            time.sleep(WAIT_SECONDS)
    
    print("\n" + "=" * 80)
    print("Test completed! Generating report...")
    print("=" * 80)
    
    # Generate and save report
    report = generate_report(results)
    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    
    print(report)
    print(f"\nReport saved to: {REPORT_FILE}")
    print(f"Raw results saved to: {RESULTS_FILE}")

if __name__ == "__main__":
    main()
