import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.benchmark_report_generator import BenchmarkReportGenerator

from .overhead_benchmark_case import LightrunOverheadBenchmarkCase
from .overhead_benchmark_result import (
    BenchmarkFailure,
    BenchmarkSuccess,
    LightrunOverheadBenchmarkResult,
)


def _linear_regression(
    x: List[float], y: List[float]
) -> tuple[float, float, float]:
    """Returns (slope, intercept, r_squared)."""
    n = len(x)
    if n < 2:
        return (0.0, float(statistics.mean(y)) if y else 0.0, 0.0)
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    # Use sample covariance (n-1) to match statistics.variance for consistent OLS slope
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / (n - 1)
    var_x = statistics.variance(x)
    if var_x == 0:
        return 0.0, mean_y, 0.0
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    y_pred = [intercept + slope * xi for xi in x]
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - pi) ** 2 for yi, pi in zip(y, y_pred))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0
    return (slope, intercept, r_squared)


class LightrunOverheadReportGenerator(
    BenchmarkReportGenerator[LightrunOverheadBenchmarkResult]
):
    """Generates reports for Lightrun overhead benchmark."""

    def save_benchmark_data(
        self,
        benchmark_results: List[BenchmarkCase[LightrunOverheadBenchmarkResult]],
        save_path: Path,
    ) -> Path:
        """Save raw benchmark run data for future analysis."""
        raw_entries: List[Dict[str, Any]] = []
        for case in benchmark_results:
            if not isinstance(case, LightrunOverheadBenchmarkCase):
                continue
            entry: Dict[str, Any] = {
                "case": {
                    "name": case.name,
                    "num_actions": case.num_actions,
                    "region": case.region,
                    "runtime": case.runtime,
                    "action_type": case.action_type,
                },
                "result": None,
            }
            result = case._benchmark_result
            if result is None:
                entry["result"] = {"success": False, "error": "No result", "cpu_info": None}
            elif isinstance(result, BenchmarkSuccess):
                entry["result"] = {
                    "success": True,
                    "handler_run_time_ns": result.handler_run_time_ns,
                    "actions_count": result.actions_count,
                    "cpu_info": result.cpu_info,
                }
            elif isinstance(result, BenchmarkFailure):
                entry["result"] = {
                    "success": False,
                    "error": result.error,
                    "cpu_info": result.cpu_info,
                }
            else:
                entry["result"] = {"success": False, "error": "Unknown result type", "cpu_info": None}
            raw_entries.append(entry)
        raw_path = save_path / "benchmark_raw_data.json"
        with open(raw_path, "w") as f:
            json.dump({"runs": raw_entries}, f, indent=2)
        return raw_path

    def generate_report(
        self,
        benchmark_results: List[BenchmarkCase[LightrunOverheadBenchmarkResult]],
        save_path: Path,
    ) -> Path:
        """Generate a report file and JSON data from the benchmark results."""
        successes: List[Dict[str, Any]] = []
        failures_count = 0

        for case in benchmark_results:
            result = case._benchmark_result
            if result is None:
                failures_count += 1
                continue
            if isinstance(result, BenchmarkSuccess):
                successes.append({
                    "actions_count": result.actions_count,
                    "handler_run_time_ns": result.handler_run_time_ns,
                })
            else:
                failures_count += 1

        total = len(benchmark_results)
        success_count = len(successes)

        # Stats over all successes
        times_ns = [s["handler_run_time_ns"] for s in successes]
        actions_counts = [s["actions_count"] for s in successes]
        summary: Dict[str, Any] = {
            "total_cases": total,
            "success_count": success_count,
            "failure_count": failures_count,
        }
        if times_ns:
            summary["handler_run_time_ns"] = {
                "min": min(times_ns),
                "max": max(times_ns),
                "mean": statistics.mean(times_ns),
                "median": statistics.median(times_ns),
                "stdev": statistics.stdev(times_ns) if len(times_ns) > 1 else 0.0,
            }

        # Per actions_count stats
        by_actions: Dict[int, List[int]] = {}
        for s in successes:
            k = s["actions_count"]
            by_actions.setdefault(k, []).append(s["handler_run_time_ns"])
        by_actions_count = [
            {
                "actions_count": k,
                "count": len(v),
                "mean_ns": statistics.mean(v),
                "samples_ns": v,
            }
            for k, v in sorted(by_actions.items())
        ]

        # Linear regression: handler_run_time_ns vs actions_count
        regression: Dict[str, Any] = {}
        if len(successes) >= 2:
            x = [float(a) for a in actions_counts]
            y = [float(t) for t in times_ns]
            slope, intercept, r_squared = _linear_regression(x, y)
            regression = {
                "slope_ns_per_action": slope,
                "intercept_ns": intercept,
                "r_squared": r_squared,
            }

        report_data = {
            "summary": summary,
            "successes": successes,
            "by_actions_count": by_actions_count,
            "regression": regression,
        }

        # Write JSON for visualizer
        data_path = save_path / "report_data.json"
        with open(data_path, "w") as f:
            json.dump(report_data, f, indent=2)

        # Human-readable report
        report_path = save_path / "benchmark_report.txt"
        lines = [
            "Lightrun Request Overhead Benchmark Report",
            "==========================================",
            "",
            f"Total cases:     {total}",
            f"Successes:      {success_count}",
            f"Failures:       {failures_count}",
            "",
        ]
        if times_ns:
            lines.extend([
                "Handler run time (ns):",
                f"  Min:    {summary['handler_run_time_ns']['min']}",
                f"  Max:    {summary['handler_run_time_ns']['max']}",
                f"  Mean:   {summary['handler_run_time_ns']['mean']:.0f}",
                f"  Median: {summary['handler_run_time_ns']['median']:.0f}",
                f"  Stdev:  {summary['handler_run_time_ns']['stdev']:.0f}",
                "",
            ])
        if by_actions_count:
            lines.append("By number of Lightrun actions:")
            for row in by_actions_count:
                lines.append(
                    f"  actions={row['actions_count']}: count={row['count']}, mean_ns={row['mean_ns']:.0f}"
                )
            lines.append("")
        if regression:
            lines.extend([
                "Linear fit: handler_run_time_ns = intercept + slope * actions_count",
                f"  Slope (ns per action): {regression['slope_ns_per_action']:.2f}",
                f"  Intercept (ns):        {regression['intercept_ns']:.2f}",
                f"  R²:                    {regression['r_squared']:.4f}",
                "",
            ])
        with open(report_path, "w") as f:
            f.write("\n".join(lines))

        return report_path
