# Installation and Testing Infrastructure Design

**Date:** 2025-12-07
**Status:** Draft
**Branch:** TBD (new worktree)

## Overview

This document covers four features to be added to claude-notify-gnome v2:

1. **Installation system** - CLI tool to configure hooks and systemd units
2. **Daemon auto-start** - systemd socket activation for on-demand daemon startup
3. **Claude Code integration tests** - Docker-based tests with real/mock Claude
4. **GNOME notification tests** - Full GNOME session in Docker with screenshot capture

## Feature 1: Installation System

### Architecture

```
src/claude_notify/
├── install/
│   ├── __init__.py
│   ├── main.py          # CLI entry point: claude-notify-install
│   ├── hooks.py         # Hook configuration management
│   ├── systemd.py       # systemd unit file generation/installation
│   └── templates/       # Unit file templates
│       ├── claude-notify-daemon.service
│       └── claude-notify-daemon.socket
```

### Entry Points

```toml
[project.scripts]
claude-notify-install = "claude_notify.install.main:main"
claude-notify-uninstall = "claude_notify.install.main:uninstall"
```

### Installation Flow

1. **Detect mode**: Ask user "development" (uv run) or "installed" (entry point)
2. **Generate hook command**: Based on mode, create appropriate command string
3. **Update settings.json**:
   - Read existing `~/.claude/settings.json`
   - For each hook event (Notification, Stop, PreToolUse, PostToolUse, UserPromptSubmit), append our hook to existing array
   - Preserve all existing hooks from other tools
   - Write back atomically (write to temp file, then rename)
4. **Install systemd units**:
   - Write `claude-notify-daemon.socket` to `~/.config/systemd/user/`
   - Write `claude-notify-daemon.service` to `~/.config/systemd/user/`
   - Run `systemctl --user daemon-reload`
5. **Optionally enable auto-start**:
   - Ask user if daemon should start on login
   - If yes: `systemctl --user enable claude-notify-daemon.socket`
6. **Verify installation**:
   - Check socket unit loads: `systemctl --user status claude-notify-daemon.socket`
   - Report success/failure

### Uninstall Flow

1. Remove claude-notify hooks from settings.json (preserve other hooks)
2. Stop and disable systemd units
3. Remove unit files from ~/.config/systemd/user/
4. Run daemon-reload

### Hook Merging Strategy

When adding hooks to settings.json:

```python
def merge_hooks(existing: dict, our_hook: str) -> dict:
    """Add our hook to each event type, preserving existing hooks."""
    events = ["Notification", "Stop", "PreToolUse", "PostToolUse", "UserPromptSubmit"]

    hooks = existing.get("hooks", {})
    for event in events:
        event_hooks = hooks.get(event, [])
        # Check if we're already installed
        if not any(our_hook in str(h) for h in event_hooks):
            event_hooks.append({
                "hooks": [{"type": "command", "command": our_hook}]
            })
        hooks[event] = event_hooks

    existing["hooks"] = hooks
    return existing
```

## Feature 2: systemd Socket Activation

### How It Works

Instead of the daemon running constantly:
1. systemd creates and listens on the Unix socket
2. When first connection arrives, systemd starts the daemon
3. Passes the already-open socket file descriptor to the daemon
4. Daemon handles the connection and continues running
5. No race conditions - systemd handles all synchronization

### Unit Files

**~/.config/systemd/user/claude-notify-daemon.socket**:
```ini
[Unit]
Description=Claude Notify Daemon Socket

[Socket]
ListenStream=%t/claude-notify.sock
SocketMode=0600

[Install]
WantedBy=sockets.target
```

**~/.config/systemd/user/claude-notify-daemon.service**:
```ini
[Unit]
Description=Claude Notify Daemon
Requires=claude-notify-daemon.socket
After=graphical-session.target

[Service]
Type=simple
ExecStart={hook_command}
Restart=on-failure
RestartSec=5
# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-notify

[Install]
WantedBy=default.target
```

Note: `{hook_command}` is templated based on install mode (uv run vs installed).

