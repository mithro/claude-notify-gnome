#!/bin/bash
# docker/gnome-test/entrypoint.sh
set -e

echo "Starting GNOME test environment..."

# Create XDG runtime directory
export XDG_RUNTIME_DIR="/tmp/runtime-testuser"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start D-Bus session bus
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "D-Bus started: $DBUS_SESSION_BUS_ADDRESS"

# Start weston with headless backend
echo "Starting weston..."
weston --config=/etc/weston.ini &
WESTON_PID=$!

# Set Wayland display
export WAYLAND_DISPLAY=wayland-0

# Wait for weston socket to exist
echo "Waiting for weston..."
for i in $(seq 1 50); do
    if [ -e "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
        echo "Weston ready"
        break
    fi
    sleep 0.1
done
if [ ! -e "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    echo "ERROR: Weston socket not found after 5 seconds"
    exit 1
fi

# Start gnome-shell nested in weston
echo "Starting gnome-shell..."
gnome-shell --nested --wayland &
GNOME_PID=$!

# Wait for notification service to be ready
echo "Waiting for notification service..."
for i in $(seq 1 100); do
    if gdbus introspect --session --dest org.freedesktop.Notifications \
        --object-path /org/freedesktop/Notifications > /dev/null 2>&1; then
        echo "Notification service available"
        break
    fi
    sleep 0.1
done

# Make notification service check fatal
if ! gdbus introspect --session --dest org.freedesktop.Notifications \
    --object-path /org/freedesktop/Notifications > /dev/null 2>&1; then
    echo "ERROR: Notification service not available after 10 seconds"
    exit 1
fi

# Start ydotool daemon (needs root for uinput)
echo "Starting ydotool daemon..."
sudo ydotoold &
sleep 1

# Create screenshots directory
mkdir -p /app/tests/e2e/screenshots

# Start our daemon
echo "Starting claude-notify-daemon..."
cd /app
uv run claude-notify-daemon --log-level DEBUG &
DAEMON_PID=$!
sleep 2

# Run the tests
echo "Running tests..."
uv run "$@"
TEST_EXIT=$?

# Copy screenshots to output
mkdir -p /app/test-output
cp -r /app/tests/e2e/screenshots/* /app/test-output/ 2>/dev/null || true

# Cleanup
echo "Cleaning up..."
kill $DAEMON_PID $GNOME_PID $WESTON_PID 2>/dev/null || true

exit $TEST_EXIT
