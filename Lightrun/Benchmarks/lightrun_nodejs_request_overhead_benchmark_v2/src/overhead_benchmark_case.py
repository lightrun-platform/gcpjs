from pathlib import Path
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import LightrunOverheadBenchmarkResult
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import MAX_GCP_FUNCTION_NAME_LENGTH
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

class LightrunOverheadBenchmarkCase(BenchmarkCase[LightrunOverheadBenchmarkResult]):
    """Benchmark case for Lightrun overhead measurement."""

    def __init__(self,
                 *,
                 benchmark_name: str,
                 runtime: str, 
                 region: str, 
                 source_code_dir: Path,
                 entry_point: str,
                 num_actions: int, 
                 action_type: str,
                 lightrun_secret: str,
                 lightrun_api_key: str,
                 lightrun_company_id: str,
                 lightrun_api_url: str,
                 project: str,
                 memory: str,
                 cpu: str,
                 timeout: int,
                 gen2: bool,
                 deployment_timeout: int,
                 delete_timeout: int,
                 logger_factory: LoggerFactory):
        super().__init__(deployment_timeout, delete_timeout, logger_factory)
        self.benchmark_name = benchmark_name
        self.runtime = runtime
        self.region = region
        self.source_code_dir = source_code_dir
        self.entry_point = entry_point
        self.num_actions = num_actions
        self.action_type = action_type
        self.lightrun_secret = lightrun_secret
        self.lightrun_api_key = lightrun_api_key
        self.lightrun_company_id = lightrun_company_id
        self.lightrun_api_url = lightrun_api_url
        self.project = project
        self.memory = memory
        self.cpu = cpu
        self.timeout = timeout
        self.gen2 = gen2
        self._gcp_function = None


    def case_identifier(self) -> str:
        sanitized_mem = self.memory.lower()
        sanitized_cpu = self.cpu.replace('.', 'p')
        generation = "gen2" if self.gen2 else "gen1"
        return f"{self.runtime}-{generation}-{sanitized_mem}-{sanitized_cpu}cpu-{self.num_actions}actions-{self.region}"

    @property
    def name(self) -> str:
        return f"{self.benchmark_name}-{self.case_identifier()}"

    @property
    def gcp_function(self) -> GCPFunction:
        if self._gcp_function:
            return self._gcp_function

        full_name = self.name
        function_name = full_name
        if len(function_name) > MAX_GCP_FUNCTION_NAME_LENGTH:
            function_name = self.case_identifier()
            if len(function_name) > MAX_GCP_FUNCTION_NAME_LENGTH:
                raise Exception(
f"""Function name '{full_name}' is too long ({len(full_name)} chars). "
Shortened function name '{function_name}' is still too long at {len(function_name)} chars.
Max allowed length for google cloud functions is {MAX_GCP_FUNCTION_NAME_LENGTH} characters.""")

        self._gcp_function = GCPFunction(
            name=function_name,
            region=self.region,
            runtime=self.runtime,
            entry_point=self.entry_point,
            function_source_code_dir=self.source_code_dir,
            project=self.project,
            memory=self.memory,
            cpu=self.cpu,
            timeout=self.timeout,
            gen2=self.gen2,
            env_vars=self.env_vars
        )
        return self._gcp_function

    @property
    def env_vars(self) -> dict:
        return {
            'LIGHTRUN_SECRET': self.lightrun_secret,
            'DISPLAY_NAME': self.name,
            'LIGHTRUN_API_ENDPOINT': self.lightrun_api_url
        }

    def execute_benchmark(self) -> LightrunOverheadBenchmarkResult:
        """Execute the benchmark logic."""
        # Placeholder implementation
        self.log_info(f"Executing benchmark with {self.num_actions} {self.action_type} actions on {self.runtime}")
        # TODO: Implement actual load generation and action application
        return LightrunOverheadBenchmarkResult(success=True)
