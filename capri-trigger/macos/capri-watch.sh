#!/bin/bash
# Capri USB trigger for macOS.
# launchd runs this every time any drive is mounted (StartOnMount).
# If a mounted drive has capri.key in its top folder, it opens Capri (unless she's already running).

APP_NAME="${CAPRI_APP:-Capri}"

for vol in /Volumes/*; do
  key="$vol/capri.key"
  [ -f "$key" ] || continue
  [ "$(head -n 1 "$key" | tr -d '\r')" = "CAPRI-KEY" ] || continue
  if ! pgrep -xq "$APP_NAME"; then
    open -a "$APP_NAME"
  fi
  exit 0
done
exit 0
