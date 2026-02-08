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
        warmup_data = data.get("warmup", {})

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

        # Section: Warmup analysis
        warmup_sections = []
        warmup_datasets_js = []
        warmup_cases = warmup_data.get("cases", [])
        warmup_summary = warmup_data.get("summary", {})
        
        if warmup_cases:
            # Warmup summary table
            warmup_summary_lines = [
                "<h3>Warmup Summary</h3>",
                "<table border='1' cellpadding='6'><tbody>",
                f"<tr><td>Total cases with warmup</td><td>{warmup_summary.get('total_cases_with_warmup', 0)}</td></tr>",
                f"<tr><td>Cases that stabilized</td><td>{warmup_summary.get('cases_stabilized', 0)}</td></tr>",
                f"<tr><td>Cases that did NOT stabilize</td><td>{warmup_summary.get('cases_not_stabilized', 0)}</td></tr>",
            ]
            if warmup_summary.get("all_run_times_ns"):
                h = warmup_summary["all_run_times_ns"]
                warmup_summary_lines.extend([
                    f"<tr><td>All run times Min (ns)</td><td>{h['min']}</td></tr>",
                    f"<tr><td>All run times Max (ns)</td><td>{h['max']}</td></tr>",
                    f"<tr><td>All run times Mean (ns)</td><td>{h['mean']:.0f}</td></tr>",
                    f"<tr><td>All run times Median (ns)</td><td>{h['median']:.0f}</td></tr>",
                ])
            warmup_summary_lines.append("</tbody></table>")
            warmup_sections.append("\n".join(warmup_summary_lines))
            
            # Per-case warmup details and chart data
            for idx, case in enumerate(warmup_cases):
                status = "STABILIZED" if case["stabilized"] else "NOT STABILIZED"
                stab_at = f" at request {case['stability_achieved_at_request']}" if case.get("stability_achieved_at_request") else ""
                case_name = case.get("case_name", f"Case {idx+1}")
                memory = case.get("memory", "")
                cpu = case.get("cpu", "")
                cpu_model = case.get("cpu_model") or "Unknown"
                stats = case.get("stats", {})
                config = case.get("config", {})
                
                case_lines = [
                    f"<h4>{case_name}</h4>",
                    "<table border='1' cellpadding='6'><tbody>",
                    f"<tr><td>Allocation</td><td>{memory} / {cpu} CPU</td></tr>",
                    f"<tr><td>Processor</td><td>{cpu_model}</td></tr>",
                    f"<tr><td>Status</td><td>{status}{stab_at}</td></tr>",
                    f"<tr><td>Total requests</td><td>{case.get('total_requests', 0)}</td></tr>",
                ]
                if stats:
                    case_lines.extend([
                        f"<tr><td>Min run time (ns)</td><td>{stats.get('min_ns', 0)}</td></tr>",
                        f"<tr><td>Max run time (ns)</td><td>{stats.get('max_ns', 0)}</td></tr>",
                        f"<tr><td>Mean run time (ns)</td><td>{stats.get('mean_ns', 0):.0f}</td></tr>",
                        f"<tr><td>Median run time (ns)</td><td>{stats.get('median_ns', 0):.0f}</td></tr>",
                    ])
                if config:
                    case_lines.extend([
                        f"<tr><td>Config</td><td>timeout={config.get('timeout_seconds', 0)}s, max={config.get('max_requests', 0)}, "
                        f"window={config.get('stability_window', 0)}, tolerance={config.get('stability_tolerance', 0)*100:.1f}%</td></tr>",
                    ])
                case_lines.append("</tbody></table>")
                warmup_sections.append("\n".join(case_lines))
                
                # Chart data for this case's warmup
                measurements = case.get("measurements", [])
                if measurements:
                    scatter_data = [{"x": m["request_number"], "y": m["handler_run_time_ns"]} for m in measurements]
                    short_model = cpu_model.split("(")[0].strip() if "(" in cpu_model else cpu_model[:15]
                    warmup_datasets_js.append({
                        "label": f"{memory}/{cpu} | {short_model}",
                        "data": scatter_data,
                    })

        # Serialize for embedding in JS
        datasets_js = json.dumps(group_datasets_js)
        warmup_datasets_js_str = json.dumps(warmup_datasets_js)

        # Warmup section HTML (only if we have warmup data)
        warmup_html = ""
        if warmup_cases:
            warmup_html = f"""
  <h2>Warmup Analysis</h2>
  <p>The warmup phase sends successive requests until the function reaches stable performance.
  Stability is achieved when the last N requests have run times within a specified tolerance of each other.</p>
  {"".join(warmup_sections)}
  
  <h2>Warmup: Handler run time vs request number</h2>
  <p>Shows how run time changes as the function warms up. Initial requests typically have higher latency.</p>
  <div class="chart-container">
    <canvas id="warmupChart"></canvas>
  </div>
"""

        # Warmup chart script (only if we have warmup data)
        warmup_chart_script = ""
        if warmup_cases:
            warmup_chart_script = f"""
    // Warmup chart
    const warmupDatasets = {warmup_datasets_js_str};
    const warmupChartDatasets = [];
    warmupDatasets.forEach((ds, i) => {{
      const c = colors[i % colors.length];
      warmupChartDatasets.push({{
        label: ds.label,
        data: ds.data,
        backgroundColor: c.scatter,
        borderColor: c.line,
        pointRadius: 3,
        showLine: true,
        tension: 0.1,
      }});
    }});
    const warmupCtx = document.getElementById('warmupChart').getContext('2d');
    new Chart(warmupCtx, {{
      type: 'scatter',
      data: {{ datasets: warmupChartDatasets }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          x: {{
            title: {{ display: true, text: 'Warmup request number' }},
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
                return 'Request ' + ctx.raw.x + ': ' + ctx.raw.y + ' ns';
              }},
            }},
          }},
        }},
      }},
    }});
"""

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
  
  {warmup_html}
  
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
    {warmup_chart_script}
  </script>
</body>
</html>
"""
        viz_path = save_path / "visualizations.html"
        with open(viz_path, "w") as f:
            f.write(html)
        self._visualizations_path = viz_path
        return viz_path
