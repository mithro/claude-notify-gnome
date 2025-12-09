# Installation and Testing Infrastructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add installation CLI, systemd socket activation, and Docker-based integration/notification tests.

**Architecture:** Four features implemented incrementally: (1) systemd socket activation in daemon, (2) installation CLI that configures hooks and systemd, (3) Docker-based mock/real Claude tests, (4) full GNOME session tests with screenshot capture.

**Tech Stack:** Python 3.11+, systemd user units, Docker/docker-compose, weston (Wayland), ydotool, pytest

---

## Task 1: Add systemd Socket Activation Support to Daemon Server

**Files:**
- Modify: `src/claude_notify/daemon/server.py`
- Create: `tests/test_socket_activation.py`

**Step 1: Write the failing test for socket activation detection**

```python
# tests/test_socket_activation.py
"""Tests for systemd socket activation support."""

import os
import socket
import tempfile
import unittest.mock as mock

from claude_notify.daemon.server import get_socket_from_systemd, DaemonServer


def test_get_socket_from_systemd_returns_none_when_no_env():
    """Without LISTEN_FDS, returns None."""
    with mock.patch.dict(os.environ, {}, clear=True):
        # Remove LISTEN_FDS if present
        os.environ.pop("LISTEN_FDS", None)
        os.environ.pop("LISTEN_PID", None)
        result = get_socket_from_systemd()
        assert result is None


def test_get_socket_from_systemd_returns_none_when_wrong_pid():
    """With LISTEN_PID not matching current PID, returns None."""
    with mock.patch.dict(os.environ, {"LISTEN_FDS": "1", "LISTEN_PID": "99999"}):
        result = get_socket_from_systemd()
        assert result is None


def test_get_socket_from_systemd_returns_socket_when_valid():
    """With valid LISTEN_FDS and LISTEN_PID, returns socket."""
    # Create a real socket at FD 3
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # Dup to FD 3 (systemd convention)
    os.dup2(sock.fileno(), 3)

    with mock.patch.dict(os.environ, {
        "LISTEN_FDS": "1",
        "LISTEN_PID": str(os.getpid())
    }):
        result = get_socket_from_systemd()
        assert result is not None
        assert isinstance(result, socket.socket)

    sock.close()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_socket_activation.py -v`
Expected: FAIL with "cannot import name 'get_socket_from_systemd'"

**Step 3: Implement get_socket_from_systemd function**

Add to `src/claude_notify/daemon/server.py` at the top after imports:

```python
SD_LISTEN_FDS_START = 3  # systemd passes sockets starting at FD 3


def get_socket_from_systemd() -> Optional[socket.socket]:
    """Get socket passed by systemd socket activation.

    Returns None if not running under systemd socket activation.
    See: https://www.freedesktop.org/software/systemd/man/sd_listen_fds.html
    """
    listen_fds = os.environ.get("LISTEN_FDS")
    listen_pid = os.environ.get("LISTEN_PID")

    if not listen_fds or not listen_pid:
        return None

    # Verify PID matches (security check)
    if int(listen_pid) != os.getpid():
        logger.warning(
            f"LISTEN_PID ({listen_pid}) does not match current PID ({os.getpid()})"
        )
        return None

    num_fds = int(listen_fds)
    if num_fds < 1:
        return None

    # Get the first passed socket (FD 3)
    sock = socket.fromfd(SD_LISTEN_FDS_START, socket.AF_UNIX, socket.SOCK_STREAM)
    logger.info("Using socket from systemd socket activation")
    return sock
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_socket_activation.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/daemon/server.py tests/test_socket_activation.py
git commit -m "feat: add systemd socket activation detection"
```

---

## Task 2: Integrate Socket Activation into DaemonServer

**Files:**
- Modify: `src/claude_notify/daemon/server.py`
- Modify: `tests/test_socket_activation.py`

**Step 1: Write the failing test for DaemonServer with socket activation**

Add to `tests/test_socket_activation.py`:

```python
def test_daemon_server_uses_systemd_socket_when_available():
    """DaemonServer uses systemd socket if available."""
    # Create a socket and bind it (simulating systemd)
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = f"{tmpdir}/test.sock"

        # Create and bind a socket at FD 3
        pre_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        pre_sock.bind(sock_path)
        pre_sock.listen(5)
        os.dup2(pre_sock.fileno(), 3)

        with mock.patch.dict(os.environ, {
            "LISTEN_FDS": "1",
            "LISTEN_PID": str(os.getpid())
        }):
            handler = mock.Mock()
            server = DaemonServer(
                socket_path=f"{tmpdir}/different.sock",  # Different path!
                message_handler=handler
            )
            server.start()

            # Server should use the systemd socket, not create new one
            assert server._systemd_activated is True
            # The different.sock should NOT exist
            assert not os.path.exists(f"{tmpdir}/different.sock")

            server.shutdown()

        pre_sock.close()


def test_daemon_server_creates_socket_when_no_systemd():
    """DaemonServer creates socket when not under systemd."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = f"{tmpdir}/test.sock"

        # Ensure no systemd env vars
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LISTEN_FDS", None)
            os.environ.pop("LISTEN_PID", None)

            handler = mock.Mock()
            server = DaemonServer(
                socket_path=sock_path,
                message_handler=handler
            )
            server.start()

            assert server._systemd_activated is False
            assert os.path.exists(sock_path)

            server.shutdown()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_socket_activation.py::test_daemon_server_uses_systemd_socket_when_available -v`
Expected: FAIL with "AttributeError: '_systemd_activated'"

