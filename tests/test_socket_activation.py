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


def test_get_socket_from_systemd_returns_none_when_listen_pid_non_numeric():
    """With non-numeric LISTEN_PID, returns None."""
    with mock.patch.dict(os.environ, {"LISTEN_FDS": "1", "LISTEN_PID": "not-a-number"}):
        result = get_socket_from_systemd()
        assert result is None


def test_get_socket_from_systemd_returns_none_when_listen_fds_non_numeric():
    """With non-numeric LISTEN_FDS, returns None."""
    with mock.patch.dict(os.environ, {
        "LISTEN_FDS": "not-a-number",
        "LISTEN_PID": str(os.getpid())
    }):
        result = get_socket_from_systemd()
        assert result is None


def test_get_socket_from_systemd_returns_none_when_both_non_numeric():
    """With both LISTEN_FDS and LISTEN_PID non-numeric, returns None."""
    with mock.patch.dict(os.environ, {
        "LISTEN_FDS": "invalid",
        "LISTEN_PID": "also-invalid"
    }):
        result = get_socket_from_systemd()
        assert result is None
