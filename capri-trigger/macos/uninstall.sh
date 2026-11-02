#!/bin/bash
# Removes the Capri USB trigger.  Run:  bash uninstall.sh
LABEL="com.capri.usbtrigger"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Library/Application Support/CapriTrigger"
echo "Capri USB trigger removed."