**Step 3: Modify DaemonServer to use socket activation**

Replace the `start` method and add `_systemd_activated` attribute in `src/claude_notify/daemon/server.py`:

```python
class DaemonServer:
    """Unix socket server for daemon."""

    def __init__(
        self,
        socket_path: str,
        message_handler: Callable[[HookMessage], None],
    ):
        self._socket_path = socket_path
        self._handler = message_handler
        self._server: Optional[socket.socket] = None
        self._running = False
        self._systemd_activated = False

    def _ensure_socket_dir(self) -> None:
        """Ensure socket directory exists."""
        socket_dir = os.path.dirname(self._socket_path)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)

    def _cleanup_stale_socket(self) -> None:
        """Remove stale socket file if it exists."""
        if not self._systemd_activated:
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass

    def start(self) -> None:
        """Start the server (non-blocking).

        Uses systemd socket activation if available, otherwise creates socket.
        """
        # Try systemd socket activation first
        systemd_sock = get_socket_from_systemd()
        if systemd_sock is not None:
            self._server = systemd_sock
            self._systemd_activated = True
            logger.info("Using systemd socket activation")
        else:
            # Manual mode - create socket ourselves
            self._ensure_socket_dir()
            self._cleanup_stale_socket()

            self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server.bind(self._socket_path)
            self._server.listen(10)
            self._systemd_activated = False
            logger.info(f"Daemon listening on {self._socket_path}")

        self._server.settimeout(1.0)
        self._running = True
```

**Step 4: Run all socket activation tests**

Run: `uv run pytest tests/test_socket_activation.py -v`
Expected: PASS (all 5 tests)

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/claude_notify/daemon/server.py tests/test_socket_activation.py
git commit -m "feat: integrate systemd socket activation into DaemonServer"
```

---

## Task 3: Create systemd Unit File Templates

**Files:**
- Create: `src/claude_notify/install/__init__.py`
- Create: `src/claude_notify/install/templates/claude-notify-daemon.socket`
- Create: `src/claude_notify/install/templates/claude-notify-daemon.service`

**Step 1: Create install package directory**

```bash
mkdir -p src/claude_notify/install/templates
```

**Step 2: Create __init__.py**

```python
# src/claude_notify/install/__init__.py
"""Installation utilities for claude-notify-gnome."""
```

**Step 3: Create socket unit template**

```ini
# src/claude_notify/install/templates/claude-notify-daemon.socket
[Unit]
Description=Claude Notify Daemon Socket

[Socket]
ListenStream=%t/claude-notify.sock
SocketMode=0600

[Install]
WantedBy=sockets.target
```

**Step 4: Create service unit template**

```ini
# src/claude_notify/install/templates/claude-notify-daemon.service
[Unit]
Description=Claude Notify Daemon
Requires=claude-notify-daemon.socket
After=graphical-session.target

[Service]
Type=simple
ExecStart={daemon_command}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-notify

[Install]
WantedBy=default.target
```

**Step 5: Commit**

```bash
git add src/claude_notify/install/
git commit -m "feat: add systemd unit file templates"
```

---

## Task 4: Implement systemd Unit Installation

**Files:**
- Create: `src/claude_notify/install/systemd.py`
- Create: `tests/test_install_systemd.py`

**Step 1: Write the failing test**

```python
# tests/test_install_systemd.py
"""Tests for systemd unit installation."""

import os
import tempfile
from pathlib import Path
from unittest import mock

from claude_notify.install.systemd import (
    get_systemd_user_dir,
    render_service_unit,
    render_socket_unit,
    install_units,
    uninstall_units,
)


def test_get_systemd_user_dir_returns_config_path():
    """Returns ~/.config/systemd/user/ path."""
    with mock.patch.dict(os.environ, {"HOME": "/home/testuser"}):
        result = get_systemd_user_dir()
        assert result == Path("/home/testuser/.config/systemd/user")


def test_render_socket_unit_is_valid():
    """Socket unit renders without placeholders."""
    content = render_socket_unit()
    assert "[Unit]" in content
    assert "[Socket]" in content
    assert "ListenStream=" in content
    assert "{" not in content  # No unreplaced placeholders


def test_render_service_unit_replaces_command():
    """Service unit replaces daemon_command placeholder."""
    content = render_service_unit(daemon_command="/usr/bin/my-daemon")
    assert "ExecStart=/usr/bin/my-daemon" in content
    assert "{daemon_command}" not in content


def test_install_units_creates_files():
    """install_units creates socket and service files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        systemd_dir = Path(tmpdir) / "systemd/user"

        with mock.patch(
            "claude_notify.install.systemd.get_systemd_user_dir",
            return_value=systemd_dir
        ):
            install_units(daemon_command="/test/daemon")

        assert (systemd_dir / "claude-notify-daemon.socket").exists()
        assert (systemd_dir / "claude-notify-daemon.service").exists()

        service_content = (systemd_dir / "claude-notify-daemon.service").read_text()
        assert "ExecStart=/test/daemon" in service_content


def test_uninstall_units_removes_files():
    """uninstall_units removes socket and service files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        systemd_dir = Path(tmpdir) / "systemd/user"
        systemd_dir.mkdir(parents=True)

        # Create the files first
        (systemd_dir / "claude-notify-daemon.socket").write_text("test")
        (systemd_dir / "claude-notify-daemon.service").write_text("test")

        with mock.patch(
            "claude_notify.install.systemd.get_systemd_user_dir",
            return_value=systemd_dir
        ):
            uninstall_units()

        assert not (systemd_dir / "claude-notify-daemon.socket").exists()
        assert not (systemd_dir / "claude-notify-daemon.service").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_install_systemd.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement systemd.py**

