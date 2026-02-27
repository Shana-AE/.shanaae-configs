---
name: qiniu-usage
description: Query Qiniu AI API (api.qnaigc.com) token usage and calculate costs in USD/CNY. Use when the user asks about API consumption (用量), token stats, how much they've used, costs (费用), or billing data for Qiniu AI models.
---

# Qiniu AI Usage Manager

This skill queries token usage data from the Qiniu AI API (`api.qnaigc.com`) using the `/v2/stat/usage` endpoint and calculates costs based on model pricing.

## Features

- **Token Usage Query**: Query usage by model, day, or time range
- **Cost Calculation**: Show costs in USD and CNY (人民币)
- **Live Exchange Rate**: Fetch real-time USD/CNY rate from API
- **Price Management**: Update prices from sufy.com
- **Price Listing**: View all cached model prices with CNY conversion

## Prerequisites

- **API Key**: Set `QINIU_AI_API_KEY` environment variable or use `--api-key` flag
- **Python 3**: Script uses only stdlib — no pip install needed

## Script Location

```
scripts/qiniu_usage.py
```

## Usage

### General Syntax

```bash
python3 scripts/qiniu_usage.py [OPTIONS]
```

### Common Commands

#### Query today's usage with cost
```bash
python3 scripts/qiniu_usage.py --today --cost
```

#### Query last 7 days (default)
```bash
python3 scripts/qiniu_usage.py
```

#### Query current month with cost
```bash
python3 scripts/qiniu_usage.py --month --cost
```

#### Query specific date range
```bash
python3 scripts/qiniu_usage.py --start 2026-02-01 --end 2026-02-25 --cost
```

#### Update prices and exchange rate from sufy.com
```bash
python3 scripts/qiniu_usage.py --update-prices
```

#### Update only exchange rate
```bash
python3 scripts/qiniu_usage.py --update-rate
```

#### List all cached model prices with CNY conversion
```bash
python3 scripts/qiniu_usage.py --list-prices
```

#### Hour-level granularity (max 7 days)
```bash
python3 scripts/qiniu_usage.py --granularity hour --days 3 --cost
```

#### Output raw JSON
```bash
python3 scripts/qiniu_usage.py --today --json
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--granularity` | `day` or `hour` | `day` |
| `--start` | Start date `YYYY-MM-DD` or RFC3339 | — |
| `--end` | End date `YYYY-MM-DD` or RFC3339 | — |
| `--days N` | Query last N days | 7 |
| `--today` | Query today only | — |
| `--month` | Query current month | — |
| `--json` | Raw JSON output | — |
| `--cost` | Show cost in USD and CNY | — |
| `--update-prices` | Fetch latest prices from sufy.com | — |
| `--update-rate` | Fetch latest USD/CNY exchange rate | — |
| `--list-prices` | List all cached model prices | — |
| `--api-key` | Override API key | env variable |

## Time Range Limits (API constraint)

- `--granularity day`: max **31 days**
- `--granularity hour`: max **7 days**

## Output Format

### Without `--cost` flag

```
  Model                   Input          Output           Total
  ---------------  ------------  --------------  --------------
  claude-4.6-sonnet   498.9 kToken    2.2 kToken   501.1 kToken
  TOTAL               554.4 kToken    2.3 kToken   556.7 kToken
```

### With `--cost` flag

```
  ═══════════════════════════════════════════════════════════════
  Qiniu AI Token Usage Report
  ═══════════════════════════════════════════════════════════════
  Period      : 2026-02-26 ~ 2026-02-26
  Granularity : day
  Exchange    : 1 USD = ¥7.25 CNY

  Model                │           Tokens │       Cost (USD/CNY)
  ─────────────────────┼──────────────────┼─────────────────────
  claude-4.6-sonnet    │      9.40 MToken │      $28.51 (¥206.7)
  ─────────────────────┼──────────────────┼─────────────────────
  TOTAL                │      9.40 MToken │      $28.51 (¥206.7)
```

### With `--list-prices` flag

```
Cached Model Prices (Exchange Rate: 1 USD = ¥7.25)
======================================================================
  claude-4.6-sonnet              Input: $3.000 (¥21.75)  Output: $15.000 (¥108.75)
  claude-4.6-opus                Input: $15.000 (¥108.75)  Output: $75.000 (¥543.75)
  deepseek-v3                    Input: $0.278 (¥2.02)  Output: $1.110 (¥8.05)
  ...

Total: 50 models
Cache file: ~/.cache/qiniu_prices.json
```

## Pricing Source

Prices are sourced from [sufy.com](https://sufy.com/zh-CN/services/ai-inference/models) and cached locally at `~/.cache/qiniu_prices.json`.

### Exchange Rate

- **Default**: 7.25 CNY per USD (fallback)
- **Live**: Fetched from exchangerate-api.com when using `--update-prices` or `--update-rate`
- The exchange rate is cached alongside prices for consistent cost calculations

### Supported Models (with pricing)

| Model | Input ($/M) | Output ($/M) | Input (¥/M) | Output (¥/M) |
|-------|-------------|--------------|-------------|--------------|
| claude-4.6-sonnet | 3.0 | 15.0 | ~21.75 | ~108.75 |
| claude-4.6-opus | 15.0 | 75.0 | ~108.75 | ~543.75 |
| claude-4.5-sonnet | 3.0 | 15.0 | ~21.75 | ~108.75 |
| claude-4.5-haiku | 1.0 | 5.0 | ~7.25 | ~36.25 |
| gpt-5 | 1.25 | 10.0 | ~9.06 | ~72.50 |
| gpt-5.2 | 1.75 | 14.0 | ~12.69 | ~101.50 |
| deepseek-v3 | 0.278 | 1.11 | ~2.02 | ~8.05 |
| deepseek-v3.1 | 0.556 | 1.67 | ~4.03 | ~12.11 |
| deepseek-r1 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| qwen3-max | 0.833 | 3.33 | ~6.04 | ~24.14 |
| glm-4.5 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| kimi-k2 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| ... | ... | ... | ... | ... |

Run `--update-prices` to fetch the latest pricing with current exchange rate from sufy.com.
## Workflow for the Agent

When the user asks about Qiniu usage:

1. **Determine the time range** from user's request:
   - "今天用了多少" / "今天花了多少钱" → `--today --cost`
   - "这个月用了多少" → `--month --cost`
   - "最近7天" → `--days 7`
   - Specific range → `--start YYYY-MM-DD --end YYYY-MM-DD`

2. **Determine if cost is needed**:
   - "用了多少钱" / "花费" / "费用" / "多少钱" / "人民币" → add `--cost`
   - Just "用量" / "token" → no `--cost` needed

3. **Run the script**:
   ```bash
   python3 scripts/qiniu_usage.py --today --cost
   ```

4. **Interpret and present** the output to the user in a readable summary.

### Additional Operations

- **Check model prices**: `--list-prices`
- **Update pricing**: `--update-prices` (fetches both prices and exchange rate)
- **Update exchange rate only**: `--update-rate`

## API Key

The default key is `$QINIU_AI_API_KEY`. The key is associated with account on `portal.qiniu.com`. Data returned is scoped to this API key's usage only.

To use a different key:
```bash
export QINIU_AI_API_KEY='sk-xxx...'
python3 scripts/qiniu_usage.py --today --cost
```

## Cache File

The cache file `~/.cache/qiniu_prices.json` stores:
- Last update timestamp
- Source URL
- Current exchange rate
- All model prices

To refresh all data:
```bash
python3 scripts/qiniu_usage.py --update-prices
```
