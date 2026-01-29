
from abc import ABC, abstractmethod
from typing import List
from gcf_models.benchmark_case_result import BenchmarkCaseResult

class BenchmarkReportGenerator[T](ABC):

    @abstractmethod
    def generate_report(self, benchmark_results: List[BenchmarkCaseResult[T]]):
        pass

