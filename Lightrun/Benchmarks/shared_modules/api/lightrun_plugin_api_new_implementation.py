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


class LightrunPluginAPINewImplementation(LightrunAPI):
    """Client for the Lightrun Internal/Plugin API (using User Tokens via Device Flow)."""

    def __init__(self, api_url, company_id, api_version, logger):
        authenticator = InteractiveAuthenticator(api_url, company_id, logger)
        super().__init__(api_url, company_id, authenticator, logger)
        self.api_version = api_version

    def _get_default_agent_pool(self) -> Optional[str]:
        pass

    def list_agents(self):
        pass

    def get_agent_id(self, display_name: str) -> Optional[str]:
        pass

    def add_snapshot(
            self,
            agent_id: str,
            filename: str,
            line_number: int,
            max_hit_count: int,
            expire_seconds: int = 3600,
    ) -> Optional[str]:
        pass

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

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        pass

    def get_log(self, log_id: str) -> Optional[dict]:
        pass

    def delete_snapshot(self, snapshot_id: str) -> bool:
        pass

    def delete_log_action(self, log_id: str) -> bool:
        pass
