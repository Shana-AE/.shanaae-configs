import argparse
import os
from pathlib import Path


def to_wsl_path(p: str) -> str:
    p = p.strip()
    if len(p) >= 3 and p[1:3] == ":\\":
        drive = p[0].lower()
        rest = p[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return p


def delete_empty_dirs(vault: Path, *, keep_root_dirs: set[str]) -> tuple[list[str], list[str]]:
    deleted: list[str] = []
    failed: list[str] = []

    for dirpath, dirnames, filenames in os.walk(vault, topdown=False):
        current = Path(dirpath)
        rel = current.relative_to(vault).as_posix()

        if rel == ".obsidian" or rel.startswith(".obsidian/"):
            continue

        if rel in keep_root_dirs:
            continue

        try:
            entries = list(current.iterdir())
        except Exception:
            failed.append(rel)
            continue

        if entries:
            continue

        try:
            current.rmdir()
            deleted.append(rel)
        except Exception:
            failed.append(rel)

    return deleted, failed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--keep-root", default="Area,Inbox,Recycle,Resource,assets,templates")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    vault = Path(to_wsl_path(args.vault)).expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        raise SystemExit(f"Vault 路径不存在或不是目录: {vault}")

    keep_root_dirs = {s.strip() for s in args.keep_root.split(",") if s.strip()}
    deleted, failed = delete_empty_dirs(vault, keep_root_dirs=keep_root_dirs)

    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(deleted) + ("\n" if deleted else ""), encoding="utf-8")

    print(f"deleted={len(deleted)} failed={len(failed)} vault={vault}")
    if failed:
        print("failed_sample=" + ",".join(failed[:20]))


if __name__ == "__main__":
    main()
