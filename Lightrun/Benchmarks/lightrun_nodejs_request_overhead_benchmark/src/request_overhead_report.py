"""Report generator for Request Overhead Benchmark."""

import statistics
from typing import Dict, Any, List
from pathlib import Path
import numpy as np

# We can reuse generic formatting functions if we extract them, but for now duplicate/adapt
# to avoid breaking changes in the other file if we modify it.
# Actually, report.py was deleted? No, `cold_start_benchmark_report.py` exists.
# I will define local helpers.

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
    return f"{milliseconds}ms {microseconds}µs"

class RequestOverheadReportGenerator:
    """Generates reports for request overhead tests."""
    
    def __init__(self, with_lightrun_results: Dict[str, Any], without_lightrun_results: Dict[str, Any]):
        self.with_lightrun = with_lightrun_results
        self.without_lightrun = without_lightrun_results
        self.output_dir = Path('.')
    
    def set_output_dir(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _extract_metrics(self, results: Dict[str, Any]) -> Dict[str, List[float]]:
        test_results = results.get('test_results', [])
        successful_results = [r for r in test_results if not r.get('error', False)]
        
        if not successful_results:
            return {}
            
        # We need "totalDurationForWarmRequests" averaged per request? 
        # Or better: construct a list of ALL individual request latencies?
        # SendRequestTask returns `_all_request_results`.
        
        all_request_latencies = []
        all_handler_runtimes = []
        
        for res in successful_results:
            request_list = res.get('_all_request_results', [])
            for req in request_list:
                # Skip the first request (warmup/cold) if we want pure warm overhead?
                # Benchmark says "send 1 request... then actions... then loop num-requests".
                # SendRequestTask sends num-requests.
                # If we want to measure overhead, we typically look at warm requests.
                # SendRequestTask splits cold/warm in `totalDurationForWarmRequests`.
                # Let's extract all latencies.
                if not req.get('error'):
                    if '_request_latency' in req:
                        all_request_latencies.append(req['_request_latency'])
                    if 'handlerRunTime' in req:
                        # handlerRunTime is in nanoseconds string from JS
                        try:
                            all_handler_runtimes.append(float(req['handlerRunTime']))
                        except:
                            pass
                            
        return {
            'requestLatency': all_request_latencies,
            'handlerRunTime': all_handler_runtimes
        }

    def generate_report(self, filename: str = 'overhead_report.txt'):
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("Lightrun Request Overhead Benchmark Report")
        report_lines.append("=" * 80)
        
        with_metrics = self._extract_metrics(self.with_lightrun)
        without_metrics = self._extract_metrics(self.without_lightrun)
        
        for metric in ['requestLatency', 'handlerRunTime']:
            report_lines.append(f"\nMETRIC: {metric}")
            report_lines.append("-" * 40)
            
            w_vals = with_metrics.get(metric, [])
            wo_vals = without_metrics.get(metric, [])
            
            if not w_vals or not wo_vals:
                report_lines.append("Insufficient data.")
                continue
                
            w_stats = calculate_stats(w_vals)
            wo_stats = calculate_stats(wo_vals)
            
            diff_mean = w_stats['mean'] - wo_stats['mean']
            pct_mean = (diff_mean / wo_stats['mean']) * 100 if wo_stats['mean'] > 0 else 0
            
            report_lines.append(f"Without Lightrun (Baseline):")
            report_lines.append(f"  Mean:   {format_duration(wo_stats['mean'])}")
            report_lines.append(f"  Median: {format_duration(wo_stats['median'])}")
            report_lines.append(f"  StdDev: {format_duration(wo_stats['stdev'])}")
            
            report_lines.append(f"With Lightrun:")
            report_lines.append(f"  Mean:   {format_duration(w_stats['mean'])}")
            report_lines.append(f"  Median: {format_duration(w_stats['median'])}")
            report_lines.append(f"  StdDev: {format_duration(w_stats['stdev'])}")
            
            report_lines.append(f"OVERHEAD:")
            report_lines.append(f"  Mean:   {format_duration(diff_mean)} (+{pct_mean:.2f}%)")
            
        # Save to file
        out_path = self.output_dir / filename
        with open(out_path, 'w') as f:
            f.write("\n".join(report_lines))
            
        print(f"Report generated at: {out_path}")
        print("\n".join(report_lines))

    def generate_all(self, filename: str):
        self.generate_report(filename)
