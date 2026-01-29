
from typing import List

from Lightrun.Benchmarks.shared_modules.benchmark_cases_generator import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_case_result import BenchmarkCaseResult
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging


class BenchmarkManager[T]:

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.logger = logging.getLogger(__name__)


    def run(self, benchmark_cases: List[BenchmarkCase[T]]) -> List[BenchmarkCaseResult[T]]:
        """Run the complete test workflow and return results."""
        res = []
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {executor.submit(benchmark_case.run): benchmark_case for benchmark_case in benchmark_cases}
            for future in as_completed(futures):
                benchmark_case = futures[future]
                try:
                    res.append(future.result())
                except Exception as e:
                    benchmark_case.log_error(e)

        return res