from dataclasses import dataclass
from typing import Optional
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase

@dataclass
class LightrunOverheadBenchmarkResult:
    """Class to hold the result of a single benchmark case run."""
    success: bool
    error: Optional[str] = None
    total_run_time_sec: float = 0.0
    handler_run_time_ns: int = 0
    actions_count: int = 0
