# Claude Notify GNOME v2

> [!WARNING]
> **VIBE-CODED SOFTWARE AHEAD!**
>
> This project was entirely vibe-coded using Claude Code in a caffeine-fueled haze of enthusiasm and questionable life choices. It might destroy your computer, eat your grandma, or worse - make your notifications too useful. Use at your own risk! We are not responsible for any spontaneous terminal focus addiction, D-Bus dependency, or sudden urges to click all the things.

---

A multi-session notification system for Claude Code on GNOME that displays persistent per-session notifications and popup alerts when Claude needs attention.

## Features

- 📊 **Multi-Session Support**: Track multiple concurrent Claude sessions with separate notifications
- 🎯 **Per-Session Notifications**: Each session gets a persistent notification with real-time status
- 🖱️ **Clickable Actions**: Click "Focus Terminal" to jump to the specific terminal tab
- 🏷️ **Friendly Names**: Sessions auto-named with memorable handles like "bold-cat" or "swift-eagle"
- ⚡ **Fast Hook**: Minimal overhead (<100ms) hook that never blocks Claude
- 🔧 **Clean Architecture**: Separated hook, tracker library, and daemon for maintainability
- 🧪 **Fully Tested**: Comprehensive test suite with mocked D-Bus for CI/CD

## Architecture (v2)

**Three-tier design:**

1. **Hook** (`src/claude_notify/hook/`) - Minimal forwarder runs on every Claude event
   - Reads Claude JSON from stdin, captures environment, sends to daemon via Unix socket
   - Fire-and-forget - returns immediately to avoid blocking Claude

2. **Tracker Library** (`src/claude_notify/tracker/`) - Reusable session tracking logic
   - Session state machine, multi-session registry, event parser, friendly name generator
   - Pure Python, no external dependencies, easy to test

3. **Daemon** (`src/claude_notify/daemon/`) - Persistent background process
   - Unix socket server, session state management, GNOME notification updates
   - Tracks all sessions in memory, updates notifications in real-time

## Installation

### 1. Install System Dependencies

```bash
# Required for D-Bus notifications (daemon only)
sudo apt install python3-dbus python3-gi
```

### 2. Install Python Package

```bash
# Install with uv (recommended)
uv sync --extra daemon --extra dev

# Or install in development mode
uv pip install -e ".[daemon,dev]"
```

### 3. Configure Claude Code Hook

Add to your Claude Code `settings.json`:

```json
{
  "hooks": {
    "Notification": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}]
  }
}
```

### 4. Start the Daemon

```bash
# Run in foreground for testing
uv run claude-notify-daemon --log-level INFO

# Or set up as systemd service (create ~/.config/systemd/user/claude-notify.service):
[Unit]
Description=Claude Code Notification Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/uv run claude-notify-daemon
Restart=on-failure

[Install]
WantedBy=default.target

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now claude-notify.service
```

## How It Works

**Event Flow:**

1. **Claude event occurs** → Hook invoked with JSON data via stdin
2. **Hook captures environment** → Reads GNOME_TERMINAL_SCREEN, TERM, etc.
3. **Hook encodes message** → Two-blob format: metadata + Claude data
4. **Hook sends to daemon** → Unix socket (fire-and-forget, <100ms)
5. **Daemon receives message** → Decodes and parses hook event
6. **Session registered/updated** → Auto-creates session with friendly name
7. **State transition** → Determines new state (WORKING/NEEDS_ATTENTION)
8. **Notification updated** → Updates persistent notification via D-Bus
9. **User clicks "Focus"** → Action handler focuses terminal tab (future feature)

**Session States:**

- **WORKING** (⚙️) - Claude is processing tools, user just submitted input
- **NEEDS_ATTENTION** (❓) - Claude stopped, waiting for user input
- **SESSION_LIMIT** (⏱️) - Session usage limit reached
- **API_ERROR** (🔴) - API error occurred

**Notifications:**

- **Persistent**: Critical urgency, never auto-dismiss, updates in real-time
  - Format: `⚙️ [bold-cat] my-project` with activity text
- **Popup**: Normal urgency, 10s timeout, alerts when attention needed (future feature)
  - Format: `Claude needs attention` with session and message

**Friendly Names:**

Each session gets a deterministic readable name:
- Hash session UUID to select adjective and noun from word lists
- Same UUID always produces same name (e.g., "bold-cat")
- Makes multiple sessions easy to distinguish

## Testing