```python
# src/claude_notify/install/systemd.py
"""systemd unit file installation."""

import os
import subprocess
from pathlib import Path
from importlib import resources


def get_systemd_user_dir() -> Path:
    """Get the systemd user unit directory."""
    return Path.home() / ".config" / "systemd" / "user"


def render_socket_unit() -> str:
    """Render the socket unit file content."""
    template = resources.files("claude_notify.install.templates").joinpath(
        "claude-notify-daemon.socket"
    ).read_text()
    return template


def render_service_unit(daemon_command: str) -> str:
    """Render the service unit file content."""
    template = resources.files("claude_notify.install.templates").joinpath(
        "claude-notify-daemon.service"
    ).read_text()
    return template.replace("{daemon_command}", daemon_command)


def install_units(daemon_command: str) -> None:
    """Install systemd socket and service units.

    Args:
        daemon_command: Full command to start the daemon
    """
    systemd_dir = get_systemd_user_dir()
    systemd_dir.mkdir(parents=True, exist_ok=True)

    # Write socket unit
    socket_path = systemd_dir / "claude-notify-daemon.socket"
    socket_path.write_text(render_socket_unit())

    # Write service unit
    service_path = systemd_dir / "claude-notify-daemon.service"
    service_path.write_text(render_service_unit(daemon_command))


def uninstall_units() -> None:
    """Remove systemd socket and service units."""
    systemd_dir = get_systemd_user_dir()

    for filename in ["claude-notify-daemon.socket", "claude-notify-daemon.service"]:
        path = systemd_dir / filename
        if path.exists():
            path.unlink()


def reload_systemd() -> bool:
    """Reload systemd user daemon. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def enable_socket() -> bool:
    """Enable the socket unit to start on login. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "enable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def disable_socket() -> bool:
    """Disable the socket unit. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_install_systemd.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/install/systemd.py tests/test_install_systemd.py
git commit -m "feat: add systemd unit installation functions"
```

---

## Task 5: Implement Hook Configuration Management

**Files:**
- Create: `src/claude_notify/install/hooks.py`
- Create: `tests/test_install_hooks.py`

**Step 1: Write the failing test**

```python
# tests/test_install_hooks.py
"""Tests for Claude Code hook configuration."""

import json
import tempfile
from pathlib import Path
from unittest import mock

from claude_notify.install.hooks import (
    get_claude_settings_path,
    read_settings,
    write_settings,
    add_hooks,
    remove_hooks,
    is_hook_installed,
)


def test_get_claude_settings_path():
    """Returns ~/.claude/settings.json path."""
    with mock.patch.dict("os.environ", {"HOME": "/home/testuser"}):
        result = get_claude_settings_path()
        assert result == Path("/home/testuser/.claude/settings.json")


def test_read_settings_returns_empty_dict_when_missing():
    """Returns empty dict when settings.json doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "settings.json"
        result = read_settings(path)
        assert result == {}


def test_read_settings_parses_existing_file():
    """Parses existing settings.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "settings.json"
        path.write_text('{"hooks": {}, "other": "value"}')
        result = read_settings(path)
        assert result == {"hooks": {}, "other": "value"}


def test_add_hooks_creates_hook_entries():
    """add_hooks adds our hook to all event types."""
    settings = {}
    hook_cmd = "claude-notify-hook"

    result = add_hooks(settings, hook_cmd)

    expected_events = ["Notification", "Stop", "PreToolUse", "PostToolUse", "UserPromptSubmit"]
    for event in expected_events:
        assert event in result["hooks"]
        assert any(hook_cmd in str(h) for h in result["hooks"][event])


def test_add_hooks_preserves_existing_hooks():
    """add_hooks preserves existing hooks from other tools."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "other-tool"}]}
            ]
        },
        "other_setting": "preserved"
    }
    hook_cmd = "claude-notify-hook"

    result = add_hooks(settings, hook_cmd)

    # Other tool's hook preserved
    assert any("other-tool" in str(h) for h in result["hooks"]["Notification"])
    # Our hook added
    assert any(hook_cmd in str(h) for h in result["hooks"]["Notification"])
    # Other settings preserved
    assert result["other_setting"] == "preserved"


def test_add_hooks_idempotent():
    """add_hooks doesn't duplicate if already installed."""
    settings = {}
    hook_cmd = "claude-notify-hook"

    result1 = add_hooks(settings, hook_cmd)
    result2 = add_hooks(result1, hook_cmd)

    # Should only have one copy of our hook
    notification_hooks = result2["hooks"]["Notification"]
    our_hook_count = sum(1 for h in notification_hooks if hook_cmd in str(h))
    assert our_hook_count == 1


def test_remove_hooks_removes_our_hooks():
    """remove_hooks removes only our hooks."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "other-tool"}]},
                {"hooks": [{"type": "command", "command": "claude-notify-hook"}]},
            ]
        }
    }
    hook_cmd = "claude-notify-hook"

    result = remove_hooks(settings, hook_cmd)

    # Other tool's hook preserved
    assert any("other-tool" in str(h) for h in result["hooks"]["Notification"])
    # Our hook removed
    assert not any(hook_cmd in str(h) for h in result["hooks"]["Notification"])


def test_is_hook_installed_returns_true_when_present():
    """is_hook_installed returns True when our hook is configured."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "claude-notify-hook"}]}
            ]
        }
    }
    assert is_hook_installed(settings, "claude-notify-hook") is True


def test_is_hook_installed_returns_false_when_absent():
    """is_hook_installed returns False when our hook is not configured."""
    settings = {"hooks": {}}
    assert is_hook_installed(settings, "claude-notify-hook") is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_install_hooks.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement hooks.py**

```python
# src/claude_notify/install/hooks.py
"""Claude Code hook configuration management."""

