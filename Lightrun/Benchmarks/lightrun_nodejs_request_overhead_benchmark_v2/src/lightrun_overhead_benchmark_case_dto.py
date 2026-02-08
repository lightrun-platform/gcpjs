from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from Lightrun.Benchmarks.shared_modules.authentication.authenticator import AuthenticationType
from Lightrun.Benchmarks.shared_modules.gcf_models import DeploymentResult
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult


@dataclass(frozen=True)
class LightrunOverheadBenchmarkCaseDTO:
    """DTO for serialization. Excludes secrets."""

    benchmark_name: str
    name: str
    runtime: str
    region: str
    source_code_dir: Path
    entry_point: str
    num_actions: int
    action_type: str
    lightrun_company_id: str
    lightrun_api_hostname: str
    project: str
    memory: str
    cpu: str
    timeout: int
    gen2: bool
    deployment_timeout_seconds: int
    delete_timeout_seconds: int
    authentication_type: AuthenticationType
    lightrun_version: str
    clean_after_run: bool
    agent_actions_update_interval_seconds: int
    lightrun_agent_log_level: str
    deployment_result: Optional[DeploymentResult]
    delete_result: Optional[DeleteFunctionResult]
    cpu_model: Optional[str] = None  # Identified CPU microarchitecture (e.g., "AMD EPYC 3rd Gen (Milan / Zen 3)")