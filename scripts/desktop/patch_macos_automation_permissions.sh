#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${ALPHAFOUNDRY_APP_PATH:-/Applications/AlphaFoundry.app}"
INFO_PLIST="$APP_PATH/Contents/Info.plist"
PLIST_BUDDY="/usr/libexec/PlistBuddy"
USAGE_KEY="NSAppleEventsUsageDescription"
USAGE_DESCRIPTION="${ALPHAFOUNDRY_APPLE_EVENTS_USAGE_DESCRIPTION:-AlphaFoundry needs to automate Microsoft Excel to open and refresh Wind realtime market workbooks.}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  log "Skipping macOS automation permission patch on non-Darwin host"
  exit 0
fi

if [[ ! -f "$INFO_PLIST" ]]; then
  log "AlphaFoundry Info.plist is missing: $INFO_PLIST"
  exit 1
fi

if [[ ! -x "$PLIST_BUDDY" ]]; then
  log "PlistBuddy is missing: $PLIST_BUDDY"
  exit 1
fi

current_value="$("$PLIST_BUDDY" -c "Print :$USAGE_KEY" "$INFO_PLIST" 2>/dev/null || true)"

if [[ "$current_value" == "$USAGE_DESCRIPTION" ]]; then
  log "Apple Events usage description is already current"
else
  if [[ -n "$current_value" ]]; then
    "$PLIST_BUDDY" -c "Set :$USAGE_KEY $USAGE_DESCRIPTION" "$INFO_PLIST"
  else
    "$PLIST_BUDDY" -c "Add :$USAGE_KEY string $USAGE_DESCRIPTION" "$INFO_PLIST"
  fi
  log "Updated $USAGE_KEY for Microsoft Excel automation"
fi

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_PATH" >/dev/null
  log "Re-signed AlphaFoundry app after Info.plist patch"
else
  log "codesign is unavailable; Info.plist was patched but app was not re-signed"
  exit 1
fi
