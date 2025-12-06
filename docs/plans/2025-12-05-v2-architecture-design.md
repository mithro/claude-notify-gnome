# Claude Notify GNOME v2 - Architecture Design

**Date:** 2025-12-05
**Status:** Draft
**Branch:** `feature/v2-architecture-refactor`

## Overview

A complete refactor of claude-notify-gnome to support persistent per-session notifications, multi-session tracking, and a clean library separation for future extensibility.

## Requirements

### Core Functionality

1. **Per-session persistent notifications** (like Chrome's audio indicator)
   - One persistent notification per active Claude Code session
   - Always visible in GNOME notification tray
   - Shows current state: working vs needs attention
   - Shows live activity indicator (terminal title or current action)
   - "Focus Terminal" button that raises the correct gnome-terminal tab

2. **Popup notifications for attention**
   - Fires when Claude transitions to NEEDS_ATTENTION state
   - Configurable delay before popup (default: 45s)
   - Auto-dismissed when Claude returns to WORKING state
   - Separate from persistent notification (freedesktop limitation)

3. **Multi-session support**
   - Track multiple concurrent Claude Code sessions
   - Each session has independent state, notifications, timers
   - Friendly session names derived from UUID ("bold-cat", "swift-eagle")

### Architecture Requirements

4. **Persistent daemon**
   - Tracks all active sessions and their state
   - Manages notifications lifecycle
   - Debug logging of all events and state changes
   - Queryable state (via socket command or SIGUSR1)

5. **Library separation**
   - `claude-session-tracker`: Reusable session tracking, no GUI deps
   - `gnome-notify-bridge`: GNOME-specific notification/focus handling
   - `claude-notify-hook`: Minimal forwarder, extremely fast

6. **Future extensibility**
   - Session tracker could run on remote machine
   - Abstract transport layer (Unix socket default, HTTP optional)
   - Notification bridge could be swapped for other desktop environments

### Performance Requirements

7. **Hook performance**
   - Target: < 50ms start-to-exit (ideally < 20ms)
   - Fire-and-forget to daemon (no blocking)
   - Phase 1: Python (MVP)
   - Phase 2: Compiled binary (Rust/Go/C) for < 10ms cold start

## Research Findings

### Claude Code Integration

- **10 hook events available**: PreToolUse, PostToolUse, Notification, Stop, SubagentStop, UserPromptSubmit, SessionStart, SessionEnd, PreCompact, PermissionRequest
- **One-way only**: No API to query Claude's state
- **Immediate return required**: Hooks must not block Claude
- **File-based state**: Only option for cross-hook communication

### GNOME Notifications (freedesktop)

- **Cannot have persistent AND popup from same notification**
  - `urgency=2 (critical)` + `resident=True` = persistent in tray
  - `urgency=1 (normal)` = popup that auto-dismisses
- **Update in-place**: Use `replaces_id` to update without flicker
- **Action buttons**: Via `ActionInvoked` D-Bus signal

### Existing Projects Analyzed

- **CCManager**: PTY-based control, 200ms state debouncing pattern
- **claude-notifications-go**: 6-status state machine, per-hook-type deduplication, temporal locality pattern

## Design

### State Machine

Two primary states:

| State | Icon | Meaning |
|-------|------|---------|
| **WORKING** | ⚙️ | Claude is actively doing something |
| **NEEDS_ATTENTION** | ❓ | Claude is waiting for user (question, finished, idle) |

Error states (special cases):
- **SESSION_LIMIT** ⏱️ - Hit usage cap
- **API_ERROR** 🔴 - Auth/connection issue

Transitions:
```
WORKING ──[Stop hook]──────────────→ NEEDS_ATTENTION
WORKING ──[AskUserQuestion]────────→ NEEDS_ATTENTION
WORKING ──[Notification hook]──────→ NEEDS_ATTENTION
NEEDS_ATTENTION ──[UserPromptSubmit]→ WORKING
NEEDS_ATTENTION ──[PreToolUse]─────→ WORKING
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 claude-session-tracker                       │
│                 (reusable library)                           │
├─────────────────────────────────────────────────────────────┤
│  • SessionRegistry - tracks all active sessions              │
│  • SessionState - state machine per session                  │
│  • HookEventParser - parses Claude hook JSON                 │
│  • TranscriptAnalyzer - analyzes JSONL for status            │
│  • FriendlyNames - generates "bold-cat" from UUID            │
│  • EventEmitter - notifies listeners of state changes        │
│                                                              │
│  Transport: Abstract (Unix socket default, HTTP optional)    │
│  No GNOME/GTK dependencies - pure Python                     │
└──────────────────────────────▲───────────────────────────────┘
                               │ events
┌──────────────────────────────┴───────────────────────────────┐
│                 gnome-notify-bridge                          │
│                 (GNOME-specific)                             │
├─────────────────────────────────────────────────────────────┤
│  • NotificationManager - D-Bus notifications                 │
│  • TerminalFocuser - GNOME Terminal tab focus                │
│  • ActionHandler - D-Bus signal listener for button clicks   │
│  • PopupTimer - manages attention popup delays               │
│                                                              │
│  Depends on: dbus, gi.repository (GTK/GLib)                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 claude-notify-hook                           │
│                 (thin CLI forwarder)                         │
├─────────────────────────────────────────────────────────────┤
│  • Reads raw JSON from stdin                                 │
│  • Adds supplemental env data                                │
│  • Forwards to daemon socket (fire-and-forget)               │
│  • ~30 lines, no parsing of Claude data                      │
└─────────────────────────────────────────────────────────────┘
```

### Hook Wire Protocol

Two newline-separated JSON blobs (custom first for robustness):

**BLOB 1** (custom/supplemental - always valid):
```json
{
  "version": 1,
  "timestamp": 1733401800.123,
  "env": {
    "GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/...",
    "TERM": "xterm-256color"
  },
  "claude_size": 1847
}
```

**BLOB 2** (raw Claude JSON - passed through verbatim):
```json
{"hook_event_name": "PreToolUse", "session_id": "abc-123", ...}
```

Benefits:
- Custom metadata always parseable even if Claude JSON malformed
- `claude_size` allows verification of complete transmission
- `version` field enables future protocol changes
- Hook never needs updating when Claude's schema changes

### Multi-Session Notification Display

```
┌──────────────────────────────────────────────┐
│ Claude Code                                  │
├──────────────────────────────────────────────┤
│ ❓ [swift-eagle] project-b                   │  ← Needs attention
│    "Apply changes? [y/n]"                    │
│    [Focus Terminal]                          │
├──────────────────────────────────────────────┤
│ ⚙️ [bold-cat] project-a                      │  ← Working
│    "Running tests..."                        │
│    [Focus Terminal]                          │
├──────────────────────────────────────────────┤
│ ❓ [cosmic-dragon] project-c                 │  ← Needs attention
│    "Ready for input"                         │
│    [Focus Terminal]                          │
└──────────────────────────────────────────────┘
```

### Debug Logging

Log file: `~/.local/state/claude-notify/daemon.log`

```
2025-12-05T10:30:00.123 [INFO] SESSION_START session=abc-123
    name=bold-cat cwd=/home/tim/project-a term=550e8400-e29b-...

2025-12-05T10:30:00.456 [DEBUG] HOOK_RECEIVED session=abc-123
    event=PreToolUse tool=Bash

2025-12-05T10:30:01.789 [INFO] STATE_CHANGE session=abc-123
    old=NEEDS_ATTENTION new=WORKING

2025-12-05T10:30:45.000 [INFO] STATE_CHANGE session=abc-123
    old=WORKING new=NEEDS_ATTENTION

2025-12-05T10:31:30.000 [INFO] POPUP_FIRED session=abc-123
    reason=timeout_45s
```

Session state dump available via SIGUSR1 or socket command.

## Configuration

Default config location: `~/.config/claude-notify/config.json`

```json
{
  "popup_delay_seconds": 45,
  "socket_path": "/run/user/$UID/claude-notify.sock",
  "log_level": "INFO",
  "log_path": "~/.local/state/claude-notify/daemon.log"
}
```

## Future Work

- [ ] Rewrite hook in Rust/Go/C for faster startup
- [ ] HTTP transport for remote session tracking
- [ ] AppIndicator integration for always-visible panel icon (requires extension)
- [ ] Sound/bell on attention needed
- [ ] Webhook integrations (Slack, Discord, etc.)

## References

- [Desktop Notifications Specification](https://specifications.freedesktop.org/notification/latest/)
- [CCManager](https://github.com/kbwo/ccmanager) - Session management patterns
- [claude-notifications-go](https://github.com/777genius/claude-notifications-go) - State machine design
- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
