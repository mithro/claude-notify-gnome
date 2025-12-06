# Claude Notify GNOME - Requirements

**Last Updated:** 2025-12-05

This is a living document. Update as requirements are discovered or changed.

## Functional Requirements

### FR-1: Per-Session Persistent Notifications

Each running Claude Code session MUST have an individual persistent notification that:

- [ ] **FR-1.1** Remains visible in GNOME notification tray until session ends
- [ ] **FR-1.2** Shows a "Focus Terminal" button that focuses the correct gnome-terminal tab
- [ ] **FR-1.3** Clearly indicates if Claude needs attention (working vs waiting)
- [ ] **FR-1.4** Shows live indication of what Claude is doing (terminal title or activity)
- [ ] **FR-1.5** Uses friendly session names derived from UUID ("bold-cat", "swift-eagle")
- [ ] **FR-1.6** Updates in-place without flickering (uses replaces_id)

### FR-2: Popup Notifications

A popup notification MUST appear when Claude needs attention:

- [ ] **FR-2.1** Fires when Claude asks for user input (AskUserQuestion, Notification hook)
- [ ] **FR-2.2** Fires when Claude has been waiting for configurable duration (default: 45s)
- [ ] **FR-2.3** Auto-dismisses when Claude returns to working state
- [ ] **FR-2.4** Separate notification from persistent (freedesktop limitation)
- [ ] **FR-2.5** Includes "Focus Terminal" button

### FR-3: Multi-Session Support

The system MUST support multiple concurrent Claude Code sessions:

- [ ] **FR-3.1** Track unlimited concurrent sessions
- [ ] **FR-3.2** Each session has independent state and notifications
- [ ] **FR-3.3** Each session has independent idle timers
- [ ] **FR-3.4** Sessions cleaned up on SessionEnd hook
- [ ] **FR-3.5** Sessions cleaned up after prolonged inactivity (configurable)

### FR-4: Terminal Focus

The "Focus Terminal" button MUST:

- [ ] **FR-4.1** Focus the correct gnome-terminal window
- [ ] **FR-4.2** Switch to the correct tab within that window
- [ ] **FR-4.3** Work on Wayland (using SearchProvider D-Bus API)
- [ ] **FR-4.4** Handle case where terminal window is on different workspace

## Architecture Requirements

### AR-1: Persistent Daemon

- [ ] **AR-1.1** Long-running daemon process tracks all sessions
- [ ] **AR-1.2** Daemon manages notification lifecycle
- [ ] **AR-1.3** Daemon provides debug logging of all events
- [ ] **AR-1.4** Daemon state queryable via socket command or signal

### AR-2: Library Separation

- [ ] **AR-2.1** `claude-session-tracker`: No GUI dependencies, pure Python
- [ ] **AR-2.2** `gnome-notify-bridge`: GNOME-specific, depends on D-Bus/GLib
- [ ] **AR-2.3** `claude-notify-hook`: Minimal forwarder, stdlib only
- [ ] **AR-2.4** Abstract transport layer (Unix socket default, HTTP optional)

### AR-3: Hook Design

- [ ] **AR-3.1** Hook forwards raw Claude JSON (no parsing)
- [ ] **AR-3.2** Hook adds supplemental env data as separate JSON blob
- [ ] **AR-3.3** Custom blob includes size of Claude blob for verification
- [ ] **AR-3.4** Wire format: two newline-separated JSON blobs

## Performance Requirements

### PR-1: Hook Performance

- [ ] **PR-1.1** Hook start-to-exit < 50ms (Python MVP)
- [ ] **PR-1.2** Hook start-to-exit < 20ms (target)
- [ ] **PR-1.3** Hook start-to-exit < 10ms (compiled binary goal)
- [ ] **PR-1.4** Hook never blocks - fire-and-forget to daemon

### PR-2: Notification Updates

- [ ] **PR-2.1** State change to notification update < 100ms
- [ ] **PR-2.2** No visible flicker on notification updates

## Configuration Requirements

### CR-1: User Configuration

- [ ] **CR-1.1** Configurable popup delay (default: 45s)
- [ ] **CR-1.2** Configurable socket path
- [ ] **CR-1.3** Configurable log level and path
- [ ] **CR-1.4** Config file: `~/.config/claude-notify/config.json`

## Debug Requirements

### DR-1: Logging

- [ ] **DR-1.1** Log all hook events received
- [ ] **DR-1.2** Log all state transitions
- [ ] **DR-1.3** Log all notification actions (create, update, dismiss)
- [ ] **DR-1.4** Log file rotation to prevent unbounded growth
- [ ] **DR-1.5** Session state dump on demand (SIGUSR1 or socket command)

## Future Requirements (Not in MVP)

- [ ] **FUT-1** Rewrite hook in Rust/Go/C
- [ ] **FUT-2** HTTP transport for remote session tracking
- [ ] **FUT-3** AppIndicator panel icon (requires extension)
- [ ] **FUT-4** Sound/bell on attention needed
- [ ] **FUT-5** Webhook integrations (Slack, Discord)

## Change Log

| Date | Change |
|------|--------|
| 2025-12-05 | Initial requirements from brainstorming session |
