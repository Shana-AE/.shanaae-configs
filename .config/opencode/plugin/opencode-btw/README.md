# opencode-btw — /btw plugin

Quick side question (by-the-way) for OpenCode. Type `/btw`, type your question in the
prompt, and the answer appears in a **dialog panel + toast** — the question runs in an
isolated child session (`btw:side-questions`), so your **main conversation is never
disturbed** (no command is sent to the main session at all).

Implemented as a **TUI plugin** (like `opencode-subagent-magazine`): it registers the
`/btw` slash command, runs the side session via the TUI plugin's own `client`, and
renders the answer with `api.ui`. This gives true main-context isolation, which a
server plugin could not (server hooks always execute in the main session).

- Full Q&A history: the `btw:side-questions` child session (session list).
- Toast shows a preview; the dialog shows the full answer (Esc to close).

## ⚠️ DEPRECATED — pending opencode v2

**This plugin uses the v1 OpenCode TUI plugin API** (`api.command.register` — the legacy
`api.command` bridge, marked "remove in v2"), and the opencode **v2 plugin system**
(`@opencode-ai/plugin/v2/effect`) redesigns the plugin surface:

- v1 TUI: `const tui = async (api) => { … }` + `api.command.register` / `api.keymap`.
- The v1 `api.command` shim already logs a deprecation warning.
- Reference: `packages/plugin/src/v2/effect/PLAN.md` in the opencode repo.

**Action required:** when opencode v2 is released, re-migrate this plugin (likely to a
v2 `define({ effect })` + v2 TUI surface, e.g. `api.keymap.registerLayer` instead of
`api.command`). The side-session logic in `src/tui.tsx` (`runBtw`) is portable; only the
registration/UI surface needs the v2 port.

> 此插件基于 v1 TUI 插件 API，opencode v2 发布后需迁移（见上）。当前仍可正常使用。

## Files

| File | Purpose |
|------|---------|
| `src/tui.tsx` | TUI plugin: `/btw` command → DialogPrompt → side session via `client` → answer dialog + toast |
| `package.json` | `oc-plugin: ["tui"]`, `./tui` → `src/tui.tsx`; deps `solid-js`/`@opentui/{solid,core}` |

## Registration

- `tui.json` → `"plugin": [ …, "./plugin/opencode-btw" ]`
- Plugin is **TUI-only** — do NOT add it to `opencode.json(c)`'s server `plugin` array.

## Deps

`solid-js@1.9.12`, `@opentui/solid@0.4.3`, `@opentui/core@0.4.3` must be installed in this
plugin's `node_modules` (they are peer deps of other TUI plugins like subagent-magazine).

```bash
bun install   # in this directory, on each machine
```

## Verify

```bash
bunx --bun tsc --noEmit                       # typecheck (in this dir)
# interactive: start opencode, type /btw, ask a question → dialog + toast appear;
# a btw:side-questions child session is created; the main session is untouched.
```
