#!/usr/bin/env python3
"""Main entry point for Cloud Function cold start testing."""

import os
import sys
import argparse
import subprocess
import webbrowser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .manager import ColdStartTestManager
from .report import ReportGenerator


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


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Test Cloud Functions with guaranteed cold starts. '
                    'Deploys multiple functions for both with/without Lightrun, '
                    'waits for them to become cold, then tests them all in parallel.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use defaults (100 functions each, 20 minute wait)
  %(prog)s --lightrun-secret YOUR_SECRET

  # Test with 50 functions each, wait 10 minutes
  %(prog)s --lightrun-secret YOUR_SECRET --num-functions 50 --wait-minutes 10

  # Custom region and project
  %(prog)s --lightrun-secret YOUR_SECRET --region us-central1 --project my-project
        """
    )
    
    parser.add_argument(
        '--lightrun-secret',
        type=str,
        default=os.environ.get('LIGHTRUN_SECRET', ''),
        help='Lightrun secret (default: from LIGHTRUN_SECRET env var)'
    )
    parser.add_argument(
        '--num-functions',
        type=int,
        default=100,
        help='Number of functions to deploy and test per variant (default: 100)'
    )
    parser.add_argument(
        '--wait-minutes',
        type=int,
        default=20,
        help='Minutes to wait for functions to become cold (default: 20)'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='europe-west3',
        help='GCP region (default: europe-west3)'
    )
    parser.add_argument(
        '--project',
        type=str,
        default='lightrun-temp',
        help='GCP project ID (default: lightrun-temp)'
    )
    parser.add_argument(
        '--runtime',
        type=str,
        default='nodejs20',
        help='Function runtime (default: nodejs20)'
    )
    parser.add_argument(
        '--results-file',
        type=str,
        default='comparative_cold_start_results.json',
        help='Output file for test results (default: comparative_cold_start_results.json)'
    )
    parser.add_argument(
        '--report-file',
        type=str,
        default='comparative_cold_start_report.txt',
        help='Output file for test report (default: comparative_cold_start_report.txt)'
    )
    parser.add_argument(
        '--num-workers',
        type=int,
        default=None,
        help='Number of worker threads per test variant (default: number of functions to deploy)'
    )
    
    args = parser.parse_args()
    
    # Set default num_workers to num_functions if not specified
    if args.num_workers is None:
        args.num_workers = args.num_functions
    
    return args


def run_single_test(config: argparse.Namespace, function_dir: Path, base_name: str, entry_point: str, output_dir: Path) -> dict:
    """Run a single test variant (with or without Lightrun)."""
    # Create a copy of config with variant-specific settings
    import copy
    variant_config = copy.deepcopy(config)
    variant_config.base_function_name = base_name
    variant_config.entry_point = entry_point
    variant_config.results_file = str(output_dir / f'{base_name}_results.json')
    variant_config.report_file = f'{base_name}_report.txt'
    variant_config.output_dir = output_dir
    
    print(f"\n{'='*80}")
    print(f"Starting test for: {base_name}")
    print(f"{'='*80}")
    
    with ColdStartTestManager(variant_config, function_dir) as manager:
        return manager.run()

def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate LIGHTRUN_SECRET
    if not args.lightrun_secret:
        print("ERROR: --lightrun-secret is required (or set LIGHTRUN_SECRET environment variable)")
        sys.exit(1)
    
    # Get base directory (gcf-example-basic)
    # __file__ is test_cold_starts/src/main.py, so parent.parent is test_cold_starts, need one more parent
    base_dir = Path(__file__).parent.parent.parent
    hello_lightrun_dir = base_dir / 'helloLightrun'
    hello_no_lightrun_dir = base_dir / 'helloNoLightrun'
    
    # Verify directories exist
    if not hello_lightrun_dir.exists():
        print(f"ERROR: Directory not found: {hello_lightrun_dir}")
        sys.exit(1)
    if not hello_no_lightrun_dir.exists():
        print(f"ERROR: Directory not found: {hello_no_lightrun_dir}")
        sys.exit(1)
    
    print("=" * 80)
    print("Cloud Function Parallel Cold Start Performance Test - Comparative Analysis")
    print("=" * 80)
    print(f"Number of Functions per Variant: {args.num_functions}")
    print(f"Cold Start Wait Time: {args.wait_minutes} minutes")
    print(f"Region: {args.region}")
    print(f"Project: {args.project}")
    print(f"Number of Worker Threads per Variant: {args.num_workers}")
    print("Note: Functions will be automatically cleaned up on exit")
    print()
    
    # Run both tests in parallel
    print("Running both test variants in parallel...")
    print()
    
    # Create test_results directory with timestamped subdirectory
    test_results_base_dir = Path(__file__).parent / 'test_results'
    test_results_base_dir.mkdir(exist_ok=True)
    
    # Create timestamped subdirectory
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    test_results_dir = test_results_base_dir / timestamp
    test_results_dir.mkdir(exist_ok=True)
    
    print(f"Results will be saved to: {test_results_dir}")
    print()
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tests
        future_with = executor.submit(
            run_single_test,
            args,
            hello_lightrun_dir,
            'helloLightrun',
            'helloLightrun',
            test_results_dir
        )
        future_without = executor.submit(
            run_single_test,
            args,
            hello_no_lightrun_dir,
            'helloNoLightrun',
            'helloNoLightrun',
            test_results_dir
        )
        
        # Wait for both to complete
        with_lightrun_results = future_with.result()
        without_lightrun_results = future_without.result()
    
    # Generate comparative report
    print("\n" + "=" * 80)
    print("Generating Comparative Analysis...")
    print("=" * 80)
    
    report_generator = ReportGenerator(with_lightrun_results, without_lightrun_results)
    report_generator.set_output_dir(test_results_dir)
    report_generator.generate_all(args.report_file)
    
    # Save combined results
    import json
    combined_results = {
        'with_lightrun': with_lightrun_results,
        'without_lightrun': without_lightrun_results,
        'test_timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    results_file_path = test_results_dir / args.results_file
    with open(results_file_path, 'w') as f:
        json.dump(combined_results, f, indent=2)
    
    print(f"\nCombined results saved to: {results_file_path}")
    
    # Display results and graphs
    print("\n" + "=" * 80)
    print("Displaying Results and Visualizations...")
    print("=" * 80)
    display_results(test_results_dir, args.report_file)
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
