#!/usr/bin/env python3
"""Persist the generated maimemo article (/tmp/maimemo-story.md) deterministically:
Obsidian save + NAS copy + Feishu full-text send.

The agent's only job is to GENERATE the article to /tmp/maimemo-story.md; this script
(runs as a separate command cron ~40min later) handles all persistence so it doesn't
depend on the agent faithfully executing multiple steps.
"""
import glob
import os
import shutil
import subprocess
import sys
import time

ARTICLE = "/tmp/maimemo-story.md"
VAULT_SAVE_SCRIPT = "/Users/shanaae/.shanaae/configs/ai/skills/local/maimemo-daily-story/scripts/maimemo_story.py"
NAS = "/Volumes/home/Documents/maimemo"
FEISHU_TO = "ou_ef08073b1540e3d078882a2b08e455bf"
FRESH_SECS = 4 * 3600  # article must be generated within last 4h


def latest_data_date():
    files = glob.glob(f"{NAS}/20??/*/*.json")
    if not files:
        return None

    def key(f):
        parts = f.split("/")
        return parts[-3] + parts[-2] + parts[-1].replace(".json", "")

    f = max(files, key=key)
    parts = f.split("/")
    return f"{parts[-3]}-{parts[-2]}-{parts[-1].replace('.json', '')}"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    if not os.path.isfile(ARTICLE):
        print("no article at /tmp/maimemo-story.md; skip")
        sys.exit(0)
    age = time.time() - os.path.getmtime(ARTICLE)
    if age > FRESH_SECS and "--force" not in sys.argv:
        print(f"article stale ({int(age/60)}min old); skip (use --force to override)")
        sys.exit(0)
    date = latest_data_date()
    if not date:
        print("no NAS data file to determine date; skip")
        sys.exit(0)
    y, m, d = date[:4], date[5:7], date[8:10]
    results = []

    # 1. Obsidian
    r = run(["python3", VAULT_SAVE_SCRIPT, "save", "--file", ARTICLE, "--date", date])
    results.append(f"obsidian:{'ok' if r.returncode == 0 else 'fail'}")
    if r.returncode != 0:
        print("  obsidian stderr:", r.stderr[:200])

    # 2. NAS copy
    try:
        os.makedirs(f"{NAS}/{y}/{m}", exist_ok=True)
        shutil.copy(ARTICLE, f"{NAS}/{y}/{m}/{d}-article.md")
        results.append("nas:ok")
    except Exception as e:
        results.append(f"nas:fail")

    # 3. Feishu full article
    with open(ARTICLE) as fh:
        content = fh.read()
    r = run(["openclaw", "message", "send", "--channel", "feishu", "--target", FEISHU_TO, "-m", content])
    results.append(f"feishu:{'ok' if r.returncode == 0 else 'fail'}")

    print(f"persisted {date}: " + ", ".join(results))


if __name__ == "__main__":
    main()
