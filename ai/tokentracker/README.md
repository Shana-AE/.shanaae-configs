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

The opencode plugin is generated per-machine by `tokentracker init` into
`~/.config/opencode/plugin/tokentracker.js` (machine-local, gitignored — not
synced). WSL uses a hand-flipped variant that calls a wrapper script on the
Windows host; see the disabled copies under `.config/opencode/plugin/disabled/`.

## After every `tokentracker init` / upgrade

The app dir (incl. `curated-overrides.json` and `rollout.js`) is recreated from the
npm package, wiping both changes. Re-apply to **both** copies:

```bash
APP=/mnt/c/Users/<user>/.tokentracker/tracker/app     # CLI app dir (Windows side, covers WSL via /mnt/c)
EMBED="/mnt/c/Users/<user>/AppData/Local/Programs/TokenTracker/EmbeddedServer/tokentracker"  # desktop app's embedded copy
for d in "$APP" "$EMBED"; do
  node patch-pricing.mjs "$d"
  node patch-rollout.mjs "$d"
done
```

Notes:
- The **desktop app** (TokenTrackerWin) runs its own **embedded copy** at
  `AppData\Local\Programs\TokenTracker\EmbeddedServer\tokentracker\` and can
  re-deploy it over the CLI app dir on start, so patch **both**.
- `patch-rollout.mjs` is **CRLF-aware** — the Windows copies use `\r\n`.
- After patching, restart the desktop app so its embedded server reloads the code
  (pricing also loads once at startup).

## Why the opencode token fix exists

opencode stores **per-message** token usage in `message.data.tokens`
(`{input, output, reasoning, cache:{read, write}}`). The bundled parser treated
these as cumulative (subtracting the previous message, like Gemini), which
overcounted massively (e.g. 4.4× Qiniu for 7 days). `patch-rollout.mjs` makes the
opencode paths emit each message's own totals exactly once. After the fix,
TokenTracker ≈ 75% of Qiniu's counted usage (the gap is messages opencode doesn't
record tokens for — not a parsing bug).

Upstream issue: https://github.com/xiufengsun/TokenTracker/issues/426

## Cloud data

The desktop app's tokens tab shows **cloud** (InsForge) data when signed in. To
re-ingest the corrected local queue to the cloud:
1. `node .../tracker/app/bin/tracker.js device-login` → approve the code in a browser.
2. `node .../tracker/app/bin/tracker.js sync --drain` → uploads the corrected queue.

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