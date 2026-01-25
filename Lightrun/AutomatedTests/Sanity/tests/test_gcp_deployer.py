"""Tests for GCPDeployer class."""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import from package
from gcp_function_tests.gcp_deployer import GCPDeployer
from gcp_function_tests.models import DeploymentResult


class TestGCPDeployer:
    """Tests for GCPDeployer class."""
    
    def test_extract_url_from_output_with_https_trigger(self):
        """Test URL extraction from deployment output."""
        deployer = GCPDeployer()
        stdout = """
        httpsTrigger:
          url: https://europe-west1-project.cloudfunctions.net/test-function
        """
        url = deployer._extract_url_from_output(stdout, "europe-west1", "test-function")
        assert url == "https://europe-west1-project.cloudfunctions.net/test-function"
    
    def test_extract_url_from_output_with_cloudfunctions_net(self):
        """Test URL extraction from cloudfunctions.net line."""
        deployer = GCPDeployer()
        stdout = """
        Some other output
        https://europe-west1-project.cloudfunctions.net/test-function
        More output
        """
        url = deployer._extract_url_from_output(stdout, "europe-west1", "test-function")
        assert url == "https://europe-west1-project.cloudfunctions.net/test-function"
    
    def test_extract_url_fallback(self):
        """Test URL extraction fallback."""
        deployer = GCPDeployer(project_id="test-project")
        stdout = "No URL in output"
        url = deployer._extract_url_from_output(stdout, "europe-west1", "test-function")
        assert url == "https://europe-west1-test-project.cloudfunctions.net/test-function"
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.gcp_deployer.run_command_async')
    async def test_deploy_function_success(self, mock_run_command):
        """Test successful function deployment."""
        deployer = GCPDeployer()
        mock_run_command.return_value = (
            0,
            "httpsTrigger:\n  url: https://region-project.cloudfunctions.net/test",
            ""
        )
        
        result = await deployer.deploy_function(
            "test", Path("/tmp"), 20, 2, "europe-west1"
        )
        
        assert isinstance(result, DeploymentResult)
        assert result.success is True
        assert result.url is not None
        assert result.error is None
        assert result.used_region == "europe-west1"
        mock_run_command.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.gcp_deployer.run_command_async')
    async def test_deploy_function_failure(self, mock_run_command):
        """Test failed function deployment."""
        deployer = GCPDeployer()
        mock_run_command.return_value = (1, "", "Deployment error")
        
        result = await deployer.deploy_function(
            "test", Path("/tmp"), 20, 2, "europe-west1"
        )
        
        assert isinstance(result, DeploymentResult)
        assert result.success is False
        assert result.url is None
        assert "Deployment error" in result.error
        assert result.used_region == "europe-west1"
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.gcp_deployer.run_command_async')
    async def test_delete_function_success(self, mock_run_command):
        """Test successful function deletion."""
        deployer = GCPDeployer()
        mock_run_command.return_value = (0, "Deleted", "")
        
        success, error = await deployer.delete_function("test", "europe-west1")
        
        assert success is True
        assert error is None
        mock_run_command.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.gcp_deployer.run_command_async')
    async def test_check_logs_for_errors_no_errors(self, mock_run_command):
        """Test log checking with no errors."""
        deployer = GCPDeployer()
        mock_run_command.return_value = (0, "Normal log output", "")
        
        success, error = await deployer.check_logs_for_errors("test", "europe-west1")
        
        assert success is True
        assert error is None
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.gcp_deployer.run_command_async')
    async def test_check_logs_for_errors_with_errors(self, mock_run_command):
        """Test log checking with errors."""
        deployer = GCPDeployer()
        mock_run_command.return_value = (0, "ERROR: Something went wrong\nFailed to process", "")
        
        success, error = await deployer.check_logs_for_errors("test", "europe-west1")
        
        assert success is False
        assert error is not None
        assert "ERROR" in error
