"""Unit tests for SendRequestTask class."""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from shared_modules.gcf_task_primitives.send_request_task import SendRequestTask
from shared_modules.gcf_models.gcp_function import GCPFunction


class TestSendRequestTask(unittest.TestCase):
    """Test SendRequestTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.function = Mock(spec=GCPFunction)
        self.function.url = 'https://test-function.run.app'
    
    def test_init(self):
        """Test SendRequestTask initialization."""
        task = SendRequestTask(function=self.function)
        self.assertEqual(task.url, self.function.url)
    
    @patch('shared_modules.gcf_task_primitives.send_request_task.requests.get')
    @patch('shared_modules.gcf_task_primitives.send_request_task.time.perf_counter')
    def test_execute_successful_request(self, mock_perf_counter, mock_get):
        """Test successful HTTP request."""
        # Mock time for latency: start, end
        mock_perf_counter.side_effect = [1000.0, 1000.5]
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'isColdStart': True,
            'message': 'Hello'
        }
        mock_get.return_value = mock_response
        
        task = SendRequestTask(function=self.function)
        result = task.execute(request_number=1)
        
        self.assertFalse(result.get('error', False))
        self.assertEqual(result['_request_number'], 1)
        self.assertEqual(result['_request_latency'], 500_000_000.0) # 0.5s in ns
        self.assertEqual(result['isColdStart'], True)
        self.assertEqual(result['_url'], self.function.url)
    
    @patch('shared_modules.gcf_task_primitives.send_request_task.requests.get')
    def test_execute_http_error(self, mock_get):
        """Test HTTP error response."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_get.return_value = mock_response
        
        task = SendRequestTask(function=self.function)
        result = task.execute(request_number=2)
        
        self.assertTrue(result['error'])
        self.assertEqual(result['_request_number'], 2)
        self.assertEqual(result['status_code'], 500)
        self.assertEqual(result['message'], 'Internal Server Error')
    
    @patch('shared_modules.gcf_task_primitives.send_request_task.requests.get')
    def test_execute_exception(self, mock_get):
        """Test exception during request."""
        mock_get.side_effect = Exception("Connection refused")
        
        task = SendRequestTask(function=self.function)
        result = task.execute()
        
        self.assertTrue(result['error'])
        self.assertEqual(result['exception'], 'Connection refused')

if __name__ == '__main__':
    unittest.main()
