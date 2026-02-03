"""Unit tests for RequestOverheadBenchmarkManager."""

import unittest
from unittest.mock import Mock, patch, call
from pathlib import Path
import argparse
import sys

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir.parent)) # Benchmarks dir for shared_modules

from lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager import RequestOverheadBenchmarkManager
from shared_modules.cli_parser import ParsedCLIArguments
from shared_modules.gcf_models.gcp_function import GCPFunction

class TestRequestOverheadBenchmarkManager(unittest.TestCase):
    """Test RequestOverheadBenchmarkManager class."""

    def setUp(self):
        self.config = ParsedCLIArguments(argparse.Namespace(
            base_function_name='testFunction',
            num_functions=1,
            lightrun_secret='test-secret',
            runtime='nodejs20',
            region='us-central1',
            project='test-project',
            entry_point='testFunction',
            num_workers=1,
            max_allocations_per_region=5,
            test_size=5,
            lightrun_action_type='snapshot',
            lightrun_api_key='key',
            lightrun_company_id='cid'
        ))
        self.function_dir = Path('/tmp/test_function')

    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.time')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.requests.get')
    def test_prepare_function_lightrun(self, mock_get, mock_time):
        """Test prepare_function logic (warmup only)."""
        manager = RequestOverheadBenchmarkManager(self.config, self.function_dir)
        
        # Create function correctly
        function = GCPFunction(index=1, region='us-central1', base_name='test-lightrun', logger=Mock())
        function.is_deployed = True
        function.url = 'https://test.run.app'
        
        # Mock requests.get (warmup)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock time to verify loop logic
        # Sequence: start_time=0, warmup_end_calc=0, loop_check1=0(<40), loop_check2=20(<40), loop_check3=41(>40), return_calc=42
        mock_time.time.side_effect = [0, 0, 0, 20, 41, 42]
        mock_time.sleep.return_value = None
        
        setup_time = manager.prepare_function(function, 1000.0)
            
        # Verify warmup requests: 2 from loop + 10 burst = 12 total
        self.assertEqual(mock_get.call_count, 12)
        mock_get.assert_called_with('https://test.run.app', timeout=5)
        
        self.assertIsNotNone(setup_time)

    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.time')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.requests.get')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.LightrunAPI')
    def test_prepare_function_no_lightrun(self, MockAPI, mock_get, mock_time):
        """Test prepare_function logic without Lightrun (warmup only)."""
        manager = RequestOverheadBenchmarkManager(self.config, self.function_dir)
        
        function = GCPFunction(index=1, region='us-central1', base_name='test-nolightrun', logger=Mock())
        function.url = 'https://test.run.app'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock time same as above
        mock_time.time.side_effect = [0, 0, 0, 20, 41, 42]
        mock_time.sleep.return_value = None
        
        manager.prepare_function(function, 1000.0)
        
        # Verify no API calls
        MockAPI.assert_not_called()
        # Verify requests count (warmup logic is same)
        self.assertEqual(mock_get.call_count, 12)

    def test_get_test_task(self):
        """Test task factory."""
        manager = RequestOverheadBenchmarkManager(self.config, self.function_dir)
        function = GCPFunction(index=1, region='us-central1', base_name='test', logger=Mock())
        
        task = manager.get_test_task(function, 1000.0)
        from lightrun_nodejs_request_overhead_benchmark.src.iterative_test_task import IterativeOverheadTestTask
        self.assertIsInstance(task, IterativeOverheadTestTask)

if __name__ == '__main__':
    unittest.main()
