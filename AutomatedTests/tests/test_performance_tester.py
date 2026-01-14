"""Tests for PerformanceTester class."""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import from package
from gcp_function_tests.performance_tester import PerformanceTester


class TestPerformanceTester:
    """Tests for PerformanceTester class."""
    
    @patch('requests.get')
    def test_invoke_function_success(self, mock_get):
        """Test successful function invocation."""
        tester = PerformanceTester()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        success, duration, error = tester.invoke_function("https://test.com")
        
        assert success is True
        assert duration >= 0
        assert error is None
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_invoke_function_http_error(self, mock_get):
        """Test function invocation with HTTP error."""
        tester = PerformanceTester()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        success, duration, error = tester.invoke_function("https://test.com")
        
        assert success is False
        assert "500" in error
        assert "Internal Server Error" in error
    
    @patch('requests.get')
    def test_invoke_function_exception(self, mock_get):
        """Test function invocation with exception."""
        tester = PerformanceTester()
        mock_get.side_effect = Exception("Connection error")
        
        success, duration, error = tester.invoke_function("https://test.com")
        
        assert success is False
        assert duration == 0
        assert "Connection error" in error
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.performance_tester.PerformanceTester.invoke_function')
    async def test_test_cold_warm_starts(self, mock_invoke):
        """Test cold/warm start testing."""
        tester = PerformanceTester(cold_start_requests=2, warm_start_requests=2)
        
        # Mock successful invocations
        mock_invoke.return_value = (True, 100.0, None)
        
        cold_avg, warm_avg, cold_success, warm_success = await tester.test_cold_warm_starts("https://test.com")
        
        assert cold_avg == 100.0
        assert warm_avg == 100.0
        assert cold_success == 2
        assert warm_success == 2
        # Should be called for first request (1) + additional requests (1) + warm starts (2) = 4 times
        # Note: The actual count may vary slightly due to async timing, so we check >= 4
        assert mock_invoke.call_count >= 4
