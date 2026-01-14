"""DeploymentResult model."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeploymentResult:
    """Result of a GCP Cloud Function deployment. Immutable."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    used_region: Optional[str] = None
