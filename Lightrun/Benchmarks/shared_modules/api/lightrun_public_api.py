from typing import Optional

from Benchmarks.shared_modules.api.lightrun_api import LightrunAPI


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
