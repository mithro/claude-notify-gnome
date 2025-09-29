#!/usr/bin/env python3
"""
Claude Code Notification Hook - Simplified Version
Sends desktop notifications when Claude needs user attention
"""

import json
import sys
import os
import dbus
import logging
from datetime import datetime
from typing import Optional

# Logging setup (debug mode)
logging.basicConfig(
    filename='/tmp/claude-notify.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def send_notification_with_actions(title: str, message: str, session_id: str) -> Optional[int]:
    """Send desktop notification with clickable actions"""
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

        # Notification with action buttons (disabled for now)
        actions = []
        # actions = [
        #     "focus_terminal", "Focus Terminal",
        #     "dismiss", "Dismiss"
        # ]

        # Critical urgency = persistent notification
        hints = {"urgency": dbus.Byte(2)}

        notification_id = notify_interface.Notify(
            "Claude Code",           # app name
            0,                      # replaces id
            "dialog-information",   # icon
            title,                  # summary
            message,                # body
            actions,                # actions
            hints,                  # hints
            0                       # timeout (0 = persistent)
        )

        logger.info(f"Notification sent successfully (ID: {notification_id})")
        return notification_id

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return None


def get_terminal_screen_uuid() -> Optional[str]:
    """Get GNOME_TERMINAL_SCREEN UUID from the bash parent process"""
    try:
        # Walk up process tree: notify_hook -> claude -> bash
        current_pid = os.getpid()

        # Get Claude process (our parent)
        claude_pid = os.getppid()

        # Get bash process (Claude's parent)
        with open(f'/proc/{claude_pid}/stat', 'r') as f:
            stat_data = f.read().split()
            bash_pid = int(stat_data[3])  # ppid field

        # Read bash environment for GNOME_TERMINAL_SCREEN
        env_file = f'/proc/{bash_pid}/environ'
        with open(env_file, 'rb') as f:
            env_data = f.read().decode('utf-8', errors='ignore')

        # Parse environment variables
        env_vars = {}
        for line in env_data.split('\0'):
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value

        screen_uuid = env_vars.get('GNOME_TERMINAL_SCREEN')
        service_id = env_vars.get('GNOME_TERMINAL_SERVICE')

        if screen_uuid:
            logger.info(f"Found terminal screen UUID: {screen_uuid}")
            if service_id:
                logger.info(f"Found terminal service ID: {service_id}")
            return screen_uuid
        else:
            logger.warning("No GNOME_TERMINAL_SCREEN found in bash environment")
            return None

    except Exception as e:
        logger.error(f"Failed to get terminal screen UUID: {e}")
        return None


def register_session_with_service(session_id: str, cwd: str, terminal_screen: Optional[str], notification_id: int):
    """Register session with the Focus Service"""
    try:
        bus = dbus.SessionBus()

        # Check if service is running
        if not bus.name_has_owner("com.claude.FocusService"):
            logger.warning("Focus service not running")
            return

        service = bus.get_object(
            "com.claude.FocusService",
            "/com/claude/FocusService"
        )
        focus_interface = dbus.Interface(
            service,
            "com.claude.FocusService"
        )

        # Register session with terminal screen UUID
        success = focus_interface.RegisterSession(session_id, cwd, terminal_screen or "")
        if success:
            logger.info(f"Registered session {session_id[:8]}... with terminal screen {terminal_screen}")

            # Map notification to session
            focus_interface.MapNotification(str(notification_id), session_id)
            logger.info(f"Mapped notification {notification_id} to session {session_id[:8]}...")
        else:
            logger.warning(f"Failed to register session {session_id[:8]}...")

    except dbus.exceptions.DBusException as e:
        logger.debug(f"Focus service not available: {e}")
    except Exception as e:
        logger.error(f"Error registering session: {e}")


def main():
    """Main entry point for the notification hook"""
    logger.info("=" * 50)
    logger.info("Notification hook triggered")

    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
        logger.debug(f"Received: {json.dumps(input_data, indent=2)}")

        # Extract event data
        event_type = input_data.get('hook_event_name', '')
        message = input_data.get('message', 'Claude needs your attention')
        session_id = input_data.get('session_id', 'unknown')
        cwd = input_data.get('cwd', os.getcwd())

        # Get terminal screen UUID for precise terminal identification
        terminal_screen = get_terminal_screen_uuid()

        logger.info(f"Event: {event_type}")
        logger.info(f"Session: {session_id}")
        logger.info(f"CWD: {cwd}")
        logger.info(f"Terminal screen: {terminal_screen}")

        # Handle UserPromptSubmit - user started typing, no notification needed
        if event_type == 'UserPromptSubmit':
            logger.info("UserPromptSubmit - user is active, skipping notification")
            return 0

        # Determine notification details based on message
        message_lower = message.lower()

        if "waiting for your input" in message_lower or "idle" in message_lower:
            title = "⏳ Claude is Waiting"
            body = "Claude has finished processing and is waiting for your response"
        elif "permission" in message_lower:
            title = "🔒 Permission Required"
            body = message
        else:
            # Generic notification
            title = "Claude Code"
            body = message

        # Add context to notification
        timestamp = datetime.now().strftime("%H:%M:%S")
        if cwd:
            dir_name = os.path.basename(cwd) or cwd
            body = f"{body}\n📁 {dir_name} • {timestamp}"
        else:
            body = f"{body}\n[{timestamp}]"

        # Send notification with actions
        if session_id != 'unknown':
            notification_id = send_notification_with_actions(title, body, session_id)

            if notification_id:
                # Register with focus service (disabled for now)
                # register_session_with_service(session_id, cwd, terminal_screen, notification_id)
                logger.info("Notification delivered successfully")
            else:
                logger.error("Failed to deliver notification")
        else:
            logger.warning("No session ID provided, skipping notification")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON input: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.debug(traceback.format_exc())

    return 0


if __name__ == "__main__":
    sys.exit(main())