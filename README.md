# ShanaAE Configs (Central Repository)

The central configuration hub for the ShanaAE development environment — the
single **Source of Truth** for AI-agent skills, user rules, MCP servers, and
model catalogs.

## Supported Tools

| Tool        | Status      | Config location in repo        |
| ----------- | ----------- | ------------------------------ |
| Claude Code | Active      | `.claude/`                       |
| OpenCode    | Active      | `.config/opencode/`              |
| Cursor      | Active      | `cursor/`                        |
| Qoder       | Active      | `qoder/` (Qoder + QoderCN)       |
| Codex CLI   | Active      | `.codex/`                        |
| dsh         | Active (dev preview) | `dsh/` (DeepSeek Harness) |
| Pi          | Active      | `pi/`                            |

> **Cross-platform support (Linux / Windows / macOS) is in design.**
> See [`docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md`](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md).
> Today the repo runs on **Linux (WSL2)** and is wired into Windows
> (Cursor/Qoder copy-sync + Claude). The design adds an `install.py` + link
> manifest so every tool live-links into the repo on all three OSes.

## Project Layout (high level)

```
configs/
├── .claude/              # Claude Code config (rules, skills, mcp.json, settings)
├── .config/opencode/     # OpenCode config (opencode.jsonc, agents, plugins)
├── cursor/               # Cursor config (skills pool, AGENTS.md, user_rules)
├── qoder/                # Qoder / QoderCN config (skills pool, AGENTS.md, user_rules)
├── ai/
│   ├── mcp/              # Master MCP server templates
│   ├── skills/           # vendor/ + local/ + private/ (gitignored) + skills-policy.json + for-tools/<agent>/ (generated, gitignored)
│   └── user_rules/       # English, Vue, HarmonyOS, learning, save-to-* rules
├── .claude-code-router/  # Claude Code Router (multi-provider routing)
├── dsh/                  # DeepSeek Harness config (settings.yaml)
├── pi/                   # Pi coding agent config (settings, models, AGENTS.md, skills)
├── .agents/              # `npx skills` CLI storage
└── .secrets              # API tokens (gitignored — see CONFIG_README.md)
```

See [`AGENTS.md`](AGENTS.md) for the full agent guidelines and
[`CONFIG_README.md`](CONFIG_README.md) for setup.

## Deployment Links (current)

### Skills & user rules (Cursor / Qoder)

- **WSL**: `~/.cursor/skills` -> `cursor/skills` and `~/.qoder/skills` ->
  `qoder/skills` (per-agent pools); rules via `cursor/user_rules` and
  `qoder/user_rules` -> `ai/user_rules`
- **Windows**: pools are **copy-synced** (NTFS can't junction into `\\wsl$`) by
  `ai/skills/local/sync-cursor-qoder/scripts/sync_cursor_qoder.py` into
  `%USERPROFILE%\.cursor`, `%USERPROFILE%\.qoder`, `%USERPROFILE%\.qoder-cn`

### MCP Configuration

- **Cursor / Qoder**: `mcp.json` written live by `sync_mcp.py` (canonical:
  `ai/skills/local/mcp-sync/scripts/mcp_servers.json`)
- **Claude**: `.claude/mcp.json` (repo) / `~/.claude.json` (runtime)
- **Codex**: `.codex/config.toml` `[mcp_servers.*]` sentinel block
- **OpenCode**: `.config/opencode/opencode.jsonc` `mcp` section

### dsh (DeepSeek Harness) & Pi

- **dsh**: `~/.dsh/settings.yaml` -> `dsh/settings.yaml` (LLM routes via
  `apiKeyEnv` env refs; credentials stay in `~/.dsh/.credentials.yaml`)
- **Pi**: `~/.pi/agent/{settings.json,models.json,AGENTS.md}` -> `pi/`; skills
  pool via `pi/skills` -> `ai/skills/for-tools/pi`

### Agent Skills CLI (`.agents`)

Used by the [skills](https://www.npmjs.com/package/skills) CLI to manage agent
skills.

- **Skills location**: `.agents/skills`
- **Usage**: `npx skills list` / `npx skills install <skill-name>`

## Quick Start

```bash
# 1. Clone
git clone git@github.com:Shana-AE/.shanaae-configs.git ~/.shanaae/configs
cd ~/.shanaae/configs

# 2. Create your .secrets (see CONFIG_README.md for the variable list)
cp .secrets.example .secrets   # when the cross-platform installer lands;
                               # for now, create .secrets manually per CONFIG_README

# 3. Render MCP configs from .secrets
python3 ai/skills/local/setup-configs/scripts/setup_configs.py

# 4. Build per-agent skill pools in for-tools/ (mandatory — for-tools is gitignored & generated)
#    Per-agent filtering: edit ai/skills/skills-policy.json first
bash ai/skills/link-skills.sh --dry-run   # preview
bash ai/skills/link-skills.sh             # apply
```
