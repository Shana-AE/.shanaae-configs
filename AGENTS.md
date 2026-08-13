# ShanaAE Configs - Agent Guidelines

This is the central configuration hub for AI development tools (Claude Code, OpenCode, Trae). It manages skills, MCP servers, and user rules across multiple AI coding agents.

## Repository Overview

- **Purpose**: Source of Truth for AI agent configurations, skills, and rules
- **Platform**: Linux (WSL2) today; **cross-platform (Linux / Windows / macOS) in design** — see [design spec](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md)
- **Active Tools**: Claude Code, OpenCode, Trae, Codex CLI, dsh (DeepSeek Harness), Pi
- **Planned Tools (WIP)**: Cursor

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
│   ├── skills/        # Skills (symlinked from ai/skills/for-tools/claude)
│   ├── mcp.json       # MCP server configuration
│   └── settings.json  # Claude settings (API keys, permissions)
├── .config/
│   └── opencode/      # OpenCode configuration
│       ├── AGENTS.md  # OpenCode-specific rules
│       ├── opencode.jsonc  # OpenCode config (uses {env:VAR} substitution)
│       ├── oh-my-openagent.jsonc  # oh-my-openagent agent routing
│       ├── agents/    # Subagents (image-op, web-devtools)
│       ├── plugin/    # Vendored plugins (shell-strategy)
│       └── skills -> ../../ai/skills/for-tools/opencode
├── .trae/             # Trae configuration
│   ├── skills -> ai/skills/for-tools/trae
│   └── user_rules -> ai/user_rules
├── .local/            # Runtime data (gitignored)
├── ai/
│   ├── mcp/           # MCP server configs (trae.json + .example)
│   ├── skills/        # Skills repository
│   │   ├── vendor/    # Third-party/installed skills
│   │   ├── local/     # Custom skills (eudic-manager, get-secret-token, etc.)
│   │   ├── private/   # Machine-local skills (gitignored — never committed)
│   │   ├── skills-policy.json  # Per-agent skill toggles (source of truth)
│   │   ├── for-tools/ # Per-agent pools: opencode/ claude/ codex/ trae/ pi/ (generated, gitignored)
│   │   └── link-skills.sh
│   └── user_rules/    # User rule definitions
├── dsh/                   # DeepSeek Harness config (settings.yaml, env-ref secrets)
├── pi/                    # Pi coding agent config (settings.json, AGENTS.md, models.json, skills link)
├── .claude-code-router/  # Claude Code Router config
│   └── config.json       # Router configuration
├── .codex/               # Codex CLI configuration
│   ├── config.toml       # Codex config (base settings + MCP via mcp-sync sentinel)
│   ├── AGENTS.md         # Codex global instructions
│   ├── skills -> ../ai/skills/for-tools/codex  # Per-agent pool (symlink)
│   ├── sqlite/           # Runtime state (gitignored)
│   ├── codex-lsp/        # LSP daemon runtime (gitignored)
│   └── process_manager/  # Background process state (gitignored)
└── .secrets           # API tokens and secrets (gitignored)
```

## Build/Setup Commands

```bash
# Build per-agent skill pools in for-tools/ (mandatory after clone — for-tools is gitignored)
bash ai/skills/link-skills.sh --dry-run   # preview what would be linked
bash ai/skills/link-skills.sh             # apply

# Setup configuration files from .secrets
python3 ai/skills/local/setup-configs/scripts/setup_configs.py

# Or use the Trae skill
trae run setup-configs

# Sync MCP server config + enabled/disabled status across opencode, ~/.claude.json, .claude/mcp.json, and ~/.codex/config.toml
# Source of truth: ai/skills/local/mcp-sync/scripts/mcp_servers.json
python3 ai/skills/local/mcp-sync/scripts/sync_mcp.py --dry-run   # preview drift
python3 ai/skills/local/mcp-sync/scripts/sync_mcp.py --apply     # write all targets
python3 ai/skills/local/mcp-sync/scripts/sync_mcp.py --check     # CI/hook: exit 1 on drift

# Setup Claude Code statusline (ccusage/claude-hud) — survives cc-switch provider switches
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py setup    # install ccusage + statusLine
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py sync    # after /claude-hud:setup
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py status   # show current config

