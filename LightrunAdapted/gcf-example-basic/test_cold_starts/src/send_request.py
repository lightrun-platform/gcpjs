"""Send request task for testing Cloud Functions."""

import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from .models import GCPFunction


class SendRequestTask:
    """Task to send a request to a Cloud Function."""
    
    def __init__(self, function: GCPFunction):
        """
        Initialize send request task.
        
        Args:
            function: GCPFunction object including URL and Index
        """
        self.function = function
        self.url = function.url
        self.function_index = function.index
    
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
