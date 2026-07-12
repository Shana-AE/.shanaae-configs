---
name: qiniu-model-sync
description: "Sync and query Qiniu (Sufy) AI model catalog. Fetches the authoritative model list from openai.sufy.com/v1/models, enriched with metadata (display names, context limits) from models.dev. Compare against opencode.jsonc / claude-code-router configs to find new or removed models. Probe individual model IDs for callability. Use when checking available Qiniu models, updating model lists, or querying by model family (claude, gpt, deepseek, glm, kimi, gemini, grok, qwen)."
---

# qiniu-model-sync

Keeps Qiniu (Sufy) AI model lists in sync across configs and lets you query the
catalog by family.

## Sources — clear separation of concerns

| Source | URL | Role |
|--------|-----|------|
| **Sufy (sole authority)** | `https://openai.sufy.com/v1/models` | **Determines model existence.** If it's not here, it's not in the catalog. |
| **models.dev (metadata only)** | `https://models.dev/api.json` | Enriches existing Sufy models with display names, context/output limits, reasoning/attachment flags. **Never adds new model IDs** — its Qiniu data is months stale. |

> **Why not use models.dev for discovery?** Its Qiniu catalog lags by 3-6 months.
> Testing showed 5/6 of its "gap-filling" entries were removed/unavailable
> (`claude-3.5-sonnet` → "no available channels", `deepseek-math-v2` → "not
> supported", etc.). Using it for existence introduces false positives.

> **Callable but unlisted models:** Some models work via Qiniu's API but don't
> appear in `/v1/models` (e.g. `openai/gpt-5.6-terra`). Use `probe` to test
> individual model IDs, then add them manually to your config.

## Usage

```bash
# Fetch + cache the catalog (Sufy live + models.dev metadata)
python3 scripts/qiniu_model_sync.py fetch

# Probe a model ID for callability (use for unlisted models like gpt-5.6-terra)
python3 scripts/qiniu_model_sync.py probe openai/gpt-5.6-terra

# Show new models in Sufy not yet in opencode.jsonc
python3 scripts/qiniu_model_sync.py diff --target opencode

# Show new models not yet in claude-code-router config
python3 scripts/qiniu_model_sync.py diff --target router

# List models by family
python3 scripts/qiniu_model_sync.py list --family claude
python3 scripts/qiniu_model_sync.py list --family gpt

# Show the latest model per family
python3 scripts/qiniu_model_sync.py latest

# Propose opencode.jsonc additions (dry-run; copy-paste the JSONC entries)
python3 scripts/qiniu_model_sync.py update --target opencode --dry-run
```

## Configs it can diff against

| Target | File | What it reads |
|--------|------|---------------|
| `opencode` | `.config/opencode/opencode.jsonc` → `provider.qiniu.models` keys | All model IDs defined |
| `router` | `.claude-code-router/config.json` → `Providers[qiniu].models` | All model IDs in the list |

## Model families

Detected by ID prefix/keyword: `claude`, `gpt`/`o3`/`o4`, `deepseek`, `glm`,
`kimi`, `gemini`/`gemma`, `grok`, `qwen`, `doubao`, `minimax`, `kling`/`veo`
(video), and image markers.
