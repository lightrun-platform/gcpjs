"""Result handling and reporting."""
import json
from datetime import datetime
from pathlib import Path
from typing import List
from .models import TestResult
from .config import RESULTS_DIR


class ResultHandler:
    """Handles test result saving and reporting."""
    
    def __init__(self, results_dir: Path = RESULTS_DIR):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def save_result(self, result: TestResult) -> Path:
        """Save test result to a file."""
        result_file = self.results_dir / f"{result.function_name}.json"
        
        result_dict = result.to_dictionary()
        result_dict["timestamp"] = datetime.now().isoformat()
        
        with open(result_file, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        return result_file
    
    def print_summary(self, results: List[TestResult]) -> None:
        """Print test summary."""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total = len(results)
        deployed = sum(1 for r in results if r.deployment_success)
        failed_deploy = total - deployed
        
        print(f"\nTotal functions tested: {total}")
        print(f"Successfully deployed: {deployed}")
        print(f"Failed to deploy: {failed_deploy}")
        
        if deployed > 0:
            print(f"\nPerformance (deployed functions only):")
            cold_avgs = [r.cold_start_avg_ms for r in results if r.cold_start_avg_ms]
            warm_avgs = [r.warm_start_avg_ms for r in results if r.warm_start_avg_ms]
            
            if cold_avgs:
                print(f"  Cold start average: {sum(cold_avgs)/len(cold_avgs):.2f}ms")
                print(f"  Warm start average: {sum(warm_avgs)/len(warm_avgs):.2f}ms")
            
            print(f"\nLightrun tests:")
            snapshot_passed = sum(1 for r in results if r.snapshot_test is True)
            counter_passed = sum(1 for r in results if r.counter_test is True)
            metric_passed = sum(1 for r in results if r.metric_test is True)
            
            print(f"  Snapshots: {snapshot_passed}/{deployed} passed")
            print(f"  Counters: {counter_passed}/{deployed} passed")
            print(f"  Metrics: {metric_passed}/{deployed} passed")
            
            print(f"\nLog errors:")
            logs_ok = sum(1 for r in results if r.logs_error_check is True)
            print(f"  Clean logs: {logs_ok}/{deployed}")
        
        print("\nDetailed results saved to:", self.results_dir)
        print("="*80)