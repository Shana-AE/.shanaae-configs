#!/usr/bin/env node
// Shana-AE repair tool: regenerate the correct opencode token buckets in a
// TokenTracker queue.jsonl.
//
// Use this after applying patch-rollout.mjs if the queue ever contains stale
// or non-monotonic opencode buckets (e.g. from pre-fix parsing or interrupted
// re-parses). It parses opencode (storage files + SQLite db) for BOTH the
// native Windows install and the WSL install using the app's own parser
// functions, and APPENDS the correct cumulative buckets to the queue. The
// dashboard's last-wins dedup (per source|model|hour) makes the appended rows
// authoritative over any stale ones.
//
// Usage:
//   node rebuild-opencode-queue.mjs [path-to-tokentracker-app] [queue-path]
//   (defaults: ~/.tokentracker/tracker/app, ~/.tokentracker/tracker/queue.jsonl)

import { createRequire } from "node:module";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

function resolveAppPath(argv) {
  if (argv[0]) return resolve(argv[0]);
  return join(homedir(), ".tokentracker", "tracker", "app");
}
function resolveQueuePath(argv) {
  if (argv[1]) return resolve(argv[1]);
  return join(homedir(), ".tokentracker", "tracker", "queue.jsonl");
}

async function main() {
  const argv = process.argv.slice(2);
  const appPath = resolveAppPath(argv);
  const queuePath = resolveQueuePath(argv);
  const rolloutPath = join(appPath, "src", "lib", "rollout.js");
  const { existsSync } = await import("node:fs");

  if (!existsSync(rolloutPath)) {
    console.error(`[rebuild] rollout.js not found under ${appPath}`);
    process.exit(1);
  }
  if (!/function diffOpencodeTotals/.test(await (await import("node:fs/promises")).readFile(rolloutPath, "utf8"))) {
    console.error("[rebuild] rollout.js is NOT patched with diffOpencodeTotals — run patch-rollout.mjs first.");
    process.exit(1);
  }

  const r = require(rolloutPath);
  const fs = await import("node:fs");

  // Resolve installs: native is always the app's home-derived path; WSL via
  // discoverWslHome (only meaningful on Windows; elsewhere wsl probe returns null).
  const os = await import("node:os");
  const path = await import("node:path");
  const nativeRoot =
    process.env.OPENCODE_HOME || path.join(os.homedir(), ".local", "share", "opencode");
  const wsl = require(join(appPath, "src", "lib", "wsl-probe.js"));
  let wslRoot = null;
  if (process.platform === "win32" && wsl.getWslMode(process.env) !== "native-only") {
    wslRoot = wsl.discoverWslHome(".local/share/opencode");
  }

  const installs = [];
  if (fs.existsSync(join(nativeRoot, "opencode.db"))) installs.push({ key: "native", root: nativeRoot });
  if (wslRoot && fs.existsSync(wslRoot + "\\opencode.db")) installs.push({ key: "wsl", root: wslRoot });
  if (installs.length === 0) {
    console.error("[rebuild] no opencode.db found under native or WSL roots");
    process.exit(1);
  }

  const cursors = { opencode: {} };
  let totalEvents = 0;
  let totalBuckets = 0;
  for (const { key, root } of installs) {
    cursors.opencode = {};
    const storagePath = path.join(root, "storage");
    try {
      const files = await r.listOpencodeMessageFiles(storagePath);
      if (files.length > 0) {
        const res = await r.parseOpencodeIncremental({
          messageFiles: files, cursors, queuePath, source: "opencode",
        });
        totalEvents += res.eventsAggregated || 0;
        totalBuckets += res.bucketsQueued || 0;
        console.log(`[${key}] storage: ${files.length} files, +${res.eventsAggregated} events, +${res.bucketsQueued} buckets`);
      }
    } catch (e) {
      console.warn(`[${key}] storage parse skipped: ${e && e.message}`);
    }
    const dbPath = path.join(root, "opencode.db");
    try {
      const msgs = r.readOpencodeDbMessages(dbPath);
      if (msgs.length > 0) {
        const res = await r.parseOpencodeDbIncremental({
          dbMessages: msgs, dbPath, cursors, queuePath, source: "opencode", cursorKey: "opencode",
        });
        totalEvents += res.eventsAggregated || 0;
        totalBuckets += res.bucketsQueued || 0;
        console.log(`[${key}] db: ${msgs.length} msgs, +${res.eventsAggregated} events, +${res.bucketsQueued} buckets`);
      }
    } catch (e) {
      console.warn(`[${key}] db parse skipped: ${e && e.message}`);
    }
  }
  console.log(`[rebuild] DONE: +${totalEvents} events, +${totalBuckets} buckets appended to ${queuePath}`);
}

main().catch((e) => { console.error("ERR:", e && e.stack || e); process.exit(1); });