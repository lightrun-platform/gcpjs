import logging
from typing import Optional

from .lightrun_api import LightrunAPI
from ..authentication import ApiKeyAuthenticator


class LightrunPublicAPI(LightrunAPI):
    """Client for the Lightrun Public API (using API Keys)."""

    def __init__(self, api_url: str, company_id: str, lightrun_api_key: str, logger: logging.Logger):
        authenticator = ApiKeyAuthenticator(lightrun_api_key)
        super().__init__(api_url, company_id, authenticator, logger)

    def list_agents(self):
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents"
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to fetch agents: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "get agent ID")

    def get_agent(self, display_name: str) -> Optional[str]:
        all_agents = self.list_agents()
        for agent in all_agents:
            if display_name == agent.get("displayName"):
                self.logger.debug(f"Found agent matching display name '{display_name}', agent id: '{agent.get("id")}'. full agents list: '{all_agents}'. ")
                return agent

        self.logger.warning(f"Could not find an agent matching the display name '{display_name}'. full agents list: '{all_agents}'. ")
        return None

    def add_snapshot(
        self,
        agent_id: str,
        agent_pool_id: str,
        filename: str,
        line_number: int,
        max_hit_count: int,
        expire_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Create a snapshot action via the Public API.
        
        Args:
            agent_id: The UUID of the agent to attach the action to.
            agent_pool_id: The agent pool ID.
            filename: Full path to the source file.
            line_number: Line number for the snapshot.
            max_hit_count: Maximum number of times the snapshot can be captured.
            expire_seconds: Action expiration time in seconds (default 3600).
        """
        try:
            url = f"{self.api_url}/api/v1/actions/snapshots"
            snapshot_data = {
                "source": {
                    "id": agent_id,
                    "type": "AGENT"
                },
                "agentPoolId": agent_pool_id,
                "filename": filename,
                "line": line_number,
                "maxHitCount": max_hit_count,
                "expirationSeconds": expire_seconds,
            }
            response = self.authenticator.send_authenticated_request(self.session, 'POST', url, json=snapshot_data, timeout=30)

            if response.status_code in [200, 201]:
                snapshot_id = response.json().get("id")
                self.logger.info(f"Snapshot created: {snapshot_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return snapshot_id
            else:
                self.logger.warning(f"Failed to create snapshot: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "create snapshot")
        return None

    def add_log_action(
        self,
        agent_id: str,
        agent_pool_id: str,
        filename: str,
        line_number: int,
        message: str,
        max_hit_count: int,
        expire_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Create a log action via the Public API.
        
        Args:
            agent_id: The UUID of the agent to attach the action to.
            agent_pool_id: The agent pool ID.
            filename: Full path to the source file.
            line_number: Line number for the log.
            message: Log message format (supports placeholders like "Hello {myVar}").
            max_hit_count: Maximum number of times the log can be triggered.
            expire_seconds: Action expiration time in seconds (default 3600).
        """
        try:
            url = f"{self.api_url}/api/v1/actions/logs"
            log_data = {
                "source": {
                    "id": agent_id,
                    "type": "AGENT"
                },
                "agentPoolId": agent_pool_id,
                "filename": filename,
                "line": line_number,
                "format": message,
                "expirationSeconds": expire_seconds,
            }
            response = self.authenticator.send_authenticated_request(self.session, 'POST', url, json=log_data, timeout=30)

            if response.status_code in [200, 201]:
                action_id = response.json().get("id")
                self.logger.info(f"Log created: {action_id} at {filename}:{line_number}")
                return action_id
            else:
                self.logger.warning(f"Failed to create log: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "create log")
        return None

    def get_snapshot(self, snapshot_id: str, agent_pool_id: str = None) -> Optional[dict]:
        """Get a snapshot action by ID."""
        try:
            url = f"{self.api_url}/api/v1/actions/snapshots/{snapshot_id}"
            params = {}
            if agent_pool_id:
                params['agentPoolId'] = agent_pool_id
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get snapshot {snapshot_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self.logger.exception(f"Error fetching snapshot: {e}")
        return None

    def get_log(self, log_id: str, agent_pool_id: str = None) -> Optional[dict]:
        """Get a log action by ID."""
        try:
            url = f"{self.api_url}/api/v1/actions/logs/{log_id}"
            params = {}
            if agent_pool_id:
                params['agentPoolId'] = agent_pool_id
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get log {log_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self.logger.exception(f"Error fetching log: {e}")
        return None

    def delete_snapshot(self, snapshot_id: str, agent_pool_id: str = None) -> bool:
        """Delete a snapshot action by ID."""
        try:
            url = f"{self.api_url}/api/v1/actions/{snapshot_id}"
            params = {}
            if agent_pool_id:
                params['agentPoolId'] = agent_pool_id
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, params=params, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Snapshot deleted: {snapshot_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete snapshot {snapshot_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "delete snapshot")
        return False

    def delete_log_action(self, log_id: str, agent_pool_id: str = None) -> bool:
        """Delete a log action by ID."""
        try:
            url = f"{self.api_url}/api/v1/actions/{log_id}"
            params = {}
            if agent_pool_id:
                params['agentPoolId'] = agent_pool_id
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, params=params, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Log action deleted: {log_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete log {log_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "delete log")
        return False
