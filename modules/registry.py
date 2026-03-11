"""Registry management for apps.yaml."""
import yaml
from pathlib import Path

from config import APPS_YAML_PATH
from modules import ManagedApp


def load_registry() -> list[ManagedApp]:
    """Load all apps from apps.yaml."""
    path = Path(APPS_YAML_PATH)
    if not path.exists():
        return []

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    apps = data.get("apps", [])
    return [ManagedApp.from_dict(app) for app in apps]


def save_registry(apps: list[ManagedApp]) -> None:
    """Save all apps to apps.yaml."""
    data = {"apps": [app.to_dict() for app in apps]}

    with open(APPS_YAML_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def validate_app_config(app_dict: dict) -> list[str]:
    """Validate app configuration. Returns list of error messages."""
    errors = []

    required_fields = ["name", "path", "port", "start_cmd", "workdir"]
    for field in required_fields:
        if field not in app_dict or not app_dict[field]:
            errors.append(f"Missing required field: {field}")

    if "port" in app_dict:
        try:
            port = int(app_dict["port"])
            if port < 1 or port > 65535:
                errors.append("Port must be between 1 and 65535")
        except (ValueError, TypeError):
            errors.append("Port must be a valid number")

    if "name" in app_dict:
        name = app_dict["name"]
        if not name.replace("_", "").replace("-", "").isalnum():
            errors.append("Name must be alphanumeric (underscores and hyphens allowed)")

    return errors


def get_app(name: str) -> ManagedApp | None:
    """Get a single app by name."""
    apps = load_registry()
    for app in apps:
        if app.name == name:
            return app
    return None


def add_app(app_dict: dict) -> tuple[bool, str]:
    """Add a new app to the registry. Returns (success, message)."""
    errors = validate_app_config(app_dict)
    if errors:
        return False, "; ".join(errors)

    apps = load_registry()

    # Check for duplicate name
    if any(app.name == app_dict["name"] for app in apps):
        return False, f"App with name '{app_dict['name']}' already exists"

    # Check for duplicate port
    if any(app.port == int(app_dict["port"]) for app in apps):
        return False, f"Port {app_dict['port']} is already in use by another app"

    new_app = ManagedApp.from_dict(app_dict)
    apps.append(new_app)
    save_registry(apps)

    return True, "App added successfully"


def update_app(name: str, app_dict: dict) -> tuple[bool, str]:
    """Update an existing app. Returns (success, message)."""
    errors = validate_app_config(app_dict)
    if errors:
        return False, "; ".join(errors)

    apps = load_registry()

    # Find and update the app
    found = False
    for i, app in enumerate(apps):
        if app.name == name:
            # Check for port conflict with other apps
            new_port = int(app_dict["port"])
            for other_app in apps:
                if other_app.name != name and other_app.port == new_port:
                    return False, f"Port {new_port} is already in use by '{other_app.name}'"

            apps[i] = ManagedApp.from_dict(app_dict)
            found = True
            break

    if not found:
        return False, f"App '{name}' not found"

    save_registry(apps)
    return True, "App updated successfully"


def remove_app(name: str) -> tuple[bool, str]:
    """Remove an app from the registry. Returns (success, message)."""
    apps = load_registry()

    original_count = len(apps)
    apps = [app for app in apps if app.name != name]

    if len(apps) == original_count:
        return False, f"App '{name}' not found"

    save_registry(apps)
    return True, "App removed successfully"