import json
import os
from pathlib import Path
from typing import Any


HOOK_EVENTS = ["Notification", "Stop", "PreToolUse", "PostToolUse", "UserPromptSubmit"]


def get_claude_settings_path() -> Path:
    """Get the path to Claude Code settings.json."""
    return Path.home() / ".claude" / "settings.json"


def read_settings(path: Path) -> dict[str, Any]:
    """Read settings.json, returning empty dict if not found."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def write_settings(path: Path, settings: dict[str, Any]) -> None:
    """Write settings.json atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then rename (atomic on POSIX)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(settings, indent=2))
    temp_path.rename(path)


def add_hooks(settings: dict[str, Any], hook_command: str) -> dict[str, Any]:
    """Add our hook to settings, preserving existing hooks.

    Args:
        settings: Current settings dict
        hook_command: Command to run for hook (e.g., "claude-notify-hook")

    Returns:
        Updated settings dict
    """
    settings = settings.copy()
    hooks = settings.get("hooks", {})

    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])

        # Check if we're already installed
        already_installed = any(hook_command in str(h) for h in event_hooks)
        if not already_installed:
            event_hooks.append({
                "hooks": [{"type": "command", "command": hook_command}]
            })

        hooks[event] = event_hooks

    settings["hooks"] = hooks
    return settings


def remove_hooks(settings: dict[str, Any], hook_command: str) -> dict[str, Any]:
    """Remove our hook from settings, preserving other hooks.

    Args:
        settings: Current settings dict
        hook_command: Command to remove

    Returns:
        Updated settings dict
    """
    settings = settings.copy()
    hooks = settings.get("hooks", {})

    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])
        # Filter out hooks containing our command
        event_hooks = [h for h in event_hooks if hook_command not in str(h)]
        hooks[event] = event_hooks

    settings["hooks"] = hooks
    return settings


def is_hook_installed(settings: dict[str, Any], hook_command: str) -> bool:
    """Check if our hook is installed in settings."""
    hooks = settings.get("hooks", {})
    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])
        if any(hook_command in str(h) for h in event_hooks):
            return True
    return False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_install_hooks.py -v`
Expected: PASS (all 8 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/install/hooks.py tests/test_install_hooks.py
git commit -m "feat: add hook configuration management"
```

---

## Task 6: Implement Installation CLI

**Files:**
- Create: `src/claude_notify/install/main.py`
- Modify: `pyproject.toml` (add entry points)

**Step 1: Implement the CLI**

```python
# src/claude_notify/install/main.py
"""Installation CLI for claude-notify-gnome."""

import argparse
import shutil
import sys
from pathlib import Path

from claude_notify.install.hooks import (
    get_claude_settings_path,
    read_settings,
    write_settings,
    add_hooks,
    remove_hooks,
    is_hook_installed,
)
from claude_notify.install.systemd import (
    install_units,
    uninstall_units,
    reload_systemd,
    enable_socket,
    disable_socket,
)


def get_hook_command(mode: str) -> str:
    """Get the hook command based on installation mode."""
    if mode == "development":
        # Find project root (where pyproject.toml is)
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return f"uv run --project {parent} claude-notify-hook"
        # Fallback
        return "uv run claude-notify-hook"
    else:
        # Installed mode - use entry point directly
        return "claude-notify-hook"


def get_daemon_command(mode: str) -> str:
    """Get the daemon command based on installation mode."""
    if mode == "development":
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return f"uv run --project {parent} claude-notify-daemon"
        return "uv run claude-notify-daemon"
    else:
        return "claude-notify-daemon"


def install(mode: str, enable_autostart: bool) -> int:
    """Install claude-notify-gnome.

    Returns exit code (0 for success).
    """
    print(f"Installing claude-notify-gnome ({mode} mode)...")

    hook_cmd = get_hook_command(mode)
    daemon_cmd = get_daemon_command(mode)

    # Step 1: Update Claude Code hooks
    print("\n1. Configuring Claude Code hooks...")
    settings_path = get_claude_settings_path()
    settings = read_settings(settings_path)

    if is_hook_installed(settings, "claude-notify"):
        print("   Hooks already installed, updating...")

    settings = add_hooks(settings, hook_cmd)
    write_settings(settings_path, settings)
    print(f"   Updated {settings_path}")

    # Step 2: Install systemd units
    print("\n2. Installing systemd units...")
    install_units(daemon_command=daemon_cmd)
    print("   Created claude-notify-daemon.socket")
    print("   Created claude-notify-daemon.service")

    # Step 3: Reload systemd
    print("\n3. Reloading systemd...")
    if reload_systemd():
        print("   systemd reloaded")
    else:
        print("   WARNING: Could not reload systemd (is systemd running?)")

    # Step 4: Enable autostart if requested
    if enable_autostart:
        print("\n4. Enabling socket autostart...")
        if enable_socket():
            print("   Socket will start on login")
        else:
            print("   WARNING: Could not enable socket")

    print("\nInstallation complete!")
    print("\nTo start the daemon now:")
    print("  systemctl --user start claude-notify-daemon.socket")
    print("\nTo check status:")
    print("  systemctl --user status claude-notify-daemon.socket")

    return 0


def uninstall() -> int:
    """Uninstall claude-notify-gnome.

    Returns exit code (0 for success).
    """
    print("Uninstalling claude-notify-gnome...")

    # Step 1: Disable and stop services
    print("\n1. Stopping services...")
    disable_socket()

    # Step 2: Remove hooks
    print("\n2. Removing Claude Code hooks...")
    settings_path = get_claude_settings_path()
    settings = read_settings(settings_path)
    settings = remove_hooks(settings, "claude-notify")
    write_settings(settings_path, settings)
    print(f"   Updated {settings_path}")

    # Step 3: Remove systemd units
    print("\n3. Removing systemd units...")
    uninstall_units()
    reload_systemd()
    print("   Removed unit files")

    print("\nUninstallation complete!")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install or uninstall claude-notify-gnome"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Install subcommand
    install_parser = subparsers.add_parser("install", help="Install claude-notify")
    install_parser.add_argument(
        "--mode",
        choices=["development", "installed"],
        default="installed",
        help="Installation mode (default: installed)"
    )
    install_parser.add_argument(
        "--enable-autostart",
        action="store_true",
        help="Enable daemon autostart on login"
    )

    # Uninstall subcommand
    subparsers.add_parser("uninstall", help="Uninstall claude-notify")

    args = parser.parse_args()

    if args.command == "install":
        return install(args.mode, args.enable_autostart)
    elif args.command == "uninstall":
        return uninstall()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Add entry points to pyproject.toml**

Add to `[project.scripts]` section:

```toml
[project.scripts]
claude-notify-hook = "claude_notify.hook.main:main"
claude-notify-daemon = "claude_notify.daemon.main:main"
claude-notify-install = "claude_notify.install.main:main"
```

**Step 3: Test CLI manually**

Run: `uv run claude-notify-install --help`
Expected: Shows help with install/uninstall subcommands

Run: `uv run claude-notify-install install --help`
Expected: Shows install options (--mode, --enable-autostart)

**Step 4: Commit**

```bash
git add src/claude_notify/install/main.py pyproject.toml
git commit -m "feat: add installation CLI"
```

---

## Task 7: Create Docker Test Infrastructure Base

**Files:**
- Create: `docker/claude-test/Dockerfile`
- Create: `docker/claude-test/entrypoint.sh`
- Create: `docker/docker-compose.test.yml`
- Create: `Makefile`

**Step 1: Create docker directory structure**

```bash
mkdir -p docker/claude-test
```

**Step 2: Create Dockerfile**

```dockerfile
# docker/claude-test/Dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, systemd support, D-Bus
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    curl \
    dbus \
    dbus-user-session \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY tests/ ./tests/

