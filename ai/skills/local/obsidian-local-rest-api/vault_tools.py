import argparse
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable
import re


API_KEY = os.environ.get("OBSIDIAN_API_KEY")
BASE_URL = os.environ.get("OBSIDIAN_BASE_URL", "http://127.0.0.1:27123").rstrip("/")
VERIFY_SSL = os.environ.get("OBSIDIAN_VERIFY_SSL", "false").lower() == "true"


def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not VERIFY_SSL:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _encode_path(path: str) -> str:
    return "/".join(urllib.parse.quote(part) for part in path.split("/"))


def _request(method: str, endpoint: str, *, params: dict[str, Any] | None = None, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    if not API_KEY:
        raise RuntimeError("OBSIDIAN_API_KEY 未设置")

    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req_headers: dict[str, str] = {"Authorization": f"Bearer {API_KEY}"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_ctx()) as resp:
            return resp.getcode(), dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        err_body = b""
        try:
            err_body = e.read()
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body[:500].decode('utf-8', errors='replace')}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL Error: {e.reason}") from e


def list_dir(path: str) -> list[str]:
    clean = path.strip("/")
    if clean:
        endpoint = f"/vault/{_encode_path(clean)}/"
    else:
        endpoint = "/vault/"
    status, _, data = _request("GET", endpoint, headers={"Accept": "application/json"})
    if status != 200:
        raise RuntimeError(f"list_dir 失败: {path} status={status}")
    payload = json.loads(data.decode("utf-8"))
    return payload.get("files", [])


def get_note_json(path: str) -> dict[str, Any]:
    encoded = _encode_path(path.strip("/"))
    status, headers, data = _request("GET", f"/vault/{encoded}", headers={"Accept": "application/vnd.olrapi.note+json"})
    if status != 200:
        raise RuntimeError(f"get_note_json 失败: {path} status={status}")
    ct = headers.get("Content-Type", "")
    if "json" not in ct and not data.strip().startswith(b"{"):
        raise RuntimeError(f"get_note_json 返回非 JSON: {path} content-type={ct}")
    return json.loads(data.decode("utf-8"))


def get_markdown(path: str) -> str:
    encoded = _encode_path(path.strip("/"))
    status, _, data = _request("GET", f"/vault/{encoded}", headers={"Accept": "text/markdown"})
    if status != 200:
        raise RuntimeError(f"get_markdown 失败: {path} status={status}")
    return data.decode("utf-8")


def put_markdown(path: str, content: str) -> None:
    encoded = _encode_path(path.strip("/"))
    _request("PUT", f"/vault/{encoded}", body=content.encode("utf-8"), headers={"Content-Type": "text/markdown"})


def get_file_bytes(path: str) -> tuple[bytes, str]:
    encoded = _encode_path(path.strip("/"))
    status, headers, data = _request("GET", f"/vault/{encoded}", headers={"Accept": "*/*"})
    if status != 200:
        raise RuntimeError(f"get_file_bytes 失败: {path} status={status}")
    return data, headers.get("Content-Type", "")


def put_file_bytes(path: str, data: bytes, content_type: str) -> None:
    encoded = _encode_path(path.strip("/"))
    _request("PUT", f"/vault/{encoded}", body=data, headers={"Content-Type": content_type or "application/octet-stream"})


def _guess_content_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".canvas") or lower.endswith(".json") or lower.endswith(".excalidraw"):
        return "application/json"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def _equivalent_content(src: bytes, dst: bytes, path: str) -> bool:
    lower = path.lower()
    if lower.endswith((".md", ".canvas", ".json", ".excalidraw", ".svg")):
        try:
            s = src.decode("utf-8")
            d = dst.decode("utf-8")
        except Exception:
            return src == dst

        def norm_text(t: str) -> str:
            t = t.replace("\r\n", "\n").replace("\r", "\n")
            lines = t.split("\n")
            while lines and lines[-1].strip() == "":
                lines.pop()
            return "\n".join(lines) + "\n"

        if lower.endswith((".canvas", ".json", ".excalidraw")):
            try:
                return json.loads(s) == json.loads(d)
            except Exception:
                return norm_text(s) == norm_text(d)

        return norm_text(s) == norm_text(d)

    return src == dst

def delete_file(path: str) -> None:
    encoded = _encode_path(path.strip("/"))
    _request("DELETE", f"/vault/{encoded}")


