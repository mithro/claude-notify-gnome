"""Tests for Claude Code hook configuration."""

import json
import tempfile
from pathlib import Path
from unittest import mock

from claude_notify.install.hooks import (
    get_claude_settings_path,
    read_settings,
    write_settings,
    add_hooks,
    remove_hooks,
    is_hook_installed,
)


def test_get_claude_settings_path():
    """Returns ~/.claude/settings.json path."""
    with mock.patch.dict("os.environ", {"HOME": "/home/testuser"}):
        result = get_claude_settings_path()
        assert result == Path("/home/testuser/.claude/settings.json")


def test_read_settings_returns_empty_dict_when_missing():
    """Returns empty dict when settings.json doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "settings.json"
        result = read_settings(path)
        assert result == {}


def test_read_settings_parses_existing_file():
    """Parses existing settings.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "settings.json"
        path.write_text('{"hooks": {}, "other": "value"}')
        result = read_settings(path)
        assert result == {"hooks": {}, "other": "value"}


def test_add_hooks_creates_hook_entries():
    """add_hooks adds our hook to all event types."""
    settings = {}
    hook_cmd = "claude-notify-hook"

    result = add_hooks(settings, hook_cmd)

    expected_events = ["Notification", "Stop", "PreToolUse", "PostToolUse", "UserPromptSubmit"]
    for event in expected_events:
        assert event in result["hooks"]
        assert any(hook_cmd in str(h) for h in result["hooks"][event])


def test_add_hooks_preserves_existing_hooks():
    """add_hooks preserves existing hooks from other tools."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "other-tool"}]}
            ]
        },
        "other_setting": "preserved"
    }
    hook_cmd = "claude-notify-hook"

    result = add_hooks(settings, hook_cmd)

    # Other tool's hook preserved
    assert any("other-tool" in str(h) for h in result["hooks"]["Notification"])
    # Our hook added
    assert any(hook_cmd in str(h) for h in result["hooks"]["Notification"])
    # Other settings preserved
    assert result["other_setting"] == "preserved"


def test_add_hooks_idempotent():
    """add_hooks doesn't duplicate if already installed."""
    settings = {}
    hook_cmd = "claude-notify-hook"

    result1 = add_hooks(settings, hook_cmd)
    result2 = add_hooks(result1, hook_cmd)

    # Should only have one copy of our hook
    notification_hooks = result2["hooks"]["Notification"]
    our_hook_count = sum(1 for h in notification_hooks if hook_cmd in str(h))
    assert our_hook_count == 1


def test_remove_hooks_removes_our_hooks():
    """remove_hooks removes only our hooks."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "other-tool"}]},
                {"hooks": [{"type": "command", "command": "claude-notify-hook"}]},
            ]
        }
    }
    hook_cmd = "claude-notify-hook"

    result = remove_hooks(settings, hook_cmd)

    # Other tool's hook preserved
    assert any("other-tool" in str(h) for h in result["hooks"]["Notification"])
    # Our hook removed
    assert not any(hook_cmd in str(h) for h in result["hooks"]["Notification"])


def test_is_hook_installed_returns_true_when_present():
    """is_hook_installed returns True when our hook is configured."""
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": "claude-notify-hook"}]}
            ]
        }
    }
    assert is_hook_installed(settings, "claude-notify-hook") is True


def test_is_hook_installed_returns_false_when_absent():
    """is_hook_installed returns False when our hook is not configured."""
    settings = {"hooks": {}}
    assert is_hook_installed(settings, "claude-notify-hook") is False
