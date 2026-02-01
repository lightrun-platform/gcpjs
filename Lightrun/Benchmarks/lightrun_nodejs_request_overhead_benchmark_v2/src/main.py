#!/usr/bin/env python3
"""Main entry point for Lightrun Request Overhead Benchmark V2."""

import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
# We need to go up 3 levels to reach the root 'Lightrun' directory context
root_dir = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root_dir))

from Lightrun.Benchmarks.shared_modules.lightrun_benchmark_runner import LightrunBenchmark
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_cases_generator import LightrunOverheadBenchmarkCasesGenerator
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_report import LightrunOverheadReportGenerator
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_results_viewer import LightrunOverheadReportVisualizer

def main():
    """Run the benchmark."""
    
    benchmark_name = "lightrun_nodejs_request_overhead_benchmark_v2"
    project_root = Path(__file__).resolve().parents[2] # .../lightrun_nodejs_request_overhead_benchmark_v2

    runner = LightrunBenchmark(
        cli_description="Measure the overhead of Lightrun actions on request latency (V2).",
        cli_epilog="Examples:\n  %(prog)s --lightrun-secret YOUR_SECRET --lightrun-api-key KEY --lightrun-company-id ID",
        benchmark_name=benchmark_name,
        test_root_dir=project_root,
        benchmark_cases_generator=LightrunOverheadBenchmarkCasesGenerator(),
        report_generator=LightrunOverheadReportGenerator(),
        report_visualizer=LightrunOverheadReportVisualizer()
    )
    
    runner.run()

if __name__ == "__main__":
    main()