def search_simple(query: str, *, context_length: int = 120) -> list[dict[str, Any]]:
    status, _, data = _request("POST", "/search/simple/", params={"query": query, "contextLength": context_length}, headers={"Accept": "application/json"})
    if status != 200:
        raise RuntimeError(f"search_simple 失败: status={status}")
    return json.loads(data.decode("utf-8"))


@dataclass(frozen=True)
class VaultEntry:
    path: str
    kind: str


def walk_vault() -> tuple[list[str], list[str]]:
    dirs: list[str] = [""]
    all_dirs: list[str] = []
    all_files: list[str] = []

    while dirs:
        current = dirs.pop()
        all_dirs.append(current)
        children = list_dir(current)
        for child in children:
            if child.endswith("/"):
                child_dir = str(PurePosixPath(current) / child[:-1]).strip("/")
                if child_dir not in all_dirs:
                    dirs.append(child_dir)
            else:
                child_file = str(PurePosixPath(current) / child).strip("/")
                all_files.append(child_file)

    all_dirs = sorted(set(all_dirs), key=lambda x: (x.count("/"), x))
    all_files = sorted(set(all_files))
    return all_dirs, all_files


def normalize_for_hash(content: str) -> str:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan")
    scan.add_argument("--out", default="vault_inventory.json")

    dedupe = sub.add_parser("dedupe")
    dedupe.add_argument("--inventory", default="vault_inventory.json")
    dedupe.add_argument("--out", default="vault_duplicates.json")
    dedupe.add_argument("--ext", default="md")

    dedupe_actions = sub.add_parser("dedupe-actions")
    dedupe_actions.add_argument("--dups", default="vault_duplicates_md.json")
    dedupe_actions.add_argument("--out", default="vault_dedupe_actions.json")
    dedupe_actions.add_argument("--empty-policy", choices=["report", "archive"], default="report")

    plan_root = sub.add_parser("plan-root")
    plan_root.add_argument("--inventory", default="vault_inventory.json")
    plan_root.add_argument("--out", default="vault_root_migration_plan.json")
    plan_root.add_argument("--dest-base", default="Area/_root-migrated")

    apply_moves = sub.add_parser("apply-moves")
    apply_moves.add_argument("--plan", default="vault_root_migration_plan.json")
    apply_moves.add_argument("--out", default="vault_root_migration_changes.json")

    fix_links = sub.add_parser("fix-links")
    fix_links.add_argument("--inventory", default="vault_inventory_after.json")
    fix_links.add_argument("--root-plan", default="vault_root_migration_plan.json")
    fix_links.add_argument("--dest-base", default="Area/_root-migrated")
    fix_links.add_argument("--out", default="vault_link_fixes.json")

    apply_dedupe = sub.add_parser("apply-dedupe")
    apply_dedupe.add_argument("--actions", default="vault_dedupe_actions_after.json")
    apply_dedupe.add_argument("--inventory", default="vault_inventory_after.json")
    apply_dedupe.add_argument("--dedup-dir", default="Recycle/_dedup")
    apply_dedupe.add_argument("--out", default="vault_dedupe_changes.json")

    args = parser.parse_args()

    if args.cmd == "scan":
        started = time.time()
        dirs, files = walk_vault()
        payload = {"generatedAt": int(time.time()), "dirs": dirs, "files": files}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        duration = time.time() - started
        print(json.dumps({"ok": True, "dirCount": len(dirs), "fileCount": len(files), "seconds": round(duration, 2), "out": args.out}, ensure_ascii=False))
        return

    if args.cmd == "dedupe":
        inv = json.load(open(args.inventory, "r", encoding="utf-8"))
        files: list[str] = inv.get("files", [])
        target_ext = args.ext.lower().lstrip(".")
        targets = [p for p in files if p.lower().endswith(f".{target_ext}")]

        by_hash: dict[str, list[dict[str, Any]]] = {}
        failures: list[dict[str, Any]] = []

        started = time.time()
        for i, path in enumerate(targets, 1):
            try:
                note = get_note_json(path)
                content = note.get("content", "")
                stat = note.get("stat", {}) or {}
                normalized = normalize_for_hash(content)
                digest = sha256_text(normalized)
                by_hash.setdefault(digest, []).append(
                    {
                        "path": path,
                        "mtime": stat.get("mtime"),
                        "ctime": stat.get("ctime"),
                        "size": stat.get("size"),
                    }
                )
            except Exception as e:
                failures.append({"path": path, "error": str(e)})

            if i % 200 == 0:
                elapsed = time.time() - started
                print(json.dumps({"progress": i, "total": len(targets), "seconds": round(elapsed, 2)}, ensure_ascii=False))

        duplicates = {h: items for h, items in by_hash.items() if len(items) > 1}
        duration = time.time() - started
        out = {
            "generatedAt": int(time.time()),
            "ext": target_ext,
            "totalScanned": len(targets),
            "hashGroups": len(by_hash),
            "duplicateGroups": len(duplicates),
            "duplicates": duplicates,
            "failures": failures,
            "seconds": round(duration, 2),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "duplicateGroups": len(duplicates), "failures": len(failures), "seconds": round(duration, 2)}, ensure_ascii=False))
        return

    if args.cmd == "dedupe-actions":
        dups = json.load(open(args.dups, "r", encoding="utf-8"))
        groups: dict[str, list[dict[str, Any]]] = dups.get("duplicates", {})

        def is_recycle(path: str) -> bool:
            return path.startswith("Recycle/") or path.startswith("Recycle\\")

        def basename(path: str) -> str:
            return path.split("/")[-1].lower()

        empty_groups: list[dict[str, Any]] = []
        actionable: list[dict[str, Any]] = []

        for digest, items in groups.items():
            paths = [it["path"] for it in items]
            try:
                sample = get_markdown(paths[0])
            except Exception:
                sample = ""
            normalized = normalize_for_hash(sample)
            is_empty = normalized.strip() == ""

            base_counts: dict[str, int] = {}
            for p in paths:
                b = basename(p)
                base_counts[b] = base_counts.get(b, 0) + 1

            shared_basename = any(c > 1 for c in base_counts.values())
            has_recycle = any(is_recycle(p) for p in paths)
            has_non_recycle = any(not is_recycle(p) for p in paths)

            if is_empty:
                empty_groups.append({"hash": digest, "count": len(paths), "paths": sorted(paths)})
                if args.empty_policy != "archive":
                    continue

            if not (shared_basename or has_recycle):
                continue

            by_base: dict[str, list[dict[str, Any]]] = {}
            for it in items:
                by_base.setdefault(basename(it["path"]), []).append(it)

            keep_paths: list[str] = []
            move_paths: list[str] = []

            for b, same_name in by_base.items():
                same_name_sorted = sorted(
                    same_name,
                    key=lambda it: (
                        is_recycle(it["path"]),
                        it["path"].count("/"),
                        -(it.get("mtime") or 0),
                        it["path"],
                    ),
                )
                keep_paths.append(same_name_sorted[0]["path"])
                move_paths.extend(it["path"] for it in same_name_sorted[1:])

            if has_recycle and has_non_recycle:
                for p in paths:
                    if is_recycle(p) and p not in move_paths and p not in keep_paths:
                        move_paths.append(p)
                for p in list(keep_paths):
                    if is_recycle(p):
                        keep_paths.remove(p)
                        move_paths.append(p)

            move_paths = sorted(set(move_paths))
            keep_paths = sorted(set(keep_paths))

            if not move_paths:
                continue

            actionable.append({"hash": digest, "keep": keep_paths, "move": move_paths, "count": len(paths)})

        out = {
            "generatedAt": int(time.time()),
            "emptyPolicy": args.empty_policy,
            "actionableGroups": len(actionable),
            "emptyGroups": len(empty_groups),
            "actions": actionable,
            "empty": empty_groups,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "actionableGroups": len(actionable), "emptyGroups": len(empty_groups)}, ensure_ascii=False))
        return

    if args.cmd == "plan-root":
        inv = json.load(open(args.inventory, "r", encoding="utf-8"))
        all_files: list[str] = inv.get("files", [])
        root_items = list_dir("")
        keep_dirs = {"Area", "Inbox", "Recycle", "Resource", "assets", "templates"}
        keep_files = {"homepage.md"}
        root_dirs: list[str] = []
        root_files: list[str] = []

        for item in root_items:
            if item.endswith("/"):
                root_dirs.append(item[:-1])
            else:
                root_files.append(item)

        moves: list[dict[str, str]] = []
        keep: list[str] = []

        for d in sorted(root_dirs):
            if d in keep_dirs:
                keep.append(f"{d}/")
                continue
            dest_dir_name = d.strip()
            if dest_dir_name == "":
                dest_dir_name = "unnamed"
            dest_prefix = str(PurePosixPath(args.dest_base) / dest_dir_name).strip("/")
            src_prefix = f"{d}/"
            for f in all_files:
                if f.startswith(src_prefix):
                    rel = f[len(src_prefix) :]
                    new_path = str(PurePosixPath(dest_prefix) / rel).strip("/")
                    moves.append({"from": f, "to": new_path})

        for f in sorted(root_files):
            if f.lower() == "homepage.md":
                if f != "homepage.md":
                    moves.append({"from": f, "to": "homepage.md"})
                keep.append("homepage.md")
                continue
            if f.lower() in keep_files:
                keep.append(f)
                continue
            dest_name = f.strip()
            dest_path = str(PurePosixPath("Inbox") / dest_name).strip("/")
            moves.append({"from": f, "to": dest_path})

        plan = {
            "generatedAt": int(time.time()),
            "rootKeep": sorted(set(keep)),
            "rootSeen": {"dirs": sorted(root_dirs), "files": sorted(root_files)},
            "destBase": args.dest_base,
            "moves": moves,
            "moveCount": len(moves),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "moveCount": len(moves), "rootDirCount": len(root_dirs), "rootFileCount": len(root_files)}, ensure_ascii=False))
        return

    if args.cmd == "apply-moves":
        plan = json.load(open(args.plan, "r", encoding="utf-8"))
        moves: list[dict[str, str]] = plan.get("moves", [])

        changes: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        started = time.time()
        for i, mv in enumerate(moves, 1):
            src = mv["from"]
            dst = mv["to"]
            try:
                src_data, src_ct = get_file_bytes(src)
                dst_exists = True
                dst_data = b""
                try:
                    dst_data, _ = get_file_bytes(dst)
                except Exception:
                    dst_exists = False

                if dst_exists and not _equivalent_content(src_data, dst_data, dst):
                    conflicts.append({"from": src, "to": dst, "reason": "destination exists and differs"})
                    continue

                if not dst_exists:
                    put_file_bytes(dst, src_data, _guess_content_type(dst))

                verify_data, _ = get_file_bytes(dst)
                if not _equivalent_content(src_data, verify_data, dst):
                    raise RuntimeError("verify mismatch")

                delete_file(src)
                changes.append({"from": src, "to": dst, "bytes": len(src_data)})
            except Exception as e:
                failures.append({"from": src, "to": dst, "error": str(e)})

            if i % 50 == 0:
                elapsed = time.time() - started
                print(json.dumps({"progress": i, "total": len(moves), "seconds": round(elapsed, 2), "changes": len(changes), "conflicts": len(conflicts), "failures": len(failures)}, ensure_ascii=False))

        out = {
            "generatedAt": int(time.time()),
            "plan": args.plan,
            "moveCount": len(moves),
            "changes": changes,
            "conflicts": conflicts,
            "failures": failures,
            "seconds": round(time.time() - started, 2),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "changes": len(changes), "conflicts": len(conflicts), "failures": len(failures)}, ensure_ascii=False))
        return

    if args.cmd == "fix-links":
        inv = json.load(open(args.inventory, "r", encoding="utf-8"))
        files: list[str] = inv.get("files", [])
        md_files = [p for p in files if p.lower().endswith(".md")]

        root_plan = json.load(open(args.root_plan, "r", encoding="utf-8"))
        root_dirs: list[str] = root_plan.get("rootSeen", {}).get("dirs", [])
        keep_dirs = {"Area", "Inbox", "Recycle", "Resource", "assets", "templates"}
        moved_dirs = [d for d in root_dirs if d not in keep_dirs]

        mappings: list[tuple[str, str]] = []
        for d in moved_dirs:
            old = f"{d}/"
            new = f"{str(PurePosixPath(args.dest_base) / d.strip()).strip('/')}/"
            mappings.append((old, new))

        wikilink_pat = re.compile(r"(!?\[\[)([^\\]]+?)\]\]")
        mdlink_pat = re.compile(r"(\\]\\()([^\\)]+)(\\))")

        changes: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []

        def rewrite_target(target: str) -> tuple[str, int]:
            count = 0
            for old, new in mappings:
                if target.startswith(old):
                    target = new + target[len(old) :]
                    count += 1
            return target, count

        started = time.time()
        for i, path in enumerate(md_files, 1):
            try:
                content = get_markdown(path)
                changed = 0

                def repl_wiki(m: re.Match[str]) -> str:
                    nonlocal changed
                    prefix, target = m.group(1), m.group(2)
                    new_target, c = rewrite_target(target)
                    changed += c
                    return f"{prefix}{new_target}]]"

                def repl_md(m: re.Match[str]) -> str:
                    nonlocal changed
                    left, target, right = m.group(1), m.group(2), m.group(3)
                    new_target, c = rewrite_target(target)
                    changed += c
                    return f"{left}{new_target}{right}"

                new_content = wikilink_pat.sub(repl_wiki, content)
                new_content = mdlink_pat.sub(repl_md, new_content)

                if new_content != content:
                    put_markdown(path, new_content)
                    changes.append({"path": path, "replacements": changed})
            except Exception as e:
                ambiguous.append({"path": path, "error": str(e)})

            if i % 200 == 0:
                print(json.dumps({"progress": i, "total": len(md_files), "seconds": round(time.time() - started, 2), "changed": len(changes)}, ensure_ascii=False))

        out = {
            "generatedAt": int(time.time()),
            "inventory": args.inventory,
            "rootPlan": args.root_plan,
            "movedDirs": moved_dirs,
            "mappingCount": len(mappings),
            "changedFiles": len(changes),
            "changes": changes,
            "errors": ambiguous,
            "seconds": round(time.time() - started, 2),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "changedFiles": len(changes), "errors": len(ambiguous)}, ensure_ascii=False))
        return

    if args.cmd == "apply-dedupe":
        inv = json.load(open(args.inventory, "r", encoding="utf-8"))
        all_files: set[str] = set(inv.get("files", []))
        actions_doc = json.load(open(args.actions, "r", encoding="utf-8"))
        actions: list[dict[str, Any]] = actions_doc.get("actions", [])

        moved: list[dict[str, Any]] = []
        skipped_missing: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        mapping: dict[str, str] = {}

        dedup_dir = args.dedup_dir.strip("/")
        put_markdown(f"{dedup_dir}/.keep.md", "# _dedup\n")

        def dedup_dest(src: str) -> str:
            safe = src.replace("/", "／")
            return f"{dedup_dir}/{safe}"

        started = time.time()
        for i, g in enumerate(actions, 1):
            keep_list = g.get("keep", [])
            if isinstance(keep_list, str):
                keep_list = [keep_list]
            keep = keep_list[0] if keep_list else ""

            for src in g.get("move", []):
                mapping[src] = keep
                if src not in all_files:
                    skipped_missing.append({"from": src, "reason": "missing"})
                    continue

                dst = dedup_dest(src)
                try:
                    src_data, _ = get_file_bytes(src)
                    try:
                        dst_data, _ = get_file_bytes(dst)
                        if not _equivalent_content(src_data, dst_data, dst):
                            conflicts.append({"from": src, "to": dst, "reason": "dedup destination exists and differs"})
                            continue
                    except Exception:
                        put_file_bytes(dst, src_data, _guess_content_type(src))
                        verify, _ = get_file_bytes(dst)
                        if not _equivalent_content(src_data, verify, dst):
                            raise RuntimeError("verify mismatch")

                    delete_file(src)
                    moved.append({"from": src, "to": dst, "bytes": len(src_data), "keep": keep})
                    all_files.remove(src)
                except Exception as e:
                    failures.append({"from": src, "to": dst, "error": str(e), "keep": keep})

            if i % 50 == 0:
                print(json.dumps({"progressGroups": i, "totalGroups": len(actions), "moved": len(moved), "skipped": len(skipped_missing), "conflicts": len(conflicts), "failures": len(failures), "seconds": round(time.time() - started, 2)}, ensure_ascii=False))

        out = {
            "generatedAt": int(time.time()),
            "actions": args.actions,
            "inventory": args.inventory,
            "dedupDir": args.dedup_dir,
            "moved": moved,
            "skippedMissing": skipped_missing,
            "conflicts": conflicts,
            "failures": failures,
            "mapping": mapping,
            "seconds": round(time.time() - started, 2),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "out": args.out, "moved": len(moved), "skipped": len(skipped_missing), "conflicts": len(conflicts), "failures": len(failures)}, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
