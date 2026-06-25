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
`KEY=value` file (an `export` prefix is tolerated). It must contain:

| Placeholder in `.example` | Key in `.secrets`      | Description                                                  |
| ------------------------- | ---------------------- | ------------------------------------------------------------ |
| `YOUR_FIGMA_API_KEY`        | `FIGMA_ACCESS_TOKEN`     | Figma Personal Access Token for the Figma MCP.               |
| `YOUR_CONTEXT7_API_KEY`     | `CONTEXT7_API_KEY`       | API Key for Context7 service.                                |
| `YOUR_EUDIC_AUTH_TOKEN`     | `EUDIC_TOKEN`            | Authorization token for Eudic (欧路词典).                      |
| `YOUR_GITHUB_TOKEN`         | `GITHUB_TOKEN_MCP`       | GitHub PAT for the GitHub MCP.                               |
| `YOUR_OBSIDIAN_API_KEY`     | `OBSIDIAN_API_KEY`       | Local REST API Key for Obsidian.                             |
| `YOUR_Z_AI_API_KEY`         | `BIGMODEL_API_KEY`       | API Key for Zhipu AI / BigModel (Z_AI + Web Search).         |
| `YOUR_ZHIPU_API_KEY`        | `BIGMODEL_API_KEY`       | Same key, used for the Zhipu Coding Plan provider.           |
| `YOUR_QINIU_API_KEY`        | `QINIU_AI_API_KEY`       | API Key for Qiniu AI services.                               |

Additional keys read directly from the environment by OpenCode / the router
(not via `.example` placeholders): `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`,
`SILICONFLOW_API_KEY`, `CCR_API_KEY`, `MAIMEMO_TOKEN`, `MINIMAX_*`, etc.

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
