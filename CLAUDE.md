# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code notification system that displays desktop notifications when Claude needs attention. It supports multiple concurrent Claude sessions with per-session persistent notifications and popup alerts. The system integrates with Claude Code via hooks configured in `settings.json`.

**Installation**: The project includes `claude-notify-install` CLI for automated setup. It configures hooks, installs systemd units, and enables socket activation. See "Installation" section below.

## Architecture (v2)

The system uses a clean three-tier architecture:

1. **Hook** (`src/claude_notify/hook/`) - Minimal forwarder that runs on every Claude event
   - Reads JSON from stdin (Claude hook data)
   - Captures environment variables (GNOME_TERMINAL_SCREEN, etc.)
   - Encodes two-blob wire format (custom metadata + Claude data)
   - Sends to daemon via Unix socket (fire-and-forget)
   - Returns immediately to avoid blocking Claude

2. **Tracker Library** (`src/claude_notify/tracker/`) - Reusable session tracking
   - `state.py` - Session state model with state machine (WORKING, NEEDS_ATTENTION, etc.)
   - `registry.py` - Multi-session registry with listener support
   - `events.py` - Hook event parser and state determination logic
   - `friendly_names.py` - Deterministic friendly name generator (adjective-noun)

3. **Daemon** (`src/claude_notify/daemon/`) - Persistent background process
   - `server.py` - Unix socket server for receiving hook messages
   - `main.py` - Main loop with session tracking and notification updates
   - Maintains session state across hook invocations
   - Updates persistent notifications in real-time
   - Handles cleanup on session end

4. **GNOME Integration** (`src/claude_notify/gnome/`) - Desktop notification interface
   - `notifications.py` - D-Bus interface to org.freedesktop.Notifications
   - Persistent notifications (critical urgency, never timeout)
   - Popup notifications (normal urgency, auto-dismiss)
   - Focus action buttons (click to focus terminal tab)

5. **Installation** (`src/claude_notify/install/`) - Automated setup utilities
   - `main.py` - CLI for install/uninstall operations
   - `hooks.py` - Hook configuration management for settings.json
   - `systemd.py` - Systemd unit file installation and management
   - `templates/` - Socket and service unit file templates

### Key Design Patterns

**Thin hook, persistent daemon**: The hook handler must return immediately to Claude (<100ms). All state, logic, and notification management lives in the daemon process.

**Unix socket IPC**: Hook communicates with daemon via Unix socket at `/run/user/$UID/claude-notify.sock`. Fire-and-forget pattern - hook never waits for response.

**Two-blob wire protocol**: Messages contain two newline-separated JSON blobs:
1. Custom metadata (version, timestamp, environment variables, Claude data size)
2. Raw Claude data (passed through unmodified)

**Friendly session names**: UUIDs are deterministically mapped to readable names like "bold-cat" or "swift-eagle" using hash-based selection from word lists.

**State machine**: Sessions transition through states (WORKING → NEEDS_ATTENTION) based on hook events. State changes trigger notification updates.

**D-Bus for all notification operations**: Uses `org.freedesktop.Notifications` interface for sending and closing notifications. No fallback methods - D-Bus is the only supported mechanism.

**Systemd socket activation**: The daemon uses socket activation - systemd listens on the Unix socket and starts the daemon on first connection. This provides automatic startup, restart on failure, and clean resource management.

## Installation

### Using the Installation CLI

The `claude-notify-install` command automates setup:

```bash
# Standard installation
uv run claude-notify-install install

# With autostart enabled (socket starts on login)
uv run claude-notify-install install --enable-autostart

# Development mode (uses 'uv run' for hook and daemon commands)
uv run claude-notify-install install --mode development
```

**What it does**:
1. Updates `~/.claude/settings.json` with hook configuration
2. Installs systemd units to `~/.config/systemd/user/`:
   - `claude-notify-daemon.socket` - Socket activation unit
   - `claude-notify-daemon.service` - Daemon service unit
3. Reloads systemd user daemon
4. Optionally enables socket for autostart

**Development vs Installed mode**:
- **development**: Hook command is `uv run --project /path/to/repo claude-notify-hook`
- **installed**: Hook command is `claude-notify-hook` (assumes package is installed)

### Uninstallation

```bash
uv run claude-notify-install uninstall
```

Stops services, removes hooks from settings.json, and deletes systemd units.

### Manual Setup

If you need to set up manually:

