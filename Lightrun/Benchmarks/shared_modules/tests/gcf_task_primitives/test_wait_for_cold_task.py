"""Unit tests for WaitForColdTask class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from ....shared_modules.gcf_task_primitives.wait_for_cold_task import WaitForColdTask


class TestWaitForColdTask(unittest.TestCase):
    """Test WaitForColdTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.function_name = 'testfunction-001'
        self.function_index = 1
        self.region = 'us-central1'
        self.project = 'test-project'
    
    def test_init(self):
        """Test WaitForColdTask initialization."""
        task = WaitForColdTask(
            function_name=self.function_name,
            region=self.region,
            project=self.project,
            cold_check_delay=15,
            consecutive_cold_checks=3
        )
        
        self.assertEqual(task.function_name, self.function_name)
        self.assertEqual(task.region, self.region)
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.cold_check_delay, 15)
    
    @patch('shared_modules.gcf_task_primitives.wait_for_cold_task.time.sleep')
    @patch('shared_modules.gcf_task_primitives.wait_for_cold_task.time.time')
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
            function_name=self.function_name,
            region=self.region,
            project=self.project,
            cold_check_delay=0, # fast
            consecutive_cold_checks=2
        )
        
        # Should succeed
        task.execute(deployment_start_time=1000, max_poll_minutes=1)
        
        self.assertGreaterEqual(mock_check.call_count, 2)

if __name__ == '__main__':
    unittest.main()
