# OpenCode Global Rules

## English Practice

Full rules live in `rules/english-learning.md` (loaded via `instructions`).
Summary: answer the real question in English **first**, then **append** an **English Check** block at the END that (A) corrects/optimizes my question, (B) nudges me to use English if I wrote Chinese, (C) lists vocabulary above CET-6 (**always shown**, never skipped), and (D) gives a one-point **grammar spotlight** (always shown); annotate long/uncommon sentences in Chinese. For deep language work (essay grading, grammar deep-dives, IELTS/TOEFL mock), dispatch the `english-tutor` subagent.

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

The Obsidian vault is **bidirectionally synced across all devices** (Windows, macOS, others) via the Livesync plugin. Each platform has its own local mount; writes propagate through CouchDB replication, not direct file sync.

- **macOS path**: `~/Developer/obsidian-vault/` (hoisted out of `~/Documents/` on 2026-07-21 to escape TCC protections and iCloud Desktop & Documents sync risk; `~/Documents/` is a TCC-shielded location on macOS)
- **Windows path**: `E:\Users\shana\Documents\Obsidian Vault\obsidian-vault`
- **WSL access**: `/mnt/e/Users/shana/Documents/Obsidian Vault/obsidian-vault`
- **Symlink** (convenience, WSL): `/home/shanaae/documents/obsidian-vault` → the Windows vault above.
- **Quartz dev server** (`~/quartz-site`) reads vault content via the symlink `~/quartz-site/content` → macOS vault path.
- Structure follows **I.A.R.P**: `Inbox/` (capture), `Area/` (life + work), `Resource/` (topics: web, rust, devops, english, cs, records, tools, glossary, others), `Project/` (bounded outcomes), `Recycle/` (trash).
- Git remote: `git@github.com:Shana-AE/obsidian-vault.git` (note: `core.ignorecase=true`; for case-only folder renames use a two-step `git mv`).

## Hoisted Code Folders (`~/Developer/`)

Code, SDKs, and the vault were hoisted out of `~/Documents/` to escape macOS TCC (Transparency, Consent, and Control) restrictions and iCloud Desktop & Documents sync risk. The `~/Developer/` location is Apple's official convention and is not TCC-shielded.

- `~/Developer/projects/` — all code projects (was `~/Documents/projects/`)
- `~/Developer/tools/` — SDKs and learning repos; referenced by `~/.zshrc` env vars `ANDROID_SDK_ROOT` and `HARMONY_CLI_HOME`
- `~/Developer/obsidian-vault/` — see Obsidian Vault Location above
- `~/Developer/hap_installer/` — HarmonyOS signing config

What **stayed** in `~/Documents/`: `chrome-devtools-overrides/` (Chrome hard-codes path), `com_tencent_imsdk_data/` (app-managed), `insurance/` (personal docs).

### Old-Path Tracker (safety-symlink usage monitor)

Safety symlinks were left in `~/Documents/{projects,tools,obsidian-vault,hap_installer}` pointing to `~/Developer/` counterparts as a 2-week transition net (installed 2026-07-21, target removal 2026-08-04). A tracker catches anything still using the OLD paths:

- **`~/.local/bin/old-docs-sweep`** — daily static-grep sweep + lsof snapshot + symlink-health check. Allowlist filters deliberate refs (AGENTS.md changelog, historical cron logs, this script itself).
- **`~/Library/LaunchAgents/com.shanaae.old-docs-tracker.plist`** — fires daily at 09:00 + RunAtLoad. Logs to `~/.local/var/log/old-docs/sweep-YYYY-MM-DD.log` (30-day retention). Pops a macOS notification (via `osascript`) with hit count.
- **`~/.local/bin/old-docs-fsusage`** — on-demand `sudo` wrapper for real-time `fs_usage` syscall tracing of literal old paths. Use when daily sweep isn't enough and we need to know WHICH process is actively using an old path.

**Limitation**: `lsof` resolves symlinks to canonical paths, so runtime symlink-path access is invisible without `fs_usage`+`sudo`. Static sweep catches hardcoded refs in configs/code (~95%); `fs_usage` catches the rest on-demand.

