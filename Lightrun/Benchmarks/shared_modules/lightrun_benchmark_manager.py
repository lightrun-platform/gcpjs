
from typing import List

from Lightrun.Benchmarks.shared_modules.benchmark_cases_generator import BenchmarkCase
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging


class BenchmarkManager[T]:

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.logger = logging.getLogger(__name__)

    def run(self, benchmark_cases: List[BenchmarkCase[T]]) -> None:
        """Run the complete test workflow. results are saved inside the benchmark case object."""

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            self.logger.info(f"Started Executor with {self.num_workers} worker threads.")
            futures = {executor.submit(benchmark_case.run): benchmark_case for benchmark_case in benchmark_cases}
            self.logger.info(f"Submitted {len(futures)} benchmark cases:\n{(''.join(f"\n\t-\t{benchmark_case.name}" for benchmark_case in benchmark_cases))}")
            self.logger.info("Starting Execution")

            for future in as_completed(futures):
                benchmark_case = futures[future]
                try:
                    future.result()
                except Exception as e:
                    benchmark_case.log_error(e)

            self.logger.info("Finished execution.")