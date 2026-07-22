---
name: mcp-sync
description: "Synchronize MCP server config and enabled/disabled status across OpenCode, Claude Code (~/.claude.json), Codex (~/.codex/config.toml), and the repo .claude/mcp.json from one canonical source (mcp_servers.json). Use when MCP configs have drifted between tools, after editing the canonical MCP list, or to enforce a consistent enabled/disabled set everywhere."
---

# mcp-sync

Keeps MCP server definitions + enabled/disabled status in sync across all
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
| codex | `~/.codex/config.toml` (`[mcp_servers.*]`, sentinel block) | `env_vars`/`bearer_token_env_var`/`env_http_headers` (env-name refs) | `enabled = false` |

The opencode edit is **surgical** — only the `"mcp": {...}` block is rewritten;
all comments, `plugin`, `provider`, `tools`, and `instructions` are preserved.

The codex edit is **sentinel-based and tolerant** — between `# BEGIN mcp-sync`
and `# END mcp-sync`, the canonical `[mcp_servers.*]` tables are regenerated
from the source of truth, while any *foreign* content other writers place
inside the sentinel (notably the ChatGPT desktop app's Codex integration,
which injects `notify`, `[mcp_servers.node_repl]`, `[mcp_servers.computer-use]`,
`[marketplaces]`, `[plugins]`, `[features]`) is preserved verbatim. App-managed
server names are listed in `CODEX_APP_MCP_SERVERS`; a `[mcp_servers.<name>]`
that is neither canonical nor in that allowlist is treated as a removed server
and dropped. Base settings, provider tables (written by cc-switch), and user
comments outside the sentinels are preserved.

`exclude_from_opencode` (default: `context7`, `codegraph`) lists servers managed
by the oh-my-openagent plugin at runtime; they are omitted from opencode.jsonc
but still written to the Claude and Codex configs.

### Codex env-var mapping

Codex's `config.toml` has no general `{env:VAR}` string interpolation. Instead it
uses dedicated fields that *name* the env var for Codex to read at runtime. The
emitter maps accordingly:

| Canonical pattern | Codex output | Notes |
|---|---|---|
| stdio `env: { "KEY": "{env:VAR}" }` | `env_vars = ["VAR"]` | Forwards from parent shell. **Name must match** — if the subprocess expects a different key (e.g. `Z_AI_API_KEY` vs `BIGMODEL_API_KEY`), export both names in the shell. |
| stdio `env: { "KEY": "literal" }` | `env = { "KEY" = "literal" }` | Inline table of literals. |
| http `Authorization: Bearer {env:VAR}` | `bearer_token_env_var = "VAR"` | Codex sets the header at runtime. |
| http other `{env:VAR}` headers | `env_http_headers = { "Hdr" = "VAR" }` | Header-name → env-var-name. |
| http static headers | `http_headers = { "Hdr" = "val" }` | Literal values. |

## Usage

```bash
# Preview drift (default; writes nothing)
python3 scripts/sync_mcp.py

# Write all targets (creates timestamped .bak backups)
python3 scripts/sync_mcp.py --apply

# Limit to one target
python3 scripts/sync_mcp.py --apply --target codex

# CI / pre-commit hook: exit 1 if drift (repo targets only: opencode + mcp.json + codex)
python3 scripts/sync_mcp.py --check
```

After `--apply`, restart opencode / Claude Code / Codex to load the new MCP set.

## Workflow

1. Edit `scripts/mcp_servers.json` (add/remove servers, flip `enabled`).
2. Run `--dry-run` → review the diff (secrets are redacted in output).
3. Run `--apply`.
4. Verify: `opencode mcp list` (in a project with omo) and check Claude Code's MCP list.
