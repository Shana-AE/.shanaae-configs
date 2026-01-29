---
name: "eudic-delete-category"
description: "Delete a Eudic wordbook/category. Invoke when user wants to remove or delete a wordbook."
---

# Eudic Delete Category

Deletes a category (wordbook) from Eudic.

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py delete-category --id ID [--name NAME] [--language LANGUAGE]
```

## Parameters

- `--id`: (Required) ID of the category to delete.
- `--name`: (Optional) Name of the category (if required by API).
- `--language`: (Optional) Language code (default: 'en').
