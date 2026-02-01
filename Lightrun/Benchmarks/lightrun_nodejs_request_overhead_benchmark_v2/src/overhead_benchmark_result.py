from dataclasses import dataclass
from typing import Optional
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase

@dataclass
class LightrunOverheadBenchmarkResult:
    """Class to hold the result of a single benchmark case run."""
    success: bool
    error: Optional[str] = None
    # Add other metrics here as needed
