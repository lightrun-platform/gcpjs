"""Lightrun API client for managing actions (snapshots, breakpoints)."""

import os
import requests
from typing import Optional


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
            api_url: Lightrun API URL (default: from LIGHTRUN_API_URL env var or https://api.lightrun.com)
            api_key: Lightrun API key (default: from LIGHTRUN_API_KEY env var)
            company_id: Lightrun Company ID (default: from LIGHTRUN_COMPANY_ID env var)
        """
        self.api_url = api_url or os.environ.get("LIGHTRUN_API_URL", "https://api.lightrun.com")
        self.api_key = api_key or os.environ.get("LIGHTRUN_API_KEY", "")
        self.company_id = company_id or os.environ.get("LIGHTRUN_COMPANY_ID", "")

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
            response = requests.get(url, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                agents = response.json()
                for agent in agents:
                    if display_name in agent.get("displayName", ""):
                        return agent.get("id")
                print(f"    Warning: No agent found matching display name '{display_name}'")
            else:
                print(f"    Warning: Failed to fetch agents: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"    Warning: Could not get agent ID: {e}")

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
            response = requests.post(url, json=snapshot_data, headers=self._get_headers(), timeout=30)

            if response.status_code in [200, 201]:
                snapshot_id = response.json().get("id")
                print(f"    ✓ Snapshot created: {snapshot_id} at {filename}:{line_number} (maxHits={max_hit_count})")
                return snapshot_id
            else:
                print(f"    Warning: Failed to create snapshot: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"    Warning: Error creating snapshot: {e}")

        return None
