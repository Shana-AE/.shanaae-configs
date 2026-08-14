# Cursor Global Instructions (~/.cursor, Windows: %USERPROFILE%\.cursor)

Global rules for Cursor sessions across all projects. Project-level
`.cursor/rules/*.mdc` files layer on top of this file. Canonical full rules:
`~/.shanaae/configs/AGENTS.md` (source of truth — keep this file in sync).

## English Practice

Answer the real question in English **first**. At the **end** of every reply,
append an **English Check** block: (A) correct/optimize the user's English,
(B) nudge to English if the user wrote Chinese, (C) list vocabulary above
CET-6 — always shown, (D) one-point grammar spotlight — always shown.
Annotate long/difficult sentences in Chinese. Full rule:
`~/.shanaae/configs/ai/user_rules/english-learning.md`.

## Secret Hygiene

Never put a literal secret in chat, prompts, configs, commands, or commits.
Load secrets via `source ~/.shanaae/configs/.secrets` (never echo the file).
Never print `$VAR` values. If a secret leaks, tell the user to rotate it.

## Obsidian

The vault syncs via the Livesync plugin (in-memory state), so **all vault
writes MUST go through the `obsidian` CLI** (local REST API), never direct
file edits. Save AI/skill notes under `/Inbox/ai-skills/<category>/` and
categorize them. Never edit vault files directly.

## Git

Only commit/push/PR when explicitly asked. Check `git status`/`git diff`
first, stage only intended files, never commit secrets, and use the repo's
conventional-commit style (`feat(scope): ...`).

## Skills

Cursor loads skills from `~/.cursor/skills` (WSL → the `cursor` pool generated
by `link-skills.sh`; Windows → the same pool copy-synced by
`sync_cursor_qoder.py`). Note: main-agent skill visibility in Cursor is
global — there is no per-subagent gating. Lint/typecheck a project with its
own tooling before claiming completion.