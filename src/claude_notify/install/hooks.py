"""Claude Code hook configuration management."""

import json
import os
from pathlib import Path
from typing import Any


HOOK_EVENTS = ["Notification", "Stop", "PreToolUse", "PostToolUse", "UserPromptSubmit"]


def get_claude_settings_path() -> Path:
    """Get the path to Claude Code settings.json."""
    return Path.home() / ".claude" / "settings.json"


def read_settings(path: Path) -> dict[str, Any]:
    """Read settings.json, returning empty dict if not found."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def write_settings(path: Path, settings: dict[str, Any]) -> None:
    """Write settings.json atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then rename (atomic on POSIX)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(settings, indent=2))
    temp_path.rename(path)


def add_hooks(settings: dict[str, Any], hook_command: str) -> dict[str, Any]:
    """Add our hook to settings, preserving existing hooks.

    Args:
        settings: Current settings dict
        hook_command: Command to run for hook (e.g., "claude-notify-hook")

    Returns:
        Updated settings dict
    """
    settings = settings.copy()
    hooks = settings.get("hooks", {})

    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])

        # Check if we're already installed
        already_installed = any(hook_command in str(h) for h in event_hooks)
        if not already_installed:
            event_hooks.append({
                "hooks": [{"type": "command", "command": hook_command}]
            })

        hooks[event] = event_hooks

    settings["hooks"] = hooks
    return settings


def remove_hooks(settings: dict[str, Any], hook_command: str) -> dict[str, Any]:
    """Remove our hook from settings, preserving other hooks.

    Args:
        settings: Current settings dict
        hook_command: Command to remove

    Returns:
        Updated settings dict
    """
    settings = settings.copy()
    hooks = settings.get("hooks", {})

    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])
        # Filter out hooks containing our command
        event_hooks = [h for h in event_hooks if hook_command not in str(h)]
        hooks[event] = event_hooks

    settings["hooks"] = hooks
    return settings


def is_hook_installed(settings: dict[str, Any], hook_command: str) -> bool:
    """Check if our hook is installed in settings."""
    hooks = settings.get("hooks", {})
    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])
        if any(hook_command in str(h) for h in event_hooks):
            return True
    return False
