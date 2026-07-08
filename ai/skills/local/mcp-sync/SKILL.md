---
name: mcp-sync
description: "Synchronize MCP server config and enabled/disabled status across OpenCode, Claude Code (~/.claude.json), and the repo .claude/mcp.json from one canonical source (mcp_servers.json). Use when MCP configs have drifted between tools, after editing the canonical MCP list, or to enforce a consistent enabled/disabled set everywhere."
---

# mcp-sync

Keeps MCP server definitions + enabled/disabled status in sync across all three
live config locations, from a single source of truth.

## Source of truth

`scripts/mcp_servers.json` — format-agnostic canonical definition of every MCP
server (command/URL, env via `{env:VAR}` refs, `enabled` flag). **Edit this file,
not the tool configs.**

## Render targets

| Target | File | Secret style | Status style |
|---|---|---|---|
| opencode | `~/.config/opencode/opencode.jsonc` (`mcp` section) | `{env:VAR}` (kept) | `enabled: false` |
| claude | `~/.claude.json` (`mcpServers`) | resolved plaintext | `disabled: true` |
| mcp.json | `~/.claude/mcp.json` (repo, committed) | `${VAR}` (shell) | `disabled: true` |

The opencode edit is **surgical** — only the `"mcp": {...}` block is rewritten;
all comments, `plugin`, `provider`, `tools`, and `instructions` are preserved.

`exclude_from_opencode` (default: `context7`, `codegraph`) lists servers managed
by the oh-my-openagent plugin at runtime; they are omitted from opencode.jsonc
but still written to the Claude configs.

## Usage

```bash
# Preview drift (default; writes nothing)
python3 scripts/sync_mcp.py

# Write all targets (creates timestamped .bak backups)
python3 scripts/sync_mcp.py --apply

# Limit to one target
python3 scripts/sync_mcp.py --apply --target opencode

# CI / pre-commit hook: exit 1 if drift
python3 scripts/sync_mcp.py --check
```

After `--apply`, restart opencode / Claude Code to load the new MCP set.

## Workflow

1. Edit `scripts/mcp_servers.json` (add/remove servers, flip `enabled`).
2. Run `--dry-run` → review the diff (secrets are redacted in output).
3. Run `--apply`.
4. Verify: `opencode mcp list` (in a project with omo) and check Claude Code's MCP list.
