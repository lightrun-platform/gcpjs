"""Performance testing for Cloud Functions."""
import asyncio
import time
import requests
from typing import Tuple, Optional
from .config import NUM_COLD_START_REQUESTS, NUM_WARM_START_REQUESTS


class PerformanceTester:
    """Handles performance testing (cold/warm starts)."""
    
    def __init__(self, cold_start_requests: int = NUM_COLD_START_REQUESTS, 
                 warm_start_requests: int = NUM_WARM_START_REQUESTS):
        self.cold_start_requests = cold_start_requests
        self.warm_start_requests = warm_start_requests
    
    def invoke_function(self, url: str, wait_between: float = 0.1) -> Tuple[bool, float, Optional[str]]:
        """Invoke a function and return success, duration in ms, and error."""
        try:
            start = time.time()
            response = requests.get(url, timeout=30)
            duration = (time.time() - start) * 1000  # Convert to ms
            
            if response.status_code == 200:
                return True, duration, None
            else:
                return False, duration, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, 0, str(e)
    
    async def test_cold_warm_starts(self, url: str) -> Tuple[float, float, int, int]:
        """
        Test cold start and warm start performance.
        
        Note: Only the first request to a GCP function is a cold start.
        All subsequent requests are warm starts (until the function instance
        is terminated by GCP, which typically takes 15+ minutes of inactivity).
        """
        # First request - THE ONLY cold start
        cold_times = []
        cold_success = 0
        
        print(f"  Testing first request (cold start - only one per function)...")
        success, duration, error = self.invoke_function(url)
        if success:
            cold_times.append(duration)
            cold_success += 1
        else:
            print(f"    ⚠️  First request failed: {error}")
        
        # Warm start: rapid requests (definitely warm)
        warm_times = []
        warm_success = 0
        
        print(f"  Testing warm starts ({self.warm_start_requests} rapid requests)...")
        # Small delay before rapid requests to ensure function is warm
        await asyncio.sleep(1)
        
        for i in range(self.warm_start_requests):
            success, duration, error = self.invoke_function(url, wait_between=0.05)
            if success:
                warm_times.append(duration)
                warm_success += 1
            if (i + 1) % 20 == 0:
                print(f"    Completed {i + 1}/{self.warm_start_requests} warm start requests")
        
        cold_avg = sum(cold_times) / len(cold_times) if cold_times else 0
        warm_avg = sum(warm_times) / len(warm_times) if warm_times else 0
        
        return cold_avg, warm_avg, cold_success, warm_success
