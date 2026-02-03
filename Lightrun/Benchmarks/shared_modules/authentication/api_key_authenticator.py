from typing import Dict

import requests

from .authenticator import Authenticator


class ApiKeyAuthenticator(Authenticator):
    """Authenticates using a static API key."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def send_authenticated_request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        # Inject standard headers
        headers = kwargs.pop('headers', {})
        headers.update(self.get_headers())

        return session.request(method, url, headers=headers, **kwargs)