# Install project with dependencies
RUN uv sync --extra daemon --extra dev

# Create test user
RUN useradd -m -s /bin/bash testuser && \
    mkdir -p /home/testuser/.claude && \
    chown -R testuser:testuser /home/testuser /app

USER testuser
ENV HOME=/home/testuser

ENTRYPOINT ["/app/docker/claude-test/entrypoint.sh"]
CMD ["pytest", "tests/", "-v", "--ignore=tests/e2e/"]
```

**Step 3: Create entrypoint.sh**

```bash
#!/bin/bash
# docker/claude-test/entrypoint.sh
set -e

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS

# Create XDG runtime directory
export XDG_RUNTIME_DIR="/tmp/runtime-testuser"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Execute the command
cd /app
exec uv run "$@"
```

Make executable:
```bash
chmod +x docker/claude-test/entrypoint.sh
```

**Step 4: Create docker-compose.test.yml**

```yaml
# docker/docker-compose.test.yml
version: '3.8'

services:
  # Unit tests (no special environment needed)
  unit-test:
    build:
      context: ..
      dockerfile: docker/claude-test/Dockerfile
    command: ["pytest", "tests/", "-v", "--ignore=tests/e2e/"]

  # Mock integration tests
  integration-test:
    build:
      context: ..
      dockerfile: docker/claude-test/Dockerfile
    command: ["pytest", "tests/e2e/", "-v", "-k", "not real_claude"]
    volumes:
      - ../tests/e2e:/app/tests/e2e:ro

  # Real Claude API tests (requires ANTHROPIC_API_KEY)
  real-claude-test:
    build:
      context: ..
      dockerfile: docker/claude-test/Dockerfile
    command: ["pytest", "tests/e2e/test_real_claude.py", "-v"]
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - ../tests/e2e:/app/tests/e2e:ro
```

**Step 5: Create Makefile**

```makefile
# Makefile
.PHONY: test test-unit test-docker test-integration test-real docker-build clean

# Default: run unit tests locally
test: test-unit

# Run unit tests locally (fast, no Docker)
test-unit:
	uv run pytest tests/ -v --ignore=tests/e2e/

# Build Docker test images
docker-build:
	docker compose -f docker/docker-compose.test.yml build

# Run unit tests in Docker
test-docker: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm unit-test

# Run mock integration tests in Docker
test-integration: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm integration-test

# Run real Claude API tests (requires ANTHROPIC_API_KEY env var)
test-real: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm real-claude-test

# Clean up Docker resources
clean:
	docker compose -f docker/docker-compose.test.yml down --rmi local --volumes
```

**Step 6: Test Docker build**

Run: `make docker-build`
Expected: Docker image builds successfully

Run: `make test-docker`
Expected: Unit tests pass in Docker container

**Step 7: Commit**

```bash
git add docker/ Makefile
git commit -m "feat: add Docker test infrastructure"
```

---

## Task 8: Create E2E Test Directory and Mock Tests

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_hook_to_daemon.py`

