"""DeploymentResult model."""
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from streamlit import success


@dataclass(frozen=True, kw_only=True)
class DeploymentResult(ABC):
    """Result of a GCP Cloud Function deployment. Immutable."""
    used_region: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'used_region': self.used_region
        }


@dataclass(frozen=True, kw_only=True)
class DeploymentSuccess(DeploymentResult):
    """Successful deployment result."""
    url: str
    deployment_duration_seconds: float
    deployment_duration_nanoseconds: int
    deploy_time: str

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'url': self.url,
            'deployment_duration_seconds': self.deployment_duration_seconds,
            'deployment_duration_nanoseconds': self.deployment_duration_nanoseconds,
            'deploy_time': self.deploy_time,
            'success': True
        })
        return d


@dataclass(frozen=True, kw_only=True)
class DeploymentFailure(DeploymentResult):
    """Failed deployment result."""
    error: str

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'error': self.error,
            'success': False
        })
        return d
