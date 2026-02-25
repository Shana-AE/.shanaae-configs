#!/usr/bin/env python3
import os
import json
import re

# Paths are relative to the project root (where the script is run from usually, 
# but we should make it robust to where it's called)
# Assuming the script is at ai/skills/local/setup-configs/scripts/setup_configs.py
# And project root is ../../../..
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../../../"))
SECRETS_FILE = os.path.join(PROJECT_ROOT, ".secrets")

CONFIG_MAPPINGS = [
    {
        "example": "ai/mcp/trae.json.example",
        "target": "ai/mcp/trae.json",
        "replacements": {
            "YOUR_FIGMA_API_KEY": "FIGMA_ACCESS_TOKEN",
            "YOUR_CONTEXT7_API_KEY": "CONTEXT7_API_KEY",
            "YOUR_EUDIC_AUTH_TOKEN": "EUDIC_TOKEN",
            "YOUR_GITHUB_TOKEN": "GITHUB_TOKEN_MCP",
            "YOUR_OBSIDIAN_API_KEY": "OBSIDIAN_API_KEY"
        }
    },
    {
        "example": ".config/opencode/opencode.json.example",
        "target": ".config/opencode/opencode.json",
        "replacements": {
            "YOUR_CONTEXT7_API_KEY": "CONTEXT7_API_KEY",
            "YOUR_GITHUB_TOKEN": "GITHUB_TOKEN_MCP",
            "YOUR_Z_AI_API_KEY": "BIGMODEL_API_KEY",
            "YOUR_ZHIPU_API_KEY": "BIGMODEL_API_KEY",
            "YOUR_QINIU_API_KEY": "QINIU_AI_API_KEY"
        }
    }
]

def load_secrets(filepath):
    """Loads secrets from a .env style file."""
    secrets = {}
    if not os.path.exists(filepath):
        print(f"Error: Secrets file not found at {filepath}")
        return secrets
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Handle export prefix if present
            if line.startswith('export '):
                line = line[7:]
            
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                secrets[key.strip()] = value
    return secrets

def generate_config(mapping, secrets):
    example_path = os.path.join(PROJECT_ROOT, mapping["example"])
    target_path = os.path.join(PROJECT_ROOT, mapping["target"])
    
    if not os.path.exists(example_path):
        print(f"Warning: Example file not found: {mapping['example']}")
        return

    print(f"Processing {mapping['example']} -> {mapping['target']}...")
    
    with open(example_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for placeholder, secret_key in mapping["replacements"].items():
        if secret_key in secrets:
            secret_value = secrets[secret_key]
            # Simple string replacement
            content = content.replace(placeholder, secret_value)
            print(f"  Replaced {placeholder} with value from {secret_key}")
        else:
            print(f"  Warning: Secret key '{secret_key}' not found in .secrets for placeholder '{placeholder}'")

    # Ensure target directory exists
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated {mapping['target']}")

def main():
    print(f"Loading secrets from {SECRETS_FILE}...")
    secrets = load_secrets(SECRETS_FILE)
    
    if not secrets:
        print("No secrets loaded. Aborting.")
        return

    for mapping in CONFIG_MAPPINGS:
        generate_config(mapping, secrets)

if __name__ == "__main__":
    main()
