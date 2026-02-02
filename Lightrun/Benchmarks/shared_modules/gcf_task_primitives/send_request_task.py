"""Send request task for testing Cloud Functions."""

import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction


class SendRequestTask:
    """Task to send a single request to a Cloud Function."""

    def __init__(self, function: GCPFunction):
        """
        Initialize send request task.

        Args:
            function: GCPFunction object including URL
        """
        self.function = function
        self.url = function.url

    def execute(self, request_number: int = 1) -> Dict[str, Any]:
        """
        Send a single request and return the result.
        
        Args:
            request_number: Optional request number to include in the result
        """
        try:
            start_time = time.perf_counter()
            response = requests.get(self.url, timeout=60)
            end_time = time.perf_counter()
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
                    'message': response.text,
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
