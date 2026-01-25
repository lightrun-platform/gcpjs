"""Unit tests for BenchmarkManager class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import argparse
import sys
import threading

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir.parent)) # Add Benchmarks dir

from src.manager import BenchmarkManager
from shared_modules.wait_for_cold import ColdStartDetectionError
from shared_modules.gcf_models import GCPFunction

class TestBenchmarkManager(unittest.TestCase):
    """Test BenchmarkManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = argparse.Namespace(
            base_function_name='testFunction',
            num_functions=2,
            wait_minutes=1,
            lightrun_secret='test-secret',
            runtime='nodejs20',
            region='us-central1',
            project='test-project',
            entry_point='testFunction',
            num_workers=2,
            max_allocations_per_region=5
        )
        self.function_dir = Path('/tmp/test_function')
    
    def test_init(self):
        """Test BenchmarkManager initialization."""
        manager = BenchmarkManager(self.config, self.function_dir)
        
        self.assertEqual(manager.config, self.config)
        self.assertEqual(manager.function_dir, self.function_dir)
        self.assertIsNone(manager.executor)
        self.assertEqual(manager.deployed_functions, [])
        self.assertFalse(manager.cleanup_registered)
    
    def test_context_manager_entry(self):
        """Test context manager entry."""
        manager = BenchmarkManager(self.config, self.function_dir)
        
        with manager:
            self.assertIsNotNone(manager.executor)
            self.assertTrue(manager.cleanup_registered)
    
    def test_context_manager_exit(self):
        """Test context manager exit."""
        manager = BenchmarkManager(self.config, self.function_dir)
        
        with manager:
            executor = manager.executor
        
        # Executor should be cleaned up
        # Note: In real scenario, cleanup() would be called
    
    @patch('shared_modules.wait_for_cold.WaitForColdTask')
    @patch('src.manager.SendRequestTask')
    @patch('src.manager.time.sleep')
    @patch('src.manager.time.time')
    def test_wait_and_test_function_success(self, mock_time, mock_sleep,
                                                     mock_send_request, mock_wait):
        """Test successful wait and test workflow."""
        deployment_start = 1000.0
        mock_time.return_value = deployment_start

        # Mock successful wait
        mock_wait_instance = Mock()
        mock_wait_instance.execute.return_value = 120.0  # 2 minutes to cold
        mock_wait.return_value = mock_wait_instance
        
        # Mock successful test
        mock_send_instance = Mock()
        mock_send_instance.execute.return_value = {
            'isColdStart': True,
            'totalDuration': 1000000000.0
        }
        mock_send_request.return_value = mock_send_instance
        
        manager = BenchmarkManager(self.config, self.function_dir)
        manager.executor = Mock()  # Mock executor

        # Create function object for testing (already deployed)
        from shared_modules.gcf_models import GCPFunction
        function = GCPFunction(index=1, region='us-central1', base_name='test')
        function.is_deployed = True
        function.url = 'https://test.run.app'

        function_result, test_result, time_to_cold = manager.wait_and_test_function(
            function, deployment_start
        )
        
        self.assertTrue(function_result.is_deployed)
        self.assertIsNotNone(test_result)
        self.assertIsNotNone(time_to_cold)
        self.assertEqual(time_to_cold, 120.0)
    

    
    @patch('shared_modules.wait_for_cold.WaitForColdTask')
    @patch('src.manager.time.sleep')
    @patch('src.manager.time.time')
    def test_wait_and_test_function_cold_detection_failure(self, mock_time,
                                                                   mock_sleep, mock_wait):
        """Test when cold detection fails."""
        deployment_start = 1000.0
        mock_time.return_value = deployment_start

        # Mock cold detection failure
        mock_wait_instance = Mock()
        mock_wait_instance.execute.side_effect = ColdStartDetectionError('Timeout')
        mock_wait.return_value = mock_wait_instance
        
        manager = BenchmarkManager(self.config, self.function_dir)
        manager.executor = Mock()

        # Create function object for testing
        from shared_modules.gcf_models import GCPFunction
        function = GCPFunction(index=1, region='us-central1', base_name='test')
        function.is_deployed = True
        function.url = 'https://test.run.app'

        function_result, test_result, time_to_cold = manager.wait_and_test_function(
            function, deployment_start
        )
        
        self.assertTrue(function_result.is_deployed)
        self.assertIsNotNone(test_result)
        self.assertTrue(test_result['error'])
        self.assertIsNone(time_to_cold)
    

    @patch('shared_modules.delete.DeleteTask')
    def test_cleanup(self, mock_delete):
        """Test cleanup function."""
        manager = BenchmarkManager(self.config, self.function_dir)
        manager.deployed_functions = [
            Mock(name='testfunction-001', region='us-central1'),
            Mock(name='testfunction-002', region='us-central1')
        ]
        manager.deployed_functions[0].name = 'testfunction-001'
        manager.deployed_functions[0].region = 'us-central1'
        manager.deployed_functions[1].name = 'testfunction-002'
        manager.deployed_functions[1].region = 'us-central1'
        
        # Mock executor
        mock_executor = Mock()
        
        # Create mock futures that will be returned by submit
        mock_future1 = Mock()
        mock_future1.result.return_value = {'success': True, 'function_name': 'testfunction-001'}
        mock_future2 = Mock()
        mock_future2.result.return_value = {'success': True, 'function_name': 'testfunction-002'}
        
        # Track which futures are created for which functions
        future_map = {}
        call_count = [0]
        
        def mock_submit(func):
            call_count[0] += 1
            if call_count[0] == 1:
                future_map[mock_future1] = 'testFunction-001'
                return mock_future1
            else:
                future_map[mock_future2] = 'testFunction-002'
                return mock_future2
        
        mock_executor.submit = mock_submit
        manager.executor = mock_executor
        
        # Mock delete task
        mock_delete_instance = Mock()
        mock_delete_instance.execute.return_value = {'success': True}
        mock_delete.return_value = mock_delete_instance
        
        # Mock as_completed - it receives the futures dict and returns futures
        from concurrent.futures import as_completed
        def mock_as_completed(futures_dict):
            # Return futures that are keys in the dict
            return iter(futures_dict.keys())
        
        with patch('src.manager.as_completed', side_effect=mock_as_completed):
            manager.cleanup()
        
        # Check that executor was shut down
        mock_executor.shutdown.assert_called_once()
        
        # Verify cleanup stats
        self.assertEqual(manager.cleanup_stats, {'deleted': 2, 'failed': 0})
    
    def test_save_results(self):
        """Test saving results to file."""
        import json
        import tempfile
        import os
        
        manager = BenchmarkManager(self.config, self.function_dir)
        manager.config.results_file = 'test_results.json'
        
        deployments = [{'function_name': 'test-001'}]
        test_results = [{'totalDuration': '1000000000'}]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager.config.results_file = os.path.join(tmpdir, 'test_results.json')
            manager.save_results(deployments, test_results)
            
            # Verify file was created
            self.assertTrue(os.path.exists(manager.config.results_file))
            
            # Verify content
            with open(manager.config.results_file, 'r') as f:
                data = json.load(f)
                self.assertEqual(data['deployments'], deployments)
                self.assertEqual(data['test_results'], test_results)
    
    def test_get_results(self):
        """Test getting results dictionary."""
        manager = BenchmarkManager(self.config, self.function_dir)
        manager.deployments = [{'function_name': 'test-001'}]
        manager.test_results = [{'totalDuration': '1000000000'}]
        
        results = manager.get_results()
        
        self.assertIn('deployments', results)
        self.assertIn('test_results', results)
        self.assertIn('cleanup_stats', results)
        self.assertIn('config', results)
        self.assertIn('test_timestamp', results)


if __name__ == '__main__':
    unittest.main()
