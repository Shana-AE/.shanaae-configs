#!/usr/bin/env python3
"""Sync MCP server config + enabled/disabled status across opencode and Claude Code.

Source of truth: mcp_servers.json (next to this script).
Targets:
  - opencode : ~/.config/opencode/opencode.jsonc  -> "mcp" section, {env:VAR}, enabled flags
               (surgical replace: preserves all comments + other top-level keys)
  - claude   : ~/.claude.json                     -> "mcpServers", resolved plaintext, disabled flags
               (JSON merge: preserves all other top-level keys)
  - mcp.json : ~/.claude/mcp.json (repo, symlinked)-> "mcpServers", ${VAR} shell syntax, disabled flags
               (full rewrite of mcpServers only)

Usage:
  python3 sync_mcp.py                      # dry-run (print diff, write nothing)
  python3 sync_mcp.py --apply              # write all targets (with .bak backups)
  python3 sync_mcp.py --apply --target opencode   # limit to one target
  python3 sync_mcp.py --check              # exit 1 if drift (for CI / hooks)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from difflib import unified_diff

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../../../"))
CANONICAL = os.path.join(SCRIPT_DIR, "mcp_servers.json")
SECRETS_FILE = os.path.join(CONFIGS_ROOT, ".secrets")

OPENCODE = os.path.expanduser("~/.config/opencode/opencode.jsonc")
CLAUDE_JSON = os.path.expanduser("~/.claude.json")
MCP_JSON = os.path.expanduser("~/.claude/mcp.json")

TARGETS = {"opencode": OPENCODE, "claude": CLAUDE_JSON, "mcp.json": MCP_JSON}
ENV_PATTERN = re.compile(r"\{env:([A-Z0-9_]+)\}")


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
_secrets_cache: dict[str, str] | None = None


def load_secrets() -> dict[str, str]:
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    out: dict[str, str] = {}
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                out[k.strip()] = v
    _secrets_cache = out
    return out


def env_value(name: str) -> str:
    if name in os.environ:
        return os.environ[name]
    return load_secrets().get(name, "")


def transform(value: str, style: str) -> str:
    """Transform {env:VAR} per target style: opencode | plain | shell."""
    def sub(m: re.Match) -> str:
        var = m.group(1)
        if style == "opencode":
            return m.group(0)  # keep {env:VAR}
        if style == "shell":
            return "${" + var + "}"
        return env_value(var)  # plain
    return ENV_PATTERN.sub(sub, value)


def transform_obj(obj, style):
    if isinstance(obj, str):
        return transform(obj, style)
    if isinstance(obj, dict):
        return {k: transform_obj(v, style) for k, v in obj.items()}
    if isinstance(obj, list):
        return [transform_obj(v, style) for v in obj]
    return obj


# --------------------------------------------------------------------------- #
# Canonical load
# --------------------------------------------------------------------------- #
def load_canonical() -> tuple[list[dict], set[str]]:
    with open(CANONICAL, encoding="utf-8") as f:
        data = json.load(f)
    servers = data["servers"]
    ordered = sorted(
        servers.items(),
        key=lambda kv: (not kv[1].get("enabled", False), kv[0].lower()),
    )
    exclude_opencode = set(data.get("exclude_from_opencode", []))
    return ordered, exclude_opencode


# --------------------------------------------------------------------------- #
# Emitters
# --------------------------------------------------------------------------- #
def to_opencode(name, spec) -> tuple[str | None, dict]:
    entry = {"type": "local" if spec.get("type") == "local" else "remote"}
    if spec.get("type") == "local":
        entry["command"] = transform_obj(spec.get("command", []), "opencode")
        if spec.get("env"):
            entry["environment"] = transform_obj(spec["env"], "opencode")
    else:
        entry["url"] = transform(spec["url"], "opencode")
        if spec.get("headers"):
            entry["headers"] = transform_obj(spec["headers"], "opencode")
    if not spec.get("enabled", False):
        entry["enabled"] = False
    return spec.get("comment"), entry


def to_claude(name, spec) -> dict:
    entry: dict = {}
    if spec.get("type") == "local":
        cmd = transform_obj(spec.get("command", []), "plain")
        entry["type"] = "stdio"
        entry["command"] = cmd[0]
        entry["args"] = cmd[1:]
        entry["env"] = transform_obj(spec.get("env") or {}, "plain")
    else:
        entry["type"] = "http"
        entry["url"] = transform(spec["url"], "plain")
        if spec.get("headers"):
            entry["headers"] = transform_obj(spec["headers"], "plain")
    if not spec.get("enabled", False):
        entry["disabled"] = True
    return entry


def to_mcpjson(name, spec) -> dict:
    entry: dict = {}
    if spec.get("type") == "local":
        cmd = transform_obj(spec.get("command", []), "shell")
        entry["command"] = cmd[0]
        entry["args"] = cmd[1:]
        entry["env"] = transform_obj(spec.get("env") or {}, "shell")
    else:
        entry["url"] = transform(spec["url"], "shell")
        if spec.get("headers"):
            entry["headers"] = transform_obj(spec["headers"], "shell")
    if not spec.get("enabled", False):
        entry["disabled"] = True
    return entry


# --------------------------------------------------------------------------- #
# JSONC surgical edit (opencode.jsonc)
# --------------------------------------------------------------------------- #
def _skip_comment(text, i):
    if text[i] == "/" and i + 1 < len(text) and text[i + 1] == "/":
        nl = text.find("\n", i)
        return nl if nl != -1 else len(text)
    if text[i] == "/" and i + 1 < len(text) and text[i + 1] == "*":
        end = text.find("*/", i + 2)
        return end + 2 if end != -1 else len(text)
    return None


def _skip_string(text, i):
    if text[i] != '"':
        return None
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == '"':
            return j + 1
        j += 1
    return len(text)


def find_top_level_key(text, key):
    """Return (key_start_idx, value_end_brace_idx) for top-level `key`, or None."""
    i, n, depth = 0, len(text), 0
    pat = '"' + key + '"'
    while i < n:
        c = text[i]
        skip = _skip_comment(text, i)
        if skip is not None:
            i = skip
            continue
        if c == '"':
            if depth == 1 and text[i:i + len(pat)] == pat:
                k = i + len(pat)
                while k < n and text[k] in " \t\r\n":
                    k += 1
                if k < n and text[k] == ":":
                    k += 1
                    while k < n and text[k] in " \t\r\n":
                        k += 1
                    if k < n and text[k] == "{":
                        end = _match_braces(text, k)
                        if end is not None:
                            return (i, end)
            ns = _skip_string(text, i)
            i = ns if ns is not None else i + 1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        i += 1
    return None


def _match_braces(text, open_idx):
    """Given index of '{', return index of matching '}' (comment/string aware)."""
    depth, i, n = 0, open_idx, len(text)
    while i < n:
        skip = _skip_comment(text, i)
        if skip is not None:
            i = skip
            continue
        c = text[i]
        if c == '"':
            ns = _skip_string(text, i)
            i = ns if ns is not None else i + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def render_opencode(ordered, exclude) -> str:
    """Build the new 'mcp' block text (with leading '  \"mcp\":' and closing brace)."""
    with open(OPENCODE, encoding="utf-8") as f:
        text = f.read()
    span = find_top_level_key(text, "mcp")
    entries = []
    for name, spec in ordered:
        if name in exclude:
            continue
        comment, entry = to_opencode(name, spec)
        body = json.dumps(entry, indent=2, ensure_ascii=False)
        lines = body.split("\n")
        padded = [lines[0]] + ["    " + ln for ln in lines[1:]]
        block = "    " + json.dumps(name, ensure_ascii=False) + ": " + "\n".join(padded)
        if comment:
            cmt_lines = comment.split("\n")
            cmt = "\n".join("    // " + cl for cl in cmt_lines)
            block = cmt + "\n" + block
        entries.append(block)
    inner = ",\n".join(entries)
    new_block = '  "mcp": {\n' + inner + "\n  }"
    if span is None:
        # no mcp key yet: append before final closing brace
        # (placeholder kept for clarity)
        # find last top-level }
        i, n, depth = 0, len(text), 0
        last = None
        while i < n:
            skip = _skip_comment(text, i)
            if skip is not None:
                i = skip
                continue
            c = text[i]
            if c == '"':
                ns = _skip_string(text, i)
                i = ns if ns is not None else i + 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    last = i
            i += 1
        if last is None:
            raise RuntimeError("could not find root closing brace in opencode.jsonc")
        # insert before last }, with a leading comma if previous non-ws char isn't { ,
        # find char before last
        j = last - 1
        while j >= 0 and text[j] in " \t\r\n":
            j -= 1
        insert = ("" if text[j] in "{" else "\n") + new_block
        return text[:last] + insert + "\n" + text[last:]
    # Splice from the START OF THE LINE containing "mcp" (not the quote mark),
    # so new_block's own indentation replaces the old indent cleanly -> idempotent.
    key_idx, end_idx = span
    line_start = text.rfind("\n", 0, key_idx) + 1
    return text[:line_start] + new_block + text[end_idx + 1:]


def render_claude_json(ordered) -> str:
    with open(CLAUDE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    data["mcpServers"] = {name: to_claude(name, spec) for name, spec in ordered}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_mcp_json(ordered) -> str:
    data = {"mcpServers": {name: to_mcpjson(name, spec) for name, spec in ordered}}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- #
# Diff / write
# --------------------------------------------------------------------------- #
SECRET_HINT = re.compile(r"(ghp_[A-Za-z0-9]{4})[A-Za-z0-9]+|("
                         r"gho_|github_pat_|ctx7sk-)[A-Za-z0-9_-]+|("
                         r"[0-9a-f]{8})[0-9a-f]+\.[A-Za-z0-9]{4}[A-Za-z0-9]+")


def redact(s: str) -> str:
    def sub(m):
        tok = m.group(0)
        return tok[:8] + "…" + f"({len(tok)}c)"
    return SECRET_HINT.sub(sub, s)


def do_target(name, new_text, apply):
    path = TARGETS[name]
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == new_text:
        print(f"  [{name}] already in sync — no changes.")
        return False
    diff = list(unified_diff(
        old.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=f"{name} (current)", tofile=f"{name} (target)", n=1))
    print(f"  [{name}] DRIFT — changes:")
    sys.stdout.write(redact("".join(diff)))
    if apply:
        bak = path + ".bak." + datetime.now().strftime("%Y%m%dT%H%M%S")
        if os.path.exists(path):
            shutil.copy2(path, bak)
            os.chmod(bak, 0o600)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
        if path == CLAUDE_JSON:
            os.chmod(path, 0o600)
        print(f"  [{name}] written (backup: {bak})")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write changes (default is dry-run)")
    ap.add_argument("--target", choices=list(TARGETS), help="limit to one target")
    ap.add_argument("--repo-only", action="store_true",
                    help="scope to repo-managed targets only (opencode + mcp.json), skip ~/.claude.json")
    ap.add_argument("--check", action="store_true", help="exit 1 if any drift (dry-run, for CI / hooks)")
    args = ap.parse_args()

    ordered, exclude = load_canonical()
    mode = "CHECK" if args.check else ("APPLY" if args.apply else "DRY-RUN")
    print(f"== mcp-sync ({mode}) ==")
    print(f"   canonical : {os.path.relpath(CANONICAL, CONFIGS_ROOT)}")
    print(f"   secrets   : {'ok' if os.path.exists(SECRETS_FILE) else 'MISSING'} ({len(load_secrets())} keys)")
    print(f"   servers   : {len(ordered)} ({sum(1 for _, s in ordered if s.get('enabled'))} enabled, "
          f"{sum(1 for _, s in ordered if not s.get('enabled'))} disabled)")

    renders = {
        "opencode": render_opencode(ordered, exclude),
        "claude": render_claude_json(ordered),
        "mcp.json": render_mcp_json(ordered),
    }
    targets = ["opencode", "mcp.json"] if args.repo_only else (
        [args.target] if args.target else list(TARGETS))
    drifted = False
    for t in targets:
        if do_target(t, renders[t], args.apply and not args.check):
            drifted = True

    if args.check:
        sys.exit(1 if drifted else 0)
    if not args.apply:
        print("\n(dry-run only. Run with --apply to write.)")
    elif drifted:
        print("\nDone. Restart opencode / Claude Code to pick up changes.")


if __name__ == "__main__":
    main()
