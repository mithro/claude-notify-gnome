"""Session state model and state machine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

from .friendly_names import generate_friendly_name


class State(Enum):
    """Session states."""
    WORKING = "working"
    NEEDS_ATTENTION = "needs_attention"
    SESSION_LIMIT = "session_limit"
    API_ERROR = "api_error"


@dataclass
class SessionState:
    """State for a single Claude Code session."""

    session_id: str
    cwd: str
    terminal_uuid: Optional[str] = None
    state: State = State.WORKING
    activity: str = ""
    friendly_name: str = field(default="", init=False)
    persistent_notif_id: Optional[int] = None
    popup_notif_id: Optional[int] = None
    last_update: float = field(default_factory=time.time)
    needs_attention_since: Optional[float] = None

    def __post_init__(self):
        """Generate friendly name from session_id."""
        self.friendly_name = generate_friendly_name(self.session_id)

    def transition_to(self, new_state: State) -> Optional[State]:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to

        Returns:
            The old state if changed, None if already in that state
        """
        if self.state == new_state:
            return None

        old_state = self.state
        self.state = new_state
        self.last_update = time.time()

        if new_state == State.NEEDS_ATTENTION:
            self.needs_attention_since = time.time()
        else:
            self.needs_attention_since = None

        return old_state

    def update_activity(self, activity: str) -> None:
        """Update the current activity text."""
        self.activity = activity
        self.last_update = time.time()

    @property
    def project_name(self) -> str:
        """Extract project name from cwd."""
        return self.cwd.rstrip("/").split("/")[-1]
