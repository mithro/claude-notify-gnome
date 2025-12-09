# Claude Notify GNOME v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-session notification system with persistent per-session notifications and popup alerts when Claude needs attention.

**Architecture:** Thin hook forwards events to persistent daemon via Unix socket. Daemon tracks session state and manages GNOME notifications via D-Bus. Libraries separated for reusability.

**Tech Stack:** Python 3.11+, D-Bus (dbus-python), GLib (PyGObject), Unix sockets

---

## Task 1: Project Structure Setup

**Files:**
- Create: `src/claude_notify/__init__.py`
- Create: `src/claude_notify/hook/__init__.py`
- Create: `src/claude_notify/tracker/__init__.py`
- Create: `src/claude_notify/gnome/__init__.py`
- Create: `src/claude_notify/daemon/__init__.py`
- Create: `tests/__init__.py`
- Create: `pyproject.toml`

**Step 1: Create directory structure**

```bash
mkdir -p src/claude_notify/{hook,tracker,gnome,daemon}
mkdir -p tests
touch src/claude_notify/__init__.py
touch src/claude_notify/hook/__init__.py
touch src/claude_notify/tracker/__init__.py
touch src/claude_notify/gnome/__init__.py
touch src/claude_notify/daemon/__init__.py
touch tests/__init__.py
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "claude-notify-gnome"
version = "2.0.0"
description = "Desktop notifications for Claude Code on GNOME"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}

dependencies = []

[project.optional-dependencies]
daemon = [
    "dbus-python>=1.3.2",
    "PyGObject>=3.42.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]

[project.scripts]
claude-notify-hook = "claude_notify.hook.main:main"
claude-notify-daemon = "claude_notify.daemon.main:main"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 3: Commit**

```bash
git add src/ tests/ pyproject.toml
git commit -m "feat: set up v2 project structure with library separation"
```

---

## Task 2: Friendly Session Names

**Files:**
- Create: `src/claude_notify/tracker/friendly_names.py`
- Create: `tests/test_friendly_names.py`

**Step 1: Write failing test**

```python
# tests/test_friendly_names.py
"""Tests for friendly session name generation."""

from claude_notify.tracker.friendly_names import generate_friendly_name


def test_generates_adjective_noun_format():
    """Name should be adjective-noun format."""
    name = generate_friendly_name("73b5e210-ec1a-4294-96e4-c2aecb2e1063")
    parts = name.split("-")
    assert len(parts) == 2
    assert len(parts[0]) > 0  # adjective
    assert len(parts[1]) > 0  # noun


def test_deterministic_for_same_uuid():
    """Same UUID should always produce same name."""
    uuid = "73b5e210-ec1a-4294-96e4-c2aecb2e1063"
    name1 = generate_friendly_name(uuid)
    name2 = generate_friendly_name(uuid)
    assert name1 == name2


def test_different_uuids_likely_different_names():
    """Different UUIDs should produce different names (with high probability)."""
    name1 = generate_friendly_name("73b5e210-ec1a-4294-96e4-c2aecb2e1063")
    name2 = generate_friendly_name("550e8400-e29b-41d4-a716-446655440000")
    assert name1 != name2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_friendly_names.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/tracker/friendly_names.py
"""Generate friendly session names from UUIDs."""

ADJECTIVES = [
    "bold", "swift", "cosmic", "bright", "calm", "eager", "fair", "gentle",
    "happy", "keen", "lively", "merry", "noble", "proud", "quick", "ready",
    "smart", "true", "vivid", "warm", "wise", "young", "zesty", "agile",
    "brave", "clear", "deft", "epic", "fresh", "grand", "humble", "ideal",
]

NOUNS = [
    "cat", "eagle", "dragon", "wolf", "bear", "hawk", "lion", "tiger",
    "fox", "owl", "raven", "shark", "whale", "deer", "horse", "falcon",
    "phoenix", "griffin", "panther", "cobra", "jaguar", "orca", "puma", "lynx",
    "badger", "otter", "crane", "heron", "swan", "viper", "raptor", "condor",
]


def generate_friendly_name(session_id: str) -> str:
    """
    Generate a deterministic friendly name from a session UUID.

    Args:
        session_id: UUID string (with or without dashes)

    Returns:
        Friendly name like "bold-cat" or "swift-eagle"
    """
    # Remove dashes and get clean hex string
    clean_id = session_id.replace("-", "")

    # Use first 8 chars for adjective, next 8 for noun
    adj_seed = int(clean_id[:8], 16)
    noun_seed = int(clean_id[8:16], 16)

    adjective = ADJECTIVES[adj_seed % len(ADJECTIVES)]
    noun = NOUNS[noun_seed % len(NOUNS)]

    return f"{adjective}-{noun}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_friendly_names.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/tracker/friendly_names.py tests/test_friendly_names.py
git commit -m "feat: add friendly session name generator"
```

---

## Task 3: Session State Model

**Files:**
- Create: `src/claude_notify/tracker/state.py`
- Create: `tests/test_state.py`

**Step 1: Write failing test**

```python
# tests/test_state.py
"""Tests for session state model."""

import time
from claude_notify.tracker.state import SessionState, State


def test_initial_state_is_working():
    """New sessions start in WORKING state."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
        terminal_uuid="550e8400-e29b-41d4-a716-446655440000",
    )
    assert session.state == State.WORKING


def test_transition_to_needs_attention():
    """Can transition from WORKING to NEEDS_ATTENTION."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    old_state = session.transition_to(State.NEEDS_ATTENTION)
    assert old_state == State.WORKING
    assert session.state == State.NEEDS_ATTENTION


