from abc import ABC
from dataclasses import dataclass
from typing import Optional
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase

@dataclass
class LightrunBenchmarkResult(ABC):
    """Class to hold the result of a single benchmark case run."""


@dataclass
class BenchmarkFailure(LightrunBenchmarkResult):
    error: str
    cpu_info: Optional[str] = None

@dataclass
class BenchmarkSuccess(LightrunBenchmarkResult):
    handler_run_time_ns: int
    actions_count: int
    cpu_info: str


