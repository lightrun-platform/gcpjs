import json
import logging
import time
import webbrowser
import platform
import subprocess
from typing import Optional

import requests


class Credentials:

    def __init__(self, logger: logging.Logger, api_url: str, company_id: str) -> None:
        self.logger = logger
        self.api_url = api_url
        self.company_id = company_id
        self.session = requests.Session()
        self._access_token = None
        self._refresh_token = None
        self.expiration_time = None

    # def _is_token_valid(self, token: str) -> bool:
    #     if not token:
    #         return False
    #     try:
    #         url = f"{self.api_url}/api/v1/companies/{self.company_id}/agents?size=1"
    #         headers = {"Authorization": f"Bearer {token}"}
    #         resp = self.session.get(url, headers=headers, timeout=5)
    #         # 200 means access allowed/token valid.
    #         return resp.status_code == 200
    #     except Exception:
    #         return False

    def is_token_expired(self) -> bool:
        if self.expiration_time is None:
             return True
        return self.expiration_time < time.monotonic_ns()

    def get_access_token(self) -> str:
        if self._access_token:
            # 2. Validate Token (Quick Check)
            if not self.is_token_expired():
                self.logger.info("Cached token is valid, reusing it..")
                return self._access_token

        if self._refresh_token:
            self.logger.info("Cached token invalid/expired. Attempting refresh...")
            self._access_token = self.try_refreshing_token(self._refresh_token)
            if self._access_token:
                return self._access_token

        # 4. Fallback to full login
        self.logger.info("Cached token invalid and refresh failed.")
        self._access_token, self._refresh_token, self.expiration_time = self._perform_device_login()

        return self._access_token

    def try_refreshing_token(self, refresh_token: str) -> Optional[str]:
        try:
            url = f"{self.api_url}/api/refresh-token"
            resp = self.session.post(url, json=refresh_token, headers={"Content-Type": "application/json"}, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                new_access = data.get("id_token")
                new_refresh = data.get("refresh_token")
                if new_access:
                    self._save_token(new_access, new_refresh)
                    return new_access
            else:
                self.logger.warning(f"Refresh failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            self.logger.exception(f"Error refreshing token: {e}")

        return None

    def _save_token(self, access_token, refresh_token):
        # In-memory only, so just update instance
        self._access_token = access_token
        self._refresh_token = refresh_token
        # Update expiration if provided? 
        # API doesn't return expires_in on refresh usually, need to check. 
        # Assuming reasonable default if not provided, but mostly get_access_token flow handles expiration.
        pass 

    def _perform_device_login(self):
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
                return None, None, None

            self.logger.info("\n" + "= " * 60)
            self.logger.info("Action Required: Lightrun Authentication")
            self.logger.info("= " * 60)
            self.logger.info(f"Please visit: {verification_uri}")
            if user_code:
                self.logger.info(f"And enter code: {user_code}")
            self.logger.info("= " * 60 + "\n")

            # Auto-open browser
            self.logger.info("Opening browser in background...")
            webbrowser.open(verification_uri, new=2, autoraise=False)

            # Step 2: Poll for Token
            token_url = f"{self.api_url}/api/oauth/authenticate/device/{device_code}"

            start_time = time.time()
            timeout = 300  # 5 minutes

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
                            time_window = token_data.get("expires_in")
                            expiration_time = time.monotonic_ns() + (time_window * 1_000_000_000)

                            if access_token:
                                self.logger.info("Successfully authenticated!")
                                self._close_active_tab_macos()
                                return access_token, refresh_token, expiration_time
                        except json.JSONDecodeError:
                            self.logger.warning(f"Failed to decode JSON from 200 response: {resp.text}")

                elif resp.status_code != 202:
                    pass

                time.sleep(polling_interval)

            self.logger.error("Authentication timed out.")
            return None, None, None

        except Exception as e:
            self.logger.exception(f"Device login failed: {e}")
            return None, None, None


    def _close_active_tab_macos(self):
        """Attempts to close the active tab in Google Chrome on macOS."""
        try:
            # Only run on macOS
            if platform.system() != 'Darwin':
                return

            # AppleScript to close the active tab of the front window of Google Chrome
            # We check if it's running to avoid launching it if it's not open (though it must be if used for auth)
            script = '''
            tell application "Google Chrome"
                if running then
                    close active tab of front window
                end if
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True, check=False)
            self.logger.info("Attempted to close browser tab.")
        except Exception as e:
            self.logger.exception(f"Failed to auto-close browser tab: {e}")
