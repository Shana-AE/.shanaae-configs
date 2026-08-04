#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from datetime import datetime, timezone, timedelta

OBSIDIAN_BASE_PATH = os.environ.get(
    "MAIMEMO_OBSIDIAN_PATH", "Inbox/ai-skills/english-learning/{YYYY}/{MM}"
)
FILE_TEMPLATE = os.environ.get(
    "MAIMEMO_FILE_TEMPLATE", "MaiMemo Daily Story - {YYYY}-{MM}-{DD}.md"
)

BEIJING_TZ = timezone(timedelta(hours=8))


def maimemo_today():
    now = datetime.now(BEIJING_TZ)
    if now.hour < 4:
        now -= timedelta(days=1)
    return now


def completed_study_day():
    """The most recently COMPLETED MaiMemo study day.

    The story reviews words from the day that just finished, so when saving in
    the morning (>=04:00 Beijing) the target is yesterday; before 04:00 it's the
    day about to close (== maimemo_today()). Prefer passing --date from
    maimemo_words_from_pg.py; this is the fallback when no date is given.
    """
    now = datetime.now(BEIJING_TZ)
    day = maimemo_today()
    if now.hour >= 4:
        day -= timedelta(days=1)
    return day


def render_template(template, dt):
    return (
        template.replace("{YYYY}", dt.strftime("%Y"))
        .replace("{YY}", dt.strftime("%y"))
        .replace("{MM}", dt.strftime("%m"))
        .replace("{DD}", dt.strftime("%d"))
    )


def save_to_obsidian(content, date_str=None):
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
    else:
        dt = completed_study_day()
    path = f"{render_template(OBSIDIAN_BASE_PATH, dt)}/{render_template(FILE_TEMPLATE, dt)}"
    try:
        result = subprocess.run(
            [
                "obsidian",
                "create",
                f"path={path}",
                f"content={content}",
                "silent",
                "overwrite",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print(f"Obsidian CLI Error: create timed out after 120s for {path}", file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(f"Obsidian CLI Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Saved to Obsidian: {path}")
    return path


def delete_from_obsidian(path):
    try:
        result = subprocess.run(
            ["obsidian", "trash", f"path={path}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print(f"Obsidian CLI Error: trash timed out after 60s for {path}", file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(f"Obsidian CLI Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Deleted from Obsidian: {path}")


def main():
    parser = argparse.ArgumentParser(description="MaiMemo Daily Story Tool")
    sub = parser.add_subparsers(dest="command", required=True)

    save_p = sub.add_parser("save", help="Save markdown content to Obsidian")
    save_p.add_argument("--date", help="Date string (YYYY-MM-DD), default today")
    save_p.add_argument("--file", help="Read content from file instead of stdin")

    delete_p = sub.add_parser("delete", help="Delete a note from Obsidian")
    delete_p.add_argument("path", help="Full path in Obsidian vault")

    args = parser.parse_args()

    if args.command == "save":
        if args.file:
            with open(args.file, "r") as f:
                content = f.read()
        else:
            content = sys.stdin.read()
        save_to_obsidian(content, args.date)

    elif args.command == "delete":
        delete_from_obsidian(args.path)


if __name__ == "__main__":
    main()
