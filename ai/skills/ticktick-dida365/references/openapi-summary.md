# TickTick / Dida365 OpenAPI Summary

## Base URLs

- TickTick (global): `https://api.ticktick.com/open/v1`
- Dida365 (CN): `https://api.dida365.com/open/v1`

Override via:
- `TICKTICK_BASE_URL`
- `TICKTICK_AUTH_URL`
- `TICKTICK_TOKEN_URL`

## OAuth2

- Authorization: `GET https://ticktick.com/oauth/authorize`
- Token: `POST https://ticktick.com/oauth/token`

Auth request parameters:
- `client_id`
- `scope` (space-separated): `tasks:read tasks:write`
- `redirect_uri`
- `response_type=code`
- `state`

Token exchange:
- Basic Auth header: `Authorization: Basic base64(client_id:client_secret)`
- Form body:
  - `grant_type=authorization_code`
  - `code`
  - `redirect_uri`

Refresh:
- Basic Auth header
- Form body:
  - `grant_type=refresh_token`
  - `refresh_token`

OpenAPI auth header:
- `Authorization: Bearer <access_token>`

## Projects

- List: `GET /project`
- Get: `GET /project/{projectId}`
- Get with tasks: `GET /project/{projectId}/data`
- Create: `POST /project`
- Update: `POST /project/{projectId}`
- Delete: `DELETE /project/{projectId}`

Common create/update fields:
- `name` (required for create)
- `color` (e.g. `#F18181`)
- `sortOrder` (int)
- `viewMode`: `list | kanban | timeline`
- `kind`: `TASK | NOTE`

## Tasks

- Get: `GET /project/{projectId}/task/{taskId}`
- Create: `POST /task`
- Update: `POST /task/{taskId}`
- Complete: `POST /project/{projectId}/task/{taskId}/complete`
- Delete: `DELETE /project/{projectId}/task/{taskId}`

Common create/update fields:
- `projectId`
- `title`
- `content`
- `desc`
- `startDate`, `dueDate`
- `timeZone` (e.g. `America/Los_Angeles`)
- `isAllDay` (boolean)
- `priority` (int): None `0`, Low `1`, Medium `3`, High `5`
- `status` (int): Normal `0`, Completed `2`

Date/time format:
- `"yyyy-MM-dd'T'HH:mm:ssZ"` (example: `2019-11-13T03:00:00+0000`)

