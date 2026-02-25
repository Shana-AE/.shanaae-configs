---
name: qiniu-usage
description: Query Qiniu AI API (api.qnaigc.com) token usage by model, day, or time range. Use when the user asks about API consumption (用量), token stats, how much they've used, or wants to check billing data for Qiniu AI models.
---

# Qiniu AI Usage Manager

This skill queries token usage data from the Qiniu AI API (`api.qnaigc.com`) using the `/v2/stat/usage` endpoint.

## Prerequisites

- **API Key**: Hardcoded default key is embedded in the script. Override via `--api-key` flag or `QINIU_API_KEY` env variable.
- **Python 3**: Script uses only stdlib — no pip install needed.

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

#### Query last N days
```bash
python3 scripts/qiniu_usage.py --days 30
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
| `--api-key` | Override API key | env/hardcoded |

## Time Range Limits (API constraint)

- `--granularity day`: max **31 days**
- `--granularity hour`: max **7 days**

## Output Format

The default output is a formatted table:

```
  Qiniu AI Token Usage Report
  Period : 2026-02-25 ~ 2026-02-25
  Granularity: day

  Model                   Input          Output           Total
  ---------------  ------------  --------------  --------------
  claude-4.6-sonnet   498.9 kToken    2.2 kToken   501.1 kToken
  ...
  TOTAL               554.4 kToken    2.3 kToken   556.7 kToken

  Daily Breakdown (1 active days)
  ...
```

## Workflow for the Agent

When the user asks about Qiniu usage:

1. **Determine the time range** from user's request:
   - "今天用了多少" → `--today`
   - "这个月用了多少" → `--month`
   - "最近7天" → `--days 7`
   - Specific range → `--start YYYY-MM-DD --end YYYY-MM-DD`

2. **Run the script**:
   ```bash
   python3 scripts/qiniu_usage.py --today
   ```

3. **Interpret and present** the output to the user in a readable summary.

## API Key

The default key is $QINIU_AI_API_KEY. The key is associated with account on `portal.qiniu.com`. Data returned is scoped to this API key's usage only.

To use a different key:
```bash
export QINIU_AI_API_KEY='sk-xxx...'
python3 scripts/qiniu_usage.py --today
```
