from abc import ABC, abstractmethod
from typing import Any

from Lightrun.Benchmarks.shared_modules.gcf_models.generated_source_attributes import GeneratedSourceAttributes


class SourceCodeGenerator(ABC):
    """Abstract base class for generating source code directories."""

    @abstractmethod
    def create_source_dir(self, *args: Any, **kwargs: Any) -> GeneratedSourceAttributes:
        """
        Create a source code directory.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
            
        Returns:
            Path to the generated source directory
        """
        pass
