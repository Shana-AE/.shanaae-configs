---
name: codegraph
description: >-
  Code intelligence via the CodeGraph index — understand and locate code in a
  repository by symbol and call-path instead of grep. Use when working in a repo
  that has a `.codegraph/` index, for tasks like: "where is X defined", "who
  calls X / what does X call", "trace the call path from A to B", "what's the
  blast radius of changing this function", "which tests cover these changed
  files", or understanding unfamiliar code before editing. Prefer this over
  grep/find/read for tracing symbols and call paths — it follows dynamic
  dispatch (interface/virtual calls) that grep cannot. Do NOT use when there is
  no `.codegraph/` directory (suggest `codegraph init` instead) or for plain
  literal text search.
---

# CodeGraph

CodeGraph builds a per-repo symbol + call-path graph. It answers code questions
in **one call** that would otherwise take many grep→read round trips, and it
follows **dynamic dispatch** (interface/virtual/method calls) that grep cannot.

## Prerequisite

A `.codegraph/` directory must exist at the repo root. Check first:

```bash
[ -d .codegraph ] && echo "indexed" || echo "not indexed"
```

- **Not indexed?** Do not use CodeGraph. Suggest initializing once:
  `codegraph init` (creates `.codegraph/` with an auto-generated `.gitignore`
  that keeps the index out of git). Then proceed.
- The `codegraph` binary lives at `~/.local/bin/codegraph` (already on the
  interactive shell PATH). Requires nothing else.

## Core workflow

1. **Stay fresh** — if files changed since the last session, sync first (fast,
   incremental, ~50-150ms):
   ```bash
   codegraph sync
   ```
2. **Pick the right command** (run from the repo root, or pass `-p <path>`):

| Goal                                          | Command                                   |
| --------------------------------------------- | ----------------------------------------- |
| Understand an area (symbols + call paths)     | `codegraph explore "router auth flow"`    |
| One symbol's source + caller/callee trail     | `codegraph node createOrder`              |
| Who calls a symbol                            | `codegraph callers createOrder`           |
| What a symbol calls                           | `codegraph callees createOrder`           |
| Blast radius of changing a symbol             | `codegraph impact createOrder`            |
| Tests affected by changed files               | `codegraph affected src/orders.ts src/cart.ts` |
| Read a file with line numbers + dependents    | `codegraph node -f src/orders.ts`         |
| Search symbols by name                        | `codegraph query <search>`                |
| Index status / stats                          | `codegraph status`                        |

`explore` and `node` produce the **same output as the `codegraph_explore` /
`codegraph_node` MCP tools** — no capability is lost by using the CLI.

## When to prefer CodeGraph over grep/find/read

- Tracing how code is reached ("how does a request get to X?")
- Finding all callers / callees of a function or method
- Assessing impact before a refactor or signature change
- Understanding an unfamiliar module before editing
- Picking which tests to run after a change

## When NOT to use it

- No `.codegraph/` index → suggest `codegraph init`, or just use grep/read.
- Plain literal text search (log strings, TODOs, exact-string matches) → grep is
  faster and needs no index.
- The repo is tiny or a one-off lookup → direct `read` is simpler.

For the full command reference and flags, see [references/cheatsheet.md](references/cheatsheet.md).
