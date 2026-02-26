# ShanaAE Configs - Agent Guidelines

This is the central configuration hub for AI development tools (Claude Code, OpenCode, Trae). It manages skills, MCP servers, and user rules across multiple AI coding agents.

## Repository Overview

- **Purpose**: Source of Truth for AI agent configurations, skills, and rules
- **Platform**: Linux (WSL2), symlinked to multiple AI tool directories
- **Primary Tools**: Claude Code, OpenCode, Trae

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
│       └── opencode.json
├── .trae/             # Trae configuration
│   ├── skills -> ai/skills/for-tools
│   └── user_rules -> ai/user_rules
├── .local/            # Runtime data (gitignored)
├── ai/
│   ├── mcp/           # MCP server configs (trae.json)
│   ├── skills/        # Skills repository
│   │   ├── vendor/    # Third-party/installed skills
│   │   ├── local/     # Custom skills (eudic-manager, get-secret-token, etc.)
│   │   ├── for-tools/ # Symlinked skills for AI tools
│   │   └── link-skills.sh
│   └── user_rules/    # User rule definitions
├── .claude-code-router/  # Claude Code Router config
│   └── config.json       # Router configuration
└── .secrets           # API tokens and secrets (gitignored)
```
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
- `ai/mcp/trae.json` - Master config
- `.claude/mcp.json` - Claude Code
- `.config/opencode/opencode.json` - OpenCode

### Common MCP Servers

| Server | Command | Purpose |
|--------|---------|---------|
| Git | `uvx mcp-server-git` | Git operations |
| Filesystem | `npx @modelcontextprotocol/server-filesystem /home/shanaae/projects` | File operations |
| Playwright | `npx @executeautomation/playwright-mcp-server` | Browser automation |
| Chrome DevTools | `npx chrome-devtools-mcp@latest` | Chrome debugging |
| context7 | `npx @upstash/context7-mcp@latest` | Documentation lookup |
| Memory | `npx @modelcontextprotocol/server-memory` | Knowledge graph |
| Sequential Thinking | `npx @modelcontextprotocol/server-sequential-thinking` | Complex reasoning |

## Claude Code Router

Claude Code Router allows routing Claude Code requests to different model providers.

- **Config Location**: `.claude-code-router/config.json`
- **Symlink**: `~/.claude-code-router` -> `configs/.claude-code-router`
- **Symlink**: `~/.claude-code-router/config.json` -> `configs/.claude-code-router/config.json`

### Supported Providers

| Provider | Base URL | Models |
|----------|----------|--------|
| Qiniu | `api.qnaigc.com` | Claude, DeepSeek, Qwen, GLM, Kimi, Doubao |
| Zhipu Coding Plan | `open.bigmodel.cn` | GLM-4.x, GLM-Z1 |
| DeepSeek | `api.deepseek.com` | deepseek-chat, deepseek-reasoner |
| OpenRouter | `openrouter.ai` | Claude, Gemini, DeepSeek |
| SiliconFlow | `api.siliconflow.cn` | Kimi-K2, DeepSeek-V3, Qwen3 |

### Router Configuration

| Route | Default Model |
|-------|---------------|
| default | qiniu,deepseek-v3.1 |
| background | qiniu,deepseek-v3 |
| think | qiniu,deepseek-r1 |
| longContext | qiniu,qwen3-max |
| webSearch | qiniu,qwen3-max |
| image | qiniu,qwen-vl-max-2025-01-25 |

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
- Annotate long/difficult sentences in Chinese
- List words above CET-4 (大学英语四级) level

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
- `.config/opencode/opencode.json` - Contains tokens
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

# Claude Code Router
~/.claude-code-router -> configs/.claude-code-router


# Claude Code Router
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
