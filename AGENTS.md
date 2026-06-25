# ShanaAE Configs - Agent Guidelines

This is the central configuration hub for AI development tools (Claude Code, OpenCode, Trae). It manages skills, MCP servers, and user rules across multiple AI coding agents.

## Repository Overview

- **Purpose**: Source of Truth for AI agent configurations, skills, and rules
- **Platform**: Linux (WSL2) today; **cross-platform (Linux / Windows / macOS) in design** — see [design spec](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md)
- **Active Tools**: Claude Code, OpenCode, Trae
- **Planned Tools (WIP)**: Cursor, Codex CLI

## Cross-Platform Support (WIP)

The repo is being made portable across **Linux (WSL2), Windows, and macOS**.
Full design: [`docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md`](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md).

Summary of the planned model:
- **Portable core** — repo configs contain no OS-specific literals.
- **Env-var values** — OS-specific paths live in `.secrets` and are resolved by
  each tool at read time (`{env:VAR}` in OpenCode, `$VAR` in Claude Code).
- **Link manifest + `install.py`** — one-time installer live-links each tool's
  native config location into the repo (symlink on *nix, junction on Windows).

> Until the installer lands, paths shown in this doc (e.g. `/home/shanaae/projects`)
> are the current **Linux/WSL** values.

## Directory Structure

```
configs/
├── .agents/           # Skills CLI storage (npx skills)
│   └── skills -> ai/skills/vendor
├── .claude/           # Claude Code configuration
│   ├── rules/         # User rules (symlinked from ai/user_rules)
│   ├── skills/        # Skills (symlinked from ai/skills/for-tools)
│   ├── mcp.json       # MCP server configuration
│   └── settings.json  # Claude settings (API keys, permissions)
├── .config/
│   └── opencode/      # OpenCode configuration
│       ├── AGENTS.md  # OpenCode-specific rules
│       ├── opencode.jsonc  # OpenCode config (uses {env:VAR} substitution)
│       ├── oh-my-openagent.jsonc  # oh-my-openagent agent routing
│       ├── agents/    # Subagents (image-op, web-devtools)
│       └── plugin/    # Vendored plugins (shell-strategy)
├── .trae/             # Trae configuration
│   ├── skills -> ai/skills/for-tools
│   └── user_rules -> ai/user_rules
├── .local/            # Runtime data (gitignored)
├── ai/
│   ├── mcp/           # MCP server configs (trae.json + .example)
│   ├── skills/        # Skills repository
│   │   ├── vendor/    # Third-party/installed skills
│   │   ├── local/     # Custom skills (eudic-manager, get-secret-token, etc.)
│   │   ├── for-tools/ # Symlinked skills for AI tools (auto-generated)
│   │   └── link-skills.sh
│   └── user_rules/    # User rule definitions
├── .claude-code-router/  # Claude Code Router config
│   └── config.json       # Router configuration
└── .secrets           # API tokens and secrets (gitignored)
```

## Build/Setup Commands

```bash
# Link all skills to for-tools directory
bash ai/skills/link-skills.sh

# Setup configuration files from .secrets
python3 ai/skills/local/setup-configs/scripts/setup_configs.py

# Or use the Trae skill
trae run setup-configs

# Manage skills with npx
npx skills list
npx skills install <skill-name>
```

## Skills Management

### Skill Types

| Location | Purpose | Examples |
|----------|---------|----------|
| `vendor/` | Third-party skills installed via `npx skills` | vue, vite, pinia, nuxt, shadcn-ui |
| `local/` | Custom skills for this environment | eudic-manager, get-secret-token, ticktick-dida365 |
| `for-tools/` | Symlinked directory for AI tools (auto-generated) |

### Creating Custom Skills

1. Create directory in `ai/skills/local/<skill-name>/`
2. Add `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: skill-name
   description: "Clear description of when to use this skill"
   ---
   # Skill Instructions
   ...
   ```
3. Add optional `scripts/` or `references/` subdirectories
4. Run `bash ai/skills/link-skills.sh` to link

### Skill Structure Convention

```
skill-name/
├── SKILL.md           # Required: metadata + instructions
├── scripts/           # Optional: executable Python/Bash scripts
└── references/        # Optional: documentation to load on demand
```

