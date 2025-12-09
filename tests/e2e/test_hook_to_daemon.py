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
