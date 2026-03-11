"""Data models for DashManager."""
from dataclasses import dataclass


@dataclass
class ManagedApp:
    """Configuration for a managed Flask application."""
    name: str
    path: str
    port: int
    start_cmd: str
    workdir: str
    health_url: str | None = None
    log_file: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "name": self.name,
            "path": self.path,
            "port": self.port,
            "start_cmd": self.start_cmd,
            "workdir": self.workdir,
            "health_url": self.health_url,
            "log_file": self.log_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ManagedApp":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            path=data["path"],
            port=data["port"],
            start_cmd=data["start_cmd"],
            workdir=data["workdir"],
            health_url=data.get("health_url"),
            log_file=data.get("log_file"),
        )


@dataclass
class AppStatus:
    """Runtime status of a managed application."""
    name: str
    running: bool
    pid: int | None
    port_open: bool
    port_owner_match: bool
    healthy: bool | None
    uptime_seconds: int | None
    last_started: str | None
    state_pid: int | None = None  # PID from state file (to detect crashes)

    @property
    def state(self) -> str:
        """
        Compute the app state label.

        Returns one of:
            - "running": Process is running and owns its port
            - "port_conflict": Process is running but different process owns port
            - "crashed": Had a PID in state but process is dead
            - "unknown_on_port": Not running, but something else is using the port
            - "stopped": Cleanly stopped (no PID in state)
        """
        if self.running:
            if self.port_open and not self.port_owner_match:
                return "port_conflict"
            return "running"
        else:
            # Not running
            if self.state_pid is not None:
                # Had a PID but process is dead = crashed
                return "crashed"
            if self.port_open:
                # Port in use by unknown process
                return "unknown_on_port"
            return "stopped"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "running": self.running,
            "pid": self.pid,
            "port_open": self.port_open,
            "port_owner_match": self.port_owner_match,
            "healthy": self.healthy,
            "uptime_seconds": self.uptime_seconds,
            "last_started": self.last_started,
            "state": self.state,
        }
