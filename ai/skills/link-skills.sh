#!/bin/bash
#
# link-skills.sh — build per-agent skill pools under for-tools/.
#
# Sources:    ai/skills/{vendor,local,private}/
# Policy:     ai/skills/skills-policy.json  (per-agent include/exclude)
# Output:     ai/skills/for-tools/<agent>/  (symlinks, gitignored)
# Ownership:  also re-points each tool's `skills` symlink (opencode /
#             claude / codex / trae) to its own pool.
#
# Usage:
#   bash link-skills.sh            link everything (idempotent)
#   bash link-skills.sh --dry-run  show what would change, touch nothing

set -euo pipefail

# Portable: resolve base dir from this script's location so it works on any OS.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
VENDOR_DIR="$BASE_DIR/vendor"
LOCAL_DIR="$BASE_DIR/local"
PRIVATE_DIR="$BASE_DIR/private"
FOR_TOOLS_DIR="$BASE_DIR/for-tools"
POLICY_FILE="$BASE_DIR/skills-policy.json"

AGENTS=(opencode claude codex trae)

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

# Per-agent tool symlink: absolute path of the `skills` link inside the repo,
# and the target it should point to (relative to that link's parent dir).
declare -A SYMLINK_PATH SYMLINK_REL
SYMLINK_PATH[opencode]="$BASE_DIR/../../.config/opencode/skills"
SYMLINK_PATH[claude]="$BASE_DIR/../../.claude/skills"
SYMLINK_PATH[codex]="$BASE_DIR/../../.codex/skills"
SYMLINK_PATH[trae]="$BASE_DIR/../../.trae/skills"
SYMLINK_REL[opencode]="../../ai/skills/for-tools/opencode"
SYMLINK_REL[claude]="../ai/skills/for-tools/claude"
SYMLINK_REL[codex]="../ai/skills/for-tools/codex"
SYMLINK_REL[trae]="../ai/skills/for-tools/trae"

# Pattern rules, per agent, as newline-separated lists.
declare -A INCLUDE EXCLUDE

load_policy() {
    if [ ! -f "$POLICY_FILE" ]; then
        echo "WARN: $POLICY_FILE not found — no per-agent filtering (full sets everywhere)."
        return 0
    fi
    local line agent kind pat
    # python3 emits one "agent<TAB>kind<TAB>pattern" line per effective rule
    # (defaults.expanded to every agent), warnings on stderr.
    while IFS=$'\t' read -r agent kind pat; do
        [ -z "$agent" ] && continue
        if [ "$kind" = "include" ]; then
            INCLUDE[$agent]+="$pat"$'\n'
        else
            EXCLUDE[$agent]+="$pat"$'\n'
        fi
    done < <(python3 - "$POLICY_FILE" <<'PYEOF'
import json, sys

agents = ["opencode", "claude", "codex", "trae"]
p = json.load(open(sys.argv[1], encoding="utf-8"))

unknown = [k for k in p if k != "defaults" and k not in agents]
for k in unknown:
    print(f"WARN: unknown agent key '{k}' in policy (ignored)", file=sys.stderr)

defaults_excl = p.get("defaults", {}).get("exclude") or []
for a in agents:
    for pat in defaults_excl:
        print(f"{a}\texclude\t{pat}")
    cfg = p.get(a, {}) or {}
    for kind in ("include", "exclude"):
        for pat in cfg.get(kind) or []:
            print(f"{a}\t{kind}\t{pat}")
PYEOF
)
}

# True if a skill name matches a policy pattern.
# Auto-detection: regex when it contains ^ or $, glob when it contains * ? [,
# otherwise exact string match. Regex uses search semantics, glob full-match.
pattern_matches() {
    local name="$1" pat="$2"
    case "$pat" in
        *'^'*|*'$'*)
            [[ "$name" =~ $pat ]] 2>/dev/null
            ;;
        *'*'*|*'?'*|*'['*)
            [[ "$name" == $pat ]]
            ;;
        *)
            [ "$name" = "$pat" ]
            ;;
    esac
}

# True if a skill name matches any pattern in a newline-separated list.
matches_any() {
    local name="$1" list="${2:-}"
    [ -n "$list" ] || return 1
    local pat
    while IFS= read -r pat; do
        [ -n "$pat" ] || continue
        if pattern_matches "$name" "$pat"; then
            return 0
        fi
    done <<< "$list"
    return 1
}

# True if a skill is allowed into an agent's pool.
# Exclusions always win; include only filters when non-empty.
skill_allowed() {
    local name="$1" agent="$2"
    if matches_any "$name" "${EXCLUDE[$agent]:-}"; then
        return 1
    fi
    if [ -n "${INCLUDE[$agent]:-}" ]; then
        matches_any "$name" "${INCLUDE[$agent]}" || return 1
    fi
    return 0
}

link_agent_pool() {
    local agent="$1"
    local agent_dir="$FOR_TOOLS_DIR/$agent"
    local name link excluded_count=0 linked=0
    local excluded=""

    mkdir -p "$agent_dir"
    if [ "$DRY_RUN" = 0 ]; then
        find "$agent_dir" -maxdepth 1 -type l -delete
    fi

    for src in "$VENDOR_DIR" "$LOCAL_DIR" "$PRIVATE_DIR"; do
        for skill_dir in "$src"/*; do
            [ -d "$skill_dir" ] || continue
            name="$(basename "$skill_dir")"
            if ! skill_allowed "$name" "$agent"; then
                excluded_count=$((excluded_count + 1))
                excluded+="$name "
                continue
            fi
            linked=$((linked + 1))
            link="$agent_dir/$name"
            if [ "$DRY_RUN" = 1 ]; then
                continue
            fi
            if [ -e "$link" ] && [ ! -L "$link" ]; then
                echo "  WARN: $link exists and is not a symlink — leaving untouched"
                continue
            fi
            ln -sfn "../../${src##*/}/$name" "$link"
        done
    done

    local verb="linked"
    [ "$DRY_RUN" = 1 ] && verb="would link"
    echo "  $agent: $verb $linked"
    if [ "$excluded_count" -gt 0 ]; then
        echo "         excluded $excluded_count: ${excluded% }"
    fi
}

rewire_tool_symlinks() {
    local agent link rel
    for agent in "${AGENTS[@]}"; do
        link="${SYMLINK_PATH[$agent]}"
        rel="${SYMLINK_REL[$agent]}"
        if [ "$DRY_RUN" = 1 ]; then
            echo "  [dry-run] $link -> $rel"
            continue
        fi
        if [ -L "$link" ]; then
            rm -f "$link"
        elif [ -e "$link" ]; then
            echo "  WARN: $link is a real file — leaving untouched"
            continue
        fi
        ln -s "$rel" "$link"
        echo "  $link -> $rel"
    done
}

echo "Starting skills linking process (policy: ${POLICY_FILE##*/})"
load_policy

mkdir -p "$FOR_TOOLS_DIR" "$PRIVATE_DIR"
# Remove legacy union symlinks at the for-tools root (pre-per-agent layout).
if [ "$DRY_RUN" = 0 ]; then
    find "$FOR_TOOLS_DIR" -maxdepth 1 -type l -delete
fi

echo ""
echo "Building per-agent skill pools:"
for agent in "${AGENTS[@]}"; do
    link_agent_pool "$agent"
done

echo ""
echo "Rewiring tool symlinks:"
rewire_tool_symlinks

echo ""
if [ "$DRY_RUN" = 1 ]; then
    echo "Done (dry-run — nothing changed)."
else
    echo "Done! Run with --dry-run to preview, or re-run to relink after policy edits."
fi