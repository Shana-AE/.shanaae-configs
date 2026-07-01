#!/bin/bash

# Portable: resolve base dir from this script's location so it works on any OS.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
VENDOR_DIR="$BASE_DIR/vendor"
LOCAL_DIR="$BASE_DIR/local"
FOR_TOOLS_DIR="$BASE_DIR/for-tools"

echo "Starting skills linking process..."
echo "Source directories:"
echo "  Vendor: $VENDOR_DIR"
echo "  Local:  $LOCAL_DIR"
echo "Target directory:"
echo "  For-tools: $FOR_TOOLS_DIR"
echo ""

if [ ! -d "$FOR_TOOLS_DIR" ]; then
    echo "Creating for-tools directory..."
    mkdir -p "$FOR_TOOLS_DIR"
fi

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
echo "Done! Skills have been linked to for-tools."
echo "Total skills linked: $(find "$FOR_TOOLS_DIR" -maxdepth 1 -type l | wc -l | tr -d ' ')"
