import tempfile
import re
from pathlib import Path
from typing import List, Optional, Iterator
from dataclasses import dataclass

from Lightrun.Benchmarks.shared_modules.benchmark_cases_generator import BenchmarkCasesGenerator
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from .overhead_benchmark_case import LightrunOverheadBenchmarkCase
from .overhead_benchmark_source_code_generator import OverheadBenchmarkSourceCodeGenerator

@dataclass
class LightrunOverheadBenchmarkResult:
    """Result of a single Lightrun overhead benchmark case."""
    success: bool
    error: Optional[Exception] = None

class LightrunOverheadBenchmarkCasesGenerator(BenchmarkCasesGenerator[LightrunOverheadBenchmarkResult]):
    """Generates benchmark cases for the Lightrun overhead benchmark."""

    def _generate_benchmark_cases(self, benchmark_name: str, benchmark_config: ParsedCLIArguments, regions_allocation_order: Iterator[str]) -> List[BenchmarkCase[LightrunOverheadBenchmarkResult]]:
        """
        Generate benchmark cases based on configuration.
        
        Args:
            benchmark_name: Name of the benchmark
            benchmark_config: Parsed CLI arguments
            regions_allocation_order: Iterator yielding regions
            
        Returns:
            List of generated benchmark cases
        """
        cases = []
        
        # Determine build/temp directory for generated source code
        # Ideally this should be persistent for the duration of the run. we use mkdtemp.
        # Note: This directory is not automatically cleaned up.
        build_dir = Path(tempfile.mkdtemp(prefix=f"lightrun_benchmark_{benchmark_name}_"))
        print(f"Generating source code in: {build_dir}")

        for runtime in benchmark_config.runtimes:
            # Extract version from runtime string (e.g. 'nodejs20' -> '20')
            match = re.search(r'nodejs(\d+)', runtime)
            node_version = match.group(1) if match else "20"
            
            # Generate source code for this runtime
            # We generate ONE set of source code (Lightrun enabled) for use by all cases of this runtime
            # regardless of num_actions.
            
            generator = OverheadBenchmarkSourceCodeGenerator(
                test_file_length=benchmark_config.test_file_length,
                node_version=node_version
                # lightrun_version and gcp_functions_version use defaults
            )
            
            source_dir = build_dir / runtime
            generated_path = generator.create_source_dir(source_dir, is_lightrun=True)
            
            # Generate cases: 0 to test_size actions
            for num_actions in range(benchmark_config.test_size + 1):
                region = next(regions_allocation_order)
                case_name = f"{benchmark_name}-{runtime}-{num_actions}actions-{region}"
                
                case = LightrunOverheadBenchmarkCase(
                    name=case_name,
                    runtime=runtime,
                    region=region,
                    source_code_dir=generated_path,
                    num_actions=num_actions,
                    action_type=benchmark_config.lightrun_action_type,
                    lightrun_secret=benchmark_config.lightrun_secret,
                    lightrun_api_key=benchmark_config.lightrun_api_key,
                    lightrun_company_id=benchmark_config.lightrun_company_id,
                    lightrun_api_url=benchmark_config.lightrun_api_url,
                    project=benchmark_config.project
                )
                cases.append(case)
                
        return cases