def test_transition_to_working():
    """Can transition from NEEDS_ATTENTION to WORKING."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    session.transition_to(State.NEEDS_ATTENTION)
    old_state = session.transition_to(State.WORKING)
    assert old_state == State.NEEDS_ATTENTION
    assert session.state == State.WORKING


def test_same_state_transition_returns_none():
    """Transitioning to same state returns None (no change)."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    result = session.transition_to(State.WORKING)
    assert result is None


def test_activity_update():
    """Can update activity text."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    session.update_activity("Running tests...")
    assert session.activity == "Running tests..."


def test_friendly_name_generated():
    """Friendly name is auto-generated from session_id."""
    session = SessionState(
        session_id="73b5e210-ec1a-4294-96e4-c2aecb2e1063",
        cwd="/home/user/project",
    )
    assert "-" in session.friendly_name
    assert len(session.friendly_name) > 3
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/tracker/state.py
"""Session state model and state machine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

from .friendly_names import generate_friendly_name


class State(Enum):
    """Session states."""
    WORKING = "working"
    NEEDS_ATTENTION = "needs_attention"
    SESSION_LIMIT = "session_limit"
    API_ERROR = "api_error"


@dataclass
class SessionState:
    """State for a single Claude Code session."""

    session_id: str
    cwd: str
    terminal_uuid: Optional[str] = None
    state: State = State.WORKING
    activity: str = ""
    friendly_name: str = field(default="", init=False)
    persistent_notif_id: Optional[int] = None
    popup_notif_id: Optional[int] = None
    last_update: float = field(default_factory=time.time)
    needs_attention_since: Optional[float] = None

    def __post_init__(self):
        """Generate friendly name from session_id."""
        self.friendly_name = generate_friendly_name(self.session_id)

    def transition_to(self, new_state: State) -> Optional[State]:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to

        Returns:
            The old state if changed, None if already in that state
        """
        if self.state == new_state:
            return None

        old_state = self.state
        self.state = new_state
        self.last_update = time.time()

        if new_state == State.NEEDS_ATTENTION:
            self.needs_attention_since = time.time()
        else:
            self.needs_attention_since = None

        return old_state

    def update_activity(self, activity: str) -> None:
        """Update the current activity text."""
        self.activity = activity
        self.last_update = time.time()

    @property
    def project_name(self) -> str:
        """Extract project name from cwd."""
        return self.cwd.rstrip("/").split("/")[-1]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/tracker/state.py tests/test_state.py
git commit -m "feat: add session state model with state machine"
```

---

## Task 4: Session Registry

**Files:**
- Create: `src/claude_notify/tracker/registry.py`
- Create: `tests/test_registry.py`

**Step 1: Write failing test**

```python
# tests/test_registry.py
"""Tests for session registry."""

import pytest
from claude_notify.tracker.registry import SessionRegistry
from claude_notify.tracker.state import State


def test_register_new_session():
    """Can register a new session."""
    registry = SessionRegistry()
    session = registry.register(
        session_id="test-123",
        cwd="/home/user/project",
        terminal_uuid="term-uuid",
    )
    assert session.session_id == "test-123"
    assert session.cwd == "/home/user/project"


def test_get_existing_session():
    """Can retrieve a registered session."""
    registry = SessionRegistry()
    registry.register("test-123", "/home/user/project")
    session = registry.get("test-123")
    assert session is not None
    assert session.session_id == "test-123"


def test_get_nonexistent_returns_none():
    """Getting nonexistent session returns None."""
    registry = SessionRegistry()
    assert registry.get("nonexistent") is None


def test_unregister_session():
    """Can unregister a session."""
    registry = SessionRegistry()
    registry.register("test-123", "/home/user/project")
    session = registry.unregister("test-123")
    assert session is not None
    assert registry.get("test-123") is None


def test_list_all_sessions():
    """Can list all sessions."""
    registry = SessionRegistry()
    registry.register("session-1", "/project-1")
    registry.register("session-2", "/project-2")
    sessions = registry.all()
    assert len(sessions) == 2


def test_list_sessions_by_state():
    """Can filter sessions by state."""
    registry = SessionRegistry()
    s1 = registry.register("session-1", "/project-1")
    s2 = registry.register("session-2", "/project-2")
    s2.transition_to(State.NEEDS_ATTENTION)

    working = registry.by_state(State.WORKING)
    needs_attention = registry.by_state(State.NEEDS_ATTENTION)

    assert len(working) == 1
    assert len(needs_attention) == 1
    assert working[0].session_id == "session-1"
    assert needs_attention[0].session_id == "session-2"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/tracker/registry.py
"""Session registry for tracking multiple Claude Code sessions."""

from typing import Dict, List, Optional, Callable
from .state import SessionState, State


class SessionRegistry:
    """Registry of active Claude Code sessions."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._listeners: List[Callable] = []

    def register(
        self,
        session_id: str,
        cwd: str,
        terminal_uuid: Optional[str] = None,
    ) -> SessionState:
        """
        Register a new session or return existing one.

        Args:
            session_id: Unique session identifier
            cwd: Working directory
            terminal_uuid: GNOME_TERMINAL_SCREEN UUID if available

        Returns:
            The session state object
        """
        if session_id in self._sessions:
            return self._sessions[session_id]

        session = SessionState(
            session_id=session_id,
            cwd=cwd,
            terminal_uuid=terminal_uuid,
        )
        self._sessions[session_id] = session
        self._notify("session_registered", session)
        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def unregister(self, session_id: str) -> Optional[SessionState]:
        """
        Remove a session from the registry.

        Returns:
            The removed session, or None if not found
        """
        session = self._sessions.pop(session_id, None)
        if session:
            self._notify("session_unregistered", session)
        return session

    def all(self) -> List[SessionState]:
        """Get all registered sessions."""
        return list(self._sessions.values())

    def by_state(self, state: State) -> List[SessionState]:
        """Get all sessions in a particular state."""
        return [s for s in self._sessions.values() if s.state == state]

    def add_listener(self, callback: Callable) -> None:
        """Add a listener for registry events."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a listener."""
        self._listeners.remove(callback)

    def _notify(self, event: str, session: SessionState) -> None:
        """Notify all listeners of an event."""
        for listener in self._listeners:
            try:
                listener(event, session)
            except Exception:
                pass  # Don't let listener errors break the registry
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/tracker/registry.py tests/test_registry.py
git commit -m "feat: add session registry for multi-session tracking"
```

---

## Task 5: Hook Wire Protocol

**Files:**
- Create: `src/claude_notify/hook/protocol.py`
- Create: `tests/test_protocol.py`

**Step 1: Write failing test**

```python
# tests/test_protocol.py
"""Tests for hook wire protocol."""

