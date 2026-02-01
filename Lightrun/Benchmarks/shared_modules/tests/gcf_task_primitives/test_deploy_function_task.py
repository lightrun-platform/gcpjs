"""Unit tests for DeployFunctionTask class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import argparse
import sys
import time

# Add parent directory to path so we can import as a package
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
# We need root dir in path to import 'Lightrun.Benchmarks...'
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from ....shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask
from ....shared_modules.gcf_models.deploy_function_result import DeploymentSuccess, DeploymentFailure
from ....shared_modules.cli_parser import ParsedCLIArguments
from ....shared_modules.gcf_models.gcp_function import GCPFunction


class TestDeployFunctionTask(unittest.TestCase):
    """Test DeployFunctionTask class."""
    
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
            region='us-central1',
            name='testfunction-001',
            runtime='nodejs20',
            entry_point='testFunction',
            function_source_code_dir=self.function_dir
        )
        
        # Patch sleep to prevent waiting during tests
        self.sleep_patcher = patch('shared_modules.gcf_task_primitives.deploy_function_task.time.sleep')
        self.mock_sleep = self.sleep_patcher.start()

        self.mock_logger_factory = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_logger_factory.get_logger.return_value = self.mock_logger
        self.task = DeployFunctionTask(deployment_timeout_seconds=600, logger_factory=self.mock_logger_factory)
    
    def tearDown(self):
        self.sleep_patcher.stop()
    
    def test_init(self):
        """Test DeployFunctionTask initialization."""
        self.assertEqual(self.task.deployment_timeout_seconds, 600)
    
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_successful(self, mock_subprocess):
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
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        result = task.deploy_gcp_function(
            function_name=self.function.name,
            region=self.function.region,
            runtime='nodejs20',
            entry_point='testFunction',
            source_code_dir=self.function_dir,
            project='test-project',
            env_vars={'LIGHTRUN_SECRET': 'secret', 'DISPLAY_NAME': 'disp'}
        )
        
        self.assertIsInstance(result, DeploymentSuccess)
        self.assertEqual(result.url, 'https://test-function-001-abc123.run.app')
        self.assertIsNotNone(result.deploy_time)
    
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_failure(self, mock_subprocess):
        """Test deployment failure."""
        # Mock failed deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 1
        mock_deploy_result.stderr = 'Permission denied'
        
        mock_subprocess.return_value = mock_deploy_result
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        result = task.deploy_gcp_function(
            function_name=self.function.name,
            region=self.function.region,
            runtime='nodejs20',
            entry_point='testFunction',
            source_code_dir=self.function_dir
        )
        
        self.assertIsInstance(result, DeploymentFailure)
        self.assertIsNotNone(result.error)
        self.assertIn('Permission denied', result.error)
    
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.time.sleep')
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_timeout(self, mock_subprocess, mock_sleep):
        """Test deployment timeout."""
        import subprocess
        
        mock_sleep.return_value = None
        
        # Make subprocess.run raise TimeoutExpired immediately
        mock_subprocess.side_effect = subprocess.TimeoutExpired('gcloud', 300)
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        
        start = time.time()
        result = task.deploy_gcp_function(
            function_name=self.function.name,
            region=self.function.region,
            runtime='nodejs20',
            entry_point='testFunction',
            source_code_dir=self.function_dir
        )
        
        self.assertIsInstance(result, DeploymentFailure)
        self.assertEqual(result.error, 'Deployment timed out after 5 minutes')
    
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_url_retrieval_failure(self, mock_subprocess):
        """Test when deployment succeeds but URL retrieval fails."""
        # Mock successful deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        
        # Mock failed URL retrieval
        mock_url_result = Mock()
        mock_url_result.returncode = 1
        mock_url_result.stdout = ''
        
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        result = task.deploy_gcp_function(
            function_name=self.function.name,
            region=self.function.region,
            runtime='nodejs20',
            entry_point='testFunction',
            source_code_dir=self.function_dir
        )
        
        self.assertIsInstance(result, DeploymentSuccess)
        self.assertIsNone(result.url)
    
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_gcloud_command_structure(self, mock_subprocess):
        """Test that gcloud command has correct structure."""
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_url_result = Mock()
        mock_url_result.returncode = 0
        mock_url_result.stdout = 'https://test.run.app'
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        task.deploy_gcp_function(
            function_name='testfunction-001',
            region='us-central1',
            runtime='nodejs20',
            entry_point='testFunction',
            source_code_dir=self.function_dir,
            project='test-project',
            gen2=True
        )
        
        # Check deploy command structure
        deploy_call = mock_subprocess.call_args_list[0]
        deploy_args = deploy_call[0][0]
        
        self.assertEqual(deploy_args[0], 'gcloud')
        self.assertEqual(deploy_args[1], 'functions')
        self.assertEqual(deploy_args[2], 'deploy')
        self.assertEqual(deploy_args[3], 'testfunction-001')
        self.assertIn('--gen2', deploy_args)
        self.assertIn('--trigger-http', deploy_args)
        
    @patch('shared_modules.gcf_task_primitives.deploy_function_task.subprocess.run')
    def test_deploy_env_vars(self, mock_subprocess):
        """Test env vars."""
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_url_result = Mock()
        mock_url_result.returncode = 0
        mock_url_result.stdout = 'https://test.run.app'
        mock_subprocess.side_effect = [mock_deploy_result, mock_url_result]
        
        task = DeployFunctionTask(logger_factory=self.mock_logger_factory)
        task.deploy_gcp_function(
            function_name='test', region='us-central1', runtime='node', entry_point='func',
            source_code_dir=Path('.'),
            env_vars={'KEY': 'VALUE'}
        )
        
        deploy_call = mock_subprocess.call_args_list[0]
        deploy_args = deploy_call[0][0]
        
        # Find --set-env-vars
        env_index = -1
        try:
            env_index = deploy_args.index('--set-env-vars')
        except ValueError:
            pass
            
        if env_index != -1:
            self.assertIn('KEY=VALUE', deploy_args[env_index+1])
        else:
            # Maybe joined
            self.assertTrue(any('KEY=VALUE' in arg for arg in deploy_args))

if __name__ == '__main__':
    unittest.main()
