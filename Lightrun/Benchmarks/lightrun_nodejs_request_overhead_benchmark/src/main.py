#!/usr/bin/env python3
"""Main entry point for Request Overhead Benchmark."""

import sys
import shutil
import json
import time
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Add parent directories to path to import shared_modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared_modules.cli_parser import CLIParser, ParsedCLIArguments
from shared_modules.thread_logger import ThreadLogger, thread_task_wrapper
from .request_overhead_benchmark_manager import RequestOverheadBenchmarkManager
from .code_generator import CodeGenerator
from .request_overhead_report import RequestOverheadReportGenerator
from .request_overhead_results_viewer import RequestOverheadResultsViewer

def run_single_variant(config: ParsedCLIArguments, base_name: str, is_lightrun: bool, output_dir: Path):
    """Run benchmark for a single variant."""
    print(f"\n{'='*80}")
    print(f"Starting test for: {base_name}")
    print(f"{'='*80}")
    
    # Create temp directory for function code
    with TemporaryDirectory(prefix=f"lightrun_benchmark_{base_name}_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Generate code
        generator = CodeGenerator(config.test_file_length)
        generator.generate_code(tmp_path, is_lightrun)
        
        # Configure variant
        import copy
        variant_config = copy.deepcopy(config)
        variant_config.base_function_name = base_name
        variant_config.entry_point = 'functionTest' # Fixed entry point in generated code
        variant_config.results_file = str(output_dir / f'{base_name}_results.json')
        variant_config.report_file = f'{base_name}_report.txt'
        variant_config.output_dir = output_dir
        
        # Run benchmark
        with RequestOverheadBenchmarkManager(variant_config, tmp_path) as manager:
            results = manager.run()
            
            # Archive source code
            source_archive_dir = output_dir / 'source' / base_name
            source_archive_dir.mkdir(parents=True, exist_ok=True)
            # shutil.copytree(tmp_path, source_archive_dir, dirs_exist_ok=True) is Python 3.8+
            # We can use a simpler approach since we know we're in a fresh directory
            for item in tmp_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, source_archive_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, source_archive_dir / item.name, dirs_exist_ok=True)
            
            return results

def main():
    """Main entry point."""
    cli_parser = CLIParser(
        description='Measure the overhead of Lightrun actions on request latency.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Measure overhead with snapshots
  %(prog)s --lightrun-secret YOUR_SECRET

  # Measure overhead with logs
  %(prog)s --lightrun-secret YOUR_SECRET --lightrun-action-type log
"""
    )
    args = cli_parser.parse()
    args.print_configuration(table_header="Lightrun Request Overhead Benchmark Configuration")
        
    # print("=" * 80)
    # print("Lightrun Request Overhead Benchmark")
    # print("=" * 80)
    # print(f"Function Length (calls): {args.test_file_length}")
    # print(f"Num Actions/Repeats: {args.test_size} ({args.lightrun_action_type})")
    
    # Setup results directory
    benchmark_name = Path(__file__).resolve().parents[1].name
    test_results_base_dir = Path(__file__).resolve().parents[2] / 'benchmark_results' / benchmark_name
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    test_results_dir = test_results_base_dir / timestamp
    test_results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Results directory: {test_results_dir}")
    
    # Run variants
    log_dir = test_results_dir / 'logs'
    variant_names = ['Variant-With-Lightrun', 'Variant-Without-Lightrun']
    with ThreadLogger.create(log_dir, variant_names):
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_with = executor.submit(
                thread_task_wrapper(
                    'Variant-With-Lightrun',
                    run_single_variant,
                    args, 'helloLightrun', True, test_results_dir
                )
            )
            future_without = executor.submit(
                thread_task_wrapper(
                    'Variant-Without-Lightrun',
                    run_single_variant,
                    args, 'helloNoLightrun', False, test_results_dir
                )
            )
            
            with_results = future_with.result()
            without_results = future_without.result()
        
    # Generate report
    print("\nGenerating Report...")
    report_gen = RequestOverheadReportGenerator(with_results, without_results)
    report_gen.set_output_dir(test_results_dir)
    report_gen.generate_all(args.report_file)
    
    # Save combined
    combined = {
        'with_lightrun': with_results,
        'without_lightrun': without_results,
        'config': args.to_dict(),
        'timestamp': timestamp
    }
    with open(test_results_dir / args.results_file, 'w') as f:
        json.dump(combined, f, indent=2, default=str)
        
    # Display
    viewer = RequestOverheadResultsViewer()
    viewer.display(test_results_dir, args.report_file)
    
    print("\nBenchmark Complete.")

if __name__ == "__main__":
    main()
