"""Tests for GNOME notification manager."""

from unittest.mock import MagicMock, patch

from claude_notify.gnome.notifications import NotificationManager
from claude_notify.tracker.state import State


@patch("claude_notify.gnome.notifications.dbus")
def test_create_persistent_notification(mock_dbus):
    """Creates a persistent notification with correct hints."""
    mock_interface = MagicMock()
    mock_interface.Notify.return_value = 42
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface
    mock_dbus.Byte = lambda x: x
    mock_dbus.Boolean = lambda x: x
    mock_dbus.String = lambda x: x

    manager = NotificationManager()
    notif_id = manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.WORKING,
        activity="Running tests...",
    )

    assert notif_id == 42
    mock_interface.Notify.assert_called_once()

    # Check urgency hint was set to critical (2)
    call_args = mock_interface.Notify.call_args
    hints = call_args[0][6]  # 7th argument is hints
    assert hints.get("urgency") == 2


@patch("claude_notify.gnome.notifications.dbus")
def test_update_persistent_notification(mock_dbus):
    """Updates existing notification using replaces_id."""
    mock_interface = MagicMock()
    mock_interface.Notify.return_value = 42
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface
    mock_dbus.Byte = lambda x: x
    mock_dbus.Boolean = lambda x: x
    mock_dbus.String = lambda x: x

    manager = NotificationManager()

    # First call
    manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.WORKING,
        activity="Starting...",
    )

    # Update call
    manager.show_persistent(
        session_id="test-123",
        friendly_name="bold-cat",
        project_name="my-project",
        state=State.NEEDS_ATTENTION,
        activity="Waiting for input",
        replaces_id=42,
    )

    # Check second call used replaces_id
    second_call = mock_interface.Notify.call_args_list[1]
    replaces_id = second_call[0][1]  # 2nd argument is replaces_id
    assert replaces_id == 42


@patch("claude_notify.gnome.notifications.dbus")
def test_dismiss_notification(mock_dbus):
    """Can dismiss a notification by ID."""
    mock_interface = MagicMock()
    mock_dbus.SessionBus.return_value.get_object.return_value = MagicMock()
    mock_dbus.Interface.return_value = mock_interface

    manager = NotificationManager()
    manager.dismiss(42)

    mock_interface.CloseNotification.assert_called_once_with(42)
