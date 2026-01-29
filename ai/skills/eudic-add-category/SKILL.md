---
name: "eudic-add-category"
description: "Create a new Eudic wordbook/category. Invoke when user wants to create a new wordbook or category."
---

# Eudic Add Category

Creates a new category (wordbook) in Eudic.

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py add-category --name NAME [--language LANGUAGE]
```

## Parameters

- `--name`: (Required) Name of the new category.
- `--language`: (Optional) Language code (default: 'en').
