---
name: searxng-search
description: >-
  Search the web using the self-hosted SearXNG metasearch engine. Free, private,
  aggregates 279+ search engines (Google, DuckDuckGo, Bing, etc.). Use for general web
  searches, quick lookups, finding URLs. Returns titles, URLs, and snippets as JSON.
  Prefer this over tavily-search for simple queries (no API key, no rate limits).
  Endpoint via $SEARXNG_INSTANCE_URL env var (default http://localhost:47432).
---

# SearXNG Search (Self-Hosted)

Free, privacy-respecting metasearch engine. Aggregates results from 279+ search
engines. No API key, no rate limits, no tracking.

## Endpoint

```bash
SEARXNG_URL="${SEARXNG_INSTANCE_URL:-http://localhost:47432}"
```

## Basic Search

```bash
curl -s "$SEARXNG_URL/search?q=QUERY&format=json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"- {r['title'][:70]}\n  {r['url']}\") for r in d.get('results',[])[:5]]"
```

## Search Options

Append as URL query parameters:

| Parameter      | Example                          | Effect                          |
| -------------- | -------------------------------- | ------------------------------- |
| `categories`   | `&categories=it,science`         | Limit to specific categories     |
| `engines`      | `&engines=google,duckduckgo`     | Use specific engines only        |
| `time_range`   | `&time_range=month`              | day / week / month / year       |
| `pageno`       | `&pageno=2`                      | Pagination                       |
| `language`     | `&language=en`                   | Result language                  |

Full example with options (remember to URL-encode the query):

```bash
curl -s "$SEARXNG_URL/search?q=rust+programming&format=json&categories=it&time_range=month" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"- [{r.get('engine','?')}] {r['title'][:60]}\") for r in d.get('results',[])[:5]]"
```

## Result Fields

Each result in the `results` array contains:

| Field      | Description                        |
| ---------- | ---------------------------------- |
| `title`    | Page title                          |
| `url`      | Direct URL to result                |
| `content`  | Short snippet/abstract              |
| `engine`   | Which search engine provided this    |
| `score`    | Relevance score (higher = better)    |
| `publishedDate` | Publication date (if available) |

## Health Check

```bash
curl -s -o /dev/null -w "%{http_code}" "$SEARXNG_URL/search?q=test&format=json"
# 200 = OK, 000 = down
```

## Troubleshooting

| Symptom                | Cause                          | Fix                                   |
| ---------------------- | ------------------------------ | ------------------------------------- |
| 0 results              | Upstream engines timed out     | Retry; or increase timeout in settings |
| Empty/HTML response    | Missing `&format=json`         | Always add `format=json`              |
| `connection refused`   | SearXNG not running            | `cd ~/webstack/searxng && docker compose up -d` |
| Slow (>10s)            | Many engines, proxy latency    | Reduce engines: `&engines=google,bing` |

## When to Use Tavily Instead

- Need AI-summarized answers with citations
- Research-quality multi-source synthesis
- SearXNG returning poor results for complex queries

## Environment Setup

On macOS the endpoint is set in `~/.hermes/.env` as `SEARXNG_INSTANCE_URL`.
On other devices, set it in `~/.shanaae/configs/.secrets` or the shell environment.
