"""Health check functionality."""
import requests

from config import HEALTH_CHECK_TIMEOUT
from modules import ManagedApp


def check_health(url: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> tuple[bool, str]:
    """
    Perform a health check on a URL.

    Returns:
        (is_healthy, status_message)
    """
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return True, "OK"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.Timeout:
        return False, "Timeout"
    except requests.ConnectionError:
        return False, "Connection Error"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_health_status(app: ManagedApp) -> str:
    """
    Get health status for an app.

    Returns:
        "OK" - Health check passed
        "Down" - Health check failed
        "Timeout" - Health check timed out
        "No Endpoint" - No health URL configured
    """
    if not app.health_url:
        return "No Endpoint"

    is_healthy, message = check_health(app.health_url)

    if is_healthy:
        return "OK"
    elif message == "Timeout":
        return "Timeout"
    else:
        return "Down"
