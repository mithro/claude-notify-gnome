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
