"""Unit tests for RequestOverheadReportGenerator."""

import unittest
import sys
from pathlib import Path

# Add parent directory
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))

from lightrun_nodejs_request_overhead_benchmark.src.request_overhead_report import RequestOverheadReportGenerator

class TestRequestOverheadReportGenerator(unittest.TestCase):
    """Test Report Generator."""

    def test_extract_metrics(self):
        """Test metric extraction."""
        # Mock results structure
        with_results = {
            'test_results': [
                {
                    '_all_request_results': [
                        {'_request_latency': 100, 'handlerRunTime': '50', 'error': False},
                        {'_request_latency': 200, 'handlerRunTime': '60', 'error': False}
                    ]
                }
            ]
        }
        without_results = {
            'test_results': [
                {
                    '_all_request_results': [
                        {'_request_latency': 50, 'handlerRunTime': '25', 'error': False}
                    ]
                }
            ]
        }
        
        generator = RequestOverheadReportGenerator(with_results, without_results)
        
        # Test extraction
        w_metrics = generator._extract_metrics(with_results)
        self.assertEqual(w_metrics['requestLatency'], [100, 200])
        self.assertEqual(w_metrics['handlerRunTime'], [50.0, 60.0])
        
        wo_metrics = generator._extract_metrics(without_results)
        self.assertEqual(wo_metrics['requestLatency'], [50])
        self.assertEqual(wo_metrics['handlerRunTime'], [25.0])

if __name__ == '__main__':
    unittest.main()
