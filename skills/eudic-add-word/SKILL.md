---
name: "eudic-add-word"
description: "Add a single word with details to Eudic. Invoke when user wants to add a word with context or rating."
---

# Eudic Add Word

Adds a single word with optional context, star rating, and category.

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py add-word --word WORD [--star RATING] [--context-line CONTEXT] [--category-ids ID1 ID2 ...] [--language LANGUAGE]
```

## Parameters

- `--word`: (Required) The word to add.
- `--star`: (Optional) Star rating (0-5).
- `--context-line`: (Optional) Context sentence.
- `--category-ids`: (Optional) List of category IDs.
- `--language`: (Optional) Language code (default: 'en').
