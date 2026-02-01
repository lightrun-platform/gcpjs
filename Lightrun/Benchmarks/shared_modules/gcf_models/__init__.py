"""Models package for cold start testing."""
from .deploy_function_result import DeploymentResult
from .gcp_function import GCPFunction

__all__ = ['DeploymentResult', 'GCPFunction']