**When the user asks "are the safety symlinks safe to remove yet?"** — run `ls ~/.local/var/log/old-docs/` and `tail -50` of each recent log. If 14+ consecutive days show "SUMMARY: 0" with no hits outside the allowlist, it's safe. Removal: `rm ~/Documents/{projects,tools,obsidian-vault,hap_installer}` then optionally unload the tracker.

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
- **Viewer**: `http://192.168.86.62:3113` (LAN-direct, no tunnel needed; accessible from any device on the LAN). The viewer is bound to `0.0.0.0:3113` via env `AGENTMEMORY_VIEWER_HOST=0.0.0.0` in the docker-compose, with DNS-rebinding guard `VIEWER_ALLOWED_HOSTS=192.168.86.62:3113,localhost:3113,127.0.0.1:3113,SHANAAE-EVO4:3113`. Data access still requires the `AGENTMEMORY_SECRET` bearer token (the viewer UI prompts for it).
- **Viewer patches** (applied via `entrypoint.sh` volume mount at each container start; see [#609](https://github.com/rohitg00/agentmemory/issues/609) and [#1117](https://github.com/rohitg00/agentmemory/issues/1117)): (1) CSP `connect-src` patched to include `ws://*:*` for LAN WebSocket access, (2) WS `onmessage` skips payloads >500KB to prevent browser freeze from the 9.4MB sync backlog, (3) sync render capped to last 200 items, (4) token stored in `localStorage` instead of `sessionStorage` (persists across tab close). All patches are in `/vol1/1000/docker/agentmemory/entrypoint.sh`.
- **LLM provider**: MiniMax-M3 via Token Plan (env: `MINIMAX_API_KEY` from `.env` file, `MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic`, `MINIMAX_MODEL=MiniMax-M3`). Graph extraction (`GRAPH_EXTRACTION_ENABLED=true`) and consolidation (`CONSOLIDATION_ENABLED=true`) are both enabled. `AGENTMEMORY_AUTO_COMPRESS` is off (synthetic compression for raw observations; LLM used for graph extraction + consolidation only). Embedding provider: none (BM25/hybrid search only).

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

## Honcho (self-hosted) — Operations

Honcho (Plastic Labs) provides **conversational memory** — persistent user profile, dialectic context, and session reasoning. Self-hosted on the NAS alongside AgentMemory. Division of labor: **Honcho = conversational/user-profile/dialectic; AgentMemory = structured coding facts.**

- **Server**: `http://192.168.86.62:18000` (v3 API at `/v3`); env `HONCHO_URL`
- **Viewer**: `http://192.168.86.62:41800` — **OpenConcho** web UI ([`offendingcommit/openconcho`](https://github.com/offendingcommit/openconcho)), LAN-direct (no tunnel). Browse peers/sessions/conclusions/dreams, dialectic playground, chat with memory context. Same-origin `/api` reverse-proxy → `https://honcho-tls:8443` (no Honcho CORS needed). API key entered once in the browser (stored in `localStorage`); not in the container. SSRF allowlist (`api,honcho-tls,192.168.86.62,localhost,127.0.0.1`) locks the proxy to known upstreams.
  - **Why `honcho-tls`**: OpenConcho's client guard refuses to send the API token unless the configured instance URL is `https://` or `localhost`. Honcho speaks plain HTTP, so an internal Caddy sidecar (`honcho-tls`, `caddy:2-alpine`, `tls internal`) terminates TLS and `reverse_proxy`s to `api:8000`. Internal-only (no published port); only OpenConcho can reach it. Honcho auth stays on (`AUTH_USE_AUTH=true`), token validated by Honcho. Caveat: the browser→OpenConcho origin hop is still HTTP on the LAN, so this satisfies the guard + keeps auth enforced, but is not full end-to-end token confidentiality.
  - In the OpenConcho UI, set the instance URL to `https://honcho-tls:8443` (seeded automatically on first load; edit manually if a stale `http://api:8000` instance lingers in `localStorage`).
- **Auth**: `HONCHO_API_KEY` env var (in `.secrets`). `~/.honcho/config.json` holds **no embedded key** — the env var is the single source of truth (the plugin resolves `config.apiKey || process.env.HONCHO_API_KEY`).
- **Deployment**: NAS docker-compose at `/vol1/1000/docker/honcho-hermes-mac/` (use `sudo` for docker on the NAS).
- **Image**: pinned `honcho-hermes-mac:3.0.11-20260713` (Honcho 3.0.11, built 2026-07-13, image `a8d49442d532`). `:latest` also exists, but the compose references the pinned tag — don't rebuild onto `:latest` without re-tagging a new pin.
- **Services**: `api` (`192.168.86.62:18000`→container `:8000`), `deriver` (background derivation), `database` (`pgvector/pgvector:pg15`), `redis` (cache), `ollama` (local embeddings fallback), `openconcho` (`192.168.86.62:41800`→container `:8080`, web UI — see Viewer above), `honcho-tls` (internal-only Caddy `:8443`→`api:8000`, TLS terminator for OpenConcho's token guard — see Viewer above).
- **LLM backend**: configured in `.env` — `LLM_OPENAI_API_KEY`/`LLM_OPENAI_BASE_URL`, five dialectic levels (`minimal`→`max`), plus summary + dream + embedding models. The dialectic **is** available and enabled.
- **Config standard** (`~/.honcho/config.json`, `hosts.opencode`, unified across machines): `recallMode: tools`, `sessionStrategy: per-directory`, `contextRefresh: {messageThreshold: 100, ttlSeconds: 600, skipDialectic: false}`, `messageUpload: {summarizeAssistant: true, maxUserTokens: 2000, maxAssistantTokens: 2000}`. Workspace `hermes` is shared across OpenCode (`aiPeer: opencode`) and Claude Code (`aiPeer: claude-code`).
- **Backup**: `./data/pgdata/` holds all conversational memory — include in the NAS backup strategy.
- **Rebuild/redeploy**: `cd /vol1/1000/docker/honcho-hermes-mac && sudo docker compose build && sudo docker tag <new-image> honcho-hermes-mac:<ver>-<date> && sudo docker compose up -d`. Changing the image tag causes a container recreate (brief restart); same image content = no data change. `~/.honcho/config.json` is machine-local (not in this repo) — edit per machine, or replicate manually.

## MCP Tools Usage

- Use the **context7 skill** (curl to context7.com API with `CONTEXT7_API_KEY`) when you need to search documentation — the MCP was removed to save per-message tokens
- Use `Git` tools for git operations
- Use `Filesystem` tools for file operations
- Use `Sequential Thinking` tools for complex problem solving

## Frontend Visual Verification

For any frontend task that changes styles, layout, spacing, responsive behavior, modals, dialogs, CSS, or screenshot/Figma fidelity:

- **MUST proactively invoke the `frontend-visual-verify` skill.** Do not wait for the user to request browser verification.
- Render the page, inspect computed styles and geometry, capture a screenshot, compare it, and iterate before claiming completion.
- Never claim visual fidelity from source review, tests, DOM structure, or CSS values alone.
- Route screenshots by the active model's normalized capabilities. Native vision requires both attachment transport and image input; false, incomplete, missing, or unknown capabilities use the skill's visual bridge.
- Prefer `agent-browser` for routine UI verification. Reserve `web-devtools` for deep performance, memory, network, or console investigations.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code. CodeGraph is wired here as the **`codegraph` skill** (CLI-based), not an always-on MCP — invoke the skill for the workflow:

- `codegraph explore "<symbol names or question>"` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Run `codegraph sync` first if the repo changed since last session.
- Also: `codegraph node <symbol>` (source + caller/callee trail), `codegraph callers|callees|impact <symbol>`, `codegraph affected [files]` (test impact).

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision (`codegraph init` to start). In projects where oh-my-openagent (omo) is enabled, omo may additionally serve the `codegraph` MCP at runtime; either path works.
<!-- CODEGRAPH_END -->