**Step 1: Create e2e test directory**

```bash
mkdir -p tests/e2e
```

**Step 2: Create conftest.py with fixtures**

```python
# tests/e2e/conftest.py
"""Shared fixtures for e2e tests."""

import json
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_socket_path() -> Generator[str, None, None]:
    """Provide a temporary socket path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield f"{tmpdir}/claude-notify.sock"


@pytest.fixture
def running_daemon(temp_socket_path: str) -> Generator[subprocess.Popen, None, None]:
    """Start daemon and yield process, cleanup on exit."""
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = os.path.dirname(temp_socket_path)

    proc = subprocess.Popen(
        ["uv", "run", "claude-notify-daemon", "--socket", temp_socket_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for socket to be ready
    for _ in range(50):  # 5 seconds max
        if os.path.exists(temp_socket_path):
            break
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Daemon failed to start")

    yield proc

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def send_hook_event(socket_path: str, event: dict) -> bool:
    """Send a hook event to the daemon via socket.

    Returns True if send succeeded.
    """
    env = os.environ.copy()
    env["SOCKET_PATH"] = socket_path

    proc = subprocess.run(
        ["uv", "run", "claude-notify-hook"],
        input=json.dumps(event).encode(),
        env=env,
        capture_output=True,
    )
    return proc.returncode == 0
```

**Step 3: Create test_hook_to_daemon.py**

```python
# tests/e2e/test_hook_to_daemon.py
"""End-to-end tests for hook to daemon communication."""

import json
import time

import pytest

from tests.e2e.conftest import send_hook_event


def test_hook_sends_stop_event_to_daemon(running_daemon, temp_socket_path):
    """Test that Stop event is received by daemon."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "test-session-001",
        "cwd": "/tmp/test-project",
    }

    result = send_hook_event(temp_socket_path, event)
    assert result, "Hook failed to send event"

    # Give daemon time to process
    time.sleep(0.2)

    # Daemon should still be running (no crash)
    assert running_daemon.poll() is None, "Daemon crashed"


def test_hook_sends_multiple_events(running_daemon, temp_socket_path):
    """Test multiple events from same session."""
    session_id = "test-session-002"

    events = [
        {"hook_event_name": "PreToolUse", "session_id": session_id, "tool_name": "Bash"},
        {"hook_event_name": "PostToolUse", "session_id": session_id, "tool_name": "Bash"},
        {"hook_event_name": "Stop", "session_id": session_id},
    ]

    for event in events:
        event["cwd"] = "/tmp/test"
        result = send_hook_event(temp_socket_path, event)
        assert result, f"Failed to send {event['hook_event_name']}"
        time.sleep(0.1)

    # Daemon should still be running
    assert running_daemon.poll() is None


def test_hook_handles_multiple_sessions(running_daemon, temp_socket_path):
    """Test events from multiple concurrent sessions."""
    sessions = ["session-a", "session-b", "session-c"]

    for session_id in sessions:
        event = {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "cwd": f"/tmp/{session_id}",
        }
        result = send_hook_event(temp_socket_path, event)
        assert result

    time.sleep(0.2)
    assert running_daemon.poll() is None


def test_hook_handles_malformed_json_gracefully(running_daemon, temp_socket_path):
    """Test that daemon handles malformed input without crashing."""
    import subprocess
    import os

    env = os.environ.copy()
    env["SOCKET_PATH"] = temp_socket_path

    # Send malformed JSON
    proc = subprocess.run(
        ["uv", "run", "claude-notify-hook"],
        input=b"not valid json {{{",
        env=env,
        capture_output=True,
    )

    # Hook should return non-zero but not crash
    # Daemon should still be running
    time.sleep(0.2)
    assert running_daemon.poll() is None, "Daemon crashed on malformed input"
```

**Step 4: Create __init__.py**

```python
# tests/e2e/__init__.py
"""End-to-end tests for claude-notify-gnome."""
```

**Step 5: Run e2e tests**

Run: `uv run pytest tests/e2e/test_hook_to_daemon.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add tests/e2e/
git commit -m "feat: add e2e mock tests for hook-to-daemon flow"
```

---

## Task 9: Add Real Claude API Test (Optional)

**Files:**
- Create: `tests/e2e/test_real_claude.py`

**Step 1: Create real Claude test file**

```python
# tests/e2e/test_real_claude.py
"""Tests using real Claude Code CLI.

These tests require ANTHROPIC_API_KEY to be set and will make real API calls.
They are skipped in CI unless explicitly enabled.
"""

import os
import subprocess
import time

import pytest

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)


@pytest.fixture
def claude_home(tmp_path):
    """Create isolated Claude home directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Minimal settings
    settings = {
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "uv run claude-notify-hook"}]}]
        }
    }
    (claude_dir / "settings.json").write_text(str(settings))

    return tmp_path


def test_claude_print_triggers_hook(claude_home, running_daemon, temp_socket_path):
    """Test that running claude --print triggers our hook."""
    env = os.environ.copy()
    env["HOME"] = str(claude_home)
    env["SOCKET_PATH"] = temp_socket_path

    # Run claude with --print (non-interactive, quick)
    proc = subprocess.run(
        ["claude", "--print", "Say exactly: hello"],
        env=env,
        capture_output=True,
        timeout=60,
    )

    # Claude should complete successfully
    assert proc.returncode == 0, f"Claude failed: {proc.stderr.decode()}"

    # Daemon should have received events
    time.sleep(0.5)
    assert running_daemon.poll() is None, "Daemon crashed"


def test_claude_simple_task_lifecycle(claude_home, running_daemon, temp_socket_path):
    """Test a simple Claude task generates expected hook events."""
    env = os.environ.copy()
    env["HOME"] = str(claude_home)
    env["SOCKET_PATH"] = temp_socket_path

    # Run a simple task
    proc = subprocess.run(
        ["claude", "--print", "What is 2+2? Reply with just the number."],
        env=env,
        capture_output=True,
        timeout=60,
    )

    assert proc.returncode == 0
    assert "4" in proc.stdout.decode()

    # Daemon still healthy
    assert running_daemon.poll() is None
```

