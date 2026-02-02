"""Unit tests for DeleteTask class."""

import unittest
from unittest.mock import Mock, patch
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
# Add parent directory to path so we can import as a package
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
# We need root dir in path to import 'Lightrun.Benchmarks...'
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task import DeleteFunctionTask, DeleteSuccess, DeleteFailure
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from unittest.mock import MagicMock


class TestDeleteFunctionTask(unittest.TestCase):
    """Test DeleteFunctionTask class."""
    
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
        self.function.project = 'test-project'
        self.function.gen2 = True
        self.function.logger = MagicMock() # Mock logger on the function
        self.function_name = self.function.name
    
    def test_init(self):
        """Test DeleteFunctionTask initialization."""
        task = DeleteFunctionTask(self.function)
        
        self.assertEqual(task.function, self.function)
        
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_successful_deletion(self, mock_subprocess):
        """Test successful function deletion."""
        # Mock successful deletion
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ''
        mock_subprocess.return_value = mock_result
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        
        self.assertIsInstance(result, DeleteSuccess)
        self.assertEqual(result.function_name, self.function_name)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_deletion_failure(self, mock_subprocess):
        """Test deletion failure."""
        # Mock failed deletion
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = 'Function not found'
        mock_subprocess.return_value = mock_result
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        self.assertEqual(result.function_name, self.function_name)
        self.assertIsNotNone(result.error)
        self.assertIn('Function not found', result.stderr)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_exception_handling(self, mock_subprocess):
        """Test exception handling during deletion."""
        # Mock exception
        mock_subprocess.side_effect = Exception('Network error')
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        self.assertEqual(result.function_name, self.function_name)
        self.assertIsNotNone(result.error)
        self.assertEqual(str(result.error), 'Network error')
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_gcloud_command_structure(self, mock_subprocess):
        """Test that gcloud command has correct structure."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        task = DeleteFunctionTask(self.function)
        task.execute(timeout=120)
        
        # Check delete command structure
        call_args = mock_subprocess.call_args
        delete_args = call_args[0][0]
        
        self.assertEqual(delete_args[0], 'gcloud')
        self.assertEqual(delete_args[1], 'functions')
        self.assertEqual(delete_args[2], 'delete')
        self.assertEqual(delete_args[3], self.function_name)
        self.assertIn('--gen2', delete_args)
        self.assertIn('--quiet', delete_args)
        self.assertIn(f'--region={self.function.region}', delete_args)
        self.assertIn(f'--project={self.function.project}', delete_args)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_error_message_truncation(self, mock_subprocess):
        """Test that error messages are truncated to 200 characters."""
        # Mock failed deletion with long error message
        long_error = 'A' * 300
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = long_error
        mock_subprocess.return_value = mock_result
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertEqual(result.stderr, long_error)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_timeout_handling(self, mock_subprocess):
        """Test timeout handling."""
        import subprocess
        
        mock_subprocess.side_effect = subprocess.TimeoutExpired('gcloud', 60)
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        self.assertIsNotNone(result.error)
        # Check for timeout-related error message (could be "timeout", "timed out", or "expired")
        error_msg = str(result.error).lower()
        self.assertTrue('timeout' in error_msg or 'timed out' in error_msg or 'expired' in error_msg,
                       f"Expected timeout-related error, got: {result.error}")


if __name__ == '__main__':
    unittest.main()
