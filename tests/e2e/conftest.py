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
