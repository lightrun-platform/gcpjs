"""Repository for saving and loading Lightrun overhead benchmark raw data."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.authentication.authenticator import AuthenticationType
from Lightrun.Benchmarks.shared_modules.benchmark_result_repository import BenchmarkResultRepository
from Lightrun.Benchmarks.shared_modules.cpu_model import CpuModel
from .lightrun_overhead_benchmark_case_dto import LightrunOverheadBenchmarkCaseDTO, BenchmarkMeasurement
from .overhead_benchmark_result import Failure, LightrunOverheadBenchmarkResult, Success

RAW_FILENAME = "benchmark_raw_data.json"


def _dict_to_dto(c: Dict[str, Any], cpu_model: str | None = None, benchmark_results: Dict[int, BenchmarkMeasurement] | None = None) -> LightrunOverheadBenchmarkCaseDTO:
    """Build LightrunOverheadBenchmarkCaseDTO from saved case dict (missing fields use defaults).
    
    Args:
        c: Dictionary of case fields
        cpu_model: Optional identified CPU model (parsed from cpu_info at load time)
        benchmark_results: Optional dict of measurement results keyed by action count
    """
    return LightrunOverheadBenchmarkCaseDTO(
        name=c.get("name", ""),
        test_size=c.get("test_size", c.get("num_actions", 0)),  # Support legacy num_actions
        region=c.get("region", ""),
        runtime=c.get("runtime", ""),
        action_type=c.get("action_type", ""),
        benchmark_name=c.get("benchmark_name", ""),
        source_code_dir=Path(c.get("source_code_dir", ".")),
        entry_point=c.get("entry_point", ""),
        project=c.get("project", ""),
        memory=c.get("memory", ""),
        cpu=c.get("cpu", ""),
        timeout=c.get("timeout", 0),
        gen2=c.get("gen2", False),
        lightrun_version=c.get("lightrun_version", ""),
        deployment_timeout_seconds=c.get("deployment_timeout_seconds", 0),
        delete_timeout_seconds=c.get("delete_timeout_seconds", 0),
        clean_after_run=c.get("clean_after_run", False),
        agent_actions_update_interval_seconds=c.get("agent_actions_update_interval_seconds", 0),
        lightrun_agent_log_level=c.get("lightrun_agent_log_level", ""),
        lightrun_company_id=c.get("lightrun_company_id", ""),
        lightrun_api_hostname=c.get("lightrun_api_hostname", ""),
        authentication_type=AuthenticationType(c["authentication_type"]) if isinstance(c.get("authentication_type"), str) else AuthenticationType.API_KEY,
        deployment_result=None,
        delete_result=None,
        cpu_model=cpu_model or c.get("cpu_model"),  # Use passed value or try from dict
        benchmark_results=benchmark_results or c.get("benchmark_results", {}),
    )


def _dto_to_dict(dto: LightrunOverheadBenchmarkCaseDTO) -> Dict[str, Any]:
    """Serialize DTO to dict for JSON (subset of fields we persist)."""
    d = {
        "name": dto.name,
        "test_size": dto.test_size,
        "region": dto.region,
        "runtime": dto.runtime,
        "action_type": dto.action_type,
        "benchmark_name": dto.benchmark_name,
        "source_code_dir": str(dto.source_code_dir),
        "entry_point": dto.entry_point,
        "project": dto.project,
        "memory": dto.memory,
        "cpu": dto.cpu,
        "timeout": dto.timeout,
        "gen2": dto.gen2,
        "lightrun_version": dto.lightrun_version,
        "deployment_timeout_seconds": dto.deployment_timeout_seconds,
        "delete_timeout_seconds": dto.delete_timeout_seconds,
        "clean_after_run": dto.clean_after_run,
        "agent_actions_update_interval_seconds": dto.agent_actions_update_interval_seconds,
        "lightrun_agent_log_level": dto.lightrun_agent_log_level,
        "lightrun_company_id": dto.lightrun_company_id,
        "lightrun_api_hostname": dto.lightrun_api_hostname,
        "authentication_type": dto.authentication_type.value,
        # Convert benchmark_results to dict for JSON serialization (keys as strings, values as dicts)
        "benchmark_results": {str(k): asdict(v) for k, v in dto.benchmark_results.items()},
    }
    if dto.cpu_model:
        d["cpu_model"] = dto.cpu_model
    return d


def _result_to_case_dict(r: LightrunOverheadBenchmarkResult) -> Dict[str, Any]:
    return _dto_to_dict(r.benchmark_dto)


class LightrunOverheadBenchmarkResultRepository(BenchmarkResultRepository[LightrunOverheadBenchmarkResult]):
    """Saves and loads overhead benchmark raw data as JSON."""

    def save_benchmark_data(
        self,
        benchmark_results: List[LightrunOverheadBenchmarkResult | None],
        save_path: Path,
    ) -> Path:
        raw_entries: List[Dict[str, Any]] = []
        for result in benchmark_results:
            if result is None:
                entry = {
                    "case": {},
                    "result": {
                        "success": False,
                        "error": "No result",
                        "cpu_info": None,
                    },
                }
            elif isinstance(result, Success):
                entry = {
                    "case": _result_to_case_dict(result),
                    "result": {
                        "success": True,
                        "handler_run_time_ns": result.handler_run_time_ns,
                        "actions_count": result.actions_count,
                        "cpu_info": result.cpu_info,
                    },
                }
            elif isinstance(result, Failure):
                entry = {
                    "case": _result_to_case_dict(result),
                    "result": {
                        "success": False,
                        "error": result.error,
                        "cpu_info": result.cpu_info,
                    },
                }
            else:
                entry = {
                    "case": {},
                    "result": {
                        "success": False,
                        "error": "Unknown result type",
                        "cpu_info": None,
                    },
                }
            raw_entries.append(entry)
        raw_path = save_path / RAW_FILENAME
        with open(raw_path, "w") as f:
            json.dump({"runs": raw_entries}, f, indent=2)
        return raw_path

    def load_benchmark_data(
        self, path: Path
    ) -> List[LightrunOverheadBenchmarkResult]:
        """Load benchmark results from the raw JSON file (same format as save).
        
        If the case dict has a stored cpu_model, uses that.
        Otherwise, identifies CPU model from cpu_info and populates it in the DTO.
        
        For new-format data with benchmark_results dict, loads that directly.
        For legacy data without benchmark_results, creates a single-entry dict.
        """
        raw_path = path / RAW_FILENAME if path.is_dir() else path
        if not raw_path.exists():
            return []
        with open(raw_path) as f:
            data = json.load(f)
        runs = data.get("runs", [])
        results: List[LightrunOverheadBenchmarkResult] = []
        for entry in runs:
            case_dict = entry.get("case", {})
            result_dict = entry.get("result", {})
            cpu_info = result_dict.get("cpu_info")
            
            # Use stored cpu_model from case dict if available, otherwise identify from cpu_info
            cpu_model = case_dict.get("cpu_model")
            if not cpu_model and cpu_info:
                cpu_model = CpuModel.identify(cpu_info).display_name
            
            # Parse benchmark_results - convert string keys back to int and dicts to BenchmarkMeasurement
            raw_benchmark_results = case_dict.get("benchmark_results", {})
            benchmark_results = {
                int(k): BenchmarkMeasurement(**v) 
                for k, v in raw_benchmark_results.items()
            } if raw_benchmark_results else {}
            
            dto = _dict_to_dto(case_dict, cpu_model=cpu_model, benchmark_results=benchmark_results)
            success = result_dict.get("success", False)
            if success:
                results.append(
                    Success(
                        benchmark_dto=dto,
                        handler_run_time_ns=result_dict["handler_run_time_ns"],
                        actions_count=result_dict["actions_count"],
                        cpu_info=cpu_info,
                    )
                )
            else:
                results.append(
                    Failure(
                        benchmark_dto=dto,
                        error=result_dict.get("error", "No result"),
                        cpu_info=cpu_info,
                    )
                )
        return results
