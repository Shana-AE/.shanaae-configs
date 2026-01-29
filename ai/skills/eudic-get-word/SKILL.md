---
name: "eudic-get-word"
description: "Get details of a single word from Eudic. Invoke when user wants to query a specific word."
---

# Eudic Get Word

Retrieves details for a specific word from Eudic.

## Usage

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py get-word --word WORD [--language LANGUAGE]
```

## Parameters

- `--word`: (Required) The word to query.
- `--language`: (Optional) Language code (default: 'en').
