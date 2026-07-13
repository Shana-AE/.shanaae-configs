#!/usr/bin/env python3
"""Configure cc-switch Claude providers and/or write settings.json directly.

Reads provider definitions from providers.json (next to this script) and API
keys from .secrets. Two modes:

  1. If ~/.cc-switch/cc-switch.db exists: inserts/updates providers in the DB,
     updates common_config_claude, writes settings.json for the current provider.
  2. If no cc-switch DB (e.g. macbook-work): writes settings.json directly from
     the default provider + common_config (standalone mode, no GUI switching).

Usage:
  python3 setup_claude_providers.py                    # full setup
  python3 setup_claude_providers.py --provider qiniu-claude  # set current + write settings.json
  python3 setup_claude_providers.py --list             # show configured providers
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIGS_ROOT = SCRIPT_DIR.parents[4]  # scripts -> qiniu-model-sync -> local -> skills -> ai -> root
PROVIDERS_JSON = SCRIPT_DIR / "providers.json"
SECRETS_FILE = CONFIGS_ROOT / ".secrets"
DB_PATH = Path(os.path.expanduser("~/.cc-switch/cc-switch.db"))
SETTINGS_JSON = Path(os.path.expanduser("~/.claude/settings.json"))


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
_secrets_cache: dict[str, str] | None = None


def load_secrets() -> dict[str, str]:
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    out: dict[str, str] = {}
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            k, v = line.split("=", 1)
            v = v.strip().strip("\"'")
            out[k.strip()] = v
    _secrets_cache = out
    return out


def get_api_key(env_var: str) -> str:
    if env_var in os.environ:
        return os.environ[env_var]
    key = load_secrets().get(env_var, "")
    if not key:
        sys.exit(f"{env_var} not found in environment or .secrets")
    return key


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_providers_json() -> dict:
    return json.loads(PROVIDERS_JSON.read_text())


def resolve_provider_env(provider: dict, api_key: str) -> dict:
    """Take the provider's env template and inject the API key."""
    env = dict(provider.get("env", {}))
    env["ANTHROPIC_AUTH_TOKEN"] = api_key
    return env


# --------------------------------------------------------------------------- #
# settings.json write (always done)
# --------------------------------------------------------------------------- #
def write_settings_json(provider: dict, common_config: dict, api_key: str):
    """Write ~/.claude/settings.json = provider env (with key) + common_config merged."""
    provider_env = resolve_provider_env(provider, api_key)

    merged: dict = {"env": provider_env}
    for k, v in common_config.items():
        if k == "env" and isinstance(v, dict):
            merged["env"].update(v)
        elif k not in merged:
            merged[k] = v

    SETTINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    # Backup
    if SETTINGS_JSON.exists():
        import shutil
        bak = SETTINGS_JSON.with_suffix(".json.bak-pre-setup")
        shutil.copy2(SETTINGS_JSON, bak)
    SETTINGS_JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    os.chmod(SETTINGS_JSON, 0o600)
    return merged


# --------------------------------------------------------------------------- #
# cc-switch DB operations (only if DB exists)
# --------------------------------------------------------------------------- #
def is_ccswitch_running() -> bool:
    try:
        subprocess.run(["pgrep", "-x", "cc-switch"], capture_output=True, timeout=5)
        return subprocess.run(["pgrep", "-x", "cc-switch"], capture_output=True).returncode == 0
    except Exception:
        return False


