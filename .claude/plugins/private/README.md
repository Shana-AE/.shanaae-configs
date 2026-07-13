# Claude Code Private Plugins

## Purpose

This directory holds Claude Code plugins that must **NOT** be committed to the
remote repository — proprietary, licensed, internal, or machine-local plugins.

Currently contains:
- **migbot** v1.1.2 — Android-to-ArkTS (HarmonyOS) migration toolkit

## Sync Rules

| Rule | Detail |
|------|--------|
| **Not git-synced** | The entire `.claude/plugins/` directory is gitignored. Each machine keeps its own copy. Only `.gitkeep` and this `README.md` are tracked. |
| **New machine setup** | Copy plugin dirs here, then update `known_marketplaces.json`, `installed_plugins.json`, `~/.claude/settings.json`, and cc-switch `common_config_claude` (in `~/.cc-switch/cc-switch.db`). |
| **Automation** | Run `python3 ai/skills/local/setup-configs/scripts/install_all_machines.py` — handles marketplace registration, cache copy, settings, and cc-switch sync. |
| **cc-switch survival** | Plugin paths in `extraKnownMarketplaces` and `enabledPlugins` are stored in cc-switch's `common_config_claude` db key, which survives provider switches. |
| **Upgrading** | Replace the plugin dir here, copy to `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, update `installed_plugins.json` version + `installPath`. Run `setup_claude_code.py sync` to push changes to cc-switch common config. |

## Path Mapping

| Machine | Path |
|---------|------|
| WSL (Linux) | `/home/shanaae/.shanaae/configs/.claude/plugins/private/<plugin>/` |
| macOS | `/Users/shanaae/.shanaae/configs/.claude/plugins/private/<plugin>/` |

The path resolves via `~/.claude` → `~/.shanaae/configs/.claude` symlink on each machine.
