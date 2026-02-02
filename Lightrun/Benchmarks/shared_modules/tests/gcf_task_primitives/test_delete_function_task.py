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
    def test_execute_successful_deletion_with_cleanup(self, mock_subprocess):
        """Test successful function deletion and cleanup."""
        
        def side_effect(args, **kwargs):
            cmd_list = args if isinstance(args, list) else args.split()
            
            # Describe command
            if 'describe' in cmd_list:
                mock_res = Mock()
                mock_res.returncode = 0
                mock_res.stdout = '{"buildConfig": {"source": {"storageSource": {"bucket": "b", "object": "o"}}, "imageUri": "img"}}'
                return mock_res
                
            # Delete function command
            if 'delete' in cmd_list and 'functions' in cmd_list:
                mock_res = Mock()
                mock_res.returncode = 0
                return mock_res
                
            # Storage delete
            if 'storage' in cmd_list and 'rm' in cmd_list:
                mock_res = Mock()
                mock_res.returncode = 0
                return mock_res

            # Artifact delete
            if 'artifacts' in cmd_list:
                mock_res = Mock()
                mock_res.returncode = 0
                return mock_res
                
            return Mock(returncode=1, stderr="Unknown command")

        mock_subprocess.side_effect = side_effect
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteSuccess)
        
        # Verify calls
        # 1. Describe
        # 2. Delete function
        # 3. Delete source
        # 4. Delete image
        # Note: order of 3 and 4 depends on dict iteration or implementation order
        
        calls = mock_subprocess.call_args_list
        self.assertGreaterEqual(len(calls), 4)
        
        commands = [c[0][0] for c in calls]
        self.assertTrue(any('describe' in c for c in commands))
        self.assertTrue(any('functions' in c and 'delete' in c for c in commands))
        self.assertTrue(any('storage' in c for c in commands))
        self.assertTrue(any('artifacts' in c for c in commands))

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_get_resource_info(self, mock_subprocess):
        """Test resource info extraction."""
        mock_res = Mock()
        mock_res.returncode = 0
        mock_res.stdout = """
        {
            "buildConfig": {
                "source": {
                    "storageSource": {
                        "bucket": "my-bucket",
                        "object": "my-object.zip"
                    }
                },
                "imageUri": "us-central1-docker.pkg.dev/proj/repo/img"
            }
        }
        """
        mock_subprocess.return_value = mock_res
        
        task = DeleteFunctionTask(self.function)
        info = task._get_resource_info()
        
        self.assertEqual(info.get('source_url'), 'gs://my-bucket/my-object.zip')
        self.assertEqual(info.get('image_uri'), 'us-central1-docker.pkg.dev/proj/repo/img')

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_deletion_failure(self, mock_subprocess):
        """Test deletion failure."""
        def side_effect(args, **kwargs):
            if 'describe' in args:
                return Mock(returncode=0, stdout='{}')
            if 'delete' in args and 'functions' in args:
                return Mock(returncode=1, stderr='Function not found')
            return Mock(returncode=0) # cleanup, shouldn't run if delete fails? 
            # Actually implementation says cleanup is inside "if returncode == 0", so it won't run.

        mock_subprocess.side_effect = side_effect
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        self.assertIn('Function not found', result.stderr)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_exception_handling(self, mock_subprocess):
        """Test exception handling during deletion."""
        mock_subprocess.side_effect = Exception('Network error')
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        self.assertEqual(str(result.error), 'Network error')
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_error_message_captured(self, mock_subprocess):
        """Test that error messages are captured."""
        def side_effect(args, **kwargs):
            if 'describe' in args:
                return Mock(returncode=0, stdout='{}')
            if 'functions' in args and 'delete' in args:
                return Mock(returncode=1, stderr='A' * 300)
            return Mock(returncode=0)
            
        mock_subprocess.side_effect = side_effect
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertEqual(result.stderr, 'A' * 300)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_timeout_handling(self, mock_subprocess):
        """Test timeout handling."""
        import subprocess
        
        # Describe succeeds
        # function delete times out
        def side_effect(args, **kwargs):
            if 'describe' in args:
                return Mock(returncode=0, stdout='{}')
            if 'functions' in args and 'delete' in args:
                raise subprocess.TimeoutExpired('gcloud', 60)
            return Mock(returncode=0)

        mock_subprocess.side_effect = side_effect
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
         
        self.assertIsInstance(result, DeleteFailure)
        # Verify it handles TimeoutExpired and wraps/returns it
        self.assertTrue(any(x in str(result.error).lower() for x in ['timeout', 'timed out', 'expired']))


if __name__ == '__main__':
    unittest.main()


if __name__ == '__main__':
    unittest.main()
