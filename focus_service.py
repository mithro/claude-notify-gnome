#!/usr/bin/env python3
"""
Claude Focus Service - Simplified Version
Background D-Bus service that handles notification clicks to focus Claude terminals

Design principles:
- Be correct or fail with clear errors (no guessing)
- Minimal code, maximum clarity
- In-memory state only (no persistent files)
"""

import json
import os
import sys
import time
import logging
import subprocess
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from typing import Dict, Optional
from dataclasses import dataclass, asdict

# Configuration
SERVICE_NAME = "com.claude.FocusService"
OBJECT_PATH = "/com/claude/FocusService"
MAX_SESSION_AGE = 24 * 60 * 60  # 24 hours
CLEANUP_INTERVAL = 60 * 60  # 1 hour

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Information about a Claude session"""
    session_id: str
    cwd: str
    pid: int
    created_at: float
    last_seen: float


class SessionRegistry:
    """In-memory store of active Claude sessions"""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.notification_map: Dict[str, str] = {}  # notification_id -> session_id

    def register_session(self, session_id: str, cwd: str, pid: int) -> bool:
        """Register a new Claude session"""
        try:
            now = time.time()
            self.sessions[session_id] = SessionInfo(
                session_id=session_id,
                cwd=cwd,
                pid=pid,
                created_at=now,
                last_seen=now
            )
            logger.info(f"Registered session {session_id[:8]}... in {cwd}")
            return True
        except Exception as e:
            logger.error(f"Failed to register session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info by ID"""
        session = self.sessions.get(session_id)
        if session:
            session.last_seen = time.time()
        return session

    def map_notification(self, notification_id: str, session_id: str):
        """Map a notification ID to a session ID"""
        self.notification_map[notification_id] = session_id
        logger.debug(f"Mapped notification {notification_id} to session {session_id[:8]}...")

    def get_session_by_notification(self, notification_id: str) -> Optional[SessionInfo]:
        """Get session info by notification ID"""
        session_id = self.notification_map.get(notification_id)
        if session_id:
            return self.get_session(session_id)
        return None

    def cleanup_stale_sessions(self):
        """Remove sessions older than MAX_SESSION_AGE"""
        now = time.time()
        stale = []
        for session_id, session in self.sessions.items():
            if now - session.created_at > MAX_SESSION_AGE:
                stale.append(session_id)

        for session_id in stale:
            del self.sessions[session_id]
            logger.info(f"Cleaned up stale session {session_id[:8]}...")

        # Also clean up orphaned notification mappings
        valid_sessions = set(self.sessions.keys())
        stale_notifications = [
            nid for nid, sid in self.notification_map.items()
            if sid not in valid_sessions
        ]
        for nid in stale_notifications:
            del self.notification_map[nid]


