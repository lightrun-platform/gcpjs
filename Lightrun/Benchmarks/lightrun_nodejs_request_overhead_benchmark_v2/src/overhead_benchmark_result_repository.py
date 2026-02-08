"""Repository for saving and loading Lightrun overhead benchmark raw data."""

import json
from pathlib import Path
from typing import List, Dict, Any

from Lightrun.Benchmarks.shared_modules.benchmark_result_repository import (
    BenchmarkResultRepository,
)
from .overhead_benchmark_result import (
    OverheadBenchmarkCaseDTO,
    LightrunOverheadBenchmarkResult,
    Success,
    LightrunOverheadBenchmarkFailure,
)

RAW_FILENAME = "benchmark_raw_data.json"


def _identity_to_dict(identity: OverheadBenchmarkCaseDTO) -> Dict[str, Any]:
    """Serialize case identity to JSON-suitable dict."""
    return {
        "name": identity.name,
        "num_actions": identity.num_actions,
        "region": identity.region,
        "runtime": identity.runtime,
        "action_type": identity.action_type,
        "benchmark_name": identity.benchmark_name,
        "source_code_dir": str(identity.source_code_dir),
        "entry_point": identity.entry_point,
        "project": identity.project,
        "memory": identity.memory,
        "cpu": identity.cpu,
        "timeout": identity.timeout,
        "gen2": identity.gen2,
        "lightrun_version": identity.lightrun_version,
        "deployment_timeout_seconds": identity.deployment_timeout_seconds,
        "delete_timeout_seconds": identity.delete_timeout_seconds,
        "clean_after_run": identity.clean_after_run,
        "agent_actions_update_interval_seconds": identity.agent_actions_update_interval_seconds,
        "lightrun_agent_log_level": identity.lightrun_agent_log_level,
    }


def _dict_to_identity(c: Dict[str, Any]) -> OverheadBenchmarkCaseDTO:
    """Build OverheadBenchmarkCaseIdentity from saved case dict."""
    return OverheadBenchmarkCaseDTO(
        name=c.get("name", ""),
        num_actions=c.get("num_actions", 0),
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
        agent_actions_update_interval_seconds=c.get(
            "agent_actions_update_interval_seconds", 0
        ),
        lightrun_agent_log_level=c.get("lightrun_agent_log_level", ""),
    )


def _result_to_case_dict(r: LightrunOverheadBenchmarkResult) -> Dict[str, Any]:
    """Serialize case identity from a result for JSON."""
    return _identity_to_dict(r.benchmark_props_dto)


class LightrunOverheadBenchmarkResultRepository(
    BenchmarkResultRepository[LightrunOverheadBenchmarkResult]
):
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
            elif isinstance(result, LightrunOverheadBenchmarkFailure):
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
        """Load benchmark results from the raw JSON file (same format as save)."""
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
            identity = _dict_to_identity(case_dict)
            success = result_dict.get("success", False)
            if success:
                results.append(
                    Success(
                        benchmark_props=identity,
                        handler_run_time_ns=result_dict["handler_run_time_ns"],
                        actions_count=result_dict["actions_count"],
                        cpu_info=result_dict["cpu_info"],
                    )
                )
            else:
                results.append(
                    LightrunOverheadBenchmarkFailure(
                        benchmark_dto=identity,
                        error=result_dict.get("error", "No result"),
                        cpu_info=result_dict.get("cpu_info"),
                    )
                )
        return results
