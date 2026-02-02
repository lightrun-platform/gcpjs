import requests
import logging
from typing import Optional
from urllib.parse import urlparse
from Lightrun.Benchmarks.shared_modules.authenticator import Authenticator


def _get_default_logger():
    logger = logging.getLogger("LightrunAPI")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class LightrunAPI:
    """Client for interacting with the Lightrun API to manage actions."""

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


    def get_agent_id(self, display_name: str) -> Optional[str]:

        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents"
            # Using send_authenticated_request instead of session.get
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
