from dataclasses import dataclass

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.lightrun_overhead_benchmark_case_dto import LightrunOverheadBenchmarkCaseDTO
from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import BenchmarkFailure, BenchmarkSuccess


class LightrunOverheadBenchmarkResult:
    """Factory for creating overhead benchmark results from a case."""

    @dataclass(kw_only=True)
    class Success(BenchmarkSuccess[LightrunOverheadBenchmarkCaseDTO]):
        pass

    @dataclass(kw_only=True)
    class Failure(BenchmarkFailure[LightrunOverheadBenchmarkCaseDTO]):
        """Overhead benchmark failure: case identity + error, cpu_info."""


    # @classmethod
    # def SUCCESS(cls, benchmark_case_dto: LightrunOverheadBenchmarkCaseDTO, handler_run_time_ns: int,actions_count: int, cpu_info: str) -> Success:
    #     """Build a success result from the benchmark case and measurement."""
    #     return Success(benchmark_dto=benchmark_case_dto,
    #                    handler_run_time_ns=handler_run_time_ns,
    #                    actions_count=actions_count,
    #                    cpu_info=cpu_info)
    #
    # @classmethod
    # def FAILURE(cls, benchmark_case_dto: LightrunOverheadBenchmarkCaseDTO, error: str, cpu_info: Optional[str] = None) -> Failure:
    #     """Build a failure result from the benchmark case and error."""
    #     return Failure(benchmark_dto=benchmark_case_dto,
    #                                             error=error,
    #                                             cpu_info=cpu_info)
