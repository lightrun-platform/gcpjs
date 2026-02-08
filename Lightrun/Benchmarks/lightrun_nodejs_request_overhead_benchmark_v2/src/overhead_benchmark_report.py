import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.benchmark_report_generator import BenchmarkReportGenerator
from .overhead_benchmark_result import Success, LightrunOverheadBenchmarkResult
from .overhead_benchmark_result_repository import (
    LightrunOverheadBenchmarkResultRepository,
    RAW_FILENAME,
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


def _build_report_data_from_results(
    results: List[LightrunOverheadBenchmarkResult],
) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Build summary, successes list, by_actions_count, regression from result list."""
    successes: List[Dict[str, Any]] = []
    failures_count = 0
    for result in results:
        if result is None:
            failures_count += 1
            continue
        if isinstance(result, Success):
            successes.append({
                "actions_count": result.actions_count,
                "handler_run_time_ns": result.handler_run_time_ns,
            })
        else:
            failures_count += 1
    total = len(results)
    success_count = len(successes)
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
    return summary, successes, by_actions_count, regression


def _write_report_files(
    save_path: Path,
    summary: Dict[str, Any],
    successes: List[Dict[str, Any]],
    by_actions_count: List[Dict[str, Any]],
    regression: Dict[str, Any],
) -> Path:
    """Write report_data.json and benchmark_report.txt; return report_path."""
    report_data = {
        "summary": summary,
        "successes": successes,
        "by_actions_count": by_actions_count,
        "regression": regression,
    }
    data_path = save_path / "report_data.json"
    with open(data_path, "w") as f:
        json.dump(report_data, f, indent=2)
    report_path = save_path / "benchmark_report.txt"
    total = summary["total_cases"]
    success_count = summary["success_count"]
    failures_count = summary["failure_count"]
    lines = [
        "Lightrun Request Overhead Benchmark Report",
        "==========================================",
        "",
        f"Total cases:     {total}",
        f"Successes:      {success_count}",
        f"Failures:       {failures_count}",
        "",
    ]
    if summary.get("handler_run_time_ns"):
        h = summary["handler_run_time_ns"]
        lines.extend([
            "Handler run time (ns):",
            f"  Min:    {h['min']}",
            f"  Max:    {h['max']}",
            f"  Mean:   {h['mean']:.0f}",
            f"  Median: {h['median']:.0f}",
            f"  Stdev:  {h['stdev']:.0f}",
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


class LightrunOverheadReportGenerator(
    BenchmarkReportGenerator[LightrunOverheadBenchmarkResult]
):
    """Generates reports for Lightrun overhead benchmark."""

    def load_benchmark_data(
        self, path: Path
    ) -> List[LightrunOverheadBenchmarkResult]:
        """Load benchmark results from raw data (inverse of repository save_benchmark_data)."""
        repo = LightrunOverheadBenchmarkResultRepository()
        raw_path = path / RAW_FILENAME if path.is_dir() else path
        if not raw_path.exists():
            return []
        return repo.load_benchmark_data(path)

    def generate_report(
        self,
        benchmark_results: List[BenchmarkCase[LightrunOverheadBenchmarkResult]],
        save_path: Path,
    ) -> Path:
        """Generate report from benchmark cases (uses get_benchmark_result on each case)."""
        results = [case.get_benchmark_result() for case in benchmark_results]
        summary, successes, by_actions_count, regression = _build_report_data_from_results(
            results
        )
        return _write_report_files(
            save_path, summary, successes, by_actions_count, regression
        )

    def generate_report_from_results(
        self,
        results: List[LightrunOverheadBenchmarkResult],
        save_path: Path,
    ) -> Path:
        """Generate report from a list of results (e.g. after load_benchmark_data)."""
        summary, successes, by_actions_count, regression = _build_report_data_from_results(
            results
        )
        return _write_report_files(
            save_path, summary, successes, by_actions_count, regression
        )
