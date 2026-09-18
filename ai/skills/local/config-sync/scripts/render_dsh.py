#!/usr/bin/env python3
"""Render the dsh ``llm-pi-ai`` provider/model catalog from the opencode source.

Canonical source: ``.config/opencode/opencode.jsonc`` → ``provider``.
Output: the block between ``# BEGIN config-sync:llm-pi-ai`` and
``# END config-sync:llm-pi-ai`` in ``.dsh/settings.yaml``.

Usage:
  python3 render_dsh.py            # write the block
  python3 render_dsh.py --check    # exit 1 if the block is stale
  python3 render_dsh.py --dry-run  # print the block, write nothing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
OPENCODE_JSONC = REPO_ROOT / ".config" / "opencode" / "opencode.jsonc"
DSH_SETTINGS = REPO_ROOT / ".dsh" / "settings.yaml"

BEGIN = "# BEGIN config-sync:llm-pi-ai"
END = "# END config-sync:llm-pi-ai"

# dsh only declares text/image input modalities; drop pdf/audio/video.
KEEP_MODALITIES = {"text", "image"}

# Reasoning levels when a model reasons but declares no explicit variants.
DEFAULT_LEVELS = [("off", None), ("low", "low"), ("medium", "medium"), ("high", "high")]

# Providers not present in opencode.jsonc but wanted in dsh (official APIs).
EXTRA_PROVIDERS = {
    "deepseek": {
        "apiKeyEnv": "DEEPSEEK_API_KEY",
        "baseURL": "https://api.deepseek.com",
        "models": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}],
    }
}


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside strings, and trailing commas."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_opencode() -> dict:
    return json.loads(strip_jsonc(OPENCODE_JSONC.read_text(encoding="utf-8")))


def yaml_str(value: str) -> str:
    """Quote a scalar only when it needs it."""
    if re.fullmatch(r"[A-Za-z0-9_./@+-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def modality_list(model: dict) -> list[str] | None:
    mods = (model.get("modalities") or {}).get("input")
    if not mods:
        return None
    kept = [m for m in mods if m in KEEP_MODALITIES]
    return kept or ["text"]


def reasoning_efforts(model: dict) -> list[tuple[str, str | None]] | None:
    """Map opencode reasoning/variants to dsh (level, wire-value) pairs."""
    variants = model.get("variants")
    if isinstance(variants, dict):
        levels: list[tuple[str, str | None]] = []
        for key, spec in variants.items():
            spec = spec or {}
            if spec.get("disabled"):
                continue
            effort = spec.get("reasoningEffort")
            if effort == "no_think":
                levels.append(("off", None))
            else:
                levels.append((key, effort or key))
        return levels or None
    if model.get("reasoning"):
        return list(DEFAULT_LEVELS)
    return None


def is_deepseek(model_id: str) -> bool:
    return model_id.startswith("deepseek/") or model_id.startswith("deepseek-")


def render_model(model_id: str, model: dict) -> list[str]:
    lines = [f"        - id: {yaml_str(model_id)}"]
    if model.get("name"):
        lines.append(f"          name: {yaml_str(model['name'])}")
    limit = model.get("limit") or {}
    if limit.get("context"):
        lines.append(f"          contextWindow: {limit['context']}")
    if limit.get("output"):
        lines.append(f"          maxTokens: {limit['output']}")
    mods = modality_list(model)
    if mods:
        lines.append(f"          input: [{', '.join(mods)}]")
    levels = reasoning_efforts(model)
    if is_deepseek(model_id) and levels:
        lines.append("          compat:")
        lines.append("            thinkingFormat: deepseek")
    if levels:
        lines.append("          reasoningEfforts:")
        for level, wire in levels:
            lines.append(f"            {level}:" + (f" {wire}" if wire else ""))
    return lines


def render_block(opencode: dict) -> str:
    providers = opencode.get("provider") or {}
    out = [BEGIN, "llm-pi-ai:", "  providers:"]
    for name, spec in providers.items():
        options = spec.get("options") or {}
        models = spec.get("models") or {}
        if not models:
            continue
        out.append(f"    {name}:")
        if options.get("apiKey") and "{" in str(options.get("apiKey", "")):
            env = re.search(r"\{env:([A-Z0-9_]+)\}", options["apiKey"])
            if env:
                out.append(f"      apiKeyEnv: {env.group(1)}")
        out.append("      api: openai-completions")
        if options.get("baseURL"):
            out.append(f"      baseURL: {options['baseURL']}")
        out.append("      models:")
        for model_id in sorted(models):
            out.extend(render_model(model_id, models[model_id] or {}))
    for name, spec in EXTRA_PROVIDERS.items():
        if name in providers:
            continue
        out.append(f"    {name}:")
        out.append(f"      apiKeyEnv: {spec['apiKeyEnv']}")
        out.append("      api: openai-completions")
        out.append(f"      baseURL: {spec['baseURL']}")
        out.append("      models:")
        for model in spec["models"]:
            out.extend(render_model(model["id"], model))
    out.append(END)
    return "\n".join(out) + "\n"


def splice(settings: str, block: str) -> str:
    if BEGIN in settings and END in settings:
        start = settings.index(BEGIN)
        end = settings.index(END) + len(END)
        return settings[:start] + block.rstrip("\n") + settings[end:]
    raise SystemExit(f"error: sentinels {BEGIN!r}/{END!r} not found in {DSH_SETTINGS}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if the rendered block differs")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args()

    block = render_block(load_opencode())
    current = DSH_SETTINGS.read_text(encoding="utf-8")
    desired = splice(current, block)

    if args.dry_run:
        print(block)
        return 0
    if args.check:
        if desired != current:
            print(f"STALE: {DSH_SETTINGS.relative_to(REPO_ROOT)} — run render_dsh.py", file=sys.stderr)
            return 1
        print(f"ok: {DSH_SETTINGS.relative_to(REPO_ROOT)} in sync")
        return 0
    DSH_SETTINGS.write_text(desired, encoding="utf-8")
    print(f"wrote {DSH_SETTINGS.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
