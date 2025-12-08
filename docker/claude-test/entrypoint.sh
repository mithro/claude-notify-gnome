#!/bin/bash
# docker/claude-test/entrypoint.sh
set -e

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS

# Create XDG runtime directory
export XDG_RUNTIME_DIR="/tmp/runtime-testuser"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Execute the command
cd /app
exec uv run "$@"
