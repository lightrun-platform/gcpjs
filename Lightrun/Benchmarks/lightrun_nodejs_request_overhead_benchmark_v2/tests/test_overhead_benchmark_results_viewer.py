"""Unit tests for LightrunOverheadReportVisualizer."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directories to path so we can import as a package
_parent_dir = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(_parent_dir))
sys.path.insert(0, str(_parent_dir.parent.parent))

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_results_viewer import (
    LightrunOverheadReportVisualizer,
)


def _make_report_data(
    total_cases=2,
    success_count=2,
    failure_count=0,
    handler_run_time_ns=None,
    successes=None,
    by_actions_count=None,
    regression=None,
):
    """Build report_data.json structure."""
    if successes is None:
        successes = [
            {"actions_count": 1, "handler_run_time_ns": 100},
            {"actions_count": 2, "handler_run_time_ns": 200},
        ]
    if by_actions_count is None:
        by_actions_count = [
            {"actions_count": 1, "count": 1, "mean_ns": 100.0, "samples_ns": [100]},
            {"actions_count": 2, "count": 1, "mean_ns": 200.0, "samples_ns": [200]},
        ]
    if regression is None:
        regression = {
            "slope_ns_per_action": 100.0,
            "intercept_ns": 0.0,
            "r_squared": 1.0,
        }
    summary = {
        "total_cases": total_cases,
        "success_count": success_count,
        "failure_count": failure_count,
    }
    if handler_run_time_ns is not None:
        summary["handler_run_time_ns"] = handler_run_time_ns
    return {
        "summary": summary,
        "successes": successes,
        "by_actions_count": by_actions_count,
        "regression": regression,
    }


class TestLightrunOverheadReportVisualizer(unittest.TestCase):
    """Tests for LightrunOverheadReportVisualizer."""

    def setUp(self):
        self.visualizer = LightrunOverheadReportVisualizer()

    def test_display_no_op_when_path_none(self):
        """display() does nothing when _visualizations_path is None."""
        self.visualizer._visualizations_path = None
        with patch("subprocess.run") as run_mock:
            self.visualizer.display()
        run_mock.assert_not_called()

    def test_display_no_op_when_path_missing(self):
        """display() does nothing when _visualizations_path does not exist."""
        self.visualizer._visualizations_path = Path("/nonexistent/viz.html")
        with patch("subprocess.run") as run_mock:
            self.visualizer.display()
        run_mock.assert_not_called()

    def test_display_opens_file_on_darwin(self):
        """On darwin, display() runs 'open' with the resolved path."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(b"<html></html>")
            viz_path = Path(f.name)
        try:
            self.visualizer._visualizations_path = viz_path
            with patch("subprocess.run") as run_mock:
                with patch("sys.platform", "darwin"):
                    self.visualizer.display()
            run_mock.assert_called_once()
            call_args = run_mock.call_args[0][0]
            self.assertEqual(call_args[0], "open")
            self.assertEqual(call_args[1], str(viz_path.resolve()))
        finally:
            viz_path.unlink(missing_ok=True)

    def test_display_uses_webbrowser_on_non_darwin(self):
        """On non-darwin, display() uses webbrowser.open with file URI."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(b"<html></html>")
            viz_path = Path(f.name)
        try:
            self.visualizer._visualizations_path = viz_path
            with patch("sys.platform", "linux"):
                with patch("webbrowser.open") as open_mock:
                    self.visualizer.display()
                    open_mock.assert_called_once()
                    uri = open_mock.call_args[0][0]
                    self.assertTrue(uri.startswith("file://"))
                    self.assertIn(str(viz_path.resolve()), uri)
        finally:
            viz_path.unlink(missing_ok=True)

    def test_create_visualizations_missing_report_data(self):
        """When report_data.json is missing, writes fallback HTML and returns path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            report_path = save_path / "benchmark_report.txt"
            report_path.touch()
            out = self.visualizer.create_visualizations(report_path, save_path)
            self.assertEqual(out, save_path / "visualizations.html")
            self.assertTrue(out.exists())
            content = out.read_text()
            self.assertIn("No report data", content)
            self.assertIn("report_data.json not found", content)
            self.assertEqual(self.visualizer._visualizations_path, out)

    def test_create_visualizations_with_data_includes_summary_table(self):
        """When report_data.json exists, HTML includes summary table."""
        data = _make_report_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertIn("Summary", content)
            self.assertIn("Total cases", content)
            self.assertIn("2", content)
            self.assertIn("Successes", content)
            self.assertIn("Failures", content)

    def test_create_visualizations_includes_handler_run_time_when_present(self):
        """Handler run time table is included when summary has handler_run_time_ns."""
        data = _make_report_data(
            handler_run_time_ns={
                "min": 50,
                "max": 150,
                "mean": 100.0,
                "median": 100.0,
                "stdev": 10.0,
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertIn("Handler run time", content)
            self.assertIn("Min", content)
            self.assertIn("Max", content)
            self.assertIn("100", content)

    def test_create_visualizations_includes_regression_table(self):
        """Regression section (slope, intercept, R²) is in HTML when present."""
        data = _make_report_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertIn("Linear fit", content)
            self.assertIn("Slope (ns per action)", content)
            self.assertIn("Intercept (ns)", content)
            self.assertIn("R²", content)
            self.assertIn("100.00", content)
            self.assertIn("0.00", content)
            self.assertIn("1.0000", content)

    def test_create_visualizations_embeds_scatter_and_line_data(self):
        """HTML contains Chart.js and embedded scatter + line data."""
        data = _make_report_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertIn("chart.js", content.lower())
            self.assertIn("scatterData", content)
            self.assertIn("lineData", content)
            self.assertIn('"x": 1', content)
            self.assertIn('"y": 100', content)
            self.assertIn("Benchmark length vs number of Lightrun actions", content)

    def test_create_visualizations_sets_visualizations_path(self):
        """After create_visualizations, _visualizations_path is set for display()."""
        data = _make_report_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            self.assertEqual(self.visualizer._visualizations_path, save_path / "visualizations.html")
            self.assertEqual(self.visualizer._visualizations_path, out)

    def test_create_visualizations_empty_successes_no_regression_line(self):
        """When successes is empty, regression line data is empty but HTML still valid."""
        data = _make_report_data(
            success_count=0,
            failure_count=2,
            successes=[],
            by_actions_count=[],
            regression={},
        )
        data["summary"].pop("handler_run_time_ns", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertIn("Total cases", content)
            self.assertIn("Failures", content)
            self.assertIn("2", content)
            # Chart data should be empty arrays
            self.assertIn("scatterData", content)
            self.assertIn("lineData", content)

    def test_create_visualizations_valid_html_structure(self):
        """Generated HTML has DOCTYPE, head, body, and required elements."""
        data = _make_report_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with open(save_path / "report_data.json", "w") as f:
                json.dump(data, f, indent=2)
            out = self.visualizer.create_visualizations(save_path / "report.txt", save_path)
            content = out.read_text()
            self.assertTrue(content.strip().startswith("<!DOCTYPE html>"))
            self.assertIn("<html", content)
            self.assertIn("</html>", content)
            self.assertIn("<head>", content)
            self.assertIn("<body>", content)
            self.assertIn("Lightrun Request Overhead Benchmark", content)
            self.assertIn("chartContainer", content)
            self.assertIn("canvas", content)
            self.assertIn("id=\"chart\"", content)


if __name__ == "__main__":
    unittest.main()
