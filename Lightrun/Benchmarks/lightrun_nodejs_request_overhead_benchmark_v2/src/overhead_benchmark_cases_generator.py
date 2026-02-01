import tempfile
import re
from pathlib import Path
from typing import List, Iterator

from Lightrun.Benchmarks.shared_modules.benchmark_cases_generator import BenchmarkCasesGenerator
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from .overhead_benchmark_source_code_generator import OverheadBenchmarkSourceCodeGenerator
from .overhead_benchmark_case import LightrunOverheadBenchmarkCase
from .overhead_benchmark_result import LightrunOverheadBenchmarkResult

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
            generator = OverheadBenchmarkSourceCodeGenerator(
                test_size=benchmark_config.test_size,
                node_version=node_version,
                lightrun_version=benchmark_config.lightrun_version,
                gcp_functions_version=benchmark_config.google_library_version
            )
            
            source_dir = build_dir / runtime
            generated_source = generator.create_source_dir(source_dir)
            
            for generation in benchmark_config.function_generations:
                is_gen2 = (generation.lower() == 'gen2')
                
                for memory in benchmark_config.memory:
                    for cpu in benchmark_config.cpus:
                        # Generate cases: 0 to test_size actions
                        for num_actions in range(benchmark_config.test_size + 1):
                            region = next(regions_allocation_order)
                            
                            case = LightrunOverheadBenchmarkCase(
                                benchmark_name=benchmark_name,
                                runtime=runtime,
                                region=region,
                                source_code_dir=generated_source.path,
                                entry_point=generated_source.entry_point,
                                num_actions=num_actions,
                                action_type=benchmark_config.lightrun_action_type,
                                lightrun_secret=benchmark_config.lightrun_secret,
                                lightrun_api_key=benchmark_config.lightrun_api_key,
                                lightrun_company_id=benchmark_config.lightrun_company_id,
                                lightrun_api_url=benchmark_config.lightrun_api_url,
                                project=benchmark_config.project,
                                memory=memory,
                                cpu=cpu,
                                timeout=benchmark_config.request_timeout,
                                deployment_timeout=benchmark_config.deployment_timeout,
                                gen2=is_gen2)
                            cases.append(case)
                
        return cases
