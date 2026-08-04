---
name: get-secret-token
description: Import keys from `.secrets` to environment variables and convert tokens for other tools/agents. Use this when you need to authenticate with external services (OpenAI, GitHub, Eudic, etc.).
---

# Get Secret Token

This skill loads secrets from `~/.shanaae/configs/.secrets` and `~/.shanaae/configs/.secrets.d/` into the environment **without ever printing their values**. Never paste or echo a secret value — the value would be recorded in the session transcript.

## Workflow

1. **List available keys (never read values)**:
    - `awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' ~/.shanaae/configs/.secrets` — key names only from the key=value file
    - or `ls ~/.shanaae/configs/.secrets.d/` — one lowercase file per key

2. **Load into the environment silently** (never `export VAR='value'` — the literal value is recorded as the command's tool argument):

    Load everything at once:
    ```bash
    set -a; source ~/.shanaae/configs/.secrets; set +a
    ```

    Or load a single key from its `.secrets.d` file (the value never appears in the command text):
    ```bash
    export EUDIC_TOKEN="$(cat ~/.shanaae/configs/.secrets.d/eudic_token)"
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
    - When a user asks to use a tool (e.g., "Use Eudic to save this word"), check if the variable is set: `test -n "$EUDIC_TOKEN" && echo set || echo missing`.
    - If not set, load it as in step 2, then reference `$EUDIC_TOKEN` in commands.
    - If a tool fails due to authentication, verify the variable is exported with `test -n "$VAR"` — never print its value.

## Hard Rules (never violate)

- **Never print a secret value**: no `echo $VAR`, no `env`, no `cat ~/.shanaae/configs/.secrets` or `cat ~/.shanaae/configs/.secrets.d/*`, no `curl -v` (verbose prints the `Authorization` header — use `-sS`).
- **Never put a literal secret in a prompt, config file, agent file, or command-line argument** (argv is visible to every user via `/proc/<pid>/cmdline`). Use `$VAR` references — shell expansion happens at runtime, after the command text is recorded.
- **Never paste a user-provided secret into chat text**. Ask the user to write it into the secrets file in their own terminal, then reference the variable.
- **Subagents inherit the environment** — source once, and downstream agents can use the variables without re-reading anything.

## Notes

- Use `set -a; source ...` or `"$(cat ...)"` inside double quotes to avoid issues with special characters (spaces or symbols in tokens).
- If multiple keys exist for the same service (e.g., OpenAI), ask the user for clarification or default to the most general one (e.g., `_OPENAPI` or `_MCP`).
