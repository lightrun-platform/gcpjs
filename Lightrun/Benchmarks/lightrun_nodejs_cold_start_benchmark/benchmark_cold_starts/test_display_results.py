#!/usr/bin/env python3
"""Test script for display_results function - regenerates report and displays results."""

import json
import sys
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime, timezone

# Add src directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from report import ReportGenerator

def display_results(results_dir: Path, report_file: str):
    """Display results and graphs in a single HTML window."""
    # Find all visualization files
    visualization_files = sorted(results_dir.glob('*_comparison.png')) + sorted(results_dir.glob('*_distribution.png'))
    
    if not visualization_files:
        print("No visualizations found to display.")
        return
    
    # Read report content
    report_path = results_dir / report_file
    report_content = ""
    if report_path.exists():
        with open(report_path, 'r') as f:
            report_content = f.read()
    else:
        report_content = 'Report file not found'
    
    # Create HTML file to display everything
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Cold Start Test Results</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .report {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            overflow-x: auto;
        }}
        .visualizations {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 20px;
        }}
        .viz-container {{
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .viz-container img {{
            width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 3px;
        }}
        .viz-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cloud Function Cold Start Performance Test Results</h1>
        <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div class="report">
{report_content}
    </div>
    
    <div class="visualizations">
"""
    
    for viz_file in visualization_files:
        # Get relative path for HTML
        rel_path = viz_file.name
        metric_name = viz_file.stem.replace('_comparison', '').replace('_distribution', '').replace('_', ' ').title()
        html_content += f"""
        <div class="viz-container">
            <div class="viz-title">{metric_name}</div>
            <img src="{rel_path}" alt="{metric_name}">
        </div>
"""
    
    html_content += """
    </div>
</body>
</html>
"""
    
    # Save HTML file
    html_file = results_dir / 'results_viewer.html'
    with open(html_file, 'w') as f:
        f.write(html_content)
    
    # Open in browser
    html_path = html_file.absolute()
    print(f"Opening results viewer: {html_path}")
    
    try:
        webbrowser.open(f'file://{html_path}')
        print("Results displayed in browser")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print(f"Please open manually: {html_path}")
    
    # Also try to open with system command (for macOS)
    try:
        subprocess.run(['open', str(html_path)], check=False)
    except Exception:
        pass

if __name__ == "__main__":
    # Use the base directory where existing results are
    base_dir = Path(__file__).parent.parent
    results_json = base_dir / 'comparative_cold_start_results.json'
    report_file = "comparative_cold_start_report.txt"
    
    # Create test_results directory
    test_results_dir = Path(__file__).parent / 'test_results'
    test_results_dir.mkdir(exist_ok=True)
    
    print(f"Regenerating report with updated analysis (stdev + F-test)...")
    print(f"  Loading from: {results_json}")
    print(f"  Output directory: {test_results_dir}")
    print()
    
    # Load existing results
    if not results_json.exists():
        print(f"ERROR: Results file not found: {results_json}")
        sys.exit(1)
    
    with open(results_json, 'r') as f:
        combined_results = json.load(f)
    
    with_lightrun_results = combined_results.get('with_lightrun', {})
    without_lightrun_results = combined_results.get('without_lightrun', {})
    
    if not with_lightrun_results or not without_lightrun_results:
        print("ERROR: Missing with_lightrun or without_lightrun results")
        sys.exit(1)
    
    # Generate updated report
    report_generator = ReportGenerator(with_lightrun_results, without_lightrun_results)
    report_generator.set_output_dir(test_results_dir)
    
    # Generate text report
    comparative_report = report_generator.generate_comparative_report()
    report_path = test_results_dir / report_file
    with open(report_path, 'w') as f:
        f.write(comparative_report)
    
    print(f"Report saved to: {report_path}")
    print("\n" + "=" * 80)
    print(comparative_report)
    print("=" * 80)
    
    # Generate visualizations
    print("\nGenerating visualizations...")
    report_generator.generate_visualizations()
    
    print(f"\nAll outputs saved to: {test_results_dir.resolve()}")
    
    # Display results
    print("\n" + "=" * 80)
    print("Displaying Results and Visualizations...")
    print("=" * 80)
    display_results(test_results_dir, report_file)
