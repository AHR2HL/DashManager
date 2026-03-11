/**
 * DashManager - Frontend JavaScript
 */

// Toast notification system
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Format uptime helper (for JS use if needed)
function formatUptime(seconds) {
    if (!seconds) return '-';

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// API helpers
async function apiCall(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {}
    };

    if (data) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Dashboard status polling
class DashboardPoller {
    constructor(interval = 10000) {
        this.interval = interval;
        this.timer = null;
        this.enabled = true;
    }

    start() {
        if (this.timer) {
            clearInterval(this.timer);
        }

        if (this.enabled) {
            this.timer = setInterval(() => this.poll(), this.interval);
        }
    }

    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (enabled) {
            this.start();
        } else {
            this.stop();
        }
    }

    setInterval(interval) {
        this.interval = interval;
        if (this.enabled) {
            this.start();
        }
    }

    async poll() {
        try {
            const data = await apiCall('/api/status');
            this.updateTable(data);
        } catch (error) {
            console.error('Failed to poll status:', error);
        }
    }

    updateTable(apps) {
        const tbody = document.querySelector('#app-table tbody');
        if (!tbody) return;

        apps.forEach(({ app, status }) => {
            const row = tbody.querySelector(`tr[data-app="${app.name}"]`);
            if (!row) return;

            // Update status badge
            const statusCell = row.cells[3];
            const statusBadge = status.running
                ? '<span class="badge badge-running">Running</span>'
                : '<span class="badge badge-stopped">Stopped</span>';

            let portWarning = '';
            if (status.port_open && !status.port_owner_match && status.running) {
                portWarning = '<span class="badge badge-warning" title="Port owned by different process">!</span>';
            }
            statusCell.innerHTML = statusBadge + portWarning;

            // Update health badge
            const healthCell = row.cells[4];
            let healthBadge;
            if (status.healthy === null) {
                healthBadge = '<span class="badge badge-na">N/A</span>';
            } else if (status.healthy) {
                healthBadge = '<span class="badge badge-ok">OK</span>';
            } else {
                healthBadge = '<span class="badge badge-down">Down</span>';
            }
            healthCell.innerHTML = healthBadge;

            // Update PID
            row.cells[2].textContent = status.pid || '-';

            // Update uptime
            row.cells[5].textContent = status.uptime_seconds
                ? formatUptime(status.uptime_seconds)
                : '-';
        });
    }
}

// Log viewer
class LogViewer {
    constructor(appName, options = {}) {
        this.appName = appName;
        this.lines = options.lines || 50;
        this.level = options.level || 'ALL';
        this.autoRefresh = false;
        this.autoScroll = true;
        this.timer = null;
        this.refreshInterval = 3000;
    }

    setAutoRefresh(enabled) {
        this.autoRefresh = enabled;

        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }

        if (enabled) {
            this.timer = setInterval(() => this.refresh(), this.refreshInterval);
        }
    }

    async refresh() {
        try {
            const data = await apiCall(
                `/api/app/${this.appName}/logs?lines=${this.lines}&level=${this.level}`
            );

            const logOutput = document.getElementById('log-output');
            if (!logOutput) return;

            if (data.lines && data.lines.length > 0) {
                logOutput.textContent = data.lines.join('');
            } else if (data.error) {
                logOutput.textContent = `Error: ${data.error}`;
            } else {
                logOutput.textContent = 'No log entries';
            }

            if (this.autoScroll) {
                logOutput.scrollTop = logOutput.scrollHeight;
            }
        } catch (error) {
            console.error('Failed to refresh logs:', error);
        }
    }
}

// Registry form validation
function validateAppForm(form) {
    const name = form.querySelector('[name="name"]');
    const port = form.querySelector('[name="port"]');
    const path = form.querySelector('[name="path"]');
    const startCmd = form.querySelector('[name="start_cmd"]');
    const workdir = form.querySelector('[name="workdir"]');

    let valid = true;

    // Name validation
    if (name && !/^[a-zA-Z0-9_-]+$/.test(name.value)) {
        valid = false;
        name.style.borderColor = 'var(--color-error)';
    } else if (name) {
        name.style.borderColor = '';
    }

    // Port validation
    if (port) {
        const portNum = parseInt(port.value);
        if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
            valid = false;
            port.style.borderColor = 'var(--color-error)';
        } else {
            port.style.borderColor = '';
        }
    }

    // Required fields
    [path, startCmd, workdir].forEach(field => {
        if (field && !field.value.trim()) {
            valid = false;
            field.style.borderColor = 'var(--color-error)';
        } else if (field) {
            field.style.borderColor = '';
        }
    });

    return valid;
}

// Confirm dialog helper
function confirmAction(message) {
    return confirm(message);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Auto-hide flash messages after 5 seconds
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 300);
        }, 5000);
    });

    // Initialize dashboard poller if on dashboard page
    const appTable = document.getElementById('app-table');
    if (appTable) {
        const poller = new DashboardPoller();

        const autoRefreshCheckbox = document.getElementById('auto-refresh');
        const intervalSelect = document.getElementById('refresh-interval');

        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.addEventListener('change', () => {
                poller.setEnabled(autoRefreshCheckbox.checked);
            });
        }

        if (intervalSelect) {
            intervalSelect.addEventListener('change', () => {
                poller.setInterval(parseInt(intervalSelect.value));
            });
        }

        // Don't auto-start poller since we're doing full page refresh for now
        // poller.start();
    }
});
