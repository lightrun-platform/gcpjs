"""Lightrun API client for managing actions (snapshots, breakpoints)."""

import os
import requests
import socket
from typing import Optional
from urllib.parse import urlparse
from urllib3.exceptions import NameResolutionError


class LightrunAPI:
    """Client for interacting with the Lightrun API to manage actions."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        company_id: Optional[str] = None,
    ):
        """
        Initialize the Lightrun API client.

        Args:
            api_url: Lightrun API URL (default: from LIGHTRUN_API_URL env var or https://app.lightrun.com)
            api_key: Lightrun API key (default: from LIGHTRUN_API_KEY env var)
            company_id: Lightrun Company ID (default: from LIGHTRUN_COMPANY_ID env var)
        """
        self.api_url = api_url or os.environ.get("LIGHTRUN_API_URL", "https://app.lightrun.com")
        self.api_key = api_key or os.environ.get("LIGHTRUN_API_KEY", "")
        self.company_id = company_id or os.environ.get("LIGHTRUN_COMPANY_ID", "")
        self.session = requests.Session()
        # Add a simple retry adapter
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def _get_headers(self) -> dict:
        """Get the authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_agent_id(self, display_name: str) -> Optional[str]:
        """
        Get the Lightrun agent ID for a function by its display name.

        Args:
            display_name: The display name of the function (set via DISPLAY_NAME env var).

        Returns:
            The agent ID if found, otherwise None.
        """
        if not self.api_key or not self.company_id:
            print("    Warning: Lightrun API credentials not configured, skipping agent lookup.")
            return None

        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents"
            response = self.session.get(url, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                agents = response.json()
                for agent in agents:
                    if display_name in agent.get("displayName", ""):
                        return agent.get("id")
                print(f"    Warning: No agent found matching display name '{display_name}'")
            else:
                print(f"    Warning: Failed to fetch agents: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "get agent ID")
        return None

    def _handle_api_error(self, e: Exception, context: str):
        """Handle and diagnose API errors, specifically DNS issues."""
        parsed = urlparse(self.api_url)
        hostname = parsed.hostname or "app.lightrun.com"
        
        if isinstance(e, requests.exceptions.ConnectionError) and "NameResolutionError" in str(e):
            print(f"    ❌ DNS RESOLUTION ERROR: Could not resolve '{hostname}'")
            print(f"    This error is occurring on your LOCAL MACHINE, not inside the Cloud Function.")
            print(f"    Possible reasons:")
            print(f"    1. No internet connection or DNS server is down.")
            print(f"    2. A VPN or Firewall is blocking access to {hostname}.")
            print(f"    3. You are on a network that doesn't resolve public DNS names correctly.")
            print(f"    4. The URL '{self.api_url}' is incorrect or missing the scheme (e.g., https://).")
            print(f"    Try running: 'ping {hostname}' or 'nslookup {hostname}' in your terminal.")
            
            # Additional socket-level check
            try:
                socket.getaddrinfo(hostname, 443)
            except Exception as se:
                 print(f"    (Socket diagnostic: {se})")
        else:
            print(f"    Warning: Could not {context}: {e}")

        return None

    def add_snapshot(
        self,
        agent_id: str,
        filename: str,
        line_number: int,
        max_hit_count: int,
        expire_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Add a snapshot (breakpoint) to an agent.

        Args:
            agent_id: The ID of the agent to add the snapshot to.
            filename: The source filename (e.g., 'helloLightrun.js').
            line_number: The line number for the snapshot.
            max_hit_count: Maximum number of times the snapshot should be hit.
            expire_seconds: How long the snapshot should live (default: 3600 seconds / 1 hour).

        Returns:
            The snapshot ID if created successfully, otherwise None.
        """
        if not self.api_key or not self.company_id:
            print("    Warning: Lightrun API credentials not configured, skipping snapshot creation.")
            return None

        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots"
            snapshot_data = {
                "agentId": agent_id,
                "filename": filename,
                "lineNumber": line_number,
                "maxHitCount": max_hit_count,
                "expireSec": expire_seconds,
            }
            response = self.session.post(url, json=snapshot_data, headers=self._get_headers(), timeout=30)

            if response.status_code in [200, 201]:
                snapshot_id = response.json().get("id")
                print(f"    ✓ Snapshot created: {snapshot_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return snapshot_id
            else:
                print(f"    Warning: Failed to create snapshot: {response.status_code} - {response.text}")
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
        """
        Add a log action to an agent.

        Args:
            agent_id: The ID of the agent to add the log to.
            filename: The source filename (e.g., 'helloLightrun.js').
            line_number: The line number for the log.
            message: The message to log (format string).
            max_hit_count: Maximum number of times the log should be hit.
            expire_seconds: How long the log should live (default: 3600 seconds / 1 hour).

        Returns:
            The action ID if created successfully, otherwise None.
        """
        if not self.api_key or not self.company_id:
            print("    Warning: Lightrun API credentials not configured, skipping log creation.")
            return None

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
            response = self.session.post(url, json=log_data, headers=self._get_headers(), timeout=30)

            if response.status_code in [200, 201]:
                action_id = response.json().get("id")
                print(f"    ✓ Log created: {action_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return action_id
            else:
                print(f"    Warning: Failed to create log: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "create log")

        return None

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        """Get snapshot details."""
        if not self.api_key or not self.company_id:
            return None
            
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching snapshot: {e}")
        return None

    def get_log(self, log_id: str) -> Optional[dict]:
        """Get log details."""
        if not self.api_key or not self.company_id:
            return None
            
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/logs/{log_id}"
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching log: {e}")
        return None

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID."""
        if not self.api_key or not self.company_id:
            return False

        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/snapshots/{snapshot_id}"
            response = self.session.delete(url, headers=self._get_headers(), timeout=10)
            if response.status_code in [200, 204]:
                print(f"    ✓ Snapshot deleted: {snapshot_id}")
                return True
            else:
                print(f"    Warning: Failed to delete snapshot {snapshot_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "delete snapshot")
        return False

    def delete_log_action(self, log_id: str) -> bool:
        """Delete a log action by ID."""
        if not self.api_key or not self.company_id:
            return False

        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/actions/logs/{log_id}"
            response = self.session.delete(url, headers=self._get_headers(), timeout=10)
            if response.status_code in [200, 204]:
                print(f"    ✓ Log action deleted: {log_id}")
                return True
            else:
                print(f"    Warning: Failed to delete log {log_id}: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_api_error(e, "delete log")
        return False
