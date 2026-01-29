#!/usr/bin/env python3
import argparse
import base64
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer


DEFAULT_BASE_URL = "https://api.ticktick.com/open/v1"
DEFAULT_AUTH_URL = "https://ticktick.com/oauth/authorize"
DEFAULT_TOKEN_URL = "https://ticktick.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://localhost:8000/callback"


def json_print(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def load_env_file(path):
    if not path or not os.path.exists(path):
        return {}
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                env[key] = value
    return env


def save_env_file(path, updates):
    existing = load_env_file(path)
    existing.update({k: v for k, v in updates.items() if v is not None})
    lines = []
    for key in sorted(existing.keys()):
        val = existing[key]
        safe_val = val.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"{key}='{safe_val}'\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_env(env_file_map, key):
    return os.environ.get(key) or env_file_map.get(key)


def _http_request(url, method, headers=None, params=None, json_body=None, form_body=None, timeout=30):
    final_url = url
    if params:
        parts = list(urllib.parse.urlparse(final_url))
        query = dict(urllib.parse.parse_qsl(parts[4], keep_blank_values=True))
        query.update({k: v for k, v in params.items() if v is not None})
        parts[4] = urllib.parse.urlencode(query)
        final_url = urllib.parse.urlunparse(parts)

    req_headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    elif form_body is not None:
        data = urllib.parse.urlencode(form_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = urllib.request.Request(final_url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="ignore") if raw else ""
            if not text:
                return resp.status, None
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, {"raw": text}
    except urllib.error.HTTPError as e:
        raw = e.read()
        text = raw.decode("utf-8", errors="ignore") if raw else ""
        payload = None
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = {"raw": text}
        return e.code, payload or {"error": e.reason}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def _basic_auth_header(client_id, client_secret):
    auth_str = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(auth_str).decode("ascii")


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        code = (qs.get("code") or [None])[0]
        self.server.auth_code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        if code:
            self.wfile.write(b"Authorization received. You can close this tab.\n")
        else:
            self.wfile.write(b"Missing authorization code.\n")

    def log_message(self, format, *args):
        return


class TickTickSession:
    def __init__(self, env_file):
        self.env_file = env_file
        self.env_map = load_env_file(env_file)
        self.base_url = get_env(self.env_map, "TICKTICK_BASE_URL") or DEFAULT_BASE_URL
        self.auth_url = get_env(self.env_map, "TICKTICK_AUTH_URL") or DEFAULT_AUTH_URL
        self.token_url = get_env(self.env_map, "TICKTICK_TOKEN_URL") or DEFAULT_TOKEN_URL
        self.client_id = get_env(self.env_map, "TICKTICK_CLIENT_ID")
        self.client_secret = get_env(self.env_map, "TICKTICK_CLIENT_SECRET")
        self.access_token = get_env(self.env_map, "TICKTICK_ACCESS_TOKEN")
        self.refresh_token = get_env(self.env_map, "TICKTICK_REFRESH_TOKEN")

    def _save_tokens(self, access_token, refresh_token=None):
        updates = {"TICKTICK_ACCESS_TOKEN": access_token}
        if refresh_token:
            updates["TICKTICK_REFRESH_TOKEN"] = refresh_token
        if self.client_id:
            updates.setdefault("TICKTICK_CLIENT_ID", self.client_id)
        if self.client_secret:
            updates.setdefault("TICKTICK_CLIENT_SECRET", self.client_secret)
        if self.base_url and self.base_url != DEFAULT_BASE_URL:
            updates.setdefault("TICKTICK_BASE_URL", self.base_url)
        if self.auth_url and self.auth_url != DEFAULT_AUTH_URL:
            updates.setdefault("TICKTICK_AUTH_URL", self.auth_url)
        if self.token_url and self.token_url != DEFAULT_TOKEN_URL:
            updates.setdefault("TICKTICK_TOKEN_URL", self.token_url)
        save_env_file(self.env_file, updates)
        self.env_map.update(updates)
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token

    def refresh_access_token(self):
        if not self.refresh_token:
            return False, {"error": "Missing TICKTICK_REFRESH_TOKEN"}
        if not self.client_id or not self.client_secret:
            return False, {"error": "Missing TICKTICK_CLIENT_ID or TICKTICK_CLIENT_SECRET"}

        headers = {
            "Authorization": _basic_auth_header(self.client_id, self.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        status, payload = _http_request(
            self.token_url,
            "POST",
            headers=headers,
            form_body={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
        )
        if status and 200 <= status < 300 and isinstance(payload, dict) and payload.get("access_token"):
            self._save_tokens(payload.get("access_token"), payload.get("refresh_token"))
            return True, {"success": True}
        return False, {"error": "Failed to refresh access token", "status_code": status, "body": payload}

    def ensure_access_token(self):
        if self.access_token:
            return True, None
        return False, {"error": "Missing TICKTICK_ACCESS_TOKEN. Run `auth` first or export token env vars."}

    def openapi_request(self, method, endpoint, json_body=None, retry_on_401=True):
        ok, err = self.ensure_access_token()
        if not ok:
            return 0, err

        url = self.base_url.rstrip("/") + "/" + endpoint.lstrip("/")
        headers = {"Authorization": f"Bearer {self.access_token}"}
        status, payload = _http_request(url, method, headers=headers, json_body=json_body)
        if status == 401 and retry_on_401:
            refreshed, _ = self.refresh_access_token()
            if refreshed:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                status, payload = _http_request(url, method, headers=headers, json_body=json_body)
        return status, payload

    def start_auth_flow(self, redirect_uri=DEFAULT_REDIRECT_URI, scopes=("tasks:read", "tasks:write"), open_browser=True):
        if not self.client_id or not self.client_secret:
            return False, {"error": "Missing TICKTICK_CLIENT_ID or TICKTICK_CLIENT_SECRET"}

        state = secrets.token_urlsafe(16)
        params = {
            "client_id": self.client_id,
            "scope": " ".join(scopes),
            "state": state,
            "redirect_uri": redirect_uri,
            "response_type": "code",
        }
        auth_link = self.auth_url + "?" + urllib.parse.urlencode(params)

        server = HTTPServer(("localhost", urllib.parse.urlparse(redirect_uri).port or 8000), _OAuthCallbackHandler)
        server.auth_code = None

        def serve_once():
            server.handle_request()

        t = threading.Thread(target=serve_once, daemon=True)
        t.start()

        if open_browser:
            webbrowser.open(auth_link)
        else:
            json_print({"authorization_url": auth_link})

        deadline = time.time() + 300
        while time.time() < deadline and not server.auth_code:
            time.sleep(0.2)

        code = server.auth_code
        if not code:
            return False, {"error": "Timed out waiting for authorization code"}

        headers = {
            "Authorization": _basic_auth_header(self.client_id, self.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        status, payload = _http_request(self.token_url, "POST", headers=headers, form_body=form)
        if status and 200 <= status < 300 and isinstance(payload, dict) and payload.get("access_token"):
            self._save_tokens(payload.get("access_token"), payload.get("refresh_token"))
            return True, {"success": True}
        return False, {"error": "Failed to exchange code for token", "status_code": status, "body": payload}


def _parse_datetime(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _iter_project_tasks(project_data):
    if not isinstance(project_data, dict):
        return
    tasks = project_data.get("tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict):
                yield task


def cmd_auth(args):
    session = TickTickSession(args.env_file)
    ok, payload = session.start_auth_flow(open_browser=(not args.no_open_browser))
    if ok:
        json_print({"success": True, "env_file": args.env_file})
        return 0
    json_print(payload)
    return 1


def cmd_projects_list(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("GET", "/project")
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_projects_get(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("GET", f"/project/{args.project_id}")
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_projects_create(args):
    session = TickTickSession(args.env_file)
    body = {"name": args.name}
    if args.color:
        body["color"] = args.color
    if args.view_mode:
        body["viewMode"] = args.view_mode
    if args.kind:
        body["kind"] = args.kind
    if args.sort_order is not None:
        body["sortOrder"] = args.sort_order
    status, payload = session.openapi_request("POST", "/project", json_body=body)
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_projects_update(args):
    session = TickTickSession(args.env_file)
    body = {}
    if args.name:
        body["name"] = args.name
    if args.color:
        body["color"] = args.color
    if args.view_mode:
        body["viewMode"] = args.view_mode
    if args.kind:
        body["kind"] = args.kind
    if args.sort_order is not None:
        body["sortOrder"] = args.sort_order
    status, payload = session.openapi_request("POST", f"/project/{args.project_id}", json_body=body)
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_projects_delete(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("DELETE", f"/project/{args.project_id}")
    if 200 <= status < 300:
        json_print({"success": True})
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_tasks_get(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("GET", f"/project/{args.project_id}/task/{args.task_id}")
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_tasks_create(args):
    session = TickTickSession(args.env_file)
    body = {
        "projectId": args.project_id,
        "title": args.title,
    }
    if args.content:
        body["content"] = args.content
    if args.desc:
        body["desc"] = args.desc
    if args.due:
        body["dueDate"] = args.due
    if args.start:
        body["startDate"] = args.start
    if args.time_zone:
        body["timeZone"] = args.time_zone
    if args.all_day:
        body["isAllDay"] = True
    if args.priority is not None:
        body["priority"] = args.priority
    status, payload = session.openapi_request("POST", "/task", json_body=body)
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_tasks_update(args):
    session = TickTickSession(args.env_file)
    body = {}
    if args.project_id:
        body["projectId"] = args.project_id
    if args.title:
        body["title"] = args.title
    if args.content is not None:
        body["content"] = args.content
    if args.desc is not None:
        body["desc"] = args.desc
    if args.due is not None:
        body["dueDate"] = args.due
    if args.start is not None:
        body["startDate"] = args.start
    if args.time_zone is not None:
        body["timeZone"] = args.time_zone
    if args.all_day is not None:
        body["isAllDay"] = bool(args.all_day)
    if args.priority is not None:
        body["priority"] = args.priority
    status, payload = session.openapi_request("POST", f"/task/{args.task_id}", json_body=body)
    if 200 <= status < 300:
        json_print(payload)
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_tasks_complete(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("POST", f"/project/{args.project_id}/task/{args.task_id}/complete")
    if 200 <= status < 300:
        json_print({"success": True})
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def cmd_tasks_delete(args):
    session = TickTickSession(args.env_file)
    status, payload = session.openapi_request("DELETE", f"/project/{args.project_id}/task/{args.task_id}")
    if 200 <= status < 300:
        json_print({"success": True})
        return 0
    json_print({"error": "Request failed", "status_code": status, "body": payload})
    return 1


def _get_all_project_data(session):
    status, projects = session.openapi_request("GET", "/project")
    if not (200 <= status < 300) or not isinstance(projects, list):
        return False, {"error": "Failed to list projects", "status_code": status, "body": projects}
    out = []
    for p in projects:
        pid = p.get("id") if isinstance(p, dict) else None
        if not pid:
            continue
        s, data = session.openapi_request("GET", f"/project/{pid}/data")
        if 200 <= s < 300 and isinstance(data, dict):
            out.append({"project": p, "data": data})
    return True, out


def cmd_tasks_list(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1

    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            if args.with_due_only and not task.get("dueDate"):
                continue
            matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})

    if args.sort_by_due:
        def due_key(x):
            due = _parse_datetime((x.get("task") or {}).get("dueDate"))
            return due or datetime.max.replace(tzinfo=datetime.now().astimezone().tzinfo)
        matches.sort(key=due_key)

    if args.limit is not None:
        matches = matches[: args.limit]

    json_print({"matches": matches, "count": len(matches)})
    return 0


def cmd_tasks_search(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1
    term = (args.term or "").lower()
    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            hay = " ".join(
                [
                    str(task.get("title") or ""),
                    str(task.get("content") or ""),
                    str(task.get("desc") or ""),
                ]
            ).lower()
            if term and term not in hay:
                continue
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})
    json_print({"matches": matches, "count": len(matches)})
    return 0


def cmd_tasks_by_priority(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1
    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            if task.get("priority") == args.priority:
                matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})
    json_print({"matches": matches, "count": len(matches)})
    return 0


def _due_filter(task, target_date, now_local):
    due = _parse_datetime(task.get("dueDate"))
    if not due:
        return False
    due_local = due.astimezone(now_local.tzinfo) if now_local.tzinfo else due
    return due_local.date() == target_date


def cmd_tasks_due_today(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1
    now = datetime.now().astimezone()
    today = date.today()
    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            if _due_filter(task, today, now):
                matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})
    json_print({"matches": matches, "count": len(matches)})
    return 0


def cmd_tasks_due_in_days(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1
    now = datetime.now().astimezone()
    target = date.today() + timedelta(days=args.days)
    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            if _due_filter(task, target, now):
                matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})
    json_print({"matches": matches, "count": len(matches), "target_date": target.isoformat()})
    return 0


def cmd_tasks_overdue(args):
    session = TickTickSession(args.env_file)
    ok, all_data = _get_all_project_data(session)
    if not ok:
        json_print(all_data)
        return 1
    now = datetime.now().astimezone()
    matches = []
    for entry in all_data:
        project = entry.get("project") or {}
        data = entry.get("data") or {}
        for task in _iter_project_tasks(data):
            if not args.include_completed and task.get("status") in (2, "2"):
                continue
            due = _parse_datetime(task.get("dueDate"))
            if not due:
                continue
            due_local = due.astimezone(now.tzinfo) if now.tzinfo else due
            if due_local < now:
                matches.append({"project": {"id": project.get("id"), "name": project.get("name")}, "task": task})
    json_print({"matches": matches, "count": len(matches)})
    return 0


def cmd_tasks_batch_create(args):
    session = TickTickSession(args.env_file)
    if args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    else:
        tasks = json.loads(args.json)
    if not isinstance(tasks, list):
        json_print({"error": "Input must be a JSON array of task objects"})
        return 1

    results = []
    for item in tasks:
        if not isinstance(item, dict):
            results.append({"success": False, "error": "Task item must be an object", "item": item})
            continue
        pid = item.get("projectId") or item.get("project_id") or item.get("projectId".lower())
        title = item.get("title")
        if not pid or not title:
            results.append({"success": False, "error": "Missing projectId or title", "item": item})
            continue
        body = dict(item)
        body["projectId"] = pid
        body["title"] = title
        status, payload = session.openapi_request("POST", "/task", json_body=body)
        ok = 200 <= status < 300
        results.append({"success": ok, "status_code": status, "response": payload, "request": {"projectId": pid, "title": title}})
    json_print({"results": results, "count": len(results)})
    return 0


def build_parser():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_env_file = os.path.join(script_dir, ".env")

    p = argparse.ArgumentParser(prog="ticktick_api.py")
    p.add_argument("--env-file", default=default_env_file)
    sub = p.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth")
    auth.add_argument("--no-open-browser", action="store_true")
    auth.set_defaults(func=cmd_auth)

    projects = sub.add_parser("projects")
    projects_sub = projects.add_subparsers(dest="projects_cmd", required=True)

    pr_list = projects_sub.add_parser("list")
    pr_list.set_defaults(func=cmd_projects_list)

    pr_get = projects_sub.add_parser("get")
    pr_get.add_argument("--project-id", required=True)
    pr_get.set_defaults(func=cmd_projects_get)

    pr_create = projects_sub.add_parser("create")
    pr_create.add_argument("--name", required=True)
    pr_create.add_argument("--color")
    pr_create.add_argument("--view-mode", choices=["list", "kanban", "timeline"])
    pr_create.add_argument("--kind", choices=["TASK", "NOTE", "task", "note"])
    pr_create.add_argument("--sort-order", type=int)
    pr_create.set_defaults(func=cmd_projects_create)

    pr_update = projects_sub.add_parser("update")
    pr_update.add_argument("--project-id", required=True)
    pr_update.add_argument("--name")
    pr_update.add_argument("--color")
    pr_update.add_argument("--view-mode", choices=["list", "kanban", "timeline"])
    pr_update.add_argument("--kind", choices=["TASK", "NOTE", "task", "note"])
    pr_update.add_argument("--sort-order", type=int)
    pr_update.set_defaults(func=cmd_projects_update)

    pr_delete = projects_sub.add_parser("delete")
    pr_delete.add_argument("--project-id", required=True)
    pr_delete.set_defaults(func=cmd_projects_delete)

    tasks = sub.add_parser("tasks")
    tasks_sub = tasks.add_subparsers(dest="tasks_cmd", required=True)

    tk_get = tasks_sub.add_parser("get")
    tk_get.add_argument("--project-id", required=True)
    tk_get.add_argument("--task-id", required=True)
    tk_get.set_defaults(func=cmd_tasks_get)

    tk_create = tasks_sub.add_parser("create")
    tk_create.add_argument("--project-id", required=True)
    tk_create.add_argument("--title", required=True)
    tk_create.add_argument("--content")
    tk_create.add_argument("--desc")
    tk_create.add_argument("--start")
    tk_create.add_argument("--due")
    tk_create.add_argument("--time-zone")
    tk_create.add_argument("--all-day", action="store_true")
    tk_create.add_argument("--priority", type=int, choices=[0, 1, 3, 5])
    tk_create.set_defaults(func=cmd_tasks_create)

    tk_update = tasks_sub.add_parser("update")
    tk_update.add_argument("--task-id", required=True)
    tk_update.add_argument("--project-id")
    tk_update.add_argument("--title")
    tk_update.add_argument("--content")
    tk_update.add_argument("--desc")
    tk_update.add_argument("--start")
    tk_update.add_argument("--due")
    tk_update.add_argument("--time-zone")
    tk_update.add_argument("--all-day", type=int, choices=[0, 1])
    tk_update.add_argument("--priority", type=int, choices=[0, 1, 3, 5])
    tk_update.set_defaults(func=cmd_tasks_update)

    tk_complete = tasks_sub.add_parser("complete")
    tk_complete.add_argument("--project-id", required=True)
    tk_complete.add_argument("--task-id", required=True)
    tk_complete.set_defaults(func=cmd_tasks_complete)

    tk_delete = tasks_sub.add_parser("delete")
    tk_delete.add_argument("--project-id", required=True)
    tk_delete.add_argument("--task-id", required=True)
    tk_delete.set_defaults(func=cmd_tasks_delete)

    tk_list = tasks_sub.add_parser("list")
    tk_list.add_argument("--include-completed", action="store_true")
    tk_list.add_argument("--with-due-only", action="store_true")
    tk_list.add_argument("--sort-by-due", action="store_true")
    tk_list.add_argument("--limit", type=int)
    tk_list.set_defaults(func=cmd_tasks_list)

    tk_search = tasks_sub.add_parser("search")
    tk_search.add_argument("--term", required=True)
    tk_search.add_argument("--include-completed", action="store_true")
    tk_search.set_defaults(func=cmd_tasks_search)

    tk_prio = tasks_sub.add_parser("by-priority")
    tk_prio.add_argument("--priority", type=int, required=True, choices=[0, 1, 3, 5])
    tk_prio.add_argument("--include-completed", action="store_true")
    tk_prio.set_defaults(func=cmd_tasks_by_priority)

    tk_due_today = tasks_sub.add_parser("due-today")
    tk_due_today.add_argument("--include-completed", action="store_true")
    tk_due_today.set_defaults(func=cmd_tasks_due_today)

    tk_due_in_days = tasks_sub.add_parser("due-in-days")
    tk_due_in_days.add_argument("--days", type=int, required=True)
    tk_due_in_days.add_argument("--include-completed", action="store_true")
    tk_due_in_days.set_defaults(func=cmd_tasks_due_in_days)

    tk_overdue = tasks_sub.add_parser("overdue")
    tk_overdue.add_argument("--include-completed", action="store_true")
    tk_overdue.set_defaults(func=cmd_tasks_overdue)

    tk_batch = tasks_sub.add_parser("batch-create")
    group = tk_batch.add_mutually_exclusive_group(required=True)
    group.add_argument("--json")
    group.add_argument("--json-file")
    tk_batch.set_defaults(func=cmd_tasks_batch_create)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