1. **Configure hooks**: Edit `~/.claude/settings.json` and add hook configuration for events: Notification, Stop, PreToolUse, PostToolUse, UserPromptSubmit

2. **Install systemd units**: Copy templates from `src/claude_notify/install/templates/` to `~/.config/systemd/user/`

3. **Reload systemd**: `systemctl --user daemon-reload`

4. **Start socket**: `systemctl --user start claude-notify-daemon.socket`

### Systemd Units

**Socket unit** (`claude-notify-daemon.socket`):
- Listens on `/run/user/$UID/claude-notify.sock`
- Socket mode 0600 (owner-only access)
- Triggers service on first connection

**Service unit** (`claude-notify-daemon.service`):
- Requires socket unit
- Type=simple with automatic restart
- Logs to systemd journal with identifier 'claude-notify'

**Checking status**:
```bash
# Socket status (should be listening)
systemctl --user status claude-notify-daemon.socket

# Service status (active when daemon running)
systemctl --user status claude-notify-daemon.service

# View logs
journalctl --user -u claude-notify-daemon.service -f
```

## Testing and Debugging

### Run test suite
```bash
# Run all unit tests (excludes E2E tests)
uv run pytest tests/ --ignore=tests/e2e -v

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_state.py -v

# Run integration tests
uv run pytest tests/test_integration.py -v

# Run with coverage
uv run pytest --cov=src/claude_notify --cov-report=term
```

### Run E2E tests with Docker

The project includes Docker-based E2E tests that simulate a complete environment:

```bash
# Build test image
docker build -t claude-test:latest -f docker/claude-test/Dockerfile .

# Run E2E tests
docker run --rm -v "$PWD:/app" claude-test:latest \
  pytest tests/e2e/test_hook_to_daemon.py -v

# Or use docker-compose
docker-compose -f docker/docker-compose.test.yml up --build
```

**E2E test coverage**:
- `tests/e2e/test_hook_to_daemon.py` - Full hook-to-daemon flow with mock Claude events
- `tests/e2e/test_notifications.py` - GNOME notification integration (requires X11/Wayland)

**CI/CD**: GitHub Actions workflow (`.github/workflows/ci.yml`) runs unit tests on every push and E2E tests on manual dispatch.

### Test hook manually
```bash
# Simulate a Claude Stop event (needs daemon running)
echo '{"hook_event_name": "Stop", "session_id": "test-123", "cwd": "'$(pwd)'", "message": "Test notification"}' | uv run claude-notify-hook

# Test hook with custom socket path
echo '{"hook_event_name": "PreToolUse", "session_id": "test-456", "cwd": "/tmp", "tool_name": "Bash"}' | SOCKET_PATH=/tmp/test.sock uv run claude-notify-hook
```

### Run daemon manually
```bash
# Run daemon in foreground with debug logging
uv run claude-notify-daemon --log-level DEBUG

# Use custom socket path
uv run claude-notify-daemon --socket /tmp/custom.sock

# Dump daemon state (send SIGUSR1)
pkill -SIGUSR1 -f claude-notify-daemon
```

### Test individual components
```bash
# Test friendly name generation
uv run python -c "from claude_notify.tracker.friendly_names import generate_friendly_name; print(generate_friendly_name('test-session-id'))"

# Test wire protocol encoding
uv run python -c "from claude_notify.hook.protocol import encode_hook_message; print(encode_hook_message({'test': 'data'}, {'TERM': 'xterm'}))"
```

## Configuration

### Installation Modes

The installation CLI supports two modes:

**Installed mode** (default):
- Hook command: `claude-notify-hook`
- Daemon command: `claude-notify-daemon`
- Use when package is installed via pip/uv to system or virtualenv

**Development mode** (`--mode development`):
- Hook command: `uv run --project /path/to/repo claude-notify-hook`
- Daemon command: `uv run --project /path/to/repo claude-notify-daemon`
- Use when working on the codebase, runs from source

### Claude Code Hook Configuration

The installation CLI automatically configures hooks in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Notification": [{"hooks": [{"type": "command", "command": "claude-notify-hook"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "claude-notify-hook"}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "claude-notify-hook"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "claude-notify-hook"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "claude-notify-hook"}]}]
  }
}
```

### Daemon Configuration

Command-line options for `claude-notify-daemon`:
- `--socket PATH` - Unix socket path (default: `/run/user/$UID/claude-notify.sock`)
- `--popup-delay SECONDS` - Delay before popup notification (default: 45.0)
- `--log-level LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

