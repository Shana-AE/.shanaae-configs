# Cross-Platform, Cross-Tool Configs

**Status:** Approved (design) — pending implementation plan
**Date:** 2026-06-25
**Owner:** shanaae

## 1. Goal

Make the `.shanaae/configs` repo — the single source of truth for AI-agent
configuration (skills, MCP servers, user rules, model catalogs) — usable on
**Linux (WSL2), Windows (native), and macOS**, across **OpenCode, Claude Code,
Trae, Cursor, Codex CLI**, and easily extensible to other tools.

Today the repo is WSL2-only: hardcoded `/home/...` paths, bash-only scripts,
Unix symlinks, and WSL-specific networking assumptions. This spec removes those
blockers while preserving the "edit once, works everywhere" property the user
requires.

## 2. Non-Goals

- Supporting GUI-only or non-config-file-based tools.
- Auto-detecting/rotating API keys (secrets remain a manual `.secrets` step).
- Rewriting the existing tool config *schema* (opencode.jsonc, mcp.json, …).
- Per-OS forks of any config file.

## 3. Key Decisions (locked)

| #  | Decision                                       | Choice                                                    |
| -- | ---------------------------------------------- | --------------------------------------------------------- |
| D1 | Target OSes                                    | Linux (WSL2), Windows (native), macOS                     |
| D2 | Target tools                                   | OpenCode, Claude Code, Trae, Cursor, Codex CLI (+ ext.)   |
| D3 | OS-specific values inside configs              | **Env-var first** + minimal templating escape-hatch       |
| D4 | How configs reach each tool                    | **Live link** tool-native-location → repo path            |
| D5 | Installer technology                           | **Single Python `install.py`** for all OSes               |
| D6 | Adding a tool                                  | Add a row to `install/manifest.json` — no code change     |

### Why these choices
- **Env-var first (D3):** tool configs are static JSON; a hardcoded path can
  never be auto-ported. Expressing paths as `{env:VAR}`/`$VAR` means *one* file
  resolves differently per OS via the tool's own substitution. No re-render on
  edit. Templating is kept only for the ~1-2 values no tool can substitute.
- **Live link (D4):** the tool reads the repo file directly → edits are
  *instantly* reflected on every OS, zero re-sync. The installer runs once per
  machine, not on every config edit — directly satisfies the user's
  "convenient when modifying configs" requirement.
- **Python installer (D5):** repo already depends on Python
  (`setup_configs.py`); one source of truth avoids bash/PowerShell drift.

## 4. Architecture — Four Layers

```
Layer 1  PORTABLE CORE (the repo, as-is)
         .config/opencode/ .claude/ .trae/ .cursor/ .codex/ ai/
         Source of truth. Contains NO OS-specific literals.

Layer 2  OS-SPECIFIC VALUES  (env / .secrets, gitignored)
         PROJECTS_DIR, MINIMAX_OUTPUT_DIR, BRAVE_DEBUG_URL,
         OBSIDIAN_VAULT_DIR, + API tokens.
         One .secrets per machine. .secrets.example ships per-OS samples.

Layer 3  LINK MANIFEST  (install/manifest.json, committed)
         Rows: tool · repo-source · native-target(linux/mac) · native-target(win) · mode
         Add a tool = add a row.

Layer 4  INSTALLER  (install.py, one-time per machine)
         Reads manifest → links native-target → repo-source
         (*nix symlink; Windows junction/symlink; copy fallback)
         Renders *.example templates · regenerates for-tools/ · boots .secrets
```

**Invariant:** Day-to-day edits happen in Layer 1. Because every OS-specific
value lives in Layer 2, a single edit resolves correctly on all OSes through the
tool's own env-var substitution. The live links (Layer 4 output) carry that edit
to each tool with no re-run.

## 5. Canonical Environment-Variable Vocabulary

These replace every hardcoded path/command currently in the repo.

| Variable             | Replaces (current)                | Linux/macOS example              | Windows example                      |
| -------------------- | --------------------------------- | -------------------------------- | ------------------------------------ |
| `PROJECTS_DIR`         | `/home/shanaae/projects`            | `/home/shanaae/projects`           | `C:\Users\shana\projects`              |
| `MINIMAX_OUTPUT_DIR`   | `/home/shanaae/minimax-output`      | `/home/shanaae/minimax-output`     | `%USERPROFILE%\minimax-output`         |
| `BRAVE_DEBUG_URL`      | `http://127.0.0.1:9222`             | same                             | same                                 |
| `OBSIDIAN_VAULT_DIR`   | Obsidian path in rules/docs        | `/mnt/e/.../obsidian-vault`        | `E:\Users\shana\...\obsidian-vault`    |
| `AI_CONFIGS_ROOT`      | repo path in scripts/docs          | **auto-derived** by installer     | **auto-derived** by installer         |
| `*_API_KEY` (existing) | tokens in configs                 | per-user                         | per-user                             |

