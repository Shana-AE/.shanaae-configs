#!/usr/bin/env python3
"""
Qiniu AI Token Usage Query Tool
Query token usage for the Qiniu AI API (api.qnaigc.com) with cost calculation.

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
    --cost          Show cost calculation (USD + CNY)
    --update-prices Fetch latest prices from sufy.com
    --update-rate   Fetch latest USD/CNY exchange rate
    --api-key       Override API key (default: reads QINIU_AI_API_KEY env)
    --list-prices   List all cached model prices
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.qnaigc.com"
USAGE_PATH = "/v2/stat/usage"
PRICING_URL = "https://sufy.com/zh-CN/services/ai-inference/models"
PRICES_CACHE_FILE = os.path.expanduser("~/.cache/qiniu_prices.json")
DEFAULT_API_KEY = os.environ.get("QINIU_AI_API_KEY")
CST = timezone(timedelta(hours=8))  # China Standard Time (UTC+8)

# Exchange rate API (free, no key required)
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"

# Default USD to CNY exchange rate (fallback when API unavailable)
DEFAULT_USD_TO_CNY = 7.25

# Default pricing (USD per 1M tokens) - fallback when cache unavailable
# Source: https://sufy.com/zh-CN/services/ai-inference/models
DEFAULT_PRICING = {
    # Claude 4 Series
    "claude-4.6-sonnet": {"input": 3.0, "output": 15.0},
    "claude-4.6-opus": {"input": 15.0, "output": 75.0},
    "claude-4.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-4.5-haiku": {"input": 1.0, "output": 5.0},
    "claude-4.5-opus": {"input": 15.0, "output": 75.0},
    "claude-4.0-sonnet": {"input": 3.0, "output": 15.0},
    "claude-4.0-opus": {"input": 15.0, "output": 75.0},
    "claude-4.1-opus": {"input": 15.0, "output": 75.0},
    # Claude 3 Series
    "claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3.5-haiku": {"input": 0.8, "output": 4.0},
    "claude-3.7-sonnet": {"input": 3.0, "output": 15.0},
    # OpenAI GPT Series
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "gpt-5": {"input": 1.25, "output": 10.0},
    "gpt-5.2": {"input": 1.75, "output": 14.0},
    # Gemini
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 2.5},
    "gemini-2.0-flash": {"input": 0.15, "output": 0.6},
    # DeepSeek
    "deepseek-v3": {"input": 0.278, "output": 1.11},
    "deepseek-v3.1": {"input": 0.556, "output": 1.67},
    "deepseek-r1": {"input": 0.556, "output": 2.22},
    # Doubao
    "doubao-1.5-pro-32k": {"input": 0.111, "output": 0.278},
    "doubao-seed-1.6": {"input": 0.111, "output": 0.278},
    # Qwen
    "qwen-turbo": {"input": 0.042, "output": 0.417},
    "qwen3-max": {"input": 0.833, "output": 3.33},
    # GLM
    "glm-4.5": {"input": 0.556, "output": 2.22},
    "glm-4.6": {"input": 1.0, "output": 1.75},
    # Kimi
    "kimi-k2": {"input": 0.556, "output": 2.22},
}


# ── Price Management ────────────────────────────────────────────────────────


def get_exchange_rate() -> float:
    """Fetch current USD to CNY exchange rate."""
    try:
        req = urllib.request.Request(
            EXCHANGE_RATE_API,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            rate = data.get("rates", {}).get("CNY", DEFAULT_USD_TO_CNY)
            print(f"Fetched exchange rate: 1 USD = ¥{rate:.4f} CNY", file=sys.stderr)
            return rate
    except Exception as e:
        print(f"Failed to fetch exchange rate: {e}", file=sys.stderr)
        return DEFAULT_USD_TO_CNY


def load_prices() -> tuple[dict, float]:
    """Load prices and exchange rate from cache or return defaults."""
    if os.path.exists(PRICES_CACHE_FILE):
        try:
            with open(PRICES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("prices", DEFAULT_PRICING), data.get(
                    "exchange_rate", DEFAULT_USD_TO_CNY
                )
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_PRICING, DEFAULT_USD_TO_CNY


def save_prices(prices: dict, exchange_rate: float) -> None:
    """Save prices and exchange rate to cache file."""
    os.makedirs(os.path.dirname(PRICES_CACHE_FILE), exist_ok=True)
    data = {
        "updated": datetime.now(CST).isoformat(),
        "source": PRICING_URL,
        "exchange_rate": exchange_rate,
        "prices": prices,
    }
    with open(PRICES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_model_name(name: str) -> str:
    """Normalize model name for consistent matching."""
    name = name.strip().lower()
    # Replace spaces and slashes with dashes
    name = re.sub(r"[\s/]+", "-", name)
    # Remove multiple consecutive dashes
    name = re.sub(r"-+", "-", name)
    # Remove common prefixes/suffixes
    name = name.strip("-")
    return name


def parse_html_prices(html: str) -> dict:
    """Parse model prices from sufy.com HTML."""
    prices = {}
    
    # Model names are in <h3> tags
    h3_pattern = re.compile(r'<h3[^>]*>([^<]+)</h3>', re.IGNORECASE)
    
    # Price pattern: <span...text-gray-500...>输入</span><span...text-blue-400...>$X.XX /M tokens</span>
    price_pattern = re.compile(
        r'<span[^>]*text-gray-500[^>]*>(输入|输出|缓存输入|批量输入|思考输入|思考输出)</span>'
        r'.*?'
        r'<span[^>]*text-blue-400[^>]*>\$([\d.]+)\s*/M\s*tokens</span>',
        re.DOTALL | re.IGNORECASE
    )

    # Find all h3 positions
    h3_matches = list(h3_pattern.finditer(html))
    
    # For each h3, find the prices that follow until the next h3
    for i, h3_match in enumerate(h3_matches):
        model_name = h3_match.group(1).strip()
        start_pos = h3_match.end()
        
        # Find the end of this card (next h3 or end of content)
        if i + 1 < len(h3_matches):
            end_pos = h3_matches[i + 1].start()
        else:
            end_pos = len(html)
        
        card_content = html[start_pos:end_pos]
        
        # Find prices in this card
        input_price = None
        output_price = None
        
        for price_match in price_pattern.finditer(card_content):
            price_type = price_match.group(1)
            price_value = float(price_match.group(2))
            
            if price_type in ['输入', '缓存输入', '批量输入', '思考输入']:
                if input_price is None:  # Take first input price
                    input_price = price_value
            elif price_type in ['输出', '思考输出']:
                if output_price is None:  # Take first output price
                    output_price = price_value
        
        if input_price is not None or output_price is not None:
            normalized_name = normalize_model_name(model_name)
            prices[normalized_name] = {
                'input': input_price or 0.0,
                'output': output_price or 0.0
            }
    
    return prices


def fetch_prices_from_web() -> tuple[dict, float]:
    """Fetch latest prices from sufy.com website."""
    print("Fetching prices from sufy.com...", file=sys.stderr)
    
    # Fetch exchange rate first
    exchange_rate = get_exchange_rate()

    try:
        req = urllib.request.Request(
            PRICING_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Failed to fetch prices: {e}", file=sys.stderr)
        print("Using default pricing.", file=sys.stderr)
        return DEFAULT_PRICING, exchange_rate

    # Parse prices from HTML
    prices = parse_html_prices(html)
    
    if prices:
        print(f"Successfully fetched prices for {len(prices)} models", file=sys.stderr)
        save_prices(prices, exchange_rate)
        return prices, exchange_rate
    else:
        print("Could not parse prices from web page.", file=sys.stderr)
        print("Using default pricing.", file=sys.stderr)
        save_prices(DEFAULT_PRICING, exchange_rate)
        return DEFAULT_PRICING, exchange_rate
# ── Helpers ───────────────────────────────────────────────────────────────────


def get_api_key(override: str | None) -> str:
    """Resolve API key: CLI arg > env var."""
    if override:
        return override
    key = os.environ.get("QINIU_AI_API_KEY") or os.environ.get("QINIU_API_KEY")
    if not key:
        print("Error: No API key found. Set QINIU_AI_API_KEY env var or use --api-key", file=sys.stderr)
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


# ── Cost Calculation ────────────────────────────────────────────────────────


def find_pricing(model_id: str, prices: dict) -> Optional[dict]:
    """Find pricing for a model, trying various matching strategies."""
    model_lower = normalize_model_name(model_id)

    # Exact match
    if model_lower in prices:
        return prices[model_lower]

    # Try partial matching for common model name variations
    for key in prices:
        # Check if key is a substring of model name or vice versa
        if key in model_lower or model_lower in key:
            return prices[key]
        # Check if most significant parts match
        key_parts = set(key.split("-"))
        model_parts = set(model_lower.split("-"))
        # If key parts are subset of model parts
        if key_parts and key_parts.issubset(model_parts):
            return prices[key]

    return None


def calculate_cost(
    model_id: str, input_ktokens: float, output_ktokens: float, prices: dict
) -> tuple:
    """
    Calculate cost based on model pricing.
    Returns: (input_cost_usd, output_cost_usd, pricing_found)
    """
    pricing = find_pricing(model_id, prices)

    if not pricing:
        return 0.0, 0.0, False

    # kToken / 1000 = MToken, then * price = USD
    input_cost_usd = (input_ktokens / 1000.0) * pricing["input"]
    output_cost_usd = (output_ktokens / 1000.0) * pricing["output"]

    return input_cost_usd, output_cost_usd, True


# ── Formatting ────────────────────────────────────────────────────────────────


def format_value(v: float) -> str:
    """Format kToken value with appropriate precision."""
    if v >= 1000:
        return f"{v / 1000:.2f} MToken"
    elif v >= 1:
        return f"{v:.3f} kToken"
    else:
        return f"{v * 1000:.0f} Token"


def format_cost(usd: float, exchange_rate: float) -> str:
    """Format cost in USD and CNY."""
    cny = usd * exchange_rate
    if usd >= 1:
        return f"${usd:.2f} (¥{cny:.1f})"
    elif usd >= 0.01:
        return f"${usd:.3f} (¥{cny:.2f})"
    else:
        return f"${usd:.4f} (¥{cny:.3f})"


def print_table(
    data: list,
    granularity: str,
    start: datetime,
    end: datetime,
    show_cost: bool = False,
    prices: dict = None,
    exchange_rate: float = DEFAULT_USD_TO_CNY,
) -> None:
    """Print a human-readable summary table."""
    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Token Usage Report")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity : {granularity}")
    if show_cost:
        print(f"  Exchange    : 1 USD = ¥{exchange_rate:.2f} CNY")
    print()

    if not data:
        print("  No usage data found.")
        return

    if prices is None:
        prices = DEFAULT_PRICING

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

        input_cost_usd, output_cost_usd, pricing_found = calculate_cost(
            model_id, input_total, output_total, prices
        )

        models_summary.append(
            {
                "model": model_id,
                "input": input_total,
                "output": output_total,
                "total": input_total + output_total,
                "input_cost_usd": input_cost_usd,
                "output_cost_usd": output_cost_usd,
                "cost_usd": input_cost_usd + output_cost_usd,
                "pricing_found": pricing_found,
            }
        )

    # Sort by total usage descending
    models_summary.sort(key=lambda x: x["total"], reverse=True)

    # Column widths
    col_model = max(18, max(len(m["model"]) for m in models_summary))
    col_tokens = 16
    col_cost = 20

    if show_cost:
        print(
            f"  {'Model':<{col_model}} │ {'Tokens':>{col_tokens}} │ {'Cost (USD/CNY)':>{col_cost}}"
        )
        print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")
    else:
        print(
            f"  {'Model':<{col_model}} │ {'Input':>{col_tokens}} │ {'Output':>{col_tokens}} │ {'Total':>{col_tokens}}"
        )
        print(
            f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )

    grand_input = 0.0
    grand_output = 0.0
    grand_cost_usd = 0.0

    for m in models_summary:
        if show_cost:
            cost_str = (
                format_cost(m["cost_usd"], exchange_rate)
                if m["pricing_found"]
                else "N/A"
            )
            total_str = format_value(m["total"])
            print(
                f"  {m['model']:<{col_model}} │ {total_str:>{col_tokens}} │ {cost_str:>{col_cost}}"
            )
        else:
            print(
                f"  {m['model']:<{col_model}} │ {format_value(m['input']):>{col_tokens}} │ "
                f"{format_value(m['output']):>{col_tokens}} │ {format_value(m['total']):>{col_tokens}}"
            )
        grand_input += m["input"]
        grand_output += m["output"]
        grand_cost_usd += m["cost_usd"]

    grand_total = grand_input + grand_output

    if show_cost:
        print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")
        cost_str = format_cost(grand_cost_usd, exchange_rate)
        print(
            f"  {'TOTAL':<{col_model}} │ {format_value(grand_total):>{col_tokens}} │ {cost_str:>{col_cost}}"
        )
    else:
        print(
            f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )
        print(
            f"  {'TOTAL':<{col_model}} │ {format_value(grand_input):>{col_tokens}} │ "
            f"{format_value(grand_output):>{col_tokens}} │ {format_value(grand_total):>{col_tokens}}"
        )
    print()

    # Daily breakdown (only for day granularity, if multiple days)
    if granularity == "day":
        print_daily_breakdown(data, show_cost, prices, exchange_rate)


def print_daily_breakdown(
    data: list,
    show_cost: bool = False,
    prices: dict = None,
    exchange_rate: float = DEFAULT_USD_TO_CNY,
) -> None:
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
    print(f"  ─── Daily Breakdown ({len(active_dates)} active days) ───")

    if show_cost and prices:
        # Calculate average pricing for estimation
        avg_input_price = (
            sum(p["input"] for p in prices.values()) / len(prices) if prices else 3.0
        )
        avg_output_price = (
            sum(p["output"] for p in prices.values()) / len(prices) if prices else 15.0
        )

        col_date = 12
        col_tokens = 16
        col_cost = 20

        print(
            f"  {'Date':<{col_date}} │ {'Tokens':>{col_tokens}} │ {'Est. Cost':>{col_cost}}"
        )
        print(f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")

        for date in active_dates:
            d = date_totals[date]
            total = d["input"] + d["output"]
            # Estimate cost using average pricing
            cost_usd = (d["input"] / 1000 * avg_input_price) + (
                d["output"] / 1000 * avg_output_price
            )
            cost_str = format_cost(cost_usd, exchange_rate)

            print(
                f"  {date:<{col_date}} │ {format_value(total):>{col_tokens}} │ {cost_str:>{col_cost}}"
            )
    else:
        col_date = 12
        col_tokens = 16

        print(
            f"  {'Date':<{col_date}} │ {'Input':>{col_tokens}} │ {'Output':>{col_tokens}} │ {'Total':>{col_tokens}}"
        )
        print(
            f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )

        for date in active_dates:
            d = date_totals[date]
            total = d["input"] + d["output"]
            print(
                f"  {date:<{col_date}} │ {format_value(d['input']):>{col_tokens}} │ "
                f"{format_value(d['output']):>{col_tokens}} │ {format_value(total):>{col_tokens}}"
            )
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query Qiniu AI API token usage with cost calculation",
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
        "--cost",
        "--price",
        action="store_true",
        dest="show_cost",
        help="Show cost in USD and CNY",
    )
    parser.add_argument(
        "--update-prices",
        action="store_true",
        dest="update_prices",
        help="Fetch latest prices from sufy.com",
    )
    parser.add_argument(
        "--update-rate",
        action="store_true",
        dest="update_rate",
        help="Fetch latest USD/CNY exchange rate",
    )
    parser.add_argument(
        "--list-prices",
        action="store_true",
        dest="list_prices",
        help="List all cached model prices",
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

    # Handle price listing
    if args.list_prices:
        prices, exchange_rate = load_prices()
        print(f"\nCached Model Prices (Exchange Rate: 1 USD = ¥{exchange_rate:.2f})")
        print("=" * 70)
        for name, pricing in sorted(prices.items()):
            input_cny = pricing["input"] * exchange_rate
            output_cny = pricing["output"] * exchange_rate
            print(
                f"  {name:<30} Input: ${pricing['input']:.3f} (¥{input_cny:.2f})  Output: ${pricing['output']:.3f} (¥{output_cny:.2f})"
            )
        print(f"\nTotal: {len(prices)} models")
        print(f"Cache file: {PRICES_CACHE_FILE}")
        return

    # Handle price update
    if args.update_prices:
        prices, exchange_rate = fetch_prices_from_web()
        print(f"\n✓ Prices updated and cached to: {PRICES_CACHE_FILE}")
        print(f"✓ Total models: {len(prices)}")
        print(f"✓ Exchange rate: 1 USD = ¥{exchange_rate:.4f} CNY")
        return

    # Handle exchange rate update only
    if args.update_rate:
        exchange_rate = get_exchange_rate()
        prices, _ = load_prices()
        save_prices(prices, exchange_rate)
        print(f"\n✓ Exchange rate updated: 1 USD = ¥{exchange_rate:.4f} CNY")
        print(f"✓ Cached to: {PRICES_CACHE_FILE}")
        return

    # Load prices
    prices, exchange_rate = load_prices()

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
        print_table(
            result.get("data", []),
            args.granularity,
            start,
            end,
            args.show_cost,
            prices,
            exchange_rate,
        )


if __name__ == "__main__":
    main()
