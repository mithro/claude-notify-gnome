# Claude Code Click-to-Focus Notification System

> [!WARNING]
> **VIBE-CODED SOFTWARE AHEAD!**
>
> This project was entirely vibe-coded using Claude Code in a caffeine-fueled haze of enthusiasm and questionable life choices. It might destroy your computer, eat your grandma, or worse - make your notifications too useful. Use at your own risk! We are not responsible for any spontaneous terminal focus addiction, D-Bus dependency, or sudden urges to click all the things.

---

A sophisticated notification system that allows you to click desktop notifications to instantly focus the specific terminal tab containing your Claude Code session.

## Features

- 🖱️ **Clickable Notifications**: Click "Focus Terminal" to instantly switch to the correct terminal tab
- 🖥️ **Cross-Platform**: Works on both X11 and Wayland (Ubuntu 24.04 tested)
- 🎯 **Tab-Aware**: Focuses the exact terminal tab running Claude, not just the window
- 🔧 **Auto-Start**: Systemd service automatically starts the background focus handler
- 📁 **Context-Rich**: Notifications show current directory and timestamp
- ⚡ **Fast & Reliable**: Uses GNOME Terminal's SearchProvider D-Bus API for direct tab control

## Architecture

1. **notify_hook.py**: Enhanced notification hook with clickable actions
2. **claude_focus_service.py**: Background D-Bus service handling clicks
3. **gnome_terminal_tabs.py**: Library for GNOME Terminal tab control via D-Bus
4. **terminal_finder.py**: Advanced terminal discovery utility
5. **Systemd Service**: Auto-starting background service

## Installation

The system is already set up and running! The components are:

### Files Created
- `./notify_hook.py` - Notification hook (already configured in Claude)
- `./claude_focus_service.py` - Background focus service
- `./gnome_terminal_tabs.py` - Terminal tab control library
- `./terminal_finder.py` - Terminal discovery utility
- `./claude_focus.service` - Systemd service definition
- `./install_service.sh` - Service installer

### Systemd Service
```bash
# Check service status
systemctl --user status claude_focus.service

# View logs
journalctl --user -u claude_focus.service -f

# Stop/start service
systemctl --user stop claude_focus.service
systemctl --user start claude_focus.service
```

## How It Works

1. **Claude triggers notification**: When Claude waits for input or needs permission
2. **Enhanced hook**: `notify_hook.py` sends notification with "Focus Terminal" button
3. **Session registration**: Hook registers session info (including terminal UUID) with background service
4. **User clicks**: Click "Focus Terminal" button on notification
5. **Service handles click**: `claude_focus_service.py` receives D-Bus ActionInvoked signal
6. **Terminal tab focus**: Service uses `gnome_terminal_tabs.py` library to focus the exact tab

### Technical Details

#### SearchProvider D-Bus API Method
- Uses GNOME Terminal's `org.gnome.Shell.SearchProvider2` D-Bus interface
- `GetInitialResultSet([])` - Lists all terminal tabs with UUIDs
- `GetResultMetas(uuids)` - Retrieves tab metadata (titles, descriptions)
- `ActivateResult(uuid, [], 0)` - Directly focuses a specific tab by UUID
- Works on both X11 and Wayland without requiring extensions
- No X11 tools (wmctrl, xdotool) needed

#### UUID Tracking
- Extracts `GNOME_TERMINAL_SCREEN` environment variable from Claude's parent bash process
- Converts D-Bus object path format to UUID format (underscores → hyphens)
- Enables precise tab identification even with multiple Claude sessions

## Testing

### Test Terminal Tab Control
```bash
# List all terminal tabs
python3 test_dbus_tab_switch.py

# Focus current tab
python3 test_dbus_tab_switch.py --focus-current

# Focus tab by index
python3 test_dbus_tab_switch.py --focus-index 2

# Focus tab by directory
python3 test_dbus_tab_switch.py --focus-directory /path/to/dir

# Interactive example with all features
python3 examples/terminal_tabs_example.py

# Interactive tab selection
python3 examples/terminal_tabs_example.py --interactive
```

### Test Terminal Discovery
```bash
# Analyze current terminal session
./terminal_finder.py analyze

# Test focusing current terminal
./terminal_finder.py focus

# Find processes in specific directory
./terminal_finder.py directory /path/to/dir
```

### Test Notification with Actions
```bash
# Simulate a Claude notification with actions
echo '{"session_id": "test-123", "cwd": "'$(pwd)'", "message": "Test notification"}' | ./notify_hook.py
```

## Logs and Debugging

### Notification Hook Logs
```bash
tail -f /tmp/claude-notify.log
```

### Focus Service Logs
```bash
journalctl --user -u claude_focus.service -f
```

### Focus Service Manual Testing
```bash
# Test focus service manually
python3 ./claude_focus_service.py
```

## Configuration Files

### Session Data
- `./session-data.json` - Active Claude sessions
- `./notification-mapping.json` - Notification ID to session mapping

### Claude Settings
The notification hook is already configured in `./settings.json`:
```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "./notify_hook.py"
          }
        ]
      }
    ]
  }
}
```

## Dependencies

### Required Packages
- `python3-dbus` - D-Bus Python bindings
- `python3-gi` - GObject introspection (for GLib mainloop)

### Install Dependencies
```bash
sudo apt update
sudo apt install python3-dbus python3-gi
```

**Note:** The terminal tab focusing feature uses GNOME Terminal's built-in D-Bus API. No GNOME Shell extensions are required! X11 tools (wmctrl, xdotool) are also not needed.

## Troubleshooting

### Service Won't Start
```bash
# Check service status
systemctl --user status claude_focus.service

# Check logs for errors
journalctl --user -u claude_focus.service -n 50
```

### Notifications Not Clickable
- Ensure the focus service is running
- Check D-Bus connectivity: `dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames`

### Terminal Focus Not Working
- Test terminal discovery: `./terminal_finder.py analyze`
- Check session type: `echo $XDG_SESSION_TYPE`
- For Wayland: Ensure GNOME Shell D-Bus is available

## License

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>