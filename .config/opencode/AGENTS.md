# OpenCode Global Rules

## English Practice

Full rules live in `rules/english-learning.md` (loaded via `instructions`).
Summary: answer in English; on every message prepend an **English Check** block that (A) corrects/optimizes my question, (B) nudges me to use English if I wrote Chinese, and (C) lists vocabulary above CET-6; annotate long/uncommon sentences in Chinese.

## Git Pull for Context

When you need to better understand a library, tool, or framework to assist the user:

1. **Clone the Repository**: You are encouraged to pull the corresponding git repository to `~/.ai-git-pulls`.
2. **Analyze Source Code**: Read the source code, README, and documentation in the cloned repository to gain a deeper understanding of its functionality, API, and usage patterns.
3. **Use Context**: Apply the knowledge gained from the source code to the user's task.

## Learning and Study

- Explain the thought process of the problem 解释一下解题思路
- Highlight the key concepts and ideas 突出重点概念和思想
- List the key concepts and ideas 列出重点概念和思想
- Ask me whether to save the list to obsidian 询问我是否把这个清单保存到obsidian

## Save to Eudic

When the user asks to save words to Eudic (欧路词典):

1. **Identify Words**: Extract the list of English words to be saved from the context.
2. **Check Token**: Verify if `EUDIC_TOKEN` is set in the environment.
    - If not, ask the user to provide it or set it via `export EUDIC_TOKEN='...'`.
    - Tell the user they can get the token from: <https://my.eudic.net/OpenAPI/Authorization>

## Obsidian Vault Location

The Obsidian vault lives on the **Windows** side. Always operate on it there — never in a WSL-local copy.

- **Windows path**: `E:\Users\shana\Documents\Obsidian Vault\obsidian-vault`
- **WSL access**: `/mnt/e/Users/shana/Documents/Obsidian Vault/obsidian-vault`
- **Symlink** ( convenience ): `/home/shanaae/documents/obsidian-vault` → the Windows vault above. Use it as the default working path.
- Structure follows **I.A.R.P**: `Inbox/` (capture), `Area/` (life + work), `Resource/` (topics: web, rust, devops, english, cs, records, tools, glossary, others), `Project/` (bounded outcomes), `Recycle/` (trash).
- Git remote: `git@github.com:Shana-AE/obsidian-vault.git` (note: `core.ignorecase=true`; for case-only folder renames use a two-step `git mv`).

## Obsidian Writes — Always Use the CLI

The **Livesync** plugin syncs Obsidian's *in-memory* vault state, not raw disk. Any change made directly to vault files on disk (by opencode or otherwise) is **not detected**, so it gets **overwritten** by the older copy arriving from other devices.

- **All writes** to the vault — creating, editing, or deleting notes; changing properties/frontmatter; installing, enabling, disabling, or uninstalling plugins — **MUST** go through the `obsidian` CLI (local REST API → Obsidian → Livesync).
- **Never** edit vault files directly via the filesystem, even though the symlink path exists. On-disk config such as `community-plugins.json` is frequently stale relative to the live app state.
- **Reads** may use either the CLI or the filesystem for quick inspection, but prefer the CLI for accuracy.
- See the `obsidian-cli` skill for commands: `read`, `create`, `append`, `delete`, `move`, `property:set`, `plugin:enable`/`disable`/`uninstall`, `search`, etc.

## Save to Obsidian

- If save to obsidian save file under `/Inbox/ai-skills` (relative to the vault root above) 如果保存到obsidian，保存在 /Inbox/ai-skills

## MCP Tools Usage

- Use the **context7 skill** (curl to context7.com API with `CONTEXT7_API_KEY`) when you need to search documentation — the MCP was removed to save per-message tokens
- Use `Git` tools for git operations
- Use `Filesystem` tools for file operations
- Use `Sequential Thinking` tools for complex problem solving
