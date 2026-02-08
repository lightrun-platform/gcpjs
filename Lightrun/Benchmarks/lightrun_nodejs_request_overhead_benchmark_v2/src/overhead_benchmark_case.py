from logging import Logger
from pathlib import Path
from typing import List

import time

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.lightrun_overhead_benchmark_case_dto import LightrunOverheadBenchmarkCaseDTO
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


class LightrunOverheadBenchmarkCase(BenchmarkCase[LightrunOverheadBenchmarkResult]):
    """Benchmark case for Lightrun overhead measurement."""

    AGENT_POLL_INTERVAL_SECONDS = 1
    AGENT_POLL_TIMEOUT_GRACE_SECONDS = 40

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
                 agent_actions_update_interval_seconds: int,
                 lightrun_agent_log_level: str):
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
        self.lightrun_agent_log_level = lightrun_agent_log_level
        self.authentication_type = authentication_type
        self._gcp_function = None
        self._logger = logger_factory.get_logger(self.name)


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
        num_actions = self.num_actions,
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
        delete_result=self.delete_result
        )

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
            'LIGHTRUN_API_ENDPOINT': self.lightrun_api_hostname, # special lightrun agent environment variable which configures the location of the lightrun server. it is misleadingly called ENDPOINT, implying a full url but it actually expects only the hostname without protocol prefix
            'AGENT_LOG_LEVEL' : self.lightrun_agent_log_level # log level for the running lightrun agent in the benchmark
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


            with DebuggingSession(self.lightrun_api, agent_display_name, actions, self.logger) as debug_session:

                # Step 1: Clear any existing actions on the agent to ensure a clean slate
                debug_session.clear_all_actions_from_agent()

                # Step 2: Warmup the function so it has stable results that can be compared with other benchmark cases
                self.warmup()

                # Step 2: Apply benchmark actions
                debug_session.apply_actions()

                # Step 3: Wait for the agent to fetch the actions
                self._wait_for_actions_to_bind(debug_session)

                # Step 4: Measurement request
                self.logger.info("Sending measurement request...")
                result = send_task.execute()
                
                # 7. Parse Result
                if not result or 'handlerRunTime' not in result:
                     return LightrunBenchmarkResult.FAILURE(benchmark_case_dto=self.to_dto(), error=f"Invalid response from function, missing 'handlerRunTime' attribute: {result}", cpu_info=None)

                handler_run_time_ns = int(result['handlerRunTime'])

                if not result or 'cpuInfo' not in result:
                     return LightrunBenchmarkResult.FAILURE(benchmark_case_dto=self.to_dto(), error=f"Invalid response from function, missing 'cpuInfo' attribute: {result}", cpu_info=None)

                cpu_info = result['cpuInfo']
                
                # 8. Verify Action Triggering
                # Iterate over applied actions and check their hit count/status
                actions_triggered = 0
                missing_actions = []

                # Allow a short buffer for async reporting from agent to server
                max_retries = 10
                for attempt in range(max_retries):
                    actions_triggered = 0
                    missing_actions = []
                    
                    for action in debug_session.applied_actions:
                        try:
                            is_hit = False
                            info = action.get_info(self.lightrun_api)
                            # Check if CAPTURED or if hit count > 0 (snapshots might be consumable)
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
                        break
                    
                    self.logger.info(f"Verification attempt {attempt+1}/{max_retries}: {actions_triggered}/{self.num_actions} triggered. Missing: {missing_actions}")
                    time.sleep(2) # Wait before retry

                if actions_triggered < self.num_actions:
                     self.logger.warning(f"Verification Failed: Only {actions_triggered}/{self.num_actions} actions triggered. Missing: {missing_actions}")
                     return LightrunBenchmarkResult.FAILURE(benchmark_case_dto=self.to_dto(),
                                                            error=f"Partial action triggering: {actions_triggered}/{self.num_actions} triggered. Potential throttling or agent lag.",
                                                            cpu_info=cpu_info)

                self.logger.info(f"Verification Successful: All {actions_triggered} actions triggered.")

                return LightrunBenchmarkResult.SUCCESS(benchmark_case_dto=self.to_dto(),
                                                       handler_run_time_ns=handler_run_time_ns,
                                                       actions_count=self.num_actions,
                                                       cpu_info=cpu_info)

        except Exception as e:
            self.logger.exception(f"Benchmark execution failed with an exception: {e}")
            return LightrunBenchmarkResult.FAILURE(benchmark_case_dto=self.to_dto(), error=str(e), cpu_info=None)
