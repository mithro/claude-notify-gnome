"""Tests for hook event parsing."""

from claude_notify.tracker.events import (
    parse_hook_event,
    HookEvent,
    determine_state_from_event,
)
from claude_notify.tracker.state import State


def test_parse_stop_event():
    """Parse a Stop hook event."""
    claude_data = {
        "hook_event_name": "Stop",
        "session_id": "abc-123",
        "cwd": "/home/user/project",
    }
    event = parse_hook_event(claude_data)

    assert event.event_name == "Stop"
    assert event.session_id == "abc-123"
    assert event.cwd == "/home/user/project"


def test_parse_pre_tool_use_event():
    """Parse a PreToolUse hook event."""
    claude_data = {
        "hook_event_name": "PreToolUse",
        "session_id": "abc-123",
        "cwd": "/home/user/project",
        "tool_name": "Bash",
    }
    event = parse_hook_event(claude_data)

    assert event.event_name == "PreToolUse"
    assert event.tool_name == "Bash"


def test_determine_state_stop_is_needs_attention():
    """Stop event transitions to NEEDS_ATTENTION."""
    event = HookEvent(
        event_name="Stop",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.NEEDS_ATTENTION


def test_determine_state_pre_tool_use_is_working():
    """PreToolUse event transitions to WORKING."""
    event = HookEvent(
        event_name="PreToolUse",
        session_id="abc-123",
        cwd="/project",
        tool_name="Bash",
    )
    state = determine_state_from_event(event)
    assert state == State.WORKING


def test_determine_state_user_prompt_is_working():
    """UserPromptSubmit event transitions to WORKING."""
    event = HookEvent(
        event_name="UserPromptSubmit",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.WORKING


def test_determine_state_notification_is_needs_attention():
    """Notification event transitions to NEEDS_ATTENTION."""
    event = HookEvent(
        event_name="Notification",
        session_id="abc-123",
        cwd="/project",
    )
    state = determine_state_from_event(event)
    assert state == State.NEEDS_ATTENTION
