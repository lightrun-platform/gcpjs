from abc import ABC
from dataclasses import dataclass
from typing import Optional
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase

@dataclass
class LightrunOverheadBenchmarkResult(ABC):
    """Class to hold the result of a single benchmark case run."""

    benchmark_case: BenchmarkCase


@dataclass
class BenchmarkFailure(LightrunOverheadBenchmarkResult):
    error: Optional[str] = None


@dataclass
class BenchmarkSuccess(LightrunOverheadBenchmarkResult):
    handler_run_time_ns: int
    actions_count: int



