---
name: tavily-search
description: >-
  Search the web using Tavily's AI-optimized search API. Best for research tasks,
  multi-source questions, and getting AI-summarized answers with citations. Use when
  SearXNG results aren't sufficient, or when the user wants research-quality output.
  Free tier: 1000 credits/month. API key loaded from ~/.shanaae/configs/.secrets
  (TAVILY_API_KEY). If Tavily fails or quota exceeded, fall back to searxng-search.
---

# Tavily Search (Cloud API)

AI-optimized web search designed for LLMs and agents. Returns ranked results with
optional AI-generated answer summaries. Free tier: 1000 credits/month.

## Load API Key

```bash
source ~/.shanaae/configs/.secrets
# Key is now available as $TAVILY_API_KEY
```

## Basic Search

```bash
curl -s -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"QUERY\",\"max_results\":5}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"- {r['title'][:70]}\n  {r['url']}\") for r in d.get('results',[])[:5]]"
```

## Search with AI Answer Summary

```bash
curl -s -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"What is Firecrawl?\",\"max_results\":3,\"include_answer\":true}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Answer:',d.get('answer','')); [print(f\"- {r['title'][:60]}\") for r in d.get('results',[])[:3]]"
```

## Search Options

| Parameter         | Values                       | Effect                               |
| ----------------- | ---------------------------- | ------------------------------------ |
| `search_depth`    | `"basic"` / `"advanced"`     | Advanced = more thorough, slower      |
| `include_answer`  | `true` / `false`             | AI-generated summary with citations   |
| `include_images`  | `true` / `false`             | Include image results                |
| `include_domains` | `["example.com"]`            | Restrict to specific domains         |
| `exclude_domains` | `["spam.com"]`               | Exclude specific domains             |
| `time_range`      | `"month"` / `"year"`         | Recency filter                        |

Full example:

```bash
curl -s -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"rust async programming\",\"max_results\":5,\"search_depth\":\"advanced\",\"include_answer\":true}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Answer:',d.get('answer','N/A')[:200]); print(); [print(f\"- [{r.get('score',0):.2f}] {r['title'][:60]}\") for r in d.get('results',[])[:5]]"
```

## Extract — Clean Content from URLs

```bash
curl -s -X POST https://api.tavily.com/extract \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"urls\":[\"https://example.com\"]}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(r.get('raw_content','')[:300]) for r in d.get('results',[])]"
```

## Result Fields

| Field      | Description                            |
| ---------- | -------------------------------------- |
| `title`    | Page title                              |
| `url`      | Direct URL                              |
| `content`  | Snippet/abstract                        |
| `score`    | Relevance score (0-1, higher = better)  |
| `answer`   | AI summary (if `include_answer: true`)  |
| `raw_content` | Full page content (extract endpoint) |

## Error Handling

| HTTP Status | Cause                    | Fix                                  |
| ----------- | ------------------------ | ------------------------------------ |
| 200         | OK                       | —                                    |
| 400         | Bad request              | Check JSON syntax and parameters     |
| 401         | Invalid API key          | Verify `$TAVILY_API_KEY` in .secrets |
| 429         | Rate limit / quota       | Fall back to searxng-search skill     |
| 500         | Server error             | Retry, or use searxng-search          |

## Routing Guidance

- **Simple lookups** ("what is X", "find docs for Y") → use `searxng-search` (free)
- **Research questions** ("compare X and Y", "analyze trends in Z") → use Tavily
- **If Tavily quota exceeded** (429) → fall back to `searxng-search`
- **If you need extracted page content** → use Tavily `/extract` or `firecrawl` skill

## Free Tier Limits

- 1,000 search requests per month (free tier)
- Each `search_depth: "advanced"` may cost more credits
- Monitor usage at https://app.tavily.com
