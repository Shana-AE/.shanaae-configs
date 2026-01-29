---
name: eudic-api-operations
description: "Perform operations on Eudic wordbooks/categories using the Eudic API. Invoke when user wants to rename, delete, or get categories, or manage words directly via API commands."
---

# Eudic API Operations

This skill provides a comprehensive CLI for interacting with the Eudic Study List API. It supports managing categories (wordbooks) and words.

## Prerequisites

- **Environment Variable**: `EUDIC_TOKEN` must be set with your Eudic API Authorization token.

## Usage

The script is located at: `/home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py`

### General Syntax

```bash
python3 /home/shanaae/.trae/skills/eudic-api-operations/scripts/eudic_api.py <COMMAND> [OPTIONS]
```

### Commands

#### 1. Category Management

*   **Get Categories**
    *   `get-categories [--language LANGUAGE]`
    *   Example: `get-categories`

*   **Add Category**
    *   `add-category --name NAME [--language LANGUAGE]`
    *   Example: `add-category --name "My New Book"`

*   **Rename Category**
    *   `rename-category --id ID --name NEW_NAME [--language LANGUAGE]`
    *   Example: `rename-category --id 12345 --name "Renamed Book"`

*   **Delete Category**
    *   `delete-category --id ID [--name NAME] [--language LANGUAGE]`
    *   Example: `delete-category --id 12345`

#### 2. Word Management

*   **Get Words**
    *   `get-words [--category-id ID] [--language LANGUAGE] [--page PAGE] [--page-size SIZE]`
    *   Example: `get-words --category-id 0 --page 1`

*   **Add Words (Batch)**
    *   `add-words --words WORD1 WORD2 ... [--category-id ID] [--language LANGUAGE]`
    *   Example: `add-words --words apple banana --category-id 0`

*   **Delete Words**
    *   `delete-words --words WORD1 WORD2 ... [--category-id ID] [--language LANGUAGE]`
    *   Example: `delete-words --words apple banana`

*   **Add Word (Single)**
    *   `add-word --word WORD [--star RATING] [--context-line CONTEXT] [--category-ids ID1 ID2 ...] [--language LANGUAGE]`
    *   Example: `add-word --word apple --star 5 --context-line "I ate an apple."`

*   **Get Word Details**
    *   `get-word --word WORD [--language LANGUAGE]`
    *   Example: `get-word --word apple`

## Language Codes

*   `en` (English - Default)
*   `fr` (French)
*   `de` (German)
*   `es` (Spanish)
