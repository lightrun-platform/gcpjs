from abc import ABC, abstractmethod
from typing import List, Iterator
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from .benchmark_case import BenchmarkCase
from .region_allocator import RegionAllocator


class BenchmarkCasesGenerator[T](ABC):

    REGIONS_ALLOCATOR = RegionAllocator()

    def generate_benchmark_cases(self, benchmark_name: str, benchmark_config: ParsedCLIArguments) -> List[BenchmarkCase[T]]:
        return self._generate_benchmark_cases(benchmark_name, benchmark_config, iter(self.REGIONS_ALLOCATOR))

    @abstractmethod
    def _generate_benchmark_cases(self, benchmark_name: str, benchmark_config: ParsedCLIArguments, regions_allocation_order: Iterator[str]) -> List[BenchmarkCase[T]]:
        raise NotImplementedError("Subclasses must implement this method to yield BenchmarkCase[T]")