import json
import subprocess
import sys
from pathlib import Path

from Lightrun.Benchmarks.shared_modules.benchmark_results_visualizer import (
    BenchmarkResultsVisualizer,
)
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult


class LightrunOverheadReportVisualizer(
    BenchmarkResultsVisualizer[LightrunOverheadBenchmarkResult]
):
    """Visualizes results for Lightrun overhead benchmark: summary and regression plot."""

    def __init__(self) -> None:
        self._visualizations_path: Path | None = None

    def display(self) -> None:
        """Open the visualizations.html file in the default browser."""
        if self._visualizations_path is None or not self._visualizations_path.exists():
            return
        path = self._visualizations_path.resolve()
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            import webbrowser
            webbrowser.open(path.as_uri())

    def create_visualizations(
        self, benchmark_report: Path, save_path: Path
    ) -> Path:
        """Creates the visualizations (summary + graph) and saves them in save_path."""
        data_path = save_path / "report_data.json"
        if not data_path.exists():
            viz_path = save_path / "visualizations.html"
            with open(viz_path, "w") as f:
                f.write(
                    "<html><body><h1>No report data</h1><p>report_data.json not found.</p></body></html>"
                )
            self._visualizations_path = viz_path
            return viz_path

        with open(data_path) as f:
            data = json.load(f)

        summary = data.get("summary", {})
        successes = data.get("successes", [])
        by_actions = data.get("by_actions_count", [])
        regression = data.get("regression", {})

        # Build summary HTML
        summary_lines = [
            "<h2>Summary</h2>",
            "<table border='1' cellpadding='6'><tbody>",
            f"<tr><td>Total cases</td><td>{summary.get('total_cases', 0)}</td></tr>",
            f"<tr><td>Successes</td><td>{summary.get('success_count', 0)}</td></tr>",
            f"<tr><td>Failures</td><td>{summary.get('failure_count', 0)}</td></tr>",
            "</tbody></table>",
        ]
        if summary.get("handler_run_time_ns"):
            h = summary["handler_run_time_ns"]
            summary_lines.extend([
                "<h3>Handler run time (ns)</h3>",
                "<table border='1' cellpadding='6'><tbody>",
                f"<tr><td>Min</td><td>{h['min']}</td></tr>",
                f"<tr><td>Max</td><td>{h['max']}</td></tr>",
                f"<tr><td>Mean</td><td>{h['mean']:.0f}</td></tr>",
                f"<tr><td>Median</td><td>{h['median']:.0f}</td></tr>",
                f"<tr><td>Stdev</td><td>{h['stdev']:.0f}</td></tr>",
                "</tbody></table>",
            ])

        # Regression summary
        reg_html = ""
        if regression:
            slope = regression["slope_ns_per_action"]
            intercept = regression["intercept_ns"]
            r2 = regression["r_squared"]
            reg_html = (
                "<h2>Linear fit: handler_run_time_ns = intercept + slope × actions_count</h2>"
                "<table border='1' cellpadding='6'><tbody>"
                f"<tr><td>Slope (ns per action)</td><td>{slope:.2f}</td></tr>"
                f"<tr><td>Intercept (ns)</td><td>{intercept:.2f}</td></tr>"
                f"<tr><td>R²</td><td>{r2:.4f}</td></tr>"
                "</tbody></table>"
            )

        # Chart data: scatter (actions_count, handler_run_time_ns) and regression line
        scatter_x = [s["actions_count"] for s in successes]
        scatter_y = [s["handler_run_time_ns"] for s in successes]
        line_x = []
        line_y = []
        if regression and scatter_x:
            x_min = min(scatter_x)
            x_max = max(scatter_x)
            line_x = [x_min, x_max]
            line_y = [
                regression["intercept_ns"] + regression["slope_ns_per_action"] * x
                for x in line_x
            ]

        # Escape JSON for embedding
        scatter_json = json.dumps(
            [{"x": x, "y": y} for x, y in zip(scatter_x, scatter_y)]
        )
        line_json = json.dumps([{"x": x, "y": y} for x, y in zip(line_x, line_y)])

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Lightrun Overhead Benchmark Results</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 900px; }}
    h1 {{ color: #1a1a2e; }}
    h2 {{ margin-top: 24px; color: #16213e; }}
    table {{ border-collapse: collapse; margin-bottom: 16px; }}
    th, td {{ text-align: left; }}
    #chartContainer {{ position: relative; height: 400px; margin: 24px 0; }}
  </style>
</head>
<body>
  <h1>Lightrun Request Overhead Benchmark</h1>
  {"".join(summary_lines)}
  {reg_html}
  <h2>Benchmark length vs number of Lightrun actions</h2>
  <p>Handler run time (ns) vs actions count. Line: linear fit. Expectation: length rises linearly with actions.</p>
  <div id="chartContainer">
    <canvas id="chart"></canvas>
  </div>
  <script>
    const scatterData = {scatter_json};
    const lineData = {line_json};
    const ctx = document.getElementById('chart').getContext('2d');
    new Chart(ctx, {{
      type: 'scatter',
      data: {{
        datasets: [
          {{
            label: 'Measured (handler_run_time_ns)',
            data: scatterData,
            backgroundColor: 'rgba(54, 162, 235, 0.6)',
            borderColor: 'rgba(54, 162, 235, 1)',
            pointRadius: 6,
          }},
          {{
            label: 'Linear fit',
            data: lineData,
            type: 'line',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 2,
            pointRadius: 0,
            fill: false,
          }},
        ],
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          x: {{
            title: {{ display: true, text: 'Number of Lightrun actions' }},
            type: 'linear',
          }},
          y: {{
            title: {{ display: true, text: 'Handler run time (ns)' }},
            type: 'linear',
          }},
        }},
        plugins: {{
          legend: {{ position: 'top' }},
          tooltip: {{
            callbacks: {{
              label: function(ctx) {{
                return ctx.raw.x + ' actions, ' + ctx.raw.y + ' ns';
              }},
            }},
          }},
        }},
      }},
    }});
  </script>
</body>
</html>
"""
        viz_path = save_path / "visualizations.html"
        with open(viz_path, "w") as f:
            f.write(html)
        self._visualizations_path = viz_path
        return viz_path
