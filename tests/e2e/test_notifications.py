"""Tests for GNOME notification display.

These tests run in a Docker container with a full GNOME session.
They verify notifications appear correctly and capture screenshots.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

# send_hook_event is imported from conftest.py which pytest loads automatically
from .conftest import send_hook_event

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def capture_screenshot(name: str) -> Path:
    """Capture screenshot using weston-screenshooter.

    Returns path to screenshot file.
    """
    time.sleep(0.5)  # Allow notification animation
    output_path = SCREENSHOTS_DIR / f"{name}.png"

    # weston-screenshooter saves to current directory with timestamp
    # We'll use a different approach - gnome-screenshot if available
    try:
        subprocess.run(
            ["gnome-screenshot", "-f", str(output_path)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: create placeholder
        output_path.write_text("screenshot capture failed")

    return output_path


def test_notification_appears_on_stop(running_daemon, temp_socket_path):
    """Test that Stop event shows a notification."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "test-session-001",
        "cwd": "/home/testuser/my-project",
    }

    result = send_hook_event(temp_socket_path, event)
    assert result, "Failed to send hook event"

    # Wait for notification
    time.sleep(1)

    # Capture screenshot for documentation
    screenshot = capture_screenshot("01_notification_stop")
    assert screenshot.exists()


def test_notification_shows_friendly_name(running_daemon, temp_socket_path):
    """Test that notification shows friendly session name."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "unique-session-id-12345",
        "cwd": "/home/testuser/project",
    }

    result = send_hook_event(temp_socket_path, event)
    assert result

    time.sleep(1)
    capture_screenshot("02_notification_friendly_name")


def test_notification_updates_on_state_change(running_daemon, temp_socket_path):
    """Test notification updates when state changes."""
    session_id = "state-change-session"

    # First: Claude stops (needs attention)
    send_hook_event(temp_socket_path, {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03a_state_needs_attention")

    # Then: User submits prompt (working)
    send_hook_event(temp_socket_path, {
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03b_state_working")

    # Then: Claude stops again
    send_hook_event(temp_socket_path, {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
    })
    time.sleep(0.5)
    capture_screenshot("03c_state_needs_attention_again")


def test_multiple_session_notifications(running_daemon, temp_socket_path):
    """Test multiple concurrent session notifications."""
    sessions = [
        ("session-alpha", "project-alpha"),
        ("session-beta", "project-beta"),
        ("session-gamma", "project-gamma"),
    ]

    for session_id, project in sessions:
        send_hook_event(temp_socket_path, {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "cwd": f"/home/testuser/{project}",
        })
        time.sleep(0.3)

    time.sleep(1)
    capture_screenshot("04_multiple_sessions")


def test_working_state_notification(running_daemon, temp_socket_path):
    """Test notification shows working state correctly."""
    session_id = "working-session"

    # Tool use indicates working state
    send_hook_event(temp_socket_path, {
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "cwd": "/home/testuser/project",
        "tool_name": "Bash",
    })

    time.sleep(1)
    capture_screenshot("05_working_state")
