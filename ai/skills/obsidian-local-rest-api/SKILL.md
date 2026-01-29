---
name: obsidian-local-rest-api
description: Manage Obsidian notes (read, write, list, search, delete) using the Local REST API and a Python client.
---

# Obsidian Local REST API Skill

This skill provides a Python CLI client for interacting with your Obsidian vault via the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api).

## Prerequisites

- **Environment Variable**: `OBSIDIAN_API_KEY` must be set.
- **Base URL**: Defaults to `http://127.0.0.1:27123` (HTTP). Set `OBSIDIAN_BASE_URL` to override.
- **SSL Verification**: Defaults to `false`. Set `OBSIDIAN_VERIFY_SSL` to `true` if using HTTPS with valid certs.

## Usage

The client script is located at `client.py` in this skill directory. You should execute it using `python3`.

### Commands

#### 1. Read a Note

Get the content of a specific note.

```bash
python3 client.py read "Folder/Note Name.md"
```

#### 2. List Notes

List files and directories in a specific path (default root).

```bash
python3 client.py list "Folder Name"
```

#### 3. Update/Create a Note

Write content to a note. Supports `overwrite` (default) or `append` modes.

**Overwrite (Create/Replace):**

```bash
python3 client.py update "New Note.md" "# Title\n\nContent here."
```

**Append:**

```bash
python3 client.py update "Log.md" "\n- New log entry" --mode append
```

#### 4. Search Notes

Search for text across the vault.

```bash
python3 client.py search "search query"
```

#### 5. Daily Note

Interact with today's daily note.

**Read:**

```bash
python3 client.py daily read
```

**Append:**

```bash
python3 client.py daily append "- [ ] New task for today"
```

#### 6. Delete a Note

Permanently delete a note.

```bash
python3 client.py delete "Note To Delete.md"
```

## Examples

**Task**: "Add a task to my daily note."
**Action**:

1. Check if `OBSIDIAN_API_KEY` is set.
2. Run: `python3 client.py daily append "- [ ] The task"`

**Task**: "Find notes about 'Python' and list them."
**Action**:

1. Run: `python3 client.py search "Python"`
