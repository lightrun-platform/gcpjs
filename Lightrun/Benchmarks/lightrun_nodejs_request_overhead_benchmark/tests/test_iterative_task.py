"""Unit tests for IterativeOverheadTestTask."""

import unittest
from unittest.mock import Mock, patch, call
from pathlib import Path
import argparse
import sys

# Add parent directory
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))

from lightrun_nodejs_request_overhead_benchmark.src.iterative_test_task import IterativeOverheadTestTask
from shared_modules.gcf_models.gcp_function import GCPFunction

class TestIterativeOverheadTestTask(unittest.TestCase):
    """Test Iterative Task."""
    
    def setUp(self):
        self.config = argparse.Namespace(
            test_size=2,
            lightrun_action_type='snapshot',
            lightrun_api_key='key',
            lightrun_company_id='cid',
            delay_between_requests=0
        )
        self.function_dir = Path('/tmp')
        self.function = GCPFunction(index=1, region='us-central1', base_name='test-lightrun')
        self.function.url = 'http://test'

    @patch('lightrun_nodejs_request_overhead_benchmark.src.iterative_test_task.LightrunAPI')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.iterative_test_task.SendRequestTask')
    @patch('lightrun_nodejs_request_overhead_benchmark.src.iterative_test_task.time.sleep')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='function function1()')
    def test_execute_iterative(self, mock_file, mock_sleep, MockSendTask, MockAPI):
        """Test execution loop."""
        # Mock API setup execution BEFORE instantiation
        mock_api = Mock()
        MockAPI.return_value = mock_api
        mock_api.get_agent_id.return_value = 'agent-1'
        mock_api.add_snapshot.side_effect = ['snap-1', 'snap-2']
        mock_api.get_snapshot.return_value = {'currentHitCount': 10}
        
        # Mock Send Task
        mock_send_task = Mock()
        MockSendTask.return_value = mock_send_task
        # Return fresh dict each time because it gets modified
        mock_send_task.execute.side_effect = lambda: {'totalDurationForColdStarts': 0.1, '_all_request_results': []}
        
        task = IterativeOverheadTestTask(self.function, self.config, self.function_dir)
        result = task.execute()
        
        # Verify iterations (0, 1, 2)
        self.assertEqual(len(result['iterations']), 3) 
        self.assertEqual(result['iterations'][0]['iteration'], 0)
        
        # Verify actions added
        # We expect 2 calls because i=1 and i=2 triggers _add_action
        self.assertEqual(mock_api.add_snapshot.call_count, 2)
        
        # Verify verification (iteration 1 verifies [snap1], iteration 2 verifies [snap1, snap2])
        # Total calls to get_snapshot: 1 (iter 1) + 2 (iter 2) = 3 calls
        self.assertEqual(mock_api.get_snapshot.call_count, 3)

if __name__ == '__main__':
    unittest.main()
