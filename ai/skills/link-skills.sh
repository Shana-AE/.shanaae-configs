#!/bin/bash

# Portable: resolve base dir from this script's location so it works on any OS.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
VENDOR_DIR="$BASE_DIR/vendor"
LOCAL_DIR="$BASE_DIR/local"
PRIVATE_DIR="$BASE_DIR/private"
FOR_TOOLS_DIR="$BASE_DIR/for-tools"

echo "Starting skills linking process..."
echo "Source directories:"
echo "  Vendor:  $VENDOR_DIR"
echo "  Local:   $LOCAL_DIR"
echo "  Private: $PRIVATE_DIR  (gitignored — never committed to remote)"
echo "Target directory:"
echo "  For-tools: $FOR_TOOLS_DIR  (gitignored — fully generated)"
echo ""

for dir in "$FOR_TOOLS_DIR" "$PRIVATE_DIR"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    fi
done

echo "Removing existing links in for-tools..."
find "$FOR_TOOLS_DIR" -maxdepth 1 -type l -delete

echo ""
echo "Linking skills from vendor..."
for skill_dir in "$VENDOR_DIR"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        ln -s "../vendor/$skill_name" "$FOR_TOOLS_DIR/$skill_name"
        echo "  Linked: $skill_name"
    fi
done

echo ""
echo "Linking skills from local..."
for skill_dir in "$LOCAL_DIR"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        ln -s "../local/$skill_name" "$FOR_TOOLS_DIR/$skill_name"
        echo "  Linked: $skill_name"
    fi
done

echo ""
echo "Linking skills from private..."
# private/ is gitignored — these skills stay machine-local and never reach the remote repo.
for skill_dir in "$PRIVATE_DIR"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        ln -s "../private/$skill_name" "$FOR_TOOLS_DIR/$skill_name"
        echo "  Linked: $skill_name"
    fi
done

if [ -z "$(ls -A "$PRIVATE_DIR" 2>/dev/null)" ]; then
    echo "  (private/ is empty — no private skills to link)"
fi

echo ""
echo "Done! Skills have been linked to for-tools."
echo "Total skills linked: $(find "$FOR_TOOLS_DIR" -maxdepth 1 -type l | wc -l | tr -d ' ')"
