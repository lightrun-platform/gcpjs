from abc import ABC, abstractmethod
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from typing import Union
from gcf_models.deployment_result import DeploymentResult
from gcf_task_primitives.delete_function_task import DeleteFunctionTask
import logging

class BenchmarkCase[T](ABC):
    """A single unit of benchmark execution. self contains everything needed to run the benchmark case."""

    def __init__(self):
        self.logger = logging.getLogger(BenchmarkCase.__class__.__name__ + "-" + self.name)
        self.deploy_task = None
        self.deployment_result = None
        self.delete_result = None
        self.benchmark_result = None
        self.errors = []

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
    def execute_benchmark(self) -> DeploymentResult:
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
            summary += f"Deployment result: {'Success' if self.deployment_result['success'] else 'Failure'}\n"
            if not self.deployment_result['success']:
                summary += f"Failure\n"
                summary += f"Error: {self.deployment_result['error']}"
            else:
                summary += f"Success\n"
                self.log_info(summary)
                if not self.delete_result['success']:
                    self.log_error(f"Failed to delete function {self.delete_result['function_name']}: {self.delete_result['error']}")



