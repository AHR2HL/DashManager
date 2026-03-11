"""Port detection and ownership checking."""
import socket
import psutil


def is_port_open(port: int) -> bool:
    """Check if a port is listening (in use)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0


def get_pid_on_port(port: int) -> int | None:
    """Find which PID owns a port. Returns None if port not in use."""
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            return conn.pid
    return None


def is_child_of(child_pid: int, parent_pid: int) -> bool:
    """Check if child_pid is a descendant of parent_pid."""
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        return any(c.pid == child_pid for c in children)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def check_port_ownership(port: int, expected_pid: int | None) -> str:
    """
    Check port ownership status.

    Returns:
        - "match": Port is owned by expected PID or one of its child processes
        - "mismatch": Port is owned by different PID (not a child)
        - "conflict": Port in use but expected PID is None
        - "free": Port is not in use
    """
    actual_pid = get_pid_on_port(port)

    if actual_pid is None:
        return "free"

    if expected_pid is None:
        return "conflict"

    if actual_pid == expected_pid:
        return "match"

    # Check if port owner is a child process of the expected PID
    if is_child_of(actual_pid, expected_pid):
        return "match"

    return "mismatch"


def get_all_listening_ports() -> list[dict]:
    """
    Get all localhost listening ports with process info.
    Returns: [{"port": int, "pid": int, "name": str}, ...]
    """
    listeners = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == "LISTEN" and conn.laddr.ip in ("127.0.0.1", "0.0.0.0"):
            try:
                proc = psutil.Process(conn.pid)
                listeners.append({
                    "port": conn.laddr.port,
                    "pid": conn.pid,
                    "name": proc.name()
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return listeners


# Known developer/coded process names (lowercase for matching)
CODED_PROCESSES = {
    "python.exe", "python3.exe", "pythonw.exe", "python",
    "node.exe", "node",
    "ruby.exe", "ruby",
    "java.exe", "javaw.exe", "java",
    "php.exe", "php", "php-cgi.exe",
    "go.exe", "go",
    "dotnet.exe", "dotnet",
    "cargo.exe", "rustc.exe",
    "npm.exe", "npx.exe", "yarn.exe", "pnpm.exe",
    "deno.exe", "deno", "bun.exe", "bun",
}


def is_coded_process(name: str) -> bool:
    """Check if a process name is a known developer/coded process."""
    return name.lower() in CODED_PROCESSES


def get_unknown_listeners(registered_ports: list[int], manager_port: int = 5050, filter_type: str = "all") -> list[dict]:
    """
    Filter to ports not in registry and not DashManager itself, sorted by port.

    Args:
        registered_ports: List of ports registered in the app registry
        manager_port: The port DashManager runs on (excluded from results)
        filter_type: "all", "coded" (python/node/etc), or "system" (everything else)
    """
    all_ports = get_all_listening_ports()
    unknown = [p for p in all_ports if p["port"] not in registered_ports and p["port"] != manager_port]

    if filter_type == "coded":
        unknown = [p for p in unknown if is_coded_process(p["name"])]
    elif filter_type == "system":
        unknown = [p for p in unknown if not is_coded_process(p["name"])]

    return sorted(unknown, key=lambda p: p["port"])
