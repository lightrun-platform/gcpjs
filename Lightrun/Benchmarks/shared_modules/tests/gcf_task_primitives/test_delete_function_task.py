"""Unit tests for DeleteTask class."""

import unittest
from unittest.mock import Mock, patch
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from shared_modules.delete import DeleteTask
from shared_modules.cli_parser import ParsedCLIArguments


class TestDeleteTask(unittest.TestCase):
    """Test DeleteTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ParsedCLIArguments(argparse.Namespace(
            region='us-central1',
            project='test-project'
        ))

        # Mock function object
        self.function = Mock()
        self.function.name = 'testfunction-001'
        self.function.region = 'us-central1'
        self.function_name = self.function.name
    
    def test_init(self):
        """Test DeleteTask initialization."""
        task = DeleteTask(self.function, self.config)
        
        self.assertEqual(task.function, self.function)
        self.assertEqual(task.config, self.config)
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_successful_deletion(self, mock_subprocess):
        """Test successful function deletion."""
        # Mock successful deletion
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ''
        mock_subprocess.return_value = mock_result
        
        task = DeleteTask(self.function, self.config)
        result = task.execute()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['function_name'], self.function_name)
        self.assertIsNone(result.get('error'))
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_deletion_failure(self, mock_subprocess):
        """Test deletion failure."""
        # Mock failed deletion
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = 'Function not found'
        mock_subprocess.return_value = mock_result
        
        task = DeleteTask(self.function, self.config)
        result = task.execute()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['function_name'], self.function_name)
        self.assertIn('error', result)
        self.assertIn('Function not found', result['error'])
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_exception_handling(self, mock_subprocess):
        """Test exception handling during deletion."""
        # Mock exception
        mock_subprocess.side_effect = Exception('Network error')
        
        task = DeleteTask(self.function, self.config)
        result = task.execute()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['function_name'], self.function_name)
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Network error')
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_gcloud_command_structure(self, mock_subprocess):
        """Test that gcloud command has correct structure."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        task = DeleteTask(self.function, self.config)
        task.execute()
        
        # Check delete command structure
        call_args = mock_subprocess.call_args
        delete_args = call_args[0][0]
        
        self.assertEqual(delete_args[0], 'gcloud')
        self.assertEqual(delete_args[1], 'functions')
        self.assertEqual(delete_args[2], 'delete')
        self.assertEqual(delete_args[3], self.function_name)
        self.assertIn('--gen2', delete_args)
        self.assertIn('--quiet', delete_args)
        self.assertIn(f'--region={self.config.region}', delete_args)
        self.assertIn(f'--project={self.config.project}', delete_args)
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_error_message_truncation(self, mock_subprocess):
        """Test that error messages are truncated to 200 characters."""
        # Mock failed deletion with long error message
        long_error = 'A' * 300
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = long_error
        mock_subprocess.return_value = mock_result
        
        task = DeleteTask(self.function, self.config)
        result = task.execute()
        
        self.assertLessEqual(len(result['error']), 200)
        self.assertEqual(result['error'], 'A' * 200)
    
    @patch('shared_modules.delete.subprocess.run')
    def test_execute_timeout_handling(self, mock_subprocess):
        """Test timeout handling."""
        import subprocess
        
        mock_subprocess.side_effect = subprocess.TimeoutExpired('gcloud', 60)
        
        task = DeleteTask(self.function, self.config)
        result = task.execute()
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        # Check for timeout-related error message (could be "timeout", "timed out", or "expired")
        error_msg = result['error'].lower()
        self.assertTrue('timeout' in error_msg or 'timed out' in error_msg or 'expired' in error_msg,
                       f"Expected timeout-related error, got: {result['error']}")


if __name__ == '__main__':
    unittest.main()
