"""Authentication strategies for Lightrun."""

import requests
from abc import ABC, abstractmethod
from typing import Dict


class Authenticator(ABC):
    """Abstract base class for authentication strategies."""
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Return the authorization headers."""
        pass
    
    @abstractmethod
    def send_authenticated_request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
         """Send an authenticated request, handling retries if necessary."""
         pass


