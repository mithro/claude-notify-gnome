#!/usr/bin/env python3
"""
Claude Code Notification Hook - Simplified Version
Sends desktop notifications when Claude needs user attention
Automatically dismisses notifications when user responds or Claude starts working
"""

import json
import sys
import os
import dbus
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

# File paths for tracking notifications
CLAUDE_DIR = Path.home() / '.claude'
ACTIVE_NOTIFICATIONS_FILE = CLAUDE_DIR / 'active-notifications.json'
IDLE_TIMER_FILE = CLAUDE_DIR / 'idle-timer.json'

# Idle notification delay (seconds after Stop before sending idle notification)
IDLE_NOTIFICATION_DELAY = 45

# Logging setup (debug mode)
logging.basicConfig(
    filename='/tmp/claude-notify.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def save_notification_id(session_id: str, notification_id: int):
    """Save notification ID for a session to track active notifications"""
    try:
        # Load existing data
        data = {}
        if ACTIVE_NOTIFICATIONS_FILE.exists():
            with open(ACTIVE_NOTIFICATIONS_FILE, 'r') as f:
                data = json.load(f)

        # Update with new notification
        data[session_id] = {
            "notification_id": notification_id,
            "timestamp": datetime.now().isoformat()
        }

        # Save back to file
        with open(ACTIVE_NOTIFICATIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved notification ID {notification_id} for session {session_id[:8]}...")
    except Exception as e:
        logger.error(f"Failed to save notification ID: {e}")


def get_notification_id(session_id: str) -> Optional[int]:
    """Get the active notification ID for a session"""
    try:
        if not ACTIVE_NOTIFICATIONS_FILE.exists():
            return None

        with open(ACTIVE_NOTIFICATIONS_FILE, 'r') as f:
            data = json.load(f)

        session_data = data.get(session_id)
        if session_data:
            return session_data.get("notification_id")
        return None
    except Exception as e:
        logger.error(f"Failed to get notification ID: {e}")
        return None


def remove_notification_id(session_id: str):
    """Remove notification ID from tracking after dismissal"""
    try:
        if not ACTIVE_NOTIFICATIONS_FILE.exists():
            return

        with open(ACTIVE_NOTIFICATIONS_FILE, 'r') as f:
            data = json.load(f)

        if session_id in data:
            del data[session_id]

            with open(ACTIVE_NOTIFICATIONS_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Removed notification tracking for session {session_id[:8]}...")
    except Exception as e:
        logger.error(f"Failed to remove notification ID: {e}")


def save_idle_timer(session_id: str, cwd: str):
    """Save idle timer info to trigger delayed notification"""
    try:
        data = {
            "session_id": session_id,
            "cwd": cwd,
            "timestamp": datetime.now().isoformat(),
            "trigger_time": (datetime.now().timestamp() + IDLE_NOTIFICATION_DELAY)
        }
        with open(IDLE_TIMER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved idle timer for session {session_id[:8]}... (will trigger in {IDLE_NOTIFICATION_DELAY}s)")
    except Exception as e:
        logger.error(f"Failed to save idle timer: {e}")


def clear_idle_timer():
    """Clear idle timer (cancel pending notification)"""
    try:
        if IDLE_TIMER_FILE.exists():
            IDLE_TIMER_FILE.unlink()
            logger.debug("Cleared idle timer")
    except Exception as e:
        logger.error(f"Failed to clear idle timer: {e}")


def spawn_idle_notification_timer():
    """Spawn background process to send idle notification after delay"""
    try:
        import subprocess
        script_path = Path(__file__).resolve()
        # Spawn detached background process
        subprocess.Popen(
            [sys.executable, str(script_path), '--idle-timer'],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info("Spawned idle notification timer process")
    except Exception as e:
        logger.error(f"Failed to spawn idle timer: {e}")


def run_idle_timer():
    """Background process: wait and send idle notification if still needed"""
    import time

    logger.info(f"Idle timer started, waiting {IDLE_NOTIFICATION_DELAY} seconds...")
    time.sleep(IDLE_NOTIFICATION_DELAY)

    try:
        # Check if timer file still exists
        if not IDLE_TIMER_FILE.exists():
            logger.info("Idle timer cancelled (file removed)")
            return

        # Load timer data
        with open(IDLE_TIMER_FILE, 'r') as f:
            timer_data = json.load(f)

        session_id = timer_data.get('session_id')
        cwd = timer_data.get('cwd', '')

        # Check if there's already an active notification (activity happened)
        if get_notification_id(session_id):
            logger.info("Idle timer: notification already active, skipping")
            clear_idle_timer()
            return

        # Send idle notification
        logger.info(f"Idle timer triggered for session {session_id[:8] if session_id else 'unknown'}...")

        title = "⏳ Claude is Waiting"
        body = "Claude has finished processing and is waiting for your response"

        timestamp = datetime.now().strftime("%H:%M:%S")
        if cwd:
            dir_name = os.path.basename(cwd) or cwd
            body = f"{body}\n📁 {dir_name} • {timestamp}"
        else:
            body = f"{body}\n[{timestamp}]"

        notification_id = send_notification_with_actions(title, body, session_id)

        if notification_id:
            save_notification_id(session_id, notification_id)
            logger.info(f"Idle notification sent successfully (ID: {notification_id})")
        else:
            logger.error("Failed to send idle notification")

        # Clean up timer file
        clear_idle_timer()

    except Exception as e:
        logger.error(f"Idle timer error: {e}")
        import traceback
        logger.debug(traceback.format_exc())


def close_notification(notification_id: int) -> bool:
    """Close a notification using D-Bus"""
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

        # Call CloseNotification method
        notify_interface.CloseNotification(dbus.UInt32(notification_id))
        logger.info(f"Successfully closed notification {notification_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to close notification {notification_id}: {e}")
        return False


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

        # Handle UserPromptSubmit - user started typing, dismiss any active notification
        if event_type == 'UserPromptSubmit':
            logger.info("UserPromptSubmit - user is responding, dismissing notification")

            # Cancel any pending idle notification
            clear_idle_timer()

            notification_id = get_notification_id(session_id)
            if notification_id:
                if close_notification(notification_id):
                    remove_notification_id(session_id)
                    logger.info(f"Dismissed notification {notification_id} for session {session_id[:8]}...")
                else:
                    logger.warning(f"Failed to dismiss notification {notification_id}")
            else:
                logger.debug("No active notification to dismiss")
            return 0

        # Handle PreToolUse - Claude started working, dismiss any active notification
        if event_type == 'PreToolUse':
            logger.info("PreToolUse - Claude is working, dismissing notification")

            # Cancel any pending idle notification
            clear_idle_timer()

            notification_id = get_notification_id(session_id)
            if notification_id:
                if close_notification(notification_id):
                    remove_notification_id(session_id)
                    logger.info(f"Dismissed notification {notification_id} for session {session_id[:8]}...")
                else:
                    logger.warning(f"Failed to dismiss notification {notification_id}")
            else:
                logger.debug("No active notification to dismiss")
            return 0

        # Handle PostToolUse - Claude finished a tool, dismiss any active notification
        if event_type == 'PostToolUse':
            logger.info("PostToolUse - Claude finished tool execution, dismissing notification")
            notification_id = get_notification_id(session_id)
            if notification_id:
                if close_notification(notification_id):
                    remove_notification_id(session_id)
                    logger.info(f"Dismissed notification {notification_id} for session {session_id[:8]}...")
                else:
                    logger.warning(f"Failed to dismiss notification {notification_id}")
            else:
                logger.debug("No active notification to dismiss")
            return 0

        # Handle Stop - Claude finished responding, dismiss any active notification
        if event_type == 'Stop':
            logger.info("Stop - Claude finished responding, dismissing notification")
            notification_id = get_notification_id(session_id)
            if notification_id:
                if close_notification(notification_id):
                    remove_notification_id(session_id)
                    logger.info(f"Dismissed notification {notification_id} for session {session_id[:8]}...")
                else:
                    logger.warning(f"Failed to dismiss notification {notification_id}")
            else:
                logger.debug("No active notification to dismiss")

            # Start idle timer to send notification if user doesn't respond
            save_idle_timer(session_id, cwd)
            spawn_idle_notification_timer()

            return 0

        # Cancel any pending idle timer since we're sending a notification now
        clear_idle_timer()

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
            # Close any existing notification for this session before sending a new one
            old_notification_id = get_notification_id(session_id)
            if old_notification_id:
                logger.info(f"Closing previous notification {old_notification_id} before sending new one")
                close_notification(old_notification_id)

            notification_id = send_notification_with_actions(title, body, session_id)

            if notification_id:
                # Save notification ID for later dismissal
                save_notification_id(session_id, notification_id)

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
    # Check if running as idle timer background process
    if len(sys.argv) > 1 and sys.argv[1] == '--idle-timer':
        run_idle_timer()
        sys.exit(0)
    else:
        # Normal hook mode
        sys.exit(main())