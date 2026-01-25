"""DeploymentResult model."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class DeploymentResult:
    """Result of a GCP Cloud Function deployment. Immutable."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    used_region: Optional[str] = None
    deployment_duration_seconds: Optional[float] = None
    deployment_duration_nanoseconds: Optional[int] = None
    deploy_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'url': self.url,
            'error': self.error,
            'used_region': self.used_region,
            'deployment_duration_seconds': self.deployment_duration_seconds,
            'deployment_duration_nanoseconds': self.deployment_duration_nanoseconds,
            'deploy_time': self.deploy_time
        }
