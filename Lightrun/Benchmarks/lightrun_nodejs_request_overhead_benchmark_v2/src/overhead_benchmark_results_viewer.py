from pathlib import Path
from Lightrun.Benchmarks.shared_modules.benchmark_results_visualizer import BenchmarkResultsVisualizer
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult

class LightrunOverheadReportVisualizer(BenchmarkResultsVisualizer[LightrunOverheadBenchmarkResult]):
    """Visualizes results for Lightrun overhead benchmark."""

    def display(self) -> None:
        """Display the visualizations file."""
        print("Displaying visualizations (stub).")

    def create_visualizations(self, benchmark_report: Path, save_path: Path) -> Path:
        """Creates the visualizations and saves them in save_path."""
        viz_path = save_path / "visualizations.html"
        with open(viz_path, "w") as f:
            f.write("<html><body><h1>Benchmark Visualizations (Stub)</h1></body></html>")
        return viz_path
