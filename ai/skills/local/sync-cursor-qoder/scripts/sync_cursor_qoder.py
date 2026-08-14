#!/usr/bin/env python3
r"""Copy-sync Cursor / Qoder / QoderCN configs from the repo to the native
Windows profile dirs (reachable from WSL via /mnt/c).

NTFS junctions cannot target \\\\wsl$ paths, so instead of symlinks this
script mirrors (with deletion of stale entries):

  ai/skills/for-tools/cursor -> %USERPROFILE%\.cursor\skills
  ai/skills/for-tools/qoder  -> %USERPROFILE%\.qoder\skills
                              -> %USERPROFILE%\.qoder-cn\skills
  ai/user_rules              -> ...\.cursor\rules (+ .qoder, .qoder-cn)
  cursor/AGENTS.md           -> %USERPROFILE%\.cursor\AGENTS.md
  qoder/AGENTS.md            -> %USERPROFILE%\.qoder\AGENTS.md (+ .qoder-cn)

Skips silently when /mnt/c is not mounted (not a WSL-Windows machine).
Windows user name defaults to "shana"; override with WIN_USER env var.
"""

import argparse
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../../../"))
MNT_C = "/mnt/c"


def mirror_dir(src_dir: str, dst_dir: str, dry_run: bool) -> int:
    """Mirror src_dir into dst_dir (delete stale entries, copy files).
    Pool entries are symlinks on the WSL side — dereferenced so Windows
    receives real files. Returns number of entries copied."""
    if not os.path.isdir(src_dir):
        print(f"  WARN: source missing, skipping: {src_dir}")
        return 0
    if dry_run:
        print(f"  [dry-run] mirror {src_dir}/ -> {dst_dir}/ ({len(os.listdir(src_dir))} entries)")
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    wanted = set(os.listdir(src_dir))
    for name in sorted(wanted):
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        if os.path.isdir(dst) and not os.path.islink(dst):
            shutil.rmtree(dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=False)
        else:
            shutil.copy2(src, dst, follow_symlinks=True)
    for name in os.listdir(dst_dir):
        if name not in wanted:
            p = os.path.join(dst_dir, name)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.unlink(p)
    return len(wanted)


def copy_file(src: str, dst: str, dry_run: bool) -> int:
    if not os.path.isfile(src):
        print(f"  WARN: source missing, skipping: {src}")
        return 0
    if dry_run:
        print(f"  [dry-run] copy {src} -> {dst}")
        return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst, follow_symlinks=True)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show what would be synced")
    args = ap.parse_args()

    if not os.path.isdir(MNT_C):
        print("  /mnt/c not mounted — nothing to sync (not a WSL/Windows machine).")
        return 0

    user = os.environ.get("WIN_USER", "shana")
    wh = os.path.join(MNT_C, "Users", user)
    if not os.path.isdir(wh):
        print(f"  WARN: {wh} not found — nothing to sync.")
        return 0

    pools = os.path.join(CONFIGS_ROOT, "ai/skills/for-tools")
    rules = os.path.join(CONFIGS_ROOT, "ai/user_rules")
    targets = [
        ("cursor", os.path.join(wh, ".cursor")),
        ("qoder", os.path.join(wh, ".qoder")),
        ("qoder", os.path.join(wh, ".qoder-cn")),
    ]

    total = 0
    for tool, profile in targets:
        print(f"== {tool} -> {profile}")
        total += mirror_dir(os.path.join(pools, tool), os.path.join(profile, "skills"), args.dry_run)
        total += copy_file(os.path.join(CONFIGS_ROOT, tool, "AGENTS.md"),
                           os.path.join(profile, "AGENTS.md"), args.dry_run)
        total += mirror_dir(rules, os.path.join(profile, "rules"), args.dry_run)
    print(f"Done — {total} entries synced." if not args.dry_run else f"Dry-run — {total} entries would sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())