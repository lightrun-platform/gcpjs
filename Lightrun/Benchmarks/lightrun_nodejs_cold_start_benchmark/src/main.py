#!/usr/bin/env python3
"""Main entry point for Cloud Function cold start testing."""

import os
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .cold_start_benchmark_manager import ColdStartBenchmarkManager
from .cold_start_benchmark_report import ColdStartReportGenerator
from .cold_start_results_viewer import ColdStartResultsViewer
from shared_modules.cli_parser import CLIParser


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
    
    with ColdStartBenchmarkManager(variant_config, function_dir) as manager:
        return manager.run()

def main():
    """Main entry point."""
    cli_parser = CLIParser()
    args = cli_parser.parse()
    
    # Validate LIGHTRUN_SECRET
    if not args.lightrun_secret:
        print("ERROR: --lightrun-secret is required (or set LIGHTRUN_SECRET environment variable)")
        sys.exit(1)
    
    # Get base directory (gcf-example-basic)
    # __file__ is test_cold_starts/src/main.py, so parent.parent is test_cold_starts, need one more parent
    base_dir = Path(__file__).parent.parent
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
    
    # Create test_results directory in centralized location
    # Path is: <RepoRoot>/Lightrun/Benchmarks/benchmark_results/<BenchmarkName>
    benchmark_name = Path(__file__).resolve().parents[1].name
    test_results_base_dir = Path(__file__).resolve().parents[2] / 'benchmark_results' / benchmark_name
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
    
    results_viewer = ColdStartResultsViewer()
    results_viewer.display(test_results_dir, args.report_file)
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