### Daemon Changes Required

The daemon's `server.py` must detect socket activation:

```python
import socket
import os

def get_server_socket(socket_path: str) -> socket.socket:
    """Get socket - either from systemd or create new."""
    # Check for systemd socket activation
    # LISTEN_FDS is set by systemd when passing sockets
    listen_fds = os.environ.get('LISTEN_FDS')
    if listen_fds and int(listen_fds) > 0:
        # Socket passed by systemd (FD 3 is first passed socket)
        # FD 0=stdin, 1=stdout, 2=stderr, 3=first passed socket
        sock = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
        sock.set_inheritable(True)
        return sock

    # Manual mode - create socket ourselves
    # Remove existing socket if present
    if os.path.exists(socket_path):
        os.unlink(socket_path)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)
    sock.listen(5)
    return sock
```

This allows the daemon to work both:
- With systemd socket activation (production)
- Standalone for development/testing

### Socket Path

Default: `/run/user/$UID/claude-notify.sock`

The `%t` in the socket unit expands to `/run/user/$UID/` which is the XDG runtime directory.

## Feature 3: Claude Code Integration Tests

### Directory Structure

```
docker/
├── claude-test/
│   ├── Dockerfile           # Claude Code + test environment
│   └── entrypoint.sh        # Test runner script
├── docker-compose.test.yml  # Orchestrates test containers
Makefile                      # make test-integration, make test-e2e
tests/
├── integration/              # Existing unit/integration tests (no Docker)
└── e2e/
    ├── conftest.py           # pytest fixtures for Docker tests
    ├── test_hook_to_daemon.py    # Mock-based e2e tests
    └── test_real_claude.py       # Real Claude API tests (optional)
```

### Dockerfile: docker/claude-test/Dockerfile

```dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, systemd-user support, D-Bus
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    curl \
    systemd \
    dbus \
    dbus-user-session \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Install Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
COPY . /app
WORKDIR /app

# Install project with dependencies
RUN uv sync --extra daemon --extra dev

# Create test user with proper home directory
RUN useradd -m -s /bin/bash testuser
RUN mkdir -p /home/testuser/.claude
RUN chown -R testuser:testuser /home/testuser

USER testuser
WORKDIR /home/testuser

ENTRYPOINT ["/app/docker/claude-test/entrypoint.sh"]
```

### Test Modes

**Mock mode** (always runs, no API key needed):
```python
def test_hook_to_daemon_flow():
    """Test hook -> socket -> daemon flow with simulated events."""
    # Start daemon in background
    daemon = subprocess.Popen(["uv", "run", "claude-notify-daemon"])

    # Simulate Claude hook event
    event = {
        "hook_event_name": "Stop",
        "session_id": "test-session-123",
        "cwd": "/tmp/test-project"
    }

    proc = subprocess.run(
        ["uv", "run", "claude-notify-hook"],
        input=json.dumps(event),
        capture_output=True
    )

    assert proc.returncode == 0
    # Verify daemon received the event (check logs or state)
```

**Real API mode** (when `ANTHROPIC_API_KEY` is set):
```python
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"),
                    reason="No API key")
def test_real_claude_integration():
    """Test with actual Claude Code CLI."""
    # Run claude with a simple prompt that completes quickly
    proc = subprocess.run(
        ["claude", "--print", "Say hello"],
        capture_output=True,
        timeout=60
    )

    # Verify hooks fired and daemon processed them
    # Check daemon logs for session events
```

### Makefile Targets

```makefile
.PHONY: test-unit test-integration test-e2e test-e2e-real

# Unit tests (no Docker)
test-unit:
	uv run pytest tests/ -v --ignore=tests/e2e/

# Integration tests in Docker (mock mode)
test-integration:
	docker compose -f docker/docker-compose.test.yml run --rm claude-test-mock

# Integration tests with real Claude API
test-e2e-real:
	docker compose -f docker/docker-compose.test.yml run --rm \
		-e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) claude-test-real
```

### docker-compose.test.yml