## MCP Configuration

MCP servers are configured in multiple locations (keep in sync):
- `ai/mcp/trae.json` - Master config (rendered from `trae.json.example`)
- `.claude/mcp.json` - Claude Code
- `.config/opencode/opencode.jsonc` - OpenCode

### Common MCP Servers

| Server | Command | Purpose |
|--------|---------|---------|
| Git | `uvx mcp-server-git` | Git operations |
| Filesystem | `npx @modelcontextprotocol/server-filesystem <PROJECTS_DIR>` | File operations (path is OS-specific; currently `/home/shanaae/projects` on WSL) |
| Chrome DevTools | `npx chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:9222` | Chrome/Brave debugging — **globally disabled; enabled only inside the `web-devtools` subagent** to save context tokens |
| Memory | `npx @modelcontextprotocol/server-memory` | Knowledge graph |
| Sequential Thinking | `npx @modelcontextprotocol/server-sequential-thinking` | Complex reasoning |

> **Replaced by skills (no longer MCP):** documentation lookup → `context7` skill
> (curl API + `CONTEXT7_API_KEY`); browser automation → `agent-browser` / `browser-use`
> skills; URL fetching → `webfetch` + `defuddle` skill.

## Claude Code Router

Claude Code Router allows routing Claude Code requests to different model providers.

- **Config Location**: `.claude-code-router/config.json`
- **Symlink**: `~/.claude-code-router` -> `configs/.claude-code-router`
- **Symlink**: `~/.claude-code-router/config.json` -> `configs/.claude-code-router/config.json`

### Supported Providers

| Provider | Base URL | Models (representative) |
|----------|----------|------------------------|
| Qiniu | `api.qnaigc.com` | Claude 4.8 Opus, GLM-5.2, Kimi-K2.7-Code, Gemini 3.5 Flash, DeepSeek V4, Qwen3.7-Max, Grok 4.3 |
| Zhipu Coding Plan | `open.bigmodel.cn` | GLM-5.2, GLM-5.1, GLM-5, GLM-Z1 |
| DeepSeek | `api.deepseek.com` | deepseek-chat, deepseek-reasoner |
| OpenRouter | `openrouter.ai` | Claude, Gemini, DeepSeek |
| SiliconFlow | `api.siliconflow.cn` | Kimi-K2, DeepSeek-V3, Qwen3 |

> The `/v1/models` endpoint is **not authoritative** (it omits many working
> models). Model availability was verified by live chat-completion probes.

### Router Configuration

Routes map Claude Code request types to a provider+model. Current defaults:

| Route | Default Model |
|-------|---------------|
| default | qiniu,claude-4.6-sonnet |
| background | qiniu,claude-4.5-haiku |
| think | qiniu,deepseek/deepseek-v3.2 |
| longContext | qiniu,qwen3-max |
| webSearch | qiniu,qwen3-max |
| image | qiniu,qwen-vl-max-2025-01-25 |

> `claude-4.6-sonnet` is the **newest available Sonnet** (4.7/4.8/4.9-sonnet
> return "no available channels"); for heavy lifting, switch to
> `claude-4.8-opus` via `ccr model`. Routes are already current-generation.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `QINIU_AI_API_KEY` | Qiniu AI API key |
| `BIGMODEL_API_KEY` | Zhipu AI API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `SILICONFLOW_API_KEY` | SiliconFlow API key |
| `CCR_API_KEY` | Router authentication key |
| `CCR_PROXY_URL` | Optional proxy URL |

### Usage

```bash
# Start Claude Code with router
ccr code

# Restart after config changes
ccr restart

# Interactive model selection
ccr model

# UI mode for config management
ccr ui
```


## User Rules

Rules are stored in `ai/user_rules/` and symlinked to tool directories.

### English Learning

- Always answer in English
- On every message, prepend an **English Check** block: correct/optimize my question, nudge me to English if I used Chinese, list vocabulary above CET-6
- Annotate long/difficult sentences in Chinese
- Full rule: `ai/user_rules/english-learning.md` (threshold = CET-6, consistent everywhere)

### Skill Coaching (self-gating)

