# Claude Code Click-to-Focus Notification System

> [!WARNING]
> **VIBE-CODED SOFTWARE AHEAD!**
>
> This project was entirely vibe-coded using Claude Code in a caffeine-fueled haze of enthusiasm and questionable life choices. It might destroy your computer, eat your grandma, or worse - make your notifications too useful. Use at your own risk! We are not responsible for any spontaneous terminal focus addiction, D-Bus dependency, or sudden urges to click all the things.

---

A sophisticated notification system that allows you to click desktop notifications to instantly focus the terminal window containing your Claude Code session.

## Features

- 🖱️ **Clickable Notifications**: Click "Focus Terminal" to instantly switch to your Claude session
- 🖥️ **Cross-Platform**: Works on both X11 and Wayland (Ubuntu 24.04 tested)
- 🎯 **Session-Aware**: Tracks multiple Claude sessions and focuses the correct terminal
- 🔧 **Auto-Start**: Systemd service automatically starts the background focus handler
- 📁 **Context-Rich**: Notifications show current directory and timestamp
- ⚡ **Fast & Reliable**: Pure Python D-Bus implementation with multiple fallback methods

## Architecture

1. **notify_hook.py**: Enhanced notification hook with clickable actions
2. **claude_focus_service.py**: Background D-Bus service handling clicks
3. **terminal_finder.py**: Advanced terminal discovery utility
4. **Systemd Service**: Auto-starting background service

## Installation

The system is already set up and running! The components are:

### Files Created
- `./notify_hook.py` - Notification hook (already configured in Claude)
- `./claude_focus_service.py` - Background focus service
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
3. **Session registration**: Hook registers session info with background service
4. **User clicks**: Click "Focus Terminal" button on notification
5. **Service handles click**: `claude_focus_service.py` receives D-Bus ActionInvoked signal
6. **Terminal focus**: Service finds and focuses the correct terminal window

### Technical Details

#### X11 Method (Removed)
- X11-specific methods (wmctrl, xdotool) removed - these don't work on Wayland
- See TERMINAL_FOCUS_METHODS.md for detailed explanation of why these fail

#### Wayland Method
- Uses GNOME Shell D-Bus interface for window management
- Executes JavaScript in GNOME Shell to find and activate terminal windows
- Fallback method works across all GNOME applications

## Testing

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

**Note:** X11 tools (wmctrl, xdotool) are not needed and don't work on Wayland. See `TERMINAL_FOCUS_METHODS.md` for details.

### GNOME Shell Extension (Required for Wayland Focus)

For the "Focus Terminal" button to work on GNOME/Wayland, you need to install the **Window Calls** extension:

#### Installation Options:

**Option 1: GNOME Extensions Website (Recommended)**
1. Visit [Window Calls on GNOME Extensions](https://extensions.gnome.org/extension/4724/window-calls/)
2. Click "Install" to add it to your browser
3. Toggle the extension ON in the GNOME Extensions app

**Option 2: Manual Installation**
```bash
# Clone the repository
git clone https://github.com/ickyicky/window-calls.git
cd window-calls

# Install to user extensions directory
cp -r . ~/.local/share/gnome-shell/extensions/window-calls@ickyicky.github.io/

# Restart GNOME Shell (Alt+F2, type 'r', press Enter)
# Or log out and back in

# Enable the extension
gnome-extensions enable window-calls@ickyicky.github.io
```

#### Verify Installation
```bash
# Test if the extension is working
gdbus call --session --dest org.gnome.Shell \
  --object-path /org/gnome/Shell/Extensions/Windows \
  --method org.gnome.Shell.Extensions.Windows.List
```

#### Why This Extension is Needed
GNOME 41+ restricts window focusing via D-Bus for security reasons. The Window Calls extension provides a safe D-Bus interface for window management operations including:
- Listing windows with details
- Activating/focusing windows
- Moving windows between workspaces
- Resizing and positioning windows

Without this extension, the "Focus Terminal" button will not work on Wayland.

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