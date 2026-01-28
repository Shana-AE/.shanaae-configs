---
name: "eudic-get-words"
description: "Get words from a Eudic wordbook. Invoke when user wants to list words in a category or study list."
---

# Eudic Get Words

Retrieves words from a specific Eudic category (wordbook).

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py get-words [--category-id ID] [--language LANGUAGE] [--page PAGE] [--page-size SIZE]
```

## Parameters

- `--category-id`: (Optional) Category ID (default: '0' for default wordbook).
- `--language`: (Optional) Language code (default: 'en').
- `--page`: (Optional) Page number (default: 1).
- `--page-size`: (Optional) Words per page (default: 100).
