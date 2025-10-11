#!/usr/bin/env python3
"""
Claude Focus Service
Background D-Bus service that handles notification clicks to focus Claude terminals

This service:
1. Listens for ActionInvoked signals from notifications
2. Maps Claude session IDs to terminal windows
3. Focuses the correct terminal when notifications are clicked
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
from pathlib import Path
from typing import Dict, Optional, Tuple, List

# Import our terminal tabs library
import gnome_terminal_tabs as gtt

# Configuration
SERVICE_NAME = "com.claude.FocusService"
OBJECT_PATH = "/com/claude/FocusService"
SESSION_DATA_FILE = os.path.expanduser("~/.claude/session-data.json")
LOG_FILE = "/tmp/claude-focus-service.log"

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SessionManager:
    """Manages Claude session to terminal window mapping"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.load_sessions()

    def load_sessions(self):
        """Load session data from disk"""
        try:
            if os.path.exists(SESSION_DATA_FILE):
                with open(SESSION_DATA_FILE, 'r') as f:
                    self.sessions = json.load(f)
                logger.info(f"Loaded {len(self.sessions)} sessions from disk")
            else:
                logger.info("No existing session data found")
        except Exception as e:
            logger.error(f"Failed to load session data: {e}")
            self.sessions = {}

    def save_sessions(self):
        """Save session data to disk"""
        try:
            os.makedirs(os.path.dirname(SESSION_DATA_FILE), exist_ok=True)
            with open(SESSION_DATA_FILE, 'w') as f:
                json.dump(self.sessions, f, indent=2)
            logger.debug("Session data saved to disk")
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")

    def register_session(self, session_id: str, cwd: str, terminal_screen: str):
        """Register a Claude session with its context"""
        self.sessions[session_id] = {
            'cwd': cwd,
            'terminal_screen': terminal_screen,
            'registered_at': time.time(),
            'last_activity': time.time()
        }
        self.save_sessions()
        logger.info(f"Registered session {session_id[:8]}... in {cwd} with terminal {terminal_screen[:16] if terminal_screen else 'unknown'}...")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        return self.sessions.get(session_id)

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove sessions older than max_age_hours"""
        cutoff = time.time() - (max_age_hours * 3600)
        old_sessions = [
            sid for sid, data in self.sessions.items()
            if data.get('last_activity', 0) < cutoff
        ]

        for session_id in old_sessions:
            del self.sessions[session_id]
            logger.debug(f"Cleaned up old session {session_id[:8]}...")

        if old_sessions:
            self.save_sessions()
            logger.info(f"Cleaned up {len(old_sessions)} old sessions")

class TerminalFinder:
    """Finds and focuses terminal windows"""

    @staticmethod
    def find_processes_by_cwd(target_cwd: str) -> List[int]:
        """Find process PIDs that have the target current working directory"""
        pids = []
        try:
            # Look for processes in the target directory
            result = subprocess.run(
                ['pgrep', '-f', 'claude'],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                for pid_str in result.stdout.strip().split('\n'):
                    if pid_str:
                        try:
                            pid = int(pid_str)
                            # Check if this process has the right CWD
                            cwd_link = f"/proc/{pid}/cwd"
                            if os.path.exists(cwd_link):
                                actual_cwd = os.readlink(cwd_link)
                                if actual_cwd == target_cwd:
                                    pids.append(pid)
                        except (ValueError, OSError):
                            continue

        except Exception as e:
            logger.error(f"Error finding processes by CWD: {e}")

        return pids

    @staticmethod
    def find_terminal_window_by_pid(claude_pid: int) -> Optional[str]:
        """Find the terminal window ID that contains the Claude process"""
        try:
            # Walk up the process tree to find the terminal
            current_pid = claude_pid

            for _ in range(10):  # Prevent infinite loops
                try:
                    # Get parent PID
                    with open(f"/proc/{current_pid}/stat", 'r') as f:
                        stat_data = f.read().split()
                        parent_pid = int(stat_data[3])

                    # Get process command
                    with open(f"/proc/{parent_pid}/comm", 'r') as f:
                        comm = f.read().strip()

                    logger.debug(f"Process tree: {current_pid} -> {parent_pid} ({comm})")

                    # Check if this is a terminal process
                    if comm in ['gnome-terminal-', 'gnome-terminal', 'terminator', 'xterm', 'konsole']:
                        # Found terminal, now find its window ID
                        window_id = TerminalFinder.find_window_by_pid(parent_pid)
                        if window_id:
                            logger.info(f"Found terminal window {window_id} for PID {claude_pid}")
                            return window_id

                    current_pid = parent_pid
                    if current_pid <= 1:
                        break

                except (FileNotFoundError, ValueError, IndexError):
                    break

        except Exception as e:
            logger.error(f"Error walking process tree: {e}")

        return None

    @staticmethod
    def find_window_by_pid(pid: int) -> Optional[str]:
        """Find X11 window ID by process PID using wmctrl"""
        try:
            result = subprocess.run(
                ['wmctrl', '-lp'],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 3:
                        window_id = parts[0]
                        window_pid = parts[2]
                        if window_pid == str(pid):
                            return window_id

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"wmctrl not available or failed: {e}")

        return None

    @staticmethod
    def focus_window(window_id: str) -> bool:
        """Focus a window by its ID"""
        try:
            # Try wmctrl first
            result = subprocess.run(
                ['wmctrl', '-ia', window_id],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                logger.info(f"Successfully focused window {window_id} with wmctrl")
                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("wmctrl focus failed, trying xdotool")

        try:
            # Fallback to xdotool
            result = subprocess.run(
                ['xdotool', 'windowactivate', window_id],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                logger.info(f"Successfully focused window {window_id} with xdotool")
                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("xdotool focus failed")

        logger.error(f"Failed to focus window {window_id}")
        return False

    @staticmethod
    def focus_gnome_terminal_tab(terminal_screen_uuid: str = None, target_cwd: str = None) -> bool:
        """
        Focus a specific GNOME Terminal tab using the SearchProvider D-Bus interface.

        Args:
            terminal_screen_uuid: The GNOME_TERMINAL_SCREEN UUID (preferred method)
            target_cwd: The working directory (fallback method)

        Returns:
            bool: True if tab was focused successfully
        """
        try:
            # Method 1: Focus by terminal UUID (most accurate)
            if terminal_screen_uuid:
                logger.debug(f"Attempting to focus tab by UUID: {terminal_screen_uuid[:16]}...")
                if gtt.focus_tab(terminal_screen_uuid):
                    logger.info(f"Successfully focused terminal tab using UUID")
                    return True
                else:
                    logger.debug(f"Failed to focus tab by UUID, trying directory fallback")

            # Method 2: Focus by working directory (fallback)
            if target_cwd:
                logger.debug(f"Attempting to focus tab by directory: {target_cwd}")
                if gtt.focus_tab_by_directory(target_cwd):
                    logger.info(f"Successfully focused terminal tab using directory")
                    return True
                else:
                    logger.debug(f"Failed to focus tab by directory")

            logger.warning("All terminal tab focus methods failed")
            return False

        except gtt.GnomeTerminalError as e:
            logger.error(f"Terminal tab focus error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error focusing terminal tab: {e}")
            return False

    @staticmethod
    def detect_session_type() -> str:
        """Detect if running on X11 or Wayland"""
        return os.environ.get('XDG_SESSION_TYPE', 'unknown')

class ClaudeFocusService(dbus.service.Object):
    """D-Bus service for handling Claude notification focus requests"""

    def __init__(self):
        self.session_manager = SessionManager()
        self.terminal_finder = TerminalFinder()

        # Set up D-Bus
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()

        # Take the bus name
        self.bus_name = dbus.service.BusName(SERVICE_NAME, self.bus)
        super().__init__(self.bus_name, OBJECT_PATH)

        # Connect to notification signals
        self.setup_notification_listener()

        logger.info("Claude Focus Service started")

    def setup_notification_listener(self):
        """Set up listener for notification ActionInvoked signals"""
        try:
            # Connect to ActionInvoked signal
            self.bus.add_signal_receiver(
                self.on_action_invoked,
                signal_name='ActionInvoked',
                dbus_interface='org.freedesktop.Notifications',
                path='/org/freedesktop/Notifications'
            )

            # Connect to NotificationClosed signal for cleanup
            self.bus.add_signal_receiver(
                self.on_notification_closed,
                signal_name='NotificationClosed',
                dbus_interface='org.freedesktop.Notifications',
                path='/org/freedesktop/Notifications'
            )

            logger.info("Connected to notification D-Bus signals")

        except Exception as e:
            logger.error(f"Failed to setup notification listener: {e}")

    def on_action_invoked(self, notification_id, action_key):
        """Handle notification action clicks"""
        logger.info(f"Action invoked: notification_id={notification_id}, action_key={action_key}")

        if action_key == "focus_terminal":
            # Get session ID from notification mapping
            session_id = self.get_session_from_notification(notification_id)
            if session_id:
                self.handle_focus_request_for_session(session_id)
            else:
                # Fallback: focus most recent session
                self.handle_focus_request(notification_id)
        elif action_key == "dismiss":
            logger.info(f"Notification {notification_id} dismissed by user")

    def on_notification_closed(self, notification_id, reason):
        """Handle notification being closed"""
        logger.debug(f"Notification closed: id={notification_id}, reason={reason}")

    def get_session_from_notification(self, notification_id):
        """Get session ID from notification ID mapping"""
        try:
            mapping_file = os.path.expanduser("~/.claude/notification-mapping.json")
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r') as f:
                    mappings = json.load(f)
                    return mappings.get(str(notification_id))
        except Exception as e:
            logger.error(f"Failed to read notification mapping: {e}")
        return None

    def handle_focus_request_for_session(self, session_id):
        """Handle focus request for a specific session"""
        session_data = self.session_manager.get_session(session_id)
        if session_data:
            logger.info(f"Focusing specific session {session_id[:8]}...")
            return self.focus_session(session_id, session_data)
        else:
            logger.warning(f"Session {session_id[:8]}... not found")
            return False

    def handle_focus_request(self, notification_id):
        """Handle a request to focus a Claude terminal"""
        # For now, we'll implement a simple approach:
        # Try to focus the most recently active Claude session

        if not self.session_manager.sessions:
            logger.warning("No active Claude sessions found")
            return

        # Find the most recent session
        latest_session = max(
            self.session_manager.sessions.items(),
            key=lambda item: item[1].get('last_activity', 0)
        )

        session_id, session_data = latest_session
        self.focus_session(session_id, session_data)

    def focus_session(self, session_id: str, session_data: Dict):
        """Focus the terminal for a specific Claude session"""
        cwd = session_data.get('cwd', '')
        terminal_screen = session_data.get('terminal_screen', '')

        logger.info(f"Attempting to focus session {session_id[:8]}... in {cwd}")

        # Convert terminal_screen path to UUID format if needed
        terminal_uuid = None
        if terminal_screen:
            terminal_uuid = gtt.extract_uuid_from_screen_path(terminal_screen)
            if terminal_uuid:
                logger.debug(f"Converted terminal_screen to UUID: {terminal_uuid}")

        # Use the new terminal tab focusing method
        # This works on both X11 and Wayland
        if self.terminal_finder.focus_gnome_terminal_tab(terminal_uuid, cwd):
            # Update last activity
            session_data['last_activity'] = time.time()
            self.session_manager.save_sessions()
            logger.info(f"Successfully focused terminal for session {session_id[:8]}...")
            return True
        else:
            logger.warning(f"Could not focus terminal for session {session_id[:8]}...")
            return False

    @dbus.service.method(
        dbus_interface="com.claude.FocusService",
        in_signature='sss', out_signature='b'
    )
    def RegisterSession(self, session_id, cwd, terminal_screen):
        """D-Bus method to register a Claude session"""
        self.session_manager.register_session(session_id, cwd, terminal_screen)
        return True

    @dbus.service.method(
        dbus_interface="com.claude.FocusService",
        in_signature='s', out_signature='b'
    )
    def FocusSession(self, session_id):
        """D-Bus method to focus a specific session"""
        session_data = self.session_manager.get_session(session_id)
        if session_data:
            return self.focus_session(session_id, session_data)
        return False

    @dbus.service.method(
        dbus_interface="com.claude.FocusService",
        in_signature='s', out_signature='b'
    )
    def DismissNotifications(self, session_id):
        """D-Bus method to dismiss all notifications for a session"""
        try:
            active_file = os.path.expanduser("~/.claude/active-notifications.json")

            if not os.path.exists(active_file):
                return True

            # Load active notifications
            with open(active_file, 'r') as f:
                active = json.load(f)

            # Check if this session has active notifications
            if session_id not in active:
                return True

            notification_data = active[session_id]
            notification_id = notification_data['notification_id']

            logger.info(f"Dismissing notification {notification_id} for session {session_id[:8]}...")

            # Dismiss the notification via D-Bus
            notify_service = self.bus.get_object(
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications"
            )
            notify_interface = dbus.Interface(
                notify_service,
                "org.freedesktop.Notifications"
            )

            # CloseNotification method
            notify_interface.CloseNotification(notification_id)

            # Remove from active notifications
            del active[session_id]

            # Save updated active notifications
            with open(active_file, 'w') as f:
                json.dump(active, f, indent=2)

            logger.info(f"Successfully dismissed notification {notification_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to dismiss notifications for session {session_id[:8]}...: {e}")
            return False

def main():
    """Main entry point"""
    logger.info("Starting Claude Focus Service...")

    try:
        service = ClaudeFocusService()

        # Set up periodic cleanup
        def cleanup_timer():
            service.session_manager.cleanup_old_sessions()
            return True  # Keep timer running

        GLib.timeout_add_seconds(3600, cleanup_timer)  # Cleanup every hour

        # Start the main loop
        main_loop = GLib.MainLoop()
        logger.info("Service ready, entering main loop")
        main_loop.run()

    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()