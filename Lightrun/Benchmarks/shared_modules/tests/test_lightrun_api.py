
import unittest
from unittest.mock import Mock, patch, ANY
import sys
from pathlib import Path
import json
import base64

# Add parent directory to path
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.api import LightrunAPI, LightrunPublicAPI, LightrunPluginAPI, get_client_info_header
from Lightrun.Benchmarks.shared_modules.authentication import Authenticator, InteractiveAuthenticator

class TestLightrunAPI(unittest.TestCase):
    
    def setUp(self):
        self.api_url = "https://app.lightrun.com"
        self.company_id = "test-company-id"
        self.mock_auth = Mock(spec=Authenticator)
    
    def test_abc_instantiation_fails(self):
        with self.assertRaises(TypeError):
            LightrunAPI(self.api_url, self.company_id, self.mock_auth, Mock())

class TestLightrunPublicAPI(unittest.TestCase):
    
    def setUp(self):
        self.api_url = "https://app.lightrun.com"
        self.company_id = "test-company"
        self.mock_auth = Mock(spec=Authenticator)
        self.mock_logger = Mock()
        self.api = LightrunPublicAPI(self.api_url, self.company_id, self.mock_auth, logger=self.mock_logger)
        self.mock_session = self.api.session # Actually we mock session passed to send_authenticated_request

    def test_get_agent_id_success(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"id": "agent-1", "displayName": "foo-agent"},
            {"id": "agent-2", "displayName": "target-agent"}
        ]
        self.mock_auth.send_authenticated_request.return_value = mock_resp
        
        agent_id = self.api.get_agent("target-agent")
        self.assertEqual(agent_id, "agent-2")
        self.mock_auth.send_authenticated_request.assert_called_with(
            ANY, 'GET', 
            f"{self.api_url}/api/v1/companies/{self.company_id}/agents", 
            timeout=30
        )

    def test_add_snapshot(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "snap-123"}
        self.mock_auth.send_authenticated_request.return_value = mock_resp
        
        snap_id = self.api.add_snapshot("agent-1", "index.js", 10, 1)
        self.assertEqual(snap_id, "snap-123")
        
        self.mock_auth.send_authenticated_request.assert_called_with(
            ANY, 'POST',
            f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots",
            json={
                "agentId": "agent-1",
                "filename": "index.js",
                "lineNumber": 10,
                "maxHitCount": 1,
                "expireSec": 3600
            },
            timeout=30
        )

class TestLightrunPluginAPI(unittest.TestCase):
    
    def setUp(self):
        self.api_url = "https://app.lightrun.com"
        self.company_id = "test-company"
        self.mock_auth = Mock(spec=InteractiveAuthenticator)
        self.mock_logger = Mock()
        self.api = LightrunPluginAPI(self.api_url, self.company_id, self.mock_auth, api_version="1.78", logger=self.mock_logger)

    def test_get_client_info_header(self):
        header = get_client_info_header("1.78")
        decoded = base64.b64decode(header).decode('utf-8')
        info = json.loads(decoded)
        self.assertEqual(info['ideInfoDTO']['pluginVersion'], "1.78.0")
        self.assertEqual(info['eventSource'], "IDE")

    def test_custom_api_version(self):
        api = LightrunPluginAPI(self.api_url, self.company_id, self.mock_auth, api_version="2.0", logger=self.mock_logger)
        self.assertEqual(api.api_version, "2.0")
        
        # Test usage in get_client_info_header via a method call (e.g. implicitly used in list_agents)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": "a1", "name": "foo"}]
        self.mock_auth.send_authenticated_request.return_value = mock_resp
        
        # Mock default pool to avoid its call
        with patch.object(api, '_get_default_agent_pool', return_value="pool-1"):
            api.list_agents()
            
        call_args = self.mock_auth.send_authenticated_request.call_args
        headers = call_args.kwargs.get('headers', {})
        client_info = headers.get('client-info')
        decoded = base64.b64decode(client_info).decode('utf-8')
        info = json.loads(decoded)
        # Should reflect 2.0
        self.assertEqual(info['ideInfoDTO']['pluginVersion'], "2.0.0")

    def test_get_default_agent_pool(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "pool-default"}
        self.mock_auth.send_authenticated_request.return_value = mock_resp
        
        pool_id = self.api.get_default_agent_pool()
        self.assertEqual(pool_id, "pool-default")
        self.mock_auth.send_authenticated_request.assert_called_with(
            ANY, 'GET',
            f"{self.api_url}/api/company/{self.company_id}/agent-pools/default"
        )

    def test_list_agents_flat(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": "agent-x", "name": "foo"}]
        self.mock_auth.send_authenticated_request.return_value = mock_resp
        
        agents = self.api._get_agents_in_pool("pool-1")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]['id'], "agent-x")
        
        # Verify client-info header
        call_args = self.mock_auth.send_authenticated_request.call_args
        headers = call_args.kwargs.get('headers', {})
        self.assertIn('client-info', headers)

    def test_get_agent_id_strict_success(self):
        mock_agents = [
            {"id": "id-1", "displayName": "my-func-gen1"},
            {"id": "id-2", "displayName": "other-func"}
        ]
        with patch.object(self.api, 'list_agents', return_value=mock_agents):
            agent_id = self.api.get_agent("my-func")
            self.assertEqual(agent_id, "id-1")

    def test_get_agent_id_strict_missing_id(self):
        # Case where displayName matches but 'id' is missing
        mock_agents = [
            {"displayName": "my-func-gen1"} # No id
        ]
        with patch.object(self.api, 'list_agents', return_value=mock_agents):
            with self.assertRaises(ValueError) as cm:
                self.api.get_agent("my-func")
            self.assertIn("has no 'id' field", str(cm.exception))

    def test_add_snapshot_internal(self):
        # Mock sequence: get_default_pool -> send POST
        
        # Setup mocks
        pool_resp = Mock()
        pool_resp.status_code = 200
        pool_resp.json.return_value = {"id": "pool-1"}
        
        snap_resp = Mock()
        snap_resp.status_code = 200
        snap_resp.json.return_value = {"id": "snap-internal-1"}
        
        self.mock_auth.send_authenticated_request.side_effect = [pool_resp, snap_resp]
        
        snap_id = self.api.add_snapshot("agent-1", "index.js", 10, 1)
        
        self.assertEqual(snap_id, "snap-internal-1")
        
        # Verify POST call structure
        self.assertEqual(self.mock_auth.send_authenticated_request.call_count, 2)
        post_call = self.mock_auth.send_authenticated_request.call_args_list[1]
        
        args, kwargs = post_call
        url = args[2]
        self.assertIn("/insertCapture/**", url)
        self.assertIn(f"/{self.api.api_version}/insertCapture", url) # Should use default 1.78
        self.assertIn("agentPoolId", kwargs['json'])
        self.assertEqual(kwargs['json']['agentPoolId'], "pool-1")
        self.assertIn('client-info', kwargs['headers'])

if __name__ == '__main__':
    unittest.main()
