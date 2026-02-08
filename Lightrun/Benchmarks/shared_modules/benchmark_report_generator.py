from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import LightrunBenchmarkResult


class BenchmarkReportGenerator[T: LightrunBenchmarkResult](ABC):

    @abstractmethod
    def generate_report(self, benchmark_results: List[BenchmarkCase[T]], save_path: Path) -> Path:
        """Generate a report file from the benchmark results and saves it to the given directory."""
        pass

