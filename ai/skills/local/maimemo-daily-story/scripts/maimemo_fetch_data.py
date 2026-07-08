#!/usr/bin/env python3
"""Fetch today's MaiMemo word-status list and save to NAS as YYYY/MM/DD.{md,json}.

Zero-token: pure HTTP + file write, no LLM. Designed to run as a cron command job.
MaiMemo day boundary is 04:00 (Asia/Shanghai); before 04:00 the data is attributed
to the previous calendar day (same logic as the maimemo-daily-story job).
"""
import datetime
import json
import os
import sys
import urllib.request

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))
API_BASE = "https://open.maimemo.com/open/api/v1/study"
NAS_ROOT = "/Volumes/home/Documents/maimemo"
SECRETS = os.path.expanduser("~/.shanaae/configs/.secrets")


def load_token():
    if os.path.isfile(SECRETS):
        with open(SECRETS) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("MAIMEMO_TOKEN"):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return os.environ.get("MAIMEMO_TOKEN", "")


def maimemo_today():
    now = datetime.datetime.now(BEIJING_TZ)
    if now.hour < 4:
        now -= datetime.timedelta(days=1)
    return now


def post(path, token, body=None):
    req = urllib.request.Request(
        f"{API_BASE}/{path}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body or {}).encode(),
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    token = load_token()
    if not token:
        print("ERROR: MAIMEMO_TOKEN not found in .secrets", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(NAS_ROOT):
        print(f"ERROR: NAS not mounted at {NAS_ROOT}", file=sys.stderr)
        sys.exit(1)

    dt = maimemo_today()
    date_str = dt.strftime("%Y-%m-%d")

    progress = post("get_study_progress", token).get("data", {}).get("progress", {})
    finished = progress.get("finished", 0)
    total = progress.get("total", 0)
    study_min = progress.get("study_time", 0) // 60000

    items = post("get_today_items", token, {"limit": 1000}).get("data", {}).get("today_items", [])
    buckets = {"FORGET": [], "VAGUE": [], "FAMILIAR": []}
    skipped = 0
    for it in items:
        fr = it.get("first_response") or "OTHER"
        sp = (it.get("voc_spelling") or "").strip()
        if not sp:
            skipped += 1
            continue
        buckets.setdefault(fr, []).append(sp)

    out_dir = os.path.join(NAS_ROOT, dt.strftime("%Y"), dt.strftime("%m"))
    os.makedirs(out_dir, exist_ok=True)

    # human-readable markdown
    md = [f"# MaiMemo 单词情况 - {date_str}", ""]
    md.append(f"📅 **{date_str}** | 学习 **{finished}/{total}** 词 | 用时 **{study_min}** 分钟 | 共 {len(items)} 条记录")
    md.append("")
    for key, emoji, name in [("FORGET", "🗑️", "忘记"), ("VAGUE", "🌀", "模糊"), ("FAMILIAR", "✅", "熟悉")]:
        words = buckets.get(key, [])
        md.append(f"## {emoji} {name}（{len(words)}）")
        md.append("")
        md.append(", ".join(words) if words else "_(无)_")
        md.append("")
    # other first_response values
    for key, words in buckets.items():
        if key in ("FORGET", "VAGUE", "FAMILIAR"):
            continue
        md.append(f"## ❓ 其他/{key}（{len(words)}）")
        md.append("")
        md.append(", ".join(words))
        md.append("")
    if skipped:
        md.append(f"_(另有 {skipped} 条无拼写，已略过；详见 .json)_")
        md.append("")
    md_path = os.path.join(out_dir, f"{dt.strftime('%d')}.md")
    with open(md_path, "w") as fh:
        fh.write("\n".join(md))

    # raw json for the record
    json_path = os.path.join(out_dir, f"{dt.strftime('%d')}.json")
    with open(json_path, "w") as fh:
        json.dump(
            {"date": date_str, "progress": progress, "items": items},
            fh, ensure_ascii=False, indent=2,
        )

    n_forget = len(buckets.get("FORGET", []))
    n_vague = len(buckets.get("VAGUE", []))
    n_familiar = len(buckets.get("FAMILIAR", []))
    print(f"saved {date_str}: {md_path}")
    print(f"  {len(items)} items | 🗑️{n_forget} 🌀{n_vague} ✅{n_familiar} | {finished}/{total} 词, {study_min}min")


if __name__ == "__main__":
    main()
