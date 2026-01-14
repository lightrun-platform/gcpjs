"""Tests for utils module."""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import from package
from gcp_function_tests.utils import run_command


class TestRunCommand:
    """Tests for run_command function."""
    
    def test_successful_command(self):
        """Test successful command execution."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Success output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            exit_code, stdout, stderr = run_command(["echo", "test"])
            
            assert exit_code == 0
            assert stdout == "Success output"
            assert stderr == ""
            mock_run.assert_called_once()
    
    def test_failed_command(self):
        """Test failed command execution."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error occurred"
            mock_run.return_value = mock_result
            
            exit_code, stdout, stderr = run_command(["false"])
            
            assert exit_code == 1
            assert stdout == ""
            assert stderr == "Error occurred"
    
    def test_timeout(self):
        """Test command timeout."""
        with patch('subprocess.run') as mock_run:
            from subprocess import TimeoutExpired
            mock_run.side_effect = TimeoutExpired("cmd", 10)
            
            exit_code, stdout, stderr = run_command(["sleep", "100"], timeout=10)
            
            assert exit_code == 1
            assert stdout == ""
            assert "timed out" in stderr
    
    def test_exception(self):
        """Test exception handling."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")
            
            exit_code, stdout, stderr = run_command(["test"])
            
            assert exit_code == 1
            assert stdout == ""
            assert "Unexpected error" in stderr
