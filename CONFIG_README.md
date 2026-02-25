# Configuration Setup Guide

This project uses sensitive configuration files that are excluded from version control. Example files with placeholders are provided to help you set up your environment.

## Required Configuration Files

The following files need to be created from their `.example` counterparts:

1.  `ai/mcp/trae.json` (from `ai/mcp/trae.json.example`)
2.  `.config/opencode/opencode.json` (from `.config/opencode/opencode.json.example`)

## Required Secrets

To generate these files, you need a `.secrets` file in the root directory (`/home/shanaae/.shanaae/configs/.secrets`). This file should contain the following environment variables:

| Placeholder in .example | Key in .secrets | Description |
| :--- | :--- | :--- |
| `YOUR_FIGMA_API_KEY` | `FIGMA_ACCESS_TOKEN` | Figma Personal Access Token for the Figma MCP. |
| `YOUR_CONTEXT7_API_KEY` | `CONTEXT7_API_KEY` | API Key for Context7 service. |
| `YOUR_EUDIC_AUTH_TOKEN` | `EUDIC_TOKEN` | Authorization token for Eudic (欧路词典). |
| `YOUR_GITHUB_TOKEN` | `GITHUB_TOKEN_MCP` | GitHub Personal Access Token (PAT) for GitHub MCP. |
| `YOUR_OBSIDIAN_API_KEY` | `OBSIDIAN_API_KEY` | Local REST API Key for Obsidian. |
| `YOUR_Z_AI_API_KEY` | `BIGMODEL_API_KEY` | API Key for Zhipu AI / BigModel (used for Z_AI and Web Search). |
| `YOUR_ZHIPU_API_KEY` | `BIGMODEL_API_KEY` | Same as above, used for Zhipu Coding Plan. |
| `YOUR_QINIU_API_KEY` | `QINIU_AI_API_KEY` | API Key for Qiniu AI services. |

## Automatic Setup

A skill `setup-configs` is provided to automatically generate the configuration files from your `.secrets` file.

**Usage:**

```bash
# Run the setup skill
trae run setup-configs
```

Or manually run the script if you are in the terminal:

```bash
python3 ai/skills/local/setup-configs/scripts/setup_configs.py
```

## Manual Setup

If you prefer to set up manually:

1.  Copy `ai/mcp/trae.json.example` to `ai/mcp/trae.json`.
2.  Copy `.config/opencode/opencode.json.example` to `.config/opencode/opencode.json`.
3.  Replace all placeholders (e.g., `YOUR_API_KEY`) with your actual secrets.
