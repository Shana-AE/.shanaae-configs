# ShanaAE Configs (Central Repository)

The central configuration hub for the ShanaAE development environment — the
single **Source of Truth** for AI-agent skills, user rules, MCP servers, and
model catalogs.

## Supported Tools

| Tool        | Status      | Config location in repo        |
| ----------- | ----------- | ------------------------------ |
| Claude Code | Active      | `.claude/`                       |
| OpenCode    | Active      | `.config/opencode/`              |
| Trae        | Active      | `.trae/` + `ai/mcp/trae.json`      |
| Cursor      | Planned (WIP) | `.cursor/` (not yet created)    |
| Codex CLI   | Planned (WIP) | `.codex/` (not yet created)     |

> **Cross-platform support (Linux / Windows / macOS) is in design.**
> See [`docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md`](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md).
> Today the repo runs on **Linux (WSL2)** and is partially wired into Windows
> (Trae/Claude). The design adds an `install.py` + link manifest so every tool
> live-links into the repo on all three OSes.

## Project Layout (high level)

```
configs/
├── .claude/              # Claude Code config (rules, skills, mcp.json, settings)
├── .config/opencode/     # OpenCode config (opencode.jsonc, agents, plugins)
├── .trae/                # Trae config (skills, user_rules)
├── ai/
│   ├── mcp/              # Master MCP configs (trae.json + .example)
│   ├── skills/           # vendor/ + local/ + private/ (gitignored) + for-tools/ (generated, gitignored)
│   └── user_rules/       # English, Vue, HarmonyOS, learning, save-to-* rules
├── .claude-code-router/  # Claude Code Router (multi-provider routing)
├── .agents/              # `npx skills` CLI storage
└── .secrets              # API tokens (gitignored — see CONFIG_README.md)
```

See [`AGENTS.md`](AGENTS.md) for the full agent guidelines and
[`CONFIG_README.md`](CONFIG_README.md) for setup.

## Deployment Links (current)

### MCP Configuration (`ai/mcp/trae.json`)

- **Linux (Remote)**: symlink to `~/.trae-server/data/Machine/mcp.json`
- **Linux (Local)**: symlink to `~/.config/Trae/User/mcp.json`
- **Windows**: symlink to `C:\Users\shana\AppData\Roaming\Trae\User\mcp.json`

> These paths are the current Linux/WSL values. The cross-platform design
> replaces them with env-var references (`{env:PROJECTS_DIR}` etc.) resolved
> per-OS at runtime.

### Trae Configuration

- **Skills**: `.trae/skills` -> `ai/skills/for-tools`
- **User Rules**: `.trae/user_rules` -> `ai/user_rules`

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

# 4. Link skills into for-tools/ (mandatory — for-tools is gitignored & generated)
bash ai/skills/link-skills.sh
```
