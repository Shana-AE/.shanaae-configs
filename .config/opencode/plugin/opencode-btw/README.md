# opencode-btw — /btw plugin

Quick side question (by-the-way) for OpenCode. Type `/btw <question>` → the question runs in
an isolated child session (`btw:side-questions`), the answer surfaces as a TUI toast, and your
**main conversation is not disturbed** (its prompt uses a "do not respond, continue your task"
template).

- Full Q&A history: open the `btw:side-questions` child session from the session list.
- The answer preview is shown in a toast (max ~400 chars); long answers are truncated there
  and point to the side session.

## ⚠️ DEPRECATED — pending opencode v2

**This plugin uses the v1 OpenCode plugin API** (`command.execute.before` hook +
`client.tui.showToast`), which the opencode **v2 plugin system**
(`@opencode-ai/plugin/v2/effect`) is designed to replace:

- v1: `PluginModule.server` returning a hooks object → v2: `define({ effect })` with
  imperative `ctx.command.hook("execute.before", …)`.
- The v1 TUI plugin API (`api.command`) is already marked `@deprecated` ("Remove in v2").
- Reference: `packages/plugin/src/v2/effect/PLAN.md` in the opencode repo.

**Action required:** when opencode v2 is released, re-migrate this plugin (likely to
`@opencode-ai/plugin/v2/effect` + a v2 TUI surface) or replace it with a native mechanism.
The side-session logic (`src/lib/btw-session.ts`, `config.ts`, `types.ts`) is portable;
only the registration/UI surface needs the v2 port.

> 此插件基于 v1 插件 API，opencode v2 发布后需迁移（见上）。当前仍可正常使用。

## Files

| File | Purpose |
|------|---------|
| `src/index.ts` | plugin entry (`id: "opencode-btw"`, `server`) |
| `src/plugin.ts` | `command.execute.before` hook → side session + toast |
| `src/lib/btw-session.ts` | `getOrCreateBtwSession`, `promptBtwSession` |
| `src/lib/config.ts` | `btw` config options (model, toastDuration, keybind, keepSession) |
| `src/lib/types.ts` | `BtwConfig`, defaults |
| `commands/btw.md` (repo) | registers the `/btw` command (silent fallback template) |

## Registration

- `opencode.jsonc` → `"plugin": [ …, "./plugin/opencode-btw" ]`
- `commands/btw.md` → the `/btw` command.

Optional config (top-level `"btw"` in `opencode.jsonc`):

```jsonc
{
  "btw": {
    "model": { "providerID": "provider", "modelID": "model" },
    "toastDuration": 10000,
    "keepSession": true
  }
}
```

## Verify

```bash
bunx --bun tsc --noEmit   # typecheck (in this dir)
# headless: main session must NOT contain the answer; a btw:side-questions child must exist
opencode run --command btw "what is 3+4"
```