Triggered only when the relevant tech is in use; surface relevant 易错点 (pitfalls) + key concepts, then offer to save to Obsidian.

- **Vue** — `ai/user_rules/vue-learning.md`: leverages the `vue` skill's `references/gotchas.md`; covers `.value`, reactivity loss on destructure, computed side-effects, `v-if`+`v-for`, prop mutation, async-watcher races.
- **HarmonyOS (ArkTS/ArkUI)** — `ai/user_rules/harmonyos-learning.md`: state decorators (`@State`/`@Prop`/`@Link`/`@Provide`-`@Consume`/`@Observed`+`@ObjectLink`), single-root `build()`, no browser APIs, `ForEach` vs `LazyForEach`, strict typing.

### Save to Obsidian

- Save files to `/Inbox/ai-skills` in Obsidian vault

### Save to Eudic

- Use `EUDIC_TOKEN` environment variable
- Script: `ai/skills/local/eudic-manager/scripts/eudic_api.py`
- Token source: https://my.eudic.net/OpenAPI/Authorization

## Secrets Management

Secrets are stored in `.secrets` file (gitignored).

### Key Mappings

| Service | Key in .secrets | Environment Variable |
|---------|-----------------|---------------------|
| OpenAI | `OPENAI_API_KEY_OPENAPI` | `OPENAI_API_KEY` |
| GitHub | `GITHUB_TOKEN_MCP` | `GITHUB_TOKEN` |
| Eudic | `EUDIC_TOKEN` | `EUDIC_TOKEN` |
| Context7 | `CONTEXT7_API_KEY` | `CONTEXT7_API_KEY` |
| TickTick | `TICKTICK_CLIENT_ID/SECRET` | Same |
| Qiniu AI | `QINIU_AI_API_KEY` | `QINIU_AI_API_KEY` |

### Loading Secrets

```bash
# Read and export a specific token
export EUDIC_TOKEN='$(grep EUDIC_TOKEN .secrets | cut -d= -f2)'

# Or use the get-secret-token skill
```

## Code Style Guidelines

### Markdown

- Use `#` for headers with consistent hierarchy
- Include both English and Chinese for user-facing rules
- Use tables for structured data

### JSON Configuration

- 2-space indentation
- Keep MCP configs synchronized across tools
- Use `disabled: true` to temporarily disable servers

### Shell Scripts

- Use `#!/bin/bash` shebang
- Quote variables: `"$VARIABLE"`
- Use `set -e` for error handling in complex scripts

### Python Scripts (in skills)

- Python 3.x compatible
- Use `argparse` for CLI arguments
- Handle environment variables with `os.environ.get()`

## Git Conventions

### .gitignore Structure

The `.gitignore` uses a layered approach:
1. **Allowlist first** (e.g., `!.claude/.claude.json`)
2. **Runtime data** (transcripts, cache, debug)
3. **Sensitive files** (.secrets, auth.json)

### Files to Never Commit

- `.secrets` - API tokens
- `ai/mcp/trae.json` - Contains embedded tokens
- `.config/opencode/opencode.jsonc` - Contains tokens (via `{env:VAR}`)
- `.local/share/opencode/auth.json` - Authentication

## Symlink Management

Key symlinks in this repository:

```bash
# Claude Code
.claude/rules -> ../../ai/user_rules
.claude/skills -> ../../ai/skills/for-tools

# Trae
.trae/skills -> ../ai/skills/for-tools
.trae/user_rules -> ../ai/user_rules

# Agents CLI
.agents/skills -> ../ai/skills/vendor

# Claude Code Router (whole dir, including config.json)
~/.claude-code-router -> configs/.claude-code-router
~/.claude-code-router/config.json -> configs/.claude-code-router/config.json
```

## Troubleshooting

### Skills not appearing

```bash
# Re-link skills
bash ai/skills/link-skills.sh

# Verify symlinks
ls -la ai/skills/for-tools/
```

### MCP server not connecting

1. Check if `npx`/`uvx` is available
2. Verify API keys in `.secrets`
3. Run setup-configs to regenerate config files

### Configuration drift

1. Compare `ai/mcp/trae.json` with `.claude/mcp.json`
2. Re-run `python3 ai/skills/local/setup-configs/scripts/setup_configs.py`
