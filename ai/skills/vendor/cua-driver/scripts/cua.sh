#!/bin/sh
# cua-driver wrapper for WSL — ensures the Windows daemon is up, then runs one-shot tool calls.
# Usage:
#   cua.sh <tool> '<json-args>'   → daemon-check + one-shot call (e.g. cua.sh get_screen_size '{}')
#   cua.sh status                 → daemon status
#   cua.sh serve                  → start daemon explicitly
# Management subcommands (status, serve, list-tools, describe, recording, ...) pass through unchanged.

BIN="${CUA_DRIVER_BIN:-$HOME/.local/bin/cua-driver}"

case "$1" in
  status|serve|stop|list-tools|describe|recording|update|check-update|doctor|diagnose|permissions|autostart|config|telemetry|skills|browser-approve|manifest|cursor-theme|mcp|call)
    exec "$BIN" "$@"
    ;;
  *)
    # one-shot tool call — make sure the daemon is alive first
    if ! "$BIN" status 2>/dev/null | grep -q "daemon is running"; then
      "$BIN" autostart kick >/dev/null 2>&1 || "$BIN" serve >/dev/null 2>&1
      sleep 1
      if ! "$BIN" status 2>/dev/null | grep -q "daemon is running"; then
        echo "cua-driver daemon is not running and could not be started. Try: cua-driver autostart kick" >&2
        exit 1
      fi
    fi
    exec "$BIN" "$@"
    ;;
esac
