#!/usr/bin/env bash
# Shana-AE auto-re-apply for TokenTracker Qiniu/Sufy pricing.
#
# The desktop app upgrade replaces the whole install dir, wiping
# `curated-overrides.json` in BOTH the embedded copy and (on next launch, via
# serve's installLocalTrackerApp) the CLI app dir. This script restores the
# pricing patch and, when the EMBEDDED copy was wiped (i.e. an upgrade just
# happened), restarts the desktop app so its server reloads pricing.
#
# Run from Windows Task Scheduler via: wsl.exe -d archlinux -- bash -lc '...'
# Idempotent + cheap; safe to run at logon and every few minutes.
set -u

USER="shana"
EMBED="/mnt/c/Users/$USER/AppData/Local/Programs/TokenTracker/EmbeddedServer/tokentracker"
CLI="/mnt/c/Users/$USER/.tokentracker/tracker/app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE="$(command -v node || echo "/home/shanaae/.local/share/fnm/aliases/default/bin/node")"
LOG_DIR="$HOME/.local/var/log"
LOG_FILE="$LOG_DIR/tokentracker-pricing-autofix.log"
APP_EXE="C:\\Users\\$USER\\AppData\\Local\\Programs\\TokenTracker\\TokenTracker.exe"

mkdir -p "$LOG_DIR"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG_FILE"; }

# 1. Did an upgrade wipe the embedded copy? (3 shanaae meta keys = patched)
embedded_patched=0
if [ -f "$EMBED/src/lib/pricing/curated-overrides.json" ] \
   && grep -q shanaae "$EMBED/src/lib/pricing/curated-overrides.json" 2>/dev/null; then
  embedded_patched=1
fi

# 2. Re-apply patch to both copies (idempotent in the script itself).
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

# 3. If the embedded copy had been wiped (upgrade), restart the desktop app so
#    the resident server reloads pricing. Guard against restart loops: only
#    restart when we actually transitioned unpatched -> patched.
if [ "$embedded_patched" -eq 0 ]; then
  log "embedded copy was unpatched (upgrade detected) -> restarting TokenTracker"
  /mnt/c/Windows/System32/taskkill.exe //F //IM TokenTracker.exe >/dev/null 2>&1 || true
  sleep 2
  /mnt/c/Windows/System32/cmd.exe /c "start \"\" \"$APP_EXE\"" >/dev/null 2>&1 || true
  log "TokenTracker relaunched"
else
  log "embedded copy already patched; no restart"
fi