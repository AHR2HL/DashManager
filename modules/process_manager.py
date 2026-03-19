"""Process management for starting/stopping apps."""
import subprocess
import psutil
import time
import shlex
import logging
import os
from datetime import datetime

from modules import ManagedApp
from modules.state import update_app_state, clear_app_state
from config import BASE_DIR

# Set up logging for process manager
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "dashmanager.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("process_manager")


def parse_command(cmd: str, workdir: str) -> list[str]:
    """Parse a command string into a list for subprocess, resolving relative paths."""
    # Use shlex with posix=False for Windows-style paths
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError:
        # Fallback: simple split
        parts = cmd.split()

    if not parts:
        return parts

    # Resolve the executable path if it's relative
    exe = parts[0].strip('"').strip("'")
    if not os.path.isabs(exe):
        abs_exe = os.path.join(workdir, exe)
        if os.path.exists(abs_exe):
            parts[0] = abs_exe

    return parts


def force_clear_port(port: int) -> tuple[bool, str]:
    """
    Force-kill whatever process is holding a port.

    Returns:
        (success, message)
    """
    from modules.ports import get_pid_on_port

    pid = get_pid_on_port(port)
    if pid is None:
        return True, "Port already free"

    logger.info(f"Force-clearing port {port} (owned by PID {pid})")

    try:
        process = psutil.Process(pid)
        process.terminate()
        try:
            process.wait(timeout=3)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

        # Wait a moment for socket to fully release
        time.sleep(0.5)

        # Verify port is now free
        new_pid = get_pid_on_port(port)
        if new_pid is None:
            logger.info(f"Successfully cleared port {port}")
            return True, f"Killed PID {pid}"
        else:
            return False, f"Port still held by PID {new_pid}"

    except psutil.NoSuchProcess:
        # Process already gone, but socket may linger
        time.sleep(1)
        return True, "Process already gone"
    except Exception as e:
        return False, f"Failed to kill PID {pid}: {e}"


def start_app(app: ManagedApp, force_clear: bool = True) -> tuple[bool, int | None, str]:
    """
    Start a managed app.

    Args:
        app: The app to start
        force_clear: If True, kill any process holding the port before starting

    Returns:
        (success, pid, message)
    """
    logger.info(f"Starting app '{app.name}' with command: {app.start_cmd}")
    logger.info(f"Working directory: {app.workdir}")

    try:
        # PORT GUARD: Check if port is already in use
        from modules.ports import is_port_open, get_pid_on_port
        if is_port_open(app.port):
            owner_pid = get_pid_on_port(app.port)
            logger.warning(f"Port {app.port} already in use by PID {owner_pid}")

            if force_clear:
                success, msg = force_clear_port(app.port)
                if not success:
                    return False, None, f"Port {app.port} blocked and could not clear: {msg}"
                logger.info(f"Cleared port {app.port}: {msg}")
            else:
                return False, None, f"Port {app.port} is already in use by PID {owner_pid}"

        # Create a temp log file to capture startup output
        startup_log = os.path.join(log_dir, f"{app.name}_startup.log")

        # Clear environment variables that might interfere with Flask
        env = os.environ.copy()
        env.pop('WERKZEUG_SERVER_FD', None)
        env.pop('WERKZEUG_RUN_MAIN', None)

        # Hide window using startupinfo
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        # Parse command into list (no shell=True)
        cmd_list = parse_command(app.start_cmd, app.workdir)
        logger.info(f"Parsed command: {cmd_list}")

        with open(startup_log, "w") as log_file:
            # Start process directly without shell
            process = subprocess.Popen(
                cmd_list,
                cwd=app.workdir,
                shell=False,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

        logger.info(f"Process started with PID: {process.pid}")

        # Give it a moment to start
        time.sleep(1.5)

        # Check if it's still running
        if process.poll() is not None:
            # Read the startup log to see what went wrong
            try:
                with open(startup_log, "r") as f:
                    output = f.read().strip()
            except:
                output = "Could not read startup log"

            logger.error(f"Process exited immediately. Exit code: {process.returncode}")
            logger.error(f"Output: {output}")
            return False, None, f"Process exited (code {process.returncode}): {output[:200] if output else 'No output'}"

        # Update state
        update_app_state(app.name, process.pid, datetime.now())
        logger.info(f"App '{app.name}' started successfully with PID {process.pid}")

        return True, process.pid, "Started successfully"

    except Exception as e:
        logger.exception(f"Failed to start app '{app.name}'")
        return False, None, f"Failed to start: {str(e)}"


def stop_app(pid: int, app_name: str) -> tuple[bool, str]:
    """
    Stop a process by PID.

    Returns:
        (success, message)
    """
    try:
        if not is_process_alive(pid):
            clear_app_state(app_name)
            return True, "Process was not running"

        process = psutil.Process(pid)

        # Try graceful termination first
        process.terminate()

        # Wait up to 5 seconds for graceful shutdown
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            # Force kill if still running
            process.kill()
            process.wait(timeout=2)

        clear_app_state(app_name)
        return True, "Stopped successfully"

    except psutil.NoSuchProcess:
        clear_app_state(app_name)
        return True, "Process was not running"
    except Exception as e:
        return False, f"Failed to stop: {str(e)}"


def restart_app(app: ManagedApp, current_pid: int | None) -> tuple[bool, int | None, str]:
    """
    Restart an app (stop then start).

    Returns:
        (success, new_pid, message)
    """
    if current_pid:
        success, msg = stop_app(current_pid, app.name)
        if not success:
            return False, None, f"Failed to stop: {msg}"
        # Brief pause between stop and start
        time.sleep(0.5)

    return start_app(app)


def is_process_alive(pid: int) -> bool:
    """Check if a process with given PID exists and is running."""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def get_process_uptime(pid: int) -> int | None:
    """Get process uptime in seconds. Returns None if process doesn't exist."""
    try:
        process = psutil.Process(pid)
        create_time = process.create_time()
        return int(time.time() - create_time)
    except psutil.NoSuchProcess:
        return None
