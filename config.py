"""Configuration for DashManager."""
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Manager configuration
MANAGER_HOST = "127.0.0.1"
MANAGER_PORT = 5050

# File paths
APPS_YAML_PATH = os.path.join(BASE_DIR, "apps.yaml")
STATE_JSON_PATH = os.path.join(BASE_DIR, "state.json")

# Health check settings
HEALTH_CHECK_TIMEOUT = 3  # seconds

# Log settings
LOG_TAIL_LINES = 50
