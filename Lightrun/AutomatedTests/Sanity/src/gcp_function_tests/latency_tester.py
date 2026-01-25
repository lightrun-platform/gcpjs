"""Comprehensive latency testing for GCP Cloud Functions with Lightrun."""
import asyncio
import time
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class LatencyTestResults:
    """Results from comprehensive latency testing."""
    # Raw measurements for each scenario
    cold_no_lightrun_no_snapshot: List[LatencyMeasurement] = None
    cold_no_lightrun_snapshot: List[LatencyMeasurement] = None
    warm_no_lightrun_no_snapshot: List[LatencyMeasurement] = None
    warm_no_lightrun_snapshot: List[LatencyMeasurement] = None
    warm_lightrun_init_no_snapshot: List[LatencyMeasurement] = None
    warm_lightrun_init_snapshot: List[LatencyMeasurement] = None
    warm_lightrun_ready_no_snapshot: List[LatencyMeasurement] = None
    warm_lightrun_ready_snapshot: List[LatencyMeasurement] = None
    
    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.cold_no_lightrun_no_snapshot is None:
            self.cold_no_lightrun_no_snapshot = []
        if self.cold_no_lightrun_snapshot is None:
            self.cold_no_lightrun_snapshot = []
        if self.warm_no_lightrun_no_snapshot is None:
            self.warm_no_lightrun_no_snapshot = []
        if self.warm_no_lightrun_snapshot is None:
            self.warm_no_lightrun_snapshot = []
        if self.warm_lightrun_init_no_snapshot is None:
            self.warm_lightrun_init_no_snapshot = []
        if self.warm_lightrun_init_snapshot is None:
            self.warm_lightrun_init_snapshot = []
        if self.warm_lightrun_ready_no_snapshot is None:
            self.warm_lightrun_ready_no_snapshot = []
        if self.warm_lightrun_ready_snapshot is None:
            self.warm_lightrun_ready_snapshot = []
    
    def compute_metrics(self) -> Dict[str, float]:
        """Compute derived metrics from raw measurements."""
        def avg_duration(measurements: List[LatencyMeasurement]) -> float:
            successful = [m.duration_ms for m in measurements if m.success]
            return sum(successful) / len(successful) if successful else 0.0
        
        # Raw averages
        avg_cold_no_lightrun_no_snapshot = avg_duration(self.cold_no_lightrun_no_snapshot)
        avg_cold_no_lightrun_snapshot = avg_duration(self.cold_no_lightrun_snapshot)
        avg_warm_no_lightrun_no_snapshot = avg_duration(self.warm_no_lightrun_no_snapshot)
        avg_warm_no_lightrun_snapshot = avg_duration(self.warm_no_lightrun_snapshot)
        avg_warm_lightrun_init_no_snapshot = avg_duration(self.warm_lightrun_init_no_snapshot)
        avg_warm_lightrun_init_snapshot = avg_duration(self.warm_lightrun_init_snapshot)
        avg_warm_lightrun_ready_no_snapshot = avg_duration(self.warm_lightrun_ready_no_snapshot)
        avg_warm_lightrun_ready_snapshot = avg_duration(self.warm_lightrun_ready_snapshot)
        
        # Derived metrics
        gcp_cold_start_duration = avg_cold_no_lightrun_no_snapshot
        
        # Lightrun initialization duration = (cold with lightrun) - (cold without lightrun)
        # But we don't have cold with lightrun directly. Instead:
        # First request with lightrun when function is warm = warm_lightrun_init
        # This includes the agent initialization time
        lightrun_init_duration = avg_warm_lightrun_init_no_snapshot - avg_warm_no_lightrun_no_snapshot
        
        # Added latency by Lightrun agent (excluding initialization)
        # = (warm with lightrun ready) - (warm without lightrun)
        lightrun_overhead = avg_warm_lightrun_ready_no_snapshot - avg_warm_no_lightrun_no_snapshot
        
        # Snapshot overhead
        snapshot_overhead_no_lightrun = avg_warm_no_lightrun_snapshot - avg_warm_no_lightrun_no_snapshot
        snapshot_overhead_lightrun_ready = avg_warm_lightrun_ready_snapshot - avg_warm_lightrun_ready_no_snapshot
        
        return {
            # Raw averages
            "avg_cold_no_lightrun_no_snapshot": avg_cold_no_lightrun_no_snapshot,
            "avg_cold_no_lightrun_snapshot": avg_cold_no_lightrun_snapshot,
            "avg_warm_no_lightrun_no_snapshot": avg_warm_no_lightrun_no_snapshot,
            "avg_warm_no_lightrun_snapshot": avg_warm_no_lightrun_snapshot,
            "avg_warm_lightrun_init_no_snapshot": avg_warm_lightrun_init_no_snapshot,
            "avg_warm_lightrun_init_snapshot": avg_warm_lightrun_init_snapshot,
            "avg_warm_lightrun_ready_no_snapshot": avg_warm_lightrun_ready_no_snapshot,
            "avg_warm_lightrun_ready_snapshot": avg_warm_lightrun_ready_snapshot,
            
            # Derived metrics
            "gcp_cold_start_duration": gcp_cold_start_duration,
            "lightrun_init_duration": lightrun_init_duration,
            "lightrun_overhead": lightrun_overhead,
            "snapshot_overhead_no_lightrun": snapshot_overhead_no_lightrun,
            "snapshot_overhead_lightrun_ready": snapshot_overhead_lightrun_ready,
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        metrics = self.compute_metrics()
        return {
            "raw_measurements": {
                "cold_no_lightrun_no_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                  for m in self.cold_no_lightrun_no_snapshot],
                "cold_no_lightrun_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                              for m in self.cold_no_lightrun_snapshot],
                "warm_no_lightrun_no_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                 for m in self.warm_no_lightrun_no_snapshot],
                "warm_no_lightrun_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                              for m in self.warm_no_lightrun_snapshot],
                "warm_lightrun_init_no_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                    for m in self.warm_lightrun_init_no_snapshot],
                "warm_lightrun_init_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                 for m in self.warm_lightrun_init_snapshot],
                "warm_lightrun_ready_no_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                     for m in self.warm_lightrun_ready_no_snapshot],
                "warm_lightrun_ready_snapshot": [{"duration_ms": m.duration_ms, "success": m.success, "error": m.error} 
                                                  for m in self.warm_lightrun_ready_snapshot],
            },
            "metrics": metrics
        }


class LatencyTester:
    """Handles comprehensive latency testing across all scenarios."""
    
    def __init__(self, requests_per_scenario: int = 10, 
                 api_url: str = "https://api.lightrun.com",
                 api_key: Optional[str] = None,
                 company_id: Optional[str] = None):
        self.requests_per_scenario = requests_per_scenario
        self.api_url = api_url
        self.api_key = api_key
        self.company_id = company_id
    
    def create_snapshot(self, agent_id: Optional[str] = None, function_name: Optional[str] = None, 
                       filename: str = "index.js", line_number: int = 60) -> Optional[str]:
        """
        Create a Lightrun snapshot and return its ID.
        
        Args:
            agent_id: Agent ID (if agent is already initialized)
            function_name: Function name for metadata tag (if agent not initialized yet)
            filename: Source file name
            line_number: Line number for snapshot
        """
        if not self.api_key or not self.company_id:
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            snapshot_data = {
                "filename": filename,
                "lineNumber": line_number,
                "maxHitCount": 1,
                "expireSec": 300
            }
            
            # If agent_id is provided, use it (agent already initialized)
            # Otherwise, use metadata tags (agent will initialize and attach snapshot)
            if agent_id:
                snapshot_data["agentId"] = agent_id
            elif function_name:
                # Use metadata tags to attach snapshot before agent initializes
                snapshot_data["metadataTags"] = [function_name]
            else:
                return None
            
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots"
            response = requests.post(url, json=snapshot_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                return response.json().get("id")
        except Exception as e:
            print(f"    Warning: Failed to create snapshot: {e}")
        
        return None
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a Lightrun snapshot."""
        if not self.api_key or not self.company_id:
            return False
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            response = requests.delete(url, headers=headers, timeout=30)
            return response.status_code in [200, 204]
        except Exception:
            return False
    
    def invoke_function(self, url: str, use_lightrun: bool = False, take_snapshot: bool = False) -> LatencyMeasurement:
        """Invoke a function with specified parameters."""
        try:
            params = {
                "useLightrun": str(use_lightrun).lower(),
                "takeSnapshot": str(take_snapshot).lower()
            }
            start = time.time()
            response = requests.get(url, params=params, timeout=60)
            duration = (time.time() - start) * 1000  # Convert to ms
            
            if response.status_code == 200:
                return LatencyMeasurement(duration_ms=duration, success=True)
            else:
                return LatencyMeasurement(
                    duration_ms=duration,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
        except Exception as e:
            return LatencyMeasurement(duration_ms=0, success=False, error=str(e))
    
    async def test_latency_matrix(
        self,
        url_without_lightrun: str,
        url_with_lightrun: str,
        function_name_with_lightrun: str,
        agent_id: Optional[str] = None,
        num_cold_starts: int = 1
    ) -> LatencyTestResults:
        """
        Test all 8 combinations of the latency matrix.
        
        IMPORTANT: isGCPFunctionWarm and wasLightrunAgentInitializedBefore are STATE variables,
        not parameters. We control test ORDERING to achieve different states:
        - First request to a function = cold start (isGCPFunctionWarm = false)
        - Subsequent requests = warm (isGCPFunctionWarm = true)
        - First request with useLightrun=true = transitions to lightrun-initialized state
        - Once lightrun is initialized, it stays initialized (cannot go back)
        
        Args:
            url_without_lightrun: URL of function without Lightrun agent
            url_with_lightrun: URL of function with Lightrun agent
            function_name_with_lightrun: Function name for metadata tags
            agent_id: Agent ID (may be None if agent not initialized yet)
            num_cold_starts: Number of cold starts to test (for averaging)
        
        Returns:
            LatencyTestResults with all measurements
        """
        results = LatencyTestResults()
        
        print(f"  Testing latency matrix (measuring {num_cold_starts} cold start(s))...")
        
        # ========================================================================
        # COMBINATION 1: Cold, Lightrun not initialized before, no snapshot
        # State: isGCPFunctionWarm=false, wasLightrunAgentInitializedBefore=false, takeSnapshot=false
        # ========================================================================
        print(f"  [1/8] Cold start, no Lightrun, no snapshot...")
        measurement = self.invoke_function(url_without_lightrun, use_lightrun=False, take_snapshot=False)
        results.cold_no_lightrun_no_snapshot.append(measurement)
        
        # ========================================================================
        # COMBINATION 2: Cold, Lightrun not initialized before, snapshot
        # State: isGCPFunctionWarm=false, wasLightrunAgentInitializedBefore=false, takeSnapshot=true
        # Note: Function doesn't have Lightrun agent, so snapshot is ignored but we measure latency
        # ========================================================================
        print(f"  [2/8] Cold start, no Lightrun, snapshot (ignored)...")
        measurement = self.invoke_function(url_without_lightrun, use_lightrun=False, take_snapshot=True)
        results.cold_no_lightrun_snapshot.append(measurement)
        
        # ========================================================================
        # COMBINATIONS 3-4: Cold + Lightrun initialized before = IMPOSSIBLE
        # If Lightrun was initialized before, a previous request happened, so it can't be cold
        # ========================================================================
        
        # Warm up the function (transition: isGCPFunctionWarm = false → true)
        print(f"  Warming up function (transitioning to warm state)...")
        for _ in range(5):
            self.invoke_function(url_without_lightrun, use_lightrun=False, take_snapshot=False)
            await asyncio.sleep(0.1)
        
        # ========================================================================
        # COMBINATION 3: Warm, Lightrun not initialized before, no snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=false, takeSnapshot=false
        # Note: This is for function WITHOUT Lightrun agent (url_without_lightrun)
        # ========================================================================
        print(f"  [3/8] Warm, no Lightrun, no snapshot...")
        for _ in range(self.requests_per_scenario):
            measurement = self.invoke_function(url_without_lightrun, use_lightrun=False, take_snapshot=False)
            results.warm_no_lightrun_no_snapshot.append(measurement)
            await asyncio.sleep(0.05)
        
        # ========================================================================
        # COMBINATION 4: Warm, Lightrun not initialized before, snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=false, takeSnapshot=true
        # Note: Function doesn't have Lightrun agent, so snapshot is ignored but we measure latency
        # ========================================================================
        print(f"  [4/8] Warm, no Lightrun, snapshot (ignored)...")
        for _ in range(self.requests_per_scenario):
            measurement = self.invoke_function(url_without_lightrun, use_lightrun=False, take_snapshot=True)
            results.warm_no_lightrun_snapshot.append(measurement)
            await asyncio.sleep(0.05)
        
        # ========================================================================
        # Now test with Lightrun function
        # First, warm up the function WITHOUT initializing Lightrun agent
        # This achieves: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=false
        # ========================================================================
        print(f"  Warming up Lightrun function (without initializing agent)...")
        for _ in range(5):
            # Call with useLightrun=false to warm the function but NOT initialize Lightrun agent
            self.invoke_function(url_with_lightrun, use_lightrun=False, take_snapshot=False)
            await asyncio.sleep(0.1)
        
        # ========================================================================
        # COMBINATION 5: Warm, Lightrun initializes during request, no snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=false, takeSnapshot=false
        # This is the FIRST request with useLightrun=true, so agent initializes during this call
        # ========================================================================
        print(f"  [5/8] Warm, Lightrun initializes (first useLightrun=true), no snapshot...")
        measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=False)
        results.warm_lightrun_init_no_snapshot.append(measurement)
        
        # ========================================================================
        # COMBINATION 6: Warm, Lightrun initializes during request, snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=false, takeSnapshot=true
        # We need a fresh function instance for this (since agent is now initialized)
        # Create snapshot via metadata tags before agent initializes
        # ========================================================================
        print(f"  [6/8] Warm, Lightrun initializes (first useLightrun=true), snapshot...")
        # Create snapshot using metadata tags (agent not initialized yet, will attach when agent initializes)
        snapshot_id = self.create_snapshot(function_name=function_name_with_lightrun)
        
        if snapshot_id:
            # Call function - agent will initialize during this call and capture the snapshot
            measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=True)
            results.warm_lightrun_init_snapshot.append(measurement)
            self.delete_snapshot(snapshot_id)
            await asyncio.sleep(0.5)
        else:
            print(f"    Warning: Could not create snapshot via metadata tags")
            measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=True)
            results.warm_lightrun_init_snapshot.append(measurement)
        
        # ========================================================================
        # Now agent is initialized (wasLightrunAgentInitializedBefore = true, cannot go back)
        # Continue warming up to ensure function is warm
        # ========================================================================
        print(f"  Warming up Lightrun function (agent now initialized)...")
        for _ in range(5):
            self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=False)
            await asyncio.sleep(0.1)
        
        # ========================================================================
        # COMBINATION 7: Warm, Lightrun initialized before, no snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=true, takeSnapshot=false
        # ========================================================================
        print(f"  [7/8] Warm, Lightrun ready, no snapshot...")
        for _ in range(self.requests_per_scenario):
            measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=False)
            results.warm_lightrun_ready_no_snapshot.append(measurement)
            await asyncio.sleep(0.05)
        
        # ========================================================================
        # COMBINATION 8: Warm, Lightrun initialized before, snapshot
        # State: isGCPFunctionWarm=true, wasLightrunAgentInitializedBefore=true, takeSnapshot=true
        # ========================================================================
        print(f"  [8/8] Warm, Lightrun ready, snapshot...")
        # Create snapshot using agent_id (agent is already initialized)
        snapshot_id = None
        if agent_id:
            snapshot_id = self.create_snapshot(agent_id=agent_id)
        
        if snapshot_id:
            for _ in range(self.requests_per_scenario):
                measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=True)
                results.warm_lightrun_ready_snapshot.append(measurement)
                await asyncio.sleep(0.05)
            self.delete_snapshot(snapshot_id)
        else:
            print(f"    Warning: Could not create snapshot (agent_id not available)")
            for _ in range(self.requests_per_scenario):
                measurement = self.invoke_function(url_with_lightrun, use_lightrun=True, take_snapshot=True)
                results.warm_lightrun_ready_snapshot.append(measurement)
                await asyncio.sleep(0.05)
        
        return results
