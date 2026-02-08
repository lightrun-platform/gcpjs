from abc import ABC
from dataclasses import dataclass
from typing import Optional


@dataclass
class LightrunBenchmarkResult[T](ABC):
    """Class to hold the result of a single benchmark case run."""
    benchmark_dto: T

    @classmethod
    def SUCCESS(cls, benchmark_case_dto: T, handler_run_time_ns: int, actions_count: int, cpu_info: str) -> Success[T]:
        """Build a success result from the benchmark case and measurement."""
        return Success(benchmark_dto=benchmark_case_dto,
                      handler_run_time_ns=handler_run_time_ns,
                      actions_count=actions_count,
                      cpu_info=cpu_info)

    @classmethod
    def FAILURE(cls, benchmark_case_dto: T, error: str, cpu_info: Optional[str] = None) -> Failure[T]:
        """Build a failure result from the benchmark case and error."""
        return Failure(benchmark_dto=benchmark_case_dto, error=error, cpu_info=cpu_info)


@dataclass
class Failure[T](LightrunBenchmarkResult[T]):
    error: str
    cpu_info: Optional[str] = None


@dataclass
class Success[T](LightrunBenchmarkResult[T]):
    handler_run_time_ns: int
    actions_count: int
    cpu_info: str