Substitution syntax per tool (the installer does **not** rewrite these — the
tool resolves them at read time):
- OpenCode `opencode.jsonc` → `{env:PROJECTS_DIR}`
- Claude Code `mcp.json` → `$PROJECTS_DIR`
- Trae `trae.json` → rendered from `trae.json.example` as `{{PROJECTS_DIR}}`
  (Trae has no native env-sub; this is the one templating case)

`AI_CONFIGS_ROOT` is exported by the installer into a sourced
`env.sh`/`env.ps1` (or the user's shell profile) so scripts and docs can refer
to the repo portably instead of hardcoding `/home/shanaae/.shanaae/configs`.

## 6. Link Manifest — `install/manifest.json`

Each row links **individual repo-owned paths**, never a whole tool dir that
holds runtime state (e.g. `~/.claude/history`, `statsig`).

| tool             | repo_source                      | native_target (linux/mac)        | native_target (windows)            | mode   |
| ---------------- | -------------------------------- | -------------------------------- | ---------------------------------- | ------ |
| opencode         | `.config/opencode/`                | `~/.config/opencode`               | `%USERPROFILE%\.config\opencode`     | dir    |
| claude           | `.claude/rules`, `.claude/skills`, `.claude/mcp.json`, `.claude/settings.json`, `.claude/config.json` | same paths under `~/.claude` | same under `%USERPROFILE%\.claude` | mixed  |
| claude-router    | `.claude-code-router/`             | `~/.claude-code-router`            | `%USERPROFILE%\.claude-code-router`  | dir    |
| trae             | `.trae/`                           | `~/.trae`                          | `%APPDATA%\Trae\User` (selective)    | mixed  |
| trae-mcp         | `ai/mcp/trae.json`                 | `~/.trae/mcp.json`                 | `%APPDATA%\Trae\User\mcp.json`       | file   |
| cursor           | `.cursor/`                         | `~/.cursor`                        | `%USERPROFILE%\.cursor`              | dir    |
| codex            | `.codex/`                          | `~/.codex`                         | `%USERPROFILE%\.codex`               | dir    |

`mode` controls link granularity: `dir` = link the whole directory;
`file` = link a single file; `mixed` = a list of (source, target) pairs.

### Windows linking strategy
- Directories → `mklink /J` (junction) — **no admin/Developer Mode needed**.
- Files → `mklink` (symlink) — needs Developer Mode enabled. If unavailable,
  fall back to **copy** and record the entry in `install/.copy-state.json` so
  re-runs of `install.py` **re-sync** copies when the source changes (detected
  via mtime/hash). This keeps the "edit once" property even where symlinks fail.

## 7. Installer — `install.py`

**Entrypoint:** `python3 install.py [--tool <name>] [--all] [--force] [--dry-run]`

**Behavior:**
1. Detect OS (`platform.system()`): `Linux`/`Darwin` → symlink path;
   `Windows` → junction/symlink/copy path.
2. Resolve `AI_CONFIGS_ROOT` = repo root (dir containing `install.py`).
3. Load `install/manifest.json`; filter to `--tool` or all.
4. For each row, for the current OS's `native_target`:
   - Expand `~` and `%VAR%`/`$HOME`.
   - If target is already our link → skip (idempotent).
   - If target exists and is not ours → back up to `<target>.bak-<timestamp>`
     (gitignored), unless `--force`.
   - Create link per `mode` and OS strategy (§6).
5. Render templates: for each `*.example`, run the replacement map from
   `setup_configs.py` (extended with the §5 path vars) → write the real file.
   Skip if `.secrets` missing (warn user).
6. Regenerate `ai/skills/for-tools/` via the portable `link_skills.py`.
7. If `.secrets` missing, copy `.secrets.example` → `.secrets` and print
   "edit me" instructions.
8. Emit `env.sh` / `env.ps1` exporting `AI_CONFIGS_ROOT` (and remind to source
   it, or offer to append to shell profile).

**Safety:** `--dry-run` prints every planned action without writing. All
backups are timestamped and gitignored. Never deletes a non-backed-up target.

## 8. Script Portability

- `ai/skills/link-skills.sh` (bash, hardcoded `/home/...`) → rewritten as
  **`ai/skills/link_skills.py`** (pure Python, derives repo root from
  `__file__`). The old `.sh` becomes a 2-line shim: `python3 link_skills.py "$@"`
  for back-compat with anything that calls it.
- `.githooks/prepare-commit-msg`: replace the nvm absolute path
  (`/home/shanaae/.nvm/.../lefthook`) with **`npx lefthook`** (PATH-resolved).
- All Python scripts use `#!/usr/bin/env python3`, `os.path`/`pathlib`, and
  never hardcode `/home/...`.

## 9. Concrete File Changes

| Action | Path                                              | Change                                                                              |
| ------ | ------------------------------------------------- | ----------------------------------------------------------------------------------- |
| new    | `install.py`                                        | cross-platform installer (§7)                                                       |
| new    | `install/manifest.json`                             | declarative link manifest (§6)                                                      |
| new    | `ai/skills/link_skills.py`                          | portable rewrite of link-skills.sh                                                  |
| new    | `.secrets.example`                                  | committed; all vars with per-OS commented samples                                   |
| new    | `.cursor/`, `.codex/`                                 | minimal config scaffolding for the two new tools                                    |
| edit   | `.config/opencode/opencode.jsonc`                   | `/home/shanaae/projects`→`{env:PROJECTS_DIR}`; minimax→`{env:MINIMAX_OUTPUT_DIR}`     |
| edit   | `.claude/mcp.json`                                  | filesystem arg → `$PROJECTS_DIR`                                                    |
| edit   | `ai/mcp/trae.json.example`                          | paths → `{{PROJECTS_DIR}}` (the one templating case)                                |
| edit   | `AGENTS.md`, `.config/opencode/AGENTS.md`             | Obsidian path → per-OS documented variants + `$OBSIDIAN_VAULT_DIR`                    |
| edit   | `ai/skills/local/get-secret-token/SKILL.md`           | hardcoded repo path → `$AI_CONFIGS_ROOT/.secrets`                                    |
| edit   | `CONFIG_README.md`                                  | hardcoded root → `$AI_CONFIGS_ROOT`                                                  |
| edit   | `.githooks/prepare-commit-msg`                      | nvm path → `npx lefthook`                                                            |
| edit   | `README.md`                                         | per-OS quickstart (Linux/macOS/Windows)                                             |
| shim   | `ai/skills/link-skills.sh`                          | reduce to `python3 link_skills.py "$@"`                                             |
| gitignore | `.gitignore`                                     | `*.bak-*`, `install/.copy-state.json`, `env.sh`/`env.ps1` (generated)               |

## 10. Templating Escape-Hatch (minimal)

`setup_configs.py` already renders `*.example` → real config via a replacement
map. We extend that map with the §5 path vars **only** for configs whose tool
cannot env-substitute (Trae is the only known case). Everything else uses
native `{env:}`/`$VAR`, resolved by the tool at read time. No new templating
engine is introduced.

## 11. Onboarding / Docs

`README.md` gains a per-OS quickstart:

```
# Linux / macOS / WSL
git clone <repo> ~/wherever && cd ~/wherever
cp .secrets.example .secrets   # fill in tokens + PROJECTS_DIR etc.
python3 install.py --all

# Windows (PowerShell, Developer Mode recommended for file symlinks)
git clone <repo> $HOME\wherever; cd $HOME\wherever
copy .secrets.example .secrets   # fill in
python install.py --all
```

Plus a short "how it works" pointer to this spec and the manifest, so adding a
tool is self-documenting.

## 12. Testing / Verification

- `install.py --dry-run --all` produces a correct, complete plan on each OS.
- After `install.py --all`: each tool resolves its config (e.g.
  `opencode` lists models; `claude mcp list` shows servers with `$PROJECTS_DIR`
  expanded).
- Idempotency: a second `install.py --all` makes zero changes.
- Windows copy-fallback: edit a repo config → re-run `install.py` → copy target
  updated (verified by diff).
- `link_skills.py` regenerates `for-tools/` identically to the old bash script
  (diff the output).
- gitleaks pre-commit still passes (no secrets enter configs).

## 13. Risks & Mitigations

| Risk                                        | Mitigation                                                              |
| ------------------------------------------- | ----------------------------------------------------------------------- |
| Windows file-symlink needs Developer Mode   | Junction for dirs (no admin); copy+sync fallback for files (§6).        |
| User hardcodes a path anyway → breaks port  | Add a CI/lint grep for `/home/`, `C:\Users`, `/mnt/` in tracked configs. |
| Whole-tool-dir link clobbers runtime state  | Manifest uses per-file/per-subdir `mode` (§6), never blind whole-dir.   |
| Trae's native location differs by version   | Manifest keeps trae target overridable; document lookup in README.      |
| `AI_CONFIGS_ROOT` not set in non-install shells | Installer emits `env.sh`/`env.ps1` + offers profile append.             |

## 14. Open Questions (to resolve in implementation plan)

1. Should `install.py` also offer to append `source .../env.sh` to the user's
   `.bashrc`/`.zshrc`/PowerShell `$PROFILE`, or only emit the file?
2. Cursor/Codex initial config content — mirror Claude Code's structure
   (rules + skills + mcp), or minimal empty scaffolding?
3. Whether to add the CI grep guard (Risks) now or as a follow-up.
