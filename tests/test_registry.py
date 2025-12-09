"""Tests for session registry."""

import pytest
from claude_notify.tracker.registry import SessionRegistry
from claude_notify.tracker.state import State


def test_register_new_session():
    """Can register a new session."""
    registry = SessionRegistry()
    session = registry.register(
        session_id="test-123",
        cwd="/home/user/project",
        terminal_uuid="term-uuid",
    )
    assert session.session_id == "test-123"
    assert session.cwd == "/home/user/project"


def test_get_existing_session():
    """Can retrieve a registered session."""
    registry = SessionRegistry()
    registry.register("test-123", "/home/user/project")
    session = registry.get("test-123")
    assert session is not None
    assert session.session_id == "test-123"


def test_get_nonexistent_returns_none():
    """Getting nonexistent session returns None."""
    registry = SessionRegistry()
    assert registry.get("nonexistent") is None


def test_unregister_session():
    """Can unregister a session."""
    registry = SessionRegistry()
    registry.register("test-123", "/home/user/project")
    session = registry.unregister("test-123")
    assert session is not None
    assert registry.get("test-123") is None


def test_list_all_sessions():
    """Can list all sessions."""
    registry = SessionRegistry()
    registry.register("session-1", "/project-1")
    registry.register("session-2", "/project-2")
    sessions = registry.all()
    assert len(sessions) == 2


def test_list_sessions_by_state():
    """Can filter sessions by state."""
    registry = SessionRegistry()
    s1 = registry.register("session-1", "/project-1")
    s2 = registry.register("session-2", "/project-2")
    s2.transition_to(State.NEEDS_ATTENTION)

    working = registry.by_state(State.WORKING)
    needs_attention = registry.by_state(State.NEEDS_ATTENTION)

    assert len(working) == 1
    assert len(needs_attention) == 1
    assert working[0].session_id == "session-1"
    assert needs_attention[0].session_id == "session-2"
