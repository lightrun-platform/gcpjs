from dataclasses import dataclass

from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import BenchmarkSuccess, BenchmarkFailure


@dataclass
class LightrunOverheadBenchmarkFailure(BenchmarkFailure):
    pass

@dataclass
class LightrunOverheadBenchmarkSuccess(BenchmarkSuccess):
    pass

