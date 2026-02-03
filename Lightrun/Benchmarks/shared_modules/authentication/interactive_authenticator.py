
import requests
import logging
from typing import Dict

from .authenticator import Authenticator
from .credentials import Credentials


class InteractiveAuthenticator(Authenticator):
    """Authenticates using the Device Authorization Flow (OAuth 2.0)."""

    def __init__(self, api_url: str, company_id: str, logger: logging.Logger):
        self.api_url = api_url
        self.company_id = company_id
        self.logger = logger
        self.session = requests.Session()
        self._credentials = Credentials(logger, api_url, company_id)

    def get_headers(self) -> Dict[str, str]:
        auth_token = self._credentials.get_access_token()
        if not auth_token:
            return {}
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def send_authenticated_request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        auth_token = self._credentials.get_access_token()

        # Prepare headers
        headers = kwargs.pop('headers', {})
        headers["Content-Type"] = "application/json"
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        return session.request(method, url, headers=headers, **kwargs)
