#!/usr/bin/env bash
# Shana-AE auto-re-apply for TokenTracker Qiniu/Sufy pricing (macOS).
# The mac app upgrade (DMG replace) wipes curated-overrides.json in the embedded
# copy; the CLI app dir is re-copied on next serve start. Restore the patch and
# restart the app when the embedded copy was wiped.
set -u

EMBED="/Applications/TokenTracker.app/Contents/Resources/EmbeddedServer/tokentracker"
CLI="$HOME/.tokentracker/tracker/app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE="/Applications/TokenTracker.app/Contents/Resources/EmbeddedServer/node"
LOG_DIR="$HOME/.local/var/log"
LOG_FILE="$LOG_DIR/tokentracker-pricing-autofix.log"

mkdir -p "$LOG_DIR"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG_FILE"; }

embedded_patched=0
if [ -f "$EMBED/src/lib/pricing/curated-overrides.json" ] \
   && grep -q shanaae "$EMBED/src/lib/pricing/curated-overrides.json" 2>/dev/null; then
  embedded_patched=1
fi

for d in "$EMBED" "$CLI"; do
  if [ ! -f "$d/src/lib/pricing/curated-overrides.json" ]; then
    log "skip (no app copy): $d"
    continue
  fi
  out=$("$NODE" "$SCRIPT_DIR/patch-pricing.mjs" "$d" 2>&1)
  rc=$?
  if [ $rc -ne 0 ]; then
    log "patch FAILED ($rc): $d :: $(echo "$out" | tail -1)"
  else
    log "patched: $d"
  fi
done

if [ "$embedded_patched" -eq 0 ]; then
  log "embedded copy was unpatched (upgrade detected) -> restarting TokenTracker"
  osascript -e 'tell application "TokenTracker" to quit' >/dev/null 2>&1 || true
  sleep 2
  open -g -a /Applications/TokenTracker.app >/dev/null 2>&1 || true
  log "TokenTracker relaunched"
else
  log "embedded copy already patched; no restart"
fi