import json
from claude_notify.hook.protocol import (
    encode_hook_message,
    decode_hook_message,
    HookMessage,
)


def test_encode_creates_two_blobs():
    """Encoding produces two newline-separated JSON blobs."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {"GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/abc"}

    encoded = encode_hook_message(claude_data, env_data)
    lines = encoded.strip().split("\n")

    assert len(lines) == 2
    # First blob should be parseable
    custom = json.loads(lines[0])
    assert "version" in custom
    assert "timestamp" in custom
    assert "claude_size" in custom


def test_encode_claude_size_matches():
    """claude_size in custom blob matches actual Claude blob size."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {}

    encoded = encode_hook_message(claude_data, env_data)
    lines = encoded.strip().split("\n")

    custom = json.loads(lines[0])
    claude_blob = lines[1]

    assert custom["claude_size"] == len(claude_blob.encode("utf-8"))


def test_decode_valid_message():
    """Can decode a valid two-blob message."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {"GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/abc"}

    encoded = encode_hook_message(claude_data, env_data)
    message = decode_hook_message(encoded)

    assert message.claude_data == claude_data
    assert message.env["GNOME_TERMINAL_SCREEN"] == "/org/gnome/Terminal/screen/abc"
    assert message.version == 1


def test_decode_malformed_claude_blob():
    """Decoding with malformed Claude blob still parses custom blob."""
    custom = json.dumps({
        "version": 1,
        "timestamp": 1234567890.0,
        "env": {"TERM": "xterm"},
        "claude_size": 50,
    })
    malformed_claude = "{ this is not valid json"
    encoded = f"{custom}\n{malformed_claude}\n"

    message = decode_hook_message(encoded)

    assert message.version == 1
    assert message.env["TERM"] == "xterm"
    assert message.claude_data is None
    assert message.claude_raw == malformed_claude
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocol.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/hook/protocol.py
"""Hook wire protocol for communication between hook and daemon."""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 1


@dataclass
class HookMessage:
    """Decoded hook message."""
    version: int
    timestamp: float
    env: Dict[str, str]
    claude_size: int
    claude_data: Optional[Dict[str, Any]]
    claude_raw: str


def encode_hook_message(
    claude_data: Dict[str, Any],
    env_data: Dict[str, str],
) -> str:
    """
    Encode a hook message for transmission to daemon.

    Args:
        claude_data: Raw JSON data from Claude (passed through)
        env_data: Environment variables to include

    Returns:
        Two newline-separated JSON blobs
    """
    # Encode Claude data first to get its size
    claude_blob = json.dumps(claude_data, separators=(",", ":"))
    claude_size = len(claude_blob.encode("utf-8"))

    # Build custom blob
    custom_blob = json.dumps({
        "version": PROTOCOL_VERSION,
        "timestamp": time.time(),
        "env": env_data,
        "claude_size": claude_size,
    }, separators=(",", ":"))

    return f"{custom_blob}\n{claude_blob}\n"


def decode_hook_message(data: str) -> HookMessage:
    """
    Decode a hook message from the wire format.

    Args:
        data: Two newline-separated JSON blobs

    Returns:
        HookMessage with parsed data (claude_data may be None if malformed)
    """
    lines = data.strip().split("\n", 1)

    # Parse custom blob (should always succeed)
    custom = json.loads(lines[0])

    # Try to parse Claude blob
    claude_raw = lines[1] if len(lines) > 1 else ""
    claude_data = None

    try:
        if claude_raw:
            claude_data = json.loads(claude_raw)
    except json.JSONDecodeError:
        pass  # Keep claude_data as None, preserve raw

    return HookMessage(
        version=custom["version"],
        timestamp=custom["timestamp"],
        env=custom.get("env", {}),
        claude_size=custom["claude_size"],
        claude_data=claude_data,
        claude_raw=claude_raw,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_protocol.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/hook/protocol.py tests/test_protocol.py
git commit -m "feat: add hook wire protocol with two-blob format"
```

---

## Task 6: Hook Main (Minimal Forwarder)

**Files:**
- Create: `src/claude_notify/hook/main.py`
- Create: `tests/test_hook_main.py`

**Step 1: Write failing test**

```python
# tests/test_hook_main.py
"""Tests for hook main entry point."""

import json
import os
import socket
import tempfile
import threading
from unittest.mock import patch

from claude_notify.hook.main import run_hook


def test_hook_sends_to_socket():
    """Hook sends message to daemon socket."""
    received_data = []

    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = os.path.join(tmpdir, "test.sock")

        # Create a simple server to receive
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen(1)
        server.settimeout(2)

        def accept_connection():
            conn, _ = server.accept()
            data = conn.recv(4096)
            received_data.append(data.decode("utf-8"))
            conn.close()

        thread = threading.Thread(target=accept_connection)
        thread.start()

        # Run hook
        claude_input = json.dumps({
            "hook_event_name": "Stop",
            "session_id": "test-123",
        })

        with patch.dict(os.environ, {"GNOME_TERMINAL_SCREEN": "test-term"}):
            result = run_hook(claude_input, socket_path)

        thread.join(timeout=2)
        server.close()

        assert result == 0
        assert len(received_data) == 1
        # Check custom blob was sent
        lines = received_data[0].strip().split("\n")
        custom = json.loads(lines[0])
        assert custom["version"] == 1
        assert "test-term" in custom["env"].get("GNOME_TERMINAL_SCREEN", "")


def test_hook_returns_zero_on_socket_error():
    """Hook returns 0 even if socket unavailable (fire-and-forget)."""
    claude_input = json.dumps({
        "hook_event_name": "Stop",
        "session_id": "test-123",
    })

    # Use non-existent socket
    result = run_hook(claude_input, "/nonexistent/socket.sock")

    assert result == 0  # Never blocks or fails
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hook_main.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/hook/main.py
"""Minimal hook forwarder - sends events to daemon."""

import json
import os
import socket
import sys
from typing import Optional

from .protocol import encode_hook_message

DEFAULT_SOCKET_PATH = f"/run/user/{os.getuid()}/claude-notify.sock"

# Environment variables to capture
CAPTURE_ENV_VARS = [
    "GNOME_TERMINAL_SCREEN",
    "TERM",
    "WINDOWID",
    "DISPLAY",
    "WAYLAND_DISPLAY",
]


def run_hook(
    stdin_data: str,
    socket_path: Optional[str] = None,
) -> int:
    """
    Run the hook: read Claude data, forward to daemon.

    Args:
        stdin_data: Raw JSON from Claude Code
        socket_path: Path to daemon socket (default: /run/user/$UID/claude-notify.sock)

    Returns:
        Exit code (always 0 - fire and forget)
    """
    socket_path = socket_path or DEFAULT_SOCKET_PATH

    # Parse Claude data (just to validate it's JSON)
    try:
        claude_data = json.loads(stdin_data)
    except json.JSONDecodeError:
        # Even if invalid, try to send raw data
        claude_data = {"_raw": stdin_data, "_parse_error": True}

    # Capture environment variables
    env_data = {}
    for var in CAPTURE_ENV_VARS:
        value = os.environ.get(var)
        if value:
            env_data[var] = value

    # Encode message
    message = encode_hook_message(claude_data, env_data)

    # Send to daemon (fire-and-forget)
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)  # Don't block for long
        sock.connect(socket_path)
        sock.sendall(message.encode("utf-8"))
        sock.close()
    except (socket.error, OSError):
        pass  # Daemon not running - that's OK

    return 0


def main() -> None:
    """Entry point for claude-notify-hook command."""
    stdin_data = sys.stdin.read()
    exit_code = run_hook(stdin_data)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_hook_main.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/hook/main.py tests/test_hook_main.py
git commit -m "feat: add minimal hook forwarder"
```

---

## Task 7: Hook Event Parser

**Files:**
- Create: `src/claude_notify/tracker/events.py`
- Create: `tests/test_events.py`

**Step 1: Write failing test**

```python
# tests/test_events.py
"""Tests for hook event parsing."""

from claude_notify.tracker.events import (
    parse_hook_event,
    HookEvent,
    determine_state_from_event,
)
from claude_notify.tracker.state import State


def test_parse_stop_event():
    """Parse a Stop hook event."""
    claude_data = {
        "hook_event_name": "Stop",
        "session_id": "abc-123",
        "cwd": "/home/user/project",
    }
    event = parse_hook_event(claude_data)

    assert event.event_name == "Stop"
    assert event.session_id == "abc-123"
    assert event.cwd == "/home/user/project"


def test_parse_pre_tool_use_event():
    """Parse a PreToolUse hook event."""
    claude_data = {
        "hook_event_name": "PreToolUse",
        "session_id": "abc-123",
        "cwd": "/home/user/project",
        "tool_name": "Bash",
    }
    event = parse_hook_event(claude_data)

    assert event.event_name == "PreToolUse"
    assert event.tool_name == "Bash"


def test_determine_state_stop_is_needs_attention():
    """Stop event transitions to NEEDS_ATTENTION."""
    event = HookEvent(
        event_name="Stop",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.NEEDS_ATTENTION


def test_determine_state_pre_tool_use_is_working():
    """PreToolUse event transitions to WORKING."""
    event = HookEvent(
        event_name="PreToolUse",
        session_id="abc-123",
        cwd="/project",
        tool_name="Bash",
    )
    state = determine_state_from_event(event)
    assert state == State.WORKING


def test_determine_state_user_prompt_is_working():
    """UserPromptSubmit event transitions to WORKING."""
    event = HookEvent(
        event_name="UserPromptSubmit",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.WORKING


def test_determine_state_notification_is_needs_attention():
    """Notification event transitions to NEEDS_ATTENTION."""
    event = HookEvent(
        event_name="Notification",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.NEEDS_ATTENTION
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_events.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/tracker/events.py
"""Hook event parsing and state determination."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .state import State


