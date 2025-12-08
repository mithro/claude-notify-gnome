"""Installation CLI for claude-notify-gnome."""

import argparse
import subprocess
import sys
from pathlib import Path

from claude_notify.install.hooks import (
    get_claude_settings_path,
    read_settings,
    write_settings,
    add_hooks,
    remove_hooks,
    is_hook_installed,
)
from claude_notify.install.systemd import (
    install_units,
    uninstall_units,
    reload_systemd,
    enable_socket,
    disable_socket,
)


def get_hook_command(mode: str) -> str:
    """Get the hook command based on installation mode.

    Args:
        mode: Either 'development' or 'installed'

    Returns:
        Command string to run the hook
    """
    if mode == "development":
        # Find project root (where pyproject.toml is)
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return f"uv run --project {parent} claude-notify-hook"
        # Fallback
        return "uv run claude-notify-hook"
    else:
        # Installed mode - use entry point directly
        return "claude-notify-hook"


def get_daemon_command(mode: str) -> str:
    """Get the daemon command based on installation mode.

    Args:
        mode: Either 'development' or 'installed'

    Returns:
        Command string to run the daemon
    """
    if mode == "development":
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return f"uv run --project {parent} claude-notify-daemon"
        return "uv run claude-notify-daemon"
    else:
        return "claude-notify-daemon"


def install(mode: str, enable_autostart: bool) -> int:
    """Install claude-notify-gnome.

    Args:
        mode: Installation mode ('development' or 'installed')
        enable_autostart: Whether to enable daemon autostart on login

    Returns:
        Exit code (0 for success)
    """
    print(f"Installing claude-notify-gnome ({mode} mode)...")

    hook_cmd = get_hook_command(mode)
    daemon_cmd = get_daemon_command(mode)

    # Step 1: Update Claude Code hooks
    print("\n1. Configuring Claude Code hooks...")
    settings_path = get_claude_settings_path()
    settings = read_settings(settings_path)

    if is_hook_installed(settings, "claude-notify"):
        print("   Hooks already installed, updating...")

    settings = add_hooks(settings, hook_cmd)
    write_settings(settings_path, settings)
    print(f"   Updated {settings_path}")

    # Step 2: Install systemd units
    print("\n2. Installing systemd units...")
    install_units(daemon_command=daemon_cmd)
    print("   Created claude-notify-daemon.socket")
    print("   Created claude-notify-daemon.service")

    # Step 3: Reload systemd
    print("\n3. Reloading systemd...")
    if reload_systemd():
        print("   systemd reloaded")
    else:
        print("   WARNING: Could not reload systemd (is systemd running?)")

    # Step 4: Enable autostart if requested
    if enable_autostart:
        print("\n4. Enabling socket autostart...")
        if enable_socket():
            print("   Socket will start on login")
        else:
            print("   WARNING: Could not enable socket")

    print("\nInstallation complete!")
    print("\nTo start the daemon now:")
    print("  systemctl --user start claude-notify-daemon.socket")
    print("\nTo check status:")
    print("  systemctl --user status claude-notify-daemon.socket")

    return 0


def uninstall() -> int:
    """Uninstall claude-notify-gnome.

    Returns:
        Exit code (0 for success)
    """
    print("Uninstalling claude-notify-gnome...")

    # Step 1: Stop and disable services
    print("\n1. Stopping services...")
    subprocess.run(
        ["systemctl", "--user", "stop", "claude-notify-daemon.socket"],
        capture_output=True,
    )
    subprocess.run(
        ["systemctl", "--user", "stop", "claude-notify-daemon.service"],
        capture_output=True,
    )
    disable_socket()

    # Step 2: Remove hooks
    print("\n2. Removing Claude Code hooks...")
    settings_path = get_claude_settings_path()
    settings = read_settings(settings_path)
    settings = remove_hooks(settings, "claude-notify")
    write_settings(settings_path, settings)
    print(f"   Updated {settings_path}")

    # Step 3: Remove systemd units
    print("\n3. Removing systemd units...")
    uninstall_units()
    reload_systemd()
    print("   Removed unit files")

    print("\nUninstallation complete!")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install or uninstall claude-notify-gnome"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Install subcommand
    install_parser = subparsers.add_parser("install", help="Install claude-notify")
    install_parser.add_argument(
        "--mode",
        choices=["development", "installed"],
        default="installed",
        help="Installation mode (default: installed)"
    )
    install_parser.add_argument(
        "--enable-autostart",
        action="store_true",
        help="Enable daemon autostart on login"
    )

    # Uninstall subcommand
    subparsers.add_parser("uninstall", help="Uninstall claude-notify")

    args = parser.parse_args()

    if args.command == "install":
        return install(args.mode, args.enable_autostart)
    elif args.command == "uninstall":
        return uninstall()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
