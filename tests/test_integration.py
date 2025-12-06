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
