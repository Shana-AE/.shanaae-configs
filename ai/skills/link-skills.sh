#!/bin/bash

BASE_DIR="/home/shanaae/.shanaae/configs/ai/skills"
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
        ln -s "$skill_dir" "$FOR_TOOLS_DIR/$skill_name"
        echo "  Linked: $skill_name"
    fi
done

echo ""
echo "Linking skills from local..."
for skill_dir in "$LOCAL_DIR"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        ln -s "$skill_dir" "$FOR_TOOLS_DIR/$skill_name"
        echo "  Linked: $skill_name"
    fi
done

echo ""
echo "Done! Skills have been linked to for-tools."
echo "Total skills linked: $(ls -la "$FOR_TOOLS_DIR" | grep -c "^l")"
