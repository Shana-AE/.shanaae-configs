#!/usr/bin/env python3
"""
Qiniu AI Token Usage Query Tool
Query token usage for the Qiniu AI API (api.qnaigc.com)

Usage:
    python3 qiniu_usage.py [OPTIONS]

Options:
    --granularity   day | hour   (default: day)
    --start         Start date, e.g. 2026-02-01 or 2026-02-01T00:00:00+08:00
    --end           End date,   e.g. 2026-02-25 or 2026-02-25T23:59:59+08:00
    --days          Shortcut: query last N days (default: 7)
    --today         Shortcut: query today only
    --month         Shortcut: query current month
    --json          Output raw JSON instead of formatted table
    --api-key       Override API key (default: reads QINIU_AI_API_KEY env or hardcoded fallback)
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.qnaigc.com"
USAGE_PATH = "/v2/stat/usage"
DEFAULT_API_KEY = os.environ.get("QINIU_AI_API_KEY")
CST = timezone(timedelta(hours=8))  # China Standard Time (UTC+8)


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_api_key(override: str | None) -> str:
    """Resolve API key: CLI arg > env var > hardcoded default."""
    if override:
        return override
    return os.environ.get("QINIU_API_KEY", DEFAULT_API_KEY)


def to_rfc3339(dt: datetime) -> str:
    """Convert datetime to RFC3339 format with +08:00 timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def parse_date_arg(s: str) -> datetime:
    """Parse date string in YYYY-MM-DD or RFC3339 format."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt[: len(s[:19])])
            return dt.replace(tzinfo=CST)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}. Use YYYY-MM-DD or RFC3339.")


def build_url(granularity: str, start: datetime, end: datetime) -> str:
    params = urllib.parse.urlencode(
        {
            "granularity": granularity,
            "start": to_rfc3339(start),
            "end": to_rfc3339(end),
        }
    )
    return f"{BASE_URL}{USAGE_PATH}?{params}"


def fetch_usage(api_key: str, granularity: str, start: datetime, end: datetime) -> dict:
    url = build_url(granularity, start, end)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


# ── Formatting ────────────────────────────────────────────────────────────────


def format_value(v: float) -> str:
    """Format kToken value with appropriate precision."""
    if v >= 1000:
        return f"{v / 1000:.2f} MToken"
    elif v >= 1:
        return f"{v:.3f} kToken"
    else:
        return f"{v * 1000:.0f} Token"


def print_table(data: list, granularity: str, start: datetime, end: datetime) -> None:
    """Print a human-readable summary table."""
    print()
    print(f"  Qiniu AI Token Usage Report")
    print(f"  Period : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity: {granularity}")
    print()

    if not data:
        print("  No usage data found.")
        return

    # Aggregate totals per model
    models_summary = []
    for model in data:
        model_id = model.get("name", model.get("id", "unknown"))
        input_total = 0.0
        output_total = 0.0

        for item in model.get("items", []):
            name = item.get("name", "")
            total = item.get("total", 0.0)
            if "输入" in name or "input" in name.lower():
                input_total += total
            elif "输出" in name or "output" in name.lower():
                output_total += total

        models_summary.append(
            {
                "model": model_id,
                "input": input_total,
                "output": output_total,
                "total": input_total + output_total,
            }
        )

    # Sort by total usage descending
    models_summary.sort(key=lambda x: x["total"], reverse=True)

    # Column widths
    col_model = max(len("Model"), max(len(m["model"]) for m in models_summary))
    col_input = 18
    col_output = 18
    col_total = 18

    header = f"  {'Model':<{col_model}}  {'Input':>{col_input}}  {'Output':>{col_output}}  {'Total':>{col_total}}"
    sep = (
        f"  {'-' * col_model}  {'-' * col_input}  {'-' * col_output}  {'-' * col_total}"
    )

    print(header)
    print(sep)

    grand_input = 0.0
    grand_output = 0.0

    for m in models_summary:
        row = (
            f"  {m['model']:<{col_model}}"
            f"  {format_value(m['input']):>{col_input}}"
            f"  {format_value(m['output']):>{col_output}}"
            f"  {format_value(m['total']):>{col_total}}"
        )
        print(row)
        grand_input += m["input"]
        grand_output += m["output"]

    print(sep)
    grand_total = grand_input + grand_output
    print(
        f"  {'TOTAL':<{col_model}}"
        f"  {format_value(grand_input):>{col_input}}"
        f"  {format_value(grand_output):>{col_output}}"
        f"  {format_value(grand_total):>{col_total}}"
    )
    print()

    # Daily breakdown (only for day granularity, if multiple days)
    if granularity == "day":
        print_daily_breakdown(data)


def print_daily_breakdown(data: list) -> None:
    """Print day-by-day breakdown for all models combined."""
    # Collect all dates
    date_totals: dict[str, dict] = {}

    for model in data:
        for item in model.get("items", []):
            name = item.get("name", "")
            is_input = "输入" in name or "input" in name.lower()

            for cat in item.get("categories", []):
                for entry in cat.get("values", []):
                    date = entry["time"]
                    val = entry.get("value", 0.0)
                    if val == 0:
                        continue
                    if date not in date_totals:
                        date_totals[date] = {"input": 0.0, "output": 0.0}
                    if is_input:
                        date_totals[date]["input"] += val
                    else:
                        date_totals[date]["output"] += val

    if not date_totals:
        return

    active_dates = sorted(date_totals.keys())
    print(f"  Daily Breakdown ({len(active_dates)} active days)")
    print(f"  {'Date':<12}  {'Input':>18}  {'Output':>18}  {'Total':>18}")
    print(f"  {'-' * 12}  {'-' * 18}  {'-' * 18}  {'-' * 18}")

    for date in active_dates:
        d = date_totals[date]
        total = d["input"] + d["output"]
        print(
            f"  {date:<12}"
            f"  {format_value(d['input']):>18}"
            f"  {format_value(d['output']):>18}"
            f"  {format_value(total):>18}"
        )
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query Qiniu AI API token usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--granularity",
        choices=["day", "hour"],
        default="day",
        help="Time granularity (default: day)",
    )
    parser.add_argument("--start", help="Start datetime (YYYY-MM-DD or RFC3339)")
    parser.add_argument("--end", help="End datetime (YYYY-MM-DD or RFC3339)")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Query last N days (default mode if no other shortcut given)",
    )
    parser.add_argument("--today", action="store_true", help="Query today only")
    parser.add_argument("--month", action="store_true", help="Query current month")
    parser.add_argument(
        "--json", action="store_true", dest="output_json", help="Output raw JSON"
    )
    parser.add_argument("--api-key", dest="api_key", help="Override API key")
    return parser.parse_args()


def resolve_time_range(args) -> tuple[datetime, datetime]:
    now = datetime.now(CST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if args.today:
        return today_start, now

    if args.month:
        month_start = today_start.replace(day=1)
        return month_start, now

    if args.start and args.end:
        return parse_date_arg(args.start), parse_date_arg(args.end)

    if args.start:
        start = parse_date_arg(args.start)
        return start, now

    # Default: last N days (default 7)
    days = args.days if args.days is not None else 7
    start = today_start - timedelta(days=days - 1)
    return start, now


def main():
    args = parse_args()
    api_key = get_api_key(args.api_key)
    start, end = resolve_time_range(args)

    # Validate time range limits
    delta = end - start
    if args.granularity == "day" and delta.days > 31:
        print("Error: day granularity supports max 31 days range.", file=sys.stderr)
        sys.exit(1)
    if args.granularity == "hour" and delta.days > 7:
        print("Error: hour granularity supports max 7 days range.", file=sys.stderr)
        sys.exit(1)

    result = fetch_usage(api_key, args.granularity, start, end)

    if not result.get("status"):
        print(f"API error: {result}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_table(result.get("data", []), args.granularity, start, end)


if __name__ == "__main__":
    main()
