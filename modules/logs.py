"""Log file reading functionality."""
from pathlib import Path
from collections import deque

from config import LOG_TAIL_LINES


def tail_log(log_path: str, lines: int = LOG_TAIL_LINES) -> tuple[bool, list[str], str]:
    """
    Read last N lines from a log file.

    Returns:
        (success, lines, message)
    """
    path = Path(log_path)

    if not path.exists():
        return False, [], "Log file not found"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            # Use deque to efficiently keep last N lines
            last_lines = deque(f, maxlen=lines)

        return True, list(last_lines), "OK"
    except PermissionError:
        return False, [], "Permission denied"
    except Exception as e:
        return False, [], f"Error reading log: {str(e)}"


def filter_log_lines(lines: list[str], level: str) -> list[str]:
    """
    Filter log lines by level.

    Args:
        lines: List of log lines
        level: Filter level - "ALL", "ERROR", "WARNING"

    Returns:
        Filtered list of lines
    """
    if level == "ALL":
        return lines

    level_upper = level.upper()
    filtered = []

    for line in lines:
        line_upper = line.upper()
        if level_upper == "ERROR" and "ERROR" in line_upper:
            filtered.append(line)
        elif level_upper == "WARNING" and ("WARNING" in line_upper or "ERROR" in line_upper):
            filtered.append(line)

    return filtered
