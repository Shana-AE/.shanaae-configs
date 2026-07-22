#!/usr/bin/env python3
"""One-shot installer: bun + ccusage + claude-hud + 5 official plugins.

Runs on macOS/Linux. Idempotent — safe to re-run.
"""
import json, os, shutil, sqlite3, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~")
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", f"{HOME}/.claude")
PLUGINS_DIR = f"{CLAUDE_DIR}/plugins"
SETTINGS_JSON = f"{CLAUDE_DIR}/settings.json"
CC_SWITCH_DB = f"{HOME}/.cc-switch/cc-switch.db"
NOW = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

OFFICIAL_MARKETPLACE = "claude-plugins-official"
OFFICIAL_PLUGINS = [
    ("commit-commands", "unknown"),
    ("security-guidance", "2.0.6"),
    ("code-review", "unknown"),
    ("hookify", "unknown"),
    ("ralph-loop", "1.0.0"),
]
HUD_VERSION = "0.4.0"
HUD_CONFIG = {
    "language": "en",
    "lineLayout": "expanded",
    "pathLevels": 2,
    "display": {
        "showTools": True,
        "showAgents": True,
        "showTodos": True,
        "showDuration": True,
        "showConfigCounts": True,
    },
}


def run(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"  ERROR: {cmd}\n  stderr: {r.stderr}")
        sys.exit(1)
    return r


def step(n, msg):
    print(f"\n[{n}] {msg}")


def find_runtime():
    for name in ("bun", "node"):
        p = shutil.which(name)
        if p:
            return p, name
    return None, None


def install_bun():
    print("  Installing bun...")
    r = run("curl -fsSL https://bun.sh/install | bash", check=False)
    if r.returncode != 0:
        print(f"  bun install failed: {r.stderr}")
        sys.exit(1)
    # Source bun env for this process
    bun_dir = f"{HOME}/.bun/bin"
    os.environ["PATH"] = bun_dir + ":" + os.environ["PATH"]
    run(f"export PATH={bun_dir}:$PATH && bun --version")
    return f"{bun_dir}/bun"


def build_statusline_cmd(runtime_path, runtime_name):
    is_bun = "bun" in runtime_name
    source = "src/index.ts" if is_bun else "dist/index.js"
    env_flag = " --env-file /dev/null" if is_bun else ""
    return (
        f"bash -c 'cols=${{COLUMNS:-}}; case \"$cols\" in \"\"|*[!0-9]*) "
        f"cols=$(stty size </dev/tty 2>/dev/null | awk '\"'\"'{{print $2}}'\"'\"');; esac; "
        f"case \"$cols\" in \"\"|*[!0-9]*) cols=120;; esac; "
        f"export COLUMNS=$(( cols > 4 ? cols - 4 : 1 )); "
        f"plugin_dir=$(ls -d \"${{CLAUDE_CONFIG_DIR:-$HOME/.claude}}\""
        f"/plugins/cache/*/claude-hud/*/ 2>/dev/null | "
        f"awk -F/ '\"'\"'{{ print $(NF-1) \"\\t\" $(0) }}'\"'\"' | "
        f"grep -E '\"'\"'^[0-9]+\\.[0-9]+\\.[0-9]+[[:space:]]'\"'\"' | "
        f"sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | tail -1 | cut -f2-); "
        f"exec \"{runtime_path}\"{env_flag} \"${{plugin_dir}}{source}\"'"
    )