```yaml
version: '3.8'

services:
  claude-test-mock:
    build:
      context: .
      dockerfile: docker/claude-test/Dockerfile
    command: ["pytest", "tests/e2e/test_hook_to_daemon.py", "-v"]
    volumes:
      - ./tests/e2e:/app/tests/e2e:ro

  claude-test-real:
    build:
      context: .
      dockerfile: docker/claude-test/Dockerfile
    command: ["pytest", "tests/e2e/test_real_claude.py", "-v"]
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - ./tests/e2e:/app/tests/e2e:ro
```

## Feature 4: GNOME Notification Tests

### Approach: Full GNOME Session in Docker

gnome-shell implements `org.freedesktop.Notifications` directly, so we need a full GNOME session. We run gnome-shell nested inside weston (headless backend).

### Directory Structure

```
docker/
├── gnome-test/
│   ├── Dockerfile           # Weston + GNOME + ydotool
│   ├── weston.ini           # Weston headless configuration
│   └── entrypoint.sh        # Start GNOME session, run tests
├── docker-compose.test.yml  # Adds gnome-test service
tests/
└── e2e/
    ├── test_notifications.py     # Notification display tests
    └── screenshots/              # Captured screenshots (gitignored)
docs/
└── images/                       # Curated screenshots for documentation
```

### Dockerfile: docker/gnome-test/Dockerfile

```dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Full GNOME session stack
RUN apt-get update && apt-get install -y \
    gnome-session \
    gnome-shell \
    gnome-settings-daemon \
    mutter \
    dbus-daemon \
    dbus-x11 \
    dbus-user-session \
    weston \
    ydotool \
    python3.12 \
    python3.12-venv \
    curl \
    # For headless GPU rendering
    libegl1-mesa \
    libgl1-mesa-dri \
    # Screenshot tools
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project
COPY . /app
WORKDIR /app

# Install project
RUN uv sync --extra daemon --extra dev

# Create test user
RUN useradd -m -s /bin/bash testuser
RUN usermod -aG input testuser  # For ydotool uinput access

# Weston config for headless
COPY docker/gnome-test/weston.ini /home/testuser/.config/weston.ini
RUN chown -R testuser:testuser /home/testuser

USER testuser
ENTRYPOINT ["/app/docker/gnome-test/entrypoint.sh"]
```

### weston.ini

```ini
[core]
backend=headless-backend.so
modules=screen-share.so

[output]
name=headless
width=1920
height=1080

[shell]
# Minimal shell for nested compositor
```

### entrypoint.sh

```bash
#!/bin/bash
set -e

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS

# Start weston with headless backend
XDG_RUNTIME_DIR=/tmp/runtime-testuser
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR
export XDG_RUNTIME_DIR

weston --config=/home/testuser/.config/weston.ini &
WESTON_PID=$!
sleep 2

# Set Wayland display for gnome-shell
export WAYLAND_DISPLAY=wayland-0

# Start gnome-shell nested inside weston
gnome-shell --nested --wayland &
GNOME_PID=$!
sleep 5  # Allow shell to fully initialize

# Verify gnome-shell is running and has D-Bus interface
gdbus introspect --session --dest org.freedesktop.Notifications \
    --object-path /org/freedesktop/Notifications || {
    echo "ERROR: Notification service not available"
    exit 1
}

# Start ydotool daemon for input injection (needs uinput)
sudo ydotoold &
sleep 1

# Start our daemon
cd /app
uv run claude-notify-daemon --log-level DEBUG &
DAEMON_PID=$!
sleep 2

# Run notification tests
uv run pytest tests/e2e/test_notifications.py -v --tb=short

# Capture screenshots are saved by tests
# Copy to output directory
mkdir -p /app/test-output
cp -r tests/e2e/screenshots/* /app/test-output/ 2>/dev/null || true

# Cleanup
kill $DAEMON_PID $GNOME_PID $WESTON_PID 2>/dev/null || true
```

### Test Implementation

