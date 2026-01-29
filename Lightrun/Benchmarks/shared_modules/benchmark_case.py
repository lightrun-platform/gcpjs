from abc import ABC, abstractmethod
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from typing import Union

class BenchmarkCase[T](ABC):

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
    def run(self):
        pass