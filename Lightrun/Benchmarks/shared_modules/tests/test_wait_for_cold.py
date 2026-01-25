"""Unit tests for WaitForColdTask class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from shared_modules.wait_for_cold import WaitForColdTask, ColdStartDetectionError


class TestWaitForColdTask(unittest.TestCase):
    """Test WaitForColdTask class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = argparse.Namespace(
            region='us-central1',
            project='test-project'
        )
        # Function names are lowercase for Cloud Run compatibility
        self.function_name = 'testfunction-001'
        self.function_index = 1
    
    def test_init(self):
        """Test WaitForColdTask initialization."""
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        
        self.assertEqual(task.function_name, self.function_name)
        self.assertEqual(task.region, 'us-central1')
        self.assertEqual(task.index, self.function_index)
        self.assertEqual(task.config, self.config)
    
    @patch('requests.get')
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_cold(self, mock_subprocess, mock_requests_get):
        """Test checking function instances when cold (no timeSeries data)."""
        # Mock Cloud Run describe succeeds
        mock_describe = Mock(returncode=0)
        # Mock gcloud auth print-access-token succeeds
        mock_token = Mock(returncode=0, stdout='test-access-token')
        
        mock_subprocess.side_effect = [mock_describe, mock_token]
        
        # Mock monitoring API returns no timeSeries (cold state)
        import json
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unit": "1"}  # No timeSeries field
        mock_response.text = '{"unit": "1"}'
        mock_requests_get.return_value = mock_response

        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()

        # Should return 1 (uncertainty) when no timeSeries data
        self.assertEqual(count, 1)
    
    @patch('requests.get')
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_warm(self, mock_subprocess, mock_requests_get):
        """Test checking function instances when warm (2 instances)."""
        # Mock Cloud Run describe succeeds
        mock_describe = Mock(returncode=0)
        # Mock gcloud auth print-access-token succeeds
        mock_token = Mock(returncode=0, stdout='test-access-token')
        
        mock_subprocess.side_effect = [mock_describe, mock_token]
        
        # Mock requests.get for monitoring API - return JSON with 2 active instances
        # Include a recent timestamp (within last 6 minutes) so the data is considered fresh
        from datetime import datetime, timezone, timedelta
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        mock_response = Mock()
        mock_response.text = '{"timeSeries": [{"metric": {"labels": {"state": "active"}}, "points": [{"value": {"int64Value": "2"}, "interval": {"endTime": "' + recent_time + '"}}]}]}'
        mock_response.json.return_value = {
            "timeSeries": [{
                "metric": {"labels": {"state": "active"}},
                "points": [{
                    "value": {"int64Value": "2"},
                    "interval": {"endTime": recent_time}
                }]
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response
        
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()
        
        self.assertEqual(count, 2)
    
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_service_not_found(self, mock_subprocess):
        """Test when Cloud Run service doesn't exist yet."""
        # Mock Cloud Run describe failure
        mock_describe = Mock()
        mock_describe.returncode = 1
        
        mock_subprocess.return_value = mock_describe
        
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()
        
        # Should return 1 (uncertainty - might still be warm)
        self.assertEqual(count, 1)
    
    @patch('requests.get')
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_monitoring_failure(self, mock_subprocess, mock_requests_get):
        """Test when monitoring API fails."""
        # Mock Cloud Run describe succeeds
        mock_describe = Mock(returncode=0)
        # Mock gcloud auth print-access-token succeeds
        mock_token = Mock(returncode=0, stdout='test-access-token')
        
        mock_subprocess.side_effect = [mock_describe, mock_token]
        
        # Mock requests.get to raise an exception (monitoring API failure)
        import requests
        mock_requests_get.side_effect = requests.RequestException('API error')
        
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()

        # Should return uncertainty (1) if monitoring fails - don't assume cold
        self.assertEqual(count, 1)
    
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_exception(self, mock_subprocess):
        """Test exception handling."""
        mock_subprocess.side_effect = Exception('Network error')
        
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()
        
        # Should return 1 (uncertainty) on exception
        self.assertEqual(count, 1)
    
    @patch('shared_modules.wait_for_cold.time.sleep')
    @patch('shared_modules.wait_for_cold.time.time')
    @patch.object(WaitForColdTask, 'check_function_instances')
    def test_execute_successful_cold_detection(self, mock_check, mock_time, mock_sleep):
        """Test successful cold start detection."""
        deployment_start = 1000.0
        poll_start = deployment_start  # Polling starts after initial wait (which is 0 in this test)

        # Track iteration count - time.time() is called multiple times per iteration
        # We need to simulate time passing: start_time is set once, then time increments
        # by 15 seconds per iteration (poll_interval)
        iteration_count = [0]  # Use list to allow modification in nested function
        
        def time_side_effect():
            # First call sets start_time
            if iteration_count[0] == 0:
                current = poll_start
            else:
                # After start_time, time increments by poll_interval (15s) per iteration
                # But time.time() is called multiple times per iteration, so we need to
                # track based on how many times it's been called, not iteration count
                # Actually, let's just increment by a small amount each call to simulate
                # the passage of time within an iteration
                calls = len([x for x in dir(mock_time) if 'call' in x.lower()]) if hasattr(mock_time, 'call_count') else iteration_count[0]
                # Simpler: just increment by a small fixed amount each call
                # After start_time, each iteration adds 15 seconds, but time.time() is called
                # ~4-5 times per iteration, so increment by ~3 seconds per call
                current = poll_start + (iteration_count[0] * 15) + ((mock_time.call_count - 1) * 0.1)
            iteration_count[0] += 1
            return current

        # Better approach: use a counter that increments properly
        call_count = [0]
        def time_side_effect_v2():
            call_count[0] += 1
            # First call sets start_time
            if call_count[0] == 1:
                return poll_start
            # After that, simulate time passing: each iteration of the loop
            # calls time.time() multiple times, but the elapsed time should increase
            # by ~15 seconds per iteration. Let's approximate: ~5 calls per iteration
            # so increment by 3 seconds per call to get ~15s per iteration
            return poll_start + (call_count[0] - 1) * 3

        mock_time.side_effect = time_side_effect_v2
        mock_sleep.return_value = None  # Skip sleep

        # Mock instance check - return 1 (no timeSeries data) for cold detection
        # Need 16 consecutive checks returning 1 to confirm cold
        mock_check.return_value = 1

        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)

        # Use very short wait times for testing (0 initial wait, 10 minutes max poll to allow 4 min confirmation)
        # Need enough time for 16 checks at 15s intervals = 240s = 4 minutes
        # Plus buffer for multiple time.time() calls per iteration
        time_to_cold = task.execute(deployment_start, max_poll_minutes=10)
        
        self.assertIsNotNone(time_to_cold)
        self.assertGreaterEqual(time_to_cold, 0)
    
    @patch('shared_modules.wait_for_cold.time.sleep')
    @patch('shared_modules.wait_for_cold.time.time')
    @patch.object(WaitForColdTask, 'check_function_instances')
    def test_execute_timeout(self, mock_check, mock_time, mock_sleep):
        """Test timeout when function never becomes cold."""
        deployment_start = 1000.0
        # Mock time progression beyond timeout
        mock_time.side_effect = [
            deployment_start,
            deployment_start + 60,  # After initial wait
            deployment_start + 120,  # Start polling
            deployment_start + 180,  # Still polling
            deployment_start + 240,  # Timeout
        ]
        
        # Mock always warm
        mock_check.return_value = 1
        
        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        
        # Use very short timeout for testing
        with self.assertRaises(ColdStartDetectionError) as context:
            task.execute(deployment_start, max_poll_minutes=1)
        
        self.assertIn('Could not confirm cold state', str(context.exception))
        self.assertIn(self.function_name, str(context.exception))
    
    def test_cold_start_detection_error(self):
        """Test ColdStartDetectionError exception."""
        error = ColdStartDetectionError('Test error message')
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), 'Test error message')
    
    @patch('requests.get')
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_invalid_monitoring_output(self, mock_subprocess, mock_requests_get):
        """Test handling of invalid monitoring output."""
        # Mock Cloud Run describe succeeds
        mock_describe = Mock(returncode=0)
        # Mock gcloud auth print-access-token succeeds
        mock_token = Mock(returncode=0, stdout='test-access-token')
        
        mock_subprocess.side_effect = [mock_describe, mock_token]
        
        # Mock monitoring API returns invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('Invalid JSON')
        mock_response.text = 'invalid'
        mock_requests_get.return_value = mock_response

        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()

        # Should return uncertainty (1) if can't parse - don't assume cold
        self.assertEqual(count, 1)
    
    @patch('requests.get')
    @patch('shared_modules.wait_for_cold.subprocess.run')
    def test_check_function_instances_empty_monitoring_output(self, mock_subprocess, mock_requests_get):
        """Test handling of empty monitoring output."""
        # Mock Cloud Run describe succeeds
        mock_describe = Mock(returncode=0)
        # Mock gcloud auth print-access-token succeeds
        mock_token = Mock(returncode=0, stdout='test-access-token')
        
        mock_subprocess.side_effect = [mock_describe, mock_token]
        
        # Mock monitoring API returns empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unit": "1"}  # No timeSeries field
        mock_response.text = '{"unit": "1"}'
        mock_requests_get.return_value = mock_response

        task = WaitForColdTask(self.function_name, 'us-central1', self.function_index, self.config)
        count = task.check_function_instances()

        # Should return uncertainty (1) if no timeSeries data - don't assume cold
        self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main()
