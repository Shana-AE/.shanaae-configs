---
name: get-secret-token
description: Import keys from `.secrets` to environment variables and convert tokens for other tools/agents. Use this when you need to authenticate with external services (OpenAI, GitHub, Eudic, etc.).
---

# Get Secret Token

This skill helps you manage and use secret tokens stored in `/home/shanaae/.shanaae/configs/.secrets`. It instructs the agent to load these secrets into the environment and map them to the variable names required by other tools or agents.

## Workflow

1. **Read Secrets**:
    The agent should first read the secrets file to identify available keys:
    `/home/shanaae/.shanaae/configs/.secrets`

2. **Import to Environment**:
    For any key needed in the current session, the agent must run the `export` command in the terminal.

    *Example:*

    ```bash
    export MY_TOKEN='value_from_file'
    ```

3. **Token Conversion / Mapping**:
    Different tools require different environment variable names. Use the mapping table below to convert the stored keys (left) to the target environment variables (right) required by specific tools.

    | Service / Tool | Stored Key in `.secrets` | Target Environment Variable / Argument |
    | :--- | :--- | :--- |
    | **OpenAI** | `OPENAI_API_KEY_OPENAPI` (default)<br>`OPENAI_API_KEY_OBSIDIAN`<br>`OPENAI_API_KEY_3` | `OPENAI_API_KEY` |
    | **GitHub** | `GITHUB_TOKEN_MCP` (preferred for MCP)<br>`GITHUB_TOKEN_REFINED` | `GITHUB_TOKEN`<br>`GITHUB_PAT` |
    | **Eudic** | `EUDIC_TOKEN` | `EUDIC_TOKEN` |
    | **DeepSeek** | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_KEY` |
    | **Cloudflare** | `CLOUDFLARE_DNS_TOKEN` | `CLOUDFLARE_API_TOKEN` |
    | **ModelScope** | `MODELSCOPE_API_KEY_OPENCODE` | `MODELSCOPE_API_TOKEN` |
    | **TickTick** | `TICKTICK_CLIENT_ID`<br>`TICKTICK_CLIENT_SECRET` | `TICKTICK_CLIENT_ID`<br>`TICKTICK_CLIENT_SECRET` |
    | **SiliconFlow** | `SILICONFLOW_API_KEY` | `SILICONFLOW_API_KEY` |
    | **Travily** | `TRAVILY_RECOVER_CODE` | `TRAVILY_API_KEY` (if applicable) |
    | **Context7** | `CONTEXT7_API_KEY` | `CONTEXT7_API_KEY` |

4. **Usage Instructions**:
    - When a user asks to use a tool (e.g., "Use Eudic to save this word"), check if `EUDIC_TOKEN` is set.
    - If not, read `.secrets`, find `EUDIC_TOKEN`, and run `export EUDIC_TOKEN='...'`.
    - If a tool fails due to authentication, verify if the correct environment variable is exported.

## Notes

- Always use `export VAR='VALUE'` with single quotes to avoid issues with special characters (like spaces or symbols in the token).
- If multiple keys exist for the same service (e.g., OpenAI), ask the user for clarification or default to the most general one (e.g., `_OPENAPI` or `_MCP`).
