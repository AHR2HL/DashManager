"""DashManager - Flask App Manager Dashboard."""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import sys
import time
import threading

from config import MANAGER_HOST, MANAGER_PORT
from modules import ManagedApp, AppStatus
from modules.registry import (
    load_registry,
    get_app,
    add_app,
    update_app,
    remove_app,
    validate_app_config,
)
from modules.state import get_app_state, load_state
from modules.ports import is_port_open, get_pid_on_port, check_port_ownership, get_unknown_listeners
from modules.process_manager import (
    start_app as pm_start_app,
    stop_app as pm_stop_app,
    restart_app as pm_restart_app,
    is_process_alive,
    get_process_uptime,
)
from modules.health import get_health_status
from modules.logs import tail_log, filter_log_lines
from modules.detector import suggest_app_config


app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.template_filter('format_uptime')
def format_uptime(seconds):
    """Format uptime seconds into human-readable string."""
    if not seconds:
        return '-'

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def get_app_status(managed_app: ManagedApp) -> AppStatus:
    """Build full status for a managed app."""
    state = get_app_state(managed_app.name)
    state_pid = state.get("pid") if state else None
    last_started = state.get("started_at") if state else None

    # Check if process is running
    running = False
    uptime = None
    if state_pid:
        running = is_process_alive(state_pid)
        if running:
            uptime = get_process_uptime(state_pid)

    # Check port status
    port_open = is_port_open(managed_app.port)
    ownership = check_port_ownership(managed_app.port, state_pid if running else None)
    port_owner_match = ownership == "match"

    # Check health
    healthy = None
    if running and port_open:
        health_status = get_health_status(managed_app)
        if health_status == "OK":
            healthy = True
        elif health_status == "No Endpoint":
            healthy = None
        else:
            healthy = False

    return AppStatus(
        name=managed_app.name,
        running=running,
        pid=state_pid if running else None,
        port_open=port_open,
        port_owner_match=port_owner_match,
        healthy=healthy,
        uptime_seconds=uptime,
        last_started=last_started,
        state_pid=state_pid if not running else None,  # Only set if crashed (had PID but not running)
    )


def get_all_statuses() -> list[tuple[ManagedApp, AppStatus]]:
    """Get status for all registered apps."""
    apps = load_registry()
    return [(app, get_app_status(app)) for app in apps]


# =============================================================================
# Dashboard Routes
# =============================================================================


@app.route("/")
def dashboard():
    """Main dashboard page."""
    app_statuses = get_all_statuses()
    registered_ports = [app.port for app, _ in app_statuses]
    unknown_filter = request.args.get("unknown_filter", "coded")
    unknown = get_unknown_listeners(registered_ports, MANAGER_PORT, unknown_filter)
    return render_template("dashboard.html", apps=app_statuses, unknown_listeners=unknown, unknown_filter=unknown_filter)


@app.route("/api/status")
def api_status():
    """JSON status for all apps (for polling)."""
    app_statuses = get_all_statuses()
    return jsonify([
        {
            "app": app.to_dict(),
            "status": status.to_dict(),
        }
        for app, status in app_statuses
    ])


# =============================================================================
# App Control Routes
# =============================================================================


@app.route("/app/<name>")
def app_detail(name):
    """Single app detail page."""
    managed_app = get_app(name)
    if not managed_app:
        flash(f"App '{name}' not found", "error")
        return redirect(url_for("dashboard"))

    status = get_app_status(managed_app)

    # Get preview of logs
    log_preview = []
    if managed_app.log_file:
        success, lines, _ = tail_log(managed_app.log_file, 10)
        if success:
            log_preview = lines

    # Check port ownership details
    port_owner_pid = get_pid_on_port(managed_app.port)

    return render_template(
        "app_detail.html",
        app=managed_app,
        status=status,
        log_preview=log_preview,
        port_owner_pid=port_owner_pid,
    )


