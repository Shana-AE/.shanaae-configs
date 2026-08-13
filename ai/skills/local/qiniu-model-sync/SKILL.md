---
name: qiniu-model-sync
description: "Sync and query Qiniu (Modelink) AI model catalog. Fetches the authoritative model list from api.modelink.ai/v1/models (successor to openai.sufy.com, same key, identical data), enriched with metadata (display names, context limits) from models.dev. Compare against opencode.jsonc / claude-code-router configs to find new or removed models. Probe individual model IDs for callability. Use when checking available Qiniu models, updating model lists, or querying by model family (claude, gpt, deepseek, glm, kimi, gemini, grok, qwen)."
---

# qiniu-model-sync

Keeps Qiniu (Modelink) AI model lists in sync across configs and lets you query
the catalog by family.

## Sources — clear separation of concerns

| Source | URL | Role |
|--------|-----|------|
| **Modelink (sole authority)** | `https://api.modelink.ai/v1/models` | **Determines model existence.** If it's not here, it's not in the catalog. Successor to `openai.sufy.com` (migrated 2026-08; both served identical 134-model lists at migration time). The script falls back to the still-live `https://openai.sufy.com/v1/models` alias on network errors. |
| **models.dev (metadata only)** | `https://models.dev/api.json` | Enriches existing catalog models with display names, context/output limits, reasoning/attachment flags, **and modalities** (image/video/audio input). **Never adds new model IDs** — its Qiniu data is months stale. |

> **CN endpoint is a subset — never the catalog source.** `https://api.qnaigc.com`
> and `https://openai.qiniu.com` (identical lists) serve the China-mainland
> gateway and list only ~73 models vs 134 on Modelink. They are fine as runtime
> base URLs but MUST NOT be used as the model-list authority — you'd miss ~60
> models.

> **Modalities = native vision.** OpenCode only sends image bytes to a model when
> the config declares `"modalities": {"input": [... "image" ...]}` (i.e. resolved
> capability `input.image=true`). `"attachment": true` alone is NOT enough — the
> model receives the file path but never the pixels. The merged catalog carries
> modalities so `update --target opencode` emits them. New multimodal models that
> models.dev hasn't indexed are covered by a hardcoded override map in
> `merge_catalog()` (e.g. claude-4.6/4.7/4.8, gpt-5, grok-4.2/4.3, kimi-k2.6/
> k2.7-code, minimax-m3, qwen3.6-plus/27b, doubao-seed-2-1). Verification: after a
> config change run `opencode models qiniu --verbose` and confirm
> `"input": {"image": true}` for the affected model.

> **Why not use models.dev for discovery?** Its Qiniu catalog lags by 3-6 months.
> Testing showed 5/6 of its "gap-filling" entries were removed/unavailable
> (`claude-3.5-sonnet` → "no available channels", `deepseek-math-v2` → "not
> supported", etc.). Using it for existence introduces false positives.

> **Callable but unlisted models:** Some models work via Qiniu's API but don't
> appear in `/v1/models` (e.g. `openai/gpt-5.6-terra`). Use `probe` to test
> individual model IDs, then add them manually to your config.

## Usage

```bash
# Fetch + cache the catalog (Modelink live + models.dev metadata)
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
