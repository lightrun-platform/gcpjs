import json
import subprocess
import sys
from pathlib import Path

from Lightrun.Benchmarks.shared_modules.benchmark_results_visualizer import BenchmarkResultsVisualizer
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult


class LightrunOverheadReportVisualizer(BenchmarkResultsVisualizer[LightrunOverheadBenchmarkResult]):
    """Visualizes results for Lightrun overhead benchmark: summary and regression plot per allocation."""

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
        """Creates the visualizations (summary + graph per allocation) and saves them in save_path."""
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
        by_allocation = data.get("by_allocation", {})

        # Global summary
        summary_lines = [
            "<h2>Summary</h2>",
            "<table border='1' cellpadding='6'><tbody>",
            f"<tr><td>Total cases</td><td>{summary.get('total_cases', 0)}</td></tr>",
            f"<tr><td>Successes</td><td>{summary.get('success_count', 0)}</td></tr>",
            f"<tr><td>Failures</td><td>{summary.get('failure_count', 0)}</td></tr>",
            f"<tr><td>Allocations</td><td>{', '.join(summary.get('allocations', []))}</td></tr>",
            "</tbody></table>",
        ]
        if summary.get("note"):
            summary_lines.append(f"<p><em>{summary['note']}</em></p>")

        # One section + chart per allocation (run times only comparable within same allocation)
        allocation_sections = []
        chart_datasets_js = []
        for idx, key in enumerate(sorted(by_allocation.keys())):
            alloc = by_allocation[key]
            memory = alloc["memory"]
            cpu = alloc["cpu"]
            successes = alloc.get("successes", [])
            regression = alloc.get("regression") or {}
            alloc_summary = alloc.get("summary", {})

            section_lines = [
                f"<h2>Allocation: {memory} / {cpu} CPU</h2>",
            ]
            if alloc_summary.get("handler_run_time_ns"):
                h = alloc_summary["handler_run_time_ns"]
                section_lines.extend([
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Min (ns)</td><td>{h['min']}</td></tr>",
                    f"<tr><td>Max (ns)</td><td>{h['max']}</td></tr>",
                    f"<tr><td>Mean (ns)</td><td>{h['mean']:.0f}</td></tr>",
                    f"<tr><td>Median (ns)</td><td>{h['median']:.0f}</td></tr>",
                    f"<tr><td>Stdev (ns)</td><td>{h['stdev']:.0f}</td></tr>",
                    "</tbody></table>",
                ])
            if regression:
                section_lines.extend([
                    "<h3>Linear fit</h3>",
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Slope (ns per action)</td><td>{regression['slope_ns_per_action']:.2f}</td></tr>",
                    f"<tr><td>Intercept (ns)</td><td>{regression['intercept_ns']:.2f}</td></tr>",
                    f"<tr><td>R²</td><td>{regression['r_squared']:.4f}</td></tr>",
                    "</tbody></table>",
                ])
            allocation_sections.append("\n".join(section_lines))

            # Chart data for this allocation
            scatter_x = [s["actions_count"] for s in successes]
            scatter_y = [s["handler_run_time_ns"] for s in successes]
            scatter_data = [{"x": x, "y": y} for x, y in zip(scatter_x, scatter_y)]
            line_x = []
            line_y = []
            if regression and scatter_x:
                line_x = [min(scatter_x), max(scatter_x)]
                line_y = [
                    regression["intercept_ns"] + regression["slope_ns_per_action"] * x
                    for x in line_x
                ]
            line_data = [{"x": x, "y": y} for x, y in zip(line_x, line_y)]
            chart_datasets_js.append({
                "label": f"{memory} / {cpu}",
                "scatterData": scatter_data,
                "lineData": line_data,
            })

        # Serialize for embedding in JS (one chart with multiple datasets)
        datasets_js = json.dumps(chart_datasets_js)

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
    h3 {{ margin-top: 16px; color: #0f3460; }}
    table {{ border-collapse: collapse; margin-bottom: 16px; }}
    th, td {{ text-align: left; }}
    #chartContainer {{ position: relative; height: 400px; margin: 24px 0; }}
  </style>
</head>
<body>
  <h1>Lightrun Request Overhead Benchmark</h1>
  {"".join(summary_lines)}
  {"".join(allocation_sections)}
  <h2>Handler run time vs number of Lightrun actions (by allocation)</h2>
  <p>Each allocation (memory/CPU) is shown separately. Run times are only comparable within the same allocation.</p>
  <div id="chartContainer">
    <canvas id="chart"></canvas>
  </div>
  <script>
    const allocationDatasets = {datasets_js};
    const colors = [
      {{ scatter: 'rgba(54, 162, 235, 0.6)', line: 'rgba(54, 162, 235, 1)' }},
      {{ scatter: 'rgba(255, 99, 132, 0.6)', line: 'rgba(255, 99, 132, 1)' }},
      {{ scatter: 'rgba(75, 192, 192, 0.6)', line: 'rgba(75, 192, 192, 1)' }},
      {{ scatter: 'rgba(255, 206, 86, 0.6)', line: 'rgba(255, 206, 86, 1)' }},
    ];
    const chartDatasets = [];
    allocationDatasets.forEach((alloc, i) => {{
      const c = colors[i % colors.length];
      chartDatasets.push({{
        label: alloc.label + ' (measured)',
        data: alloc.scatterData,
        backgroundColor: c.scatter,
        borderColor: c.line,
        pointRadius: 6,
      }});
      chartDatasets.push({{
        label: alloc.label + ' (fit)',
        data: alloc.lineData,
        type: 'line',
        borderColor: c.line,
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
      }});
    }});
    const ctx = document.getElementById('chart').getContext('2d');
    new Chart(ctx, {{
      type: 'scatter',
      data: {{ datasets: chartDatasets }},
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
