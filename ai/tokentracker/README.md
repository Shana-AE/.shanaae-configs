# TokenTracker (Shana-AE) setup

Local-first token tracker (`tokentracker-cli`) with WSL tracking + custom-provider
(Qiniu/Sufy) pricing. Files here are synced across devices via `.shanaae-configs`.

## What's here

| File | Purpose |
|------|---------|
| `pricing.json`        | USD/M model prices for custom Qiniu models (edited rarely; see notes) |
| `patch-pricing.mjs`   | Idempotently merges `pricing.json` into the app's `curated-overrides.json` |
| `patch-rollout.mjs`   | Applies the opencode per-message token-accounting fix to `src/lib/rollout.js` |
| `rebuild-opencode-queue.mjs` | Repair tool: regenerates correct opencode buckets in `queue.jsonl` |

The WSL opencode plugin lives at `.config/opencode/plugin/tokentracker.js` (same repo).

## After every `tokentracker init` / upgrade

The app dir (incl. `curated-overrides.json` and `rollout.js`) is recreated from the
npm package, wiping both changes. Re-apply:

```bash
APP=/mnt/c/Users/<user>/.tokentracker/tracker/app     # Windows side (covers WSL too)
node patch-pricing.mjs "$APP"
node patch-rollout.mjs "$APP"
```

Then restart the dashboard (pricing loads once at startup).

## Why the opencode token fix exists

opencode stores **per-message** token usage in `message.data.tokens`
(`{input, output, reasoning, cache:{read, write}}`). The bundled parser treated
these as cumulative (subtracting the previous message, like Gemini), which
overcounted massively (e.g. 4.4× Qiniu for 7 days). `patch-rollout.mjs` makes the
opencode paths emit each message's own totals exactly once. After the fix,
TokenTracker ≈ 75% of Qiniu's counted usage (the gap is messages opencode doesn't
record tokens for — not a parsing bug).

## Cost display in RMB

Dashboard → Settings → Appearance → Currency → **CNY (¥)** (built-in conversion,
default 7.2, adjustable). Pricing data in `pricing.json` is USD; entries marked
"estimate" should be verified against Qiniu billing.

## Repairing a corrupted queue

If the queue ever has stale/non-monotonic opencode buckets:

```bash
node rebuild-opencode-queue.mjs "$APP" "$QUEUE"
# then compact (keep last row per source|model|hour):
python3 - <<'PY'
import json
p = "/mnt/c/Users/<user>/.tokentracker/tracker/queue.jsonl"
best = {}
for line in open(p):
    r = json.loads(line)
    best[(r["source"], r["model"], r.get("hour_start"))] = r
open(p, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in best.values()))
PY
```