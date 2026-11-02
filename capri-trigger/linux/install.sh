#!/bin/bash
# Installs the Capri USB trigger for the current Linux user. No sudo needed.
# Run from this folder:  bash install.sh [path-to-Capri-binary]
# Default Capri path:    ~/Capri/Capri  (where the Capri-linux-x64.tar.gz usually unpacks)
set -e

CAPRI_BIN="${1:-$HOME/Capri/Capri}"
CAPRI_BIN="$(realpath -m "$CAPRI_BIN")"
DIR="$HOME/.local/share/capri-trigger"
AUTO="$HOME/.config/autostart"
HERE="$(cd "$(dirname "$0")" && pwd)"

[ -x "$CAPRI_BIN" ] || echo "Warning: $CAPRI_BIN not found yet. Pass the right path: bash install.sh /path/to/Capri"

mkdir -p "$DIR" "$AUTO"
cp "$HERE/capri-watch.sh" "$DIR/capri-watch.sh"
chmod +x "$DIR/capri-watch.sh"

cat > "$AUTO/capri-usb-trigger.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Capri USB Trigger
Comment=Starts Capri when a USB drive with capri.key is plugged in
Exec=$DIR/capri-watch.sh "$CAPRI_BIN"
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF

# start it now too, so it works without logging out
pkill -f "$DIR/capri-watch.sh" 2>/dev/null || true
setsid "$DIR/capri-watch.sh" "$CAPRI_BIN" >/dev/null 2>&1 &

echo "Capri USB trigger installed and running (it also starts automatically when you log in)."
echo "Copy capri.key (from the usb folder) to the top folder of your USB drive, then plug it in."
