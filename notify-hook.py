#!/usr/bin/env python3
"""
Claude Code Notification Hook
Sends desktop notifications when Claude is waiting for user input
Uses D-Bus directly - no external commands needed
"""

import json
import sys
import dbus
import logging
import os
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename='/tmp/claude-notify.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def register_session_with_service(session_id, cwd, transcript_path):
    """Register session with the Claude Focus Service"""
    try:
        bus = dbus.SessionBus()
        service = bus.get_object(
            "com.claude.FocusService",
            "/com/claude/FocusService"
        )
        focus_interface = dbus.Interface(
            service,
            "com.claude.FocusService"
        )

        success = focus_interface.RegisterSession(session_id, cwd, transcript_path)
        if success:
            logging.info(f"Successfully registered session {session_id[:8]}... with focus service")
        else:
            logging.warning(f"Failed to register session {session_id[:8]}... with focus service")

    except dbus.exceptions.DBusException as e:
        logging.debug(f"Focus service not available: {e}")
    except Exception as e:
        logging.error(f"Error registering session: {e}")

def store_notification_mapping(notification_id, session_id):
    """Store mapping between notification ID and session ID"""
    try:
        mapping_file = os.path.expanduser("~/.claude/notification-mapping.json")

        # Load existing mappings
        mappings = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                mappings = json.load(f)

        # Add new mapping
        mappings[str(notification_id)] = session_id

        # Clean up old mappings (keep only last 100)
        if len(mappings) > 100:
            # Keep only the most recent entries
            sorted_items = sorted(mappings.items(), key=lambda x: int(x[0]))
            mappings = dict(sorted_items[-100:])

        # Save mappings
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, 'w') as f:
            json.dump(mappings, f, indent=2)

        logging.debug(f"Stored notification mapping: {notification_id} -> {session_id[:8]}...")

    except Exception as e:
        logging.error(f"Failed to store notification mapping: {e}")

def track_active_notification(session_id, notification_id):
    """Track active notification for a session"""
    try:
        active_file = os.path.expanduser("~/.claude/active-notifications.json")

        # Load existing active notifications
        active = {}
        if os.path.exists(active_file):
            with open(active_file, 'r') as f:
                active = json.load(f)

        # Add new active notification for this session
        active[session_id] = {
            'notification_id': notification_id,
            'timestamp': datetime.now().isoformat()
        }

        # Save active notifications
        os.makedirs(os.path.dirname(active_file), exist_ok=True)
        with open(active_file, 'w') as f:
            json.dump(active, f, indent=2)

        logging.debug(f"Tracked active notification {notification_id} for session {session_id[:8]}...")

    except Exception as e:
        logging.error(f"Failed to track active notification: {e}")

