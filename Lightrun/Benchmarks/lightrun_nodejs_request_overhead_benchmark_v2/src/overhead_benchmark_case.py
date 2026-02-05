from logging import Logger
from pathlib import Path
from typing import List

import time

from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction
from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_result import LightrunOverheadBenchmarkResult
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import MAX_GCP_FUNCTION_NAME_LENGTH
from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

from Benchmarks.shared_modules.api import LightrunPluginAPI
from Benchmarks.shared_modules.authentication import ApiKeyAuthenticator
from Benchmarks.shared_modules.authentication.authenticator import AuthenticationType
from Lightrun.Benchmarks.shared_modules.agent_models import BreakpointAction, LogAction
from Lightrun.Benchmarks.shared_modules.debugging_session import DebuggingSession

from Benchmarks.shared_modules.gcf_task_primitives.send_request_task import SendRequestTask


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
                 lightrun_api_hostname: str,
                 project: str,
                 memory: str,
                 cpu: str,
                 timeout: int,
                 gen2: bool,
                 deployment_timeout: int,
                 delete_timeout: int,
                 authentication_type: AuthenticationType,
                 logger_factory: LoggerFactory,
                 lightrun_version: str,
                 clean_after_run: bool,
                 agent_actions_update_interval_seconds: int):
        super().__init__(deployment_timeout, delete_timeout, clean_after_run=clean_after_run)
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
        self.lightrun_api_hostname = lightrun_api_hostname
        self.project = project
        self.memory = memory
        self.cpu = cpu
        self.timeout = timeout
        self.gen2 = gen2
        self.lightrun_version = lightrun_version
        self.agent_actions_update_interval_seconds = agent_actions_update_interval_seconds
        self._gcp_function = None
        self._logger = logger_factory.get_logger(self.name)


        match authentication_type:
            case AuthenticationType.API_KEY:
                self.logger.info("Using public api with a public API key for API authentication.")
                self.lightrun_api = ApiKeyAuthenticator(lightrun_api_key)
            case AuthenticationType.MANUAL:
                self.logger.info("Using internal Plugin API with User Token authentication for API authentication.")
                self.lightrun_api = LightrunPluginAPI(f"https://{self.lightrun_api_hostname}", self.lightrun_company_id, logger=self.logger, api_version=self.lightrun_version)

    @property
    def logger(self) -> Logger:
        return self._logger

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
            'LIGHTRUN_SECRET': self.lightrun_secret, # special lightrun agent environment variable which configured the lightrun secret
            'DISPLAY_NAME': self.name,
            'LIGHTRUN_API_ENDPOINT': self.lightrun_api_hostname # special lightrun agent environment variable which configures the location of the lightrun server. it is misleadingly called ENDPOINT, implying a full url but it actually expects only the hostname without protocol prefix
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

    def _wait_for_actions_to_bind(self, debug_session: DebuggingSession, poll_interval: int = 2) -> bool:
        """
        Wait for actions to be bound to the agent, with early exit detection.
        
        Uses the getActionsByAgent endpoint to efficiently check if all applied actions
        have been received by the agent, allowing early exit instead of waiting the full duration.
        
        Args:
            debug_session: The active debugging session with applied actions.
            poll_interval: Seconds between status checks (default 2).
            
        Returns:
            True if all actions were confirmed bound, False if timed out.
        """
        
        max_wait = self.agent_actions_update_interval_seconds + 10  # + grace period
        expected_action_ids = {action_id for _, action_id in debug_session.applied_actions}
        missing_actions = expected_action_ids.copy()
        self.logger.info(f"Waiting up to {max_wait}s for agent to bind {len(expected_action_ids)} actions. "
                         f"Polling every {poll_interval}s for early detection.")

        for elapsed in range(0, max_wait, poll_interval):

            # Get all actions currently bound to this agent (single API call)
            agent_actions = self.lightrun_api.get_actions_by_agent(debug_session.agent_id, debug_session.agent_pool_id)
            
            # Log response on first poll to help debug
            if elapsed == 0:
                self.logger.debug(f"Agent actions response (first poll): {agent_actions}")
            
            # Extract action IDs from the response
            bound_action_ids = {action.get('id') for action in agent_actions if action.get('id')}
            
            # Check if all our expected actions are in the bound set
            missing_actions = expected_action_ids - bound_action_ids
            
            if not missing_actions:
                self.logger.info(f"All {len(expected_action_ids)} actions bound to agent after {elapsed + poll_interval}s")
                return True
            
            remaining = max_wait - elapsed - poll_interval
            self.logger.info(f"Waiting for actions to bind... {len(missing_actions)}/{len(expected_action_ids)} still pending, {remaining}s remaining")

            time.sleep(poll_interval)

            # the following step is important. we have to trigger the function otherwise it will not wake up to fetch breakpoints
            # unfortunately this might also carry the side effect of letting the git
            # more opportunities to optimize, making the duration of the test a less reliable
            # metric, since it is affected by the number of rounds this loop made before
            # until the agent fetched its actions. this is why its imperative to add
            # a warmup phase to the test so it will already be "maximally optimized"
            # before getting here to allow stable comparison between different
            # benchmark case results and different runs.
            SendRequestTask(self.gcp_function).execute()
        
        self.logger.warning(f"Timed out waiting for actions to bind after {max_wait}s. Missing actions: {missing_actions}")
        return False

    def warmup(self):
        pass # stub

    def execute_benchmark(self) -> LightrunOverheadBenchmarkResult:
        """Execute the benchmark logic."""

        self.logger.info(f"Executing benchmark with {self.num_actions} {self.action_type} actions on {self.runtime}")
        
        # 1. get Agent Display Name (used to identify the agent on the server)
        agent_display_name = self.name

        # 2. Determine Action Lines
        if self.num_actions > 0:
            action_lines = self._get_action_line_numbers()
            if len(action_lines) != self.num_actions:
                 self.logger.warning(f"Expected {self.num_actions} action lines but found {len(action_lines)}. Adjusting action count.")
        else:
            action_lines = []

        # 3. Create Actions
        actions = []
        filename = "lightrunOverheadBenchmark.js"
        
        for line in action_lines:
            if self.action_type.lower() == 'snapshot':
                actions.append(BreakpointAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600))
            elif self.action_type.lower() == 'log':
                actions.append(LogAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600, log_message="deployment-test-log: Hello from Lightrun!"))

        # 4. Execute with Actions Context
        try:
            send_task = SendRequestTask(self.gcp_function)
            
            # Step 1: Warmup request - triggers agent startup and registration
            # The agent registers with the server during the first request execution.
            # Once this request completes, the agent is already registered (sends "isLambda: true" header).
            self.logger.info("Sending warmup request to trigger agent registration...")
            cold_start_request = send_task.execute()
            
            # Validate that the agent initialized with the correct display name
            if cold_start_request and 'initArguments' in cold_start_request:
                init_args = cold_start_request['initArguments']
                returned_display_name = init_args.get('metadata', {}).get('registration', {}).get('displayName')
                
                if returned_display_name != agent_display_name:
                    raise ValueError(
                        f"Agent initialized with incorrect display name. "
                        f"Expected: '{agent_display_name}', Got: '{returned_display_name}'. "
                        f"Full initArguments: {init_args}"
                    )
                self.logger.info(f"Agent registered with display name: '{returned_display_name}'")
            else:
                self.logger.warning(f"Cold Start response did not contain initArguments. Response: {cold_start_request}")


            self.warmup() # Todo - important! add definition later.


            with DebuggingSession(self.lightrun_api, agent_display_name, actions, self.logger) as debug_session:
                # Step 2: Apply actions
                debug_session.apply_actions()

                # Step 3: Wait for the agent to fetch the actions
                self._wait_for_actions_to_bind(debug_session)

                # Step 4: Measurement request
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
                if len(debug_session.applied_actions) == self.num_actions:
                    self.logger.error(f"Failed to apply all actions. Expected {self.num_actions}, applied {len(debug_session.applied_actions)}.")
                    return LightrunOverheadBenchmarkResult(success=False,
                                                           error=f"Action Application Failed: Expected {self.num_actions} actions, succeeded in applying {len(debug_session.applied_actions)}. Check credentials.",
                                                           total_run_time_sec=end_time - start_time,
                                                           handler_run_time_ns=handler_run_time_ns,
                                                           actions_count=len(debug_session.applied_actions))

                # Allow a short buffer for async reporting from agent to server
                max_retries = 3
                for _ in range(max_retries):
                    actions_triggered = 0
                    missing_actions = []
                    
                    for action, action_id in debug_session.applied_actions:
                        is_hit = False
                        
                        if isinstance(action, BreakpointAction):
                            info = self.lightrun_api.get_snapshot(action_id)
                            # Check if CAPTURED or if hit count > 0 (snapshots might be consumable)
                            if info and (info.get('captureState') == 'CAPTURED' or info.get('hitCount', 0) > 0):
                                is_hit = True
                        elif isinstance(action, LogAction):
                            info = self.lightrun_api.get_log(action_id)
                            if info and info.get('hitCount', 0) > 0:
                                is_hit = True
                        
                        if is_hit:
                            actions_triggered += 1
                        else:
                            missing_actions.append(f"{action.__class__.__name__}:{action_id}")
                    
                    if actions_triggered == len(debug_session.applied_actions):
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
            self.logger.exception(f"Benchmark execution failed with an exception: {e}")
            return LightrunOverheadBenchmarkResult(success=False, error=str(e))