```python
# tests/e2e/test_notifications.py
import subprocess
import time
import json
import os
from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

def send_hook_event(event: dict):
    """Send a hook event to the daemon."""
    proc = subprocess.run(
        ["uv", "run", "claude-notify-hook"],
        input=json.dumps(event).encode(),
        capture_output=True,
        cwd="/app"
    )
    assert proc.returncode == 0, f"Hook failed: {proc.stderr}"

def capture_screenshot(name: str):
    """Capture screenshot using weston-screenshooter."""
    time.sleep(0.5)  # Allow notification animation to complete
    output_path = SCREENSHOTS_DIR / f"{name}.png"
    subprocess.run(
        ["weston-screenshooter", str(output_path)],
        check=True
    )
    return output_path

def test_notification_appears_on_stop():
    """Test that stopping Claude shows a notification."""
    # Send Stop event (Claude needs attention)
    send_hook_event({
        "hook_event_name": "Stop",
        "session_id": "test-session-001",
        "cwd": "/home/testuser/project"
    })

    # Wait for notification to appear
    time.sleep(1)

    # Capture screenshot
    screenshot = capture_screenshot("notification_stop")
    assert screenshot.exists(), "Screenshot not captured"

def test_notification_updates_on_activity():
    """Test that notification updates when Claude starts working."""
    # First, create a session in NEEDS_ATTENTION state
    send_hook_event({
        "hook_event_name": "Stop",
        "session_id": "test-session-002",
        "cwd": "/home/testuser/project"
    })
    time.sleep(0.5)
    capture_screenshot("notification_before_activity")

    # Now simulate user input (Claude starts working)
    send_hook_event({
        "hook_event_name": "UserPromptSubmit",
        "session_id": "test-session-002",
        "cwd": "/home/testuser/project"
    })
    time.sleep(0.5)
    capture_screenshot("notification_after_activity")

def test_multiple_sessions():
    """Test multiple concurrent session notifications."""
    sessions = [
        ("session-a", "project-alpha"),
        ("session-b", "project-beta"),
        ("session-c", "project-gamma"),
    ]

    for session_id, project in sessions:
        send_hook_event({
            "hook_event_name": "Stop",
            "session_id": session_id,
            "cwd": f"/home/testuser/{project}"
        })
        time.sleep(0.3)

    time.sleep(1)
    capture_screenshot("notification_multiple_sessions")
```

### CI Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Run unit tests
        run: uv run pytest tests/ --ignore=tests/e2e/ -v

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run mock integration tests
        run: make test-integration

  notification-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run GNOME notification tests
        run: make test-notifications
      - name: Upload screenshots
        uses: actions/upload-artifact@v4
        with:
          name: notification-screenshots
          path: test-output/
        if: always()

  real-claude-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Run real Claude tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: make test-e2e-real
```

### Makefile Additions

```makefile
.PHONY: test-notifications

test-notifications:
	docker compose -f docker/docker-compose.test.yml run --rm gnome-test

# Build all test images
docker-build:
	docker compose -f docker/docker-compose.test.yml build

# Run all tests
test-all: test-unit test-integration test-notifications
```

## Summary

| Feature | Implementation | Key Files |
|---------|---------------|-----------|
| Installation | CLI tool with hook merging | `src/claude_notify/install/` |
| Auto-start | systemd socket activation | `.socket` and `.service` units |
| Claude tests | Docker + mock/real modes | `docker/claude-test/` |
| GNOME tests | weston + gnome-shell nested | `docker/gnome-test/` |

## Open Questions

1. **GNOME version**: Should we test on multiple GNOME versions (40, 42, 44, 46)?
2. **Screenshot curation**: Process for selecting screenshots for documentation?
3. **Flaky test handling**: Strategy for handling timing-sensitive notification tests?

## References

- [systemd Socket Activation](https://www.freedesktop.org/software/systemd/man/systemd.socket.html)
- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [weston headless backend](https://wayland.freedesktop.org/weston.html)
- [ydotool](https://github.com/ReimuNotMoe/ydotool)
