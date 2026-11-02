#!/bin/bash
# Capri USB trigger for Linux.
# Runs in the background after you log in. When a drive with capri.key in its top folder
# gets mounted, it starts Capri (unless she's already running). Once per plug-in.
#
# Capri's location comes from the first argument, then $CAPRI_BIN, then ~/Capri/Capri.

CAPRI_BIN="${1:-${CAPRI_BIN:-$HOME/Capri/Capri}}"
INTERVAL="${CAPRI_TRIGGER_INTERVAL:-2}"
declare -A seen=()

mounts() {
  # removable-media mount points used by GNOME, KDE, udisks and most desktops
  awk '{print $2}' /proc/mounts | sed 's/\\040/ /g' | grep -E "^(/media|/run/media|/mnt)/" || true
}

while true; do
  declare -A now=()
  while IFS= read -r m; do
    [ -n "$m" ] || continue
    key="$m/capri.key"
    [ -f "$key" ] || continue
    [ "$(head -n 1 "$key" | tr -d '\r')" = "CAPRI-KEY" ] || continue
    now["$m"]=1
    if [ -z "${seen[$m]}" ]; then
      if ! pgrep -x "$(basename "$CAPRI_BIN")" >/dev/null; then
        (cd "$(dirname "$CAPRI_BIN")" && setsid "$CAPRI_BIN" >/dev/null 2>&1 &)
      fi
    fi
  done < <(mounts)
  seen=()
  for m in "${!now[@]}"; do seen["$m"]=1; done
  unset now
  sleep "$INTERVAL"
done
