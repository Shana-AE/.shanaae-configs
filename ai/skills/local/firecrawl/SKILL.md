---
name: firecrawl
description: >-
  Scrape, crawl, map, extract structured data, or interact with web pages using the
  self-hosted Firecrawl instance. Use when the user wants to read a URL into clean
  markdown, crawl an entire site, discover all URLs (map), extract specific fields as
  JSON, or click/navigate dynamic pages. Superior to defuddle for complex scraping —
  handles JS rendering, structured extraction, multi-page crawls. Do NOT use for simple
  article reading (use defuddle instead). Endpoint via $FIRECRAWL_API_URL env var
  (default http://localhost:47813). If Firecrawl is down, fall back to defuddle.
---

# Firecrawl (Self-Hosted)

Self-hosted Firecrawl instance for scraping, crawling, and extracting web content.
Produces clean markdown (strips 94% of HTML noise) and supports structured JSON
extraction, multi-page crawls, and browser interaction.

## Endpoint

```bash
FIRECRAWL_URL="${FIRECRAWL_API_URL:-http://localhost:47813}"
```

No API key needed (self-hosted bypass-auth mode). All examples below use `$FIRECRAWL_URL`.

## Quick Reference

| Endpoint               | Use when...                                          |
| ---------------------- | ---------------------------------------------------- |
| `POST /v2/scrape`        | You know the URL, want clean markdown or structured JSON |
| `POST /v2/search`        | You need to find information across the web            |
| `POST /v2/crawl`         | You want content from multiple pages of a site         |
| `POST /v2/map`           | You want to discover all URLs on a site               |
| `POST /v2/extract`       | You want specific structured fields from page(s)       |
| `POST /v2/interact`      | You need to click, type, or navigate a dynamic page    |

## Scrape — Clean Markdown from One URL

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/scrape" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['markdown'][:500])"
```

### Scrape — Structured JSON (recommended for specific data)

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "url":"https://example.com/product",
    "formats":[{"type":"json","prompt":"Extract product info","schema":{
      "type":"object",
      "properties":{
        "name":{"type":"string"},
        "price":{"type":"number"},
        "description":{"type":"string"}
      },
      "required":["name","price"]
    }}]
  }'
```

## Search — Web Search with Content

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"latest AI news","limit":5}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(r.get('title','')) for r in d.get('data',{}).get('web',d.get('data',[]))[:5]]"
```

## Crawl — Multi-Page Site Extraction

Warning: responses can be large. Always set a limit.

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/crawl" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/blog","limit":20,"maxDiscoveryDepth":2}'
```

Crawl is asynchronous — the response contains a job `id`. Poll for results:

```bash
curl -s "$FIRECRAWL_URL/v1/crawl/JOB_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status'), len(d.get('data',[])), 'pages')"
```

## Map — Discover All URLs on a Site

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/map" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(u) for u in d.get('links',d.get('data',[]))[:20]]"
```

## Extract — Structured Data from Multiple URLs

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "urls":["https://example.com/page1","https://example.com/page2"],
    "prompt":"Extract the product name, price, and description"
  }'
```

## Interact — Click, Type, Navigate Dynamic Pages

```bash
curl -s -X POST "$FIRECRAWL_URL/v2/interact" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","prompt":"Click the pricing link and list the plans"}'
```

## Health Check

Verify Firecrawl is running before using:

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$FIRECRAWL_URL/v1/scrape" \
  -H "Content-Type: application/json" -d '{"url":"https://example.com"}'
# 200 = OK, 000 = down (fall back to defuddle)
```

## Error Handling

| Symptom                          | Cause                    | Fix                             |
| -------------------------------- | ------------------------ | ------------------------------- |
| HTTP 403 + "insecure target URL" | SSRF protection blocked  | Check if URL resolves to public IP |
| HTTP 500                         | Server error             | Retry, or check `docker logs`   |
| Empty markdown                   | JS page didn't render    | Retry, or use /v2/interact      |
| `curl: (7) connection refused`   | Firecrawl not running    | `cd ~/webstack/firecrawl && docker compose up -d` |
| Timeout (>60s)                   | Slow site or deep crawl  | Reduce limit, or use /v2/map first |

## When to Use defuddle Instead

- Simple article/blog reading (no JS, no structured data needed)
- Firecrawl Docker stack is down
- You just need a quick text extract without setup overhead

## Token Efficiency

Firecrawl strips navigation, ads, scripts, and footers — returning ~94% fewer tokens
than raw HTML. Prefer `"onlyMainContent": true` and JSON format with a schema to
minimize context window usage.
