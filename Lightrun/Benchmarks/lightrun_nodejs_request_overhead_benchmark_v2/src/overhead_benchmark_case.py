from logging import Logger
from pathlib import Path
from typing import List, Dict

import time

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.lightrun_overhead_benchmark_case_dto import LightrunOverheadBenchmarkCaseDTO, BenchmarkMeasurement
from Lightrun.Benchmarks.shared_modules.benchmark_case import BenchmarkCase
from Lightrun.Benchmarks.shared_modules.gcf_models.benchmark_result import LightrunBenchmarkResult
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
from Benchmarks.shared_modules.cpu_model import CpuModel


class LightrunOverheadBenchmarkCase(BenchmarkCase[LightrunOverheadBenchmarkResult]):
    """Benchmark case for Lightrun overhead measurement."""

    AGENT_POLL_INTERVAL_SECONDS = 1
    AGENT_POLL_TIMEOUT_GRACE_SECONDS = 40
    DEFAULT_DELAY_BETWEEN_TESTS_SECONDS = 10

    def __init__(self,
                 *,
                 benchmark_name: str,
                 runtime: str,
                 region: str,
                 source_code_dir: Path,
                 entry_point: str,
                 test_size: int,
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
                 agent_actions_update_interval_seconds: int,
                 lightrun_agent_log_level: str,
                 required_cpu_model: str | None = None,
                 delay_between_tests_seconds: int | None = None):
        super().__init__(deployment_timeout, delete_timeout, clean_after_run=clean_after_run)
        self.benchmark_name = benchmark_name
        self.runtime = runtime
        self.region = region
        self.source_code_dir = source_code_dir
        self.entry_point = entry_point
        self.test_size = test_size
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
        self.lightrun_agent_log_level = lightrun_agent_log_level
        self.authentication_type = authentication_type
        self.required_cpu_model = required_cpu_model
        self.delay_between_tests_seconds = delay_between_tests_seconds or self.DEFAULT_DELAY_BETWEEN_TESTS_SECONDS
        self._gcp_function = None
        self._logger = logger_factory.get_logger(self.name)
        # Results for each action count tested (key: num_actions, value: measurement result)
        self.benchmark_results: Dict[int, BenchmarkMeasurement] = {}


        match authentication_type:
            case AuthenticationType.API_KEY:
                self.logger.info("Using public api with a public API key for API authentication.")
                self.lightrun_api = ApiKeyAuthenticator(lightrun_api_key)
            case AuthenticationType.MANUAL:
                self.logger.info("Using internal Plugin API with User Token authentication for API authentication.")
                self.lightrun_api = LightrunPluginAPI(f"https://{self.lightrun_api_hostname}", self.lightrun_company_id, logger=self.logger, api_version=self.lightrun_version)


    def to_dto(self) -> LightrunOverheadBenchmarkCaseDTO:
        return LightrunOverheadBenchmarkCaseDTO(
        deployment_timeout_seconds=self.deployment_timeout_seconds,
        delete_timeout_seconds=self.delete_timeout_seconds,
        clean_after_run=self.clean_after_run,
        benchmark_name = self.benchmark_name,
        name=self.name,
        runtime = self.runtime,
        region = self.region,
        source_code_dir = self.source_code_dir,
        entry_point = self.entry_point,
        test_size = self.test_size,
        action_type = self.action_type,
        authentication_type=self.authentication_type,
        lightrun_company_id = self.lightrun_company_id,
        lightrun_api_hostname = self.lightrun_api_hostname,
        project = self.project,
        memory = self.memory,
        cpu = self.cpu,
        timeout = self.timeout,
        gen2 = self.gen2,
        lightrun_version = self.lightrun_version,
        agent_actions_update_interval_seconds = self.agent_actions_update_interval_seconds,
        lightrun_agent_log_level = self.lightrun_agent_log_level,
        deployment_result=self.deployment_result,
        delete_result=self.delete_result,
        benchmark_results=self.benchmark_results
        )

    @property
    def logger(self) -> Logger:
        return self._logger

    def case_identifier(self) -> str:
        sanitized_mem = self.memory.lower()
        sanitized_cpu = self.cpu.replace('.', 'p')
        generation = "gen2" if self.gen2 else "gen1"
        return f"{self.runtime}-{generation}-{sanitized_mem}-{sanitized_cpu}cpu-{self.test_size}size-{self.region}"

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
            logger=self.logger,
            required_cpu_model=self.required_cpu_model
        )
        return self._gcp_function

    @property
    def env_vars(self) -> dict:
        vars = {
            'LIGHTRUN_SECRET': self.lightrun_secret, # special lightrun agent environment variable which configured the lightrun secret
            'DISPLAY_NAME': self.name,
            'LIGHTRUN_API_ENDPOINT': self.lightrun_api_hostname, # special lightrun agent environment variable which configures the location of the lightrun server. it is misleadingly called ENDPOINT, implying a full url but it actually expects only the hostname without protocol prefix
            'AGENT_LOG_LEVEL' : self.lightrun_agent_log_level # log level for the running lightrun agent in the benchmark
        }
        # Add CPU pinning env vars if specified
        # Instead of passing the model name, we pass the vendor and flags to check
        # This keeps the JS code simple - it just verifies vendor and flags match
        if self.required_cpu_model:
            # Look up the CpuModel enum by its display_name (the human-readable name)
            cpu_model = None
            for model in CpuModel:
                if model.display_name == self.required_cpu_model:
                    cpu_model = model
                    break
            
            if cpu_model and cpu_model.can_be_pinned():
                vendor, flags, excluded_flags = cpu_model.get_signature()
                vars['REQUIRED_CPU_MODEL'] = self.required_cpu_model  # For logging/error messages
                vars['REQUIRED_CPU_VENDOR'] = vendor
                # Use pipe delimiter instead of comma to avoid gcloud --set-env-vars parsing issues
                # (gcloud uses comma as separator between key=value pairs)
                vars['REQUIRED_CPU_FLAGS'] = '|'.join(flags)
                # Excluded flags: flags that must NOT be present (to distinguish from newer generations)
                if excluded_flags:
                    vars['EXCLUDED_CPU_FLAGS'] = '|'.join(excluded_flags)
            else:
                # Model name provided but can't be pinned - just pass the name for error messages
                vars['REQUIRED_CPU_MODEL'] = self.required_cpu_model
        return vars

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
        
        for i in range(1, self.test_size + 1):
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

    def _wait_for_actions_to_bind(self, debug_session: DebuggingSession) -> bool:
        """
        Wait for actions to be bound to the agent, with early exit detection.
        
        Uses the getActionsByAgent endpoint to efficiently check if all applied actions
        have been ACCEPTED by the agent (not just submitted), allowing early exit instead 
        of waiting the full duration.
        
        Action acceptanceStatus lifecycle:
            SUBMITTED -> REQUESTED -> ACCEPTED

        legend:

        SUBMITTED	Server knows about the action, but agent hasn't fetched it yet
        REQUESTED	Agent fetched the action definition from the server
        ACCEPTED    the agent has successfully injected the instrumentation bytecode at the target location

        We wait for ACCEPTED to infer that the breakpoint is ready for test.
        
        Args:
            debug_session: The active debugging session with applied actions.
            
        Returns:
            True if all actions were confirmed ACCEPTED before timeout, False if timed out.
        """

        max_wait = self.agent_actions_update_interval_seconds + LightrunOverheadBenchmarkCase.AGENT_POLL_TIMEOUT_GRACE_SECONDS
        poll_interval = LightrunOverheadBenchmarkCase.AGENT_POLL_INTERVAL_SECONDS

        self.logger.info(f"Waiting up to {max_wait}s for agent to accept {len(debug_session.actions)} actions. "
                         f"Polling every {poll_interval}s for early detection.")

        expected_bounded_action_ids = {action.action_id for action in debug_session.actions}
        bounded_action_ids = set()
        seconds_until_timeout = max_wait
        for elapsed in range(0, max_wait, poll_interval):
            bounded_action_ids = debug_session.get_bounded_actions_ids()
            if bounded_action_ids == expected_bounded_action_ids:
                self.logger.info(f"All actions were accepted after {elapsed} seconds.")
                return True

            # sleep if some of the actions have not been bounded yet

            self.logger.info(f"Waiting for actions to be fetched by the agent... accepted actions: {len(bounded_action_ids)}/{len(expected_bounded_action_ids)}. {seconds_until_timeout}s left until timeout.")
            time.sleep(poll_interval)
            seconds_until_timeout -= poll_interval

            # the following step is important. after we wake up we have to trigger the function
            # otherwise it will not wake up to fetch breakpoints.
            # unfortunately this might also carry the side effect of letting the git
            # more opportunities to optimize, making the duration of the test a less reliable
            # metric, since it is affected by the number of rounds this loop made before
            # until the agent fetched its actions. this is why its imperative to add
            # a warmup phase to the test so it will already be "maximally optimized"
            # before getting here to allow stable comparison between different
            # benchmark case results and different runs.
            SendRequestTask(self.gcp_function).execute()
        
        self.logger.warning(f"Timed out waiting for actions to be accepted after {max_wait}s. Pending actions: {[action for action in debug_session.actions if action.action_id not in bounded_action_ids ]}")
        return False

    def warmup(self):
        # Todo - important! add definition later.
        pass # stub

    def _create_actions_for_count(self, num_actions: int) -> List[BreakpointAction | LogAction]:
        """Create a list of actions for a given action count."""
        if num_actions <= 0:
            return []
        
        action_lines = self._get_action_line_numbers()
        if len(action_lines) < num_actions:
            self.logger.warning(f"Requested {num_actions} actions but only {len(action_lines)} action lines available.")
            num_actions = len(action_lines)
        
        actions = []
        filename = "lightrunOverheadBenchmark.js"
        
        for line in action_lines[:num_actions]:
            if self.action_type.lower() == 'snapshot':
                actions.append(BreakpointAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600))
            elif self.action_type.lower() == 'log':
                actions.append(LogAction(filename=filename, line_number=line, max_hit_count=1, expire_seconds=3600, log_message="deployment-test-log: Hello from Lightrun!"))
        
        return actions

    def _verify_actions_triggered(self, debug_session: DebuggingSession, num_actions: int) -> tuple[bool, int, List[str]]:
        """Verify that all actions were triggered.
        
        Returns:
            Tuple of (success, actions_triggered_count, missing_actions_list)
        """
        max_retries = 10
        actions_triggered = 0
        missing_actions = []
        
        for attempt in range(max_retries):
            actions_triggered = 0
            missing_actions = []
            
            for action in debug_session.applied_actions:
                try:
                    is_hit = False
                    info = action.get_info(self.lightrun_api)
                    if info:
                        hit_count = info.get('hitCount', 0)
                        if hit_count > 0:
                            is_hit = True
                        status = f"Hits={hit_count}"
                    else:
                        status = "Info=None"
                except Exception as e:
                    status = f"Error fetching snapshot: {e}"
                
                if is_hit:
                    actions_triggered += 1
                else:
                    missing_actions.append(f"{action.__class__.__name__}:{action.action_id} ({status})")
            
            if actions_triggered == len(debug_session.applied_actions):
                return True, actions_triggered, []
            
            self.logger.info(f"Verification attempt {attempt+1}/{max_retries}: {actions_triggered}/{num_actions} triggered. Missing: {missing_actions}")
            time.sleep(2)
        
        return False, actions_triggered, missing_actions

    def _run_single_measurement(self, send_task: SendRequestTask, num_actions: int, 
                                 agent_display_name: str, cpu_info_cache: dict) -> BenchmarkMeasurement:
        """Run a single measurement for a given action count.
        
        Args:
            send_task: The task to send requests to the function
            num_actions: Number of actions for this measurement
            agent_display_name: The agent display name for the debugging session
            cpu_info_cache: Dict to cache cpu_info (populated on first measurement)
        
        Returns:
            BenchmarkMeasurement with the result
        """
        self.logger.info(f"--- Running measurement with {num_actions} actions ---")
        
        # Create actions for this measurement
        actions = self._create_actions_for_count(num_actions)
        
        # Use a new DebuggingSession for each measurement
        with DebuggingSession(self.lightrun_api, agent_display_name, actions, self.logger) as debug_session:
            
            # Clear any existing actions on the agent
            debug_session.clear_all_actions_from_agent()
            
            # Apply actions (only if we have any)
            if num_actions > 0:
                debug_session.apply_actions()
                
                # Wait for actions to bind
                if not self._wait_for_actions_to_bind(debug_session):
                    return BenchmarkMeasurement(
                        success=False,
                        actions_count=num_actions,
                        error=f"Timed out waiting for {num_actions} actions to bind",
                        cpu_info=cpu_info_cache.get('cpu_info')
                    )
            
            # Send measurement request
            self.logger.info("Sending measurement request...")
            result = send_task.execute()
            
            # Parse result
            if not result or 'handlerRunTime' not in result:
                return BenchmarkMeasurement(
                    success=False,
                    actions_count=num_actions,
                    error=f"Invalid response from function, missing 'handlerRunTime' attribute: {result}",
                    cpu_info=cpu_info_cache.get('cpu_info')
                )
            
            handler_run_time_ns = int(result['handlerRunTime'])
            
            if not result or 'cpuInfo' not in result:
                return BenchmarkMeasurement(
                    success=False,
                    actions_count=num_actions,
                    error=f"Invalid response from function, missing 'cpuInfo' attribute: {result}",
                    cpu_info=cpu_info_cache.get('cpu_info')
                )
            
            cpu_info = result['cpuInfo']
            cpu_info_cache['cpu_info'] = cpu_info  # Cache for future failures
            
            # Verify actions triggered (only if we have actions)
            if num_actions > 0:
                success, actions_triggered, missing_actions = self._verify_actions_triggered(debug_session, num_actions)
                if not success:
                    self.logger.warning(f"Verification Failed: Only {actions_triggered}/{num_actions} actions triggered. Missing: {missing_actions}")
                    return BenchmarkMeasurement(
                        success=False,
                        actions_count=num_actions,
                        error=f"Partial action triggering: {actions_triggered}/{num_actions} triggered. Potential throttling or agent lag.",
                        cpu_info=cpu_info
                    )
                self.logger.info(f"Verification Successful: All {actions_triggered} actions triggered.")
            else:
                self.logger.info("No actions to verify (baseline measurement with 0 actions).")
            
            return BenchmarkMeasurement(
                success=True,
                actions_count=num_actions,
                handler_run_time_ns=handler_run_time_ns,
                cpu_info=cpu_info
            )

    def execute_benchmark(self) -> LightrunOverheadBenchmarkResult:
        """Execute the benchmark logic for all action counts (0 to test_size).
        
        This method deploys a single function and runs multiple measurements,
        varying the number of actions from 0 to test_size. This is more efficient
        than deploying separate functions for each action count.
        
        Results for each action count are stored in self.benchmark_results dict.
        
        Returns:
            A single result indicating overall success/failure with the DTO containing all measurements.
        """
        cpu_info_cache: dict = {}  # Cache CPU info for failures that happen before we get it
        
        self.logger.info(f"Executing benchmark with action counts 0 to {self.test_size} using {self.action_type} actions on {self.runtime}")
        
        agent_display_name = self.name
        
        try:
            send_task = SendRequestTask(self.gcp_function)
            
            # Initial warmup request - triggers agent startup and registration
            self.logger.info("Sending initial warmup request to trigger agent registration...")
            cold_start_request = send_task.execute()
            
            # Validate agent initialization
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
            
            # Cache CPU info from cold start if available
            if cold_start_request and 'cpuInfo' in cold_start_request:
                cpu_info_cache['cpu_info'] = cold_start_request['cpuInfo']
            
            # Warmup phase
            self.warmup()
            
            # Run measurements for each action count: 0, 1, 2, ..., test_size
            for num_actions in range(self.test_size + 1):
                measurement = self._run_single_measurement(send_task, num_actions, agent_display_name, cpu_info_cache)
                self.benchmark_results[num_actions] = measurement
                
                # Log result summary
                if measurement.success:
                    self.logger.info(f"Measurement {num_actions}/{self.test_size}: SUCCESS - {measurement.handler_run_time_ns}ns")
                else:
                    self.logger.warning(f"Measurement {num_actions}/{self.test_size}: FAILURE - {measurement.error}")
                
                # Pause between tests to avoid exhausting CPU quota
                # (skip pause after the last measurement)
                if num_actions < self.test_size:
                    self.logger.info(f"Pausing {self.delay_between_tests_seconds}s before next measurement...")
                    time.sleep(self.delay_between_tests_seconds)
            
            # Determine overall success (all measurements succeeded)
            all_success = all(m.success for m in self.benchmark_results.values())
            success_count = sum(1 for m in self.benchmark_results.values() if m.success)
            
            self.logger.info(f"Benchmark completed. {success_count}/{len(self.benchmark_results)} measurements succeeded.")
            
            if all_success:
                return LightrunBenchmarkResult.SUCCESS(
                    benchmark_case_dto=self.to_dto(),
                    handler_run_time_ns=0,  # Not applicable for aggregate result
                    actions_count=self.test_size,
                    cpu_info=cpu_info_cache.get('cpu_info')
                )
            else:
                failed_actions = [k for k, v in self.benchmark_results.items() if not v.success]
                return LightrunBenchmarkResult.FAILURE(
                    benchmark_case_dto=self.to_dto(),
                    error=f"Some measurements failed: action counts {failed_actions}",
                    cpu_info=cpu_info_cache.get('cpu_info')
                )
            
        except Exception as e:
            self.logger.exception(f"Benchmark execution failed with an exception: {e}")
            return LightrunBenchmarkResult.FAILURE(
                benchmark_case_dto=self.to_dto(),
                error=str(e),
                cpu_info=cpu_info_cache.get('cpu_info')
            )
