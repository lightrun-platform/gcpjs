import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.benchmark_report_generator import BenchmarkReportGenerator
from Lightrun.Benchmarks.shared_modules.cpu_model import CpuModel
from .overhead_benchmark_result import Success, LightrunOverheadBenchmarkResult
from .overhead_benchmark_result_repository import LightrunOverheadBenchmarkResultRepository, RAW_FILENAME


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


def _allocation_key(memory: str, cpu: str) -> str:
    """Stable key for grouping by memory and CPU allocation (e.g. '512Mi-2')."""
    return f"{memory}-{cpu}"


def _group_key(memory: str, cpu: str, cpu_model: str | None) -> str:
    """Stable key for grouping by memory, CPU allocation, and processor type.
    
    Results are only comparable when they have the same allocation AND the same processor.
    """
    model_part = cpu_model or "Unknown"
    return f"{memory}-{cpu}|{model_part}"


def _build_report_data_from_results(
    results: List[LightrunOverheadBenchmarkResult],
) -> Dict[str, Any]:
    """Build report data with results grouped by (memory, cpu, cpu_model) so run times are comparable.

    Run times are only comparable when they have the same memory/CPU allocation AND the same
    processor type. Different allocations or different processors use different underlying
    hardware, so cross-group comparison is not meaningful.
    
    Returns a structure with:
    - summary: global stats
    - by_allocation: grouped by memory/cpu allocation only (for backward compatibility)
    - by_group: grouped by (allocation, cpu_model) for precise comparisons
    
    Note: Results can contain individual measurements in benchmark_results dict (new format)
    or a single measurement (legacy format). This function handles both.
    """
    failures_count = 0
    # Group by (allocation, cpu_model) for precise comparisons
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    
    for result in results:
        if result is None:
            failures_count += 1
            continue
        
        if not isinstance(result, Success):
            failures_count += 1
            continue
            
        memory = result.benchmark_dto.memory
        cpu = result.benchmark_dto.cpu
        # Get cpu_model from DTO (populated during load) or identify from cpu_info
        cpu_model = result.benchmark_dto.cpu_model
        if not cpu_model and result.cpu_info:
            cpu_model = CpuModel.identify(result.cpu_info).display_name
        
        key = _group_key(memory, cpu, cpu_model)
        
        # Check if this result has benchmark_results dict (new format)
        benchmark_results = result.benchmark_dto.benchmark_results
        if benchmark_results:
            # Extract individual measurements from benchmark_results dict
            for num_actions, measurement in benchmark_results.items():
                if measurement.success:
                    grouped.setdefault(key, []).append({
                        "memory": memory,
                        "cpu": cpu,
                        "cpu_model": cpu_model,
                        "actions_count": measurement.actions_count,
                        "handler_run_time_ns": measurement.handler_run_time_ns,
                    })
                else:
                    failures_count += 1
        else:
            # Legacy format: single measurement per result
            grouped.setdefault(key, []).append({
                "memory": memory,
                "cpu": cpu,
                "cpu_model": cpu_model,
                "actions_count": result.actions_count,
                "handler_run_time_ns": result.handler_run_time_ns,
            })
    
    total = len(results)
    success_count = sum(len(s) for s in grouped.values())

    by_group: Dict[str, Dict[str, Any]] = {}
    # Also build by_allocation for backward compatibility (aggregates across cpu_models)
    by_allocation_aggregated: Dict[str, List[Dict[str, Any]]] = {}
    
    for key, successes in grouped.items():
        times_ns = [s["handler_run_time_ns"] for s in successes]
        actions_counts = [s["actions_count"] for s in successes]
        memory = successes[0]["memory"]
        cpu = successes[0]["cpu"]
        cpu_model = successes[0]["cpu_model"]
        alloc_key = _allocation_key(memory, cpu)
        
        # Aggregate for by_allocation
        by_allocation_aggregated.setdefault(alloc_key, []).extend(successes)
        
        group_summary: Dict[str, Any] = {
            "count": len(successes),
        }
        if times_ns:
            group_summary["handler_run_time_ns"] = {
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
        by_group[key] = {
            "memory": memory,
            "cpu": cpu,
            "cpu_model": cpu_model,
            "summary": group_summary,
            "successes": successes,
            "by_actions_count": by_actions_count,
            "regression": regression,
        }

    # Build by_allocation (backward compatible structure, aggregates cpu_models)
    by_allocation: Dict[str, Dict[str, Any]] = {}
    for alloc_key, successes in by_allocation_aggregated.items():
        times_ns = [s["handler_run_time_ns"] for s in successes]
        actions_counts = [s["actions_count"] for s in successes]
        memory = successes[0]["memory"]
        cpu = successes[0]["cpu"]
        cpu_models_in_alloc = sorted(set(s["cpu_model"] or "Unknown" for s in successes))
        
        alloc_summary: Dict[str, Any] = {
            "count": len(successes),
            "cpu_models": cpu_models_in_alloc,
        }
        if times_ns:
            alloc_summary["handler_run_time_ns"] = {
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
        by_allocation[alloc_key] = {
            "memory": memory,
            "cpu": cpu,
            "summary": alloc_summary,
            "successes": successes,
            "by_actions_count": by_actions_count,
            "regression": regression,
        }

    # Collect unique allocations and groups
    allocations = sorted(by_allocation.keys())
    groups = sorted(by_group.keys())
    
    summary: Dict[str, Any] = {
        "total_cases": total,
        "success_count": success_count,
        "failure_count": failures_count,
        "allocations": allocations,
        "groups": groups,
    }
    if len(by_group) > 1:
        summary["note"] = (
            "Run times are only comparable within the same (allocation, processor) group. "
            "Different allocations or processors use different underlying hardware; "
            "cross-group comparison is not meaningful."
        )

    return {
        "summary": summary,
        "by_allocation": by_allocation,
        "by_group": by_group,
    }


def _write_report_files(save_path: Path, report_data: Dict[str, Any]) -> Path:
    """Write report_data.json and benchmark_report.txt; return report_path."""
    data_path = save_path / "report_data.json"
    with open(data_path, "w") as f:
        json.dump(report_data, f, indent=2)
    report_path = save_path / "benchmark_report.txt"
    summary = report_data["summary"]
    by_allocation = report_data["by_allocation"]
    by_group = report_data.get("by_group", {})
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
        f"Allocations:    {', '.join(summary.get('allocations', []))}",
        f"Groups:         {len(summary.get('groups', []))}",
        "",
    ]
    if summary.get("note"):
        lines.extend([summary["note"], ""])
    
    # Section 1: Results by (allocation, cpu_model) group - precise comparison
    lines.extend([
        "=" * 60,
        "RESULTS BY GROUP (Allocation + Processor)",
        "=" * 60,
        "",
        "Results grouped by (memory/CPU allocation, processor type).",
        "Run times are only comparable within the same group.",
        "",
    ])
    for key in sorted(by_group.keys()):
        group = by_group[key]
        memory = group["memory"]
        cpu = group["cpu"]
        cpu_model = group.get("cpu_model") or "Unknown"
        lines.extend([
            f"--- Group: {memory} / {cpu} CPU | {cpu_model} ---",
            "",
        ])
        group_summary = group["summary"]
        if group_summary.get("handler_run_time_ns"):
            h = group_summary["handler_run_time_ns"]
            lines.extend([
                "  Handler run time (ns):",
                f"    Min:    {h['min']}",
                f"    Max:    {h['max']}",
                f"    Mean:   {h['mean']:.0f}",
                f"    Median: {h['median']:.0f}",
                f"    Stdev:  {h['stdev']:.0f}",
                "",
            ])
        by_actions_count = group["by_actions_count"]
        if by_actions_count:
            lines.append("  By number of Lightrun actions:")
            for row in by_actions_count:
                lines.append(
                    f"    actions={row['actions_count']}: count={row['count']}, mean_ns={row['mean_ns']:.0f}"
                )
            lines.append("")
        regression = group.get("regression") or {}
        if regression:
            lines.extend([
                "  Linear fit: handler_run_time_ns = intercept + slope * actions_count",
                f"    Slope (ns per action): {regression['slope_ns_per_action']:.2f}",
                f"    Intercept (ns):        {regression['intercept_ns']:.2f}",
                f"    R²:                    {regression['r_squared']:.4f}",
                "",
            ])
    
    # Section 2: Aggregated by allocation (backward compatible, but note mixed processors)
    lines.extend([
        "=" * 60,
        "RESULTS BY ALLOCATION (Aggregated across processors)",
        "=" * 60,
        "",
        "WARNING: These results aggregate across different processor types.",
        "For precise comparison, use the 'by group' section above.",
        "",
    ])
    for key in sorted(by_allocation.keys()):
        alloc = by_allocation[key]
        memory = alloc["memory"]
        cpu = alloc["cpu"]
        cpu_models = alloc["summary"].get("cpu_models", [])
        lines.extend([
            f"--- Allocation: {memory} / {cpu} CPU ---",
            f"  Processors: {', '.join(cpu_models) if cpu_models else 'Unknown'}",
            "",
        ])
        alloc_summary = alloc["summary"]
        if alloc_summary.get("handler_run_time_ns"):
            h = alloc_summary["handler_run_time_ns"]
            lines.extend([
                "  Handler run time (ns):",
                f"    Min:    {h['min']}",
                f"    Max:    {h['max']}",
                f"    Mean:   {h['mean']:.0f}",
                f"    Median: {h['median']:.0f}",
                f"    Stdev:  {h['stdev']:.0f}",
                "",
            ])
        by_actions_count = alloc["by_actions_count"]
        if by_actions_count:
            lines.append("  By number of Lightrun actions:")
            for row in by_actions_count:
                lines.append(
                    f"    actions={row['actions_count']}: count={row['count']}, mean_ns={row['mean_ns']:.0f}"
                )
            lines.append("")
        regression = alloc.get("regression") or {}
        if regression:
            lines.extend([
                "  Linear fit: handler_run_time_ns = intercept + slope * actions_count",
                f"    Slope (ns per action): {regression['slope_ns_per_action']:.2f}",
                f"    Intercept (ns):        {regression['intercept_ns']:.2f}",
                f"    R²:                    {regression['r_squared']:.4f}",
                "",
            ])
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    return report_path


class LightrunOverheadReportGenerator(BenchmarkReportGenerator[LightrunOverheadBenchmarkResult]):
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
        report_data = _build_report_data_from_results(results)
        return _write_report_files(save_path, report_data)

    def generate_report_from_results(
        self,
        results: List[LightrunOverheadBenchmarkResult],
        save_path: Path,
    ) -> Path:
        """Generate report from a list of results (e.g. after load_benchmark_data)."""
        report_data = _build_report_data_from_results(results)
        return _write_report_files(save_path, report_data)
