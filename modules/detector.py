"""Auto-detection of Flask apps in folders."""
import os
import re
from pathlib import Path


# Common entry point filenames (checked first)
ENTRY_POINTS = ["app.py", "main.py", "run.py", "wsgi.py", "application.py", "server.py", "web.py"]


def find_flask_entry_point(path: str) -> str | None:
    """Search for a Flask app by scanning Python files for Flask patterns."""
    p = Path(path)

    # First check common names
    for name in ENTRY_POINTS:
        if (p / name).exists():
            return name

    # Then scan all .py files in root for Flask patterns
    flask_patterns = [
        r'from\s+flask\s+import',
        r'import\s+flask',
        r'Flask\s*\(',
        r'\.run\s*\(',
    ]

    for py_file in p.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            # Check if file has Flask import AND .run() call
            has_flask = any(re.search(pat, content) for pat in flask_patterns[:3])
            has_run = re.search(r'\.run\s*\(', content) is not None
            if has_flask and has_run:
                return py_file.name
        except Exception:
            continue

    return None

# Common venv directory names
VENV_DIRS = [".venv", "venv", "env", ".env"]


def scan_folder(path: str) -> dict:
    """
    Scan a folder for Flask app indicators.

    Returns dict with detected features.
    """
    p = Path(path)

    if not p.exists() or not p.is_dir():
        return {"valid": False, "error": "Path does not exist or is not a directory"}

    result = {
        "valid": True,
        "path": str(p.absolute()),
        "entry_point": None,
        "venv_path": None,
        "has_requirements": False,
        "has_logs_dir": False,
        "detected_port": None,
    }

    # Check for entry point
    result["entry_point"] = detect_entry_point(path)

    # Check for venv
    result["venv_path"] = detect_venv(path)

    # Check for requirements.txt
    result["has_requirements"] = (p / "requirements.txt").exists()

    # Check for logs directory
    result["has_logs_dir"] = (p / "logs").is_dir()

    # Try to detect port from entry point
    if result["entry_point"]:
        result["detected_port"] = detect_port_in_file(p / result["entry_point"])

    return result


def detect_entry_point(path: str) -> str | None:
    """Find Flask app entry point file."""
    return find_flask_entry_point(path)


def detect_venv(path: str) -> str | None:
    """Find virtual environment directory."""
    p = Path(path)

    for venv in VENV_DIRS:
        venv_path = p / venv
        # Check for Scripts folder (Windows) or bin folder (Unix)
        if venv_path.is_dir():
            if (venv_path / "Scripts" / "python.exe").exists():
                return str(venv_path.absolute())
            if (venv_path / "bin" / "python").exists():
                return str(venv_path.absolute())

    return None


def detect_port_in_file(file_path: Path) -> int | None:
    """Try to detect port number from a Python file."""
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Look for common port patterns
        patterns = [
            r"port\s*=\s*(\d+)",
            r"PORT\s*=\s*(\d+)",
            r"\.run\([^)]*port\s*=\s*(\d+)",
            r"app\.run\([^)]*(\d{4,5})",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                port = int(match.group(1))
                if 1024 <= port <= 65535:
                    return port

        return None
    except Exception:
        return None


def build_start_command(path: str, entry_point: str, venv_path: str | None) -> str:
    """Build the start command for an app."""
    if venv_path:
        # Windows path
        python_path = os.path.join(venv_path, "Scripts", "python.exe")
        if not os.path.exists(python_path):
            # Unix path
            python_path = os.path.join(venv_path, "bin", "python")
    else:
        python_path = "python"

    return f'"{python_path}" {entry_point}'


def suggest_app_config(path: str) -> dict:
    """
    Generate a suggested app configuration from a folder scan.

    Returns a dict ready for use as app config.
    """
    scan = scan_folder(path)

    if not scan["valid"]:
        return {"valid": False, "error": scan.get("error", "Invalid path")}

    # Generate app name from folder name
    folder_name = Path(path).name
    app_name = re.sub(r"[^a-zA-Z0-9_-]", "_", folder_name).lower()

    # Determine port
    port = scan["detected_port"] or 5001  # Default to 5001 if not detected

    # Build start command
    entry_point = scan["entry_point"] or "app.py"
    start_cmd = build_start_command(path, entry_point, scan["venv_path"])

    # Build log file path
    log_file = None
    if scan["has_logs_dir"]:
        log_file = os.path.join(scan["path"], "logs", "app.log")

    config = {
        "valid": True,
        "name": app_name,
        "path": scan["path"],
        "port": port,
        "start_cmd": start_cmd,
        "workdir": scan["path"],
        "health_url": f"http://127.0.0.1:{port}/health",
        "log_file": log_file,
        "scan_info": {
            "entry_point": entry_point,
            "venv_detected": scan["venv_path"] is not None,
            "has_requirements": scan["has_requirements"],
            "port_detected": scan["detected_port"] is not None,
        },
    }

    return config
