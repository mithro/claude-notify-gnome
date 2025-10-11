# Terminal Focus Methods - What Works and What Doesn't

This document explains the various methods we tested for focusing terminal windows on Wayland/GNOME and why most of them don't work.

## ✅ Working Method

### Window Calls GNOME Extension
**Status: WORKING** ✅

The only reliable method for focusing terminal windows on GNOME Wayland is using the [Window Calls extension](https://github.com/ickyicky/window-calls).

**How it works:**
```bash
# List windows
gdbus call --session --dest org.gnome.Shell \
  --object-path /org/gnome/Shell/Extensions/Windows \
  --method org.gnome.Shell.Extensions.Windows.List

# Activate specific window by ID
gdbus call --session --dest org.gnome.Shell \
  --object-path /org/gnome/Shell/Extensions/Windows \
  --method org.gnome.Shell.Extensions.Windows.Activate 1896398278
```

**Why it works:**
- GNOME Shell extension runs with elevated privileges
- Provides safe D-Bus interface for window management
- Handles cross-workspace window activation
- Actually focuses the correct window

**Installation required:**
```bash
# Install from GNOME Extensions website
# OR manually:
cp -r window-calls ~/.local/share/gnome-shell/extensions/window-calls@domandoman.xyz/
gnome-extensions enable window-calls@domandoman.xyz
```

## ❌ Non-Working Methods

### 1. Legacy GNOME Shell D-Bus Eval
**Status: BROKEN** ❌

```bash
gdbus call --session --dest org.gnome.Shell \
  --object-path /org/gnome/Shell \
  --method org.gnome.Shell.Eval \
  'global.workspace_manager.get_active_workspace().list_windows().find(w => w.get_wm_class() === "Gnome-terminal").activate(global.get_current_time())'
```

**Why it doesn't work:**
- GNOME 41+ disabled `org.gnome.Shell.Eval` for security reasons
- Returns success (exit code 0) but doesn't actually focus anything
- Creates false positives in logs
- Security restriction prevents arbitrary JavaScript execution

**Symptoms:**
- Logs show "success" but no visual change
- No error messages despite complete failure
- Gives false confidence that focus worked

### 2. wmctrl (X11 tool)
**Status: INCOMPATIBLE** ❌

```bash
wmctrl -ia 0x12345678  # Window ID from wmctrl -l
```

**Why it doesn't work on Wayland:**
- wmctrl is an X11-only tool
- Wayland doesn't expose window management to external tools
- No equivalent functionality in Wayland protocol
- Security-by-design: Wayland isolates applications

**Error symptoms:**
```
Cannot open display
wmctrl: cannot open X11 display
```

### 3. xdotool (X11 automation)
**Status: INCOMPATIBLE** ❌

```bash
xdotool windowactivate 0x12345678
```

**Why it doesn't work on Wayland:**
- Another X11-only tool
- Wayland doesn't provide X11 compatibility for window management
- No direct equivalent in Wayland
- Would require compositor-specific solutions

### 4. Native Wayland Protocols
**Status: BLOCKED** ❌

**Why native Wayland doesn't help:**
- `wl_seat` and `wl_surface` protocols don't include window focusing
- Wayland deliberately doesn't expose global window management
- Each compositor (GNOME, KDE, sway) has different approaches
- No standardized window focusing protocol
- Security model prevents cross-application window manipulation

### 5. Direct GNOME Shell D-Bus (without extension)
**Status: RESTRICTED** ❌

```bash
# These interfaces are locked down
gdbus call --session --dest org.gnome.Shell \
  --object-path /org/gnome/Shell \
  --method org.gnome.Shell.FocusWindow 1234
```

**Why it doesn't work:**
- GNOME 41+ removed most window management D-Bus methods
- Security hardening prevents external focus control
- Only GNOME Shell extensions can access these capabilities
- Methods either don't exist or are permission-denied

### 6. Process Tree + Kill/Signal Approaches
**Status: DESTRUCTIVE** ❌

**Why we don't use these:**
- Sending signals (SIGUSR1, SIGCONT) to terminal processes is unreliable
- Risk of terminating or corrupting running processes
- No guarantee of window focus, only process state change
- Could break ongoing work in terminal sessions

## Why Wayland is Different

### Security Model
- Wayland was designed with security isolation in mind
- Applications cannot manipulate other applications' windows
- Global window management requires compositor permission
- X11's "anyone can do anything" model was intentionally rejected

### Compositor Control
- Each Wayland compositor (GNOME, KDE, sway) handles window management differently
- No universal window management protocol
- Extensions/plugins required for cross-application window control

### The Extension Requirement
- GNOME Shell extensions run with elevated privileges
- Can access internal GNOME Shell APIs
- Window Calls extension bridges this gap safely
- Provides controlled D-Bus interface for window management

## Implementation Notes

### Our Focus Service Strategy
1. **Only use Window Calls extension** - removed all fallback methods
2. **Fail fast and clearly** - no false positives in logs
3. **Clear error messages** - tell users exactly what's missing
4. **No security workarounds** - work within Wayland's design

### Detection and Fallback
```python
# Detect session type
session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')

if session_type == 'wayland':
    # Only attempt Window Calls extension
    # Fail clearly if not available
elif session_type == 'x11':
    # Can use wmctrl, xdotool, etc.
```

### Error Handling
- Check for Window Calls extension availability first
- Provide clear installation instructions when missing
- Never claim success when focus actually failed
- Log specific D-Bus error codes for debugging

## Summary

**On GNOME Wayland: Window Calls extension is required and is the ONLY working method.**

All other approaches either:
- Don't work due to Wayland security model
- Are X11-only tools incompatible with Wayland
- Give false positive results while failing silently
- Present security risks or could damage running processes

The solution is simple but absolute: install and enable the Window Calls GNOME extension.