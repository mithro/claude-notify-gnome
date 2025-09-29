#!/bin/bash
#
# Claude Focus Service Installer
# Installs the systemd user service for the Claude notification focus system
#

set -e

CLAUDE_DIR="$HOME/.claude"
SERVICE_FILE="claude_focus.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "Installing Claude Focus Service..."

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_USER_DIR"

# Copy service file
cp "$CLAUDE_DIR/$SERVICE_FILE" "$SYSTEMD_USER_DIR/"

# Reload systemd and enable the service
systemctl --user daemon-reload
systemctl --user enable claude_focus.service

echo "✅ Service installed successfully!"
echo ""
echo "To start the service now:"
echo "  systemctl --user start claude_focus.service"
echo ""
echo "To check service status:"
echo "  systemctl --user status claude_focus.service"
echo ""
echo "To view logs:"
echo "  journalctl --user -u claude_focus.service -f"
echo ""
echo "To stop the service:"
echo "  systemctl --user stop claude_focus.service"
echo ""
echo "To disable the service:"
echo "  systemctl --user disable claude_focus.service"