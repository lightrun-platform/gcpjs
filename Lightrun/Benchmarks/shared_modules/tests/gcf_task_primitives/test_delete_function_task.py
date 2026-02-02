"""Unit tests for DeleteTask class."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import argparse
import sys
from pathlib import Path

# Add parent directory to path
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task import DeleteFunctionTask, DeleteSuccess, DeleteFailure
from Lightrun.Benchmarks.shared_modules.cli_parser import ParsedCLIArguments
from Lightrun.Benchmarks.shared_modules.gcf_models import GCPFunction


class TestDeleteFunctionTask(unittest.TestCase):
    """Test DeleteFunctionTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock function object
        self.function = Mock(spec=GCPFunction)
        self.function.name = 'testfunction-001'
        self.function.region = 'us-central1'
        self.function.project = 'test-project'
        self.function.gen2 = True
        self.function.logger = MagicMock()
        self.function.assets = []  # Start with empty assets (simulating fresh load)

    def test_init(self):
        """Test DeleteFunctionTask initialization."""
        task = DeleteFunctionTask(self.function)
        self.assertEqual(task.function, self.function)

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_successful_deletion_with_discovery_and_cleanup(self, mock_subprocess):
        """Test successful deletion where assets are discovered and cleaned."""
        
        # 1. Mock asset discovery on function object
        mock_asset1 = Mock()
        mock_asset1.name = "asset-1"
        mock_asset2 = Mock()
        mock_asset2.name = "asset-2"
        self.function.discover_associated_assets.return_value = [mock_asset1, mock_asset2]
        
        # 2. Mock asset existence checks (to verify they are checked after delete)
        mock_asset1.exists.return_value = False # Cleaned up
        mock_asset2.exists.return_value = False # Cleaned up
        
        # 3. Mock function deletion success
        mock_res = Mock()
        mock_res.returncode = 0
        mock_subprocess.return_value = mock_res
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteSuccess)
        
        # Verify discovery was called (since function.assets was empty)
        self.function.discover_associated_assets.assert_called_once()
        
        # Verify function delete command
        mock_subprocess.assert_called()
        args = mock_subprocess.call_args[0][0]
        self.assertIn('delete', args)
        
        # Verify asset cleanup (called on all assets)
        mock_asset1.delete.assert_called_with(self.function.logger)
        
        mock_asset2.delete.assert_called_with(self.function.logger)

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_with_preexisting_assets(self, mock_subprocess):
        """Test deletion when assets are already present in function object."""
        
        mock_asset = Mock()
        mock_asset.name = "known-asset"
        # Since we mock the attribute, we need to ensure the task picks it up.
        # But 'function' is a Mock passed to init. 
        # The task copies reference. 
        self.function.assets = [mock_asset]
        
        mock_res = Mock()
        mock_res.returncode = 0
        mock_subprocess.return_value = mock_res
        
        task = DeleteFunctionTask(self.function)
        
        result = task.execute(timeout=120)
        
        # Verify discovery NOT called because assets present
        self.function.discover_associated_assets.assert_not_called()
        
        self.assertIsInstance(result, DeleteSuccess)
        mock_asset.delete.assert_called()

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_cleanup_continues_on_failure(self, mock_subprocess):
        """Test that assets are cleaned even if function deletion fails."""
        
        mock_asset = Mock()
        self.function.discover_associated_assets.return_value = [mock_asset]
        
        # Mock function deletion failure
        mock_res = Mock()
        mock_res.returncode = 1
        mock_res.stderr = "Function delete failed"
        mock_subprocess.return_value = mock_res
        
        task = DeleteFunctionTask(self.function)
        result = task.execute(timeout=120)
        
        self.assertIsInstance(result, DeleteFailure)
        
        # Asset cleanup should still happen
        mock_asset.delete.assert_called()

    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.delete_function_task.subprocess.run')
    def test_execute_logs_verification_failure(self, mock_subprocess):
        """Test that failure to clean an asset is logged."""
        
        mock_asset = Mock()
        mock_asset.name = "stubborn-asset"
        # Simulate failure during deletion
        mock_asset.delete.side_effect = Exception("Simulated deletion error")
        self.function.discover_associated_assets.return_value = [mock_asset]
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        task = DeleteFunctionTask(self.function)
        task.execute(timeout=120)
        
        mock_asset.delete.assert_called()
        # Should have logged error
        self.function.logger.error.assert_any_call(f"Failed to clean up asset stubborn-asset: Simulated deletion error")

if __name__ == '__main__':
    unittest.main()