def load_json(path, default=None):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_cc_switch(statusline_config, new_enabled_plugins):
    if not os.path.isfile(CC_SWITCH_DB):
        print("  (cc-switch not found — skipping common config)")
        return
    conn = sqlite3.connect(CC_SWITCH_DB)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'common_config_claude'")
    row = cur.fetchone()
    if not row:
        print("  (common_config_claude not found — skipping)")
        conn.close()
        return
    common = json.loads(row[0])
    if statusline_config:
        common["statusLine"] = statusline_config
    if "enabledPlugins" not in common:
        common["enabledPlugins"] = {}
    for k, v in new_enabled_plugins.items():
        common["enabledPlugins"][k] = v
    cur.execute(
        "UPDATE settings SET value = ? WHERE key = 'common_config_claude'",
        (json.dumps(common, indent=2, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()
    print("  ✅ cc-switch common_config_claude updated")


def install_official_plugins(marketplace_dir):
    installed = load_json(f"{PLUGINS_DIR}/installed_plugins.json", {"version": 2, "plugins": {}})
    new_enabled = {}
    for name, version in OFFICIAL_PLUGINS:
        src = f"{marketplace_dir}/plugins/{name}"
        if not os.path.isdir(src):
            print(f"  SKIP: {name} (not in marketplace)")
            continue
        cache_key = f"{name}@{OFFICIAL_MARKETPLACE}"
        dest = f"{PLUGINS_DIR}/cache/{OFFICIAL_MARKETPLACE}/{name}/{version}"
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        os.makedirs(dest, exist_ok=True)
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        installed["plugins"][cache_key] = [{
            "scope": "user", "installPath": dest, "version": version,
            "installedAt": NOW, "lastUpdated": NOW,
        }]
        new_enabled[cache_key] = True
        print(f"  ✅ {cache_key} (v{version})")
    save_json(f"{PLUGINS_DIR}/installed_plugins.json", installed)
    return new_enabled


def install_claude_hud(runtime_path, runtime_name):
    mp_dir = f"{PLUGINS_DIR}/marketplaces/claude-hud"
    cache_dir = f"{PLUGINS_DIR}/cache/claude-hud/claude-hud/{HUD_VERSION}"

    # Clone if needed
    if not os.path.isdir(mp_dir):
        print("  Cloning claude-hud marketplace...")
        run(f"git clone --depth 1 https://github.com/jarrodwatts/claude-hud.git '{mp_dir}'")

    # Copy to cache
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    for item in os.listdir(mp_dir):
        if item in (".git", ".github"):
            continue
        s = os.path.join(mp_dir, item)
        d = os.path.join(cache_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    print(f"  ✅ Cached v{HUD_VERSION}")

    # Register marketplace
    known = load_json(f"{PLUGINS_DIR}/known_marketplaces.json", {})
    known["claude-hud"] = {
        "source": {"source": "github", "repo": "jarrodwatts/claude-hud"},
        "installLocation": mp_dir,
        "lastUpdated": NOW,
    }
    save_json(f"{PLUGINS_DIR}/known_marketplaces.json", known)

    # Register plugin
    installed = load_json(f"{PLUGINS_DIR}/installed_plugins.json", {"version": 2, "plugins": {}})
    cache_key = "claude-hud@claude-hud"
    installed["plugins"][cache_key] = [{
        "scope": "user", "installPath": cache_dir, "version": HUD_VERSION,
        "installedAt": NOW, "lastUpdated": NOW,
    }]
    save_json(f"{PLUGINS_DIR}/installed_plugins.json", installed)

    # HUD config
    hud_config_dir = f"{CLAUDE_DIR}/plugins/claude-hud"
    os.makedirs(hud_config_dir, exist_ok=True)
    save_json(f"{hud_config_dir}/config.json", HUD_CONFIG)
    print("  ✅ HUD config (tools/agents/todos/duration/configCounts)")

    # Build statusline command
    statusline_cmd = build_statusline_cmd(runtime_path, runtime_name)
    return {"type": "command", "command": statusline_cmd}, {cache_key: True}


def main():
    hostname = run("hostname").stdout.strip()
    print(f"=== Claude Code Setup on {hostname} ===")

    # 1. Runtime
    step(1, "Checking JS runtime (bun/node)...")
    runtime, name = find_runtime()
    if not runtime:
        runtime = install_bun()
        name = "bun"
    print(f"  Using: {runtime} ({name})")

    # 2. ccusage (global via bun or pnpm)
    step(2, "Installing ccusage globally...")
    if name == "bun":
        run(f"{runtime} install -g ccusage", check=False)
    else:
        pm = shutil.which("pnpm") or shutil.which("npm")
        if pm:
            run(f"{pm} install -g ccusage", check=False)
    ccusage = shutil.which("ccusage")
    print(f"  ccusage: {ccusage or 'not on PATH (use bunx/pnpx)'}")

    # 3. Official marketplace + plugins
    step(3, "Installing 5 official plugins...")
    mp_dir = f"{PLUGINS_DIR}/marketplaces/{OFFICIAL_MARKETPLACE}"
    if not os.path.isdir(mp_dir):
        print("  Cloning official marketplace...")
        run(f"git clone --depth 1 https://github.com/anthropics/claude-plugins-official.git '{mp_dir}'")
    new_enabled = install_official_plugins(mp_dir)

    # 4. claude-hud
    step(4, "Installing claude-hud...")
    statusline_config, hud_enabled = install_claude_hud(runtime, name)
    new_enabled.update(hud_enabled)

    # 5. Update settings.json
    step(5, "Updating settings.json...")
    settings = load_json(SETTINGS_JSON, {})
    settings["statusLine"] = statusline_config
    if "enabledPlugins" not in settings:
        settings["enabledPlugins"] = {}
    for k, v in new_enabled.items():
        settings["enabledPlugins"][k] = v
    save_json(SETTINGS_JSON, settings)
    print("  ✅ settings.json updated")

    # 6. cc-switch common config
    step(6, "Syncing to cc-switch common_config_claude...")
    update_cc_switch(statusline_config, new_enabled)

    print(f"\n=== Done on {hostname}! ===")
    print("Restart Claude Code to see the HUD.")


if __name__ == "__main__":
    main()
