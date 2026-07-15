# CodeGraph Command Reference

`codegraph` v1.3.0 — `~/.local/bin/codegraph`. Run from the repo root, or pass
`-p <path>` / a path argument. A `.codegraph/` index must exist (`codegraph init`
to create one).

## Lifecycle

| Command                  | Purpose                                                      |
| ------------------------ | ------------------------------------------------------------ |
| `init [path]`            | Initialize + build the initial index (creates `.codegraph/`, auto-adds `.gitignore`) |
| `index [path]`           | Rebuild the full index from scratch (use after a version upgrade or corruption) |
| `sync [path]`            | Incremental update of changed files since last index (fast; run before querying if the repo changed) |
| `status [path]`          | Index status + statistics. `-j` for JSON                       |
| `uninit [path]`          | Remove CodeGraph from a project (deletes `.codegraph/`)        |
| `unlock [path]`          | Remove a stale lock file blocking indexing                     |
| `daemon` / `daemons`     | Manage running background daemons (stop idle ones)             |

## Querying

### `explore <query...>` — understand an area

Returns relevant symbols' verbatim source **+ the call paths between them**,
including dynamic-dispatch hops. Same output as the `codegraph_explore` MCP tool.

```bash
codegraph explore "how is authentication handled"
codegraph explore "order creation flow" --max-files 8
```

- `-p, --path <path>` — project path
- `--max-files <number>` — cap how many files include source

### `node [name]` — one symbol, or read a file

A symbol's source + caller/callee trail. Same output as `codegraph_node` MCP tool.
With `-f`, switches to **file mode**: reads a file with line numbers + its
dependents.

```bash
codegraph node createOrder          # symbol mode
codegraph node -f src/orders.ts     # file mode (line-numbered + dependents)
codegraph node -f src/orders.ts --symbols-only   # just the symbol map + dependents
codegraph node -f src/orders.ts --offset 120 --limit 40
```

- `-p, --path <path>`
- `-f, --file <file>` — file mode, or disambiguate a symbol to this file
- `--offset <number>` — file mode, 1-based start line
- `--limit <number>` — file mode, max lines
- `--symbols-only` — file mode, just symbol map + dependents

### `callers <symbol>` / `callees <symbol>`

```bash
codegraph callers createOrder        # who calls it (-l <limit>, default 20)
codegraph callees createOrder        # what it calls
```

- `-p, --path <path>`, `-l, --limit <number>` (callers), `-j, --json`

### `impact <symbol>` — blast radius of a change

```bash
codegraph impact createOrder -d 3    # traversal depth (default 2)
```

- `-p, --path <path>`, `-d, --depth <number>`, `-j, --json`

### `affected [files...]` — tests impacted by changed source

```bash
codegraph affected src/orders.ts src/cart.ts
git diff --name-only | codegraph affected --stdin   # pipe a file list
codegraph affected -f "e2e/*.spec.ts"               # custom test glob
```

- `-p, --path <path>`, `--stdin`, `-d, --depth <number>` (default 5),
  `-f, --filter <glob>`, `-j, --json`, `-q, --quiet` (paths only)

### `query <search>` / `files`

```bash
codegraph query createOrder          # search symbols by name
codegraph files                      # project file structure from the index
```

## Notes

- The daemon auto-starts on query and idles out after ~5 min; it also runs a file
  watcher that auto-syncs the graph while alive. If unsure about freshness, run
  `codegraph sync` before querying.
- Install/uninstall into agents: `codegraph install` / `codegraph uninstall`
  (targets: claude-code, cursor, codex, opencode, hermes). Not used in this setup
  — CodeGraph is wired here as a skill over the CLI, not as an always-on MCP.