@dataclass
class HookEvent:
    """Parsed hook event from Claude Code."""
    event_name: str
    session_id: str
    cwd: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    transcript_path: Optional[str] = None


def parse_hook_event(claude_data: Dict[str, Any]) -> HookEvent:
    """
    Parse Claude hook data into a HookEvent.

    Args:
        claude_data: Raw JSON from Claude Code hook

    Returns:
        Parsed HookEvent
    """
    return HookEvent(
        event_name=claude_data.get("hook_event_name", "Unknown"),
        session_id=claude_data.get("session_id", ""),
        cwd=claude_data.get("cwd", ""),
        tool_name=claude_data.get("tool_name"),
        tool_input=claude_data.get("tool_input"),
        message=claude_data.get("message"),
        transcript_path=claude_data.get("transcript_path"),
    )


# Events that indicate Claude is working
WORKING_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "SessionStart",
}

# Events that indicate Claude needs attention
NEEDS_ATTENTION_EVENTS = {
    "Stop",
    "SubagentStop",
    "Notification",
}


def determine_state_from_event(event: HookEvent) -> State:
    """
    Determine what state a session should be in based on an event.

    Args:
        event: The hook event

    Returns:
        The state the session should transition to
    """
    if event.event_name in WORKING_EVENTS:
        return State.WORKING

    if event.event_name in NEEDS_ATTENTION_EVENTS:
        return State.NEEDS_ATTENTION

    # Default to working for unknown events
    return State.WORKING
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_events.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/tracker/events.py tests/test_events.py
git commit -m "feat: add hook event parser with state determination"
```

---

## Task 8: GNOME Notification Manager

**Files:**
- Create: `src/claude_notify/gnome/notifications.py`
- Create: `tests/test_notifications.py`

**Step 1: Write failing test (mock D-Bus)**

```python
# tests/test_notifications.py
"""Tests for GNOME notification manager."""

