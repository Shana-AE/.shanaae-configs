---
name: ticktick-dida365
description: Manage TickTick / 滴答清单 (Dida365) via the official OpenAPI (OAuth2). Use when you need to list/create/update/delete projects or tasks, complete tasks, or search/filter tasks (due/overdue/priority/batch create).
---

# TickTick / Dida365 Operations

Use this skill to execute real TickTick (国际版) / 滴答清单 Dida365 (国内版) operations through the OpenAPI with OAuth2 tokens.

## Quick Start

1. Ensure credentials are present:
   - `TICKTICK_CLIENT_ID`
   - `TICKTICK_CLIENT_SECRET`
2. Authenticate once (creates/updates a local `.env` next to the script by default):
   - `python3 scripts/ticktick_api.py auth`
3. Run operations (all output is JSON):
   - `python3 scripts/ticktick_api.py projects list`
   - `python3 scripts/ticktick_api.py tasks create --project-id ... --title ...`

If you already have tokens, set:
- `TICKTICK_ACCESS_TOKEN`
- `TICKTICK_REFRESH_TOKEN`

## Dida365 (滴答清单国内版) Switch

Set these env vars before `auth` and before API calls:

```bash
export TICKTICK_BASE_URL='https://api.dida365.com/open/v1'
export TICKTICK_AUTH_URL='https://dida365.com/oauth/authorize'
export TICKTICK_TOKEN_URL='https://dida365.com/oauth/token'
```

Defaults (TickTick global):
- `TICKTICK_BASE_URL=https://api.ticktick.com/open/v1`
- `TICKTICK_AUTH_URL=https://ticktick.com/oauth/authorize`
- `TICKTICK_TOKEN_URL=https://ticktick.com/oauth/token`

## Workflow Decision Tree

1. If tokens are missing or expired:
   - Run `python3 scripts/ticktick_api.py auth`
2. If you need to identify a project:
   - Run `python3 scripts/ticktick_api.py projects list`
3. Then perform the target operation:
   - Project CRUD: `projects get|create|update|delete`
   - Task CRUD: `tasks get|create|update|delete`
   - Complete: `tasks complete`
   - Search/filter: `tasks search|due-today|due-in-days|overdue|by-priority`
   - Batch create: `tasks batch-create --json ...` or `--json-file ...`

## Common Commands

Projects:
- List: `python3 scripts/ticktick_api.py projects list`
- Create: `python3 scripts/ticktick_api.py projects create --name 'Inbox' --color '#F18181'`

Tasks:
- Create: `python3 scripts/ticktick_api.py tasks create --project-id '...' --title 'Buy milk' --due '2026-01-29T09:00:00+0800'`
- Complete: `python3 scripts/ticktick_api.py tasks complete --project-id '...' --task-id '...'`
- Search (client-side): `python3 scripts/ticktick_api.py tasks search --term 'meeting'`

## Reference

Read [openapi-summary.md](references/openapi-summary.md) when you need field formats (date/time, priority/status) or endpoint details.
