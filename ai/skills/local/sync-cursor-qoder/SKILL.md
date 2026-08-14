---
name: sync-cursor-qoder
description: "Copy-sync the Cursor / Qoder / QoderCN skill pools, user rules, and AGENTS.md from the repo into the native Windows profile dirs (%USERPROFILE%\\.cursor, .qoder, .qoder-cn) since NTFS cannot junction into \\\\wsl$. Use after running link-skills.sh, after editing skills-policy.json, or when contributing skill changes from WSL for Windows IDEs."
---

# sync-cursor-qoder

WSL `~/.cursor/skills` and `~/.qoder/skills` are symlinks into the repo's
per-agent pools (`ai/skills/for-tools/`). Windows-installed Cursor / Qoder /
QoderCN cannot read WSL symlinks and NTFS junctions cannot target `\\wsl$`
paths, so the Windows side is mirrored by **copies**.

## What it syncs

| Source (repo)                        | Windows target                                          |
| ------------------------------------ | ------------------------------------------------------- |
| `ai/skills/for-tools/cursor/`        | `%USERPROFILE%\.cursor\skills\`                         |
| `ai/skills/for-tools/qoder/`         | `%USERPROFILE%\.qoder\skills\`                          |
| `ai/skills/for-tools/qoder/`         | `%USERPROFILE%\.qoder-cn\skills\`                       |
| `ai/user_rules/`                     | `%USERPROFILE%\.cursor\rules\`, `.qoder\rules\`, `.qoder-cn\rules\` |
| `cursor/AGENTS.md` / `qoder/AGENTS.md` | `%USERPROFILE%\.cursor\AGENTS.md` / `.qoder\AGENTS.md` / `.qoder-cn\AGENTS.md` |

The pool is mirrored (stale symlinks/entries deleted) so the Windows side
always equals `for-tools/<agent>/`. `skills-cursor/` (Cursor's own skill set)
is never touched.

## Usage (run from WSL on the Windows machine)

```bash
python3 ai/skills/local/sync-cursor-qoder/scripts/sync_cursor_qoder.py --dry-run
python3 ai/skills/local/sync-cursor-qoder/scripts/sync_cursor_qoder.py
```

Skipped automatically when `/mnt/c` is not mounted (macOS/plain-Linux).
Custom Windows user: `WIN_USER=someone python3 .../sync_cursor_qoder.py`.