from unittest.mock import MagicMock, patch

from claude_notify.gnome.notifications import NotificationManager
from claude_notify.tracker.state import State


@patch("claude_notify.gnome.notifications.dbus")
def test_create_persistent_notification(mock_dbus):
    """Creates a persistent notification with correct hints."""
    mock_interface = MagicMock()
    mock_interface.Notify.return_value = 42
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface
    mock_dbus.Byte = lambda x: x
    mock_dbus.Boolean = lambda x: x
    mock_dbus.String = lambda x: x

    manager = NotificationManager()
    notif_id = manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.WORKING,
        activity="Running tests...",
    )

    assert notif_id == 42
    mock_interface.Notify.assert_called_once()

    # Check urgency hint was set to critical (2)
    call_args = mock_interface.Notify.call_args
    hints = call_args[0][6]  # 7th argument is hints
    assert hints.get("urgency") == 2


@patch("claude_notify.gnome.notifications.dbus")
def test_update_persistent_notification(mock_dbus):
    """Updates existing notification using replaces_id."""
    mock_interface = MagicMock()
    mock_interface.Notify.return_value = 42
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface
    mock_dbus.Byte = lambda x: x
    mock_dbus.Boolean = lambda x: x
    mock_dbus.String = lambda x: x

    manager = NotificationManager()

    # First call
    manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.WORKING,
        activity="Starting...",
    )

    # Update call
    manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.NEEDS_ATTENTION,
        activity="Waiting for input",
        replaces_id=42,
    )

    # Check second call used replaces_id
    second_call = mock_interface.Notify.call_args_list[1]
    replaces_id = second_call[0][1]  # 2nd argument is replaces_id
    assert replaces_id == 42


@patch("claude_notify.gnome.notifications.dbus")
def test_dismiss_notification(mock_dbus):
    """Can dismiss a notification by ID."""
    mock_interface = MagicMock()
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface

    manager = NotificationManager()
    manager.dismiss(42)

    mock_interface.CloseNotification.assert_called_once_with(42)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_notifications.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/gnome/notifications.py
"""GNOME notification manager using D-Bus."""

from typing import Optional

try:
    import dbus
except ImportError:
    dbus = None  # Will fail at runtime if actually used

from claude_notify.tracker.state import State


STATE_ICONS = {
    State.WORKING: "\u2699\ufe0f",  # ⚙️
    State.NEEDS_ATTENTION: "\u2753",  # ❓
    State.SESSION_LIMIT: "\u23f1\ufe0f",  # ⏱️
    State.API_ERROR: "\U0001f534",  # 🔴
}