def setup_db(definition: dict, api_key: str, set_current: str | None):
    """Insert/update providers + common_config in cc-switch's SQLite DB."""
    if is_ccswitch_running():
        print("WARNING: cc-switch appears to be running. DB edits may conflict.")
        print("  Consider quitting cc-switch first for safety (SQLite WAL usually handles it).")

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    now = int(time.time())

    # Update common_config_claude
    common = json.dumps(definition["common_config"], ensure_ascii=False)
    existing_setting = db.execute(
        "SELECT key FROM settings WHERE key='common_config_claude'"
    ).fetchone()
    if existing_setting:
        db.execute(
            "UPDATE settings SET value=? WHERE key='common_config_claude'", (common,)
        )
    else:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('common_config_claude', ?)", (common,)
        )
    print("[DB] common_config_claude updated")

    # Upsert providers
    for idx, p in enumerate(definition["providers"]):
        pid = p["id"]
        env = resolve_provider_env(p, api_key)
        settings_config = json.dumps({"env": env}, ensure_ascii=False)
        meta = json.dumps({"commonConfigEnabled": True}, ensure_ascii=False)

        existing = db.execute(
            "SELECT id FROM providers WHERE app_type='claude' AND id=?", (pid,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE providers SET name=?, settings_config=? WHERE app_type='claude' AND id=?",
                (p["name"], settings_config, pid),
            )
            print(f"  [update] {pid}: {p['name']}")
        else:
            db.execute(
                """INSERT INTO providers
                   (id, app_type, name, settings_config, website_url, category,
                    created_at, sort_index, notes, icon, icon_color, meta,
                    is_current, in_failover_queue, cost_multiplier,
                    limit_daily_usd, limit_monthly_usd, provider_type)
                   VALUES (?, 'claude', ?, ?, ?, 'custom',
                           ?, ?, NULL, NULL, NULL, ?,
                           0, 0, '1', NULL, NULL, 'qiniu')""",
                (pid, p["name"], settings_config,
                 "https://www.qiniu.com", now, idx + 10, meta),
            )
            print(f"  [insert] {pid}: {p['name']}")

    # Remove old merged providers
    for old_id in ["qiniu-claude-sonnet", "qiniu-claude-opus"]:
        db.execute(
            "DELETE FROM providers WHERE app_type='claude' AND id=?", (old_id,)
        )

    # Rename stale 'default' if it still has the old name
    db.execute(
        """UPDATE providers SET name='Router (ccr) \u2014 offline', is_current=0
           WHERE app_type='claude' AND id='default' AND is_current=1"""
    )

    # Set current provider
    current = set_current or definition.get("default_provider")
    if current:
        db.execute("UPDATE providers SET is_current=0 WHERE app_type='claude'")
        row = db.execute(
            "SELECT id FROM providers WHERE app_type='claude' AND id=?", (current,)
        ).fetchone()
        if row:
            db.execute(
                "UPDATE providers SET is_current=1 WHERE app_type='claude' AND id=?",
                (current,),
            )
            print(f"[DB] current provider: {current}")

    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", help="set as current provider + write its settings.json")
    ap.add_argument("--list", action="store_true", help="list configured providers")
    args = ap.parse_args()

    definition = load_providers_json()
    api_key = get_api_key(definition["api_key_env"])

    providers_by_id = {p["id"]: p for p in definition["providers"]}

    if args.list:
        print(f"Providers in {PROVIDERS_JSON.name}:")
        for p in definition["providers"]:
            model = p.get("env", {}).get("ANTHROPIC_MODEL", "?")
            print(f"  {p['id']:30s} {p['name']:35s} model={model}")
        default = definition.get("default_provider", "?")
        print(f"\nDefault: {default}")
        return

    # Determine which provider to use
    current_id = args.provider or definition.get("default_provider", "qiniu-claude")
    if current_id not in providers_by_id:
        sys.exit(f"Unknown provider: {current_id}. Available: {list(providers_by_id.keys())}")
    provider = providers_by_id[current_id]

    # DB setup (if cc-switch exists)
    if DB_PATH.exists():
        print(f"== cc-switch DB found: {DB_PATH} ==")
        setup_db(definition, api_key, current_id if args.provider else None)
    else:
        print("== No cc-switch DB — standalone mode (settings.json only) ==")

    # Always write settings.json for the target provider
    merged = write_settings_json(provider, definition["common_config"], api_key)
    print(f"\n[settings.json] written for {current_id}")
    print(f"  env keys: {sorted(merged['env'].keys())}")
    print(f"  plugins: {list(merged.get('enabledPlugins', {}).keys())}")


if __name__ == "__main__":
    main()
