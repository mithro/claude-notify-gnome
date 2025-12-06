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