def dismiss_previous_notifications(session_id):
    """Dismiss any previous notifications for this session when Claude starts working"""
    try:
        active_file = os.path.expanduser("~/.claude/active-notifications.json")

        if not os.path.exists(active_file):
            return

        # Load active notifications
        with open(active_file, 'r') as f:
            active = json.load(f)

        # Check if this session has active notifications
        if session_id not in active:
            return

        notification_data = active[session_id]
        notification_id = notification_data['notification_id']

        logging.info(f"Dismissing previous notification {notification_id} for session {session_id[:8]}...")

        # Dismiss the notification via D-Bus
        bus = dbus.SessionBus()
        notify_service = bus.get_object(
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

        logging.info(f"Successfully dismissed notification {notification_id}")

    except dbus.exceptions.DBusException as e:
        logging.debug(f"Could not dismiss notification via D-Bus: {e}")
    except Exception as e:
        logging.error(f"Failed to dismiss previous notifications: {e}")

def detect_claude_activity(input_data):
    """Detect if this hook call indicates Claude is starting work (not waiting)"""
    message = input_data.get('message', '').lower()
    hook_event = input_data.get('hook_event_name', '')

    # Indicators that Claude is starting work
    work_indicators = [
        'needs your permission',  # About to use a tool
        'permission to use',      # About to use a tool
    ]

    # Indicators that Claude is waiting/idle
    wait_indicators = [
        'waiting for your input',
        'is waiting',
        'idle'
    ]

    # If it's a waiting message, Claude is NOT working
    for indicator in wait_indicators:
        if indicator in message:
            return False

    # If it's a permission request, Claude is about to work
    for indicator in work_indicators:
        if indicator in message:
            return True

    # Default: assume it's activity unless explicitly a wait message
    return True

def send_notification_with_actions(title, message, session_id, urgency=2, timeout=0):
    """
    Send desktop notification with clickable actions

    Args:
        title: Notification title
        message: Notification body text
        session_id: Claude session ID for focus callback
        urgency: 0=low, 1=normal, 2=critical (persistent)
        timeout: Duration in ms (0 = persistent for critical)

    Returns:
        notification_id if successful, None otherwise
    """
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

        # Define actions - these appear as buttons on the notification
        actions = [
            "focus_terminal", "Focus Terminal",
            "dismiss", "Dismiss"
        ]

        # Enhanced hints for better notification experience
        hints = {
            "urgency": dbus.Byte(urgency),
            "category": dbus.String("im.received"),  # Message category
            "desktop-entry": dbus.String("org.gnome.Terminal"),  # Associate with terminal
        }

        # Send notification with actions
        # Parameters: app_name, replaces_id, icon, summary, body, actions, hints, timeout
        notification_id = notify_interface.Notify(
            "Claude Code",           # app name
            0,                      # replaces id (0 = new notification)
            "dialog-information",   # icon
            title,                  # summary
            message,                # body
            actions,                # actions
            hints,                  # hints
            timeout                 # timeout in ms
        )

        # Store the mapping for later action handling
        store_notification_mapping(notification_id, session_id)

        logging.info(f"Notification with actions sent successfully (ID: {notification_id})")
        return notification_id

    except dbus.exceptions.DBusException as e:
        logging.error(f"D-Bus error: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to send notification: {e}")
        return None

def send_notification(title, message, urgency=2, timeout=0):
    """
    Send basic desktop notification via D-Bus (fallback method)

    Args:
        title: Notification title
        message: Notification body text
        urgency: 0=low, 1=normal, 2=critical (persistent)
        timeout: Duration in ms (0 = persistent for critical)

    Returns:
        True if successful, False otherwise
    """
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

        # Send notification
        # Parameters: app_name, replaces_id, icon, summary, body, actions, hints, timeout
        notification_id = notify_interface.Notify(
            "Claude Code",           # app name
            0,                      # replaces id (0 = new notification)
            "dialog-information",   # icon
            title,                  # summary
            message,                # body
            [],                     # actions
            {"urgency": dbus.Byte(urgency)},  # hints
            timeout                 # timeout in ms
        )

        logging.info(f"Basic notification sent successfully (ID: {notification_id})")
        return True

    except dbus.exceptions.DBusException as e:
        logging.error(f"D-Bus error: {e}")
        return False
    except Exception as e:
        logging.error(f"Failed to send notification: {e}")
        return False

def main():
    """Main entry point for the notification hook"""

    logging.info("=" * 50)
    logging.info("Notification hook triggered")

    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Log the received data
        logging.debug(f"Received input: {json.dumps(input_data, indent=2)}")

        # Extract message and other fields
        message = input_data.get('message', 'Claude needs your attention')
        session_id = input_data.get('session_id', 'unknown')
        cwd = input_data.get('cwd', '')
        transcript_path = input_data.get('transcript_path', '')

        logging.info(f"Session: {session_id}")
        logging.info(f"Message: {message}")
        logging.info(f"CWD: {cwd}")

        # Check if Claude is starting work and dismiss previous notifications
        is_claude_working = detect_claude_activity(input_data)
        if is_claude_working and session_id != 'unknown':
            dismiss_previous_notifications(session_id)

        # Register session with focus service
        if session_id != 'unknown' and cwd:
            register_session_with_service(session_id, cwd, transcript_path)

        # Determine notification details based on message content
        message_lower = message.lower()

        if "waiting for your input" in message_lower:
            # Claude is idle and waiting for user
            title = "⏳ Claude is Waiting"
            body = "Claude has finished processing and is waiting for your response"
            urgency = 2  # Critical - stays visible
            use_actions = True

        elif "permission" in message_lower:
            # Claude needs permission for a tool
            title = "🔒 Permission Required"
            body = message
            urgency = 2  # Critical - needs user action
            use_actions = True

        elif "idle" in message_lower:
            # General idle notification
            title = "💭 Claude is Idle"
            body = "Claude is waiting for your input"
            urgency = 2
            use_actions = True

        else:
            # Generic notification
            title = "Claude Code Notification"
            body = message
            urgency = 1  # Normal priority
            use_actions = False

        # Add timestamp and directory info to the body
        timestamp = datetime.now().strftime("%H:%M:%S")
        if cwd:
            dir_name = os.path.basename(cwd) or cwd
            body = f"{body}\n📁 {dir_name} • {timestamp}"
        else:
            body = f"{body}\n[{timestamp}]"

        # Send the notification with or without actions
        notification_id = None
        if use_actions and session_id != 'unknown':
            notification_id = send_notification_with_actions(title, body, session_id, urgency=urgency)
            success = notification_id is not None
        else:
            success = send_notification(title, body, urgency=urgency)

        # Track the notification as active if it's a waiting/idle notification
        if success and notification_id and not is_claude_working and session_id != 'unknown':
            track_active_notification(session_id, notification_id)

        if success:
            logging.info("Notification delivered successfully")
            sys.exit(0)
        else:
            logging.error("Failed to deliver notification")
            # Don't exit with error - we don't want to break Claude's flow
            sys.exit(0)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON input: {e}")
        logging.debug(f"Raw stdin: {sys.stdin.read()}")
        sys.exit(0)  # Exit cleanly to not disrupt Claude

    except Exception as e:
        logging.error(f"Unexpected error in notification hook: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        sys.exit(0)  # Exit cleanly to not disrupt Claude

if __name__ == "__main__":
    main()