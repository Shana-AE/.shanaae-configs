---
name: qiniu-model-sync
description: "Sync and query Qiniu (Sufy) AI model catalog. Fetches the live model list from openai.sufy.com/v1/models (primary, authoritative) merged with models.dev/api.json (supplementary — fills gaps for models available but not listed, e.g. gpt-5.6-terra). Compare against opencode.jsonc / claude-code-router configs to find new or removed models. Use when checking available Qiniu models, updating model lists, or querying by model family (claude, gpt, deepseek, glm, kimi, gemini, grok, qwen)."
---

# qiniu-model-sync

Keeps Qiniu (Sufy) AI model lists in sync across configs and lets you query the
catalog by family.

## Sources

| Source | URL | Role |
|--------|-----|------|
| **Sufy (primary)** | `https://openai.sufy.com/v1/models` | Authoritative live list of Qiniu's available models |
| **models.dev (supplementary)** | `https://models.dev/api.json` | Fills gaps — some models work via Qiniu but aren't in the `/v1/models` list (e.g. `openai/gpt-5.6-terra`) |

Both are merged. Sufy takes precedence for existence; models.dev adds metadata
(description, context limits, family).

## Usage

```bash
# Fetch + cache the merged model list (24h TTL on models.dev, always-fresh Sufy)
python3 scripts/qiniu_model_sync.py fetch

# Show new models in Sufy not yet in opencode.jsonc
python3 scripts/qiniu_model_sync.py diff --target opencode

# Show new models not yet in claude-code-router config
python3 scripts/qiniu_model_sync.py diff --target router

# List models by family
python3 scripts/qiniu_model_sync.py list --family claude
python3 scripts/qiniu_model_sync.py list --family gpt
python3 scripts/qiniu_model_sync.py list --family grok

# Show only the latest model per family
python3 scripts/qiniu_model_sync.py latest

# Propose opencode.jsonc additions (dry-run; copy-paste the JSONC entries)
python3 scripts/qiniu_model_sync.py update --target opencode --dry-run
```

## How it works

1. Fetches `openai.sufy.com/v1/models` → list of model IDs (authoritative).
2. Fetches `models.dev/api.json` (cached 24h) → rich metadata + any models the
   Sufy list missed.
3. Merges: Sufy IDs are the base set; models.dev adds (a) any Qiniu models not
   in the Sufy list and (b) metadata (name, description, context/output limits,
   reasoning, attachment flags) for all models.
4. Categorizes: text models, image-gen, video-gen.
5. State file (`~/.cache/qiniu-model-sync-state.json`) tracks `seen` IDs — first
   run is a baseline; subsequent runs report only what's new.

## Configs it can diff against

| Target | File | What it reads |
|--------|------|---------------|
| `opencode` | `.config/opencode/opencode.jsonc` → `provider.qiniu.models` keys | All model IDs defined |
| `router` | `.claude-code-router/config.json` → `Providers[qiniu].models` | All model IDs in the list |

## Model families

Detected by ID prefix/keyword: `claude`, `gpt`/`o3`/`o4`, `deepseek`, `glm`,
`kimi`, `gemini`/`gemma`, `grok`, `qwen`, `doubao`, `minimax`, `kling`/`veo`
(video), and image markers.
