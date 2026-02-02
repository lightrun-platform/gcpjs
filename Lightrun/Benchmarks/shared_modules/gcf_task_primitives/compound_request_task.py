"""Sequential request task for executing multiple requests against a Cloud Function."""

import time
from typing import Dict, Any, Optional, List
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction
from Lightrun.Benchmarks.shared_modules.lightrun_api import LightrunAPI
from .send_request_task import SendRequestTask


from Lightrun.Benchmarks.shared_modules.logger_factory import LoggerFactory

class CompoundRequestTask:
    """Task to send multiple requests to a Cloud Function sequentially."""

    def __init__(
        self,
        function: GCPFunction,
        delay_between_requests: int,
        num_requests: int,
        skip_lightrun_action_setup: bool,
        logger_factory: LoggerFactory,
        lightrun_api_key: Optional[str] = None,
        lightrun_company_id: Optional[str] = None,
        lightrun_api_url: Optional[str] = None,
    ):
        """
        Initialize sequential request task.

        Args:
            function: GCPFunction object including URL and Index
            delay_between_requests: Seconds to wait between requests
            num_requests: Number of requests to send
            skip_lightrun_action_setup: If True, skip setting up Lightrun actions
            logger_factory: Factory to create loggers
            lightrun_api_key: API key for Lightrun API
            lightrun_company_id: Company ID for Lightrun API
            lightrun_api_url: Optional custom API URL for Lightrun
        """
        self.function = function
        self.delay_between_requests = delay_between_requests
        self.num_requests = num_requests
        self.skip_lightrun_action_setup = skip_lightrun_action_setup
        self.logger_factory = logger_factory
        self.logger = logger_factory.get_logger(f"CompoundRequestTask_{function.index}")
        self.lightrun_api_key = lightrun_api_key
        self.lightrun_company_id = lightrun_company_id
        self.lightrun_api_url = lightrun_api_url

        # Determine if this is a "With Lightrun" function
        self.is_lightrun = function.is_lightrun_variant

    def execute(self) -> Dict[str, Any]:
        """Execute the request task with multiple requests."""
        all_results: List[Dict[str, Any]] = []
        cold_start_duration = 0.0
        warm_request_durations = 0.0
        total_duration = 0.0

        # Create the single request task primitive
        # We re-use it or create new one? Creating new one per request or once seems fine.
        # SendRequestTask is now stateless regarding iteration, so one instance is fine if it just holds the function.
        single_task = SendRequestTask(self.function)

        for i in range(1, self.num_requests + 1):
            result = single_task.execute(request_number=i)
            all_results.append(result)

            if not result.get('error'):
                # Handle both Python (totalDuration) and Node.js (handlerRunTime) metric names
                duration_str = result.get('totalDuration') or result.get('handlerRunTime')
                duration = float(duration_str) if duration_str is not None else 0.0
                total_duration += duration

                if i == 1:
                    cold_start_duration = duration
                    is_cold = result.get('isColdStart', False)
                    # Use higher precision if duration is small
                    duration_s = duration / 1e9
                    if duration_s < 0.1:
                        self.logger.info(f"[{self.function.index:3d}] Request 1/{self.num_requests}: Cold={is_cold}, Duration={duration/1e6:.3f}ms")
                    else:
                        self.logger.info(f"[{self.function.index:3d}] Request 1/{self.num_requests}: Cold={is_cold}, Duration={duration_s:.3f}s")

                    if self.is_lightrun and not self.skip_lightrun_action_setup:
                        self._add_lightrun_snapshot()
                else:
                    warm_request_durations += duration
                    if self.num_requests <= 5 or i % 5 == 0 or i == self.num_requests: # Reduce log noise for many requests
                        duration_s = duration / 1e9
                        if duration_s < 0.1:
                            self.logger.info(f"[{self.function.index:3d}] Request {i}/{self.num_requests}: Duration={duration/1e6:.3f}ms")
                        else:
                            self.logger.info(f"[{self.function.index:3d}] Request {i}/{self.num_requests}: Duration={duration_s:.3f}s")
            else:
                self.logger.info(f"[{self.function.index:3d}] Request {i}/{self.num_requests}: FAILED")

            # Wait between requests (except after the last one)
            if i < self.num_requests:
                time.sleep(self.delay_between_requests)

        # Aggregate results
        first_result = all_results[0] if all_results else {}
        return {
            **first_result,  # Include first request's detailed data
            '_function_index': self.function.index,
            '_display_name': self.function.display_name,
            '_all_request_results': all_results,
            'totalDurationForColdStarts': cold_start_duration,
            'totalDurationForWarmRequests': warm_request_durations,
            'totalDuration': total_duration,
            'handlerRunTime': first_result.get('handlerRunTime'), # Perpetuate the metric name
            '_num_requests': self.num_requests,
            '_num_successful_requests': sum(1 for r in all_results if not r.get('error')),
        }

    def _add_lightrun_snapshot(self):
        """Add a Lightrun snapshot to the function's agent."""
        lightrun_api = LightrunAPI(
            api_key=self.lightrun_api_key or '',
            company_id=self.lightrun_company_id or '',
            api_url=self.lightrun_api_url,
            logger_factory=self.logger_factory
        )

        agent_id = lightrun_api.get_agent_id(self.function.display_name)
        if agent_id:
            lightrun_api.add_snapshot(
                agent_id=agent_id,
                filename="helloLightrun.js",
                line_number=67,
                max_hit_count=self.num_requests,
            )
