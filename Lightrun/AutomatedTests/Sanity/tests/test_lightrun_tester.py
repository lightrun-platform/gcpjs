"""Tests for LightrunTester class."""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import from package
from gcp_function_tests.lightrun_tester import LightrunTester


class TestLightrunTester:
    """Tests for LightrunTester class."""
    
    @patch('requests.get')
    def test_get_agent_id_success(self, mock_get):
        """Test successful agent ID retrieval."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "agent-1", "displayName": "test-node20-gen2"},
            {"id": "agent-2", "displayName": "other-function"}
        ]
        mock_get.return_value = mock_response
        
        agent_id = tester.get_agent_id("test-node20-gen2")
        
        assert agent_id == "agent-1"
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_get_agent_id_not_found(self, mock_get):
        """Test agent ID not found."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "agent-1", "displayName": "other-function"}
        ]
        mock_get.return_value = mock_response
        
        agent_id = tester.get_agent_id("test-node20-gen2")
        
        assert agent_id is None
    
    def test_get_agent_id_no_credentials(self):
        """Test agent ID retrieval without credentials."""
        tester = LightrunTester(api_key="", company_id="")
        
        agent_id = tester.get_agent_id("test-function")
        
        assert agent_id is None
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.lightrun_tester.PerformanceTester.invoke_function')
    @patch('requests.get')
    @patch('requests.post')
    async def test_test_snapshot_success(self, mock_post, mock_get, mock_invoke):
        """Test successful snapshot test."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        
        # Mock snapshot creation
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"id": "snapshot-1"}
        mock_post.return_value = mock_post_response
        
        # Mock snapshot check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"hitCount": 1}
        mock_get.return_value = mock_get_response
        
        mock_invoke.return_value = (True, 100.0, None)
        
        success, error = await tester.test_snapshot("test-function", "https://test.com", "agent-1")
        
        assert success is True
        assert error is None
        mock_post.assert_called_once()
        mock_invoke.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_test_snapshot_creation_failed(self, mock_post):
        """Test snapshot test with creation failure."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        
        mock_post_response = MagicMock()
        mock_post_response.status_code = 400
        mock_post_response.text = "Bad Request"
        mock_post.return_value = mock_post_response
        
        success, error = await tester.test_snapshot("test-function", "https://test.com", "agent-1")
        
        assert success is False
        assert "400" in error
        assert "Bad Request" in error
    
    @pytest.mark.asyncio
    async def test_test_snapshot_no_agent_id(self):
        """Test snapshot test without agent ID."""
        tester = LightrunTester()
        
        success, error = await tester.test_snapshot("test-function", "https://test.com", None)
        
        assert success is False
        assert "Agent ID not found" in error
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.lightrun_tester.PerformanceTester.invoke_function')
    @patch('requests.get')
    @patch('requests.post')
    async def test_test_counter_success(self, mock_post, mock_get, mock_invoke):
        """Test successful counter test."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        
        # Mock counter creation
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"id": "counter-1"}
        mock_post.return_value = mock_post_response
        
        # Mock counter check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"hitCount": 5}
        mock_get.return_value = mock_get_response
        
        mock_invoke.return_value = (True, 100.0, None)
        
        success, error = await tester.test_counter("test-function", "https://test.com", "agent-1")
        
        assert success is True
        assert error is None
        assert mock_invoke.call_count == 5  # Called 5 times
    
    @pytest.mark.asyncio
    @patch('gcp_function_tests.lightrun_tester.PerformanceTester.invoke_function')
    @patch('requests.get')
    @patch('requests.post')
    async def test_test_metric_success(self, mock_post, mock_get, mock_invoke):
        """Test successful metric test."""
        tester = LightrunTester(api_key="test-key", company_id="test-company")
        
        # Mock metric creation
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"id": "metric-1"}
        mock_post.return_value = mock_post_response
        
        # Mock metric check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"data": [1, 2, 3]}
        mock_get.return_value = mock_get_response
        
        mock_invoke.return_value = (True, 100.0, None)
        
        success, error = await tester.test_metric("test-function", "https://test.com", "agent-1")
        
        assert success is True
        assert error is None
        assert mock_invoke.call_count == 5  # Called 5 times
