# Managed App Specification

This document describes the requirements for Flask applications
to be fully compatible with DashManager.

## Required

### 1. Standalone Execution
- App must be runnable via a single command
- Must use its own virtual environment
- Command format: `<venv>/Scripts/python.exe <entry_point>.py`

### 2. Port Binding
- Must bind to a specific, configurable port
- Must bind to 127.0.0.1 (localhost only)
- Port must be consistent across restarts

## Recommended (for full functionality)

### 3. Health Endpoint
Expose a `/health` endpoint for status monitoring:

```python
@app.route("/health")
def health():
    return {"status": "ok"}, 200
```

**Response requirements:**
- HTTP 200 for healthy
- Any other status code = unhealthy
- Timeout after 3 seconds = unhealthy

**Advanced health check (optional):**

```python
@app.route("/health")
def health():
    checks = {
        "database": check_db_connection(),
        "cache": check_redis(),
    }
    status = "ok" if all(checks.values()) else "degraded"
    code = 200 if status == "ok" else 503
    return {"status": status, "checks": checks}, code
```

### 4. File-based Logging
Log to a file for the manager to tail:

```python
import logging
from logging.handlers import RotatingFileHandler
import os

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Configure file handler
handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s: %(message)s"
))

# Attach to app logger
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
```

**Log format recommendation:**
- Include timestamp, level, logger name, message
- Use standard levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### 5. Graceful Shutdown
Handle SIGTERM for clean shutdown:

```python
import signal
import sys

def handle_sigterm(signum, frame):
    app.logger.info("Received SIGTERM, shutting down...")
    # Cleanup code here
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
```

## Project Structure (Recommended)

```
my_flask_app/
├── app.py              # Entry point with app.run()
├── .venv/              # Virtual environment
├── logs/
│   └── app.log         # Application log file
├── requirements.txt
└── ...
```

## Registry Entry Example

When registered in DashManager, your app entry looks like:

```yaml
apps:
  - name: my_flask_app
    path: C:\projects\my_flask_app
    port: 5001
    start_cmd: C:\projects\my_flask_app\.venv\Scripts\python.exe app.py
    workdir: C:\projects\my_flask_app
    health_url: http://127.0.0.1:5001/health
    log_file: C:\projects\my_flask_app\logs\app.log
```

## Compliance Checklist

- [ ] App runs via single command with venv python
- [ ] Binds to specific port on 127.0.0.1
- [ ] Exposes /health endpoint (recommended)
- [ ] Logs to file in logs/ directory (recommended)
- [ ] Handles SIGTERM gracefully (recommended)
