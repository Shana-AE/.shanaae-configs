#!/usr/bin/env python3
"""Qiniu (Sufy) model catalog — fetch, query, diff, and sync.

Primary source: https://openai.sufy.com/v1/models (authoritative live list)
Supplementary:  https://models.dev/api.json (fills gaps + adds metadata)

Usage:
  python3 qiniu_model_sync.py fetch                          # fetch + cache merged list
  python3 qiniu_model_sync.py diff --target opencode          # new models vs opencode.jsonc
  python3 qiniu_model_sync.py diff --target router            # new models vs router config
  python3 qiniu_model_sync.py list --family claude            # list by family
  python3 qiniu_model_sync.py latest                          # latest model per family
  python3 qiniu_model_sync.py update --target opencode --dry-run  # propose additions
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SUFY_ENDPOINT = "https://openai.sufy.com/v1/models"
MODELS_DEV_ENDPOINT = "https://models.dev/api.json"

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "qiniu-model-sync"
SUFY_CACHE = CACHE_DIR / "sufy.json"
MODELS_DEV_CACHE = CACHE_DIR / "models-dev.json"
STATE_FILE = CACHE_DIR / "state.json"

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIGS_ROOT = SCRIPT_DIR.parents[4]  # ai/skills/local/qiniu-model-sync/scripts -> repo root
OPENCODE_CONFIG = CONFIGS_ROOT / ".config" / "opencode" / "opencode.jsonc"
ROUTER_CONFIG = CONFIGS_ROOT / ".claude-code-router" / "config.json"

IMAGE_MARKERS = ("image", "dall", "flux", "sd3", "kolors", "wanx")
VIDEO_MARKERS = ("video", "kling", "veo", "sora", "cogvideo")

FAMILY_MAP = {
    "claude": ("claude", "anthropic"),
    "gpt": ("gpt", "o3", "o4", "o1"),
    "deepseek": ("deepseek",),
    "glm": ("glm",),
    "kimi": ("kimi",),
    "gemini": ("gemini", "gemma"),
    "grok": ("grok",),
    "qwen": ("qwen",),
    "doubao": ("doubao",),
    "minimax": ("minimax",),
    "doubao": ("doubao", "seed"),
}


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def _api_key() -> str:
    key = os.environ.get("QINIU_AI_API_KEY")
    if not key:
        secrets = CONFIGS_ROOT / ".secrets"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip() == "QINIU_AI_API_KEY":
                        v = v.strip().strip("\"'")
                        key = v
                        break
    if not key:
        sys.exit("QINIU_AI_API_KEY not found in env or .secrets")
    return key


def fetch_sufy(force: bool = False) -> list[str]:
    """Fetch the authoritative model list from openai.sufy.com."""
    if not force and SUFY_CACHE.exists():
        import time
        age = time.time() - SUFY_CACHE.stat().st_mtime
        if age < 300:  # 5-min cache
            return json.loads(SUFY_CACHE.read_text())

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _api_key()
    req = urllib.request.Request(SUFY_ENDPOINT, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    ids = sorted(m["id"] for m in data.get("data", []) if m.get("id"))
    SUFY_CACHE.write_text(json.dumps(ids, ensure_ascii=False, indent=2))
    return ids


def fetch_models_dev(force: bool = False) -> dict:
    """Fetch models.dev catalog (cached 24h)."""
    if not force and MODELS_DEV_CACHE.exists():
        import time
        age = time.time() - MODELS_DEV_CACHE.stat().st_mtime
        if age < 86400:  # 24h cache
            return json.loads(MODELS_DEV_CACHE.read_text())

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(MODELS_DEV_ENDPOINT, headers={"User-Agent": "qiniu-model-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    MODELS_DEV_CACHE.write_text(json.dumps(data, ensure_ascii=False))
    return data


def merge_catalog(sufy_ids: list[str], dev_data: dict) -> dict[str, dict]:
    """Merge Sufy IDs with models.dev metadata.

    Returns {model_id: {name, family, reasoning, attachment, context, output, source}}
    """
    catalog: dict[str, dict] = {}
    # Start with Sufy IDs
    for mid in sufy_ids:
        catalog[mid] = {"id": mid, "source": "sufy"}

    # Enrich / supplement from models.dev (qiniu-ai provider)
    qiniu_dev = dev_data.get("qiniu-ai", {}).get("models", {})
    for mid, m in qiniu_dev.items():
        if mid not in catalog:
            catalog[mid] = {"id": mid, "source": "models-dev"}
        entry = catalog[mid]
        entry.setdefault("name", m.get("name", mid))
        if m.get("reasoning"):
            entry["reasoning"] = True
        if m.get("attachment"):
            entry["attachment"] = True
        lim = m.get("limit", {})
        if isinstance(lim, dict):
            if lim.get("context"):
                entry["context"] = lim["context"]
            if lim.get("output"):
                entry["output"] = lim["output"]
        # Fill name for Sufy-only entries from dev if available
        if "name" not in entry and m.get("name"):
            entry["name"] = m["name"]

    # Also check openai provider in dev (for models like gpt-5.6-terra that Qiniu relays)
    openai_dev = dev_data.get("openai", {}).get("models", {})
    for mid, m in openai_dev.items():
        qiniu_id = f"openai/{mid}"
        if qiniu_id in catalog and "name" not in catalog[qiniu_id]:
            catalog[qiniu_id]["name"] = m.get("name", qiniu_id)

    # Fill in family for all
    for mid, entry in catalog.items():
        if "family" not in entry:
            entry["family"] = detect_family(mid)
    return catalog


# --------------------------------------------------------------------------- #
# Categorize / family detection
# --------------------------------------------------------------------------- #
def categorize(ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    text, image, video = [], [], []
    for mid in ids:
        low = mid.lower()
        if any(mk in low for mk in IMAGE_MARKERS):
            image.append(mid)
        elif any(mk in low for mk in VIDEO_MARKERS):
            video.append(mid)
        else:
            text.append(mid)
    return text, image, video


def detect_family(mid: str) -> str:
    low = mid.lower()
    for family, markers in FAMILY_MAP.items():
        if any(m in low for m in markers):
            return family
    return "other"


# --------------------------------------------------------------------------- #
# Target parsing (opencode.jsonc / router config)
# --------------------------------------------------------------------------- #
def _skip_jsonc_comment(text: str, i: int) -> int | None:
    if text[i] == "/" and i + 1 < len(text) and text[i + 1] == "/":
        nl = text.find("\n", i)
        return nl if nl != -1 else len(text)
    if text[i] == "/" and i + 1 < len(text) and text[i + 1] == "*":
        end = text.find("*/", i + 2)
        return end + 2 if end != -1 else len(text)
    return None


def parse_opencode_models(config_path: Path) -> set[str]:
    """Extract model IDs from provider.qiniu.models in opencode.jsonc."""
    text = config_path.read_text()
    # Find all 8-space-indented keys that look like model entries
    models: set[str] = set()
    for line in text.split("\n"):
        m = re.match(r'^ {8}"([^"]+)"\s*:\s*\{', line)
        if m:
            models.add(m.group(1))
    return models


def parse_router_models(config_path: Path) -> set[str]:
    """Extract model IDs from Providers[qiniu].models in router config.json."""
    data = json.loads(config_path.read_text())
    for p in data.get("Providers", []):
        if p.get("name") == "qiniu":
            return set(p.get("models", []))
    return set()


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"seen": []}


def save_state(state: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_fetch(args):
    sufy_ids = fetch_sufy(force=getattr(args, "force", False))
    dev_data = fetch_models_dev(force=getattr(args, "force", False))
    catalog = merge_catalog(sufy_ids, dev_data)
    text, image, video = categorize(list(catalog.keys()))

    # State tracking
    state = load_state()
    seen = set(state.get("seen") or [])
    first_run = not seen

    all_ids = sorted(catalog.keys())
    new_ids = sorted(set(all_ids) - seen)

    state["seen"] = all_ids
    save_state(state)

    print(f"== qiniu-model-sync fetch ==")
    print(f"   Sufy models  : {len(sufy_ids)}")
    print(f"   models.dev   : {len(dev_data.get('qiniu-ai', {}).get('models', {}))} qiniu + {len(dev_data.get('openai', {}).get('models', {}))} openai")
    print(f"   merged total : {len(catalog)} ({len(text)} text, {len(image)} image, {len(video)} video)")
    if first_run:
        print(f"   first run — baseline established ({len(all_ids)} models)")
    elif new_ids:
        print(f"   NEW since last fetch ({len(new_ids)}):")
        for mid in new_ids:
            entry = catalog[mid]
            name = entry.get("name", mid)
            print(f"     + {mid:45s} ({name})")
    else:
        print(f"   no new models since last fetch")


def cmd_diff(args):
    catalog = merge_catalog(fetch_sufy(), fetch_models_dev())
    sufy_ids = set(fetch_sufy())

    if args.target == "opencode":
        target_ids = parse_opencode_models(OPENCODE_CONFIG)
        target_name = "opencode.jsonc"
    elif args.target == "router":
        target_ids = parse_router_models(ROUTER_CONFIG)
        target_name = "router config.json"
    else:
        sys.exit(f"unknown target: {args.target}")

    catalog_ids = set(catalog.keys())
    new_in_catalog = sorted(catalog_ids - target_ids)
    removed_from_catalog = sorted(target_ids - catalog_ids)

    print(f"== diff: merged catalog vs {target_name} ==")
    print(f"   catalog: {len(catalog_ids)} models | {target_name}: {len(target_ids)} models")

    if new_in_catalog:
        print(f"\n   NEW (in catalog, not in {target_name}) — {len(new_in_catalog)}:")
        for mid in new_in_catalog:
            entry = catalog.get(mid, {})
            name = entry.get("name", "")
            fam = entry.get("family", "?")
            src = entry.get("source", "?")
            tag = f" [{src}]" if src == "models-dev" else ""
            print(f"     + {mid:45s} {name:45s} ({fam}){tag}")

    if removed_from_catalog:
        print(f"\n   REMOVED (in {target_name}, not in catalog) — {len(removed_from_catalog)}:")
        for mid in removed_from_catalog:
            print(f"     - {mid}")

    if not new_in_catalog and not removed_from_catalog:
        print("   fully in sync")


def cmd_list(args):
    catalog = merge_catalog(fetch_sufy(), fetch_models_dev())
    if args.family:
        fam = args.family.lower()
        entries = [(mid, e) for mid, e in sorted(catalog.items()) if e.get("family") == fam]
        print(f"== family: {fam} ({len(entries)} models) ==")
        for mid, entry in entries:
            name = entry.get("name", mid)
            ctx = entry.get("context", "?")
            tags = []
            if entry.get("reasoning"):
                tags.append("reasoning")
            if entry.get("attachment"):
                tags.append("attachment")
            tagstr = f" [{', '.join(tags)}]" if tags else ""
            print(f"  {mid:45s} | {name:45s} | ctx={ctx}{tagstr}")
    else:
        families: dict[str, list[str]] = {}
        for mid, entry in sorted(catalog.items()):
            fam = entry.get("family", "other")
            families.setdefault(fam, []).append(mid)
        print(f"== all families ({len(catalog)} models) ==")
        for fam in sorted(families.keys()):
            print(f"  {fam:12s}: {len(families[fam])} models")


def cmd_latest(args):
    catalog = merge_catalog(fetch_sufy(), fetch_models_dev())
    families: dict[str, list[str]] = {}
    for mid, entry in sorted(catalog.items()):
        fam = entry.get("family", "other")
        families.setdefault(fam, []).append(mid)

    print("== latest model per family ==")
    for fam in sorted(families.keys()):
        ids = families[fam]
        # Pick the "latest" by highest version number heuristic
        latest = pick_latest(ids)
        entry = catalog.get(latest, {})
        name = entry.get("name", latest)
        print(f"  {fam:12s}: {latest:45s} ({name})  [{len(ids)} total]")


def pick_latest(ids: list[str]) -> str:
    """Heuristic: pick the highest-version model from a list of IDs.

    Scoring (highest wins):
    1. Decimal version (5.6 > 4.8) extracted from patterns like gpt-5.6, glm-5.2
    2. Single-generation number (5 in fable-5, 3 in minimax-m3)
    3. Parameter-count suffixes (120b, 27b) are penalized — they're sizes, not versions
    4. Among equal versions, prefer shorter IDs (main model over variants)
    """
    def score(mid: str):
        low = mid.lower()
        # Penalize parameter-count-only models (gpt-oss-120b, autoglm-phone-9b)
        has_param = bool(re.search(r'\d{2,}b\b', low))
        # Extract decimal versions (5.6, 4.8, 3.7)
        decimals = re.findall(r'(\d+)\.(\d+)', low)
        if decimals:
            best = max((int(a), int(b)) for a, b in decimals)
            return (best[0], best[1], -1 if has_param else 0, -len(mid))
        # v-suffix generation (v4-pro, v3-flash)
        vmatch = re.search(r'v(\d{1,2})\b', low)
        if vmatch:
            return (int(vmatch.group(1)), 0, -1 if has_param else 0, -len(mid))
        # Single-generation number after dash (fable-5, minimax-m3, seed-2)
        gmatch = re.search(r'-m?(\d{1,2})\b', low)
        if gmatch and not has_param:
            return (int(gmatch.group(1)), 0, 0, -len(mid))
        return (0, 0, -1 if has_param else 0, -len(mid))
    return max(ids, key=score)


def cmd_update(args):
    catalog = merge_catalog(fetch_sufy(), fetch_models_dev())
    if args.target == "opencode":
        target_ids = parse_opencode_models(OPENCODE_CONFIG)
    elif args.target == "router":
        target_ids = parse_router_models(ROUTER_CONFIG)
    else:
        sys.exit(f"unknown target: {args.target}")

    new_ids = sorted(set(catalog.keys()) - target_ids)
    if not new_ids:
        print("nothing to add — fully in sync")
        return

    print(f"# {len(new_ids)} new models to add to {args.target}:")
    if args.target == "opencode":
        for mid in new_ids:
            entry = catalog[mid]
            name = entry.get("name", mid)
            reasoning = entry.get("reasoning", False)
            attachment = entry.get("attachment", False)
            context = entry.get("context", 200000)
            output = entry.get("output", 64000)
            parts = [f'"name": "{name} (Qiniu)"']
            if reasoning:
                parts.append('"reasoning": true')
            if attachment:
                parts.append('"attachment": true')
            parts.append(f'"limit": {{"context": {context}, "output": {output}}}')
            body = ", ".join(parts)
            print(f'        "{mid}": {{ {body} }},')
    elif args.target == "router":
        print("Add these to the qiniu provider's models array in config.json:")
        for mid in new_ids:
            print(f'        "{mid}",')


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch + cache the merged model list")
    p_fetch.add_argument("--force", action="store_true", help="bypass cache")
    p_fetch.set_defaults(func=cmd_fetch)

    p_diff = sub.add_parser("diff", help="compare catalog against a config")
    p_diff.add_argument("--target", choices=["opencode", "router"], required=True)
    p_diff.set_defaults(func=cmd_diff)

    p_list = sub.add_parser("list", help="list models, optionally filtered by family")
    p_list.add_argument("--family", help="filter: claude, gpt, deepseek, glm, kimi, gemini, grok, qwen, doubao, minimax")
    p_list.set_defaults(func=cmd_list)

    p_latest = sub.add_parser("latest", help="show the latest model per family")
    p_latest.set_defaults(func=cmd_latest)

    p_update = sub.add_parser("update", help="propose additions for a config")
    p_update.add_argument("--target", choices=["opencode", "router"], required=True)
    p_update.add_argument("--dry-run", action="store_true", default=True)
    p_update.set_defaults(func=cmd_update)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
