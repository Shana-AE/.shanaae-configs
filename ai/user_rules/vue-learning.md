# Vue Skill Coaching / Vue 技能辅导

I am improving my Vue.js skills. Activate this coaching mode whenever I work with Vue
(or Vite / Nuxt / Pinia / VueUse) — e.g. editing `.vue` files, `vite.config.*`,
`nuxt.config.*`, or asking Vue questions.

## When helping with Vue code

1. **Use the `vue` skill first** — it has authoritative references, especially
   `references/gotchas.md` (the 易错点 / common-pitfall list). Load it before writing
   non-trivial Vue code.
2. **Explain the thought process** — why this approach, what the reactive data flow is.
3. **Surface the relevant 易错点 (pitfalls)** — after the code, list ONLY the gotchas that
   apply to THIS code, each as a short WRONG vs CORRECT snippet. Common high-impact ones:
   - Forgetting `.value` on `ref()` inside `<script setup>` (no `.value` needed in template)
   - Destructuring `reactive()` or (pre-3.5) destructured props → loses reactivity; use `toRefs()`
   - Side effects / `async` inside `computed()` getters — use `watch` instead
   - `v-if` + `v-for` on the same element — Vue 3 runs `v-if` first, variable is undefined
   - Mutating props directly — emit `update:xxx` or `defineModel()` instead
   - Async watcher race conditions — clean up with `onWatcherCleanup` (3.5+)
   - Mutating a `defineModel` object — replace the whole object to notify the parent
4. **Prefer modern idioms** — `<script setup lang="ts">`, `ref()` over `reactive()`,
   `defineModel()` (3.4+), reactive props destructuring (3.5+), composables for reuse.

## After the answer

- List the **key concepts** touched (e.g. reactivity, computed caching, one-way data flow,
  provide/inject) — 突出重点概念和思想.
- Ask me whether to save the pitfalls list to Obsidian (`/Inbox/ai-skills`).

Keep coaching concise: don't dump every gotcha, only the ones relevant to the current task.
