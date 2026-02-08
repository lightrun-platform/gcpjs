
import requests
import logging
from typing import Dict

from .authenticator import Authenticator
from .credentials import Credentials


class InteractiveAuthenticator(Authenticator):
    """Authenticates using the Device Authorization Flow (OAuth 2.0)."""

    DEFAULT_HEADERS = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def __init__(self, api_url: str, company_id: str, logger: logging.Logger):
        self.api_url = api_url
        self.company_id = company_id
        self.logger = logger
        self.session = requests.Session()
        self._credentials = Credentials(logger, api_url, company_id)

    def get_headers(self, **kwargs) -> Dict[str, str]:
        headers = {**InteractiveAuthenticator.DEFAULT_HEADERS}
        auth_token = self._credentials.get_access_token()
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        override_headers = kwargs.pop('override_headers', {})
        return {**headers, **override_headers}

    def send_authenticated_request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        headers = self.get_headers(**kwargs)
        return session.request(method, url, headers=headers, **kwargs)