class NotificationManager:
    """Manages GNOME desktop notifications via D-Bus."""

    def __init__(self):
        if dbus is None:
            raise RuntimeError("dbus-python not installed")

        self._bus = dbus.SessionBus()
        self._notify_obj = self._bus.get_object(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
        )
        self._notify_interface = dbus.Interface(
            self._notify_obj,
            "org.freedesktop.Notifications",
        )

    def show_persistent(
        self,
        session_id: str,
        friendly_name: str,
        project_name: str,
        state: State,
        activity: str,
        replaces_id: int = 0,
    ) -> int:
        """
        Show or update a persistent notification for a session.

        Args:
            session_id: Session identifier (for action handling)
            friendly_name: Human-friendly session name
            project_name: Project directory name
            state: Current session state
            activity: Current activity text
            replaces_id: Notification ID to replace (0 for new)

        Returns:
            Notification ID
        """
        icon = STATE_ICONS.get(state, "\u2753")
        summary = f"{icon} [{friendly_name}] {project_name}"
        body = activity or "Ready"

        actions = [
            f"focus:{session_id}", "Focus Terminal",
        ]

        hints = {
            "urgency": dbus.Byte(2),  # Critical - persistent
            "resident": dbus.Boolean(True),
            "desktop-entry": dbus.String("claude-notify"),
            "category": dbus.String("im.received"),
        }

        notif_id = self._notify_interface.Notify(
            "Claude Code",  # app_name
            replaces_id,    # replaces_id
            "dialog-information",  # icon
            summary,        # summary
            body,           # body
            actions,        # actions
            hints,          # hints
            0,              # timeout (0 = persistent)
        )

        return int(notif_id)

    def show_popup(
        self,
        session_id: str,
        friendly_name: str,
        project_name: str,
        message: str,
        timeout_ms: int = 10000,
    ) -> int:
        """
        Show a popup notification for attention.

        Args:
            session_id: Session identifier
            friendly_name: Human-friendly session name
            project_name: Project directory name
            message: Alert message
            timeout_ms: Auto-dismiss timeout in milliseconds

        Returns:
            Notification ID
        """
        summary = f"Claude needs attention"
        body = f"[{friendly_name}] {project_name}\n{message}"

        actions = [
            f"focus:{session_id}", "Focus Terminal",
        ]

        hints = {
            "urgency": dbus.Byte(1),  # Normal - popup
            "category": dbus.String("im.received"),
        }

        notif_id = self._notify_interface.Notify(
            "Claude Code",
            0,              # Always new notification
            "dialog-warning",
            summary,
            body,
            actions,
            hints,
            timeout_ms,
        )

        return int(notif_id)

    def dismiss(self, notification_id: int) -> None:
        """Dismiss a notification by ID."""
        try:
            self._notify_interface.CloseNotification(notification_id)
        except dbus.DBusException:
            pass  # Already closed or invalid ID
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_notifications.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/gnome/notifications.py tests/test_notifications.py
git commit -m "feat: add GNOME notification manager with D-Bus"
```

---

## Task 9: Daemon Socket Server

**Files:**
- Create: `src/claude_notify/daemon/server.py`
- Create: `tests/test_server.py`

**Step 1: Write failing test**

```python
# tests/test_server.py
"""Tests for daemon socket server."""

import json
import os
import socket
import tempfile
import threading
import time

from claude_notify.daemon.server import DaemonServer
from claude_notify.hook.protocol import encode_hook_message


def test_server_receives_hook_messages():
    """Server receives and processes hook messages."""
    received_messages = []

    def handler(message):
        received_messages.append(message)

    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = os.path.join(tmpdir, "test.sock")

        server = DaemonServer(socket_path, handler)
        server_thread = threading.Thread(target=server.serve_once)
        server_thread.start()

        # Give server time to start
        time.sleep(0.1)

        # Send a message
        claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
        message = encode_hook_message(claude_data, {"TERM": "xterm"})

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.sendall(message.encode("utf-8"))
        sock.close()

        server_thread.join(timeout=2)
        server.shutdown()

        assert len(received_messages) == 1
        assert received_messages[0].claude_data["session_id"] == "test-123"


def test_server_handles_malformed_data():
    """Server handles malformed data gracefully."""
    received_messages = []
    errors = []

    def handler(message):
        received_messages.append(message)

    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = os.path.join(tmpdir, "test.sock")

        server = DaemonServer(socket_path, handler)
        server_thread = threading.Thread(target=server.serve_once)
        server_thread.start()

        time.sleep(0.1)

        # Send malformed data
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.sendall(b"not json at all")
        sock.close()

        server_thread.join(timeout=2)
        server.shutdown()

        # Should not crash, may or may not have message
        assert True  # Server didn't crash
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/claude_notify/daemon/server.py
"""Unix socket server for receiving hook messages."""

import logging
import os
import socket
import threading
from typing import Callable, Optional

from claude_notify.hook.protocol import decode_hook_message, HookMessage

logger = logging.getLogger(__name__)


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

    def _ensure_socket_dir(self) -> None:
        """Ensure socket directory exists."""
        socket_dir = os.path.dirname(self._socket_path)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)

    def _cleanup_stale_socket(self) -> None:
        """Remove stale socket file if it exists."""
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

    def start(self) -> None:
        """Start the server (non-blocking)."""
        self._ensure_socket_dir()
        self._cleanup_stale_socket()

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self._socket_path)
        self._server.listen(10)
        self._server.settimeout(1.0)
        self._running = True

        logger.info(f"Daemon listening on {self._socket_path}")

    def serve_once(self) -> None:
        """Accept and handle one connection (for testing)."""
        self.start()
        try:
            self._accept_one()
        finally:
            self.shutdown()

    def serve_forever(self) -> None:
        """Accept connections until shutdown."""
        self.start()
        while self._running:
            self._accept_one()

    def _accept_one(self) -> None:
        """Accept and handle one connection."""
        try:
            conn, _ = self._server.accept()
            threading.Thread(
                target=self._handle_connection,
                args=(conn,),
                daemon=True,
            ).start()
        except socket.timeout:
            pass
        except OSError:
            pass  # Server was shut down

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            if data:
                message = decode_hook_message(data.decode("utf-8"))
                self._handler(message)
        except Exception as e:
            logger.warning(f"Error handling connection: {e}")
        finally:
            conn.close()

    def shutdown(self) -> None:
        """Shutdown the server."""
        self._running = False
        if self._server:
            self._server.close()
            self._server = None
        self._cleanup_stale_socket()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/claude_notify/daemon/server.py tests/test_server.py
