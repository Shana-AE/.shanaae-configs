---
name: "eudic-add-words"
description: "Add multiple words to a Eudic wordbook. Invoke when user wants to add a list of words."
---

# Eudic Add Words

Adds multiple words to a Eudic category (wordbook).

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py add-words --words WORD1 WORD2 ... [--category-id ID] [--language LANGUAGE]
```

## Parameters

- `--words`: (Required) List of words to add (space separated).
- `--category-id`: (Optional) Category ID (default: '0').
- `--language`: (Optional) Language code (default: 'en').
