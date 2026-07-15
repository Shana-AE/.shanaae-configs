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
- **Always categorize into the appropriate subfolder** based on the note's topic. Create the subfolder via `obsidian create path="Inbox/ai-skills/<category>/.folder"` first if it doesn't exist.
- 保存到 ai-skills 时，**必须按主题归类到对应子文件夹**，不要散落在根目录

### Category Map

| Subfolder         | Save when the note is about…                                              |
| ----------------- | ------------------------------------------------------------------------ |
| `frontend/`       | CSS, HTML, JS/DOM APIs, Vue/React, browser behavior, third-party frontend SDKs |
| `tooling/`        | Build tools (Vite, webpack), package managers (pnpm, npm), bundlers, CI    |
| `shell/`          | Shell scripting, env vars, Linux/WSL, terminal tools                      |
| `debugging/`      | Bug investigation writeups, root-cause analysis, postmortems              |
| `finance/`        | Insurance, pension, investment, personal financial planning               |
| `english-learning/` | English vocabulary, grammar, study notes (existing)                     |
| `2026-01/`        | Archive (legacy notes, don't add new files here)                           |

If a note doesn't fit any existing category, **create a new subfolder** with a sensible short name (e.g. `database/`, `security/`, `networking/`) via `obsidian create path="Inbox/ai-skills/<new-category>/.folder"`, save the note there, then add the new category to the table above and **flag it to the user** so they can rename or merge it later. Never leave notes loose at the `ai-skills/` root.

## AgentMemory — Persistent Cross-Session Memory

AgentMemory is deployed on the NAS (`192.168.86.62:3111`) via Docker. It captures coding session events automatically via the `agentmemory-capture.ts` plugin (22 hooks). The MCP server (`@agentmemory/mcp`) provides 53 tools for structured memory operations.

- **Server**: `http://192.168.86.62:3111` (env: `AGENTMEMORY_URL`)
- **Secret**: env: `AGENTMEMORY_SECRET` (required for all API calls)
- **Viewer**: `http://localhost:3113` via SSH tunnel: `ssh -L 3113:127.0.0.1:3113 -L 3112:127.0.0.1:3112 nas-fnos`
- **No LLM provider**: compression/summarization disabled; raw observations + structured memories only

### When to Proactively Save to AgentMemory

Use `memory_save` (or `/remember`) when encountering:

| Trigger | Type | Example |
|---------|------|---------|
| Business requirements | `fact` | "Company X needs invoice export in PDF format" |
| Domain knowledge | `fact` | "The regulatory framework requires quarterly compliance reports" |
| Architecture decisions | `architecture` | "Chose Honcho for conversational memory, AgentMemory for coding memory" |
| Project constraints | `fact` | "Must support WSL2 + macOS + Windows clients" |
| Workflow patterns | `workflow` | "Deploy Docker services to NAS at /vol1/1000/docker/" |
| Bug insights | `bug` | "iii-exec watcher fails if src/ dir doesn't exist in Docker image" |
| User preferences | `preference` | "User prefers Chinese annotations for difficult English" |

**Do NOT save**: routine code snippets, tool outputs, file reads — these are captured automatically by the plugin hooks.

### How to Recall

- Use `memory_smart_search` (or `/recall`) for hybrid semantic+keyword search
- Use `memory_recall` for keyword-based search
- Use `memory_file_history` before editing a file to check past context
- Use `memory_sessions` to list past sessions

## MCP Tools Usage

- Use the **context7 skill** (curl to context7.com API with `CONTEXT7_API_KEY`) when you need to search documentation — the MCP was removed to save per-message tokens
- Use `Git` tools for git operations
- Use `Filesystem` tools for file operations
- Use `Sequential Thinking` tools for complex problem solving

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code. CodeGraph is wired here as the **`codegraph` skill** (CLI-based), not an always-on MCP — invoke the skill for the workflow:

- `codegraph explore "<symbol names or question>"` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Run `codegraph sync` first if the repo changed since last session.
- Also: `codegraph node <symbol>` (source + caller/callee trail), `codegraph callers|callees|impact <symbol>`, `codegraph affected [files]` (test impact).

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision (`codegraph init` to start). In projects where oh-my-openagent (omo) is enabled, omo may additionally serve the `codegraph` MCP at runtime; either path works.
<!-- CODEGRAPH_END -->
