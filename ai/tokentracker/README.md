# TokenTracker (Shana-AE) setup

Local-first token tracker (`tokentracker-cli`) with WSL tracking + custom-provider
(Qiniu/Sufy) pricing. Files here are synced across devices via `.shanaae-configs`.

## What's here

| File | Purpose |
|------|---------|
| `pricing.json`        | USD/M model prices for custom Qiniu models (edited rarely; see notes) |
| `patch-pricing.mjs`   | Idempotently merges `pricing.json` into the app's `curated-overrides.json` |
| `ensure-pricing-patched.sh` | **Auto-re-apply** (Windows/WSL): patches both copies + restarts the desktop app when an upgrade wipes pricing |
| `ensure-pricing-patched-mac.sh` | **Auto-re-apply** (macOS): same, with `open -g` relaunch (no focus steal) |
| `patch-rollout.mjs`   | **RETIRED** — see "Why the opencode token fix was RETIRED" below |
| `revert-rollout-patch.mjs` | Removes the retired `diffOpencodeTotals` patch from a `rollout.js` |
| `rebuild-opencode-forkdedup.mjs` | Repair tool: rebuilds opencode buckets de-duplicating fork-copied messages |
| `rebuild-opencode-queue.mjs` | Legacy repair tool (requires the retired patch; kept for reference) |

## Auto-re-apply (pricing patch survives upgrades)

Desktop app upgrades replace the whole install dir, wiping `curated-overrides.json`
in the **embedded copy**; every `serve` start re-copies embedded → CLI app dir.
`pricing/index.js` `require()`s the file at module load, so it must be patched
before the server starts (or the app restarted after).

- **Windows**: Task Scheduler job `TokenTrackerPricingAutoPatch` (logon + every
  10 min) runs a hidden VBS launcher
  (`C:\Users\<user>\.tokentracker\run-pricing-autofix.vbs`, `wscript.exe` — no
  console window) → `wsl.exe` → `ensure-pricing-patched.sh`.
- **macOS**: launchd agent `com.shanaae.tokentracker-pricing-autofix`
  (`~/Library/LaunchAgents/`, `StartInterval` 600 + `RunAtLoad`) → the mac script.
- Both scripts detect the embedded-copy wipe via `grep shanaae`; if unpatched,
  re-run `patch-pricing.mjs` on embedded + CLI, then restart the desktop app so
  the server reloads pricing. Idempotent + cheap; no restart in steady state.
- The VBS is machine-local (Windows-only); the bash scripts live here (synced).

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
done
```

Notes:
- The **desktop app** (TokenTrackerWin) runs its own **embedded copy** at
  `AppData\Local\Programs\TokenTracker\EmbeddedServer\tokentracker\` and can
  re-deploy it over the CLI app dir on start, so patch **both**.
- `patch-rollout.mjs` is **retired** — do NOT re-apply it. If a machine's
  `rollout.js` still contains `diffOpencodeTotals`, run
  `node revert-rollout-patch.mjs "$d"` to restore pristine upstream.
- After patching, restart the desktop app so its embedded server reloads the code
  (pricing also loads once at startup).

## Fork-session duplication (the real inflation cause)

opencode's `Session.fork` copies every parent message up to the fork point into a
new session — preserving `time_created` and the per-message token payloads but
assigning **new message IDs**. TokenTracker keys on `sessionID|messageID`, so the
entire copied prefix is counted twice (parent + fork). Symptom: a machine's daily
usage spikes to >1B while its baseline is tens of millions, and the cloud total =
sum of parent + fork copies.

**Fix** (`rebuild-opencode-forkdedup.mjs`): rebuild the opencode buckets de-duplicating
by `(time_created, content-hash)`, keeping the first occurrence (the parent, which
holds the authoritative post-update tokens) and keeping the fork's genuine
continuation messages. Then compact + reset the upload offset + drain:

```bash
# On each machine, for each opencode.db (native + WSL):
node rebuild-opencode-forkdedup.mjs "$APP" "$QUEUE" "$DB" ["$DB2"...]
# compact (keep last row per source|model|hour):
python3 - <<'PY'
import json
p = "$QUEUE"
best = {}
for line in open(p):
    r = json.loads(line)
    best[(r["source"], r["model"], r.get("hour_start"))] = r
open(p, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in best.values()))
PY
# reset upload offset so the cloud re-ingests (idempotent upsert by key):
echo '{"offset":0,"updatedAt":"'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'","note":"fork-dedup-repair"}' > "$(dirname "$QUEUE")/queue.state.json"
# drain to cloud (Windows box: run node from the Windows side so it reads the
# Windows queue; or trigger the desktop app's Sync Now):
node "$APP/bin/tracker.js" sync --drain
```

## Why the opencode token fix was RETIRED

> **Status (2026-08-07): `patch-rollout.mjs` is RETIRED.** The maintainer's
> analysis of [issue #426](https://github.com/xiufengsun/TokenTracker/issues/426)
> is correct: the parser is **not** broken. `lastTotals` is looked up by
> `sessionID|messageID` (the same message's previous snapshot), so a first-seen
> message already emits its full per-message usage; the reported 4.4× was a
> **raw `queue.jsonl` line summation** (append-only replacement snapshots — invalid),
> not a parser bug. `diffOpencodeTotals` also **breaks in-place message updates**
> (5→8 tokens emits 13). The patch has been reverted on all installs; the parser
> runs pristine upstream `diffGeminiTotals`.

The real inflation turned out to be **opencode fork sessions** (see
`rebuild-opencode-forkdedup.mjs` below), not the parser.

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