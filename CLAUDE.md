# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code notification system that displays desktop notifications when Claude needs attention and automatically dismisses them based on user activity. It integrates with Claude Code via hooks configured in `settings.json`.

## Architecture

The system has three main components:

1. **notify_hook.py** - Main hook handler that processes Claude lifecycle events (Notification, UserPromptSubmit, PreToolUse, PostToolUse, Stop). This is the active component that runs for every Claude event.

2. **claude_focus_service.py** - Background D-Bus service for terminal focus functionality. **Currently disabled** - action buttons are commented out in notify_hook.py:230-235.

3. **terminal_finder.py** - Utility for terminal discovery and focus testing. Used for development/debugging, not part of the active system.

### Key Design Patterns

**Event-driven with detached idle timer**: The hook handler must return immediately to Claude, so the 45-second idle timer spawns as a detached background process. Cancellation is handled via file deletion (`~/.claude/idle-timer.json`).

**State tracking via JSON files**: Notification IDs are persisted in `~/.claude/active-notifications.json` to enable dismissal across multiple hook invocations. Each hook invocation is stateless - state must be loaded from disk.

**D-Bus for all notification operations**: Uses `org.freedesktop.Notifications` interface for sending and closing notifications. No fallback methods - D-Bus is the only supported mechanism.

## Testing and Debugging

### Test notification system
```bash
# Simulate Claude notification event
echo '{"hook_event_name": "Notification", "session_id": "test-123", "cwd": "'$(pwd)'", "message": "Test notification"}' | ./notify_hook.py

# Watch notification logs
tail -f /tmp/claude-notify.log
```

### Test terminal discovery
```bash
./terminal_finder.py analyze    # Show current session info
./terminal_finder.py focus      # Test terminal focus
./terminal_finder.py directory /path  # Find processes in directory
```

### Manual service testing (if re-enabling focus)
```bash
# Run focus service manually
python3 ./claude_focus_service.py

# Check systemd service
systemctl --user status claude_focus.service
journalctl --user -u claude_focus.service -f
```

## Configuration

**settings.json** - Claude Code hook configuration. The hook is registered for 5 events: Notification, UserPromptSubmit, PreToolUse, PostToolUse, Stop.

**notify_hook.py constants**:
- `IDLE_NOTIFICATION_DELAY = 45` - seconds to wait before sending idle notification
- `ACTIVE_NOTIFICATIONS_FILE` - tracks notification IDs per session
- `IDLE_TIMER_FILE` - stores pending idle notification data

## State Files

Located in `~/.claude/`:
- **active-notifications.json** - Maps session_id → {notification_id, timestamp}
- **idle-timer.json** - Temporary file for pending idle notification (deleted when cancelled or triggered)

## Platform Notes

**Wayland terminal focus**: Requires Window Calls GNOME extension (`org.gnome.Shell.Extensions.Windows` D-Bus interface). GNOME 41+ disabled direct window management APIs. See TERMINAL_FOCUS_METHODS.md for technical details.

**X11 tools (wmctrl, xdotool)**: Not compatible with Wayland. Do not add fallback code using these tools.

## Dependencies

Required: `python3-dbus`, `python3-gi`

Install: `sudo apt install python3-dbus python3-gi`

## Important Implementation Notes

- Hook handler receives JSON via stdin with fields: hook_event_name, message, session_id, cwd
- All D-Bus operations use `dbus.SessionBus()`, not system bus
- Notification urgency is set to critical (2) for persistent notifications
- Idle timer uses `subprocess.Popen()` with `start_new_session=True` to detach
- Process tree walking reads `/proc/<pid>/stat` and `/proc/<pid>/environ` to identify terminal
- Focus service functionality is disabled but code remains for potential future use
