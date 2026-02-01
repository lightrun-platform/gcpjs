from pathlib import Path
from typing import List
from Lightrun.Benchmarks.shared_modules.benchmark_report_generator import BenchmarkReportGenerator
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult

class LightrunOverheadReportGenerator(BenchmarkReportGenerator[LightrunOverheadBenchmarkResult]):
    """Generates reports for Lightrun overhead benchmark."""

    def generate_report(self, benchmark_results: List[BenchmarkCase[LightrunOverheadBenchmarkResult]], save_path: Path) -> Path:
        """Generate a report file from the benchmark results and saves it to the given directory."""
        report_path = save_path / "benchmark_report.txt"
        with open(report_path, "w") as f:
            f.write("Lightrun Request Overhead Benchmark Report\n")
            f.write("========================================\n\n")
            # Stub content
            f.write(f"Processed {len(benchmark_results)} cases.\n")
        return report_path
