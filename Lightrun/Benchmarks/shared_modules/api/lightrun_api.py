import requests
import logging
from typing import Optional
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from Lightrun.Benchmarks.shared_modules.authentication import Authenticator, InteractiveAuthenticator


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

    def _handle_api_error_or_raise(self, e: Exception, context: str):
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
            raise e

    @abstractmethod
    def list_agents(self):
        pass

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