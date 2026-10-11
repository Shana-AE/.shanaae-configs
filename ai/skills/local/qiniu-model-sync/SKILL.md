---
name: qiniu-model-sync
description: "Sync and query Qiniu (Modelink) AI model catalog. Fetches the authoritative model list from api.modelink.ai/v1/models (successor to openai.sufy.com, same key, identical data), enriched with metadata (display names, context limits) from models.dev. Compare against opencode.jsonc / claude-code-router / ~/.hermes/config.yaml configs to find new or removed models. Probe individual model IDs for callability. Use when checking available Qiniu models, updating model lists, or querying by model family (claude, gpt, deepseek, glm, kimi, gemini, grok, qwen)."
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
> k2.7-code, minimax-m3, qwen3.6-plus/27b, doubao-seed-2-1, deepseek-v4.1-flash, glm-5.3-flash). Verification: after a
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

# Compare Hermes custom Qiniu provider (honors HERMES_HOME)
python3 scripts/qiniu_model_sync.py diff --target hermes

# List models by family
python3 scripts/qiniu_model_sync.py list --family claude
python3 scripts/qiniu_model_sync.py list --family gpt

# Show the latest model per family
python3 scripts/qiniu_model_sync.py latest

# Preview additions and outdated-model removals
python3 scripts/qiniu_model_sync.py update --target all --dry-run

# Apply to portable OpenCode, Mac Studio OpenCode V2, router, and regenerate dsh
python3 scripts/qiniu_model_sync.py update --target all --apply
```

## Configs it can diff against

| Target | File | What it reads |
|--------|------|---------------|
| `opencode` | `.config/opencode/opencode.jsonc` → `provider.qiniu.models` keys | All model IDs defined |
| `router` | `.claude-code-router/config.json` → `Providers[qiniu].models` | All model IDs in the list |
| `hermes` | `${HERMES_HOME:-~/.hermes}/config.yaml` → `custom_providers[name=qiniu].models` | Qiniu model IDs only |

## Model families

Detected by ID prefix/keyword: `claude`, `gpt`/`o3`/`o4`, `deepseek`, `glm`,
`kimi`, `gemini`/`gemma`, `grok`, `qwen`, `doubao`, `minimax`, `kling`/`veo`
(video), and image markers.

## Retention policy / 模型保留规则

`model-policy.json` is the editable source of truth for model retention.
Every `update` refreshes the live Modelink list and applies this policy to both
additions and existing entries; excluded models cannot reappear on the next sync.

- `keep_versions_per_series: 2`: keep the two newest numeric versions within
  each product series (e.g. Claude Opus / Sonnet / Haiku, DeepSeek Pro / Flash,
  GPT Codex / Sol / Luna). Dates and parameter counts are not versions.
- `minimum_versions`: family-wide cutoffs remove old specialized variants too:
  GPT 5.5+, Gemini 3.5+, Grok 4.6+, GLM 5.3+, Kimi 2.7+, Claude 5+,
  DeepSeek 4+, and MiniMax 2.7+. Numeric versions are compared as tuples.
- `exclude`: case-insensitive regex rules retire known obsolete generations,
  including **all DeepSeek V1–V3 and R1**. Applied regardless of API availability.
- `pin`: exact model IDs that must be retained, overriding age rules. A pin does
  not add a model that is absent from both the live catalog and the config.
- `route_replacements`: explicit replacements for removed active router models.
  Otherwise, the newest retained model in the same product series is selected.
  An unresolved active selection aborts before any config is written.
- Unknown model series and manually configured unlisted models are preserved
  unless an explicit exclusion or a recognized version window retires them.
- An empty live catalog aborts the update. Dry run is the default; `--apply`
  writes the changes. This command does not install a background schedule.

`--target opencode` updates the portable config and the Mac Studio V2 config
when present. `--target all` also updates the router and Hermes when its config exists
(the default target). `--target hermes` requires PyYAML; use the Hermes Python
environment if your system Python does not include it. Hermes edits preserve
other providers, credentials, comments, and its non-Qiniu default model.
`--config PATH` overrides the path for a single target. Existing retained-model
settings are preserved; new entries use the target's V1/V2 schema. Applying an
update to the portable OpenCode config automatically regenerates the dsh catalog
through `config-sync`, including live `DSH_HOME/profiles/*/cordis.patch.yml`
Qiniu model lists. Updating legacy `settings.yaml` alone does not update the
current desktop profile. After updates, inspect `opencode models --standalone` on OpenCode V2;
OpenCode V1 supports `opencode models qiniu --verbose`.

## dsh Fetch available / 桌面模型发现

Install `.dsh/plugins/qiniu-model-discovery` as the local
`dsh-qiniu-model-discovery` bundle through `dsh plugin --profile desktop add`,
then run `config-sync` to migrate the old direct mount and credential reference.
The plugin appears in **Plugins → Installed → Qiniu Model Discovery**; model
synchronization respects its enable/disable and removal choices. The desktop **Fetch available** button obtains the Modelink live
catalog, then applies this same retention policy. Runtime requests keep the
configured Qnaigc endpoint. The adapter bypasses pi-ai's bundled Qiniu catalog
with an anonymous discovery draft and resolves the profile's `apiKeyEnv` through
the host credentials service. Draft API keys take precedence. Keys stay out of
the Python policy subprocess and logs. Network failures alone fall back to Sufy.

`python3 scripts/qiniu_model_sync.py filter` reads discovery metadata as JSON
from stdin and emits filtered JSON without fetching or writing configuration.
Known canonical metadata fills missing fields; upstream fields take precedence.
Restart dsh after initial installation if its runtime has not loaded the plugin.
Check the adapter after dsh upgrades: it wraps the public `discoverModels` method
because this build lacks a separate discovery endpoint setting.
