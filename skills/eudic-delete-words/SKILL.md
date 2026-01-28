---
name: "eudic-delete-words"
description: "Delete words from a Eudic wordbook. Invoke when user wants to remove words from a study list."
---

# Eudic Delete Words

Deletes multiple words from a Eudic category (wordbook).

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py delete-words --words WORD1 WORD2 ... [--category-id ID] [--language LANGUAGE]
```

## Parameters

- `--words`: (Required) List of words to delete (space separated).
- `--category-id`: (Optional) Category ID (default: '0').
- `--language`: (Optional) Language code (default: 'en').
