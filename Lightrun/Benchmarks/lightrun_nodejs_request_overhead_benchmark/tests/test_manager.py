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
from shared_modules.gcf_models.gcp_function import GCPFunction

class TestRequestOverheadBenchmarkManager(unittest.TestCase):
    """Test RequestOverheadBenchmarkManager class."""

    def setUp(self):
        self.config = argparse.Namespace(
            base_function_name='testFunction',
            num_functions=1,
            lightrun_secret='test-secret',
            runtime='nodejs20',
            region='us-central1',
            project='test-project',
            entry_point='testFunction',
            num_workers=1,
            max_allocations_per_region=5,
            number_of_lightrun_actions=1,
            lightrun_action_type='snapshot',
            lightrun_api_key='key',
            lightrun_company_id='cid',
            num_requests_per_function=5
        )
        self.function_dir = Path('/tmp/test_function')

    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.time.sleep')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.requests.get')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.LightrunAPI')
    def test_prepare_function_lightrun(self, MockLightrunAPI, mock_get, mock_sleep):
        """Test prepare_function logic with Lightrun enabled."""
        manager = RequestOverheadBenchmarkManager(self.config, self.function_dir)
        
        function = GCPFunction(index=1, region='us-central1', base_name='test-lightrun')
        function.is_deployed = True
        function.url = 'https://test.run.app'
        function.name = 'test-lightrun-1'
        function.display_name = 'test-lightrun-1'
        
        # Mock requests.get (warmup)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock Lightrun API
        mock_api_instance = Mock()
        MockLightrunAPI.return_value = mock_api_instance
        mock_api_instance.get_agent_id.return_value = 'agent-123'
        
        # Mock reading file for line number (open)
        with patch('builtins.open', unittest.mock.mock_open(read_data='line1\nhandlerRunTime:\nline3')):
            setup_time = manager.prepare_function(function, 1000.0)
            
        # Verify warmup request
        mock_get.assert_called_with('https://test.run.app', timeout=30)
        
        # Verify API called
        mock_api_instance.get_agent_id.assert_called_with('test-lightrun-1')
        mock_api_instance.add_snapshot.assert_called_with(
            agent_id='agent-123',
            filename='helloLightrun.js',
            line_number=2, # Line 2 because handlerRunTime is on line 2 (0-indexed 1 + 1)
            max_hit_count=15 # 5 requests + 10
        )
        
        # Verify sleep called (grace period)
        mock_sleep.assert_called_with(15)
        
        self.assertIsNotNone(setup_time)

    def test_prepare_function_no_lightrun(self):
        """Test prepare_function logic without Lightrun."""
        manager = RequestOverheadBenchmarkManager(self.config, self.function_dir)
        
        function = GCPFunction(index=1, region='us-central1', base_name='test-nolightrun')
        function.url = 'https://test.run.app'
        function.name = 'test-nolightrun-1' # No 'lightrun' in name (case insensitive check in manager)
        # Actually the manager checks 'lightrun' in name. 'test-nolightrun' has 'lightrun'.
        # Let's use a name without 'lightrun' string to be sure, or just test logic.
        function.name = 'hello-no-lr-1'
        
        with patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.requests.get') as mock_get, \
             patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.time.sleep') as mock_sleep, \
             patch('lightrun_nodejs_request_overhead_benchmark.src.request_overhead_benchmark_manager.LightrunAPI') as MockAPI:
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            manager.prepare_function(function, 1000.0)
            
            # Verify no API calls
            MockAPI.assert_not_called()
            
            # Verify grace period still happens (to be fair comparison? Manager logic does it always)
            mock_sleep.assert_called_with(15)

if __name__ == '__main__':
    unittest.main()
