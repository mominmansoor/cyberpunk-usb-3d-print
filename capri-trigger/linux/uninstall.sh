#!/bin/bash
# Removes the Capri USB trigger.  Run:  bash uninstall.sh
DIR="$HOME/.local/share/capri-trigger"
pkill -f "$DIR/capri-watch.sh" 2>/dev/null || true
rm -f "$HOME/.config/autostart/capri-usb-trigger.desktop"
rm -rf "$DIR"
echo "Capri USB trigger removed."
