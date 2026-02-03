import re
from pathlib import Path
from typing import List, Iterator

from Lightrun.Benchmarks.shared_modules.benchmark_cases_generator import BenchmarkCasesGenerator
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_source_code_generator import OverheadBenchmarkSourceCodeGenerator
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_case import LightrunOverheadBenchmarkCase
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import LightrunOverheadBenchmarkResult
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

from Lightrun.Benchmarks.shared_modules.authentication import ApiKeyAuthenticator, InteractiveAuthenticator


class LightrunOverheadBenchmarkCasesGenerator(BenchmarkCasesGenerator[LightrunOverheadBenchmarkResult]):
    """Generates benchmark cases for the Lightrun overhead benchmark."""

    def _generate_benchmark_cases(self, benchmark_name: str, benchmark_config: ParsedCLIArguments, regions_allocation_order: Iterator[str], logger_factory: LoggerFactory, results_directory: Path) -> List[BenchmarkCase[LightrunOverheadBenchmarkResult]]:
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

        logger = logger_factory.get_logger(self.__class__.__name__)
        source_dir = results_directory / 'source_code'
        logger.info(f"Generating source code in: {source_dir}")

        authenticator = None
        if benchmark_config.authentication_type == 'API_KEY':
            authenticator = ApiKeyAuthenticator(benchmark_config.lightrun_api_key)
        elif benchmark_config.authentication_type == 'MANUAL':
            authenticator = InteractiveAuthenticator(benchmark_config.lightrun_api_url, benchmark_config.lightrun_company_id, logger)

        for runtime in benchmark_config.runtimes:
            # Extract version from runtime string (e.g. 'nodejs20' -> '20')
            match = re.search(r'nodejs(\d+)', runtime)
            if not match:
                raise Exception(f"Could not extract node version from runtime name: {runtime}")
            node_version = match.group(1)
            
            # Generate source code for this runtime
            generator = OverheadBenchmarkSourceCodeGenerator(
                test_size=benchmark_config.test_size,
                node_version=node_version,
                lightrun_version=benchmark_config.lightrun_version,
                gcp_functions_version=benchmark_config.google_library_version
            )

            sources_dir_for_runtime = results_directory / 'source_code' / runtime
            generated_source = generator.create_source_dir(sources_dir_for_runtime)
            
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
                                gen2=is_gen2,
                                deployment_timeout=benchmark_config.deployment_timeout,
                                delete_timeout=benchmark_config.delete_timeout,
                                authenticator=authenticator,
                                logger_factory=logger_factory)
                            cases.append(case)
                
        return cases
