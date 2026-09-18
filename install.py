#!/usr/bin/env python3
"""Cross-platform installer for the AI-agent configs repo.

Reads ``install/manifest.json`` and live-links each tool's native config
location to its repo source.  One-time per machine; day-to-day edits happen in
the repo and are picked up instantly through the links.

Design: docs/superpowers/specs/2026-06-25-cross-platform-configs-design.md

Usage:
  python3 install.py --all              link every tool, render configs, build skills
  python3 install.py --tool dsh         one tool only
  python3 install.py --list             show the plan without touching anything
  python3 install.py --dry-run --all    same as --list, but includes derived steps
  python3 install.py --force --all      overwrite non-owned targets (no backup)

Linking strategy:
  Linux / macOS : symlink
  Windows       : directory -> junction (mklink /J, no admin needed)
                  file      -> symlink, falling back to copy + state tracking
  Entries may set "windows_strategy": "copy" | "delegate:<script>" to override.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = REPO_ROOT / "install" / "manifest.json"
COPY_STATE_PATH = REPO_ROOT / "install" / ".copy-state.json"
ENV_SH = REPO_ROOT / "env.sh"
ENV_PS1 = REPO_ROOT / "env.ps1"
SECRETS = REPO_ROOT / ".secrets"
SECRETS_EXAMPLE = REPO_ROOT / ".secrets.example"

# Canonical environment vocabulary (spec §5).
ENV_EXPORTS = {"AI_CONFIGS_ROOT": str(REPO_ROOT)}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def current_os() -> str:
    system = platform.system()
    if system == "Darwin":
        return "darwin"
    if system == "Windows":
        return "windows"
    return "linux"


def is_windows() -> bool:
    return current_os() == "windows"


def expand_target(raw: str) -> Path:
    """Expand %VAR% / $VAR / ~ in a manifest target path."""
    home = str(Path.home())

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name.upper() == "USERPROFILE":
            return home
        return os.environ.get(name, os.environ.get(name.upper(), match.group(0)))

    raw = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", repl, raw)
    raw = os.path.expandvars(raw)
    raw = os.path.expanduser(raw)
    return Path(raw)


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    dest = path.with_name(f"{path.name}.bak-{stamp}")
    path.rename(dest)
    return dest


def link_is_correct(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    try:
        return Path(os.path.realpath(target)) == Path(os.path.realpath(source))
    except OSError:
        return False


def load_copy_state() -> dict:
    try:
        return json.loads(COPY_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_copy_state(state: dict) -> None:
    COPY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COPY_STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def record_copy(source: Path, target: Path) -> None:
    state = load_copy_state()
    state[str(target)] = {
        "source": str(source),
        "source_mtime": source.stat().st_mtime if source.exists() else 0,
        "copied_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_copy_state(state)


# --------------------------------------------------------------------------- #
# linking
# --------------------------------------------------------------------------- #
def create_symlink(source: Path, target: Path, mode: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] symlink {target} -> {source}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    os.symlink(source, target, target_is_directory=(mode == "dir"))
    return f"linked   {target} -> {source}"


def create_windows_link(source: Path, target: Path, mode: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] {mode} link {target} -> {source}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_symlink():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    if mode == "dir":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            check=True,
            capture_output=True,
        )
        return f"junction {target} -> {source}"
    try:
        os.symlink(source, target)
        return f"symlink  {target} -> {source}"
    except OSError:
        shutil.copy2(source, target)
        record_copy(source, target)
        return f"copy     {target} <- {source} (symlink unavailable)"


def create_copy(source: Path, target: Path, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] copy {source} -> {target}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=False)
    else:
        shutil.copy2(source, target, follow_symlinks=True)
    record_copy(source, target)
    return f"copied   {target} <- {source}"


def link_entry(entry: dict, os_name: str, force: bool, dry_run: bool) -> str:
    source = REPO_ROOT / entry["source"]
    raw_target = entry["target"].get(os_name) or entry["target"].get("linux")
    if not raw_target:
        return f"skip     {entry['source']} (no target for {os_name})"
    target = expand_target(raw_target)
    mode = entry.get("mode", "dir")

    if not source.exists():
        return f"WARN     source missing: {source}"

    strategy = entry.get("windows_strategy")
    if os_name == "windows" and strategy:
        if strategy.startswith("delegate:"):
            return f"delegate {target} (run {strategy.split(':', 1)[1]})"
        if strategy == "copy":
            return create_copy(source, target, dry_run)

    if os_name != "windows":
        if link_is_correct(target, source):
            return f"ok       {target} -> {source}"
        if target.exists() or target.is_symlink():
            if not force:
                bak = backup(target) if not dry_run else target.with_name(target.name + ".bak-<ts>")
                action = create_symlink(source, target, mode, dry_run)
                return f"{action}\n         backed up -> {bak}"
            if not dry_run:
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
        return create_symlink(source, target, mode, dry_run)

    if mode == "dir" and target.is_dir() and not target.is_symlink():
        return create_windows_link(source, target, mode, dry_run)
    if target.exists() and not target.is_symlink() and strategy != "copy":
        bak = backup(target) if not dry_run else target.with_name(target.name + ".bak-<ts>")
        action = create_windows_link(source, target, mode, dry_run)
        return f"{action}\n         backed up -> {bak}"
    return create_windows_link(source, target, mode, dry_run)


# --------------------------------------------------------------------------- #
# derived steps
# --------------------------------------------------------------------------- #
def run_step(label: str, cmd: list[str], dry_run: bool) -> None:
    print(f"\n[{label}] {' '.join(cmd)}")
    if dry_run:
        print("  [dry-run] skipped")
        return
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"  WARN: exited {result.returncode}")


def render_configs(dry_run: bool) -> None:
    script = REPO_ROOT / "ai/skills/local/setup-configs/scripts/setup_configs.py"
    if script.exists():
        run_step("render", [sys.executable, str(script)], dry_run)


def regen_skills(dry_run: bool) -> None:
    script = REPO_ROOT / "ai/skills/link-skills.sh"
    if not script.exists():
        return
    bash = shutil.which("bash")
    if not bash:
        print("\n[skills] bash not found — run ai/skills/link-skills.sh manually")
        return
    run_step("skills", [bash, str(script)], dry_run)


def bootstrap_secrets(dry_run: bool) -> None:
    if SECRETS.exists() or not SECRETS_EXAMPLE.exists():
        return
    print("\n[secrets] .secrets missing")
    if dry_run:
        print(f"  [dry-run] would copy {SECRETS_EXAMPLE.name} -> .secrets")
        return
    shutil.copy2(SECRETS_EXAMPLE, SECRETS)
    print("  copied .secrets.example -> .secrets — edit it and fill in your values")


def emit_env(dry_run: bool) -> None:
    lines_sh = ["# Generated by install.py — source this to export canonical paths."]
    lines_ps = ["# Generated by install.py — dot-source this to export canonical paths."]
    for key, value in ENV_EXPORTS.items():
        lines_sh.append(f'export {key}="{value}"')
        lines_ps.append(f'$env:{key} = "{value}"')
    if dry_run:
        print(f"\n[env] would write {ENV_SH.name} and {ENV_PS1.name}")
        return
    ENV_SH.write_text("\n".join(lines_sh) + "\n", encoding="utf-8")
    ENV_PS1.write_text("\n".join(lines_ps) + "\n", encoding="utf-8")
    print(f"\n[env] wrote {ENV_SH.name} / {ENV_PS1.name} (AI_CONFIGS_ROOT={REPO_ROOT})")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tool", action="append", default=[], help="only this tool (repeatable)")
    parser.add_argument("--all", action="store_true", help="link every tool in the manifest")
    parser.add_argument("--list", action="store_true", help="show the plan, touch nothing")
    parser.add_argument("--dry-run", action="store_true", help="alias for --list plus derived steps")
    parser.add_argument("--force", action="store_true", help="overwrite non-owned targets without backup")
    parser.add_argument("--no-skills", action="store_true", help="skip for-tools regeneration")
    parser.add_argument("--no-render", action="store_true", help="skip *.example rendering")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"error: manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tools: dict[str, list[dict]] = manifest["tools"]
    os_name = current_os()
    dry = args.list or args.dry_run

    selected = list(tools) if (args.all or not args.tool) else args.tool
    unknown = [t for t in selected if t not in tools]
    if unknown:
        print(f"error: unknown tool(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    print(f"AI configs installer — os={os_name}  root={REPO_ROOT}")
    print(f"tools: {', '.join(selected)}")

    changed = 0
    for tool in selected:
        print(f"\n== {tool} ==")
        for entry in tools[tool]:
            line = link_entry(entry, os_name, args.force, dry)
            print(f"  {line}")
            if not line.startswith(("ok ", "skip ")):
                changed += 1

    if not args.no_render:
        render_configs(dry)
    if not args.no_skills:
        regen_skills(dry)
    bootstrap_secrets(dry)
    emit_env(dry)

    print(f"\nDone. {changed} link action(s){' planned' if dry else ''}.")
    if dry:
        print("Re-run without --list/--dry-run to apply.")
    else:
        print(f"Tip: source {ENV_SH} (or {ENV_PS1}) to export AI_CONFIGS_ROOT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