When using systemd socket activation, the socket path is managed by systemd (configured in the .socket unit file).

### Environment Variables

Hook captures these environment variables:
- `GNOME_TERMINAL_SCREEN` - Terminal tab UUID for focus functionality
- `TERM` - Terminal type
- `WINDOWID` - X11 window ID
- `DISPLAY` - X11 display
- `WAYLAND_DISPLAY` - Wayland display socket

## Runtime State

The daemon maintains all state in memory. No persistent state files are used in v2. Session state includes:
- Session ID and friendly name
- Current working directory
- Terminal UUID (from GNOME_TERMINAL_SCREEN)
- State (WORKING, NEEDS_ATTENTION, SESSION_LIMIT, API_ERROR)
- Current activity message
- Notification IDs (persistent and popup)
- Timestamps

**Daemon lifecycle with systemd**:
1. Socket unit starts on boot (if enabled) or manually
2. systemd listens on Unix socket at `/run/user/$UID/claude-notify.sock`
3. First hook event triggers daemon start via socket activation
4. Daemon receives file descriptor from systemd and begins accepting connections
5. Daemon continues running, processing hook events and managing notifications
6. If daemon crashes, systemd restarts it automatically (RestartSec=5)
7. Socket remains active even if daemon stops

## Platform Notes

**Wayland terminal focus**: Requires Window Calls GNOME extension (`org.gnome.Shell.Extensions.Windows` D-Bus interface). GNOME 41+ disabled direct window management APIs. See TERMINAL_FOCUS_METHODS.md for technical details.

**X11 tools (wmctrl, xdotool)**: Not compatible with Wayland. Do not add fallback code using these tools.

## Dependencies

### System Dependencies (daemon only)

Required for daemon D-Bus functionality:
- `python3-dbus` - D-Bus Python bindings
- `python3-gi` - GObject introspection for GLib

Install: `sudo apt install python3-dbus python3-gi`

### Python Dependencies

The project uses `pyproject.toml` with optional dependency groups:
- **daemon**: `dbus-python`, `PyGObject` (for notification functionality)
- **dev**: `pytest`, `pytest-asyncio` (for testing)

Install: `uv sync --extra daemon --extra dev`

### Runtime Dependencies

- Python 3.11+
- GNOME desktop with D-Bus notification support
- `/run/user/$UID/` directory for socket (provided by systemd on modern Linux)

## Important Implementation Notes

### Hook Design
- Hook receives JSON via stdin with fields: `hook_event_name`, `message`, `session_id`, `cwd`, `tool_name`, etc.
- Hook must return within 100ms to avoid blocking Claude
- Fire-and-forget socket communication - no response waited
- Captures environment at hook invocation time (terminal UUID, display info)

### Wire Protocol
- Two-blob format: custom metadata (line 1) + raw Claude data (line 2)
- Custom blob includes protocol version, timestamp, environment, and Claude data size
- Allows daemon to validate message integrity and parse environment
- Forward-compatible: version field enables protocol evolution

### Session Tracking
- Sessions auto-register on first event
- Friendly names are deterministic (same UUID = same name)
- State transitions trigger notification updates
- Session cleanup dismisses all notifications

### Notifications
- Persistent notifications use critical urgency (urgency=2) to prevent auto-dismiss
- Popup notifications use normal urgency (urgency=1) with timeout
- All D-Bus operations use `dbus.SessionBus()`, not system bus
- Action buttons use format `"action_id:session_id", "Button Label"`
- Focus functionality requires terminal UUID from GNOME_TERMINAL_SCREEN

### Testing
- All components have unit tests with mocked D-Bus
- Integration tests use real Unix sockets in temp directories
- E2E tests use Docker to simulate complete environment with mock Claude
- Run with `uv run pytest` - no system dependencies needed for unit tests
- Mock-based testing allows CI/CD without GNOME desktop
- GitHub Actions CI runs unit tests on Python 3.11, 3.12, 3.13
- E2E tests available via manual workflow dispatch

### Installation
- `claude-notify-install` CLI automates setup process
- Hooks are added to `~/.claude/settings.json` atomically (write to temp, then rename)
- Systemd units use template substitution for daemon command
- Socket activation requires systemd user session
- Development mode uses `uv run --project` to run from source
- Installed mode assumes package is installed and uses entry points directly