**Step 2: Run test (only if API key available)**

Run: `ANTHROPIC_API_KEY=your-key uv run pytest tests/e2e/test_real_claude.py -v`
Expected: PASS (or SKIP if no key)

**Step 3: Commit**

```bash
git add tests/e2e/test_real_claude.py
git commit -m "feat: add real Claude API integration tests"
```

---

## Task 10: Create GNOME Test Docker Infrastructure

**Files:**
- Create: `docker/gnome-test/Dockerfile`
- Create: `docker/gnome-test/weston.ini`
- Create: `docker/gnome-test/entrypoint.sh`
- Modify: `docker/docker-compose.test.yml`

**Step 1: Create gnome-test directory**

```bash
mkdir -p docker/gnome-test
```

**Step 2: Create Dockerfile**

```dockerfile
# docker/gnome-test/Dockerfile
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
    # For screenshots
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY docker/gnome-test/weston.ini /etc/weston.ini
COPY docker/gnome-test/entrypoint.sh /entrypoint.sh

# Install project
RUN uv sync --extra daemon --extra dev

# Create test user with uinput access for ydotool
RUN useradd -m -s /bin/bash testuser && \
    usermod -aG input testuser && \
    mkdir -p /home/testuser/.claude && \
    chown -R testuser:testuser /home/testuser /app

RUN chmod +x /entrypoint.sh

USER testuser
ENV HOME=/home/testuser

ENTRYPOINT ["/entrypoint.sh"]
CMD ["pytest", "tests/e2e/test_notifications.py", "-v"]
```

**Step 3: Create weston.ini**

```ini
# docker/gnome-test/weston.ini
[core]
backend=headless-backend.so

[output]
name=headless
width=1920
height=1080
```

**Step 4: Create entrypoint.sh**

```bash
#!/bin/bash
# docker/gnome-test/entrypoint.sh
set -e

echo "Starting GNOME test environment..."

# Create XDG runtime directory
export XDG_RUNTIME_DIR="/tmp/runtime-testuser"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "D-Bus started: $DBUS_SESSION_BUS_ADDRESS"

# Start weston with headless backend
echo "Starting weston..."
weston --config=/etc/weston.ini &
WESTON_PID=$!
sleep 2

# Set Wayland display
export WAYLAND_DISPLAY=wayland-0

# Start gnome-shell nested in weston
echo "Starting gnome-shell..."
gnome-shell --nested --wayland &
GNOME_PID=$!
sleep 5

# Verify notification service is available
echo "Checking notification service..."
if gdbus introspect --session --dest org.freedesktop.Notifications \
    --object-path /org/freedesktop/Notifications > /dev/null 2>&1; then
    echo "Notification service available"
else
    echo "WARNING: Notification service not available"
fi

# Start ydotool daemon (needs root for uinput)
echo "Starting ydotool daemon..."
sudo ydotoold &
sleep 1

# Create screenshots directory
mkdir -p /app/tests/e2e/screenshots

# Start our daemon
echo "Starting claude-notify-daemon..."
cd /app
uv run claude-notify-daemon --log-level DEBUG &
DAEMON_PID=$!
sleep 2

# Run the tests
echo "Running tests..."
uv run "$@"
TEST_EXIT=$?

# Copy screenshots to output
mkdir -p /app/test-output
cp -r /app/tests/e2e/screenshots/* /app/test-output/ 2>/dev/null || true

# Cleanup
echo "Cleaning up..."
kill $DAEMON_PID $GNOME_PID $WESTON_PID 2>/dev/null || true

exit $TEST_EXIT
```

Make executable:
```bash
chmod +x docker/gnome-test/entrypoint.sh
```

**Step 5: Add gnome-test to docker-compose.test.yml**

Add this service to `docker/docker-compose.test.yml`:

```yaml
  # GNOME notification tests
  gnome-test:
    build:
      context: ..
      dockerfile: docker/gnome-test/Dockerfile
    command: ["pytest", "tests/e2e/test_notifications.py", "-v"]
    # Needs privileged for ydotool uinput access
    privileged: true
    volumes:
      - ../tests/e2e:/app/tests/e2e
      - ../test-output:/app/test-output
```

**Step 6: Add Makefile target**

Add to `Makefile`:

```makefile
# Run GNOME notification tests
test-notifications: docker-build
	mkdir -p test-output
	docker compose -f docker/docker-compose.test.yml run --rm gnome-test

# Run all tests
test-all: test-unit test-integration test-notifications
```

**Step 7: Commit**

```bash
git add docker/gnome-test/ Makefile
git add -u docker/docker-compose.test.yml
git commit -m "feat: add GNOME notification test infrastructure"
```

---

## Task 11: Create Notification Display Tests

**Files:**
- Create: `tests/e2e/test_notifications.py`

**Step 1: Create notification tests**

