#!/bin/bash
# docker/claude-test/entrypoint.sh
set -e

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS

# Create XDG runtime directory
export XDG_RUNTIME_DIR="/tmp/runtime-$$"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Install dependencies (needed when /app is volume-mounted from host)
cd /app
uv sync --extra daemon --extra dev

# Execute the command
exec uv run "$@"
