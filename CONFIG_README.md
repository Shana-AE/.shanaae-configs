# Configuration Setup Guide

This project uses sensitive configuration files that are excluded from version
control. Some ship as `.example` templates with placeholders; others use
**runtime environment-variable substitution** (no rendering needed).

## Required Configuration Files

| File                          | How it's produced                                         |
| ----------------------------- | --------------------------------------------------------- |
| `ai/mcp/trae.json`              | Rendered from `ai/mcp/trae.json.example` by `setup_configs.py` |
| `.config/opencode/opencode.jsonc` | **Live file** — uses `{env:VAR}` substitution at read time; no `.example` |
| `.claude/mcp.json`              | Live file — uses `$VAR` substitution where supported        |
| `.codex/config.toml`            | Live file — MCP servers rendered by `sync_mcp.py`; uses env-name refs (`env_vars`, `bearer_token_env_var`); no secrets |
| `.secrets`                      | Manual — holds all tokens + per-OS paths (gitignored)       |

## Required Secrets

Create a `.secrets` file in the **repo root** (this directory). It is a plain
`KEY=value` file (an `export` prefix is tolerated).

Only one config is still rendered from a `.example` template — `ai/mcp/trae.json`
(from `ai/mcp/trae.json.example`) — which uses this placeholder:

| Placeholder in `trae.json.example` | Key in `.secrets`   | Description                          |
| ---------------------------------- | ------------------- | ------------------------------------ |
| `YOUR_GITHUB_TOKEN`                  | `GITHUB_TOKEN_MCP`    | GitHub PAT for the GitHub MCP.       |

All other secrets are read directly from `.secrets` / the environment at runtime
(via OpenCode `{env:VAR}`, the router `$VAR`, or skills via curl):

| Key                    | Used by                                                            |
| ---------------------- | ------------------------------------------------------------------ |
| `QINIU_AI_API_KEY`       | Qiniu AI provider (router + OpenCode)                              |
| `BIGMODEL_API_KEY`       | Zhipu / BigModel (router + OpenCode + Zhipu hosted MCPs)           |
| `DEEPSEEK_API_KEY`       | DeepSeek provider (router)                                         |
| `OPENROUTER_API_KEY`     | OpenRouter provider (router)                                       |
| `SILICONFLOW_API_KEY`    | SiliconFlow provider (router)                                      |
| `CCR_API_KEY`            | Claude Code Router authentication                                  |
| `CONTEXT7_API_KEY`       | `context7` skill (curl API — higher rate limit)                    |
| `EUDIC_TOKEN`            | `eudic-manager` skill                                              |
| `MAIMEMO_TOKEN`          | MaiMemo skills                                                     |
| `MINIMAX_*`              | MiniMax MCPs (if enabled)                                          |

> **Cross-platform note:** the design spec also moves OS-specific *paths*
> (`PROJECTS_DIR`, `MINIMAX_OUTPUT_DIR`, `OBSIDIAN_VAULT_DIR`) into `.secrets`
> so one config resolves per-OS. See
> [`docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md`](docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md).

## Customizing Agent Models

Subagents ship with a default model but every user can override it. The
`image-op` agent (`.config/opencode/agents/image-op.md`) defaults to
`qiniu/qwen/qwen3.6-plus`. To run it on your own model/provider:

1. **Per-project override (recommended).** Copy the agent into your project and
   change the `model:` line in its frontmatter. Project agents
   (`.opencode/agents/`) override the global ones
   (`~/.config/opencode/agents/`):

   ```bash
   mkdir -p .opencode/agents
   cp ~/.config/opencode/agents/image-op.md .opencode/agents/image-op.md
   # edit .opencode/agents/image-op.md → model: your-provider/your-model
   ```

2. **JSON config override.** Add an `agent` entry to your `opencode.jsonc`:

   ```jsonc
   {
     "agent": {
       "image-op": { "model": "provider/model-id" }
     }
   }
   ```

   `{env:VAR}` is substituted here (e.g. `"model": "{env:IMAGE_OP_MODEL}"`),
   but if the variable is unset it becomes an empty string and the agent will
   fail to load — set it, or use a literal model ID.

> **Vision requirement:** whatever model you pick must accept image input
> (`attachment`/vision). `image-op`'s core job is visual analysis — a text-only
> model will not work.

> **`image-op-pro` (optional):** a hidden subagent variant that uses
> `qiniu/google/gemini-3.6-flash` for dense OCR / chart / pixel-level
> verification, self-dispatched by `image-op`. It requires the `qiniu` provider
> and a vision-capable Gemini model. If you don't need it, delete
> `.config/opencode/agents/image-op-pro.md` — `image-op` then handles everything
> with its own model.

> Markdown agent frontmatter (`agents/*.md`) does **not** support `{env:VAR}`
> substitution — that only applies to `opencode.jsonc` values.

## Automatic Setup

The `setup-configs` skill renders the `.example` files from your `.secrets`.

```bash
# Via the Trae skill
trae run setup-configs

# Or directly
python3 ai/skills/local/setup-configs/scripts/setup_configs.py
```

## Manual Setup

1. Create `.secrets` in the repo root with the keys above.
2. Render the templated configs:
   ```bash
   python3 ai/skills/local/setup-configs/scripts/setup_configs.py
   ```
3. OpenCode/Claude configs need no rendering — they read `{env:VAR}`/`$VAR`
   directly, so just ensure the variables are exported in your shell
   (or sourced from `.secrets`).
