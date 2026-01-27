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
    
    def _extract_iterative_metrics(self, results: Dict[str, Any]) -> Dict[int, List[float]]:
        """Extract metrics per iteration (number of actions)."""
        metrics_per_action = {}
        
        test_results = results.get('test_results', [])
        for res in test_results:
            if res.get('is_iterative'):
                iterations = res.get('iterations', [])
                for iter_res in iterations:
                    if not iter_res.get('error'):
                        iter_num = iter_res.get('iteration', 0)
                        
                        # Extract handlerRunTime
                        request_list = iter_res.get('_all_request_results', [])
                        for req in request_list:
                            if not req.get('error') and 'handlerRunTime' in req:
                                try:
                                    val = float(req['handlerRunTime'])
                                    if iter_num not in metrics_per_action:
                                        metrics_per_action[iter_num] = []
                                    metrics_per_action[iter_num].append(val)
                                except:
                                    pass
            else:
                # Fallback for non-iterative results (treat as 0 actions)
                pass
                
        return metrics_per_action

    def generate_report(self, filename: str = 'overhead_report.txt'):
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("Lightrun Iterative Request Overhead Benchmark Report")
        report_lines.append("=" * 80)
        
        # With Lightrun (Iterative)
        w_metrics = self._extract_iterative_metrics(self.with_lightrun)
        
        # Without Lightrun (Baseline - assume 0 actions always)
        wo_metrics_map = self._extract_iterative_metrics(self.without_lightrun)
        wo_values = wo_metrics_map.get(0, []) # Should be iteration 0
        
        baseline_mean = statistics.mean(wo_values) if wo_values else 0
        report_lines.append(f"Baseline (No Lightrun) Mean Runtime: {format_duration(baseline_mean)}")
        report_lines.append("-" * 40)
        
        # Regression Data
        x_actions = []
        y_runtimes = []
        
        report_lines.append(f"{'Actions':<10} {'Mean Runtime':<20} {'Overhead':<20} {'% Increase':<10}")
        
        sorted_actions = sorted(w_metrics.keys())
        for action_count in sorted_actions:
            vals = w_metrics[action_count]
            mean_val = statistics.mean(vals)
            
            x_actions.append(action_count)
            y_runtimes.append(mean_val)
            
            overhead = mean_val - baseline_mean
            pct = (overhead / baseline_mean * 100) if baseline_mean > 0 else 0
            
            report_lines.append(f"{action_count:<10} {format_duration(mean_val):<20} {format_duration(overhead):<20} {pct:6.2f}%")
            
        # Linear Regression
        if len(x_actions) > 1:
            try:
                slope, intercept = statistics.linear_regression(x_actions, y_runtimes)
            except AttributeError:
                 # Phyton < 3.10
                 n = len(x_actions)
                 sum_x = sum(x_actions)
                 sum_y = sum(y_runtimes)
                 sum_xy = sum(x*y for x,y in zip(x_actions, y_runtimes))
                 sum_xx = sum(x*x for x in x_actions)
                 slope = (n*sum_xy - sum_x*sum_y) / (n*sum_xx - sum_x**2) if (n*sum_xx - sum_x**2) != 0 else 0
                 intercept = (sum_y - slope*sum_x) / n
                 
            report_lines.append("-" * 40)
            report_lines.append(f"Linear Regression: Runtime = {format_duration(slope)} * Actions + {format_duration(intercept)}")
            report_lines.append(f"Cost per Action: {format_duration(slope)}")
            
        # Save to file
        out_path = self.output_dir / filename
        with open(out_path, 'w') as f:
            f.write("\n".join(report_lines))
            
        print(f"Report generated at: {out_path}")
        print("\n".join(report_lines))

    def generate_all(self, filename: str):
        self.generate_report(filename)
