"""Runtime state management for state.json."""
import json
from pathlib import Path
from datetime import datetime

from config import STATE_JSON_PATH


def load_state() -> dict:
    """Load runtime state from state.json."""
    path = Path(STATE_JSON_PATH)
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_state(state: dict) -> None:
    """Save runtime state to state.json."""
    with open(STATE_JSON_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_app_state(name: str) -> dict | None:
    """Get state for a single app."""
    state = load_state()
    return state.get(name)


def update_app_state(name: str, pid: int, started_at: datetime | None = None) -> None:
    """Update app state on start."""
    state = load_state()

    if started_at is None:
        started_at = datetime.now()

    state[name] = {
        "pid": pid,
        "started_at": started_at.isoformat(),
    }

    save_state(state)


def clear_app_state(name: str) -> None:
    """Clear app state on stop."""
    state = load_state()

    if name in state:
        del state[name]
        save_state(state)
