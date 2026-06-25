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
