"""Unit tests for WaitForColdTask class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import argparse
import sys

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.gcf_task_primitives.wait_for_cold_task import WaitForColdTask
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction


class TestWaitForColdTask(unittest.TestCase):
    """Test WaitForColdTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = MagicMock()
        self.function = Mock(spec=GCPFunction)
        self.function.name = 'testfunction-001'
        self.function.region = 'us-central1'
        self.function.project = 'test-project'
        self.function.logger = self.mock_logger
    
    def test_init(self):
        """Test WaitForColdTask initialization."""
        task = WaitForColdTask(
            function=self.function,
            cold_check_delay=15,
            consecutive_cold_checks=3
        )
        
        self.assertEqual(task.function_name, self.function.name)
        self.assertEqual(task.region, self.function.region)
        self.assertEqual(task.project, self.function.project)
        self.assertEqual(task.cold_check_delay, 15)
        self.assertEqual(task.logger, self.mock_logger)
    
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.wait_for_cold_task.time.sleep')
    @patch('Lightrun.Benchmarks.shared_modules.gcf_task_primitives.wait_for_cold_task.time.time')
    @patch.object(WaitForColdTask, 'check_function_instances')
    def test_execute_successful(self, mock_check, mock_time, mock_sleep):
        """Test successful cold wait."""
        
        mock_sleep.return_value = None
        # Mock time sequence: start, start+delay...
        # Just need it to not timeout
        mock_time.side_effect = lambda: 1000 + mock_check.call_count * 10
        
        # We need check_function_instances to return 1 (cold/uncertain) enough times
        mock_check.return_value = 1
        
        task = WaitForColdTask(
            function=self.function,
            cold_check_delay=0, # fast
            consecutive_cold_checks=2
        )
        
        # Should succeed
        task.execute(deployment_start_time=1000, max_poll_minutes=1)
        
        self.assertGreaterEqual(mock_check.call_count, 2)

if __name__ == '__main__':
    unittest.main()
