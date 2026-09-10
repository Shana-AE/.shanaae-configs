#!/usr/bin/env zsh
# sync-deveco.zsh — copy-sync the curated deveco config to the Windows profile.
#
# Source: ~/.shanaae/configs/deveco/   (git-managed source of truth)
# Target: C:\Users\shana\.config\deveco\  (NTFS cannot junction into \\wsl$,
#         so this is a one-way copy, same pattern as sync-cursor-qoder)
#
# Usage: zsh ~/.shanaae/configs/shell/sync-deveco.zsh
set -euo pipefail

SRC="${0:A:h}/../deveco"
DST="/mnt/c/Users/shana/.config/deveco"

[[ -d "$SRC" ]] || { echo "source missing: $SRC" >&2; exit 1 }
[[ -f "$SRC/deveco.jsonc" ]] || { echo "deveco.jsonc missing in $SRC" >&2; exit 1 }
mkdir -p "$DST"

# Mirror without --delete: deveco may write its own state files into the dir
# later; sync only overwrites the files we own.
cd "$SRC"
find . -type f ! -path './node_modules/*' | while read -r f; do
  mkdir -p "$DST/$(dirname "${f#./}")"
  cp -p "$f" "$DST/${f#./}"
done

echo "synced deveco config -> $DST"
find "$DST" -type f | sed "s|$DST/||" | sort
