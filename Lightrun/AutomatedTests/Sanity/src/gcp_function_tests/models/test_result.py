"""TestResult model."""
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict
from .deployment_result import DeploymentResult


@dataclass
class TestResult:
    """Test result for a single function."""
    function_name: str
    gen_version: int
    nodejs_version: int
    deployment_result: Optional[DeploymentResult] = None
    # Legacy fields for backward compatibility (derived from deployment_result)
    deployment_error: Optional[str] = None
    region_used: Optional[str] = None
    cold_start_avg_ms: Optional[float] = None
    warm_start_avg_ms: Optional[float] = None
    cold_start_requests: int = 0
    warm_start_requests: int = 0
    logs_error_check: Optional[bool] = None
    logs_error_message: Optional[str] = None
    snapshot_test: Optional[bool] = None
    snapshot_error: Optional[str] = None
    counter_test: Optional[bool] = None
    counter_error: Optional[str] = None
    metric_test: Optional[bool] = None
    metric_error: Optional[str] = None
    function_url: Optional[str] = None
    cleanup_error: Optional[str] = None
    
    @property
    def deployment_success(self) -> bool:
        """Computed property: True if deployment_result exists and is successful."""
        return self.deployment_result is not None and self.deployment_result.success
    
    @property
    def cleanup_success(self) -> bool:
        """Computed property: True if cleanup_error is None (no error means success)."""
        return self.cleanup_error is None
    
    def to_dictionary(self) -> Dict[str, Any]:
        """Convert TestResult to dictionary, including computed properties."""
        # Start with dataclass fields
        result_dict = asdict(self)
        
        # Add computed properties (those decorated with @property)
        for name, attr in self.__class__.__dict__.items():
            if isinstance(attr, property):
                try:
                    value = getattr(self, name)
                    result_dict[name] = value
                except Exception:
                    # Skip properties that raise exceptions
                    pass
        
        # Convert nested dataclass objects to dictionaries
        if self.deployment_result:
            result_dict["deployment_result"] = asdict(self.deployment_result)
        
        return result_dict