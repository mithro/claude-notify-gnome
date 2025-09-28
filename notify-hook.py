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
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename='/tmp/claude-notify.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def send_notification(title, message, urgency=2, timeout=0):
    """
    Send desktop notification via D-Bus

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

        logging.info(f"Notification sent successfully (ID: {notification_id})")
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

        logging.info(f"Session: {session_id}")
        logging.info(f"Message: {message}")

        # Determine notification details based on message content
        message_lower = message.lower()

        if "waiting for your input" in message_lower:
            # Claude is idle and waiting for user
            title = "⏳ Claude is Waiting"
            body = "Claude has finished processing and is waiting for your response"
            urgency = 2  # Critical - stays visible
            icon = "dialog-question"

        elif "permission" in message_lower:
            # Claude needs permission for a tool
            title = "🔒 Permission Required"
            body = message
            urgency = 2  # Critical - needs user action
            icon = "dialog-warning"

        elif "idle" in message_lower:
            # General idle notification
            title = "💭 Claude is Idle"
            body = "Claude is waiting for your input"
            urgency = 2
            icon = "dialog-information"

        else:
            # Generic notification
            title = "Claude Code Notification"
            body = message
            urgency = 1  # Normal priority
            icon = "dialog-information"

        # Add timestamp to the body
        timestamp = datetime.now().strftime("%H:%M:%S")
        body = f"{body}\n[{timestamp}]"

        # Send the notification
        success = send_notification(title, body, urgency=urgency)

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