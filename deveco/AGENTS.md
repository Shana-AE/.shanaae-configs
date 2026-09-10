# DevEco Code Global Rules (Windows)

Curated port of the WSL opencode rules. Source of truth: `~/.shanaae/configs/deveco/`
(synced by `shell/sync-deveco.zsh`). DevEco Code is an OpenCode fork — most opencode
conventions apply; HarmonyOS-specific notes at the bottom.

## English Practice

Full rules live in `user_rules/english-learning.md` (loaded via `instructions`).
Summary: answer the real question in English **first**; at the very END of **every** reply append the panel below (never skipped — code-only turns use a minimal variant with `✓ (command turn)`):

```
─── English Check ─────────────────────────
✍️  "<my words>" → "<better version>"   (or "✓ looks good" / "✓ (command turn)")
💬  Let's try English next time! ✨        (only when I wrote Chinese)
🧠  Vocab >CET-6: word (pos) — 中文 · …   (max 5 from this turn, never empty)
📚  Grammar: rule — "mini example"        (anchored to this turn; "(review)" fallback)
```

Annotate long/difficult sentences in Chinese. For deep language work (essay grading, grammar deep-dives, IELTS/TOEFL mock), dispatch the `english-tutor` subagent.

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
    - If not, ask the user to provide it or set it.
    - Tell the user they can get the token from: <https://my.eudic.net/OpenAPI/Authorization>

## Obsidian Vault Location

The Obsidian vault is **bidirectionally synced across all devices** (Windows, macOS, others) via the Livesync plugin. Each platform has its own local mount; writes propagate through CouchDB replication, not direct file sync.

- **Windows path (this machine)**: `E:\Users\shana\Documents\Obsidian Vault\obsidian-vault`
- macOS path: `~/Developer/obsidian-vault/` (other machines)
- Structure follows **I.A.R.P**: `Inbox/` (capture), `Area/` (life + work), `Resource/` (topics), `Project/` (bounded outcomes), `Recycle/` (trash).
- Git remote: `git@github.com:Shana-AE/obsidian-vault.git` (note: `core.ignorecase=true`; for case-only folder renames use a two-step `git mv`).

## Obsidian Writes — Always Use the CLI

The **Livesync** plugin syncs Obsidian's *in-memory* vault state, not raw disk. Any change made directly to vault files on disk is **not detected**, so it gets **overwritten** by the older copy arriving from other devices.

- **All writes** to the vault — creating, editing, or deleting notes — **MUST** go through the `obsidian` CLI (local REST API → Obsidian → Livesync), never by editing files under `E:\...\obsidian-vault` directly.
- **Reads** may use either the CLI or the filesystem for quick inspection, but prefer the CLI for accuracy.

## Save to Obsidian

- If save to obsidian, save under `Inbox/ai-skills` (relative to the vault root) 如果保存到obsidian，保存在 /Inbox/ai-skills
- **Always categorize into the appropriate subfolder** based on the note's topic (frontend / tooling / shell / debugging / finance / english-learning; create a new one if nothing fits and flag it to the user).
- 保存到 ai-skills 时，**必须按主题归类到对应子文件夹**，不要散落在根目录

## AgentMemory — Persistent Cross-Session Memory

AgentMemory is deployed on the NAS (`192.168.86.62:3111`) via Docker. The `agentmemory-capture.ts` plugin (in this config dir) captures session events automatically — it only needs the `AGENTMEMORY_URL` / `AGENTMEMORY_SECRET` env vars (set as Windows user env vars).

- **Server**: `http://192.168.86.62:3111` (env: `AGENTMEMORY_URL`)
- **Secret**: env: `AGENTMEMORY_SECRET` (required for all API calls)
- **Viewer**: `http://192.168.86.62:3113` (LAN-direct; the viewer UI prompts for the bearer token)
- **Recall**: the AgentMemory MCP is NOT configured on deveco yet — use the viewer URL for browsing past sessions; ask the user if they want the MCP added.
- **When to proactively save**: business requirements / domain knowledge / architecture decisions / project constraints (`fact`, `architecture`, `workflow`, `bug`, `preference`). **Do NOT save** routine code snippets, tool outputs, file reads — captured automatically by the plugin hooks.

## Honcho (self-hosted) — Conversational Memory

Honcho provides **conversational memory** (user profile, dialectic context). Division of labor: **Honcho = conversational/user-profile; AgentMemory = structured coding facts.** The `@honcho-ai/opencode-honcho` plugin is enabled and resolves `HONCHO_URL` / `HONCHO_API_KEY` from env.

- **Server**: `http://192.168.86.62:18000` (v3 API at `/v3`)
- **Viewer**: `http://192.168.86.62:41800` (OpenConcho web UI, LAN-direct)

## DevEco Code (this tool) — HarmonyOS Specifics

- DevEco Code is an **OpenCode fork** by Huawei: same config schema (`$schema: https://opencode.ai/config.json`), same Skill / MCP / Plugin system.
- Built-in agents: `Build` (default), `Plan`, `Goal` (SDD 5-phase; writes `.specs/` in the project).
- Built-in HarmonyOS tools: `build_project`, `start_app`, `hdc_log`, `verify_ui`, `arkts_check`, `switch_cwd`. Built-in skills: `arkts-grammar-standards`, `arkts-error-fixes`, `deveco-create-project`, `arkts-runtime-fix`.
- `DEVECO_HOME` env var points at DevEco Studio (`C:\Program Files\Huawei\DevEco Studio`) — required for build/emulator/device features.
- `devecocli` (DevEco CLI) wraps `hvigor` / `ohpm` / `hdc`, scaffolding, docs knowledge base (`devecocli docs search <kw>`), skills installer, and MCP.
- Free model: log in with a Huawei account (`deveco auth login`), then use the `deveco` provider (GLM-5.1, 50 req/min per account). Third-party models via the `qiniu` provider in `deveco.jsonc`.
- Update with `deveco upgrade`. Config changes (skills/MCP/plugins) require restarting `deveco`.
- Recommended terminal: PowerShell 7+ (some `devecocli` commands hang in the default Windows console host).
