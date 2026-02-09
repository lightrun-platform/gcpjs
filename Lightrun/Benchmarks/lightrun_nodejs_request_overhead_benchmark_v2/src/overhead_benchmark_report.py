import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.benchmark_report_generator import BenchmarkReportGenerator
from Lightrun.Benchmarks.shared_modules.cpu_model import CpuModel
from .overhead_benchmark_result import Success, Failure, LightrunOverheadBenchmarkResult
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


def _build_warmup_summary(results: List[LightrunOverheadBenchmarkResult]) -> Dict[str, Any]:
    """Build warmup summary across all results that have warmup data.
    
    Returns:
        Dict with warmup statistics and per-case warmup info
    """
    warmup_cases: List[Dict[str, Any]] = []
    
    for result in results:
        if result is None:
            continue
        if not isinstance(result, Success):
            continue
        
        warmup_result = result.benchmark_dto.warmup_result
        if not warmup_result or not warmup_result.measurements:
            continue
        
        measurements = warmup_result.measurements
        run_times = [m.handler_run_time_ns for m in measurements]
        
        case_warmup = {
            "case_name": result.benchmark_dto.name,
            "memory": result.benchmark_dto.memory,
            "cpu": result.benchmark_dto.cpu,
            "cpu_model": result.benchmark_dto.cpu_model,
            "total_requests": warmup_result.total_requests,
            "stabilized": warmup_result.stabilized,
            "stability_achieved_at_request": warmup_result.stability_achieved_at_request,
            "config": {
                "timeout_seconds": warmup_result.timeout_seconds,
                "max_requests": warmup_result.max_requests,
                "stability_window": warmup_result.stability_window,
                "stability_tolerance": warmup_result.stability_tolerance,
            },
            "stats": {
                "min_ns": min(run_times),
                "max_ns": max(run_times),
                "mean_ns": statistics.mean(run_times),
                "median_ns": statistics.median(run_times),
                "stdev_ns": statistics.stdev(run_times) if len(run_times) > 1 else 0.0,
            },
            # Include all measurements for the graph
            "measurements": [
                {"request_number": m.request_number, "handler_run_time_ns": m.handler_run_time_ns, "timestamp_ns": m.timestamp_ns}
                for m in measurements
            ],
        }
        warmup_cases.append(case_warmup)
    
    if not warmup_cases:
        return {"cases": [], "summary": {}}
    
    # Aggregate summary
    all_run_times = []
    total_stabilized = 0
    for case in warmup_cases:
        all_run_times.extend([m["handler_run_time_ns"] for m in case["measurements"]])
        if case["stabilized"]:
            total_stabilized += 1
    
    summary = {
        "total_cases_with_warmup": len(warmup_cases),
        "cases_stabilized": total_stabilized,
        "cases_not_stabilized": len(warmup_cases) - total_stabilized,
    }
    if all_run_times:
        summary["all_run_times_ns"] = {
            "min": min(all_run_times),
            "max": max(all_run_times),
            "mean": statistics.mean(all_run_times),
            "median": statistics.median(all_run_times),
        }
    
    return {
        "summary": summary,
        "cases": warmup_cases,
    }


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
    - warmup: warmup phase data from all cases
    - failed_measurements: list of failed measurements with their action counts (for visualization)
    
    Note: Results can contain individual measurements in benchmark_results dict (new format)
    or a single measurement (legacy format). This function handles both.
    
    Also handles partial failures: even if a result is marked as Failure overall, 
    it may contain some successful individual measurements that we can still use.
    """
    failures_count = 0
    # Group by (allocation, cpu_model) for precise comparisons
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    # Track failed measurements for visualization (show X marks on chart)
    failed_measurements: Dict[str, List[Dict[str, Any]]] = {}
    
    for result in results:
        if result is None:
            failures_count += 1
            continue
        
        # Process both Success and Failure results - Failure may have partial data
        if not isinstance(result, (Success, Failure)):
            failures_count += 1
            continue
        
        # Get DTO - both Success and Failure have benchmark_dto
        dto = result.benchmark_dto
        if dto is None:
            failures_count += 1
            continue
            
        memory = dto.memory
        cpu = dto.cpu
        # Get cpu_model from DTO (populated during load) or identify from cpu_info
        cpu_model = dto.cpu_model
        if not cpu_model and result.cpu_info:
            cpu_model = CpuModel.identify(result.cpu_info).display_name
        
        key = _group_key(memory, cpu, cpu_model)
        
        # Check if this result has benchmark_results dict (new format)
        benchmark_results = dto.benchmark_results
        if benchmark_results:
            # Extract individual measurements from benchmark_results dict
            recorded_action_counts = set()
            for num_actions, measurement in benchmark_results.items():
                recorded_action_counts.add(int(num_actions))
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
                    # Track failed measurement for visualization
                    failed_measurements.setdefault(key, []).append({
                        "memory": memory,
                        "cpu": cpu,
                        "cpu_model": cpu_model,
                        "actions_count": measurement.actions_count,
                        "error": measurement.error,
                    })
            
            # Check for missing measurements (action counts that should have been tested but weren't)
            # test_size means we should test 0 through test_size (inclusive)
            test_size = dto.test_size
            if test_size is not None:
                expected_action_counts = set(range(test_size + 1))
                missing_action_counts = expected_action_counts - recorded_action_counts
                for missing_count in missing_action_counts:
                    failures_count += 1
                    failed_measurements.setdefault(key, []).append({
                        "memory": memory,
                        "cpu": cpu,
                        "cpu_model": cpu_model,
                        "actions_count": missing_count,
                        "error": "Measurement not recorded (benchmark stopped early)",
                    })
        elif isinstance(result, Success):
            # Legacy format: single measurement per result (only for Success)
            grouped.setdefault(key, []).append({
                "memory": memory,
                "cpu": cpu,
                "cpu_model": cpu_model,
                "actions_count": result.actions_count,
                "handler_run_time_ns": result.handler_run_time_ns,
            })
        else:
            # Legacy Failure without benchmark_results
            failures_count += 1
    
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
        # Get failed measurements for this group
        group_failures = failed_measurements.get(key, [])
        failed_action_counts = sorted(set(f["actions_count"] for f in group_failures))
        
        by_group[key] = {
            "memory": memory,
            "cpu": cpu,
            "cpu_model": cpu_model,
            "summary": group_summary,
            "successes": successes,
            "by_actions_count": by_actions_count,
            "regression": regression,
            "failed_measurements": group_failures,
            "failed_action_counts": failed_action_counts,  # For easy chart rendering
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

    # Build warmup data
    warmup_data = _build_warmup_summary(results)
    
    # Aggregate all failed measurements for summary
    all_failed = []
    for group_failures in failed_measurements.values():
        all_failed.extend(group_failures)
    
    return {
        "summary": summary,
        "by_allocation": by_allocation,
        "by_group": by_group,
        "warmup": warmup_data,
        "failed_measurements": all_failed,
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
    
    # Section 3: Warmup Analysis
    warmup_data = report_data.get("warmup", {})
    warmup_cases = warmup_data.get("cases", [])
    if warmup_cases:
        warmup_summary = warmup_data.get("summary", {})
        lines.extend([
            "=" * 60,
            "WARMUP ANALYSIS",
            "=" * 60,
            "",
            f"Total cases with warmup data: {warmup_summary.get('total_cases_with_warmup', 0)}",
            f"Cases that stabilized:        {warmup_summary.get('cases_stabilized', 0)}",
            f"Cases that did NOT stabilize: {warmup_summary.get('cases_not_stabilized', 0)}",
            "",
        ])
        
        if warmup_summary.get("all_run_times_ns"):
            h = warmup_summary["all_run_times_ns"]
            lines.extend([
                "Aggregate warmup run times (ns):",
                f"  Min:    {h['min']}",
                f"  Max:    {h['max']}",
                f"  Mean:   {h['mean']:.0f}",
                f"  Median: {h['median']:.0f}",
                "",
            ])
        
        lines.append("Per-case warmup summary:")
        lines.append("")
        for case in warmup_cases:
            status = "STABILIZED" if case["stabilized"] else "NOT STABILIZED"
            stab_at = f" at request {case['stability_achieved_at_request']}" if case["stability_achieved_at_request"] else ""
            lines.extend([
                f"--- {case['case_name']} ---",
                f"  Allocation: {case['memory']} / {case['cpu']} CPU",
                f"  Processor:  {case.get('cpu_model') or 'Unknown'}",
                f"  Status:     {status}{stab_at}",
                f"  Requests:   {case['total_requests']}",
            ])
            stats = case.get("stats", {})
            if stats:
                lines.extend([
                    f"  Run time (ns): min={stats['min_ns']}, max={stats['max_ns']}, mean={stats['mean_ns']:.0f}",
                ])
            config = case.get("config", {})
            if config:
                lines.extend([
                    f"  Config: timeout={config['timeout_seconds']}s, max_requests={config['max_requests']}, "
                    f"window={config['stability_window']}, tolerance={config['stability_tolerance']*100:.1f}%",
                ])
            lines.append("")
    
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
