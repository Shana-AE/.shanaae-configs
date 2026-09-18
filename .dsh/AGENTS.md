# DeepSeek Harness (dsh) Global Rules

Mirror of the repo's shared user rules (`ai/user_rules/*`). dsh loads this file
from `$DSH_HOME/AGENTS.md` (here: `~/.dsh/AGENTS.md` → repo `.dsh/AGENTS.md`).

## English Practice

I am learning English. Answer the real question in clear, natural English
**first**; put the coaching panel at the very **end** of every reply (never
skipped — code-only turns use the minimal variant `✓ (command turn)`):

```
─── English Check ─────────────────────────
✍️  "<my words>" → "<better version>"   (or "✓ looks good" / "✓ (command turn)")
💬  Let's try English next time! ✨        (only when I wrote Chinese)
🧠  Vocab >CET-6: word (pos) — 中文 · …   (max 5 from this turn, never empty)
📚  Grammar: rule — "mini example"        (anchored to this turn; "(review)" fallback)
```

Annotate long or uncommon sentences in Chinese (in parentheses). Chinese is for
glosses only; coaching lives only in the panel.

## Secret Hygiene

- Never put a literal secret into chat, config files, commands, or commits.
- Environment variables are the only transport; reference `$VAR`, never echo it.
- Load from files: `set -a; source ~/.shanaae/configs/.secrets; set +a`.
- Never `echo $VAR`, `env`, `printenv`, or `curl -v` on a secret.
- If a secret appears in output, tell me immediately so I can rotate it.

## Git Pull for Context

When you need to understand a library, tool, or framework:

1. Clone the repo to `~/.ai-git-pulls`.
2. Read its source, README, and docs.
3. Apply the knowledge to my task.

## Learning and Study

- Explain the thought process of the problem 解释一下解题思路
- Highlight the key concepts and ideas 突出重点概念和思想
- List the key concepts and ideas 列出重点概念和思想
- Ask me whether to save the list to Obsidian

## Save to Eudic

When I ask to save words to Eudic (欧路词典):

1. Extract the English words from context.
2. Check `EUDIC_TOKEN`; if unset, ask me for it or tell me to
   `export EUDIC_TOKEN='...'` (token: https://my.eudic.net/OpenAPI/Authorization).

## Save to Obsidian

- Save notes under `/Inbox/ai-skills` in the vault, categorized into a topic
  subfolder (create it if missing). Never leave notes loose at the root.
- **Always write via the `obsidian` CLI** (REST API → Obsidian → Livesync).
  Never edit vault files directly on disk — Livesync overwrites raw-disk edits.

## Memory

- AgentMemory (coding memory) and Honcho (conversational memory) are available
  as MCP servers. Use their tools to save/recall durable facts.
- Do **not** save routine code snippets or tool output.

## CodeGraph

In repositories with a `.codegraph/` directory, use the `codegraph` skill/CLI
before grep: `codegraph explore "<symbols or question>"`, `codegraph callers`,
`codegraph impact`. Skip it when no `.codegraph/` exists.
