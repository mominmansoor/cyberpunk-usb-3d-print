#!/bin/bash
# Installs the Capri USB trigger for the current macOS user. No sudo needed.
# Run from this folder:  bash install.sh
set -e

LABEL="com.capri.usbtrigger"
DIR="$HOME/Library/Application Support/CapriTrigger"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DIR" "$HOME/Library/LaunchAgents"
cp "$HERE/capri-watch.sh" "$DIR/capri-watch.sh"
chmod +x "$DIR/capri-watch.sh"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$DIR/capri-watch.sh</string>
  </array>
  <key>StartOnMount</key><true/>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Capri USB trigger installed."
echo "Copy capri.key (from the usb folder) to the top folder of your USB drive, then plug it in."
echo "The first time, macOS may ask to let bash read files on a removable volume: click Allow."
