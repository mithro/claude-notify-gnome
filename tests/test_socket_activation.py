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