class ClaudeFocusService(dbus.service.Object):
    """D-Bus service for handling focus requests"""

    def __init__(self):
        # Initialize D-Bus
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()

        # Try to request the service name
        try:
            self.bus_name = dbus.service.BusName(SERVICE_NAME, self.bus)
        except dbus.exceptions.NameExistsException:
            logger.error(f"Service {SERVICE_NAME} is already running")
            sys.exit(1)

        # Initialize parent class
        super().__init__(self.bus_name, OBJECT_PATH)

        # Initialize session registry
        self.registry = SessionRegistry()

        # Set up notification listener
        self.setup_notification_listener()

        logger.info("Claude Focus Service started")

    def setup_notification_listener(self):
        """Set up listener for notification action clicks"""
        try:
            self.bus.add_signal_receiver(
                self.on_action_invoked,
                signal_name='ActionInvoked',
                dbus_interface='org.freedesktop.Notifications',
                bus_name='org.freedesktop.Notifications',
                path='/org/freedesktop/Notifications'
            )
            logger.info("Connected to notification D-Bus signals")
        except Exception as e:
            logger.error(f"Failed to set up notification listener: {e}")

    def on_action_invoked(self, notification_id, action_key):
        """Handle notification action clicks"""
        logger.info(f"Action invoked: notification_id={notification_id}, action={action_key}")

        if action_key == "focus_terminal":
            session = self.registry.get_session_by_notification(str(notification_id))

            if not session:
                self.send_error_notification(
                    "Focus Failed",
                    "Session no longer active. This notification may be stale."
                )
                logger.error(f"No session found for notification {notification_id}")
                return

            # Try to focus the terminal
            success = self.focus_terminal_for_session(session)

            if not success:
                self.send_error_notification(
                    "Focus Failed",
                    f"Could not focus terminal for session in {session.cwd}"
                )

    def focus_terminal_for_session(self, session: SessionInfo) -> bool:
        """Focus the terminal window for a specific session"""
        try:
            # Get list of windows using Window Calls extension
            result = subprocess.run([
                'gdbus', 'call', '--session',
                '--dest=org.gnome.Shell',
                '--object-path=/org/gnome/Shell/Extensions/Windows',
                '--method=org.gnome.Shell.Extensions.Windows.List'
            ], capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                logger.error("Window Calls extension not available")
                self.send_error_notification(
                    "Focus Failed",
                    "Window Calls GNOME extension is required but not available.\n"
                    "See README for installation instructions."
                )
                return False

            # Parse window list
            import json
            windows_data = result.stdout.strip()
            if not (windows_data.startswith("('[") and windows_data.endswith("',)")):
                logger.error(f"Unexpected Window Calls output: {windows_data[:100]}")
                return False

            json_str = windows_data[2:-3]
            windows = json.loads(json_str)

            # Find terminal windows
            terminal_windows = [
                w for w in windows
                if w.get('wm_class') == 'gnome-terminal-server'
            ]

            if not terminal_windows:
                logger.error("No terminal windows found")
                self.send_error_notification(
                    "Focus Failed",
                    "No terminal windows are open."
                )
                return False

            # Try to find the specific terminal for this session
            # For now, use the working directory in the title as a heuristic
            target_window = None
            cwd_basename = os.path.basename(session.cwd) or session.cwd

            for window in terminal_windows:
                title = window.get('title', '')
                # Check if the window title contains the working directory
                if session.cwd in title or cwd_basename in title:
                    target_window = window
                    logger.info(f"Found matching terminal: {title}")
                    break

            if not target_window:
                # We cannot determine which terminal to focus
                logger.error(f"Could not determine terminal for session in {session.cwd}")
                self.send_error_notification(
                    "Focus Failed",
                    f"Could not determine which terminal window contains the session in {session.cwd}"
                )
                return False

            # Focus the terminal window
            window_id = target_window['id']
            activate_result = subprocess.run([
                'gdbus', 'call', '--session',
                '--dest=org.gnome.Shell',
                '--object-path=/org/gnome/Shell/Extensions/Windows',
                '--method=org.gnome.Shell.Extensions.Windows.Activate',
                str(window_id)
            ], capture_output=True, text=True, timeout=5)

            if activate_result.returncode == 0:
                logger.info(f"Successfully focused terminal window {window_id}")
                return True
            else:
                logger.error(f"Failed to activate window: {activate_result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error focusing terminal: {e}")
            return False

    def send_error_notification(self, title: str, message: str):
        """Send an error notification to the user"""
        try:
            bus = dbus.SessionBus()
            notify_service = bus.get_object(
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications"
            )
            notify_interface = dbus.Interface(
                notify_service,
                "org.freedesktop.Notifications"
            )

            notify_interface.Notify(
                "Claude Focus",      # app name
                0,                   # replaces id
                "dialog-error",      # icon
                title,               # summary
                message,             # body
                ["dismiss", "Dismiss"],  # actions
                {"urgency": dbus.Byte(2)},  # hints
                5000                 # timeout in ms
            )
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    @dbus.service.method(
        dbus_interface=SERVICE_NAME,
        in_signature='ssi', out_signature='b'
    )
    def RegisterSession(self, session_id: str, cwd: str, pid: int) -> bool:
        """D-Bus method to register a Claude session"""
        return self.registry.register_session(session_id, cwd, pid)

    @dbus.service.method(
        dbus_interface=SERVICE_NAME,
        in_signature='ss', out_signature=''
    )
    def MapNotification(self, notification_id: str, session_id: str):
        """D-Bus method to map notification ID to session ID"""
        self.registry.map_notification(notification_id, session_id)

    def run(self):
        """Start the service main loop"""
        # Set up periodic cleanup
        GLib.timeout_add_seconds(CLEANUP_INTERVAL, self.cleanup_timer)

        # Run the main loop
        try:
            self.loop = GLib.MainLoop()
            logger.info("Service ready, entering main loop")
            self.loop.run()
        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
            self.loop.quit()

    def cleanup_timer(self):
        """Timer callback for periodic cleanup"""
        self.registry.cleanup_stale_sessions()
        return True  # Continue timer


def main():
    """Main entry point"""
    try:
        service = ClaudeFocusService()
        service.run()
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()