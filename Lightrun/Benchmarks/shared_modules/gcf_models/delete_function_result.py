from abc import ABC
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class DeleteFunctionResult(ABC):
    """Result of a GCP Cloud Function deletion. Abstract base class."""
    function_name: str


@dataclass(frozen=True, kw_only=True)
class DeleteSuccess(DeleteFunctionResult):
    """Successful deletion result."""
    pass


@dataclass(frozen=True, kw_only=True)
class DeleteFailure(DeleteFunctionResult):
    """Failed deletion result."""
    error: Exception
    stderr: Optional[str]