@app.route("/app/<name>/start", methods=["POST"])
def start_app_route(name):
    """Start an app."""
    managed_app = get_app(name)
    if not managed_app:
        flash(f"App '{name}' not found", "error")
        return redirect(url_for("dashboard"))

    success, pid, message = pm_start_app(managed_app)

    if success:
        flash(f"Started '{name}' (PID: {pid})", "success")
    else:
        flash(f"Failed to start '{name}': {message}", "error")

    # Redirect back to referrer or dashboard
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/app/<name>/stop", methods=["POST"])
def stop_app_route(name):
    """Stop an app."""
    state = get_app_state(name)
    if not state:
        flash(f"App '{name}' is not running", "warning")
        return redirect(request.referrer or url_for("dashboard"))

    pid = state.get("pid")
    success, message = pm_stop_app(pid, name)

    if success:
        flash(f"Stopped '{name}'", "success")
    else:
        flash(f"Failed to stop '{name}': {message}", "error")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/app/<name>/restart", methods=["POST"])
def restart_app_route(name):
    """Restart an app."""
    managed_app = get_app(name)
    if not managed_app:
        flash(f"App '{name}' not found", "error")
        return redirect(url_for("dashboard"))

    state = get_app_state(name)
    current_pid = state.get("pid") if state else None

    success, pid, message = pm_restart_app(managed_app, current_pid)

    if success:
        flash(f"Restarted '{name}' (PID: {pid})", "success")
    else:
        flash(f"Failed to restart '{name}': {message}", "error")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/app/<name>/logs")
def logs_page(name):
    """Log viewer page."""
    managed_app = get_app(name)
    if not managed_app:
        flash(f"App '{name}' not found", "error")
        return redirect(url_for("dashboard"))

    if not managed_app.log_file:
        flash(f"No log file configured for '{name}'", "warning")
        return redirect(url_for("app_detail", name=name))

    lines_count = request.args.get("lines", 50, type=int)
    level_filter = request.args.get("level", "ALL")

    success, lines, message = tail_log(managed_app.log_file, lines_count)

    if not success:
        flash(f"Error reading logs: {message}", "error")
        lines = []
    elif level_filter != "ALL":
        lines = filter_log_lines(lines, level_filter)

    return render_template(
        "logs.html",
        app=managed_app,
        lines=lines,
        lines_count=lines_count,
        level_filter=level_filter,
        error=None if success else message,
    )


@app.route("/api/app/<name>/logs")
def api_logs(name):
    """JSON log content for refresh."""
    managed_app = get_app(name)
    if not managed_app:
        return jsonify({"error": "App not found"}), 404

    if not managed_app.log_file:
        return jsonify({"error": "No log file configured"}), 400

    lines_count = request.args.get("lines", 50, type=int)
    level_filter = request.args.get("level", "ALL")

    success, lines, message = tail_log(managed_app.log_file, lines_count)

    if not success:
        return jsonify({"error": message, "lines": []}), 200

    if level_filter != "ALL":
        lines = filter_log_lines(lines, level_filter)

    return jsonify({"lines": lines, "error": None})


# =============================================================================
# Registry Editor Routes
# =============================================================================


@app.route("/registry")
def registry_editor():
    """Registry editor page."""
    apps = load_registry()
    return render_template("registry_editor.html", apps=apps)


@app.route("/api/registry")
def api_registry():
    """Get all apps as JSON."""
    apps = load_registry()
    return jsonify([app.to_dict() for app in apps])