git commit -m "feat: add daemon Unix socket server"
```

---

## Task 10: Daemon Main Loop

**Files:**
- Create: `src/claude_notify/daemon/main.py`
- Modify: `src/claude_notify/tracker/__init__.py`
- Modify: `src/claude_notify/gnome/__init__.py`

**Step 1: Create tracker package exports**

```python
# src/claude_notify/tracker/__init__.py
"""Session tracking library."""

from .state import SessionState, State
from .registry import SessionRegistry
from .events import parse_hook_event, determine_state_from_event, HookEvent
from .friendly_names import generate_friendly_name

__all__ = [
    "SessionState",
    "State",
    "SessionRegistry",
    "parse_hook_event",
    "determine_state_from_event",
    "HookEvent",
    "generate_friendly_name",
]
```

**Step 2: Create gnome package exports**

```python
# src/claude_notify/gnome/__init__.py
"""GNOME desktop integration."""

from .notifications import NotificationManager

__all__ = [
    "NotificationManager",
]
```

**Step 3: Write daemon main**

```python
# src/claude_notify/daemon/main.py
"""Daemon main entry point."""

import argparse
import logging
import os
import signal
import sys
import time
from typing import Optional

from claude_notify.hook.protocol import HookMessage
from claude_notify.tracker import (
    SessionRegistry,
    parse_hook_event,
    determine_state_from_event,
    State,
)

logger = logging.getLogger(__name__)

# Try to import GNOME components (optional)
try:
    from claude_notify.gnome import NotificationManager
    HAS_GNOME = True
except ImportError:
    HAS_GNOME = False
    NotificationManager = None


class Daemon:
    """Main daemon process."""

    def __init__(
        self,
        socket_path: str,
        popup_delay: float = 45.0,
    ):
        self.socket_path = socket_path
        self.popup_delay = popup_delay
        self.registry = SessionRegistry()
        self.notifications: Optional[NotificationManager] = None
        self._server = None
        self._running = False

        if HAS_GNOME:
            try:
                self.notifications = NotificationManager()
            except Exception as e:
                logger.warning(f"Could not initialize notifications: {e}")

    def handle_message(self, message: HookMessage) -> None:
        """Handle an incoming hook message."""
        if message.claude_data is None:
            logger.warning(f"Received malformed Claude data: {message.claude_raw[:100]}")
            return

        event = parse_hook_event(message.claude_data)
        logger.debug(f"Received event: {event.event_name} for session {event.session_id}")

        # Get or create session
        terminal_uuid = message.env.get("GNOME_TERMINAL_SCREEN")
        session = self.registry.get(event.session_id)

        if session is None:
            session = self.registry.register(
                event.session_id,
                event.cwd,
                terminal_uuid,
            )
            logger.info(
                f"SESSION_START session={event.session_id} "
                f"name={session.friendly_name} cwd={event.cwd}"
            )

        # Update terminal UUID if we have it
        if terminal_uuid and not session.terminal_uuid:
            session.terminal_uuid = terminal_uuid

        # Determine and apply state transition
        new_state = determine_state_from_event(event)
        old_state = session.transition_to(new_state)

        if old_state is not None:
            logger.info(
                f"STATE_CHANGE session={event.session_id} "
                f"old={old_state.value} new={new_state.value}"
            )

        # Update activity if we have a message
        if event.message:
            session.update_activity(event.message)

        # Update notifications
        self._update_notifications(session)

        # Handle SessionEnd
        if event.event_name == "SessionEnd":
            self._cleanup_session(session)

    def _update_notifications(self, session) -> None:
        """Update notifications for a session."""
        if self.notifications is None:
            return

        try:
            notif_id = self.notifications.show_persistent(
                session_id=session.session_id,
                friendly_name=session.friendly_name,
                project_name=session.project_name,
                state=session.state,
                activity=session.activity,
                replaces_id=session.persistent_notif_id or 0,
            )
            session.persistent_notif_id = notif_id
            logger.debug(f"NOTIFICATION_UPDATE session={session.session_id} notif_id={notif_id}")
        except Exception as e:
            logger.error(f"Failed to update notification: {e}")

    def _cleanup_session(self, session) -> None:
        """Clean up a session."""
        if self.notifications and session.persistent_notif_id:
            self.notifications.dismiss(session.persistent_notif_id)
        if self.notifications and session.popup_notif_id:
            self.notifications.dismiss(session.popup_notif_id)
        self.registry.unregister(session.session_id)
        logger.info(f"SESSION_END session={session.session_id}")

    def dump_state(self) -> str:
        """Dump current state for debugging."""
        lines = [f"SESSION REGISTRY ({len(self.registry.all())} active):"]
        for s in self.registry.all():
            lines.append(
                f"  [{s.friendly_name}] {s.session_id[:8]}... "
                f"{s.state.value} {s.project_name} notif={s.persistent_notif_id}"
            )
        return "\n".join(lines)

    def run(self) -> None:
        """Run the daemon."""
        from claude_notify.daemon.server import DaemonServer

        self._server = DaemonServer(self.socket_path, self.handle_message)
        self._running = True

        # Handle SIGUSR1 for state dump
        def handle_sigusr1(signum, frame):
            print(self.dump_state())

        signal.signal(signal.SIGUSR1, handle_sigusr1)

        # Handle SIGTERM/SIGINT for graceful shutdown
        def handle_shutdown(signum, frame):
            logger.info("Shutting down...")
            self._running = False
            if self._server:
                self._server.shutdown()

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

        logger.info("Daemon starting...")
        self._server.serve_forever()
        logger.info("Daemon stopped")


