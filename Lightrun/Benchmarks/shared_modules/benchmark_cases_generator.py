from abc import ABC, abstractmethod
from typing import List
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from .benchmark_case import BenchmarkCase


class BenchmarkCasesGenerator[T](ABC):

    @abstractmethod
    def generate_benchmark_cases(self, benchmark_name: str, benchmark_config: ParsedCLIArguments) -> List[BenchmarkCase[T]]:
        raise NotImplementedError("Subclasses must implement this method to yield BenchmarkCase[T]")