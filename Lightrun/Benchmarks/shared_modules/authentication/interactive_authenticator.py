
import os
import requests
import logging
import time
import json
import webbrowser
from pathlib import Path
from typing import Optional, Dict

from .authenticator import Authenticator


class InteractiveAuthenticator(Authenticator):
    """Authenticates using the Device Authorization Flow (OAuth 2.0)."""

    TOKEN_CACHE_DIR = Path.home() / ".lightrun_benchmark"
    TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / "token.json"

    def __init__(self, api_url: str, company_id: str, logger: logging.Logger):
        self.api_url = api_url
        self.company_id = company_id
        self.logger = logger
        self.session = requests.Session()

    def get_headers(self) -> Dict[str, str]:
        # NOTE: This method is now secondary to send_authenticated_request but kept for interface compatibility
        auth_token = self._get_valid_token()
        if not auth_token:
            return {}
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def send_authenticated_request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        # 1. Get current valid token (validates on load or refresh)
        auth_token = self._get_valid_token()

        # Prepare headers
        headers = kwargs.pop('headers', {})
        headers["Content-Type"] = "application/json"
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # 2. First Attempt
        response = session.request(method, url, headers=headers, **kwargs)

        # 3. Handle 401 (Unauthorized) - Token might have expired during execution
        if response.status_code == 401:
            self.logger.warning("Request failed with 401. Attempting to refresh token...")

            # Attempt to refresh
            cached_data = self._load_from_cache_raw()
            refresh_token = cached_data.get("refresh_token") if cached_data else None

            new_token = None
            if refresh_token:
                new_token = self._refresh_token(refresh_token)

            if new_token:
                self.logger.info("Token refreshed successfully. Retrying request...")
                headers["Authorization"] = f"Bearer {new_token}"
                # Retry
                response = session.request(method, url, headers=headers, **kwargs)
            else:
                self.logger.error("Token refresh failed. Authentication required.")

        return response

    def _get_valid_token(self) -> Optional[str]:
        # 1. Try to load from cache
        cached_data = self._load_from_cache_raw()
        if not cached_data:
            return self._perform_device_login()

        access_token = cached_data.get("access_token")
        refresh_token = cached_data.get("refresh_token")

        # 2. Validate Token (Quick Check)
        if self._is_token_valid(access_token):
            return access_token

        # 3. If invalid, try refresh
        if refresh_token:
            self.logger.info("Cached token invalid/expired. Attempting refresh...")
            new_token = self._refresh_token(refresh_token)
            if new_token:
                return new_token

        # 4. Fallback to full login
        self.logger.info("Cached token invalid and refresh failed.")
        return self._perform_device_login()

    def _load_from_cache_raw(self) -> Optional[dict]:
        if not self.TOKEN_CACHE_FILE.exists():
            return None
        try:
            with open(self.TOKEN_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _is_token_valid(self, token: str) -> bool:
        if not token:
            return False
        try:
            url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents?size=1"
            headers = {"Authorization": f"Bearer {token}"}
            resp = self.session.get(url, headers=headers, timeout=5)
            # 200 means access allowed/token valid.
            return resp.status_code == 200
        except Exception:
            return False

    def _refresh_token(self, refresh_token: str) -> Optional[str]:
        try:
            url = f"{self.api_url}/api/refresh-token"
            resp = self.session.post(url, json=refresh_token, headers={"Content-Type": "application/json"}, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                new_access = data.get("id_token")
                new_refresh = data.get("refresh_token")
                if new_access:
                    self._save_to_cache(new_access, new_refresh)
                    return new_access
            else:
                self.logger.warning(f"Refresh failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")

        return None

    def _perform_device_login(self) -> Optional[str]:
        self.logger.info("Initiating interactive device login...")

        try:
            # Step 1: Get Device Code / Auth Info
            auth_info_url = f"{self.api_url}/api/oauth/authenticate/device-login-info"
            params = {}
            if self.company_id:
                params['companyId'] = self.company_id

            resp = self.session.get(auth_info_url, params=params)
            resp.raise_for_status()
            auth_info = resp.json()

            verification_uri = auth_info.get("verificationURI")
            user_code = auth_info.get("userCode")
            device_code = auth_info.get("deviceCode")
            polling_interval = auth_info.get("pollingIntervalMillis", 2000) / 1000.0

            if not verification_uri or not device_code:
                self.logger.error(f"Invalid response from auth info endpoint. Keys found: {list(auth_info.keys())}. Content: {auth_info}")
                return None

            print("\n" + "= " *60)
            print("Action Required: Lightrun Authentication")
            print("= " *60)
            print(f"Please visit: {verification_uri}")
            if user_code:
                print(f"And enter code: {user_code}")
            print("= " *60 + "\n")

            # Auto-open browser
            self.logger.info("Opening browser...")
            webbrowser.open(verification_uri)

            # Step 2: Poll for Token
            token_url = f"{self.api_url}/api/oauth/authenticate/device/{device_code}"

            start_time = time.time()
            timeout = 300 # 5 minutes

            while time.time() - start_time < timeout:
                resp = self.session.get(token_url)

                if resp.status_code == 200:
                    if not resp.text.strip():
                        # Empty response means pending
                        pass
                    else:
                        try:
                            token_data = resp.json()
                            access_token = token_data.get("id_token")
                            refresh_token = token_data.get("refresh_token")

                            if access_token:
                                self.logger.info("Successfully authenticated!")
                                self._save_to_cache(access_token, refresh_token)
                                return access_token
                        except json.JSONDecodeError:
                            self.logger.warning(f"Failed to decode JSON from 200 response: {resp.text}")

                elif resp.status_code != 202:
                    pass

                time.sleep(polling_interval)

            self.logger.error("Authentication timed out.")
            return None

        except Exception as e:
            self.logger.error(f"Device login failed: {e}")
            return None

    def _save_to_cache(self, access_token: str, refresh_token: Optional[str] = None):
        try:
            self.TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Save strictly
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(str(self.TOKEN_CACHE_FILE), flags, 0o600)
            with os.fdopen(fd, 'w') as f:
                data = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "created_at": time.time()
                }
                json.dump(data, f)

        except Exception as e:
            self.logger.warning(f"Failed to cache token: {e}")
