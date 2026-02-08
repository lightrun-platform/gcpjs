from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict

from Lightrun.Benchmarks.shared_modules.authentication.authenticator import AuthenticationType
from Lightrun.Benchmarks.shared_modules.gcf_models import DeploymentResult
from Lightrun.Benchmarks.shared_modules.gcf_models.delete_function_result import DeleteFunctionResult


@dataclass(frozen=True)
class BenchmarkMeasurement:
    """Result of a single measurement (one action count)."""
    success: bool
    actions_count: int
    handler_run_time_ns: Optional[int] = None  # Only present on success
    error: Optional[str] = None  # Only present on failure
    cpu_info: Optional[str] = None


@dataclass(frozen=True)
class LightrunOverheadBenchmarkCaseDTO:
    """DTO for serialization. Excludes secrets."""

    benchmark_name: str
    name: str
    runtime: str
    region: str
    source_code_dir: Path
    entry_point: str
    test_size: int  # Maximum number of actions tested (tests 0 to test_size)
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
    # Results for each action count tested (key: num_actions, value: measurement result)
    benchmark_results: Dict[int, BenchmarkMeasurement] = field(default_factory=dict)