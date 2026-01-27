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
        # Mock results structure (Iterative)
        with_results = {
            'test_results': [
                {
                    'is_iterative': True,
                    'iterations': [
                        {
                            'iteration': 1,
                            '_all_request_results': [
                                {'_request_latency': 100, 'handlerRunTime': '50', 'error': False},
                                {'_request_latency': 200, 'handlerRunTime': '60', 'error': False}
                            ]
                        }
                    ]
                }
            ]
        }
        # Without results (Baseline / non-iterative fallback simulation)
        without_results = { 'test_results': [] }
        
        generator = RequestOverheadReportGenerator(with_results, without_results)
        
        # Test extraction
        w_metrics = generator._extract_iterative_metrics(with_results)
        # Should have key 1 (iteration 1)
        self.assertIn(1, w_metrics)
        self.assertEqual(w_metrics[1], [50.0, 60.0])

if __name__ == '__main__':
    unittest.main()
