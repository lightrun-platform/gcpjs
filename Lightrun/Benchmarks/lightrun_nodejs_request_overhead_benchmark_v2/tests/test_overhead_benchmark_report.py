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

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_report import (
    LightrunOverheadReportGenerator,
    _linear_regression,
)
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import (
    LightrunOverheadBenchmarkFailure,
    LightrunOverheadBenchmarkSuccess,
)


def _make_fake_case(name="fake", num_actions=0, region="r", runtime="nodejs20", action_type="snapshot", benchmark_result=None):
    """Minimal case-like object for generator tests."""
    obj = MagicMock()
    obj.name = name
    obj.num_actions = num_actions
    obj.region = region
    obj.runtime = runtime
    obj.action_type = action_type
    obj.benchmark_result = benchmark_result
    return obj


def _make_success(handler_run_time_ns, actions_count, cpu_info="cpu"):
    return LightrunOverheadBenchmarkSuccess(
        benchmark_case=MagicMock(),
        handler_run_time_ns=handler_run_time_ns,
        actions_count=actions_count,
        cpu_info=cpu_info,
    )


def _make_failure(error="err", cpu_info=None):
    return LightrunOverheadBenchmarkFailure(
        benchmark_case=MagicMock(),
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

    def test_save_benchmark_data_skips_non_overhead_case(self):
        """Only LightrunOverheadBenchmarkCase instances are persisted."""
        class FakeOverheadCase:
            def __init__(self):
                self.name = "only-case"
                self.num_actions = 1
                self.region = "us-central1"
                self.runtime = "nodejs20"
                self.action_type = "snapshot"
                self.benchmark_result = _make_success(100, 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            with patch(
                "Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_report.LightrunOverheadBenchmarkCase",
                FakeOverheadCase,
            ):
                out = self.generator.save_benchmark_data(
                    [FakeOverheadCase()],
                    path,
                )
            self.assertEqual(out, path / "benchmark_raw_data.json")
            self.assertTrue(out.exists())
            with open(out) as f:
                data = json.load(f)
            self.assertIn("runs", data)
            self.assertEqual(len(data["runs"]), 1)
            self.assertEqual(data["runs"][0]["case"]["name"], "only-case")
            self.assertTrue(data["runs"][0]["result"]["success"])
            self.assertEqual(data["runs"][0]["result"]["handler_run_time_ns"], 100)

    def test_save_benchmark_data_ignores_generic_benchmark_case(self):
        """Generic BenchmarkCase (not LightrunOverheadBenchmarkCase) is skipped."""
        generic_case = _make_fake_case(name="generic", benchmark_result=_make_success(200, 2))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            # Do not patch: real generator uses real LightrunOverheadBenchmarkCase
            out = self.generator.save_benchmark_data([generic_case], path)
            self.assertTrue(out.exists())
            with open(out) as f:
                data = json.load(f)
            self.assertEqual(len(data["runs"]), 0)

    def test_save_benchmark_data_records_success_and_failure(self):
        """Raw data includes both success and failure results."""
        class FakeOverheadCase:
            def __init__(self, name, result):
                self.name = name
                self.num_actions = 0
                self.region = "r"
                self.runtime = "nodejs20"
                self.action_type = "snapshot"
                self.benchmark_result = result

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            cases = [
                FakeOverheadCase("s1", _make_success(100, 1)),
                FakeOverheadCase("f1", _make_failure("deploy failed")),
                FakeOverheadCase("none", None),
            ]
            with patch(
                "Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_report.LightrunOverheadBenchmarkCase",
                FakeOverheadCase,
            ):
                self.generator.save_benchmark_data(cases, path)
            with open(path / "benchmark_raw_data.json") as f:
                data = json.load(f)
            self.assertEqual(len(data["runs"]), 3)
            self.assertTrue(data["runs"][0]["result"]["success"])
            self.assertFalse(data["runs"][1]["result"]["success"])
            self.assertEqual(data["runs"][1]["result"]["error"], "deploy failed")
            self.assertFalse(data["runs"][2]["result"]["success"])
            self.assertEqual(data["runs"][2]["result"]["error"], "No result")

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
            self.assertEqual(data["successes"], [])
            self.assertEqual(data["regression"], {})
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
            self.assertNotIn("handler_run_time_ns", data["summary"])
            self.assertEqual(data["regression"], {})

    def test_generate_report_single_success_no_regression(self):
        """Single success: stats present, regression empty (need >=2 points)."""
        cases = [_make_fake_case(benchmark_result=_make_success(50_000, 1))]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            self.generator.generate_report(cases, path)
            with open(path / "report_data.json") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["success_count"], 1)
            self.assertEqual(data["summary"]["handler_run_time_ns"]["min"], 50_000)
            self.assertEqual(data["summary"]["handler_run_time_ns"]["max"], 50_000)
            self.assertEqual(data["summary"]["handler_run_time_ns"]["mean"], 50_000)
            self.assertEqual(data["regression"], {})

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
            reg = data["regression"]
            self.assertIn("slope_ns_per_action", reg)
            self.assertIn("intercept_ns", reg)
            self.assertIn("r_squared", reg)
            self.assertAlmostEqual(reg["slope_ns_per_action"], 50.0, places=2)
            self.assertAlmostEqual(reg["intercept_ns"], 100.0, places=2)

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
            by_actions = data["by_actions_count"]
            self.assertEqual(len(by_actions), 2)
            one = next(r for r in by_actions if r["actions_count"] == 1)
            two = next(r for r in by_actions if r["actions_count"] == 2)
            self.assertEqual(one["count"], 2)
            self.assertEqual(one["mean_ns"], 150.0)
            self.assertEqual(one["samples_ns"], [100, 200])
            self.assertEqual(two["count"], 1)
            self.assertEqual(two["mean_ns"], 400.0)

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
            self.assertIn("Handler run time (ns):", content)
            self.assertIn("Linear fit:", content)
            self.assertIn("Slope (ns per action)", content)
            self.assertIn("R²", content)

    def test_generate_report_writes_report_data_json_for_visualizer(self):
        """report_data.json has structure expected by visualizer (summary, successes, regression)."""
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
            self.assertIn("successes", data)
            self.assertIn("by_actions_count", data)
            self.assertIn("regression", data)
            self.assertEqual(len(data["successes"]), 2)
            self.assertEqual(data["successes"][0]["actions_count"], 1)
            self.assertEqual(data["successes"][0]["handler_run_time_ns"], 100)


if __name__ == "__main__":
    unittest.main()
