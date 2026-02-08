from abc import ABC
from dataclasses import dataclass
from typing import Optional
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase

@dataclass
class LightrunBenchmarkResult[T](ABC):
    """Class to hold the result of a single benchmark case run."""
    benchmark_dto: T


@dataclass
class BenchmarkFailure[T](LightrunBenchmarkResult[T]):
    error: str
    cpu_info: Optional[str] = None

@dataclass
class BenchmarkSuccess[T](LightrunBenchmarkResult[T]):
    handler_run_time_ns: int
    actions_count: int
    cpu_info: str


