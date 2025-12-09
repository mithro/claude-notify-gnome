"""systemd unit file installation."""

import os
import subprocess
from pathlib import Path
from importlib import resources


def get_systemd_user_dir() -> Path:
    """Get the systemd user unit directory."""
    return Path.home() / ".config" / "systemd" / "user"


def render_socket_unit() -> str:
    """Render the socket unit file content."""
    template = resources.files("claude_notify.install.templates").joinpath(
        "claude-notify-daemon.socket"
    ).read_text()
    return template


def render_service_unit(daemon_command: str) -> str:
    """Render the service unit file content.

    Args:
        daemon_command: Full command to start the daemon

    Raises:
        ValueError: If daemon_command is empty or whitespace-only
    """
    if not daemon_command or not daemon_command.strip():
        raise ValueError("daemon_command cannot be empty")

    template = resources.files("claude_notify.install.templates").joinpath(
        "claude-notify-daemon.service"
    ).read_text()
    return template.replace("{daemon_command}", daemon_command)


def _atomic_write(path: Path, content: str) -> None:
    """Write content to file atomically using temp file and rename.

    Args:
        path: Target file path
        content: Content to write
    """
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(content)
    temp.rename(path)  # atomic on POSIX


def install_units(daemon_command: str) -> None:
    """Install systemd socket and service units.

    Args:
        daemon_command: Full command to start the daemon
    """
    systemd_dir = get_systemd_user_dir()
    systemd_dir.mkdir(parents=True, exist_ok=True)

    # Write socket unit atomically
    socket_path = systemd_dir / "claude-notify-daemon.socket"
    _atomic_write(socket_path, render_socket_unit())

    # Write service unit atomically
    service_path = systemd_dir / "claude-notify-daemon.service"
    _atomic_write(service_path, render_service_unit(daemon_command))


def uninstall_units() -> None:
    """Remove systemd socket and service units."""
    systemd_dir = get_systemd_user_dir()

    for filename in ["claude-notify-daemon.socket", "claude-notify-daemon.service"]:
        path = systemd_dir / filename
        if path.exists():
            path.unlink()


def reload_systemd() -> bool:
    """Reload systemd user daemon. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def enable_socket() -> bool:
    """Enable the socket unit to start on login. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "enable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def disable_socket() -> bool:
    """Disable the socket unit. Returns True on success."""
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "claude-notify-daemon.socket"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
