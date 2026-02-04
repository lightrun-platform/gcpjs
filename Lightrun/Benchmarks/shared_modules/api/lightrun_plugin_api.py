from .lightrun_api import LightrunAPI
import json
import base64
from typing import Optional
from Lightrun.Benchmarks.shared_modules.authentication import Authenticator, InteractiveAuthenticator


def get_client_info_header(api_version: str):
    info = {
        "eventSource": "IDE",
        "os": "darwin",
        "ideInfoDTO": {
            "name": "Visual Studio Code",
            "version": "1.90.0",
            "theme": "Dark",
            "pluginVersion": f"{api_version}.0",
            "ecosystem": "vscode"
        }
    }
    json_str = json.dumps(info)
    return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')


class LightrunPluginAPI(LightrunAPI):
    """Client for the Lightrun Internal/Plugin API (using User Tokens via Device Flow)."""
    
    def __init__(self, api_url, company_id, api_version, logger):
        authenticator = InteractiveAuthenticator(api_url, company_id, logger)
        super().__init__(api_url, company_id, authenticator, logger)
        self.api_version = api_version

    def _get_default_agent_pool(self) -> Optional[str]:
        try:
            url = f"{self.api_url}/api/company/{self.company_id}/agent-pools/default"
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url)
            if response.status_code == 200:
                return response.json().get('id')
            else:
                # Fallback: List all pools
                self.logger.warning(f"Failed to get default pool: {response.text}, trying list")
                url_all = f"{self.api_url}/api/company/{self.company_id}/agent-pools"
                resp_all = self.authenticator.send_authenticated_request(self.session, 'GET', url_all)
                if resp_all.status_code == 200:
                    pools = resp_all.json().get('content', [])
                    if pools:
                        return pools[0]['id']
        except Exception as e:
            self.logger.exception(f"Error getting default agent pool: {e}")
        return None

    def _list_agents_flat(self, pool_id: str) -> list:
        agents = []
        try:
            url = f"{self.api_url}/athena/company/{self.company_id}/agent-pools/{pool_id}/{self.api_version}/agentsFlat"
            headers = {"client-info": get_client_info_header(self.api_version)}
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    agents = data
                elif isinstance(data, dict) and 'content' in data:
                    agents = data['content']
            else:
                self.logger.warning(f"Failed to list agents flat: {response.status_code}")
        except Exception as e:
            self.logger.exception(f"Error listing agents flat: {e}")
        return agents

    def list_agents(self):
        try:
            pool_id = self._get_default_agent_pool()
            if not pool_id:
                raise Exception("No default agent pool found")
            return self._list_agents_flat(pool_id)
        except Exception as e:
            self._handle_api_error_or_raise(e, "get agent ID (Internal)")
        return None

    def get_agent_id(self, display_name: str) -> Optional[str]:
        try:
            agents = self.list_agents()
            if agents:
                for agent in agents:
                    # Strict extraction: matched displayName -> return id
                    # We expect 'id' and 'displayName' based on AgentDTO
                    current_name = agent.get("displayName")
                    current_id = agent.get("id")
                    
                    if current_name and display_name in current_name:
                        if current_id:
                            return current_id
                        else:
                            raise ValueError(f"Found agent matching '{display_name}' but it has no 'id' field: {agent}")
                
            self.logger.warning(f"No agent found matching display name '{display_name}' via Plugin API. Agents count: {len(agents) if agents else 0}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "get agent ID (Internal)")
        return None

    def add_snapshot(
            self,
            agent_id: str,
            filename: str,
            line_number: int,
            max_hit_count: int,
            expire_seconds: int = 3600,
    ) -> Optional[str]:
        try:
            pool_id = self._get_default_agent_pool()
            if pool_id:
                url = f"{self.api_url}/athena/company/{self.company_id}/{self.api_version}/insertCapture/**"
                headers = {"client-info": get_client_info_header(self.api_version)}
                snapshot_data = {
                    "actionType": "CAPTURE",
                    "agentId": agent_id,
                    "agentPoolId": pool_id,
                    "filename": filename,
                    "line": line_number,
                    "maxHitCount": max_hit_count,
                    "captureActionExtensionDTO": {
                        "contextExpressions": {},
                        "watchExpressions": []
                    },
                    "pipingStatus": "NOT_SET",
                    "disabled": False
                }

                response = self.authenticator.send_authenticated_request(
                    self.session, 'POST', url, json=snapshot_data, headers=headers, timeout=30
                )

                if response.status_code in [200, 201]:
                    snapshot_id = response.json().get("id")
                    self.logger.info(f"Snapshot created (Internal): {snapshot_id} at {filename}:{line_number}")
                    return snapshot_id
                else:
                    self.logger.warning(f"Failed to create snapshot (Internal): {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "create snapshot (Internal)")
        return None

    def add_log_action(
            self,
            agent_id: str,
            filename: str,
            line_number: int,
            message: str,
            max_hit_count: int,
            expire_seconds: int = 3600,
    ) -> Optional[str]:
        try:
            pool_id = self._get_default_agent_pool()
            if pool_id:
                url = f"{self.api_url}/athena/company/{self.company_id}/{self.api_version}/insertLog/**"
                headers = {"client-info": get_client_info_header(self.api_version)}

                log_data = {
                    "actionType": "LOG",
                    "agentId": agent_id,
                    "agentPoolId": pool_id,
                    "filename": filename,
                    "line": line_number,
                    "maxHitCount": max_hit_count,
                    "logActionExtensionDTO": {
                        "logMessage": message
                    },
                    "pipingStatus": "NOT_SET",
                    "disabled": False
                }

                response = self.authenticator.send_authenticated_request(
                    self.session, 'POST', url, json=log_data, headers=headers, timeout=30
                )

                if response.status_code in [200, 201]:
                    action_id = response.json().get("id")
                    self.logger.info(f"Log created (Internal): {action_id} at {filename}:{line_number}")
                    return action_id
                else:
                    self.logger.warning(f"Failed to create log (Internal): {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "create log (Internal)")
        return None

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        try:
            # Fallback to Public API for retrieval if Internal doesn't have easy GET endpoint or same endpoint works
            # The actions endpoint often works with user tokens for READ, just not WRITE?
            # Let's try standard Public API first, if fails we might need internal.
            # But wait, we determined Public API agents endpoint failed.
            # So we likely need internal GET endpoints.
            # Plugin uses: getAction or getActions.
            # getAction: /athena/company/{company}/{apiVersion}/getAction/{actionId}
            url = f"{self.api_url}/athena/company/{self.company_id}/{self.api_version}/getAction/{snapshot_id}"
            headers = {"client-info": get_client_info_header(self.api_version)}
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get snapshot (Internal): {response.status_code}")
        except Exception as e:
            self.logger.exception(f"Error fetching snapshot: {e}")
        return None

    def get_log(self, log_id: str) -> Optional[dict]:
        # Same as get_snapshot, assuming getAction works for Logs too
        return self.get_snapshot(log_id)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        try:
            # deleteAction: /athena/company/{company}/{apiVersion}/deleteAction/{actionId}
            url = f"{self.api_url}/athena/company/{self.company_id}/{self.api_version}/deleteAction/{snapshot_id}"
            headers = {"client-info": get_client_info_header(self.api_version)}
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, headers=headers, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Snapshot deleted (Internal): {snapshot_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete snapshot (Internal): {response.status_code}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "delete snapshot (Internal)")
        return False

    def delete_log_action(self, log_id: str) -> bool:
        return self.delete_snapshot(log_id)
