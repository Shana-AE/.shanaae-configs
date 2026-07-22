#!/usr/bin/env python3
"""Set up Claude Code statusline (ccusage) and sync claude-hud config.

Subcommands:
  setup   Install ccusage globally + configure statusLine in cc-switch common config
  sync    Read statusLine from ~/.claude/settings.json and sync it into cc-switch db
          (run this after /claude-hud:setup to make claude-hud survive provider switches)
  status  Show the current statusLine config from both settings.json and cc-switch db
"""
import json
import os
import sqlite3
import shutil
import subprocess
import sys

CLAUDE_SETTINGS = os.path.expanduser("~/.claude/settings.json")
CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
CC_SWITCH_SETTINGS = os.path.expanduser("~/.cc-switch/settings.json")
COMMON_CONFIG_KEY = "common_config_claude"


def find_ccusage_bin():
    """Find the ccusage binary path."""
    which = shutil.which("ccusage")
    if which:
        return which
    pnpm_bin = os.path.expanduser("~/.local/share/pnpm/bin/ccusage")
    if os.path.isfile(pnpm_bin) and os.access(pnpm_bin, os.X_OK):
        return pnpm_bin
    npm_bin = os.path.expanduser("~/.npm-global/bin/ccusage")
    if os.path.isfile(npm_bin) and os.access(npm_bin, os.X_OK):
        return npm_bin
    return None


def cmd_setup():
    """Install ccusage globally and configure statusLine."""
    print("=== Claude Code Statusline Setup ===\n")

    # Step 1: Install ccusage globally
    ccusage = find_ccusage_bin()
    if ccusage:
        print(f"[1/3] ccusage already installed: {ccusage}")
    else:
        print("[1/3] Installing ccusage globally...")
        pkg_mgr = shutil.which("pnpm") or shutil.which("npm")
        if not pkg_mgr:
            print("ERROR: Neither pnpm nor npm found. Install one first.")
            sys.exit(1)
        result = subprocess.run(
            [pkg_mgr, "install", "-g", "ccusage"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: Install failed:\n{result.stderr}")
            sys.exit(1)
        ccusage = find_ccusage_bin()
        if not ccusage:
            print("ERROR: ccusage installed but binary not found on PATH.")
            sys.exit(1)
        print(f"  Installed: {ccusage}")

    # Step 2: Add statusLine to cc-switch common_config_claude
    print(f"\n[2/3] Configuring cc-switch common_config ({COMMON_CONFIG_KEY})...")
    statusline_config = {
        "type": "command",
        "command": f"{ccusage} statusline",
        "padding": 0,
    }
    _update_common_config(statusline_config)
    print("  ✅ statusLine added to cc-switch common_config_claude (survives provider switches)")

    # Step 3: Add to current settings.json for immediate effect
    print(f"\n[3/3] Adding statusLine to {CLAUDE_SETTINGS} (immediate effect)...")
    _update_settings_json(statusline_config)
    print("  ✅ statusLine added to current settings.json")

    print(f"\n=== Done! ===")
    print(f"ccusage statusline is now active. Restart Claude Code to see it.")
    print(f"\nTo install claude-hud (recommended replacement), run in Claude Code:")
    print(f"  /plugin marketplace add jarrodwatts/claude-hud")
    print(f"  /plugin install claude-hud")
    print(f"  /claude-hud:setup")
    print(f"  /claude-hud:configure   # enable tools/agents/todos/git")
    print(f"\nAfter claude-hud setup, run:")
    print(f"  python3 {__file__} sync")
    print(f"\nLinux TMPDIR workaround (if /plugin install fails with EXDEV):")
    print(f"  mkdir -p ~/.cache/tmp && TMPDIR=~/.cache/tmp claude")


def cmd_sync():
    """Read statusLine from settings.json and sync into cc-switch db."""
    print("=== Sync statusLine to cc-switch db ===\n")

    if not os.path.isfile(CLAUDE_SETTINGS):
        print(f"ERROR: {CLAUDE_SETTINGS} not found")
        sys.exit(1)

    with open(CLAUDE_SETTINGS, "r") as f:
        settings = json.load(f)

    statusline = settings.get("statusLine")
    if not statusline:
        print("ERROR: No statusLine key in settings.json. Run /claude-hud:setup first.")
        sys.exit(1)

    print(f"Read statusLine from settings.json:")
    print(f"  command: {statusline.get('command', 'N/A')}")

    _update_common_config(statusline)
    print(f"\n✅ Synced statusLine into cc-switch common_config_claude")
    print(f"   claude-hud will now survive provider switches.")


def cmd_status():
    """Show current statusLine config."""
    print("=== StatusLine Status ===\n")

    # settings.json
    if os.path.isfile(CLAUDE_SETTINGS):
        with open(CLAUDE_SETTINGS, "r") as f:
            settings = json.load(f)
        sl = settings.get("statusLine")
        if sl:
            print(f"[Active] ~/.claude/settings.json:")
            print(f"  command: {sl.get('command', 'N/A')}")
        else:
            print(f"[Active] ~/.claude/settings.json: (no statusLine)")
    else:
        print(f"[Active] ~/.claude/settings.json: (file not found)")

    # cc-switch db
    if os.path.isfile(CC_SWITCH_DB):
        conn = sqlite3.connect(CC_SWITCH_DB)
        cur = conn.cursor()
        cur.execute(f"SELECT value FROM settings WHERE key = '{COMMON_CONFIG_KEY}'")
        row = cur.fetchone()
        conn.close()
        if row:
            common = json.loads(row[0])
            sl = common.get("statusLine")
            if sl:
                print(f"\n[cc-switch common_config_claude]:")
                print(f"  command: {sl.get('command', 'N/A')}")
            else:
                print(f"\n[cc-switch common_config_claude]: (no statusLine)")
        else:
            print(f"\n[cc-switch common_config_claude]: (key not found)")
    else:
        print(f"\n[cc-switch db]: not found at {CC_SWITCH_DB}")

    # ccusage binary
    ccusage = find_ccusage_bin()
    print(f"\n[ccusage binary]: {ccusage or 'not found'}")


def _update_common_config(statusline_config):
    """Update the statusLine key in cc-switch's common_config_claude."""
    if not os.path.isfile(CC_SWITCH_DB):
        print(f"  WARNING: cc-switch db not found at {CC_SWITCH_DB}")
        print(f"  Skipping cc-switch common config update.")
        return

    conn = sqlite3.connect(CC_SWITCH_DB)
    cur = conn.cursor()
    cur.execute(f"SELECT value FROM settings WHERE key = '{COMMON_CONFIG_KEY}'")
    row = cur.fetchone()
    if not row:
        print(f"  WARNING: '{COMMON_CONFIG_KEY}' not found in cc-switch db.")
        print(f"  Skipping. Is cc-switch installed?")
        conn.close()
        return

    common_config = json.loads(row[0])
    common_config["statusLine"] = statusline_config
    cur.execute(
        f"UPDATE settings SET value = ? WHERE key = '{COMMON_CONFIG_KEY}'",
        (json.dumps(common_config, indent=2, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()


def _update_settings_json(statusline_config):
    """Add statusLine to the current ~/.claude/settings.json."""
    if os.path.isfile(CLAUDE_SETTINGS):
        with open(CLAUDE_SETTINGS, "r") as f:
            settings = json.load(f)
    else:
        settings = {}

    settings["statusLine"] = statusline_config

    os.makedirs(os.path.dirname(CLAUDE_SETTINGS), exist_ok=True)
    with open(CLAUDE_SETTINGS, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if cmd == "setup":
        cmd_setup()
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "status":
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)
