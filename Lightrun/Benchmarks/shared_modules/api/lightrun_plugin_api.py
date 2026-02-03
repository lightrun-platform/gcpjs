from .lightrun_api import LightrunAPI
import json
import base64
from typing import Optional
from Lightrun.Benchmarks.shared_modules.authentication import Authenticator, InteractiveAuthenticator


def get_client_info_header(api_version="1.78"):
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

    def _list_agents_flat(self, pool_id: str, api_version="1.78") -> list:
        agents = []
        try:
            url = f"{self.api_url}/athena/company/{self.company_id}/agent-pools/{pool_id}/{api_version}/agentsFlat"
            headers = {"client-info": get_client_info_header(api_version)}
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

    def get_agent_id(self, display_name: str) -> Optional[str]:
        try:
            pool_id = self._get_default_agent_pool()
            if pool_id:
                agents = self._list_agents_flat(pool_id)
                for agent in agents:
                    a_name = agent.get("name") or agent.get("displayName") or ""
                    if display_name in a_name:
                        return agent.get("id") or agent.get("agentId")
            self.logger.warning(f"No agent found matching display name '{display_name}' via Plugin API")
        except Exception as e:
            self._handle_api_error(e, "get agent ID (Internal)")
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
            api_version = "1.78"
            pool_id = self._get_default_agent_pool()
            if pool_id:
                url = f"{self.api_url}/athena/company/{self.company_id}/{api_version}/insertCapture/**"
                headers = {"client-info": get_client_info_header(api_version)}
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
            self._handle_api_error(e, "create snapshot (Internal)")
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
            api_version = "1.78"
            pool_id = self._get_default_agent_pool()
            if pool_id:
                url = f"{self.api_url}/athena/company/{self.company_id}/{api_version}/insertLog/**"
                headers = {"client-info": get_client_info_header(api_version)}

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
            self._handle_api_error(e, "create log (Internal)")
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
            api_version = "1.78"
            url = f"{self.api_url}/athena/company/{self.company_id}/{api_version}/getAction/{snapshot_id}"
            headers = {"client-info": get_client_info_header(api_version)}
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
            api_version = "1.78"
            url = f"{self.api_url}/athena/company/{self.company_id}/{api_version}/deleteAction/{snapshot_id}"
            headers = {"client-info": get_client_info_header(api_version)}
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, headers=headers, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Snapshot deleted (Internal): {snapshot_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete snapshot (Internal): {response.status_code}")
        except Exception as e:
            self._handle_api_error(e, "delete snapshot (Internal)")
        return False

    def delete_log_action(self, log_id: str) -> bool:
        return self.delete_snapshot(log_id)
