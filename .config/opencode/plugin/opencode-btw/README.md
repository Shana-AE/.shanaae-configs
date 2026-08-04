# opencode-btw — /btw plugin

Quick side question (by-the-way) for OpenCode. Type `/btw <question>` → the question runs
in an isolated child session (`btw:side-questions`), and the answer shows in a **persistent
TUI sidebar panel** (plus a toast cue). The main conversation is not disturbed — its prompt
uses a silent "do not respond, continue your task" template.

## How it works (two cooperating plugins)

| Part | File | Role |
|------|------|------|
| Server plugin | `src/plugin.ts` | `command.execute.before` hook → creates `btw:side-questions` child session → prompts it → shows a toast (`client.tui.showToast`, title `💡 BTW`) |
| TUI plugin | `src/tui.tsx` | `api.slots.register({ slots: { sidebar_content } })` renders a persistent sidebar panel; `api.event.on("tui.toast.show")` (title `💡 BTW`) triggers reading the child session's full answer via `api.client.session.children` + `session.messages` → updates the panel |
| Command | `commands/btw.md` | registers `/btw`; silent template so the main agent doesn't re-answer |

The answer panel updates reactively after the toast fires (which happens only after the
side session fully answers), so it shows the **complete** answer, persistent and readable.
This avoids the opencode 1.18 plugin-dialog key-routing bug (DialogPrompt opened from a
plugin command renders but never receives Enter/Esc) — no dialogs are used.

## ⚠️ DEPRECATED — pending opencode v2

Uses the v1 plugin API: server `command.execute.before` + `client.tui.showToast`, and the
v1 TUI API (`api.slots` / `api.event`). The opencode **v2 plugin system**
(`@opencode-ai/plugin/v2/effect`) redesigns this surface.

- Server: v1 hook → v2 `ctx.command.hook("execute.before", …)`.
- TUI: v1 `api.slots`/`api.event` → v2 TUI surface (to be defined).
- Reference: `packages/plugin/src/v2/effect/PLAN.md`.

**Action required:** re-migrate when opencode v2 ships. The side-session logic is portable;
only the registration/UI surface needs the v2 port.

> 此插件基于 v1 插件 API，opencode v2 发布后需迁移（见上）。当前仍可正常使用。

## Registration

- `opencode.jsonc` → `"plugin": [ …, "./plugin/opencode-btw" ]` (server part)
- `tui.json` → `"plugin": [ …, "./plugin/opencode-btw" ]` (TUI part)
- `commands/btw.md` → the `/btw` command.

Optional config (top-level `"btw"` in `opencode.jsonc`): `model`, `toastDuration`, `keepSession`.

## Deps (TUI part)

`solid-js@1.9.12`, `@opentui/solid@0.4.3`, `@opentui/core@0.4.3` must be in the plugin's
`node_modules` (per machine):

```bash
bun install   # in this directory, on each machine
```

## Verify

```bash
bunx --bun tsc --noEmit   # typecheck (in this dir)
# interactive: start opencode, in a session type /btw <question> → a toast pops and the
# answer appears in the sidebar panel; full Q&A in the btw:side-questions child session.
```
