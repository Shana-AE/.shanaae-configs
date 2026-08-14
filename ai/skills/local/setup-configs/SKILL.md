---
name: setup-configs
description: >
  Generates configuration files from .example files by substituting secrets,
  AND sets up Claude Code statusline (ccusage/claude-hud) with cc-switch
  common config integration. Use when setting up a new machine or refreshing
  configs.
---

# setup-configs

Two scripts handle different concerns:

## 1. `scripts/setup_configs.py` — Generate config files from secrets

Substitutes placeholders in `.example` files with values from `.secrets`:

```bash
python3 ai/skills/local/setup-configs/scripts/setup_configs.py
```

Generates: `.config/opencode/opencode.json` from its `.example` template.

## 2. `scripts/setup_claude_code.py` — Claude Code statusline setup

Manages the statusLine config (ccusage or claude-hud) in a way that
**survives cc-switch provider switches** by writing to cc-switch's
`common_config_claude` key in its SQLite db.

### Subcommands

```bash
# One-time setup: install ccusage globally + configure statusLine
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py setup

# After installing claude-hud (run /claude-hud:setup first), sync its
# statusLine command into cc-switch common config so it survives switches
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py sync

# Show current statusLine config from settings.json + cc-switch db
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py status
```

### How it works

- **`setup`**: Installs `ccusage` via pnpm, adds `statusLine` to both
  `~/.claude/settings.json` (immediate effect) and cc-switch's
  `common_config_claude` db key (survives provider switches).
- **`sync`**: Reads the `statusLine` key from `~/.claude/settings.json`
  (e.g. after `/claude-hud:setup` overwrites it) and writes it into
  cc-switch's `common_config_claude`. Run this after any statusLine change
  you want to persist across switches.

### cc-switch common config

cc-switch stores a `common_config_claude` JSON blob in `~/.cc-switch/cc-switch.db`
(settings table). This JSON is **merged into every provider's settings.json**
on switch. Keys in this blob (permissions, hooks, enabledPlugins,
extraKnownMarketplaces, statusLine) survive provider switches. Keys NOT in
this blob get wiped on each switch.

### Installing claude-hud (interactive, must run in Claude Code)

```
/plugin marketplace add jarrodwatts/claude-hud
/plugin install claude-hud
/claude-hud:setup
/claude-hud:configure
```

Linux TMPDIR workaround (if `/plugin install` fails with `EXDEV`):
```bash
mkdir -p ~/.cache/tmp && TMPDIR=~/.cache/tmp claude
```

After `/claude-hud:setup`, run:
```bash
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py sync
```
