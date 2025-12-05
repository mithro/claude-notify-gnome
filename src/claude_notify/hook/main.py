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
