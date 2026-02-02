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

from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task import DeployFunctionTask, LabelClashException
from Lightrun.Benchmarks.shared_modules.gcf_models.deploy_function_result import DeploymentSuccess, DeploymentFailure
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction

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
        
        # Mock logger
        self.mock_logger = MagicMock()
        
        self.function = GCPFunction(
            region='us-central1',
            name='testfunction-001',
            runtime='nodejs20',
            entry_point='testFunction',
            function_source_code_dir=self.function_dir,
            project='test-project',
            env_vars={'LIGHTRUN_SECRET': 'secret', 'DISPLAY_NAME': 'disp'},
            kwargs={},
            labels={'foo': 'bar'}
        )
        self.function.logger = self.mock_logger
        
        # Patch sleep to prevent waiting during tests
        self.sleep_patcher = patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task.time.sleep')
        self.mock_sleep = self.sleep_patcher.start()

        self.task = DeployFunctionTask(function=self.function, deployment_timeout_seconds=600)
    
    def tearDown(self):
        self.sleep_patcher.stop()
    
    def test_init(self):
        """Test DeployFunctionTask initialization."""
        self.assertEqual(self.task.deployment_timeout_seconds, 600)
        self.assertEqual(self.task.f, self.function)
        self.assertEqual(self.task.logger, self.mock_logger)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._execute_gcloud_command')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._get_function_url')
    def test_deploy_successful(self, mock_get_url, mock_execute):
        """Test successful deployment."""
        # Mock successful deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_deploy_result.stdout = 'Deployment successful'
        mock_deploy_result.stderr = ''
        mock_execute.return_value = mock_deploy_result
        
        # Mock successful URL retrieval
        mock_get_url.return_value = 'https://test-function-001-abc123.run.app'
        
        # Mock asset discovery on the function object
        mock_asset = Mock()
        mock_asset.name = "test-asset"
        # We need to ensure we patch the method on the class or instance.
        # Since self.function is a real object, we can use patch.object or assign a Mock
        with patch.object(self.function, 'discover_associated_assets', return_value=[mock_asset]) as mock_discover:
            result = self.task.deploy()
            
            self.assertIsInstance(result, DeploymentSuccess)
            self.assertEqual(result.url, 'https://test-function-001-abc123.run.app')
            self.assertIsNotNone(result.deploy_time)
            mock_execute.assert_called_once()
            mock_discover.assert_called()
            self.assertEqual(len(result.assets), 1)
            mock_asset.apply_labels.assert_called_with({'foo': 'bar'}, self.mock_logger)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._execute_gcloud_command')
    def test_deploy_failure(self, mock_execute):
        """Test deployment failure."""
        # Mock failed deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 1
        mock_deploy_result.stderr = 'Permission denied'
        mock_execute.return_value = mock_deploy_result
        
        # Mock asset discovery return empty on failure
        with patch.object(self.function, 'discover_associated_assets', return_value=[]) as mock_discover:
            result = self.task.deploy()
            
            self.assertIsInstance(result, DeploymentFailure)
            self.assertIsNotNone(result.error)
            self.assertIn('Permission denied', result.error)
            mock_discover.assert_called()
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._execute_gcloud_command')
    def test_deploy_timeout(self, mock_execute):
        """Test deployment timeout."""
        import subprocess
        # Make _execute_gcloud_command raise TimeoutExpired immediately
        mock_execute.side_effect = subprocess.TimeoutExpired('gcloud', 300)
        
        with patch.object(self.function, 'discover_associated_assets', return_value=[]) as mock_discover:
            result = self.task.deploy()
            
            self.assertIsInstance(result, DeploymentFailure)
            self.assertEqual(result.error, 'Deployment timed out after 5 minutes')
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._execute_gcloud_command')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task._get_function_url')
    def test_deploy_url_retrieval_failure(self, mock_get_url, mock_execute):
        """Test when deployment succeeds but URL retrieval fails."""
        # Mock successful deployment
        mock_deploy_result = Mock()
        mock_deploy_result.returncode = 0
        mock_execute.return_value = mock_deploy_result
        
        # Mock failed URL retrieval
        mock_get_url.return_value = None
        
        with patch.object(self.function, 'discover_associated_assets', return_value=[]) as mock_discover:
            result = self.task.deploy()
            
            self.assertIsInstance(result, DeploymentSuccess)
            self.assertIsNone(result.url)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task.GCFDeployCommandParameters.create')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task.deploy_with_extended_gcf_parameters')
    def test_deploy_parameter_passing(self, mock_deploy_helper, mock_create):
        """Test that parameters are correctly passed from GCPFunction to parameters creator."""
        self.task.deploy()
        
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['function_name'], self.function.name)
        self.assertEqual(call_kwargs['region'], self.function.region)
        self.assertEqual(call_kwargs['runtime'], self.function.runtime)
        # Verify kwargs are passed
        self.assertEqual(call_kwargs['env_vars']['LIGHTRUN_SECRET'], 'secret')
        self.assertEqual(call_kwargs['update_labels'], {'foo': 'bar'})
        
        # Verify BP_IMAGE_LABELS injection
        self.assertIn('update_build_env_vars', call_kwargs)
        self.assertIn('BP_IMAGE_LABELS', call_kwargs['update_build_env_vars'])
        self.assertEqual(call_kwargs['update_build_env_vars']['BP_IMAGE_LABELS'], 'foo=bar')

    def test_deploy_label_clash(self):
        """Test that conflicting labels raise LabelClashException."""
        # Setup conflicting labels
        self.function.labels = {'app': 'v1'}
        self.function.kwargs = {'update_build_env_vars': {'app': 'v2'}}
        
        with self.assertRaises(LabelClashException):
            self.task.deploy()

    def test_deploy_label_merge_success(self):
        """Test that same labels merge successfully."""
        # Setup matching labels
        self.function.labels = {'app': 'v1'}
        self.function.kwargs = {'update_build_env_vars': {'app': 'v1', 'env': 'prod'}}
        
        # We need to mock the helpers that deploy() calls after label check
        with patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task.GCFDeployCommandParameters.create') as mock_create, \
             patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.deploy_function_task.deploy_with_extended_gcf_parameters') as mock_deploy_helper:
             
            self.task.deploy()
            
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            
            # Check combined BP_IMAGE_LABELS
            bp_labels = call_kwargs['update_build_env_vars']['BP_IMAGE_LABELS']
            self.assertIn('app=v1', bp_labels)
            self.assertIn('env=prod', bp_labels)

if __name__ == '__main__':
    unittest.main()
