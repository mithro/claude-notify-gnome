"""Tests for session state model."""

import time
from claude_notify.tracker.state import SessionState, State


def test_initial_state_is_working():
    """New sessions start in WORKING state."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
        terminal_uuid="550e8400-e29b-41d4-a716-446655440000",
    )
    assert session.state == State.WORKING


def test_transition_to_needs_attention():
    """Can transition from WORKING to NEEDS_ATTENTION."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    old_state = session.transition_to(State.NEEDS_ATTENTION)
    assert old_state == State.WORKING
    assert session.state == State.NEEDS_ATTENTION


def test_transition_to_working():
    """Can transition from NEEDS_ATTENTION to WORKING."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    session.transition_to(State.NEEDS_ATTENTION)
    old_state = session.transition_to(State.WORKING)
    assert old_state == State.NEEDS_ATTENTION
    assert session.state == State.WORKING


def test_same_state_transition_returns_none():
    """Transitioning to same state returns None (no change)."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    result = session.transition_to(State.WORKING)
    assert result is None


def test_activity_update():
    """Can update activity text."""
    session = SessionState(
        session_id="test-123",
        cwd="/home/user/project",
    )
    session.update_activity("Running tests...")
    assert session.activity == "Running tests..."


def test_friendly_name_generated():
    """Friendly name is auto-generated from session_id."""
    session = SessionState(
        session_id="73b5e210-ec1a-4294-96e4-c2aecb2e1063",
        cwd="/home/user/project",
    )
    assert "-" in session.friendly_name
    assert len(session.friendly_name) > 3
