# Design Document: claude-notify-gnome

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Data Flow](#data-flow)
5. [Implementation Details](#implementation-details)
6. [Configuration](#configuration)
7. [Platform Notes](#platform-notes)

## Overview

A notification system for Claude Code that displays desktop notifications when Claude needs user attention and automatically dismisses them based on user activity and Claude's execution state.

### Features

- Desktop notifications via D-Bus when Claude is idle or needs permission
- Automatic dismissal when user responds or Claude resumes execution
- 45-second idle timer that triggers delayed notification after Claude finishes responding
- Per-session notification tracking
- Context information: current directory and timestamp

## Architecture

Hook-based system that responds to Claude Code lifecycle events. Uses D-Bus for notification management and file-based state tracking.

```
Claude Code
    │ (JSON via stdin for each event)
    ▼
notify_hook.py
    │
    ├─→ D-Bus Notifications (send/close)
    │
    ├─→ Idle Timer (detached background process)
    │
    └─→ State Files (~/.claude/)
            ├─ active-notifications.json
            └─ idle-timer.json
```

## Components

### notify_hook.py

Main hook handler that processes Claude lifecycle events.

**Event Handling**:

| Event | Action |
|-------|--------|
| `Notification` | Send notification, cancel idle timer |
| `UserPromptSubmit` | Close notification, cancel idle timer |
| `PreToolUse` | Close notification, cancel idle timer |
| `PostToolUse` | Close notification |
| `Stop` | Close notification, start 45s idle timer |

**Key Functions**:

- `send_notification_with_actions(title, message, session_id)` - Sends notification via D-Bus
  - Uses org.freedesktop.Notifications interface
  - Returns notification_id for later dismissal
  - Sets urgency to critical (persistent notification)

- `close_notification(notification_id)` - Closes active notification via D-Bus

- `save_notification_id(session_id, notification_id)` - Persists notification ID to `~/.claude/active-notifications.json`

- `get_notification_id(session_id)` - Retrieves active notification ID for a session

- `save_idle_timer(session_id, cwd)` - Writes idle timer state to `~/.claude/idle-timer.json`

- `clear_idle_timer()` - Deletes `idle-timer.json` to cancel pending notification

- `spawn_idle_notification_timer()` - Launches detached background process that:
  1. Sleeps 45 seconds
  2. Checks if `idle-timer.json` still exists (cancellation check)
  3. Checks if notification already active (activity check)
  4. Sends idle notification if both checks pass

- `get_terminal_screen_uuid()` - Extracts GNOME_TERMINAL_SCREEN from bash parent process environment (used for terminal identification, currently not actively used)

**Input Format** (JSON via stdin):
```json
{
  "hook_event_name": "Notification",
  "message": "Claude needs your attention",
  "session_id": "abc123-...",
  "cwd": "/path/to/directory"
}
```

### claude_focus_service.py

Background D-Bus service for terminal focus (currently disabled).

**Status**: Action buttons are disabled in notify_hook.py:230-235, so this service is not actively used.

Original functionality:
- Listens for ActionInvoked D-Bus signals
- Maps notification IDs to Claude sessions
- Focuses terminal windows via Window Calls GNOME extension on Wayland
- Session registry with working directory tracking

### terminal_finder.py

Utility for terminal discovery and focus testing.

**Capabilities**:
- Process tree walking via `/proc/<pid>/stat`
- Find processes by working directory via `/proc/<pid>/cwd`
- Terminal window enumeration
- Focus terminal on Wayland via Window Calls extension
- Session type detection (X11 vs Wayland)

**Commands**:
```bash
./terminal_finder.py analyze    # Show current session info
./terminal_finder.py focus      # Test terminal focus
./terminal_finder.py directory /path  # Find processes in directory
```

## Data Flow

### Notification Event

```
1. Claude emits "Notification" event
2. notify_hook.py parses JSON from stdin
3. Cancel idle timer (delete idle-timer.json)
4. Close existing notification for session if present
5. Format notification body: message + directory + timestamp
6. Call D-Bus Notify method → returns notification_id
7. Save notification_id to active-notifications.json
8. GNOME shows notification
```

### UserPromptSubmit Event (User Responds)

```
1. User starts typing in Claude
2. Claude emits "UserPromptSubmit" event
3. notify_hook.py parses event
4. Cancel idle timer (delete idle-timer.json)
5. Lookup notification_id from active-notifications.json
6. Call D-Bus CloseNotification
7. Remove entry from active-notifications.json
8. GNOME dismisses notification
```

### Stop Event (Idle Timer)

```
1. Claude emits "Stop" event
2. notify_hook.py closes any active notification
3. Write idle timer data to idle-timer.json
4. Spawn detached background process with --idle-timer flag
5. Background process sleeps 45 seconds
6. Check if idle-timer.json exists (no = cancelled)
7. Check if notification already active (yes = user active)
8. Send notification "⏳ Claude is Waiting"
9. Save notification_id to active-notifications.json
10. Delete idle-timer.json
```

### State Files

**~/.claude/active-notifications.json**:
```json
{
  "session-abc123": {
    "notification_id": 42,
    "timestamp": "2025-10-11T10:30:00"
  }
}
```

**~/.claude/idle-timer.json**:
```json
{
  "session_id": "session-abc123",
  "cwd": "/home/user/project",
  "timestamp": "2025-10-11T10:30:00",
  "trigger_time": 1728645045.0
}
```

## Implementation Details

### D-Bus Integration

Uses freedesktop Notifications specification.

**Send Notification**:
```python
bus = dbus.SessionBus()
notify_service = bus.get_object(
    "org.freedesktop.Notifications",
    "/org/freedesktop/Notifications"
)
notify_interface = dbus.Interface(
    notify_service,
    "org.freedesktop.Notifications"
)

notification_id = notify_interface.Notify(
    "Claude Code",              # app_name
    0,                          # replaces_id (0 = new)
    "dialog-information",       # icon
    title,                      # summary
    message,                    # body
    [],                         # actions (disabled)
    {"urgency": dbus.Byte(2)},  # hints (2 = critical)
    0                           # timeout (0 = persistent)
)
```

**Close Notification**:
```python
notify_interface.CloseNotification(dbus.UInt32(notification_id))
```

### Process Tree Walking

To identify the terminal hosting Claude:

1. Get current PID (notify_hook.py process)
2. Read `/proc/<PID>/stat` → extract parent PID (Claude process)
3. Read `/proc/<claude_pid>/stat` → extract parent PID (bash shell)
4. Read `/proc/<bash_pid>/environ` → extract GNOME_TERMINAL_SCREEN UUID

This provides unique terminal tab identification.

### Idle Timer Implementation

Uses detached subprocess to avoid blocking the hook handler:

```python
subprocess.Popen(
    [sys.executable, str(script_path), '--idle-timer'],
    start_new_session=True,    # Detach from parent process
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
```

The background process runs `run_idle_timer()` which:
- Sleeps 45 seconds
- Checks for file existence (cancellation mechanism)
- Checks for existing notifications (activity detection)
- Sends notification if conditions met

Cancellation works via file deletion - any new event removes `idle-timer.json`.

### Notification State Machine

```
No Notification
    │
    │ (Notification event)
    ▼
Active Notification
    │
    ├─ UserPromptSubmit → Dismissed + Cancel Timer
    ├─ PreToolUse → Dismissed + Cancel Timer
    ├─ PostToolUse → Dismissed
    └─ Stop → Dismissed + Start Timer
                │
                │ (45s idle)
                ▼
            Active Idle Notification
                │
                │ (UserPromptSubmit)
                ▼
            Dismissed + Cancel Timer
```

### Error Handling

- Missing D-Bus service: Log error, continue
- File access errors: Log warning, continue
- Missing notification tracking: Assume already dismissed
- Invalid JSON: Log error, exit cleanly
- Race conditions in timer cancellation: Handled by file existence checks

### Logging

Log file: `/tmp/claude-notify.log`

Format: `%(asctime)s - %(levelname)s - %(message)s`

Levels:
- DEBUG: State changes, D-Bus calls
- INFO: Notification lifecycle, timer events
- WARNING: Missing files, unavailable services
- ERROR: Core functionality failures

## Configuration

### Claude Code Hooks

Configured in `settings.json`:

```json
{
  "hooks": {
    "Notification": [{"hooks": [{"type": "command", "command": "./notify_hook.py"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "./notify_hook.py"}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "./notify_hook.py"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "./notify_hook.py"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "./notify_hook.py"}]}]
  }
}
```

### Configuration Constants

In `notify_hook.py`:

```python
IDLE_NOTIFICATION_DELAY = 45  # seconds

# Notification urgency: 0=low, 1=normal, 2=critical
hints = {"urgency": dbus.Byte(2)}

# Timeout: 0=persistent, N=milliseconds
timeout = 0
```

### Dependencies

Required:
- `python3` (3.8+)
- `python3-dbus` - D-Bus bindings
- `python3-gi` - GObject introspection

Installation:
```bash
sudo apt install python3-dbus python3-gi
```

## Platform Notes

### GNOME on Wayland

Primary target platform. Tested on Ubuntu 24.04.

Notification functionality works out of the box.

Terminal focus (currently disabled) requires Window Calls extension:
- Extension: https://extensions.gnome.org/extension/4724/window-calls/
- Provides D-Bus interface at `org.gnome.Shell.Extensions.Windows`
- Required because GNOME 41+ disabled direct window management APIs

### GNOME on X11

Notification functionality works identically.

Terminal focus could use `wmctrl` or `xdotool` directly (not implemented as focus is disabled).

### Other Desktop Environments

Untested. Should work if desktop has freedesktop-compatible notification daemon.

### Wayland Terminal Focus

Wayland's security model prevents cross-application window manipulation. Options:

1. **GNOME Shell Extension** (Window Calls): Provides controlled D-Bus interface for window management
2. **X11 tools** (wmctrl, xdotool): Not compatible with Wayland
3. **Direct Wayland protocols**: No standard window focus protocol exists

See TERMINAL_FOCUS_METHODS.md for detailed technical explanation.

## Known Limitations

1. Action buttons (Focus Terminal) are disabled
2. Idle timer delay is hard-coded to 45 seconds
3. All notifications use critical urgency (persistent)
4. GNOME-focused implementation
5. No notification grouping for multiple sessions
6. Terminal focus requires external GNOME extension
