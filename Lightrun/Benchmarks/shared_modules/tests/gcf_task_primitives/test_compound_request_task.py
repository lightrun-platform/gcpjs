"""Unit tests for CompoundRequestTask class."""

import unittest
from unittest.mock import Mock, patch, call, MagicMock
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.compound_request_task import CompoundRequestTask
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction


class TestCompoundRequestTask(unittest.TestCase):
    """Test CompoundRequestTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.function = Mock(spec=GCPFunction)
        self.function.url = 'https://test-function.run.app'
        self.function.index = 1
        self.function.display_name = 'testFunction-001'
        self.function.is_lightrun_variant = True
        
        self.mock_logger_factory = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_logger_factory.get_logger.return_value = self.mock_logger
    
    def test_init(self):
        """Test initialization."""
        task = CompoundRequestTask(
            function=self.function,
            delay_between_requests=1,
            num_requests=5,
            skip_lightrun_action_setup=False,
            lightrun_api_key='key',
            logger_factory=self.mock_logger_factory
        )
        
        self.assertEqual(task.function, self.function)
        self.assertEqual(task.delay_between_requests, 1)
        self.assertEqual(task.num_requests, 5)
        self.assertEqual(task.lightrun_api_key, 'key')
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.compound_request_task.SendRequestTask')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.compound_request_task.time.sleep')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.compound_request_task.LightrunAPI') # Mock the API class
    def test_execute_flow(self, mock_lightrun_api_cls, mock_sleep, mock_send_task_cls):
        """Test execution flow including looping and lightrun setup."""
        
        # Mock SendRequestTask instance and its execute method
        mock_send_task_instance = mock_send_task_cls.return_value
        
        # Mock results for 2 requests
        mock_send_task_instance.execute.side_effect = [
            {'error': False, 'totalDuration': '1000000000', 'isColdStart': True}, # 1s
            {'error': False, 'totalDuration': '500000000', 'isColdStart': False}  # 0.5s
        ]
        
        # Mock Lightrun API
        mock_lightrun_api = mock_lightrun_api_cls.return_value
        mock_lightrun_api.get_agent_id.return_value = 'agent-123'
        
        task = CompoundRequestTask(
            function=self.function,
            delay_between_requests=0.1,
            num_requests=2,
            skip_lightrun_action_setup=False,
            lightrun_api_key='key',
            logger_factory=self.mock_logger_factory
        )
        
        result = task.execute()
        
        # Verify SendRequestTask was created
        mock_send_task_cls.assert_called_with(self.function)
        
        # Verify execute called twice
        self.assertEqual(mock_send_task_instance.execute.call_count, 2)
        mock_send_task_instance.execute.assert_has_calls([call(request_number=1), call(request_number=2)])
        
        # Verify sleep called once (between requests)
        mock_sleep.assert_called_once_with(0.1)
        
        # Verify Lightrun snapshot added (request 1 is cold/start)
        mock_lightrun_api.get_agent_id.assert_called_with(self.function.display_name)
        mock_lightrun_api.add_snapshot.assert_called_once()
        
        # Verify aggregation results
        self.assertEqual(result['_num_requests'], 2)
        self.assertEqual(result['totalDuration'], 1_500_000_000.0)
        self.assertEqual(result['totalDurationForColdStarts'], 1_000_000_000.0)
        self.assertEqual(result['totalDurationForWarmRequests'], 500_000_000.0)

if __name__ == '__main__':
    unittest.main()
