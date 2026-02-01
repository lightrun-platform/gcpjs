"""Unit tests for SendRequestTask class."""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from ....shared_modules.gcf_task_primitives.send_request_task import SendRequestTask
from ....shared_modules.cli_parser import ParsedCLIArguments


class TestSendRequestTask(unittest.TestCase):
    """Test SendRequestTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ParsedCLIArguments(argparse.Namespace(
            delay_between_requests=0,
            test_size=5,
            base_function_name='testFunction',
            lightrun_api_key='key',
            lightrun_company_id='id'
        ))
        self.function = Mock()
        self.function.url = 'https://test-function-001-abc123.run.app'
        self.function.index = 1
        self.function.display_name = 'testFunction-001'
        self.function.name = 'testFunction-001'
        self.function.is_lightrun_variant = True
    
    def test_init(self):
        """Test SendRequestTask initialization."""
        task = SendRequestTask(
            function=self.function,
            delay_between_requests=0,
            num_requests=5,
            skip_lightrun_action_setup=False,
            lightrun_api_key='key'
        )
        
        self.assertEqual(task.url, self.function.url)
        self.assertEqual(task.function_index, self.function.index)
        self.assertEqual(task.delay_between_requests, 0)
        self.assertEqual(task.num_requests, 5)
    
    @patch('shared_modules.gcf_task_primitives.send_request_task.requests.get')
    @patch('shared_modules.gcf_task_primitives.send_request_task.time.time')
    def test_execute_successful_request(self, mock_time, mock_get):
        """Test successful HTTP request."""
        # Mock time for latency calculation
        # 5 requests * 2 calls to time() per request = 10 calls
        # We need to provide enough values
        mock_time.side_effect = [1000.0, 1000.5] * 10
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'isColdStart': True,
            'totalDuration': '1000000000',
            'message': 'Hello from function'
        }
        mock_get.return_value = mock_response
        
        task = SendRequestTask(
            function=self.function,
            delay_between_requests=0,
            num_requests=1,
            skip_lightrun_action_setup=True,
            lightrun_api_key='key'
        )
        result = task.execute()
        
        self.assertFalse(result.get('error', False))
        self.assertEqual(result['_function_index'], self.function.index)
        self.assertEqual(result['isColdStart'], True)
        self.assertEqual(result['totalDuration'], 1_000_000_000.0)
    
    @patch('shared_modules.gcf_task_primitives.send_request_task.requests.get')
    @patch('shared_modules.gcf_task_primitives.send_request_task.time.time')
    def test_execute_http_error(self, mock_time, mock_get):
        """Test HTTP error response."""
        mock_time.side_effect = [1000.0, 1000.1] * 2
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_get.return_value = mock_response
        
        task = SendRequestTask(
            function=self.function,
            delay_between_requests=0,
            num_requests=1,
            skip_lightrun_action_setup=True
        )
        result = task.execute()
        
        self.assertTrue(result['error']) # The aggregated result might behave differently?
        # send_request_task.execute combines results. 
        # If any request failed, does the wrapper return error?
        # execute returns **first_result + aggregates.
        # If first request failed, it returns error info.
        self.assertEqual(result['status_code'], 500)

if __name__ == '__main__':
    unittest.main()
