from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeleteFunctionResult:

    success : bool
    function_name: str
    error: Optional[Exception]
    stderr: Optional[str]