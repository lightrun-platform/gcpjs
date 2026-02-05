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

    def delete_lightrun_action(self, action_id: str, agent_pool_id: str = None) -> bool:
        """Delete any action (snapshot, log, etc.) by its ID."""
        try:
            url = f"{self.api_url}/api/v1/actions/{action_id}"
            params = {}
            if agent_pool_id:
                params['agentPoolId'] = agent_pool_id
            response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, params=params, timeout=10)
            if response.status_code in [200, 204]:
                self.logger.info(f"Action deleted: {action_id}")
                return True
            else:
                self.logger.warning(f"Failed to delete action {action_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error_or_raise(e, "delete action")
        return False

    def list_actions(self, agent_pool_id: str, page: int = 0) -> dict:
        """
        List all actions with pagination.
        
        Uses: GET /api/v1/actions
        
        Args:
            agent_pool_id: The agent pool ID (required).
            page: Page number (0-indexed).
            size: Page size (default 100).
        
        Returns:
            Dict with 'content' (list of actions) and pagination info.
        """
        try:
            url = f"{self.api_url}/api/v1/actions"
            params = {"page": page, "size": LightrunAPI.DEFAULT_PAGE_SIZE, "agentPoolId": agent_pool_id}
            
            response = self.authenticator.send_authenticated_request(self.session, 'GET', url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            self._handle_api_error_or_raise(e, "list actions (Public API)")
        return {"content": [], "last": True}

    def get_actions_by_agent(self, agent_id: str, pool_id: str) -> list:
        """
        Get all actions currently bound to a specific agent.
        
        Note: The Public API doesn't have a direct server-side filter for agent ID,
        so this fetches all actions and filters client-side by matching source.id.
        
        Args:
            agent_id: The agent's UUID.
            pool_id: The agent pool ID (required).
            
        Returns:
            List of actions bound to the specified agent.
        """
        all_agent_actions = []
        page = 0
        
        while True:
            response = self.list_actions(agent_pool_id=pool_id, page=page)
            actions = response.get('content', [])
            
            # Filter actions where source.id matches our agent_id and source.type is AGENT
            for action in actions:
                source = action.get('source', {})
                if source.get('id') == agent_id and source.get('type') == 'AGENT':
                    all_agent_actions.append(action)
            
            # Check if we've reached the last page
            if response.get('last', True):
                break
            page += 1
        
        self.logger.debug(f"Found {len(all_agent_actions)} actions for agent {agent_id}")
        return all_agent_actions

    def clear_agent_actions(self, agent_id: str, pool_id: str) -> int:
        """
        Clear all actions for a specific agent.
        
        Args:
            agent_id: The agent's UUID.
            pool_id: The agent pool ID (required).
            
        Returns:
            Number of actions deleted, or -1 on error.
        """
        try:
            # Get all actions for this agent
            agent_actions = self.get_actions_by_agent(agent_id, pool_id)
            
            if not agent_actions:
                self.logger.info(f"No actions found for agent {agent_id}")
                return 0
            
            action_ids = [action.get('id') for action in agent_actions if action.get('id')]
            
            if not action_ids:
                return 0
            
            self.logger.info(f"Clearing {len(action_ids)} actions from agent {agent_id}")
            
            # Delete each action individually (Public API doesn't have bulk delete)
            deleted_count = 0
            for action_id in action_ids:
                # Use the generic delete endpoint
                try:
                    url = f"{self.api_url}/api/v1/actions/{action_id}"
                    params = {"agentPoolId": pool_id}
                    response = self.authenticator.send_authenticated_request(self.session, 'DELETE', url, params=params, timeout=10)
                    response.raise_for_status()
                    deleted_count += 1

                except Exception as e:
                    self.logger.warning(f"Error deleting action {action_id}: {e}")
            
            self.logger.info(f"Deleted {deleted_count}/{len(action_ids)} actions")
            return deleted_count
            
        except Exception as e:
            self.logger.exception(f"Error clearing agent actions: {e}")
            return -1
