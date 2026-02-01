from abc import ABC, abstractmethod
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from typing import Union, Optional, List

from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult
from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask
from gcf_models.deploy_function_result import DeploymentResult
import logging

class BenchmarkCase[T](ABC):
    """A single unit of benchmark execution. self contains everything needed to run the benchmark case."""

    def __init__(self):
        self.logger = logging.getLogger(BenchmarkCase.__class__.__name__ + "-" + self.name)
        self.deploy_task: Optional[DeployFunctionTask] = None
        self.deployment_result: Optional[DeploymentResult] = None
        self.delete_result: Optional[DeleteFunctionResult] = None
        self.benchmark_result: Optional[T] = None
        self.errors: List[Exception] = []
        self.summary: Optional[str] = None

    def log_error(self, e: Union[str,Exception]) -> None:
        self.logger.error(e)

    def log_info(self, e: Union[str,Exception]) -> None:
        self.logger.info(e)

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def gcp_function(self) -> GCPFunction:
        pass

    @property
    @abstractmethod
    def env_vars(self) -> dict:
        pass

    @abstractmethod
    def execute_benchmark(self) -> T:
        pass

    def run(self):
        self.log_info(f"Starting benchmark case: {self.name}")
        try:
            self.deployment_result = self.gcp_function.deploy(self.env_vars)
            if not self.deployment_result.success:
                raise self.deployment_result.error
            self.benchmark_result = self.execute_benchmark()

        except Exception as e:
            self.log_error(e)
            self.errors.append(e)
        finally:
            self.delete_result = self.gcp_function.delete()
            
            summary = f"Finished benchmark case: {self.name}.\n"

            if self.deployment_result is None:
                summary += "Deployment result: deployment not attempted or info is missing"
            else:
                summary += "Deployment result: "
                if not self.deployment_result.success:
                    summary += f"Failure\n"
                    summary += f"Error: {self.deployment_result.error}\n"
                else:
                    summary += f"Success\n"
                    # Only show benchmark result if deployment succeeded
                    if self.benchmark_result is None:
                        summary += "Benchmark result: benchmark did not run or info is missing"
                    else:
                        summary += f"Benchmark result: "
                        if not self.benchmark_result.success:
                            summary += f"Failure\n"
                            summary += f"Error: {self.benchmark_result.error}\n"
                        else:
                            summary += f"Success\n"
                    # only check delete state if the function was deployed, hence its in this nested else
                    if self.delete_result is None:
                        summary += "Delete result: delete was not attempted or info is missing"
                    else:
                        summary += "Delete result: "
                        if not self.delete_result.success:
                            summary += f"Failure\n"
                            summary += f"Error: {str(self.delete_result.error)}\n"
                            summary += f"Stderr: {self.delete_result.stderr}\n"
                        else:
                            summary += f"Success\n"

            self.summary = summary
            self.log_info(summary)



