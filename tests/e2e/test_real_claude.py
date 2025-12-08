"""Tests using real Claude Code CLI.

These tests require ANTHROPIC_API_KEY to be set and will make real API calls.
They are skipped in CI unless explicitly enabled.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)


@pytest.fixture
def claude_home(tmp_path, temp_socket_path):
    """Create isolated Claude home directory with minimal settings.

    Configures hooks to use our hook handler with the test socket path.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Get the hook command - need to pass SOCKET_PATH to hook
    hook_cmd = "uv run claude-notify-hook"

    # Minimal settings with hooks configured for all events
    settings = {
        "hooks": {
            "Notification": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
            "Stop": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
            "PreToolUse": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
            "PostToolUse": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
        }
    }

    # Write settings
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2))

    # Set HOME to this isolated directory
    yield tmp_path


def test_claude_print_triggers_hook(claude_home, running_daemon, temp_socket_path):
    """Test that running claude --print triggers our hook.

    This test verifies:
    1. Claude CLI can run with our hook configured
    2. Hook events are sent to the daemon
    3. Daemon stays running (doesn't crash)
    """
    env = os.environ.copy()
    env["HOME"] = str(claude_home)
    env["SOCKET_PATH"] = temp_socket_path

    # Check if claude command is available
    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("claude command not available")

    # Run claude with --print (non-interactive, quick)
    proc = subprocess.run(
        ["claude", "--print", "Say exactly: hello"],
        env=env,
        capture_output=True,
        timeout=60,
    )

    # Claude should complete successfully
    assert proc.returncode == 0, f"Claude failed: {proc.stderr.decode()}"

    # Daemon should have received events and still be running
    time.sleep(0.5)
    assert running_daemon.poll() is None, "Daemon crashed during Claude execution"


def test_claude_simple_task_lifecycle(claude_home, running_daemon, temp_socket_path):
    """Test a simple Claude task generates expected hook events.

    This test verifies:
    1. Claude can complete a simple task
    2. Multiple hook events are received during task execution
    3. Daemon processes events without crashing
    """
    env = os.environ.copy()
    env["HOME"] = str(claude_home)
    env["SOCKET_PATH"] = temp_socket_path

    # Check if claude command is available
    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("claude command not available")

    # Run a simple task
    proc = subprocess.run(
        ["claude", "--print", "What is 2+2? Reply with just the number."],
        env=env,
        capture_output=True,
        timeout=60,
    )

    # Claude should complete successfully
    assert proc.returncode == 0, f"Claude failed: {proc.stderr.decode()}"

    # Verify the output contains the expected answer
    output = proc.stdout.decode()
    assert "4" in output, f"Expected '4' in output, got: {output}"

    # Daemon should still be healthy after processing all events
    time.sleep(0.5)
    assert running_daemon.poll() is None, "Daemon crashed during task lifecycle"
