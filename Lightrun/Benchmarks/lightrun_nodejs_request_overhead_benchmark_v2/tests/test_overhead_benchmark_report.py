"""Unit tests for LightrunOverheadReportGenerator."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directories to path so we can import as a package
_parent_dir = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(_parent_dir))
sys.path.insert(0, str(_parent_dir.parent.parent))
# overhead_benchmark_report imports overhead_benchmark_case which uses "from Benchmarks.shared_modules..."
# Register Lightrun.Benchmarks as Benchmarks so that import resolves.
import Lightrun.Benchmarks  # noqa: E402
sys.modules["Benchmarks"] = Lightrun.Benchmarks

from Lightrun.Benchmarks.shared_modules.authentication.authenticator import AuthenticationType
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.lightrun_overhead_benchmark_case_dto import LightrunOverheadBenchmarkCaseDTO
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_report import LightrunOverheadReportGenerator, _linear_regression
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import Failure, Success
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result_repository import LightrunOverheadBenchmarkResultRepository, RAW_FILENAME


def _make_fake_case(name="fake", num_actions=0, region="r", runtime="nodejs20", action_type="snapshot", benchmark_result=None):
    """Minimal case-like object for generator tests (get_benchmark_result returns the result)."""
    obj = MagicMock()
    obj.name = name
    obj.test_size = num_actions
    obj.region = region
    obj.runtime = runtime
    obj.action_type = action_type
    obj.get_benchmark_result = MagicMock(return_value=benchmark_result)
    return obj


def _default_dto(cpu_model: str | None = "Intel Xeon 2nd Gen (Cascade Lake)", benchmark_results=None) -> LightrunOverheadBenchmarkCaseDTO:
    """Minimal DTO for test result construction.
    
    benchmark_results should be a Dict[int, BenchmarkMeasurement] if provided.
    """
    from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.lightrun_overhead_benchmark_case_dto import BenchmarkMeasurement
    return LightrunOverheadBenchmarkCaseDTO(
        benchmark_name="bench",
        name="fake",
        runtime="nodejs20",
        region="r",
        source_code_dir=Path("."),
        entry_point="index.js",
        test_size=0,
        action_type="snapshot",
        lightrun_company_id="",
        lightrun_api_hostname="",
        project="p",
        memory="256Mi",
        cpu="1",
        timeout=60,
        gen2=False,
        deployment_timeout_seconds=300,
        delete_timeout_seconds=120,
        authentication_type=AuthenticationType.API_KEY,
        lightrun_version="",
        clean_after_run=False,
        agent_actions_update_interval_seconds=0,
        lightrun_agent_log_level="",
        deployment_result=None,
        delete_result=None,
        cpu_model=cpu_model,
        benchmark_results=benchmark_results if benchmark_results is not None else {},
    )


def _make_success(handler_run_time_ns, actions_count, cpu_info="cpu", cpu_model="Intel Xeon 2nd Gen (Cascade Lake)"):
    """Build a success result with default case DTO (for tests)."""
    return Success(
        benchmark_dto=_default_dto(cpu_model=cpu_model),
        handler_run_time_ns=handler_run_time_ns,
        actions_count=actions_count,
        cpu_info=cpu_info,
    )


def _make_failure(error="err", cpu_info=None, cpu_model="Intel Xeon 2nd Gen (Cascade Lake)"):
    """Build a failure result with default case DTO (for tests)."""
    return Failure(
        benchmark_dto=_default_dto(cpu_model=cpu_model),
        error=error,
        cpu_info=cpu_info,
    )


class TestLinearRegression(unittest.TestCase):
    """Tests for _linear_regression helper."""

    def test_empty_x_y_returns_zero_slope_intercept_r2(self):
        slope, intercept, r2 = _linear_regression([], [])
        self.assertEqual(slope, 0.0)
        self.assertEqual(intercept, 0.0)
        self.assertEqual(r2, 0.0)

    def test_single_point_returns_zero_slope_r2(self):
        slope, intercept, r2 = _linear_regression([1.0], [10.0])
        self.assertEqual(slope, 0.0)
        self.assertEqual(intercept, 10.0)
        self.assertEqual(r2, 0.0)

    def test_perfect_line(self):
        x = [1.0, 2.0, 3.0]
        y = [5.0, 7.0, 9.0]  # y = 3 + 2*x (perfect line)
        slope, intercept, r2 = _linear_regression(x, y)
        self.assertAlmostEqual(slope, 2.0, places=5)
        self.assertAlmostEqual(intercept, 3.0, places=5)
        self.assertAlmostEqual(r2, 1.0, places=5)

    def test_constant_x_returns_zero_slope(self):
        slope, intercept, r2 = _linear_regression([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])
        self.assertEqual(slope, 0.0)
        self.assertAlmostEqual(intercept, 2.0, places=5)
        self.assertEqual(r2, 0.0)


class TestLightrunOverheadReportGenerator(unittest.TestCase):
    """Tests for LightrunOverheadReportGenerator."""

    def setUp(self):
        self.generator = LightrunOverheadReportGenerator()

    def test_repository_save_then_load_roundtrip(self):
        """Repository save_benchmark_data then load_benchmark_data returns equivalent results."""
        repo = LightrunOverheadBenchmarkResultRepository()
        results = [
            _make_success(100, 1),
            _make_failure("deploy failed"),
            None,
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            out = repo.save_benchmark_data(results, path)
            self.assertEqual(out, path / RAW_FILENAME)
            self.assertTrue(out.exists())
            loaded = repo.load_benchmark_data(path)
            self.assertEqual(len(loaded), 3)
            self.assertIsInstance(loaded[0], Success)
            self.assertEqual(loaded[0].handler_run_time_ns, 100)
            self.assertEqual(loaded[0].actions_count, 1)
            self.assertIsInstance(loaded[1], Failure)
            self.assertEqual(loaded[1].error, "deploy failed")
            self.assertIsInstance(loaded[2], Failure)
            self.assertEqual(loaded[2].error, "No result")

    def test_load_benchmark_data_missing_file_returns_empty_list(self):
        """Report generator load_benchmark_data returns [] when file does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            loaded = self.generator.load_benchmark_data(path)
            self.assertEqual(loaded, [])

    def test_load_benchmark_data_then_generate_report_from_results(self):
        """Load raw data then generate_report_from_results produces same report shape as from cases."""
        repo = LightrunOverheadBenchmarkResultRepository()
        results = [
            _make_success(100, 0),
            _make_success(150, 1),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            repo.save_benchmark_data(results, path)
            loaded = self.generator.load_benchmark_data(path)
            self.assertEqual(len(loaded), 2)
            report_path = self.generator.generate_report_from_results(loaded, path)
            self.assertTrue(report_path.exists())
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["total_cases"], 2)
            self.assertEqual(data["summary"]["success_count"], 2)
            # Check by_allocation (backward compat)
            alloc = data["by_allocation"]["256Mi-1"]
            self.assertAlmostEqual(
                alloc["regression"]["slope_ns_per_action"], 50.0, places=2
            )
            # Check by_group (new structure)
            self.assertIn("by_group", data)
            group_key = "256Mi-1|Intel Xeon 2nd Gen (Cascade Lake)"
            self.assertIn(group_key, data["by_group"])
            group = data["by_group"][group_key]
            self.assertAlmostEqual(
                group["regression"]["slope_ns_per_action"], 50.0, places=2
            )

    def test_generate_report_empty_results(self):
        """Report with no cases produces valid summary and no regression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            report_path = self.generator.generate_report([], path)
            self.assertEqual(report_path, path / "benchmark_report.txt")
            self.assertTrue(report_path.exists())
            data_path = path / "report_data.json"
            self.assertTrue(data_path.exists())
            with open(data_path) as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["total_cases"], 0)
            self.assertEqual(data["summary"]["success_count"], 0)
            self.assertEqual(data["summary"]["failure_count"], 0)
            self.assertEqual(data["by_allocation"], {})
            self.assertEqual(data["by_group"], {})
            content = report_path.read_text()
            self.assertIn("Total cases:     0", content)
            self.assertIn("Failures:       0", content)

    def test_generate_report_all_failures(self):
        """All failures: no handler_run_time stats, no regression."""
        cases = [
            _make_fake_case(benchmark_result=None),
            _make_fake_case(benchmark_result=_make_failure("err1")),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["total_cases"], 2)
            self.assertEqual(data["summary"]["success_count"], 0)
            self.assertEqual(data["summary"]["failure_count"], 2)
            self.assertEqual(data["by_allocation"], {})
            self.assertEqual(data["by_group"], {})

    def test_generate_report_single_success_no_regression(self):
        """Single success: stats present, regression empty (need >=2 points)."""
        cases = [_make_fake_case(benchmark_result=_make_success(50_000, 1))]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["success_count"], 1)
            # Check by_allocation
            alloc = data["by_allocation"]["256Mi-1"]
            self.assertEqual(alloc["summary"]["handler_run_time_ns"]["min"], 50_000)
            self.assertEqual(alloc["summary"]["handler_run_time_ns"]["max"], 50_000)
            self.assertEqual(alloc["summary"]["handler_run_time_ns"]["mean"], 50_000)
            self.assertEqual(alloc["regression"], {})
            # Check by_group
            group_key = "256Mi-1|Intel Xeon 2nd Gen (Cascade Lake)"
            group = data["by_group"][group_key]
            self.assertEqual(group["summary"]["handler_run_time_ns"]["min"], 50_000)
            self.assertEqual(group["regression"], {})

    def test_generate_report_two_successes_produces_regression(self):
        """Two or more successes produce regression slope, intercept, r_squared."""
        cases = [
            _make_fake_case(benchmark_result=_make_success(100, 0)),
            _make_fake_case(benchmark_result=_make_success(150, 1)),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["success_count"], 2)
            # Check by_allocation regression
            reg = data["by_allocation"]["256Mi-1"]["regression"]
            self.assertIn("slope_ns_per_action", reg)
            self.assertIn("intercept_ns", reg)
            self.assertIn("r_squared", reg)
            self.assertAlmostEqual(reg["slope_ns_per_action"], 50.0, places=2)
            self.assertAlmostEqual(reg["intercept_ns"], 100.0, places=2)
            # Check by_group regression
            group_key = "256Mi-1|Intel Xeon 2nd Gen (Cascade Lake)"
            group_reg = data["by_group"][group_key]["regression"]
            self.assertAlmostEqual(group_reg["slope_ns_per_action"], 50.0, places=2)
            self.assertAlmostEqual(group_reg["intercept_ns"], 100.0, places=2)

    def test_generate_report_by_actions_count_aggregation(self):
        """by_actions_count groups by actions_count with mean and samples."""
        cases = [
            _make_fake_case(benchmark_result=_make_success(100, 1)),
            _make_fake_case(benchmark_result=_make_success(200, 1)),
            _make_fake_case(benchmark_result=_make_success(400, 2)),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            # Check by_allocation
            by_actions = data["by_allocation"]["256Mi-1"]["by_actions_count"]
            self.assertEqual(len(by_actions), 2)
            one = next(r for r in by_actions if r["actions_count"] == 1)
            two = next(r for r in by_actions if r["actions_count"] == 2)
            self.assertEqual(one["count"], 2)
            self.assertEqual(one["mean_ns"], 150.0)
            self.assertEqual(one["samples_ns"], [100, 200])
            self.assertEqual(two["count"], 1)
            self.assertEqual(two["mean_ns"], 400.0)
            # Check by_group
            group_key = "256Mi-1|Intel Xeon 2nd Gen (Cascade Lake)"
            group_by_actions = data["by_group"][group_key]["by_actions_count"]
            self.assertEqual(len(group_by_actions), 2)

    def test_generate_report_txt_contains_summary_and_regression(self):
        """Human-readable report contains totals and regression line when applicable."""
        cases = [
            _make_fake_case(benchmark_result=_make_success(100, 0)),
            _make_fake_case(benchmark_result=_make_success(200, 1)),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            report_path = self.generator.generate_report(cases, path)
            content = report_path.read_text()
            self.assertIn("Lightrun Request Overhead Benchmark Report", content)
            self.assertIn("Total cases:     2", content)
            self.assertIn("Successes:      2", content)
            # Check for new group-based structure
            self.assertIn("RESULTS BY GROUP", content)
            self.assertIn("Group: 256Mi / 1 CPU | Intel Xeon 2nd Gen (Cascade Lake)", content)
            self.assertIn("Handler run time (ns):", content)
            self.assertIn("Linear fit:", content)
            self.assertIn("Slope (ns per action)", content)
            self.assertIn("R²", content)
            # Check for allocation section
            self.assertIn("RESULTS BY ALLOCATION", content)
            self.assertIn("Allocation: 256Mi / 1 CPU", content)

    def test_generate_report_writes_report_data_json_for_visualizer(self):
        """report_data.json has structure expected by visualizer (summary, by_allocation, by_group)."""
        cases = [
            _make_fake_case(benchmark_result=_make_success(100, 1)),
            _make_fake_case(benchmark_result=_make_success(200, 2)),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertIn("summary", data)
            self.assertIn("by_allocation", data)
            self.assertIn("by_group", data)
            # Check by_allocation
            alloc = data["by_allocation"]["256Mi-1"]
            self.assertIn("successes", alloc)
            self.assertIn("by_actions_count", alloc)
            self.assertIn("regression", alloc)
            self.assertEqual(len(alloc["successes"]), 2)
            self.assertEqual(alloc["successes"][0]["actions_count"], 1)
            self.assertEqual(alloc["successes"][0]["handler_run_time_ns"], 100)
            # Check by_group
            group_key = "256Mi-1|Intel Xeon 2nd Gen (Cascade Lake)"
            group = data["by_group"][group_key]
            self.assertIn("cpu_model", group)
            self.assertEqual(group["cpu_model"], "Intel Xeon 2nd Gen (Cascade Lake)")
            self.assertIn("successes", group)
            self.assertEqual(len(group["successes"]), 2)


if __name__ == "__main__":
    unittest.main()