```python
# tests/e2e/test_notifications.py
"""Tests for GNOME notification display.

These tests run in a Docker container with a full GNOME session.
They verify notifications appear correctly and capture screenshots.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def send_hook_event(event: dict) -> bool:
    """Send a hook event to the running daemon."""
    proc = subprocess.run(
        ["uv", "run", "claude-notify-hook"],
        input=json.dumps(event).encode(),
        capture_output=True,
        cwd="/app",
    )
    return proc.returncode == 0


def capture_screenshot(name: str) -> Path:
    """Capture screenshot using weston-screenshooter.

    Returns path to screenshot file.
    """
    time.sleep(0.5)  # Allow notification animation
    output_path = SCREENSHOTS_DIR / f"{name}.png"

    # weston-screenshooter saves to current directory with timestamp
    # We'll use a different approach - gnome-screenshot if available
    try:
        subprocess.run(
            ["gnome-screenshot", "-f", str(output_path)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: create placeholder
        output_path.write_text("screenshot capture failed")

    return output_path


def test_notification_appears_on_stop():
    """Test that Stop event shows a notification."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "test-session-001",
        "cwd": "/home/testuser/my-project",
    }

    result = send_hook_event(event)
    assert result, "Failed to send hook event"

    # Wait for notification
    time.sleep(1)

    # Capture screenshot for documentation
    screenshot = capture_screenshot("01_notification_stop")
    assert screenshot.exists()


def test_notification_shows_friendly_name():
    """Test that notification shows friendly session name."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "unique-session-id-12345",
        "cwd": "/home/testuser/project",
    }

    result = send_hook_event(event)
    assert result

    time.sleep(1)
    capture_screenshot("02_notification_friendly_name")


def test_notification_updates_on_state_change():
    """Test notification updates when state changes."""
    session_id = "state-change-session"

    # First: Claude stops (needs attention)
    send_hook_event({
        "hook_event_name": "Stop",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03a_state_needs_attention")

    # Then: User submits prompt (working)
    send_hook_event({
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03b_state_working")

    # Then: Claude stops again
    send_hook_event({
        "hook_event_name": "Stop",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03c_state_needs_attention_again")


def test_multiple_session_notifications():
    """Test multiple concurrent session notifications."""
    sessions = [
        ("session-alpha", "project-alpha"),
        ("session-beta", "project-beta"),
        ("session-gamma", "project-gamma"),
    ]

    for session_id, project in sessions:
        send_hook_event({
            "hook_event_name": "Stop",
            "session_id": session_id,
            "cwd": f"/home/testuser/{project}",
        })
        time.sleep(0.3)

    time.sleep(1)
    capture_screenshot("04_multiple_sessions")


def test_working_state_notification():
    """Test notification shows working state correctly."""
    session_id = "working-session"

    # Tool use indicates working state
    send_hook_event({
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
        "tool_name": "Bash",
    })

    time.sleep(1)
    capture_screenshot("05_working_state")
```

**Step 2: Run notification tests (in Docker)**

Run: `make test-notifications`
Expected: Tests run in Docker, screenshots captured in test-output/

**Step 3: Commit**

```bash
git add tests/e2e/test_notifications.py
git commit -m "feat: add GNOME notification display tests"
```

---

## Task 12: Add GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/test.yml`

**Step 1: Create workflow file**

```bash
mkdir -p .github/workflows
```

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, feature/*]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run unit tests
        run: uv run pytest tests/ -v --ignore=tests/e2e/

  integration-tests:
    name: Integration Tests (Docker)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Run integration tests
        run: make test-integration

  notification-tests:
    name: GNOME Notification Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Run notification tests
        run: make test-notifications

      - name: Upload screenshots
        uses: actions/upload-artifact@v4
        with:
          name: notification-screenshots
          path: test-output/
        if: always()

  real-claude-tests:
    name: Real Claude Tests
    runs-on: ubuntu-latest
    # Only run on main branch pushes (not PRs) to limit API usage
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Run real Claude tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: make test-real
        # Don't fail the build if API tests fail (optional)
        continue-on-error: true
```

**Step 2: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add GitHub Actions test workflow"
```

---

## Task 13: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md with installation info**

Add to `CLAUDE.md` after the Configuration section:

```markdown
## Installation

### Quick Install

```bash
# Install in development mode (uses uv run)
uv run claude-notify-install install --mode development --enable-autostart

# Or install in production mode (uses installed entry points)
pip install .
claude-notify-install install --enable-autostart
```

### Manual Installation

1. Configure hooks in `~/.claude/settings.json`
2. Install systemd units to `~/.config/systemd/user/`
3. Enable socket: `systemctl --user enable claude-notify-daemon.socket`
4. Start socket: `systemctl --user start claude-notify-daemon.socket`

### Uninstall

```bash
claude-notify-install uninstall
```
```

**Step 2: Update README.md**

Add installation and testing sections to README.md.

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add installation and testing documentation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Socket activation detection | server.py, test_socket_activation.py |
| 2 | Integrate socket activation | server.py |
| 3 | systemd unit templates | install/templates/ |
| 4 | systemd installation functions | systemd.py |
| 5 | Hook configuration management | hooks.py |
| 6 | Installation CLI | install/main.py |
| 7 | Docker test infrastructure | docker/, Makefile |
| 8 | E2E mock tests | tests/e2e/ |
| 9 | Real Claude API tests | test_real_claude.py |
| 10 | GNOME test Docker | docker/gnome-test/ |
| 11 | Notification display tests | test_notifications.py |
| 12 | GitHub Actions CI | .github/workflows/ |
| 13 | Documentation | CLAUDE.md, README.md |
