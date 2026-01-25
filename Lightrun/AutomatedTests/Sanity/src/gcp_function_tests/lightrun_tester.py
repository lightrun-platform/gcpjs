"""Lightrun API testing functionality."""
import asyncio
import time
import requests
from typing import Tuple, Optional
from .config import LIGHTRUN_API_URL, LIGHTRUN_API_KEY, LIGHTRUN_COMPANY_ID
from .performance_tester import PerformanceTester


class LightrunTester:
    """Handles Lightrun API testing (snapshots, counters, metrics)."""
    
    def __init__(self, api_url: str = LIGHTRUN_API_URL, 
                 api_key: str = LIGHTRUN_API_KEY,
                 company_id: str = LIGHTRUN_COMPANY_ID):
        self.api_url = api_url
        self.api_key = api_key
        self.company_id = company_id
        self.performance_tester = PerformanceTester()
    
    def get_agent_id(self, function_name: str) -> Optional[str]:
        """Get Lightrun agent ID for the function."""
        if not self.api_key or not self.company_id:
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents"
            
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                agents = response.json()
                # Find agent matching function name
                for agent in agents:
                    if function_name in agent.get("displayName", ""):
                        return agent.get("id")
        except Exception as e:
            print(f"    Warning: Could not get agent ID: {e}")
        
        return None
    
    async def test_snapshot(self, function_name: str, function_url: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Test Lightrun snapshot functionality."""
        if not agent_id:
            return False, "Agent ID not found"
        
        if not self.api_key or not self.company_id:
            return False, "Lightrun API credentials not configured"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            snapshot_data = {
                "agentId": agent_id,
                "filename": "index.js",
                "lineNumber": 30,
                "maxHitCount": 1,
                "expireSec": 300
            }
            
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots"
            response = requests.post(url, json=snapshot_data, headers=headers, timeout=30)
            
            if response.status_code not in [200, 201]:
                return False, f"Failed to create snapshot: {response.status_code} - {response.text}"
            
            snapshot_id = response.json().get("id")
            
            # Invoke function to trigger snapshot
            self.performance_tester.invoke_function(function_url)
            
            # Wait a bit for snapshot to be captured
            await asyncio.sleep(2)
            
            # Check if snapshot was captured
            check_url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            check_response = requests.get(check_url, headers=headers, timeout=30)
            
            if check_response.status_code == 200:
                snapshot_data = check_response.json()
                if snapshot_data.get("hitCount", 0) > 0:
                    return True, None
            
            return False, "Snapshot was not captured"
            
        except Exception as e:
            return False, f"Snapshot test error: {str(e)}"
    
    async def test_counter(self, function_name: str, function_url: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Test Lightrun counter functionality."""
        if not agent_id:
            return False, "Agent ID not found"
        
        if not self.api_key or not self.company_id:
            return False, "Lightrun API credentials not configured"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            counter_data = {
                "agentId": agent_id,
                "filename": "index.js",
                "lineNumber": 30,
                "name": f"test_counter_{function_name}",
                "expireSec": 300
            }
            
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/counters"
            response = requests.post(url, json=counter_data, headers=headers, timeout=30)
            
            if response.status_code not in [200, 201]:
                return False, f"Failed to create counter: {response.status_code} - {response.text}"
            
            counter_id = response.json().get("id")
            
            # Invoke function multiple times to increment counter
            for _ in range(5):
                self.performance_tester.invoke_function(function_url)
                await asyncio.sleep(0.5)
            
            # Wait for counter data
            await asyncio.sleep(3)
            
            # Check counter value
            check_url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/counters/{counter_id}"
            check_response = requests.get(check_url, headers=headers, timeout=30)
            
            if check_response.status_code == 200:
                counter_info = check_response.json()
                # Counter should have been hit
                return True, None
            
            return False, "Counter was not incremented"
            
        except Exception as e:
            return False, f"Counter test error: {str(e)}"
    
    async def test_metric(self, function_name: str, function_url: str, agent_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Test Lightrun metric functionality."""
        if not agent_id:
            return False, "Agent ID not found"
        
        if not self.api_key or not self.company_id:
            return False, "Lightrun API credentials not configured"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            metric_data = {
                "agentId": agent_id,
                "filename": "index.js",
                "lineNumber": 30,
                "name": f"test_metric_{function_name}",
                "expression": "requestCount",
                "expireSec": 300
            }
            
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/metrics"
            response = requests.post(url, json=metric_data, headers=headers, timeout=30)
            
            if response.status_code not in [200, 201]:
                return False, f"Failed to create metric: {response.status_code} - {response.text}"
            
            metric_id = response.json().get("id")
            
            # Invoke function to generate metric data
            for _ in range(5):
                self.performance_tester.invoke_function(function_url)
                await asyncio.sleep(0.5)
            
            # Wait for metric data
            await asyncio.sleep(3)
            
            # Check metric data
            check_url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/metrics/{metric_id}"
            check_response = requests.get(check_url, headers=headers, timeout=30)
            
            if check_response.status_code == 200:
                metric_info = check_response.json()
                # Metric should have data
                return True, None
            
            return False, "Metric was not collected"
            
        except Exception as e:
            return False, f"Metric test error: {str(e)}"