def main() -> None:
    """Entry point for claude-notify-daemon command."""
    parser = argparse.ArgumentParser(description="Claude Notify Daemon")
    parser.add_argument(
        "--socket",
        default=f"/run/user/{os.getuid()}/claude-notify.sock",
        help="Socket path",
    )
    parser.add_argument(
        "--popup-delay",
        type=float,
        default=45.0,
        help="Seconds before popup notification",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    daemon = Daemon(
        socket_path=args.socket,
        popup_delay=args.popup_delay,
    )
    daemon.run()


if __name__ == "__main__":
    main()
```

**Step 4: Commit**

```bash
git add src/claude_notify/tracker/__init__.py src/claude_notify/gnome/__init__.py src/claude_notify/daemon/main.py
git commit -m "feat: add daemon main loop with event handling"
```

---

## Task 11: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
"""Integration tests for full hook-to-daemon flow."""

import json
import os
import socket
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

from claude_notify.daemon.main import Daemon
from claude_notify.daemon.server import DaemonServer
from claude_notify.hook.protocol import encode_hook_message


def test_full_hook_to_daemon_flow():
    """Test complete flow from hook message to state update."""
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = os.path.join(tmpdir, "test.sock")

        # Create daemon without notifications
        with patch("claude_notify.daemon.main.HAS_GNOME", False):
            daemon = Daemon(socket_path)

        # Start server in background
        server = DaemonServer(socket_path, daemon.handle_message)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        time.sleep(0.1)  # Let server start

        # Send SessionStart-like message
        claude_data = {
            "hook_event_name": "PreToolUse",
            "session_id": "test-session-123",
            "cwd": "/home/user/my-project",
            "tool_name": "Bash",
        }
        message = encode_hook_message(
            claude_data,
            {"GNOME_TERMINAL_SCREEN": "test-terminal-uuid"},
        )

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.sendall(message.encode("utf-8"))
        sock.close()

        time.sleep(0.2)  # Let message process

        # Check session was created
        session = daemon.registry.get("test-session-123")
        assert session is not None
        assert session.friendly_name != ""
        assert session.project_name == "my-project"
        assert session.terminal_uuid == "test-terminal-uuid"

        # Send Stop message
        stop_data = {
            "hook_event_name": "Stop",
            "session_id": "test-session-123",
            "cwd": "/home/user/my-project",
        }
        message = encode_hook_message(stop_data, {})

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.sendall(message.encode("utf-8"))
        sock.close()

        time.sleep(0.2)

        # Check state changed
        from claude_notify.tracker import State
        assert session.state == State.NEEDS_ATTENTION

        server.shutdown()
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for hook-to-daemon flow"
```

---

## Task 12: Update CLAUDE.md and README

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md**

Update the CLAUDE.md to reflect the new v2 architecture. Key sections to update:
- Overview (new architecture)
- Component descriptions
- Testing commands
- Configuration

**Step 2: Update README.md**

Update README with:
- New installation instructions
- Usage for v2
- Configuration options
- Development setup

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLAUDE.md and README for v2 architecture"
```

---

## Task 13: Add .tmp to .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Add .tmp directory**

Add to .gitignore:
```
# Temporary files
.tmp/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .tmp to gitignore"
```

---

## Future Tasks (Post-MVP)

These tasks are documented for future implementation:

- [ ] **Task F1**: Popup timer implementation (fires after configurable delay in NEEDS_ATTENTION)
- [ ] **Task F2**: Terminal focuser (GNOME Terminal tab focus via SearchProvider)
- [ ] **Task F3**: Action handler (D-Bus signal listener for button clicks)
- [ ] **Task F4**: Systemd service file for daemon
- [ ] **Task F5**: Rewrite hook in Rust/Go for faster startup
- [ ] **Task F6**: HTTP transport option for remote tracking
- [ ] **Task F7**: Configuration file support

---

## Execution Checklist

- [ ] Task 1: Project Structure Setup
- [ ] Task 2: Friendly Session Names
- [ ] Task 3: Session State Model
- [ ] Task 4: Session Registry
- [ ] Task 5: Hook Wire Protocol
- [ ] Task 6: Hook Main (Minimal Forwarder)
- [ ] Task 7: Hook Event Parser
- [ ] Task 8: GNOME Notification Manager
- [ ] Task 9: Daemon Socket Server
- [ ] Task 10: Daemon Main Loop
- [ ] Task 11: Integration Test
- [ ] Task 12: Update Documentation
- [ ] Task 13: Add .tmp to .gitignore
