import json
import subprocess
import sys
from pathlib import Path

from Lightrun.Benchmarks.shared_modules.benchmark_results_visualizer import BenchmarkResultsVisualizer
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult


class LightrunOverheadReportVisualizer(BenchmarkResultsVisualizer[LightrunOverheadBenchmarkResult]):
    """Visualizes results for Lightrun overhead benchmark: summary and regression plot per group."""

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
        """Creates the visualizations (summary + graph per group) and saves them in save_path."""
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
        by_group = data.get("by_group", {})

        # Global summary
        summary_lines = [
            "<h2>Summary</h2>",
            "<table border='1' cellpadding='6'><tbody>",
            f"<tr><td>Total cases</td><td>{summary.get('total_cases', 0)}</td></tr>",
            f"<tr><td>Successes</td><td>{summary.get('success_count', 0)}</td></tr>",
            f"<tr><td>Failures</td><td>{summary.get('failure_count', 0)}</td></tr>",
            f"<tr><td>Allocations</td><td>{', '.join(summary.get('allocations', []))}</td></tr>",
            f"<tr><td>Groups (allocation + processor)</td><td>{len(summary.get('groups', []))}</td></tr>",
            "</tbody></table>",
        ]
        if summary.get("note"):
            summary_lines.append(f"<p><em>{summary['note']}</em></p>")

        # Section: Results by group (allocation + cpu_model) - preferred for comparison
        group_sections = []
        group_datasets_js = []
        for idx, key in enumerate(sorted(by_group.keys())):
            group = by_group[key]
            memory = group["memory"]
            cpu = group["cpu"]
            cpu_model = group.get("cpu_model") or "Unknown"
            successes = group.get("successes", [])
            regression = group.get("regression") or {}
            group_summary = group.get("summary", {})

            section_lines = [
                f"<h3>Group: {memory} / {cpu} CPU | {cpu_model}</h3>",
            ]
            if group_summary.get("handler_run_time_ns"):
                h = group_summary["handler_run_time_ns"]
                section_lines.extend([
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Count</td><td>{group_summary.get('count', 0)}</td></tr>",
                    f"<tr><td>Min (ns)</td><td>{h['min']}</td></tr>",
                    f"<tr><td>Max (ns)</td><td>{h['max']}</td></tr>",
                    f"<tr><td>Mean (ns)</td><td>{h['mean']:.0f}</td></tr>",
                    f"<tr><td>Median (ns)</td><td>{h['median']:.0f}</td></tr>",
                    f"<tr><td>Stdev (ns)</td><td>{h['stdev']:.0f}</td></tr>",
                    "</tbody></table>",
                ])
            if regression:
                section_lines.extend([
                    "<h4>Linear fit</h4>",
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Slope (ns per action)</td><td>{regression['slope_ns_per_action']:.2f}</td></tr>",
                    f"<tr><td>Intercept (ns)</td><td>{regression['intercept_ns']:.2f}</td></tr>",
                    f"<tr><td>R²</td><td>{regression['r_squared']:.4f}</td></tr>",
                    "</tbody></table>",
                ])
            group_sections.append("\n".join(section_lines))

            # Chart data for this group
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
            # Shorten cpu_model for chart label
            short_model = cpu_model.split("(")[0].strip() if "(" in cpu_model else cpu_model[:20]
            group_datasets_js.append({
                "label": f"{memory}/{cpu} | {short_model}",
                "scatterData": scatter_data,
                "lineData": line_data,
            })

        # Section: Aggregated by allocation (backward compat, but warns about mixed processors)
        allocation_sections = []
        for idx, key in enumerate(sorted(by_allocation.keys())):
            alloc = by_allocation[key]
            memory = alloc["memory"]
            cpu = alloc["cpu"]
            alloc_summary = alloc.get("summary", {})
            cpu_models = alloc_summary.get("cpu_models", [])
            regression = alloc.get("regression") or {}

            section_lines = [
                f"<h3>Allocation: {memory} / {cpu} CPU</h3>",
                f"<p><em>Processors: {', '.join(cpu_models) if cpu_models else 'Unknown'}</em></p>",
            ]
            if len(cpu_models) > 1:
                section_lines.append(
                    "<p><strong>Warning:</strong> This allocation has multiple processor types. "
                    "Results are not directly comparable. See 'By Group' section for precise comparison.</p>"
                )
            if alloc_summary.get("handler_run_time_ns"):
                h = alloc_summary["handler_run_time_ns"]
                section_lines.extend([
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Count</td><td>{alloc_summary.get('count', 0)}</td></tr>",
                    f"<tr><td>Min (ns)</td><td>{h['min']}</td></tr>",
                    f"<tr><td>Max (ns)</td><td>{h['max']}</td></tr>",
                    f"<tr><td>Mean (ns)</td><td>{h['mean']:.0f}</td></tr>",
                    f"<tr><td>Median (ns)</td><td>{h['median']:.0f}</td></tr>",
                    f"<tr><td>Stdev (ns)</td><td>{h['stdev']:.0f}</td></tr>",
                    "</tbody></table>",
                ])
            if regression:
                section_lines.extend([
                    "<h4>Linear fit (aggregated)</h4>",
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Slope (ns per action)</td><td>{regression['slope_ns_per_action']:.2f}</td></tr>",
                    f"<tr><td>Intercept (ns)</td><td>{regression['intercept_ns']:.2f}</td></tr>",
                    f"<tr><td>R²</td><td>{regression['r_squared']:.4f}</td></tr>",
                    "</tbody></table>",
                ])
            allocation_sections.append("\n".join(section_lines))

        # Serialize for embedding in JS
        datasets_js = json.dumps(group_datasets_js)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Lightrun Overhead Benchmark Results</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 1100px; }}
    h1 {{ color: #1a1a2e; }}
    h2 {{ margin-top: 24px; color: #16213e; border-bottom: 2px solid #16213e; padding-bottom: 8px; }}
    h3 {{ margin-top: 16px; color: #0f3460; }}
    h4 {{ margin-top: 12px; color: #333; }}
    table {{ border-collapse: collapse; margin-bottom: 16px; }}
    th, td {{ text-align: left; }}
    .chart-container {{ position: relative; height: 450px; margin: 24px 0; }}
    .warning {{ color: #856404; background-color: #fff3cd; padding: 8px 12px; border-radius: 4px; margin: 8px 0; }}
  </style>
</head>
<body>
  <h1>Lightrun Request Overhead Benchmark</h1>
  {"".join(summary_lines)}
  
  <h2>Results by Group (Allocation + Processor)</h2>
  <p>Results grouped by (memory/CPU allocation, processor type). Run times are only comparable within the same group.</p>
  {"".join(group_sections)}
  
  <h2>Handler run time vs number of Lightrun actions (by group)</h2>
  <p>Each group (allocation + processor) is shown separately. Run times are only comparable within the same group.</p>
  <div class="chart-container">
    <canvas id="groupChart"></canvas>
  </div>
  
  <h2>Results by Allocation (Aggregated)</h2>
  <p><em>Warning: These results aggregate across different processor types. For precise comparison, use the 'By Group' section above.</em></p>
  {"".join(allocation_sections)}
  
  <script>
    const groupDatasets = {datasets_js};
    const colors = [
      {{ scatter: 'rgba(54, 162, 235, 0.6)', line: 'rgba(54, 162, 235, 1)' }},
      {{ scatter: 'rgba(255, 99, 132, 0.6)', line: 'rgba(255, 99, 132, 1)' }},
      {{ scatter: 'rgba(75, 192, 192, 0.6)', line: 'rgba(75, 192, 192, 1)' }},
      {{ scatter: 'rgba(255, 206, 86, 0.6)', line: 'rgba(255, 206, 86, 1)' }},
      {{ scatter: 'rgba(153, 102, 255, 0.6)', line: 'rgba(153, 102, 255, 1)' }},
      {{ scatter: 'rgba(255, 159, 64, 0.6)', line: 'rgba(255, 159, 64, 1)' }},
      {{ scatter: 'rgba(199, 199, 199, 0.6)', line: 'rgba(199, 199, 199, 1)' }},
      {{ scatter: 'rgba(83, 102, 255, 0.6)', line: 'rgba(83, 102, 255, 1)' }},
    ];
    const chartDatasets = [];
    groupDatasets.forEach((group, i) => {{
      const c = colors[i % colors.length];
      chartDatasets.push({{
        label: group.label + ' (measured)',
        data: group.scatterData,
        backgroundColor: c.scatter,
        borderColor: c.line,
        pointRadius: 6,
      }});
      chartDatasets.push({{
        label: group.label + ' (fit)',
        data: group.lineData,
        type: 'line',
        borderColor: c.line,
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
      }});
    }});
    const ctx = document.getElementById('groupChart').getContext('2d');
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
