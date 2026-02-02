"""DeploymentResult model."""
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from Benchmarks.shared_modules.cloud_assets import CloudAsset


@dataclass(frozen=True, kw_only=True)
class DeploymentResult(ABC):
    """Result of a GCP Cloud Function deployment. Immutable."""
    used_region: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'used_region': self.used_region
        }


@dataclass(frozen=True, kw_only=True)
class DeploymentSuccess(DeploymentResult):
    """Successful deployment result."""
    url: str
    deployment_duration_seconds: float
    deployment_duration_nanoseconds: int
    deploy_time: str
    assets: List[CloudAsset] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'url': self.url,
            'deployment_duration_seconds': self.deployment_duration_seconds,
            'deployment_duration_nanoseconds': self.deployment_duration_nanoseconds,
            'deploy_time': self.deploy_time,
            'success': True,
            'assets': [a.name for a in self.assets]
        })
        return d


@dataclass(frozen=True, kw_only=True)
class DeploymentFailure(DeploymentResult):
    """Failed deployment result."""
    error: str
    partial_assets: List[Any] = field(default_factory=list)  # List[CloudAsset]

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'error': self.error,
            'success': False,
            'partial_assets': [a.name for a in self.partial_assets]
        })
        return d
