from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import LightrunBenchmarkResult


class BenchmarkResultRepository[T](ABC):

    @abstractmethod
    def save_benchmark_data(self, benchmark_results: List[T], save_path: Path) -> Path:
        pass

    @abstractmethod
    def load_benchmark_data(self, path: Path) -> List[T]:
        pass
