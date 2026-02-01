
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path

class BenchmarkResultsVisualizer[T](ABC):

    @abstractmethod
    def display(self) -> None:
        """Display the visualizations file. can only be called after create_visualizations"""
        pass

    @abstractmethod
    def create_visualizations(self, benchmark_report: Path, save_path: Path) -> Path:
        """Creates the visualizations and saves them in save_path, returning the path to the visualizations file."""
        pass

