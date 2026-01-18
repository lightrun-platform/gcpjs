"""Send request task for testing Cloud Functions."""

import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any


class SendRequestTask:
    """Task to send a request to a Cloud Function."""
    
    def __init__(self, url: str, function_index: int):
        """
        Initialize send request task.
        
        Args:
            url: URL of the Cloud Function
            function_index: Index of the function
        """
        self.url = url
        self.function_index = function_index
    
    def execute(self) -> Dict[str, Any]:
        """Execute the request task."""
        try:
            start_time = time.time()
            response = requests.get(self.url, timeout=60)
            end_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                data['_function_index'] = self.function_index
                data['_request_latency'] = (end_time - start_time) * 1_000_000_000  # Convert to nanoseconds
                data['_timestamp'] = datetime.now(timezone.utc).isoformat()
                data['_url'] = self.url
                return data
            else:
                return {
                    'function_index': self.function_index,
                    'error': True,
                    'status_code': response.status_code,
                    'message': response.text[:200],
                    '_timestamp': datetime.now(timezone.utc).isoformat(),
                    '_url': self.url
                }
        except Exception as e:
            return {
                'function_index': self.function_index,
                'error': True,
                'exception': str(e),
                '_timestamp': datetime.now(timezone.utc).isoformat(),
                '_url': self.url
            }
