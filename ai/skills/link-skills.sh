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
# Bash 3.2+ compatible (macOS /bin/bash, Linux bash 4/5). No associative
# arrays, no gnu-only flags.
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

AGENTS=(opencode claude codex trae pi)
POLICY_TMP="$(mktemp -d "${TMPDIR:-/tmp}/link-skills.XXXXXX")"
trap 'rm -rf "$POLICY_TMP"' EXIT

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

# Absolute path of a tool's `skills` symlink inside the repo...
tool_link_path() {
    case "$1" in
        opencode) echo "$BASE_DIR/../../.config/opencode/skills" ;;
        claude)   echo "$BASE_DIR/../../.claude/skills" ;;
        codex)    echo "$BASE_DIR/../../.codex/skills" ;;
        trae)     echo "$BASE_DIR/../../.trae/skills" ;;
        pi)       echo "$BASE_DIR/../../pi/skills" ;;
    esac
}

# ...and the repo-relative target it should point to.
tool_link_rel() {
    case "$1" in
        opencode) echo "../../ai/skills/for-tools/opencode" ;;
        claude)   echo "../ai/skills/for-tools/claude" ;;
        codex)    echo "../ai/skills/for-tools/codex" ;;
        trae)     echo "../ai/skills/for-tools/trae" ;;
        pi)       echo "../ai/skills/for-tools/pi" ;;
    esac
}

# Parse the policy into per-agent pattern lists:
#   $POLICY_TMP/<agent>.include   $POLICY_TMP/<agent>.exclude
# python3 emits one "agent<TAB>kind<TAB>pattern" line per effective rule
# (defaults expanded to every agent), warnings on stderr.
load_policy() {
    if [ ! -f "$POLICY_FILE" ]; then
        echo "WARN: $POLICY_FILE not found — no per-agent filtering (full sets everywhere)."
        return 0
    fi
    local agent kind pat
    while IFS=$'\t' read -r agent kind pat; do
        [ -z "$agent" ] && continue
        printf '%s\n' "$pat" >> "$POLICY_TMP/$agent.$kind"
    done < <(python3 - "$POLICY_FILE" <<'PYEOF'
import json, sys

agents = ["opencode", "claude", "codex", "trae", "pi"]
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

# True if a skill name matches any pattern line in a file.
matches_file() {
    local name="$1" file="$2" pat
    [ -f "$file" ] || return 1
    while IFS= read -r pat; do
        [ -n "$pat" ] || continue
        if pattern_matches "$name" "$pat"; then
            return 0
        fi
    done < "$file"
    return 1
}

# True if a skill is allowed into an agent's pool.
# Exclusions always win; include only filters when non-empty.
skill_allowed() {
    local name="$1" agent="$2"
    if matches_file "$name" "$POLICY_TMP/$agent.exclude"; then
        return 1
    fi
    if [ -s "$POLICY_TMP/$agent.include" ]; then
        matches_file "$name" "$POLICY_TMP/$agent.include" || return 1
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
            if [ "$DRY_RUN" = 1 ]; then
                continue
            fi
            link="$agent_dir/$name"
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
        link="$(tool_link_path "$agent")"
        rel="$(tool_link_rel "$agent")"
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