# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DashManager is a local admin dashboard for managing multiple independent Flask applications. It tracks apps defined in `apps.yaml`, controls their lifecycle (start/stop/restart), monitors health endpoints, displays logs, and detects port status. Each managed app runs as its own process - the manager controls apps, it doesn't absorb them.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the manager (starts on http://127.0.0.1:5050)
python app.py
```

No test suite exists yet.

## Architecture

### Data Flow
1. **Registry** (`apps.yaml`) - Persistent app configurations loaded by `modules/registry.py`
2. **State** (`state.json`) - Runtime state (PIDs, timestamps) managed by `modules/state.py`
3. **Status** - Computed at request time by combining registry config + state + live process/port checks

### Core Modules (`modules/`)
- `__init__.py` - Dataclasses: `ManagedApp` (config) and `AppStatus` (runtime status)
- `registry.py` - CRUD operations for apps.yaml
- `state.py` - Runtime state persistence (PIDs, start times)
- `process_manager.py` - subprocess.Popen with DETACHED_PROCESS, psutil for stop/status
- `ports.py` - Socket checks, psutil net_connections for port ownership
- `health.py` - HTTP health endpoint checks with timeout
- `logs.py` - File tailing with level filtering
- `detector.py` - Auto-detect Flask apps by scanning for entry points and venvs

### Routes (`app.py`)
- `/` - Dashboard with all app statuses
- `/app/<name>` - Detail view, `/app/<name>/start|stop|restart` - Control actions
- `/app/<name>/logs` - Log viewer
- `/registry` - In-app registry editor UI
- `/api/*` - JSON endpoints for AJAX operations

### Key Design Decisions
- Apps are started with `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags (Windows)
- Health checks run synchronously at page load (no background polling)
- Port ownership verified by matching expected PID against psutil's net_connections
- Plain HTML/CSS templates - no framework dependencies
