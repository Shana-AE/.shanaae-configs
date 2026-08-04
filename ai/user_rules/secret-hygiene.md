# Secret Hygiene / 凭据保密纪律

Hard rules for handling credentials (tokens, usernames, passwords) in agent sessions. Never let a secret value appear in any recorded text.

## Core rules

1. **Never put a literal secret in anything that gets recorded**: chat messages, prompts, config files, agent/skill files, shell commands, tool arguments, git commits.
2. **Environment variables are the only transport**: `$VAR` references in commands are safe — shell expansion happens at runtime, *after* the command text is recorded.
3. **Load from files, never echo**:
   - Whole file: `set -a; source ~/.shanaae/configs/.secrets; set +a`
   - Single key: `export VAR="$(cat ~/.shanaae/configs/.secrets.d/var)"`
   - NEVER `export VAR='literal'` and never `cat` the secrets file into output.
4. **Never print a value**: no `echo $VAR`, no `env`, no `printenv`, no `curl -v` (verbose prints the `Authorization` header — use `-sS`).
5. **argv is visible to all users** (`/proc/<pid>/cmdline`): never pass a literal secret as a command-line argument; read it from the environment *inside* the command.
6. **Subagents inherit the environment**: source once; downstream agents use the variables without re-reading anything.
7. **If the user pastes a secret into chat**, tell them it must be treated as compromised and rotated; load it via the secrets file instead.
8. **Never write secrets into project files, logs, or the Obsidian vault.**

## Escalation

If you see a secret value in a tool output, session file, or log, tell the user immediately so they can rotate it.
