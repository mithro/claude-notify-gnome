"""Session registry for tracking multiple Claude Code sessions."""

from typing import Dict, List, Optional, Callable
from .state import SessionState, State


class SessionRegistry:
    """Registry of active Claude Code sessions."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._listeners: List[Callable] = []

    def register(
        self,
        session_id: str,
        cwd: str,
        terminal_uuid: Optional[str] = None,
    ) -> SessionState:
        """
        Register a new session or return existing one.

        Args:
            session_id: Unique session identifier
            cwd: Working directory
            terminal_uuid: GNOME_TERMINAL_SCREEN UUID if available

        Returns:
            The session state object
        """
        if session_id in self._sessions:
            return self._sessions[session_id]

        session = SessionState(
            session_id=session_id,
            cwd=cwd,
            terminal_uuid=terminal_uuid,
        )
        self._sessions[session_id] = session
        self._notify("session_registered", session)
        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def unregister(self, session_id: str) -> Optional[SessionState]:
        """
        Remove a session from the registry.

        Returns:
            The removed session, or None if not found
        """
        session = self._sessions.pop(session_id, None)
        if session:
            self._notify("session_unregistered", session)
        return session

    def all(self) -> List[SessionState]:
        """Get all registered sessions."""
        return list(self._sessions.values())

    def by_state(self, state: State) -> List[SessionState]:
        """Get all sessions in a particular state."""
        return [s for s in self._sessions.values() if s.state == state]

    def add_listener(self, callback: Callable) -> None:
        """Add a listener for registry events."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a listener."""
        self._listeners.remove(callback)

    def _notify(self, event: str, session: SessionState) -> None:
        """Notify all listeners of an event."""
        for listener in self._listeners:
            try:
                listener(event, session)
            except Exception:
                pass  # Don't let listener errors break the registry
