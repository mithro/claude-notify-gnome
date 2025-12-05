"""Hook event parsing and state determination."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .state import State


@dataclass
class HookEvent:
    """Parsed hook event from Claude Code."""
    event_name: str
    session_id: str
    cwd: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    transcript_path: Optional[str] = None


def parse_hook_event(claude_data: Dict[str, Any]) -> HookEvent:
    """
    Parse Claude hook data into a HookEvent.

    Args:
        claude_data: Raw JSON from Claude Code hook

    Returns:
        Parsed HookEvent
    """
    return HookEvent(
        event_name=claude_data.get("hook_event_name", "Unknown"),
        session_id=claude_data.get("session_id", ""),
        cwd=claude_data.get("cwd", ""),
        tool_name=claude_data.get("tool_name"),
        tool_input=claude_data.get("tool_input"),
        message=claude_data.get("message"),
        transcript_path=claude_data.get("transcript_path"),
    )


# Events that indicate Claude is working
WORKING_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "SessionStart",
}

# Events that indicate Claude needs attention
NEEDS_ATTENTION_EVENTS = {
    "Stop",
    "SubagentStop",
    "Notification",
}


def determine_state_from_event(event: HookEvent) -> State:
    """
    Determine what state a session should be in based on an event.

    Args:
        event: The hook event

    Returns:
        The state the session should transition to
    """
    if event.event_name in WORKING_EVENTS:
        return State.WORKING

    if event.event_name in NEEDS_ATTENTION_EVENTS:
        return State.NEEDS_ATTENTION

    # Default to working for unknown events
    return State.WORKING
