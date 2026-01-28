"""Send request task for testing Cloud Functions."""

import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import argparse
from .gcf_models import GCPFunction
from .lightrun_api import LightrunAPI


class SendRequestTask:
    """Task to send multiple requests to a Cloud Function."""

    def __init__(self, function: GCPFunction, config: argparse.Namespace):
        """
        Initialize send request task.

        Args:
            function: GCPFunction object including URL and Index
            config: Configuration namespace with test parameters
        """
        self.function = function
        self.url = function.url
        self.function_index = function.index
        self.display_name = function.display_name
        self.config = config
        self.delay_between_requests = getattr(config, 'delay_between_requests', 10)
        self.num_requests = getattr(config, 'test_size', 10)

        # Determine if this is a "With Lightrun" function
        self.is_lightrun = function.is_lightrun_variant

    def _send_single_request(self, request_number: int) -> Dict[str, Any]:
        """Send a single request and return the result."""
        try:
            start_time = time.time()
            response = requests.get(self.url, timeout=60)
            end_time = time.time()
            latency_ns = (end_time - start_time) * 1_000_000_000

            if response.status_code == 200:
                data = response.json()
                data['_request_number'] = request_number
                data['_request_latency'] = latency_ns
                data['_timestamp'] = datetime.now(timezone.utc).isoformat()
                data['_url'] = self.url
                return data
            else:
                return {
                    'error': True,
                    '_request_number': request_number,
                    'status_code': response.status_code,
                    'message': response.text[:200],
                    '_timestamp': datetime.now(timezone.utc).isoformat(),
                    '_url': self.url
                }
        except Exception as e:
            return {
                'error': True,
                '_request_number': request_number,
                'exception': str(e),
                '_timestamp': datetime.now(timezone.utc).isoformat(),
                '_url': self.url
            }

    def execute(self) -> Dict[str, Any]:
        """Execute the request task with multiple requests."""
        all_results: List[Dict[str, Any]] = []
        cold_start_duration = 0.0
        warm_request_durations = 0.0
        total_duration = 0.0

        for i in range(1, self.num_requests + 1):
            result = self._send_single_request(i)
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
                        print(f"[{self.function_index:3d}] Request 1/{self.num_requests}: Cold={is_cold}, Duration={duration/1e6:.3f}ms")
                    else:
                        print(f"[{self.function_index:3d}] Request 1/{self.num_requests}: Cold={is_cold}, Duration={duration_s:.3f}s")

                    if self.is_lightrun and not getattr(self.config, 'skip_lightrun_action_setup', False):
                        self._add_lightrun_snapshot()
                else:
                    warm_request_durations += duration
                    if self.num_requests <= 5 or i % 5 == 0 or i == self.num_requests: # Reduce log noise for many requests
                        duration_s = duration / 1e9
                        if duration_s < 0.1:
                            print(f"[{self.function_index:3d}] Request {i}/{self.num_requests}: Duration={duration/1e6:.3f}ms")
                        else:
                            print(f"[{self.function_index:3d}] Request {i}/{self.num_requests}: Duration={duration_s:.3f}s")
            else:
                print(f"[{self.function_index:3d}] Request {i}/{self.num_requests}: FAILED")

            # Wait between requests (except after the last one)
            if i < self.num_requests:
                time.sleep(self.delay_between_requests)

        # Aggregate results
        first_result = all_results[0] if all_results else {}
        return {
            **first_result,  # Include first request's detailed data
            '_function_index': self.function_index,
            '_display_name': self.display_name,
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
            api_key=getattr(self.config, 'lightrun_api_key', ''),
            company_id=getattr(self.config, 'lightrun_company_id', ''),
            api_url=getattr(self.config, 'lightrun_api_url', None)
        )

        agent_id = lightrun_api.get_agent_id(self.display_name)
        if agent_id:
            lightrun_api.add_snapshot(
                agent_id=agent_id,
                filename="helloLightrun.js",
                line_number=67,
                max_hit_count=self.num_requests,
            )

