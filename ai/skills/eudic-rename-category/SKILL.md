---
name: "eudic-rename-category"
description: "Rename an existing Eudic wordbook/category. Invoke when user wants to rename a wordbook."
---

# Eudic Rename Category

Renames an existing category (wordbook) in Eudic.

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py rename-category --id ID --name NEW_NAME [--language LANGUAGE]
```

## Parameters

- `--id`: (Required) ID of the category to rename.
- `--name`: (Required) New name for the category.
- `--language`: (Optional) Language code (default: 'en').
