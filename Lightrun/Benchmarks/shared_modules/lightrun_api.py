import requests
import logging
import json
import base64
from typing import Optional
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from Lightrun.Benchmarks.shared_modules.authenticator import Authenticator, InteractiveAuthenticator


def _get_default_logger():
    logger = logging.getLogger("LightrunAPI")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class LightrunAPI(ABC):
    """Abstract Base Client for interacting with the Lightrun API."""

    def __init__(
        self,
        api_url: str,
        company_id: str,
        authenticator: Authenticator,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Lightrun API client.
        
        Args:
            api_url: Lightrun API URL.
            company_id: Lightrun Company ID.
            authenticator: Authenticator instance.
            logger: Optional logger instance.
        """
        self.api_url = api_url
        if self.api_url.endswith("/"):
             self.api_url = self.api_url[:-1]
             
        self.company_id = company_id
        self.authenticator = authenticator

        if logger:
            self.logger = logger
        else:
            self.logger = _get_default_logger()

        self.session = requests.Session()
        # Add a simple retry adapter
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def _handle_api_error(self, e: Exception, context: str):
        parsed = urlparse(self.api_url)
        hostname = parsed.hostname or "app.lightrun.com"
        
        if isinstance(e, requests.exceptions.ConnectionError) and "NameResolutionError" in str(e):
            self.logger.error(f"DNS RESOLUTION ERROR: Could not resolve '{hostname}'\n" +
                              f"Possible reasons:\n" +
                              f"1. No internet connection or DNS server is down.\n" +
                              f"2. A VPN or Firewall is blocking access to {hostname}.\n" +
                              f"3. You are on a network that doesn't resolve public DNS names correctly.\n" +
                              f"4. The URL '{self.api_url}' is incorrect or missing the scheme (e.g., https://).\n")
        else:
            self.logger.warning(f"Could not {context}: {e}")

        return None

    @abstractmethod
    def get_agent_id(self, display_name: str) -> Optional[str]:
        pass

    @abstractmethod
    def add_snapshot(
        self,
        agent_id: str,
        filename: str,
        line_number: int,
        max_hit_count: int,
        expire_seconds: int = 3600,
    ) -> Optional[str]:
        pass

    @abstractmethod
    def add_log_action(
        self,
        agent_id: str,
        filename: str,
        line_number: int,
        message: str,
        max_hit_count: int,
        expire_seconds: int = 3600,
    ) -> Optional[str]:
        pass

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    def get_log(self, log_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    def delete_snapshot(self, snapshot_id: str) -> bool:
        pass

    @abstractmethod
    def delete_log_action(self, log_id: str) -> bool:
        pass


class LightrunPublicAPI(LightrunAPI):
    """Client for the Lightrun Public API (using API Keys)."""

    def get_agent_id(self, display_name: str) -> Optional[str]:
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents"
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, timeout=30)

            if response.status_code == 200:
                agents = response.json()
                for agent in agents:
                    if display_name in agent.get("displayName", ""):
                        return agent.get("id")
                self.logger.warning(f"No agent found matching display name '{display_name}'")
            else:
                self.logger.warning(f"Failed to fetch agents: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "get agent ID")
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
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots"
            snapshot_data = {
                "agentId": agent_id,
                "filename": filename,
                "lineNumber": line_number,
                "maxHitCount": max_hit_count,
                "expireSec": expire_seconds,
            }
            response = self.authenticator.send_authenticated_request(self.session, 'POST', url, json=snapshot_data, timeout=30)

            if response.status_code in [200, 201]:
                snapshot_id = response.json().get("id")
                self.logger.info(f"Snapshot created: {snapshot_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return snapshot_id
            else:
                self.logger.warning(f"Failed to create snapshot: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "create snapshot")
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
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/logs"
            log_data = {
                "agentId": agent_id,
                "filename": filename,
                "lineNumber": line_number,
                "maxHitCount": max_hit_count,
                "expireSec": expire_seconds,
                "logMessage": message,
            }
            response = self.authenticator.send_authenticated_request(self.session, 'POST', url, json=log_data, timeout=30)

            if response.status_code in [200, 201]:
                action_id = response.json().get("id")
                self.logger.info(f"Log created: {action_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return action_id
            else:
                self.logger.warning(f"Failed to create log: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "create log")
        return None

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching snapshot: {e}")
        return None

    def get_log(self, log_id: str) -> Optional[dict]:
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/logs/{log_id}"
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching log: {e}")
        return None

    def delete_snapshot(self, snapshot_id: str) -> bool:
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Snapshot deleted: {snapshot_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete snapshot {snapshot_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "delete snapshot")
        return False

    def delete_log_action(self, log_id: str) -> bool:
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/logs/{log_id}"
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Log action deleted: {log_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete log {log_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "delete log")
        return False


class LightrunPluginAPI(LightrunAPI):
    """Client for the Lightrun Internal/Plugin API (using User Tokens via Device Flow)."""

    def _get_client_info_header(self, api_version="1.78"):
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
            self.logger.error(f"Error getting default agent pool: {e}")
        return None

    def _list_agents_flat(self, pool_id: str, api_version="1.78") -> list:
        agents = []
        try:
            url = f"{self.api_url}/athena/company/{self.company_id}/agent-pools/{pool_id}/{api_version}/agentsFlat"
            headers = {"client-info": self._get_client_info_header(api_version)}
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
             self.logger.error(f"Error listing agents flat: {e}")
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
                headers = {"client-info": self._get_client_info_header(api_version)}
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
                headers = {"client-info": self._get_client_info_header(api_version)}
                
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
             headers = {"client-info": self._get_client_info_header(api_version)}
             response = self.authenticator.send_authenticated_request(self.session, 'GET', url, headers=headers, timeout=10)
             if response.status_code == 200:
                 return response.json()
             else:
                 self.logger.warning(f"Failed to get snapshot (Internal): {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error fetching snapshot: {e}")
        return None

    def get_log(self, log_id: str) -> Optional[dict]:
        # Same as get_snapshot, assuming getAction works for Logs too
        return self.get_snapshot(log_id)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        try:
             # deleteAction: /athena/company/{company}/{apiVersion}/deleteAction/{actionId}
             api_version = "1.78"
             url = f"{self.api_url}/athena/company/{self.company_id}/{api_version}/deleteAction/{snapshot_id}"
             headers = {"client-info": self._get_client_info_header(api_version)}
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