@app.route("/api/registry/app", methods=["POST"])
def api_add_app():
    """Add a new app."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Ensure port is int
    if "port" in data:
        try:
            data["port"] = int(data["port"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid port"}), 400

    success, message = add_app(data)
    return jsonify({"success": success, "message": message})


@app.route("/api/registry/app/<name>", methods=["PUT"])
def api_update_app(name):
    """Update an existing app."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Ensure port is int
    if "port" in data:
        try:
            data["port"] = int(data["port"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid port"}), 400

    success, message = update_app(name, data)
    return jsonify({"success": success, "message": message})


@app.route("/api/registry/app/<name>", methods=["DELETE"])
def api_delete_app(name):
    """Remove an app."""
    success, message = remove_app(name)
    return jsonify({"success": success, "message": message})


# =============================================================================
# Auto-Detect Routes
# =============================================================================


@app.route("/api/detect", methods=["POST"])
def api_detect():
    """Auto-detect Flask app configuration from a folder path."""
    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"valid": False, "error": "No path provided"}), 400

    path = data["path"]

    # Basic path validation
    if not os.path.isabs(path):
        return jsonify({"valid": False, "error": "Path must be absolute"}), 400

    if ".." in path:
        return jsonify({"valid": False, "error": "Path traversal not allowed"}), 400

    config = suggest_app_config(path)
    return jsonify(config)


# =============================================================================
# AI Agent API Routes
# =============================================================================


@app.route("/api/app/<name>/start", methods=["POST"])
def api_start_app(name):
    """Start an app via API. Returns JSON."""
    managed_app = get_app(name)
    if not managed_app:
        return jsonify({"success": False, "error": "App not found"}), 404

    success, pid, message = pm_start_app(managed_app)
    return jsonify({"success": success, "pid": pid, "message": message})


@app.route("/api/app/<name>/stop", methods=["POST"])
def api_stop_app(name):
    """Stop an app via API. Returns JSON."""
    managed_app = get_app(name)
    if not managed_app:
        return jsonify({"success": False, "error": "App not found"}), 404

    state = get_app_state(name)
    if not state:
        return jsonify({"success": False, "error": "App not running"}), 400

    pid = state.get("pid")
    success, message = pm_stop_app(pid, name)
    return jsonify({"success": success, "message": message})


@app.route("/api/app/<name>/restart", methods=["POST"])
def api_restart_app(name):
    """Restart an app via API. Returns JSON."""
    managed_app = get_app(name)
    if not managed_app:
        return jsonify({"success": False, "error": "App not found"}), 404

    state = get_app_state(name)
    current_pid = state.get("pid") if state else None

    success, pid, message = pm_restart_app(managed_app, current_pid)
    return jsonify({"success": success, "pid": pid, "message": message})


@app.route("/api/unknown-ports", methods=["GET"])
def api_unknown_ports():
    """List ports in use that aren't registered. Filter: all, coded, system."""
    registered = [app.port for app in load_registry()]
    filter_type = request.args.get("filter", "all")
    unknown = get_unknown_listeners(registered, MANAGER_PORT, filter_type)
    return jsonify({"unknown_ports": unknown, "count": len(unknown), "filter": filter_type})


# =============================================================================
# Server Management Routes
# =============================================================================


def _restart_server():
    """Restart the server by touching app.py to trigger werkzeug reloader."""
    time.sleep(0.5)  # Allow response to be sent
    # Touch app.py to trigger the reloader
    app_file = os.path.join(os.path.dirname(__file__), "app.py")
    os.utime(app_file, None)


@app.route("/restart-server", methods=["POST"])
def restart_server():
    """Restart DashManager server to pick up code changes."""
    # Start restart in background thread so response can be sent
    thread = threading.Thread(target=_restart_server)
    thread.daemon = True
    thread.start()
    flash("Server restarting...", "info")
    return redirect(url_for("dashboard"))


@app.route("/api/restart-server", methods=["POST"])
def api_restart_server():
    """Restart server via API."""
    thread = threading.Thread(target=_restart_server)
    thread.daemon = True
    thread.start()
    return jsonify({"success": True, "message": "Server restarting..."})


# =============================================================================
# Entry Point
# =============================================================================


if __name__ == "__main__":
    print(f"Starting DashManager on http://{MANAGER_HOST}:{MANAGER_PORT}")
    app.run(host=MANAGER_HOST, port=MANAGER_PORT, debug=True)
