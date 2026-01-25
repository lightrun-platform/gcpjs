
from pathlib import Path
from datetime import datetime, timezone
import webbrowser
import subprocess

class ResultsViewer:
    """Displays benchmark results and visualizations."""

    def display(self, results_dir: Path, report_file: str):
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
