#!/usr/bin/env python3
r"""Sync MCP server config + enabled/disabled status across opencode, Claude Code, Codex, Cursor, and Qoder.

Source of truth: mcp_servers.json (next to this script).
Targets:
  - opencode : ~/.config/opencode/opencode.jsonc  -> "mcp" section, {env:VAR}, enabled flags
               (surgical replace: preserves all comments + other top-level keys)
  - claude   : ~/.claude.json                     -> "mcpServers", resolved plaintext, disabled flags
               (JSON merge: preserves all other top-level keys)
  - mcp.json : ~/.claude/mcp.json (repo, symlinked)-> "mcpServers", ${VAR} shell syntax, disabled flags
               (full rewrite of mcpServers only)
  - codex    : ~/.codex/config.toml (repo, symlinked) -> [mcp_servers.*] TOML tables, env_var refs,
               enabled flags (sentinel-block merge: preserves base settings + provider tables)
  - cursor   : ~/.cursor/mcp.json + %USERPROFILE%\.cursor\mcp.json -> "mcpServers",
               resolved plaintext, disabled flags (VS Code-style IDE config)
  - qoder    : ~/.qoder/mcp.json + %USERPROFILE%\.qoder\{,cn}\mcp.json -> same as cursor

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
CODEX_CONFIG = os.path.expanduser("~/.codex/config.toml")

# IDE (VS Code-style mcp.json) targets. Secrets are resolved to plaintext like
# the claude runtime target (these IDEs have no {env:VAR} substitution in
# mcp.json). Windows profile paths are included only when /mnt/c is mounted.
def _win_user_home() -> str:
    return "/mnt/c/Users/shana"


def _ide_targets(wsl_path: str, *win_rels: str) -> list[str]:
    paths = [os.path.expanduser(wsl_path)]
    if os.path.isdir("/mnt/c"):
        for rel in win_rels:
            paths.append(os.path.join(_win_user_home(), rel))
    return paths

CURSOR_TARGETS = _ide_targets("~/.cursor/mcp.json", ".cursor/mcp.json")
QODER_TARGETS = _ide_targets("~/.qoder/mcp.json", ".qoder/mcp.json", ".qoder-cn/mcp.json")

TARGETS = {
    "opencode": [OPENCODE],
    "claude": [CLAUDE_JSON],
    "mcp.json": [MCP_JSON],
    "codex": [CODEX_CONFIG],
    "cursor": CURSOR_TARGETS,
    "qoder": QODER_TARGETS,
}
# Targets whose rendered config contains resolved secrets — chmod 0600 on write.
SECRET_BEARING = {"claude", "cursor", "qoder"}
ENV_PATTERN = re.compile(r"\{env:([A-Z0-9_]+)\}")
# Codex sentinel delimiters — canonical [mcp_servers.*] tables between these
# lines are regenerated from the source of truth; foreign content placed here
# by other writers (e.g. the ChatGPT app) is preserved verbatim.
CODEX_BEGIN = "# BEGIN mcp-sync"
CODEX_END = "# END mcp-sync"
_CODEX_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*$")
# ``[mcp_servers.<name>]`` tables injected by the ChatGPT desktop app's Codex
# integration (NOT managed by mcp-sync). They are preserved across renders.
# If the app adds new MCP servers, add their names here. Any other
# ``[mcp_servers.<name>]`` that is no longer in the canonical source is treated
# as a removed server and dropped.
CODEX_APP_MCP_SERVERS = frozenset({"node_repl", "computer-use"})


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
        # opencode-specific overrides let a server use {file:...} secrets (resolved by
        # opencode at spawn time) so MCPs work without the token being in the shell/session env.
        # Other targets still use the base command/env. transform() leaves {file:...} untouched.
        cmd_src = spec.get("command_opencode", spec.get("command", []))
        env_src = spec.get("env_opencode", spec.get("env"))
        entry["command"] = transform_obj(cmd_src, "opencode")
        if env_src:
            entry["environment"] = transform_obj(env_src, "opencode")
    else:
        entry["url"] = transform(spec["url"], "opencode")
        headers_src = spec.get("headers_opencode", spec.get("headers"))
        if headers_src:
            entry["headers"] = transform_obj(headers_src, "opencode")
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


def to_ide(name, spec) -> dict:
    """VS Code-style IDE mcp.json entry (Cursor / Qoder): resolved plaintext
    secrets (no {env:} substitution in these IDEs' mcp.json), disabled flag."""
    entry: dict = {}
    if spec.get("type") == "local":
        cmd = transform_obj(spec.get("command", []), "plain")
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


def _toml_str(s: str) -> str:
    """Emit a TOML basic string (double-quoted). json.dumps is a valid subset."""
    return json.dumps(str(s), ensure_ascii=False)


def _toml_inline_map(pairs: list[tuple[str, str]]) -> str:
    """Emit a TOML inline table: { "key" = "value", ... }"""
    return "{ " + ", ".join(f"{_toml_str(k)} = {_toml_str(v)}" for k, v in pairs) + " }"


def to_codex(name, spec) -> str:
    """Emit a [mcp_servers.<name>] TOML table for Codex config.toml.

    Secret-free / portable: uses env-name references (env_vars, bearer_token_env_var,
    env_http_headers) rather than resolved values, so the file is safe to commit.
    """
    lines = [f"[mcp_servers.{name}]"]
    if spec.get("type") == "local":
        cmd = spec.get("command", [])
        lines.append(f"command = {_toml_str(cmd[0])}")
        if len(cmd) > 1:
            lines.append("args = [" + ", ".join(_toml_str(c) for c in cmd[1:]) + "]")
        # Split env into literal values (env = {...}) vs env-var refs (env_vars = [...]).
        env = spec.get("env") or {}
        literals: list[tuple[str, str]] = []
        env_vars: list[str] = []
        for k, v in env.items():
            m = ENV_PATTERN.search(v) if isinstance(v, str) else None
            if m:
                env_vars.append(m.group(1))
            else:
                literals.append((k, str(v)))
        if literals:
            lines.append("env = " + _toml_inline_map(literals))
        if env_vars:
            lines.append("env_vars = [" + ", ".join(_toml_str(v) for v in env_vars) + "]")
    else:  # remote / streamable HTTP
        lines.append(f"url = {_toml_str(spec['url'])}")
        headers = spec.get("headers") or {}
        bearer_var: str | None = None
        static_headers: list[tuple[str, str]] = []
        env_headers: list[tuple[str, str]] = []
        for k, v in headers.items():
            if k.lower() == "authorization" and isinstance(v, str):
                m = re.match(r"[Bb]earer\s+\{env:([A-Z0-9_]+)\}", v)
                if m:
                    bearer_var = m.group(1)
                    continue
            if isinstance(v, str):
                mv = ENV_PATTERN.search(v)
                if mv:
                    env_headers.append((k, mv.group(1)))
                    continue
            static_headers.append((k, str(v)))
        if bearer_var:
            lines.append(f"bearer_token_env_var = {_toml_str(bearer_var)}")
        if static_headers:
            lines.append("http_headers = " + _toml_inline_map(static_headers))
        if env_headers:
            lines.append("env_http_headers = " + _toml_inline_map(env_headers))
    if not spec.get("enabled", False):
        lines.append("enabled = false")
    return "\n".join(lines)


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


def render_ide_json(ordered) -> str:
    data = {"mcpServers": {name: to_ide(name, spec) for name, spec in ordered}}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _segment_codex_sentinel(inner, canonical_names):
    """Split sentinel inner text into ordered segments.

    Returns a list of ('canonical', name) | ('foreign', text) tuples.
    Canonical ``[mcp_servers.<name>]`` tables are regenerated by the caller.
    Tables injected by the ChatGPT app (named in ``CODEX_APP_MCP_SERVERS``,
    plus their sub-tables) and all non-mcp_servers content (``notify``,
    ``[marketplaces]``, ``[plugins]``, ``[features]``) are preserved verbatim.
    Any other ``[mcp_servers.<name>]`` not in the canonical source is treated
    as a removed server and dropped (along with its sub-tables). Leading
    comment/blank lines belonging to a managed server are consumed.
    """
    lines = inner.split("\n")
    segs = []
    pending = []

    def flush():
        nonlocal pending
        if pending:
            t = "\n".join(pending).rstrip()
            if t.strip():
                segs.append(("foreign", t))
            pending = []

    def classify(header):
        """Return ('canonical', name) | ('foreign', None) | ('drop', None)."""
        if not header.startswith("mcp_servers."):
            return ("foreign", None)
        rem = header[len("mcp_servers."):]
        if "." in rem:
            parent = rem.split(".", 1)[0]
            if parent in CODEX_APP_MCP_SERVERS or parent in canonical_names:
                return ("foreign", None)
            return ("drop", None)
        if rem in canonical_names:
            return ("canonical", rem)
        if rem in CODEX_APP_MCP_SERVERS:
            return ("foreign", None)
        return ("drop", None)

    def pop_trailing_comments():
        while pending and (pending[-1].lstrip().startswith("#") or pending[-1].strip() == ""):
            pending.pop()

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        m = _CODEX_HEADER_RE.match(line)
        if m:
            header = m.group(1).strip()
            body = []
            j = i + 1
            while j < n and not _CODEX_HEADER_RE.match(lines[j]):
                body.append(lines[j])
                j += 1
            block_lines = [line] + body
            kind, name = classify(header)
            if kind == "canonical":
                pop_trailing_comments()
                flush()
                segs.append(("canonical", name))
            elif kind == "foreign":
                flush()
                segs.append(("foreign", "\n".join(block_lines).rstrip()))
            else:  # drop: removed server — discard its leading comments too
                pop_trailing_comments()
                flush()
            i = j
        else:
            pending.append(line)
            i += 1
    flush()
    return segs


def render_codex(ordered) -> str:
    """Tolerant merge of [mcp_servers.*] into ~/.codex/config.toml.

    Regenerates the canonical ``[mcp_servers.<name>]`` tables between the
    ``# BEGIN/END mcp-sync`` sentinels from the source of truth, while
    preserving any *foreign* content other writers place inside the sentinel
    region (e.g. the ChatGPT desktop app's Codex integration injects ``notify``,
    ``node_repl``, ``computer-use``, ``[marketplaces]``, ``[plugins]``,
    ``[features]``). Base settings and provider tables outside the sentinels
    are preserved verbatim. If the sentinels are missing, a canonical block is
    appended at the end.
    """
    with open(CODEX_CONFIG, encoding="utf-8") as f:
        text = f.read()
    canonical_names = {name for name, _ in ordered}
    spec_by_name = dict(ordered)

    def emit_canon(name, blocks):
        spec = spec_by_name[name]
        comment = spec.get("comment")
        chunk = []
        if comment:
            for cl in comment.split("\n"):
                chunk.append("# " + cl if cl else "#")
        chunk.append(to_codex(name, spec))
        blocks.append("\n".join(chunk))

    bi = text.find(CODEX_BEGIN)
    ei = text.find(CODEX_END)
    if bi != -1 and ei != -1 and ei > bi:
        inner_start = text.find("\n", bi) + 1
        inner = text[inner_start:ei].rstrip("\n")
        segs = _segment_codex_sentinel(inner, canonical_names)
        blocks = []
        seen = set()
        for kind, val in segs:
            if kind == "canonical":
                if val in seen:
                    continue
                seen.add(val)
                emit_canon(val, blocks)
            else:
                blocks.append(val)
        for name, _ in ordered:
            if name not in seen:
                seen.add(name)
                emit_canon(name, blocks)
        new_inner = "\n\n".join(b for b in blocks if b.strip()).rstrip()
        new_section = f"{CODEX_BEGIN}\n{new_inner}\n{CODEX_END}"
        line_start = text.rfind("\n", 0, bi) + 1
        line_end = text.find("\n", ei)
        if line_end == -1:
            line_end = len(text)
        return text[:line_start] + new_section + text[line_end:]
    # No sentinels: append a fresh canonical block at the end.
    blocks = []
    for name, spec in ordered:
        comment = spec.get("comment")
        if comment:
            for cl in comment.split("\n"):
                blocks.append("# " + cl if cl else "#")
        blocks.append(to_codex(name, spec))
        blocks.append("")
    inner = "\n".join(blocks).rstrip()
    new_section = f"{CODEX_BEGIN}\n{inner}\n{CODEX_END}"
    if text and not text.endswith("\n"):
        text += "\n"
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + new_section + "\n"


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
    """Write new_text to every path of a multi-path target (e.g. WSL + Windows)."""
    paths = TARGETS[name]
    changed_any = False
    for path in paths:
        old = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
        if old == new_text:
            print(f"  [{name}] {os.path.basename(path)} already in sync — no changes.")
            continue
        print(f"  [{name}] {path} DRIFT — changes:")
        diff = list(unified_diff(
            old.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"{name} (current)", tofile=f"{name} (target)", n=1))
        sys.stdout.write(redact("".join(diff)))
        changed_any = True
        if apply:
            bak = path + ".bak." + datetime.now().strftime("%Y%m%dT%H%M%S")
            if os.path.exists(path):
                shutil.copy2(path, bak)
                os.chmod(bak, 0o600)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            if name in SECRET_BEARING:
                os.chmod(path, 0o600)
            print(f"  [{name}] written (backup: {bak})")
    return changed_any


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
        "codex": render_codex(ordered),
        "cursor": render_ide_json(ordered),
        "qoder": render_ide_json(ordered),
    }
    targets = ["opencode", "mcp.json", "codex"] if args.repo_only else (
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
