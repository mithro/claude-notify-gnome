"""GNOME notification manager using D-Bus."""

from typing import Optional

try:
    import dbus
except ImportError:
    dbus = None  # Will fail at runtime if actually used

from claude_notify.tracker.state import State


STATE_ICONS = {
    State.WORKING: "\u2699\ufe0f",  # ⚙️
    State.NEEDS_ATTENTION: "\u2753",  # ❓
    State.SESSION_LIMIT: "\u23f1\ufe0f",  # ⏱️
    State.API_ERROR: "\U0001f534",  # 🔴
}


class NotificationManager:
    """Manages GNOME desktop notifications via D-Bus."""

    def __init__(self):
        if dbus is None:
            raise RuntimeError("dbus-python not installed")

        self._bus = dbus.SessionBus()
        self._notify_obj = self._bus.get_object(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
        )
        self._notify_interface = dbus.Interface(
            self._notify_obj,
            "org.freedesktop.Notifications",
        )

    def show_persistent(
        self,
        session_id: str,
        friendly_name: str,
        project_name: str,
        state: State,
        activity: str,
        replaces_id: int = 0,
    ) -> int:
        """
        Show or update a persistent notification for a session.

        Args:
            session_id: Session identifier (for action handling)
            friendly_name: Human-friendly session name
            project_name: Project directory name
            state: Current session state
            activity: Current activity text
            replaces_id: Notification ID to replace (0 for new)

        Returns:
            Notification ID
        """
        icon = STATE_ICONS.get(state, "\u2753")
        summary = f"{icon} [{friendly_name}] {project_name}"
        body = activity or "Ready"

        actions = [
            f"focus:{session_id}", "Focus Terminal",
        ]

        hints = {
            "urgency": dbus.Byte(2),  # Critical - persistent
            "resident": dbus.Boolean(True),
            "desktop-entry": dbus.String("claude-notify"),
            "category": dbus.String("im.received"),
        }

        notif_id = self._notify_interface.Notify(
            "Claude Code",  # app_name
            replaces_id,    # replaces_id
            "dialog-information",  # icon
            summary,        # summary
            body,           # body
            actions,        # actions
            hints,          # hints
            0,              # timeout (0 = persistent)
        )

        return int(notif_id)

    def show_popup(
        self,
        session_id: str,
        friendly_name: str,
        project_name: str,
        message: str,
        timeout_ms: int = 10000,
    ) -> int:
        """
        Show a popup notification for attention.

        Args:
            session_id: Session identifier
            friendly_name: Human-friendly session name
            project_name: Project directory name
            message: Alert message
            timeout_ms: Auto-dismiss timeout in milliseconds

        Returns:
            Notification ID
        """
        summary = f"Claude needs attention"
        body = f"[{friendly_name}] {project_name}\n{message}"

        actions = [
            f"focus:{session_id}", "Focus Terminal",
        ]

        hints = {
            "urgency": dbus.Byte(1),  # Normal - popup
            "category": dbus.String("im.received"),
        }

        notif_id = self._notify_interface.Notify(
            "Claude Code",
            0,              # Always new notification
            "dialog-warning",
            summary,
            body,
            actions,
            hints,
            timeout_ms,
        )

        return int(notif_id)

    def dismiss(self, notification_id: int) -> None:
        """Dismiss a notification by ID."""
        try:
            self._notify_interface.CloseNotification(notification_id)
        except dbus.DBusException:
            pass  # Already closed or invalid ID
