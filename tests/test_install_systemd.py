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
    reload_systemd,
    enable_socket,
    disable_socket,
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


def test_reload_systemd_success():
    """reload_systemd returns True on successful daemon-reload."""
    with mock.patch("subprocess.run") as mock_run:
        result = reload_systemd()
        assert result is True
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )


def test_reload_systemd_failure():
    """reload_systemd returns False on subprocess error."""
    import subprocess
    with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
        result = reload_systemd()
        assert result is False


def test_reload_systemd_not_found():
    """reload_systemd returns False when systemctl not found."""
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        result = reload_systemd()
        assert result is False


def test_enable_socket_success():
    """enable_socket returns True on successful enable."""
    with mock.patch("subprocess.run") as mock_run:
        result = enable_socket()
        assert result is True
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "enable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )


def test_enable_socket_failure():
    """enable_socket returns False on subprocess error."""
    import subprocess
    with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
        result = enable_socket()
        assert result is False


def test_enable_socket_not_found():
    """enable_socket returns False when systemctl not found."""
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        result = enable_socket()
        assert result is False


def test_disable_socket_success():
    """disable_socket returns True on successful disable."""
    with mock.patch("subprocess.run") as mock_run:
        result = disable_socket()
        assert result is True
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "disable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )


def test_disable_socket_failure():
    """disable_socket returns False on subprocess error."""
    import subprocess
    with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
        result = disable_socket()
        assert result is False


def test_disable_socket_not_found():
    """disable_socket returns False when systemctl not found."""
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        result = disable_socket()
        assert result is False


def test_render_service_unit_validates_empty_command():
    """render_service_unit raises ValueError for empty daemon_command."""
    import pytest
    with pytest.raises(ValueError, match="daemon_command cannot be empty"):
        render_service_unit("")


def test_render_service_unit_validates_whitespace_command():
    """render_service_unit raises ValueError for whitespace-only daemon_command."""
    import pytest
    with pytest.raises(ValueError, match="daemon_command cannot be empty"):
        render_service_unit("   ")
