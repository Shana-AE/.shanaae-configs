---
name: qiniu-usage
description: Query Qiniu AI API (api.qnaigc.com) token usage and estimated billing. Use when the user asks about API consumption (用量), token stats, costs (费用), or billing data for Qiniu AI models.
---

# Qiniu AI Usage Manager

This skill queries token usage data and estimated billing from the Qiniu AI API (`api.qnaigc.com`).

## Features

- **Token Usage Query**: Query usage by model, day, or time range
- **Billing Query**: Query estimated billing for today, this week, or this month (CNY)

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

#### Query today's usage
```bash
python3 scripts/qiniu_usage.py --today
```

#### Query last 7 days (default)
```bash
python3 scripts/qiniu_usage.py
```

#### Query current month
```bash
python3 scripts/qiniu_usage.py --month
```

#### Query specific date range
```bash
python3 scripts/qiniu_usage.py --start 2026-02-01 --end 2026-02-25
```

#### Hour-level granularity (max 7 days)
```bash
python3 scripts/qiniu_usage.py --granularity hour --days 3
```

#### Query estimated billing for this month
```bash
python3 scripts/qiniu_usage.py --bill
```

#### Query estimated billing for today
```bash
python3 scripts/qiniu_usage.py --bill --bill-type day
```

#### Query estimated billing for this week
```bash
python3 scripts/qiniu_usage.py --bill --bill-type week
```

#### Output raw JSON
```bash
python3 scripts/qiniu_usage.py --today --json
python3 scripts/qiniu_usage.py --bill --json
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
| `--bill` | Query estimated billing | — |
| `--bill-type` | Billing period: `day`, `week`, `month` | `month` |
| `--api-key` | Override API key | env variable |

## Time Range Limits (API constraint)

- `--granularity day`: max **31 days**
- `--granularity hour`: max **7 days**

## Output Format

### Token Usage

```
  ═══════════════════════════════════════════════════════════════
  Qiniu AI Token Usage Report
  ═══════════════════════════════════════════════════════════════
  Period      : 2026-02-26 ~ 2026-02-26
  Granularity : day

  Model                   Input          Output           Total
  ───────────────────  ────────────── ────────────── ──────────────
  claude-4.6-sonnet      498.9 kToken    2.2 kToken   501.1 kToken
  TOTAL                  554.4 kToken    2.3 kToken   556.7 kToken
```

### Billing

```
  ═══════════════════════════════════════════════════════════════
  Qiniu AI Estimated Billing Report
  ═══════════════════════════════════════════════════════════════
  Period      : This Month
  Note        : Estimated prices at original rate (CNY)

  Model                      Tokens       Fee (CNY)
  ──────────────────────  ──────────────  ──────────────
  claude-4.6-sonnet          9.40 MToken        ¥206.70
  TOTAL                      9.40 MToken        ¥206.70
```

## Workflow for the Agent

When the user asks about Qiniu usage or billing:

1. **Determine query type**:
   - "用了多少 token" / "用量" → token usage query
   - "花了多少钱" / "费用" / "账单" / "多少钱" / "人民币" → billing query (`--bill`)

2. **Determine the time range** from user's request:
   - "今天用了多少" / "今天花了多少钱" → `--today` / `--bill --bill-type day`
   - "这个月" → `--month` / `--bill` (default is month)
   - "本周" → `--bill --bill-type week`
   - "最近7天" → `--days 7`
   - Specific range → `--start YYYY-MM-DD --end YYYY-MM-DD`

3. **Run the script**:
   ```bash
   # Token usage
   python3 scripts/qiniu_usage.py --today

   # Billing
   python3 scripts/qiniu_usage.py --bill --bill-type day
   ```

4. **Interpret and present** the output to the user in a readable summary.

## API Key

The default key is `$QINIU_AI_API_KEY`. The key is associated with account on `portal.qiniu.com`. Data returned is scoped to this API key's usage only.

To use a different key:
```bash
export QINIU_AI_API_KEY='sk-xxx...'
python3 scripts/qiniu_usage.py --bill
```

## Billing API Details

- **Endpoint**: `GET /v2/stat/usage/apikey/cost?type=day|week|month`
- **Auth**: `Authorization: Bearer <APIKey>`
- **Returns**: Per-model token count and fee in CNY (original rate, estimated)
