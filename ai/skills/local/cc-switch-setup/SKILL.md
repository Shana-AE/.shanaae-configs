---
name: cc-switch-setup
description: "Configure Claude Code providers in cc-switch (or standalone) from a version-controlled definition file. Inserts Qiniu model-preset providers with full Claude Code tier mapping (haiku/sonnet/opus/fable) into cc-switch's SQLite DB, and writes settings.json. Use when setting up Claude Code on a new machine, after changing provider definitions, or to switch the current provider."
---

# cc-switch-setup

Configures Claude Code's model providers from `scripts/providers.json` — a
version-controlled, secret-free definition file. Run once per machine.

## What it does

1. Reads `providers.json` (provider definitions with tier mappings) + `.secrets` (API key)
2. If `~/.cc-switch/cc-switch.db` exists: inserts/updates providers, updates `common_config_claude`, manages current provider
3. Always writes `~/.claude/settings.json` with the selected provider's config + common config (plugins/hooks/permissions) merged

## Provider tier mapping

Each provider maps Claude Code's internal model tiers (haiku/sonnet/opus/fable)
to the provider's model IDs. This lets Claude Code's model picker work correctly
with non-Claude models (GPT, DeepSeek, etc.) via Qiniu's Anthropic-compatible endpoint.

| Provider              | haiku       | sonnet      | opus        | fable       |
| --------------------- | ----------- | ----------- | ----------- | ----------- |
| Qiniu · Claude        | 4.5-haiku   | 4.6-sonnet  | 4.8-opus    | fable-5     |
| Qiniu · GPT-5.6       | gpt-5.6-luna| gpt-5.6-terra| gpt-5.6-sol| gpt-5.6-sol |
| Qiniu · DeepSeek V4   | v4-flash    | v4-pro-202606 | v4-pro-202606 | v4-pro-202606 |
| Qiniu · GPT-5.5       | (single model) | | | |
| Qiniu · GLM-5.2       | (single model) | | | |
| Qiniu · Kimi K2.7 Code| (single model) | | | |
| Qiniu · Grok 4.5      | (single model) | | | |

## Usage

```bash
# Full setup (insert providers into cc-switch DB + write settings.json)
python3 scripts/setup_claude_providers.py

# Switch to a specific provider + write its settings.json
python3 scripts/setup_claude_providers.py --provider qiniu-gpt-56-sol

# List available providers
python3 scripts/setup_claude_providers.py --list
```

## Platform notes

- **macOS**: cc-switch DB at `~/.cc-switch/cc-switch.db` (same path). If cc-switch
  is running, the script warns (SQLite WAL usually handles concurrent access).
- **No cc-switch** (e.g. macbook-work): standalone mode — writes settings.json
  directly from the default provider. No GUI switching, but Claude Code works.
- **settings.json**: written through the `~/.claude` → repo symlink. Contains the
  API key from `.secrets` — gitignored, never committed.