# Manage skills with npx
npx skills list
npx skills install <skill-name>
```

## Skills Management

### Skill Types

| Location | Purpose | Examples |
|----------|---------|----------|
| `vendor/` | Third-party skills installed via `npx skills` | vue, vite, pinia, nuxt, shadcn-ui |
| `local/` | Custom skills for this environment (committed) | eudic-manager, get-secret-token, ticktick-dida365 |
| `private/` | Machine-local skills — **gitignored, never committed to remote**; still linked into `for-tools/<agent>/` so all AI tools pick them up | backend-api-generator-skill |
| `for-tools/<agent>/` | Per-agent symlink pool (opencode/ claude/ codex/ trae/); **generated by `link-skills.sh`, gitignored** | — |
| `skills-policy.json` | Per-agent include/exclude rules (**source of truth** for toggles) — see below | — |

### Per-Agent Skill Toggles

Each tool sees its **own** filtered pool: `link-skills.sh` renders
`for-tools/<agent>/` per the rules in `ai/skills/skills-policy.json`, then
re-points every tool's `skills` symlink there. An agent absent from the policy
(or with `{}`) gets the full set.

```json
{
  "defaults": { "exclude": ["*.bak*"] },
  "opencode": { "include": ["vue", "vite-*", "^obsidian-"], "exclude": ["lark-*"] },
  "claude": {},
  "codex": {},
  "trae": {}
}
```

| Key | Role |
|-----|------|
| `defaults.exclude` | Applied to **every** agent; hard exclusion — always wins over `include` |
| `<agent>.include` | If **non-empty**, only matching skills are linked |
| `<agent>.exclude` | Removed from that agent's pool even if `include` matches |

Pattern types are **auto-detected** per entry (documented in the repo's
`link-skills.sh`): contains `^`/`$` → regex (search semantics); contains
`*`/`?`/`[` → glob (full match); otherwise exact skill-name match.

After editing the policy, preview with `--dry-run` then re-run
`bash ai/skills/link-skills.sh` to relink all pools.

### Creating Custom Skills

1. Create directory in `ai/skills/local/<skill-name>/` (committed) **or** `ai/skills/private/<skill-name>/` if the skill must **not** be committed (machine-local / sensitive — `private/` is gitignored)
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
4. Run `bash ai/skills/link-skills.sh` to link into every agent pool (skills from `private/` are linked the same way but never reach the remote repo). If a skill stays invisible in a tool, check `skills-policy.json` — its patterns may exclude it.

### Skill Structure Convention

```
skill-name/
├── SKILL.md           # Required: metadata + instructions
├── scripts/           # Optional: executable Python/Bash scripts
└── references/        # Optional: documentation to load on demand
```

## MCP Configuration

**Canonical source of truth:** `ai/skills/local/mcp-sync/scripts/mcp_servers.json`
(format-agnostic: command/URL, `{env:VAR}` secret refs, `enabled` flag). The
`mcp-sync` skill renders it into all live targets — edit the canonical, then run
`python3 ai/skills/local/mcp-sync/scripts/sync_mcp.py --apply`.

MCP servers are configured in multiple locations (kept in sync by `mcp-sync`):

| Target | File | Secret style | Status style |
|---|---|---|---|
| OpenCode | `.config/opencode/opencode.jsonc` (`mcp` section) | `{env:VAR}` (kept) | `enabled: false` |
| Claude (runtime) | `~/.claude.json` (`mcpServers`) — not in repo | resolved plaintext | `disabled: true` |
| Claude (repo) | `.claude/mcp.json` — committed | `${VAR}` (shell) | `disabled: true` |
| Codex | `.codex/config.toml` (`[mcp_servers.*]`, sentinel block) — committed | `env_vars`/`bearer_token_env_var` (env-name refs) | `enabled = false` |
| Trae | `ai/mcp/trae.json` (rendered from `trae.json.example` by `setup-configs`) | embedded tokens | — |

> The OpenCode edit is surgical — only the `"mcp": {...}` block is rewritten; all
> comments and other top-level keys are preserved. `~/.claude.json` is merged
> (all its other keys are kept). A lefthook `pre-commit` job runs
> `sync_mcp.py --check --repo-only` whenever `mcp_servers.json` is staged, so a
> stale canonical that wasn't re-rendered blocks the commit.
>
> `exclude_from_opencode` (`context7`, `codegraph`) lists servers omitted from
> `opencode.jsonc` because they are delivered as **skills** (the `context7` and
> `codegraph` skills wrap the curl API / `codegraph` CLI directly) rather than as
> always-on global MCP servers — keeping the global config light and decoupled
> from oh-my-openagent (omo). They are still written to the Claude and Codex
> configs. When omo is enabled for a project it may additionally provision/serve
> `codegraph` at runtime regardless of the canonical `enabled` flag; disable that
> via omo's `disabled_mcps` if it conflicts.
>
> The Codex edit is **sentinel-based and tolerant** — between `# BEGIN mcp-sync`
> and `# END mcp-sync` the canonical `[mcp_servers.*]` tables are regenerated
> from the source of truth, while foreign content the ChatGPT app injects
> inside the sentinel (`notify`, `node_repl`, `computer-use`, `[marketplaces]`,
> `[plugins]`, `[features]`) is preserved verbatim. App-managed server names
> live in `CODEX_APP_MCP_SERVERS`; any other `[mcp_servers.<name>]` not in the
> canonical source is treated as removed and dropped. Base settings and
> provider tables (written by cc-switch) outside the sentinels are preserved.
> Codex's `config.toml` has no general `{env:VAR}` interpolation, so secrets use
> env-name reference fields (`env_vars`, `bearer_token_env_var`, `env_http_headers`).

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

### Model routing: cc-switch vs claude-code-router

Two systems can route Claude Code to non-default providers. They are
**complementary** — pick one per session, not both:

| | cc-switch (primary) | claude-code-router (fallback) |
|---|---|---|
| **How** | Writes `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` directly to `~/.claude/settings.json`; Claude reads it natively | Wraps Claude via `ccr code`; a Node proxy at `:3456` translates formats |
| **Scope** | Claude Code, Claude Desktop, Codex, Gemini, OpenCode (7 tools) | Claude Code only |
| **Switching** | GUI / tray / deep-link (no CLI) | CLI (`ccr model`) |
| **Status** | Active (default provider) | Idle (kept for CLI-driven / transformer-heavy use) |

> **Note**: cc-switch **full-overwrites** `~/.claude/settings.json` on every
> provider switch (it does not merge). However, cc-switch has a
> **`common_config_claude`** key in its db (`~/.cc-switch/cc-switch.db`,
> settings table) that is **merged into every provider's settings.json** on
> switch. Keys in this blob (permissions, hooks, enabledPlugins,
> extraKnownMarketplaces, statusLine) survive provider switches. Keys NOT in
> this blob get wiped on each switch. The `setup_claude_code.py sync` script
> reads the `statusLine` key from `~/.claude/settings.json` and writes it
> into `common_config_claude` so it persists. cc-switch also writes Codex's
> `config.toml` via `toml_edit` (a non-destructive merge — base settings and
> the mcp-sync block are preserved).

## Claude Code Statusline & Plugins

### Statusline (ccusage + claude-hud)

The statusline shows real-time model, cost, context usage, tools, agents, and
todos at the bottom of the Claude Code terminal.

- **ccusage** (`pnpm install -g ccusage`) — cost/burn-rate/billing focus.
  Installed globally, configured as the default statusline.
- **claude-hud** (plugin, `jarrodwatts/claude-hud`) — session-visibility
  focus (tools, agents, todos, git, context bar). More OpenCode-like.
  Recommended primary; install interactively in Claude Code.

After installing/changing the statusline (e.g. via `/claude-hud:setup`), run:
```bash
python3 ai/skills/local/setup-configs/scripts/setup_claude_code.py sync
```
This syncs the `statusLine` key from `~/.claude/settings.json` into cc-switch's
`common_config_claude` so it survives provider switches.

### Recommended Plugins

Install from the official marketplace (already added as `claude-plugins-official`):

| Plugin | Purpose | Install |
|--------|---------|---------|
| `claude-hud` | Real-time statusline (context, tools, agents, todos, git) | `/plugin marketplace add jarrodwatts/claude-hud` + `/plugin install claude-hud` |
| `commit-commands` | `/commit`, `/commit-push-pr`, `/clean_gone` | `/plugin install commit-commands@claude-plugins-official` |
| `security-guidance` | Passive PreToolUse hook — 9 security patterns | `/plugin install security-guidance@claude-plugins-official` |
| `code-review` | Multi-agent `/code-review` with confidence scoring | `/plugin install code-review@claude-plugins-official` |
| `hookify` | Build custom behavior-prevention hooks | `/plugin install hookify@claude-plugins-official` |
| `ralph-wiggum` | Autonomous iteration loops (`/ralph-loop`) | `/plugin install ralph-wiggum@claude-plugins-official` |

> Linux TMPDIR workaround (if `/plugin install` fails with `EXDEV`):
> ```bash
> mkdir -p ~/.cache/tmp && TMPDIR=~/.cache/tmp claude
> ```

### Built-in Commands (no plugin needed)

Claude Code v2.1.x has many built-in slash commands that match OpenCode features:
`/model`, `/effort`, `/context`, `/usage`, `/mcp`, `/resume`, `/branch`,
`/background`, `/fork`, `/tasks`, `/rewind`, `/diff`, `/focus`, `/compact`,
`/goal`, `/advisor`, `/export`.

## Codex CLI

Codex CLI (OpenAI) configuration lives in `.codex/` (whole-dir symlinked:
`~/.codex` → `configs/.codex`).

- **Config**: `.codex/config.toml` — base settings (`approval_policy`,
  `sandbox_mode`, `model_reasoning_effort`) + MCP servers (rendered by mcp-sync
  into a `# BEGIN/END mcp-sync` sentinel block). No secrets — portable.
- **Instructions**: `.codex/AGENTS.md` — global rules (full parity with the
  OpenCode `AGENTS.md` instruction set).
- **Skills**: `.codex/skills` → `ai/skills/for-tools/codex` (per-agent pool —
  filtered by `ai/skills/skills-policy.json`, same mechanism as the other tools).
- **Model provider**: uses the built-in `openai` provider with **ChatGPT Plus
  OAuth login** (`codex login` → `~/.codex/auth.json`, gitignored). No provider
  table in the committed config — OpenAI natively supports the Responses API.
  To switch to Qiniu later: note that Qiniu lacks `/v1/responses`, so use
  cc-switch's built-in proxy (`:15721`, which translates Responses→Chat).
- **Runtime** (gitignored): `sqlite/` (goals/memories/logs), `codex-lsp/`,
  `process_manager/`, `auth.json`, `cc-switch-model-catalog.json`.
- **cc-switch coexistence**: cc-switch merges `[model_providers.*]` +
  `model`/`model_provider` into `config.toml` via `toml_edit` (non-destructive).
  mcp-sync owns the `[mcp_servers.*]` sentinel block. Both write through the
  `~/.codex` → repo symlink without conflict. Set
  `preserveCodexOfficialAuthOnSwitch: true` in cc-switch settings so switching
  Claude providers doesn't wipe the ChatGPT login.

## DeepSeek Harness (dsh)

DeepSeek Harness (`dsh`, [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness))
is an open-source agent harness ("everything is a plugin", Cordis-based,
developer preview).

- **Config**: `dsh/settings.yaml` — symlinked as `~/.dsh/settings.yaml`
  (`$DSH_HOME` defaults to `~/.dsh`; dsh watches the file and hot-publishes
  edits). LLM routes are declared under `llm-pi-ai.providers.*` with
  `apiKeyEnv:` env refs — **no secrets in the repo**.
- **Credentials**: `~/.dsh/.credentials.yaml` (write-only key store) and
  `~/.dsh/profiles/` (installed web profile + node_modules) stay machine-local.
- **Run**: `npx @deepseek-ai/dsh web` → http://127.0.0.1:3080 (Settings → Models).
- **Providers configured**: `qiniu` (Qiniu AI gateway,
  `api.qnaigc.com/v1`, OpenAI-compatible, `QINIU_AI_API_KEY`) and `deepseek`
  (official, `DEEPSEEK_API_KEY`). Model IDs verified against the live catalog.

## Pi Coding Agent

Pi ([earendil-works/pi](https://github.com/earendil-works/pi),
terminal coding agent) configuration lives in `pi/` — **file-level links**
into `~/.pi/agent/` (runtime: `sessions/`, `auth.json`, `trust.json`,
`npm/` stay machine-local).

| Repo file | Home link | Purpose |
|---|---|---|
| `pi/settings.json` | `~/.pi/agent/settings.json` | Global settings: default model, thinking, theme, skills dir |
| `pi/AGENTS.md` | `~/.pi/agent/AGENTS.md` | Global instructions (English Check, secret hygiene, obsidian CLI, git) |
| `pi/models.json` | `~/.pi/agent/models.json` | Custom provider `qiniu` (`$QINIU_AI_API_KEY`, OpenAI-compat) |
| `pi/skills` | `~/.pi/agent/skills` | Skill pool (`for-tools/pi`, generated by `link-skills.sh`) |

Built-in providers (`deepseek` ← `DEEPSEEK_API_KEY`, `openrouter` ←
`OPENROUTER_API_KEY`, etc.) need no config. `pi/settings.json` wires the
skill pool via `"skills": ["~/.shanaae/configs/pi/skills"]`.

## User Rules

Rules are stored in `ai/user_rules/` and symlinked to tool directories.

### English Learning

- Always answer the real question in English **first**; the coaching block goes at the **end** of the response
- On every message, **append** an **English Check** block: (A) correct/optimize my question, (B) nudge me to English if I used Chinese, (C) vocabulary above CET-6 — **always shown, never skipped**, (D) a one-point **grammar spotlight** — always shown
- Annotate long/difficult sentences in Chinese
- For deep language work (essay grading, grammar deep-dives, IELTS/TOEFL mock), dispatch the `english-tutor` subagent
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
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_KEY` |

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
.claude/skills -> ../ai/skills/for-tools/claude

# Trae
.trae/skills -> ../ai/skills/for-tools/trae
.trae/user_rules -> ../ai/user_rules

# OpenCode
.config/opencode/skills -> ../../ai/skills/for-tools/opencode

# Agents CLI
.agents/skills -> ../ai/skills/vendor

# Claude Code Router (whole dir, including config.json)
~/.claude-code-router -> configs/.claude-code-router
~/.claude-code-router/config.json -> configs/.claude-code-router/config.json

# Codex CLI (whole dir — runtime subdirs gitignored)
~/.codex -> configs/.codex

# DeepSeek Harness (file-level — runtime stays in ~/.dsh)
~/.dsh/settings.yaml -> configs/dsh/settings.yaml

# Pi (file-level — runtime sessions/auth stay in ~/.pi/agent)
~/.pi/agent/settings.json -> configs/pi/settings.json
~/.pi/agent/AGENTS.md -> configs/pi/AGENTS.md
~/.pi/agent/models.json -> configs/pi/models.json
~/.pi/agent/skills -> configs/pi/skills
```

## Troubleshooting

### Skills not appearing

```bash
# Re-link pools (for-tools/ is gitignored — empty until this runs)
bash ai/skills/link-skills.sh

# Preview policy effects without touching anything
bash ai/skills/link-skills.sh --dry-run

# Verify symlinks per agent
ls -la ai/skills/for-tools/opencode/
```

If a skill is missing from one tool only, check its entry in
`ai/skills/skills-policy.json` (include/exclude patterns) — the pool for that
agent is filtered per policy.

### MCP server not connecting

1. Check if `npx`/`uvx` is available
2. Verify API keys in `.secrets`
3. Run setup-configs to regenerate config files

### Configuration drift

1. Run `python3 ai/skills/local/mcp-sync/scripts/sync_mcp.py --dry-run` to see
   which MCP targets have drifted from the canonical (`mcp_servers.json`).
2. If intentional, edit `mcp_servers.json` then `--apply` (regenerates all MCP
   targets consistently).
3. For Trae-only drift, compare `ai/mcp/trae.json` with `.claude/mcp.json` and
   re-run `python3 ai/skills/local/setup-configs/scripts/setup_configs.py`.
