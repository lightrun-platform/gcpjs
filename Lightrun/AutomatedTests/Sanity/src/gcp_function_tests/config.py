"""Configuration settings for GCP Cloud Functions testing."""
import os
import subprocess
from pathlib import Path


def sanitize_username(username: str) -> str:
    """Sanitize username for use in function names (GCP allows alphanumeric and hyphens)."""
    # Replace spaces and special chars with hyphens, keep alphanumeric
    username = "".join(c if c.isalnum() or c == "-" else "-" for c in username)
    # Remove multiple consecutive hyphens
    username = "-".join(filter(None, username.split("-")))
    return username.lower()


def get_git_username() -> str | None:
    """Get git global user name for function naming. Returns None if not available."""
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return sanitize_username(result.stdout.strip())
    except Exception:
        pass
    return None


def get_username() -> str:
    """
    Get username for function naming.
    Priority: TEST_USERNAME env var > git config user.name
    Raises ValueError if neither is available.
    
    Note: Uses TEST_USERNAME instead of USERNAME to avoid conflicts with
    system USERNAME variable (which is set to login name on Unix systems).
    """
    # Check TEST_USERNAME environment variable first (takes precedence)
    # Use TEST_USERNAME to avoid conflicts with system USERNAME variable
    username_env = os.environ.get("TEST_USERNAME", "").strip()
    if username_env:
        return sanitize_username(username_env)
    
    # Fall back to git username
    git_username = get_git_username()
    if git_username:
        return git_username
    
    # Neither available - raise error
    raise ValueError(
        "Username not found. Please set TEST_USERNAME environment variable or configure git user.name:\n"
        "  export TEST_USERNAME='your-username'\n"
        "  OR\n"
        "  git config --global user.name 'Your Name'"
    )


# Initialize username and prefix
USERNAME_ERROR = None
try:
    USERNAME = get_username()
    FUNCTION_NAME_PREFIX = f"{USERNAME}-automated-test-"
except ValueError as e:
    # Store error message for validation in main script
    USERNAME_ERROR = str(e)
    USERNAME = None
    FUNCTION_NAME_PREFIX = None

# Region precedence: europe-north2 > northamerica-northeast1 > europe-west6
REGION_PRECEDENCE = ["europe-north2", "northamerica-northeast1", "europe-west6"]
REGION = os.environ.get("GCP_REGION", REGION_PRECEDENCE[0])
PROJECT_ID = os.environ.get("GCP_PROJECT", "lightrun-temp")

# Lightrun configuration
# All values are read from environment variables
# Required: LIGHTRUN_SECRET (used for agent initialization in deployed functions)
# Optional: LIGHTRUN_API_KEY, LIGHTRUN_COMPANY_ID (used for Lightrun API tests)
# Optional: LIGHTRUN_API_URL (defaults to https://api.lightrun.com)
LIGHTRUN_SECRET = os.environ.get("LIGHTRUN_SECRET", "")
LIGHTRUN_API_URL = os.environ.get("LIGHTRUN_API_URL", "https://api.lightrun.com")
LIGHTRUN_API_KEY = os.environ.get("LIGHTRUN_API_KEY", "")
LIGHTRUN_COMPANY_ID = os.environ.get("LIGHTRUN_COMPANY_ID", "")

# Test configuration
NODEJS_VERSIONS = list(range(18, 25))  # 18-24
FUNCTION_VERSIONS = [1, 2]  # Gen1 and Gen2
NUM_COLD_START_REQUESTS = 100
NUM_WARM_START_REQUESTS = 100

# Directory paths
# BASE_DIR is the gcp-function-tests directory (parent of src/)
BASE_DIR = Path(__file__).parent.parent.parent
TEST_FUNCTIONS_DIR = BASE_DIR / "test-functions"
RESULTS_DIR = BASE_DIR / "test-results"
