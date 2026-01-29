"""Unit tests for DeployTask class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import argparse
import sys
import time

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from shared_modules.deploy import DeployTask
from shared_modules.cli_parser import ParsedCLIArguments
from shared_modules.gcf_models.gcp_function import GCPFunction


class TestDeployTask(unittest.TestCase):
    """Test DeployTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ParsedCLIArguments(argparse.Namespace(
            base_function_name='testFunction',
            runtime='nodejs20',
            region='us-central1',
            project='test-project',
            entry_point='testFunction'
        ))
        self.function_dir = Path('/tmp/test_function')
        self.lightrun_secret = 'test-secret-123'
        self.function_index = 1
        self.function = GCPFunction(
            index=1,
            region='us-central1',
            base_name='testFunction'
        )
    
    def test_init(self):
        """Test DeployTask initialization."""
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        
        self.assertEqual(task.index, 1)
        self.assertEqual(task.lightrun_secret, 'test-secret-123')
        # Function names are converted to lowercase for Cloud Run compatibility
        self.assertEqual(task.function_name, 'testfunction-001')
        self.assertEqual(task.display_name, 'testFunction-gcf-performance-test-001')
        self.assertEqual(task.function_dir, self.function_dir)
    
    def test_init_function_name_formatting(self):
        """Test function name formatting with different indices."""
        function = GCPFunction(index=42, region='us-central1', base_name='testFunction')
        task = DeployTask(
            function_name=function.name,
            display_name=function.display_name,
            region=function.region,
            index=function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        # Function names are converted to lowercase for Cloud Run compatibility
        self.assertEqual(task.function_name, 'testfunction-042')
        self.assertEqual(task.display_name, 'testFunction-gcf-performance-test-042')
    
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_successful_deployment(self, mock_subprocess):
        """Test successful deployment."""
        # Mock successful deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_deploy_result.stdout = 'Deployment successful'
        mock_deploy_result.stderr = ''
        
        # Mock successful URL retrieval
        mock_url_result = Mock()
        mock_url_result.returncode = 0
        mock_url_result.stdout = 'https://test-function-001-abc123.run.app'
        
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        result = task.execute()
        
        self.assertTrue(result.success)
        # Function names are converted to lowercase for Cloud Run compatibility
        self.assertEqual(task.function_name, 'testfunction-001')
        self.assertEqual(task.display_name, 'testFunction-gcf-performance-test-001')
        self.assertEqual(result.url, 'https://test-function-001-abc123.run.app')
        self.assertIsNotNone(result.deploy_time)
        self.assertIsNone(result.error)
    
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_deployment_failure(self, mock_subprocess):
        """Test deployment failure."""
        # Mock failed deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 1
        mock_deploy_result.stderr = 'Permission denied'
        
        mock_subprocess.return_value = mock_deploy_result
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        result = task.execute()
        
        self.assertFalse(result.success)
        # Function names are converted to lowercase for Cloud Run compatibility
        self.assertEqual(task.function_name, 'testfunction-001')
        self.assertIsNone(result.url)
        self.assertIsNotNone(result.error)
        self.assertIn('Permission denied', result.error)
    
    @patch('shared_modules.deploy.time.sleep')
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_timeout(self, mock_subprocess, mock_sleep):
        """Test deployment timeout."""
        import subprocess
        import threading
        
        # Track total sleep time - allow up to 1 second total
        total_slept = [0.0]
        sleep_event = threading.Event()
        
        def sleep_side_effect(seconds):
            if total_slept[0] < 1.0:
                # Allow up to 1 second of real sleep using threading.Event.wait()
                sleep_amount = min(seconds, 1.0 - total_slept[0])
                if sleep_amount > 0:
                    # Use threading.Event.wait() which is not mocked
                    sleep_event.wait(timeout=sleep_amount)
                    total_slept[0] += sleep_amount
            # Skip longer retry delays
        
        mock_sleep.side_effect = sleep_side_effect
        
        # Make subprocess.run raise TimeoutExpired immediately
        mock_subprocess.side_effect = subprocess.TimeoutExpired('gcloud', 300)
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        
        start = time.time()
        result = task.execute()
        elapsed = time.time() - start
        
        # Should take approximately 1 second (initial sleep + some overhead)
        self.assertGreaterEqual(elapsed, 0.9)
        self.assertLess(elapsed, 2.0)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Deployment timed out after 5 minutes')
        self.assertIsNone(result.url)
    
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_url_retrieval_failure(self, mock_subprocess):
        """Test when deployment succeeds but URL retrieval fails."""
        # Mock successful deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        
        # Mock failed URL retrieval
        mock_url_result = Mock()
        mock_url_result.returncode = 1
        mock_url_result.stdout = ''
        
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        result = task.execute()
        
        self.assertTrue(result.success)
        self.assertIsNone(result.url)
    
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_env_vars_formatting(self, mock_subprocess):
        """Test that environment variables are correctly formatted."""
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_url_result = Mock()
        mock_url_result.returncode = 0
        mock_url_result.stdout = 'https://test.run.app'
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        task.execute()
        
        # Check that env vars are included in deploy command
        self.assertTrue(mock_subprocess.called, 'subprocess.run should have been called')
        deploy_call = mock_subprocess.call_args_list[0]
        deploy_args = deploy_call[0][0]
        
        # Find --set-env-vars argument
        env_var_index = None
        for i, arg in enumerate(deploy_args):
            if arg == '--set-env-vars':
                env_var_index = i
                break
        
        if env_var_index is None:
            # If not found, check all args as a string
            all_args = ' '.join(deploy_args)
            self.assertIn('LIGHTRUN_SECRET=test-secret-123', all_args)
            self.assertIn('DISPLAY_NAME=testFunction-gcf-performance-test-001', all_args)
        else:
            env_vars = deploy_args[env_var_index + 1]
            self.assertIn('LIGHTRUN_SECRET=test-secret-123', env_vars)
            self.assertIn('DISPLAY_NAME=testFunction-gcf-performance-test-001', env_vars)
    
    @patch('shared_modules.deploy.subprocess.run')
    def test_execute_gcloud_command_structure(self, mock_subprocess):
        """Test that gcloud command has correct structure."""
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_url_result = Mock()
        mock_url_result.returncode = 0
        mock_url_result.stdout = 'https://test.run.app'
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployTask(
            function_name=self.function.name,
            display_name=self.function.display_name,
            region=self.function.region,
            index=self.function.index,
            lightrun_secret=self.lightrun_secret,
            config=self.config,
            function_dir=self.function_dir
        )
        task.execute()
        
        # Check deploy command structure
        deploy_call = mock_subprocess.call_args_list[0]
        deploy_args = deploy_call[0][0]
        
        self.assertEqual(deploy_args[0], 'gcloud')
        self.assertEqual(deploy_args[1], 'functions')
        self.assertEqual(deploy_args[2], 'deploy')
        # Function names are converted to lowercase for Cloud Run compatibility
        self.assertEqual(deploy_args[3], 'testfunction-001')
        self.assertIn('--gen2', deploy_args)
        self.assertIn('--trigger-http', deploy_args)
        self.assertIn('--allow-unauthenticated', deploy_args)
        self.assertIn('--min-instances=0', deploy_args)


if __name__ == '__main__':
    unittest.main()
