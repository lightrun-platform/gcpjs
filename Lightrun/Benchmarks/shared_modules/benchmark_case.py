from abc import ABC, abstractmethod
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory
from typing import Union, Optional, List

from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult, DeleteSuccess, DeleteFailure
from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask
from Lightrun.Benchmarks.shared_modules.gcf_models.deploy_function_result import DeploymentResult, DeploymentSuccess, DeploymentFailure
import logging

class BenchmarkCase[T](ABC):
    """A single unit of benchmark execution. self contains everything needed to run the benchmark case."""

    def __init__(self, deployment_timeout_seconds: int, delete_timeout_seconds: int, clean_after_run: bool) -> None:
        self.deployment_timeout_seconds = deployment_timeout_seconds
        self.delete_timeout_seconds = delete_timeout_seconds
        self.clean_after_run = clean_after_run
        self.deploy_task: Optional[DeployFunctionTask] = None
        self.deployment_result: Optional[DeploymentResult] = None
        self.delete_result: Optional[DeleteFunctionResult] = None
        self.benchmark_result: Optional[T] = None
        self.errors: List[Exception] = []
        self.summary: Optional[str] = None


    @property
    @abstractmethod
    def logger(self) -> logging.Logger:
        pass

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
        self.logger.info(f"Starting benchmark case: {self.name}")
        try:
            self.deployment_result = self.gcp_function.deploy(self.deployment_timeout_seconds)
            
            match self.deployment_result:
                case DeploymentFailure(error=error):
                    raise Exception(error)
                case DeploymentSuccess():
                    self.benchmark_result = self.execute_benchmark()
                case _:
                    raise Exception(f"Unknown deployment result type: {type(self.deployment_result)}")

        except Exception as e:
            self.logger.exception(f"Benchmark case execution failed with exception: {e}")
            self.errors.append(e)
        finally:
            if self.clean_after_run:
                self.delete_result = self.gcp_function.delete(self.delete_timeout_seconds)
            
            summary = f"Finished benchmark case: {self.name}.\n"

            match self.deployment_result:
                case None:
                     summary += "Deployment result: deployment not attempted or info is missing"
                case DeploymentFailure(error=error):
                    summary += f"Failure\n"
                    summary += f"Error: {error}\n"
                case DeploymentSuccess():
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
                    match self.delete_result:
                        case None:
                            summary += "Delete result: delete was not attempted or info is missing"
                        case DeleteFailure(error=error, stderr=stderr):
                            summary += f"Delete result: Failure\n"
                            summary += f"Error: {error}\n"
                            summary += f"Stderr: {stderr}\n"
                        case DeleteSuccess():
                            summary += f"Delete result: Success\n"

            self.summary = summary
            self.logger.info(summary)



