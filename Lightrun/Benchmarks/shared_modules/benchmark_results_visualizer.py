
from abc import ABC, abstractmethod
from typing import List
from gcf_models.benchmark_case_result import BenchmarkCaseResult
from pathlib import Path

class BenchmarkResultsVisualizer[T](ABC):

    @abstractmethod
    def display(self) -> None:
        """Display the visualizations file. can only be called after create_visualizations"""
        pass

    @abstractmethod
    def create_visualizations(self, benchmark_results: List[BenchmarkCaseResult[T]]) -> Path:
        """Creates the visualizations and saves them, returning the path to the visualizations file."""
        pass

