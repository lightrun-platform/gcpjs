import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
import logging

# Add parent directories to path to import shared_modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from .lightrun_benchmark_manager import BenchmarkManager
from .benchmark_cases_generator import BenchmarkCasesGenerator
from .benchmark_report_generator import BenchmarkReportGenerator
from .benchmark_results_visualizer import BenchmarkResultsVisualizer
from .cli_parser import CLIParser

class LightrunBenchmark[T]:

    def __init__(self,
                 cli_description: str,
                 cli_epilog: str,
                 benchmark_name: str,
                 test_root_dir: Path,
                 benchmark_cases_generator: BenchmarkCasesGenerator[T],
                 # benchmark_manager: BenchmarkManager,
                 report_generator: BenchmarkReportGenerator[T],
                 report_visualizer: BenchmarkResultsVisualizer[T]):

        self.cli_parser = CLIParser(description=cli_description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=cli_epilog)
        self.benchmark_parameters = self.cli_parser.parse()
        self.logger = logging.getLogger(__name__)
        self.cli_description = cli_description
        self.cli_epilog = cli_epilog
        self.benchmark_name = benchmark_name
        self.test_root_dir = test_root_dir
        self.benchmark_cases_generator = benchmark_cases_generator
        # self.benchmark_manager = benchmark_manager
        self.benchmark_report_generator = report_generator
        self.benchmark_report_visualizer = report_visualizer
        self.test_results_dir = test_root_dir / 'benchmark_results' / self.benchmark_name / datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        self.per_thread_logs_dir = self.test_results_dir / 'logs'
        self.benchmark_manager = None
        self.benchmark_cases = None
        self.benchmark_results = None
        self.benchmark_report = None
        self.benchmark_report_visualizations = None
        self.logger = None


    def run(self):
        self.test_results_dir.mkdir(parents=True, exist_ok=True)
        self.benchmark_parameters.print_configuration(table_header="Lightrun Request Overhead Benchmark Configuration")
        self.logger.info(f"Benchmark results directory: {self.test_results_dir}")

        self.benchmark_cases = self.benchmark_cases_generator.generate_benchmark_cases(self.benchmark_name, self.benchmark_parameters)
        # self.logger = ThreadSafeBenchmarkLogger.create(self.per_thread_logs_dir, [case.get_gcp_function().name for case in self.benchmark_cases])
        self.benchmark_manager = BenchmarkManager(self.benchmark_parameters.num_workers)
        self.benchmark_results = self.benchmark_manager.run(self.benchmark_cases)
        self.benchmark_report = self.benchmark_report_generator.generate_report(self.benchmark_results)
        self.benchmark_report_visualizations = self.benchmark_report_visualizer.create_visualizations(self.benchmark_report)

        self.logger.info("Benchmark Complete.")
        self.logger.info("Opening benchmark results.")
        self.benchmark_report_visualizer.display()