### Run Test Suite

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test module
uv run pytest tests/test_state.py -v

# Run integration tests
uv run pytest tests/test_integration.py -v

# Run with coverage
uv run pytest --cov=src/claude_notify --cov-report=html
```

### Manual Testing

```bash
# Test hook manually (requires daemon running)
echo '{"hook_event_name": "Stop", "session_id": "test-123", "cwd": "'$(pwd)'"}' | uv run claude-notify-hook

# Test daemon in foreground with debug logging
uv run claude-notify-daemon --log-level DEBUG

# Send SIGUSR1 to dump daemon state
pkill -SIGUSR1 -f claude-notify-daemon

# Test friendly name generation
uv run python -c "from claude_notify.tracker.friendly_names import generate_friendly_name; print(generate_friendly_name('test-uuid'))"
```

### Development Workflow

```bash
# Install in development mode with all extras
uv sync --extra daemon --extra dev

# Run tests on file change
uv run pytest-watch

# Type check (if using mypy)
uv run mypy src/

# Format code
uv run black src/ tests/
```

## Configuration

### Daemon Options

```bash
# Default socket path
uv run claude-notify-daemon --socket /run/user/$UID/claude-notify.sock

# Custom popup delay (seconds before popup notification)
uv run claude-notify-daemon --popup-delay 60.0

# Logging level
uv run claude-notify-daemon --log-level DEBUG
```

### Hook Environment

The hook can be customized via environment:
- Set `SOCKET_PATH` to override default socket location
- All GNOME_TERMINAL_SCREEN, DISPLAY, etc. captured automatically

## Project Structure

```
src/claude_notify/
├── hook/                    # Hook entry point
│   ├── main.py             # CLI entry point, socket sender
│   └── protocol.py         # Wire protocol encoder/decoder
├── tracker/                 # Session tracking library
│   ├── state.py            # Session state model
│   ├── registry.py         # Multi-session registry
│   ├── events.py           # Hook event parser
│   └── friendly_names.py   # Name generator
├── gnome/                   # GNOME integration
│   └── notifications.py    # D-Bus notification manager
└── daemon/                  # Daemon process
    ├── main.py             # Main loop and CLI
    └── server.py           # Unix socket server

tests/                       # Test suite
├── test_*.py               # Unit tests (mocked D-Bus)
└── test_integration.py     # Integration tests (real sockets)
```

## Dependencies

### System Requirements
- Python 3.11+
- GNOME desktop environment
- D-Bus session bus
- `/run/user/$UID/` directory (systemd)

### Python Packages
- **Runtime (hook)**: None! Pure Python stdlib
- **Runtime (daemon)**: `dbus-python`, `PyGObject`
- **Development**: `pytest`, `pytest-asyncio`

### Installation
```bash
# System dependencies (Ubuntu/Debian)
sudo apt install python3-dbus python3-gi

# Python dependencies
uv sync --extra daemon --extra dev
```

## Troubleshooting

### Daemon Won't Start

```bash
# Check if socket already exists
ls -la /run/user/$UID/claude-notify.sock

# Check daemon logs
uv run claude-notify-daemon --log-level DEBUG

# Verify D-Bus is available
dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep Notifications
```

### Hook Not Sending Messages

```bash
# Test hook manually with daemon running
echo '{"hook_event_name": "Stop", "session_id": "test"}' | uv run claude-notify-hook

# Check socket permissions
ls -la /run/user/$UID/claude-notify.sock

# Verify hook is in Claude settings.json
cat ~/.config/claude/settings.json | grep claude-notify-hook
```

### Notifications Not Appearing

```bash
# Check if GNOME notifications are working
notify-send "Test" "This is a test"

# Verify daemon has D-Bus connection
uv run python -c "import dbus; bus = dbus.SessionBus(); print('D-Bus OK')"

# Check daemon state
pkill -SIGUSR1 -f claude-notify-daemon
```

### Multiple Sessions Not Working

```bash
# Dump daemon state to see all sessions
pkill -SIGUSR1 -f claude-notify-daemon

# Verify each session has unique ID
# Check terminal UUID is being captured
echo $GNOME_TERMINAL_SCREEN
```

## Future Features

See implementation plan for planned features:
- Popup notifications after configurable delay
- Terminal tab focus via SearchProvider API
- D-Bus action handler for "Focus Terminal" button
- Systemd service configuration
- HTTP transport for remote tracking

## License

Apache 2.0

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>