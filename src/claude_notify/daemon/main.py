"""Daemon main entry point."""

import argparse
import logging
import os
import signal
import sys
import time
from typing import Optional

from claude_notify.hook.protocol import HookMessage
from claude_notify.tracker import (
    SessionRegistry,
    parse_hook_event,
    determine_state_from_event,
    State,
)

logger = logging.getLogger(__name__)

# Try to import GNOME components (optional)
try:
    from claude_notify.gnome import NotificationManager
    HAS_GNOME = True
except ImportError:
    HAS_GNOME = False
    NotificationManager = None


class Daemon:
    """Main daemon process."""

    def __init__(
        self,
        socket_path: str,
        popup_delay: float = 45.0,
    ):
        self.socket_path = socket_path
        self.popup_delay = popup_delay
        self.registry = SessionRegistry()
        self.notifications: Optional[NotificationManager] = None
        self._server = None
        self._running = False

        if HAS_GNOME:
            try:
                self.notifications = NotificationManager()
            except Exception as e:
                logger.warning(f"Could not initialize notifications: {e}")

    def handle_message(self, message: HookMessage) -> None:
        """Handle an incoming hook message."""
        if message.claude_data is None:
            logger.warning(f"Received malformed Claude data: {message.claude_raw[:100]}")
            return

        event = parse_hook_event(message.claude_data)
        logger.debug(f"Received event: {event.event_name} for session {event.session_id}")

        # Get or create session
        terminal_uuid = message.env.get("GNOME_TERMINAL_SCREEN")
        session = self.registry.get(event.session_id)

        if session is None:
            session = self.registry.register(
                event.session_id,
                event.cwd,
                terminal_uuid,
            )
            logger.info(
                f"SESSION_START session={event.session_id} "
                f"name={session.friendly_name} cwd={event.cwd}"
            )

        # Update terminal UUID if we have it
        if terminal_uuid and not session.terminal_uuid:
            session.terminal_uuid = terminal_uuid

        # Determine and apply state transition
        new_state = determine_state_from_event(event)
        old_state = session.transition_to(new_state)

        if old_state is not None:
            logger.info(
                f"STATE_CHANGE session={event.session_id} "
                f"old={old_state.value} new={new_state.value}"
            )

        # Update activity if we have a message
        if event.message:
            session.update_activity(event.message)

        # Update notifications
        self._update_notifications(session)

        # Handle SessionEnd
        if event.event_name == "SessionEnd":
            self._cleanup_session(session)

    def _update_notifications(self, session) -> None:
        """Update notifications for a session."""
        if self.notifications is None:
            return

        try:
            notif_id = self.notifications.show_persistent(
                session_id=session.session_id,
                friendly_name=session.friendly_name,
                project_name=session.project_name,
                state=session.state,
                activity=session.activity,
                replaces_id=session.persistent_notif_id or 0,
            )
            session.persistent_notif_id = notif_id
            logger.debug(f"NOTIFICATION_UPDATE session={session.session_id} notif_id={notif_id}")
        except Exception as e:
            logger.error(f"Failed to update notification: {e}")

    def _cleanup_session(self, session) -> None:
        """Clean up a session."""
        if self.notifications and session.persistent_notif_id:
            self.notifications.dismiss(session.persistent_notif_id)
        if self.notifications and session.popup_notif_id:
            self.notifications.dismiss(session.popup_notif_id)
        self.registry.unregister(session.session_id)
        logger.info(f"SESSION_END session={session.session_id}")

    def dump_state(self) -> str:
        """Dump current state for debugging."""
        lines = [f"SESSION REGISTRY ({len(self.registry.all())} active):"]
        for s in self.registry.all():
            lines.append(
                f"  [{s.friendly_name}] {s.session_id[:8]}... "
                f"{s.state.value} {s.project_name} notif={s.persistent_notif_id}"
            )
        return "\n".join(lines)

    def run(self) -> None:
        """Run the daemon."""
        from claude_notify.daemon.server import DaemonServer

        self._server = DaemonServer(self.socket_path, self.handle_message)
        self._running = True

        # Handle SIGUSR1 for state dump
        def handle_sigusr1(signum, frame):
            print(self.dump_state())

        signal.signal(signal.SIGUSR1, handle_sigusr1)

        # Handle SIGTERM/SIGINT for graceful shutdown
        def handle_shutdown(signum, frame):
            logger.info("Shutting down...")
            self._running = False
            if self._server:
                self._server.shutdown()

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

        logger.info("Daemon starting...")
        self._server.serve_forever()
        logger.info("Daemon stopped")


def main() -> None:
    """Entry point for claude-notify-daemon command."""
    parser = argparse.ArgumentParser(description="Claude Notify Daemon")
    parser.add_argument(
        "--socket",
        default=f"/run/user/{os.getuid()}/claude-notify.sock",
        help="Socket path",
    )
    parser.add_argument(
        "--popup-delay",
        type=float,
        default=45.0,
        help="Seconds before popup notification",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    daemon = Daemon(
        socket_path=args.socket,
        popup_delay=args.popup_delay,
    )
    daemon.run()


if __name__ == "__main__":
    main()
