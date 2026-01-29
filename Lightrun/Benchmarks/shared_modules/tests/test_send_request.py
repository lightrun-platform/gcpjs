"""Unit tests for SendRequestTask class."""

import unittest
from unittest.mock import Mock, patch, call, MagicMock
from datetime import datetime, timezone
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from shared_modules.send_request import SendRequestTask
from shared_modules.cli_parser import ParsedCLIArguments


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
    
    def test_init(self):
        """Test SendRequestTask initialization."""
        task = SendRequestTask(self.function, self.config)
        
        self.assertEqual(task.url, self.function.url)
        self.assertEqual(task.function_index, self.function.index)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_successful_request(self, mock_time, mock_get):
        """Test successful HTTP request."""
        # Mock time for latency calculation
        mock_time.side_effect = [1000.0, 1000.5]  # 0.5 second latency
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'isColdStart': True,
            'totalDuration': '1000000000',
            'message': 'Hello from function'
        }
        mock_get.return_value = mock_response
        
        task = SendRequestTask(self.function, self.config)
        result = task.execute()
        
        self.assertFalse(result.get('error', False))
        self.assertEqual(result['_function_index'], self.function.index)
        self.assertEqual(result['_url'], self.function.url)
        self.assertEqual(result['isColdStart'], True)
        self.assertEqual(result['totalDuration'], 1000000000.0)
        self.assertIn('_request_latency', result)
        self.assertIn('_timestamp', result)
        
        # Check latency is in nanoseconds (0.5 seconds = 500000000 nanoseconds)
        self.assertEqual(result['_request_latency'], 500_000_000)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_http_error(self, mock_time, mock_get):
        """Test HTTP error response."""
        mock_time.side_effect = [1000.0, 1000.1]
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_get.return_value = mock_response
        
        task = SendRequestTask(self.function, self.config)
        result = task.execute()
        
        self.assertTrue(result['error'])
        self.assertEqual(result['_function_index'], self.function.index)
        self.assertEqual(result['status_code'], 500)
        self.assertIn('message', result)
        self.assertIn('_timestamp', result)
        self.assertEqual(result['_url'], self.function.url)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_request_exception(self, mock_time, mock_get):
        """Test request exception handling."""
        mock_time.side_effect = [1000.0, 1000.1]
        
        # Mock exception
        mock_get.side_effect = Exception('Connection timeout')
        
        task = SendRequestTask(self.function, self.config)
        result = task.execute()
        
        self.assertTrue(result['error'])
        self.assertEqual(result['_function_index'], self.function.index)
        self.assertIn('exception', result)
        self.assertEqual(result['exception'], 'Connection timeout')
        self.assertIn('_timestamp', result)
        self.assertEqual(result['_url'], self.function.url)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_latency_calculation(self, mock_time, mock_get):
        """Test request latency calculation."""
        # Test with different latencies
        test_cases = [
            (1000.0, 1000.001, 1_000_000),  # 1ms
            (1000.0, 1001.0, 1_000_000_000),  # 1 second
            (1000.0, 1000.000001, 1000),  # 1 microsecond
        ]
        
        for start, end, expected_ns in test_cases:
            mock_time.side_effect = [start, end]
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'test': 'data'}
            mock_get.return_value = mock_response
            
            task = SendRequestTask(self.function, self.config)
            result = task.execute()
            
            # Allow small floating point differences
            self.assertAlmostEqual(result['_request_latency'], expected_ns, delta=1000)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_response_data_preserved(self, mock_time, mock_get):
        """Test that all response data is preserved."""
        # Set explicitly to 1 request
        self.config.test_size = 1
        
        mock_time.side_effect = [1000.0, 1000.1]
        
        response_data = {
            'isColdStart': True,
            'totalDuration': 1000000000.0,
            'totalImportsDuration': 500000000.0,
            'gcfImportDuration': 1000000.0,
            'envCheckDuration': 10000.0,
            'totalSetupDuration': 501000000.0,
            'functionInvocationOverhead': 499000000.0,
            'lightrunImportDuration': 499000000.0,
            'lightrunInitDuration': 50000.0,
            'message': 'Test message'
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_get.return_value = mock_response
        
        task = SendRequestTask(self.function, self.config)
        result = task.execute()
        
        # Check all original fields are preserved
        for key, value in response_data.items():
            self.assertEqual(result[key], value)
        
        # Check added fields
        self.assertEqual(result['_function_index'], self.function.index)
        self.assertIn('_request_latency', result)
        self.assertIn('_timestamp', result)
        self.assertEqual(result['_url'], self.function.url)
    
    @patch('shared_modules.send_request.requests.get')
    @patch('shared_modules.send_request.time.time')
    def test_execute_timeout_handling(self, mock_time, mock_get):
        """Test timeout exception handling."""
        import requests
        
        mock_time.side_effect = [1000.0, 1000.1]
        mock_get.side_effect = requests.Timeout('Request timed out')
        
        task = SendRequestTask(self.function, self.config)
        result = task.execute()
        
        self.assertTrue(result['error'])
        self.assertIn('exception', result)
        self.assertIn('timed out', result['exception'].lower())


if __name__ == '__main__':
    unittest.main()
