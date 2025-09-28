# Claude Code Click-to-Focus Notification System

A sophisticated notification system that allows you to click desktop notifications to instantly focus the terminal window containing your Claude Code session.

## Features

- 🖱️ **Clickable Notifications**: Click "Focus Terminal" to instantly switch to your Claude session
- 🖥️ **Cross-Platform**: Works on both X11 and Wayland (Ubuntu 24.04 tested)
- 🎯 **Session-Aware**: Tracks multiple Claude sessions and focuses the correct terminal
- 🔧 **Auto-Start**: Systemd service automatically starts the background focus handler
- 📁 **Context-Rich**: Notifications show current directory and timestamp
- ⚡ **Fast & Reliable**: Pure Python D-Bus implementation with multiple fallback methods

## Architecture

1. **notify-hook.py**: Enhanced notification hook with clickable actions
2. **claude-focus-service.py**: Background D-Bus service handling clicks
3. **terminal-finder.py**: Advanced terminal discovery utility
4. **Systemd Service**: Auto-starting background service

## Installation

The system is already set up and running! The components are:

### Files Created
- `~/.claude/notify-hook.py` - Notification hook (already configured in Claude)
- `~/.claude/claude-focus-service.py` - Background focus service
- `~/.claude/terminal-finder.py` - Terminal discovery utility
- `~/.claude/claude-focus.service` - Systemd service definition
- `~/.claude/install-service.sh` - Service installer

### Systemd Service
```bash
# Check service status
systemctl --user status claude-focus.service

# View logs
journalctl --user -u claude-focus.service -f

# Stop/start service
systemctl --user stop claude-focus.service
systemctl --user start claude-focus.service
```

## How It Works

1. **Claude triggers notification**: When Claude waits for input or needs permission
2. **Enhanced hook**: `notify-hook.py` sends notification with "Focus Terminal" button
3. **Session registration**: Hook registers session info with background service
4. **User clicks**: Click "Focus Terminal" button on notification
5. **Service handles click**: `claude-focus-service.py` receives D-Bus ActionInvoked signal
6. **Terminal focus**: Service finds and focuses the correct terminal window

### Technical Details

#### X11 Method
- Uses process tree walking to find: Claude PID → bash → gnome-terminal
- Maps process PID to window ID using `wmctrl -lp`
- Focuses window with `wmctrl -ia` or `xdotool windowactivate`

#### Wayland Method
- Uses GNOME Shell D-Bus interface for window management
- Executes JavaScript in GNOME Shell to find and activate terminal windows
- Fallback method works across all GNOME applications

## Testing

### Test Terminal Discovery
```bash
# Analyze current terminal session
~/.claude/terminal-finder.py analyze

# Test focusing current terminal
~/.claude/terminal-finder.py focus

# Find processes in specific directory
~/.claude/terminal-finder.py directory /path/to/dir
```

### Test Notification with Actions
```bash
# Simulate a Claude notification with actions
echo '{"session_id": "test-123", "cwd": "'$(pwd)'", "message": "Test notification"}' | ~/.claude/notify-hook.py
```

## Logs and Debugging

### Notification Hook Logs
```bash
tail -f /tmp/claude-notify.log
```

### Focus Service Logs
```bash
journalctl --user -u claude-focus.service -f
```

### Focus Service Manual Testing
```bash
# Test focus service manually
python3 ~/.claude/claude-focus-service.py
```

## Configuration Files

### Session Data
- `~/.claude/session-data.json` - Active Claude sessions
- `~/.claude/notification-mapping.json` - Notification ID to session mapping

### Claude Settings
The notification hook is already configured in `~/.claude/settings.json`:
```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/home/tim/.claude/notify-hook.py"
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
- `wmctrl` - X11 window management (optional, for X11 support)
- `xdotool` - X11 automation (optional, for X11 support)

### Install Dependencies
```bash
sudo apt update
sudo apt install python3-dbus python3-gi wmctrl xdotool
```

## Troubleshooting

### Service Won't Start
```bash
# Check service status
systemctl --user status claude-focus.service

# Check logs for errors
journalctl --user -u claude-focus.service -n 50
```

### Notifications Not Clickable
- Ensure the focus service is running
- Check D-Bus connectivity: `dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames`

### Terminal Focus Not Working
- Test terminal discovery: `~/.claude/terminal-finder.py analyze`
- Check session type: `echo $XDG_SESSION_TYPE`
- For Wayland: Ensure GNOME Shell D-Bus is available

## License

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>