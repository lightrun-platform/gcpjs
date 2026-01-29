from abc import ABC, abstractmethod
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from typing import Union
import
from gcf_task_primitives.deploy_function_task import DeployFunctionTask

class BenchmarkCase[T](ABC):
    """A single unit of benchmark execution. self contains everything needed to run the benchmark case."""

    def __init__(self):
        self.logger = logging.getLogger(BenchmarkCase.__class__.__name__)
        self.deploy_task = None
        self.gcf_function = self.get_gcp_function()

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def log_error(self, msg: Union[str,Exception]) -> None:
        pass

    @abstractmethod
    def log_info(self, msg: str) -> None:
        pass

    @abstractmethod
    def get_gcp_function(self) -> GCPFunction:
        pass

    @abstractmethod
    def has_next(self) -> bool:
        pass

    def run(self):
        self.logger.info(f"Starting benchmark case: {self.name}")
        try {
            self.get_gcp_function().deploy_task()
        while self.has_next():
        }


