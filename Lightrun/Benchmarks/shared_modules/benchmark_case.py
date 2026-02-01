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

    def __init__(self, logger_factory: LoggerFactory):
        self.logger_factory = logger_factory
        self._logger = None
        self.deploy_task: Optional[DeployFunctionTask] = None
        self.deployment_result: Optional[DeploymentResult] = None
        self.delete_result: Optional[DeleteFunctionResult] = None
        self.benchmark_result: Optional[T] = None
        self.errors: List[Exception] = []
        self.summary: Optional[str] = None


    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = self.logger_factory.get_logger(self.__class__.__name__ + "-" + self.name)
        return self._logger

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
            self.deployment_result = self.gcp_function.deploy(logger_factory=self.logger_factory)
            
            match self.deployment_result:
                case DeploymentFailure(error=error):
                    raise Exception(error)
                case DeploymentSuccess():
                    self.benchmark_result = self.execute_benchmark()
                case _:
                    raise Exception(f"Unknown deployment result type: {type(self.deployment_result)}")

        except Exception as e:
            self.log_error(e)
            self.errors.append(e)
        finally:
            self.delete_result = self.gcp_function.delete(logger_factory=self.logger_factory)
            
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
            self.log_info(summary)



