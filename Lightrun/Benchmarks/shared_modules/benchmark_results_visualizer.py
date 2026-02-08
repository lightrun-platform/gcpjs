
from abc import ABC, abstractmethod
from pathlib import Path

from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import LightrunBenchmarkResult


class BenchmarkResultsVisualizer[T: LightrunBenchmarkResult](ABC):

    @abstractmethod
    def display(self) -> None:
        """Display the visualizations file. can only be called after create_visualizations"""
        pass

    @abstractmethod
    def create_visualizations(self, benchmark_report: Path, save_path: Path) -> Path:
        """Creates the visualizations and saves them in save_path, returning the path to the visualizations file."""
        pass

