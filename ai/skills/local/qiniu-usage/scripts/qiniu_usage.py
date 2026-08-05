#!/usr/bin/env python3
"""
Qiniu AI Token Usage Query Tool
Query token usage for the Qiniu AI API (api.qnaigc.com).

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
    --api-key       Override API key (default: reads QINIU_AI_API_KEY env)
    --bill          Query estimated billing (day/week/month)
    --bill-type     Billing period: day, week, month (default: month)
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.qnaigc.com"
USAGE_PATH = "/v2/stat/usage"
DEFAULT_API_KEY = os.environ.get("QINIU_AI_API_KEY")
CST = timezone(timedelta(hours=8))  # China Standard Time (UTC+8)


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_api_key(override: str | None) -> str:
    """Resolve API key: CLI arg > env var."""
    if override:
        return override
    key = os.environ.get("QINIU_AI_API_KEY") or os.environ.get("QINIU_API_KEY")
    if not key:
        print(
            "Error: No API key found. Set QINIU_AI_API_KEY env var or use --api-key",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


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


# ── Formatting ────────────────────────────────────────────────────────────────


def count_to_mtoken(count: float, unit: str) -> float:
    """Convert a usage count to MToken based on its unit."""
    unit = unit or "k/tokens"
    if unit == "default":
        return count / 1_000_000.0
    elif unit in ("k/tokens", "kToken"):
        return count / 1000.0
    else:
        return 0.0


def format_mtoken(v: float) -> str:
    """Format MToken value with appropriate precision."""
    if v >= 1:
        return f"{v:.2f} MToken"
    elif v >= 0.01:
        return f"{v:.2f} MToken"
    elif v > 0:
        return f"{v:.4f} MToken"
    else:
        return "0"


def fetch_billing(api_key: str, bill_type: str) -> dict:
    """Fetch estimated billing from /v2/stat/usage/apikey/cost."""
    if bill_type not in ("day", "week", "month"):
        print(f"Error: --bill-type must be day, week, or month", file=sys.stderr)
        sys.exit(1)
    url = f"{BASE_URL}/v2/stat/usage/apikey/cost?type={bill_type}"
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


def print_billing(data: dict, bill_type: str) -> None:
    """Print estimated billing report."""
    period_label = {"day": "Today", "week": "This Week", "month": "This Month"}
    api_keys = data.get("api_keys", [])

    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Estimated Billing Report")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {period_label.get(bill_type, bill_type)}")
    print(f"  Note        : Estimated prices at original rate (CNY)")
    print()

    if not api_keys:
        print("  No billing data found.")
        return

    # Aggregate across all api_keys (usually just one)
    # Collect per-model totals
    model_totals: dict[str, dict] = {}
    for key_data in api_keys:
        for model in key_data.get("models", []):
            model_id = model.get("model_id", "unknown")
            total_fee = model.get("total_fee", 0.0)
            if model_id not in model_totals:
                model_totals[model_id] = {"fee": 0.0, "items": []}
            model_totals[model_id]["fee"] += total_fee
            # Merge items for detail
            for item in model.get("items", []):
                model_totals[model_id]["items"].append(item)

    if not model_totals:
        print("  No billing data found.")
        return

    # Sort by fee descending
    sorted_models = sorted(
        model_totals.items(), key=lambda x: x[1]["fee"], reverse=True
    )

    col_model = max(18, max(len(m) for m, _ in sorted_models))
    col_tokens = 16
    col_fee = 14

    print(
        f"  {'Model':<{col_model}} │ {'Tokens (MToken)':>{col_tokens}} │ {'Fee (CNY)':>{col_fee}}"
    )
    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_fee}")

    grand_fee = 0.0
    grand_mtokens = 0.0

    for model_id, mdata in sorted_models:
        fee = mdata["fee"]
        total_mtokens = 0.0
        image_count = 0
        for item in mdata["items"]:
            usage = item.get("usage", {})
            count = usage.get("count", 0.0)
            unit = usage.get("unit", "k/tokens")
            if unit in ("张", "image"):
                image_count += int(count)
            else:
                total_mtokens += count_to_mtoken(count, unit)
        grand_fee += fee
        grand_mtokens += total_mtokens

        if total_mtokens > 0:
            token_str = format_mtoken(total_mtokens)
        elif image_count > 0:
            token_str = f"({image_count} image{'s' if image_count != 1 else ''})"
        else:
            token_str = "0"

        fee_str = f"¥{fee:.4f}" if fee < 0.01 else f"¥{fee:.2f}"
        print(
            f"  {model_id:<{col_model}} │ {token_str:>{col_tokens}} │ {fee_str:>{col_fee}}"
        )

    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_fee}")
    grand_fee_str = f"¥{grand_fee:.4f}" if grand_fee < 0.01 else f"¥{grand_fee:.2f}"
    print(
        f"  {'TOTAL':<{col_model}} │ {format_mtoken(grand_mtokens):>{col_tokens}} │ {grand_fee_str:>{col_fee}}"
    )
    print()


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


def print_table(
    data: list,
    granularity: str,
    start: datetime,
    end: datetime,
) -> None:
    """Print a human-readable summary table."""
    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Token Usage Report")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity : {granularity}")
    print()

    if not data:
        print("  No usage data found.")
        return

    # Aggregate totals per model
    models_summary = []
    for model in data:
        model_id = model.get("name", model.get("id", "unknown"))
        input_mtokens = 0.0
        output_mtokens = 0.0

        for item in model.get("items", []):
            name = item.get("name", "")
            total = item.get("total", 0.0)
            unit = item.get("unit", "kToken")
            mtokens = count_to_mtoken(total, unit)
            if "输入" in name or "input" in name.lower():
                input_mtokens += mtokens
            elif "输出" in name or "output" in name.lower():
                output_mtokens += mtokens

        models_summary.append(
            {
                "model": model_id,
                "input": input_mtokens,
                "output": output_mtokens,
                "total": input_mtokens + output_mtokens,
            }
        )

    # Sort by total usage descending
    models_summary.sort(key=lambda x: x["total"], reverse=True)

    # Column widths
    col_model = max(18, max(len(m["model"]) for m in models_summary))
    col_tokens = 16

    print(
        f"  {'Model':<{col_model}} │ {'Input (MToken)':>{col_tokens}} │ {'Output (MToken)':>{col_tokens}} │ {'Total (MToken)':>{col_tokens}}"
    )
    print(
        f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
    )

    grand_input = 0.0
    grand_output = 0.0

    for m in models_summary:
        print(
            f"  {m['model']:<{col_model}} │ {format_mtoken(m['input']):>{col_tokens}} │ "
            f"{format_mtoken(m['output']):>{col_tokens}} │ {format_mtoken(m['total']):>{col_tokens}}"
        )
        grand_input += m["input"]
        grand_output += m["output"]

    grand_total = grand_input + grand_output

    print(
        f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
    )
    print(
        f"  {'TOTAL':<{col_model}} │ {format_mtoken(grand_input):>{col_tokens}} │ "
        f"{format_mtoken(grand_output):>{col_tokens}} │ {format_mtoken(grand_total):>{col_tokens}}"
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
            unit = item.get("unit", "kToken")
            is_input = "输入" in name or "input" in name.lower()

            for cat in item.get("categories", []):
                for entry in cat.get("values", []):
                    date = entry["time"]
                    val = entry.get("value", 0.0)
                    if val == 0:
                        continue
                    mtokens = count_to_mtoken(val, unit)
                    if date not in date_totals:
                        date_totals[date] = {"input": 0.0, "output": 0.0}
                    if is_input:
                        date_totals[date]["input"] += mtokens
                    else:
                        date_totals[date]["output"] += mtokens

    if not date_totals:
        return

    active_dates = sorted(date_totals.keys())
    print(f"  ─── Daily Breakdown ({len(active_dates)} active days) ───")

    col_date = 12
    col_tokens = 16

    print(
        f"  {'Date':<{col_date}} │ {'Input (MToken)':>{col_tokens}} │ {'Output (MToken)':>{col_tokens}} │ {'Total (MToken)':>{col_tokens}}"
    )
    print(
        f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
    )

    for date in active_dates:
        d = date_totals[date]
        total = d["input"] + d["output"]
        print(
            f"  {date:<{col_date}} │ {format_mtoken(d['input']):>{col_tokens}} │ "
            f"{format_mtoken(d['output']):>{col_tokens}} │ {format_mtoken(total):>{col_tokens}}"
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
    parser.add_argument(
        "--bill",
        action="store_true",
        help="Query estimated billing (use --bill-type to set period)",
    )
    parser.add_argument(
        "--bill-type",
        dest="bill_type",
        choices=["day", "week", "month"],
        default="month",
        help="Billing period: day, week, or month (default: month)",
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

    # Handle billing query
    if args.bill:
        result = fetch_billing(api_key, args.bill_type)
        if not result.get("status"):
            print(f"API error: {result}", file=sys.stderr)
            sys.exit(1)
        if args.output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_billing(result.get("data", {}), args.bill_type)
        return

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
        print_table(
            result.get("data", []),
            args.granularity,
            start,
            end,
        )


if __name__ == "__main__":
    main()
