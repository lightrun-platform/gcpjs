from pathlib import Path
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import LightrunOverheadBenchmarkResult
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import MAX_GCP_FUNCTION_NAME_LENGTH
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

from Benchmarks.shared_modules.authentication import Authenticator


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
                 authenticator: Authenticator,
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
        self.authenticator = authenticator
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
            env_vars=self.env_vars,
            labels={'created-by': 'lightrun-benchmark', 'benchmark-name': self.benchmark_name},
            logger=self.logger
        )
        return self._gcp_function

    @property
    def env_vars(self) -> dict:
        return {
            'LIGHTRUN_SECRET': self.lightrun_secret,
            'DISPLAY_NAME': self.name,
            'LIGHTRUN_API_ENDPOINT': self.lightrun_api_url
        }

    def _get_action_line_numbers(self) -> List[int]:
        """
        Parses the generated source code to find line numbers for action placement.
        Target: The 'return' statement line inside each 'function{i}'.
        """
        source_file = self.source_code_dir / "lightrunOverheadBenchmark.js"
        if not source_file.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        lines = source_file.read_text().splitlines()
        action_lines = []
        
        # Look for function definitions and then the return statement inside them
        # Pattern: function function{i}() { ... return ... }
        # We know the generator structure:
        # function function{i}() {
        #     ...
        #     return ...  <-- Target
        # }
        
        for i in range(1, self.num_actions + 1):
            func_def_str = f"function function{i}() {{"
            found_func = False
            for line_idx, line in enumerate(lines):
                if func_def_str in line:
                    found_func = True
                    # Look for return statement in subsequent lines
                    for offset in range(1, 10): # Look ahead a few lines
                        if line_idx + offset < len(lines):
                            if "return process.hrtime.bigint()" in lines[line_idx + offset]:
                                action_lines.append(line_idx + offset + 1) # 1-based line number
                                break
                    break
            
            if not found_func:
                self.logger.warning(f"Could not find definition for function{i} in source code.")
        
        return action_lines

    def execute_benchmark(self) -> LightrunOverheadBenchmarkResult:
        """Execute the benchmark logic."""

        from Lightrun.Benchmarks.shared_modules.api import LightrunAPI, LightrunPublicAPI, LightrunPluginAPI
        import time
        from Lightrun.Benchmarks.shared_modules.authentication import ApiKeyAuthenticator, InteractiveAuthenticator
        from Lightrun.Benchmarks.shared_modules.agent_models import BreakpointAction, LogAction
        from Lightrun.Benchmarks.shared_modules.agent_actions import AgentActions
        from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.send_request_task import SendRequestTask

        self.logger.info(f"Executing benchmark with {self.num_actions} {self.action_type} actions on {self.runtime}")


        # Initialize Lightrun API with correct authenticator
        if isinstance(self.authenticator, InteractiveAuthenticator):
            self.logger.info("Using internal Plugin API for User Token authentication.")
            api: LightrunAPI = LightrunPluginAPI(self.lightrun_api_url, self.lightrun_company_id, self.authenticator, logger=self.logger)
        else:
             self.logger.info("Using Public API for API Key authentication.")
             api: LightrunAPI = LightrunPublicAPI(self.lightrun_api_url, self.lightrun_company_id, self.authenticator, logger=self.logger)
        
        # 2. Identify Agent ID (DISPLAY_NAME)
        agent_id = self.name 

        # 3. Determine Action Lines
        if self.num_actions > 0:
            action_lines = self._get_action_line_numbers()
            if len(action_lines) != self.num_actions:
                 self.logger.warning(f"Expected {self.num_actions} action lines but found {len(action_lines)}. Adjusting action count.")
        else:
            action_lines = []

        # 4. Create Actions
        actions = []
        filename = "lightrunOverheadBenchmark.js"
        
        for line in action_lines:
            if self.action_type.lower() == 'snapshot':
                actions.append(BreakpointAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600))
            elif self.action_type.lower() == 'log':
                actions.append(LogAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600, log_message="deployment-test-log: Hello from Lightrun!"))
            # Default/Fallback? Raise error? Assuming validated config.

        # 5. Execute with Actions Context
        try:
            with AgentActions(api, agent_id, actions) as active_actions:
                # 6. Send Request
                # Use SendRequestTask directly or mimic its logic? 
                # We need the response payload.
                send_task = SendRequestTask(self.gcp_function)
                
                # Request 1: Warmup / Verify Agent Connection
                # This request ensures the function is hot and the agent has time to connect/sync
                self.logger.info("Sending warmup request...")
                send_task.execute()
                
                # Wait a moment for actions to be bound if not already
                time.sleep(2) 

                # Request 2: Measurement
                self.logger.info("Sending measurement request...")
                start_time = time.perf_counter()
                result = send_task.execute()
                end_time = time.perf_counter()
                
                # 7. Parse Result
                if not result or 'handlerRunTime' not in result:
                     return LightrunOverheadBenchmarkResult(success=False, error=f"Invalid response from function: {result}")

                handler_run_time_ns = int(result['handlerRunTime'])
                
                # 8. Verify Action Triggering
                # Iterate over applied actions and check their hit count/status
                actions_triggered = 0
                missing_actions = []
                
                # First check if we successfully applied all actions
                if len(active_actions.applied_actions) != self.num_actions:
                    self.logger.error(f"Failed to apply all actions. Expected {self.num_actions}, applied {len(active_actions.applied_actions)}.")
                    return LightrunOverheadBenchmarkResult(
                         success=False,
                         error=f"Action Application Failed: Expected {self.num_actions} actions, succeeded in applying {len(active_actions.applied_actions)}. Check credentials.",
                         total_run_time_sec=end_time - start_time,
                         handler_run_time_ns=handler_run_time_ns,
                         actions_count=len(active_actions.applied_actions)
                     )

                # Allow a short buffer for async reporting from agent to server
                max_retries = 3
                for _ in range(max_retries):
                    actions_triggered = 0
                    missing_actions = []
                    
                    for action, action_id in active_actions.applied_actions:
                        status = None
                        is_hit = False
                        
                        if isinstance(action, BreakpointAction):
                            info = api.get_snapshot(action_id)
                            # Check if CAPTURED or if hit count > 0 (snapshots might be consumable)
                            if info and (info.get('captureState') == 'CAPTURED' or info.get('hitCount', 0) > 0):
                                is_hit = True
                        elif isinstance(action, LogAction):
                            info = api.get_log(action_id)
                            if info and info.get('hitCount', 0) > 0:
                                is_hit = True
                        
                        if is_hit:
                            actions_triggered += 1
                        else:
                            missing_actions.append(f"{action.__class__.__name__}:{action_id}")
                    
                    if actions_triggered == len(active_actions.applied_actions):
                        break
                    
                    time.sleep(1) # Wait before retry

                if actions_triggered < self.num_actions:
                     self.logger.warning(f"Verification Failed: Only {actions_triggered}/{self.num_actions} actions triggered. Missing: {missing_actions}")
                     return LightrunOverheadBenchmarkResult(
                         success=False,
                         error=f"Partial action triggering: {actions_triggered}/{self.num_actions} triggered. Potential throttling or agent lag.",
                         total_run_time_sec=end_time - start_time,
                         handler_run_time_ns=handler_run_time_ns,
                         actions_count=self.num_actions
                     )

                self.logger.info(f"Verification Successful: All {actions_triggered} actions triggered.")

                return LightrunOverheadBenchmarkResult(
                    success=True,
                    total_run_time_sec=end_time - start_time,
                    handler_run_time_ns=handler_run_time_ns,
                    actions_count=self.num_actions
                )

        except Exception as e:
            self.logger.error(f"Benchmark execution failed: {e}")
            return LightrunOverheadBenchmarkResult(success=False, error=str(e))
