# HarmonyOS Skill Coaching / 鸿蒙开发技能辅导

I am improving my HarmonyOS (ArkTS / ArkUI) skills. Activate this coaching mode whenever
I work with HarmonyOS — e.g. `.ets` files, ArkTS/ArkUI code, or OpenHarmony questions.

## When helping with HarmonyOS code

1. **Verify specifics via docs / context7** — the ArkUI API evolves quickly; confirm
   decorator names, parameters, and signatures against official docs instead of guessing.
2. **Explain the thought process** — component lifecycle, state data flow.
3. **Surface the relevant 易错点 (pitfalls)** — after the code, list ONLY the gotchas that
   apply to THIS code.

### High-impact ArkUI state-management pitfalls (易错点)

- **`@State` must be initialized** — `@State count: number = 0`; no initial value = error.
- **Pick the right decorator**:
  - `@State` — component-internal state (must init)
  - `@Prop` — one-way parent → child
  - `@Link` — two-way; parent passes `$var` (the reference form)
  - `@Provide` / `@Consume` — cross-component-tree; **the string key must match on both sides**
  - `@Observed` + `@ObjectLink` — for nested-class / array-of-object reactivity
- **Nested object changes need `@Observed` + `@ObjectLink`** — editing a property of a plain
  object stored in `@State` will NOT refresh the UI unless its class is `@Observed` and the
  child uses `@ObjectLink`.
- **`build()` has exactly one root child** — wrap multiple children in `Column` / `Row` / `Stack`.
- **No browser APIs** — there is no `window` / `document` / `localStorage`; use
  `@ohos.data.preferences`, `@ohos.*` system kits instead.
- **`ForEach` loads all items** — for long lists use `LazyForEach` with a data source that
  implements `IDataSource`.
- **ArkTS is strictly typed** — avoid `any`; assigning a brand-new object is the reliable way
  to trigger a `@State` refresh.
- **Lifecycle** — `aboutToAppear` / `aboutToDisappear` (not `mounted`/`unmounted`); do async
  data fetch in `aboutToAppear`, not inside `build()`.

## After the answer

- List the **key concepts** touched (e.g. one-way vs two-way binding, lifecycle, list
  rendering, dependency injection) — 突出重点概念和思想.
- Ask me whether to save the pitfalls list to Obsidian (`/Inbox/ai-skills`).

Keep coaching concise: only the pitfalls relevant to the current task.
