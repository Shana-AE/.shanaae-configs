#!/usr/bin/env node
// Shana-AE repair tool: regenerate correct opencode token buckets in a
// TokenTracker queue.jsonl by de-duplicating opencode FORK sessions.
//
// Root cause: opencode's Session.fork copies every parent message up to the
// fork point into a new session with a NEW message id but PRESERVED
// time_created and token payloads. TokenTracker keys messages on
// sessionID|messageID, so the copied prefix is counted twice (once in the
// parent, once in the fork). This inflates the queue by the sum of all fork
// copies (e.g. ~2.0B tokens across both machines in use).
//
// Fix: build a per-message content signature (time_created + sha256 of the
// sorted part texts) and keep the FIRST occurrence of each signature across
// all sessions (the parent, created earliest). Fork copies collide with the
// parent's signature and are dropped. Genuine fork continuation messages
// (new time_created / content) are kept, so the fork's real new cost
// (context re-send cache.read) is still counted.
//
// The deduped message set is fed to the app's OWN parser
// (parseOpencodeDbIncremental), which appends correct cumulative buckets to
// the queue. The dashboard's last-wins dedup (per source|model|hour) makes
// the appended rows authoritative over stale ones.
//
// Usage:
//   node rebuild-opencode-forkdedup.mjs <app-path> <queue-path> <db-path> [<db-path>...]
//
// After running: compact the queue (keep last row per source|model|hour),
// reset queue.state.json offset to 0, then `tracker.js sync --drain`.

import { createRequire } from "node:module";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

function usage() {
  console.log(
    "Usage: node rebuild-opencode-forkdedup.mjs <app-path> <queue-path> <db-path> [<db-path>...]"
  );
  process.exit(1);
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length < 3) usage();
  const appPath = resolve(argv[0]);
  const queuePath = resolve(argv[1]);
  const dbPaths = argv.slice(2).map((p) => resolve(p));

  const rolloutPath = join(appPath, "src", "lib", "rollout.js");
  const sqliteReaderPath = join(appPath, "src", "lib", "sqlite-reader.js");
  const { existsSync } = await import("node:fs");
  if (!existsSync(rolloutPath) || !existsSync(sqliteReaderPath)) {
    console.error(`[forkdedup] app not found under ${appPath}`);
    process.exit(1);
  }

  const r = require(rolloutPath);
  const { readSqliteJsonRows } = require(sqliteReaderPath);

  // ---------------------------------------------------------------------------
  // 1. Read all assistant messages + their parts from every provided DB.
  // ---------------------------------------------------------------------------
  const MESSAGE_SQL = `SELECT id, session_id, time_created, time_updated, data
    FROM message WHERE json_extract(data, '$.role') = 'assistant'
    ORDER BY time_created ASC`;

  // Fork sessions are named "<title> (fork #N)" by opencode. Prefer the
  // parent (non-fork) copy on a signature collision, because the parent's
  // message may have been updated in place AFTER the fork (growing tokens),
  // so the parent holds the authoritative post-update value.
  const SESSION_SQL = `SELECT id, title FROM session`;
  const forkSessionIds = new Set();
  for (const dbPath of dbPaths) {
    if (!existsSync(dbPath)) continue;
    try {
      const srows = readSqliteJsonRows(dbPath, SESSION_SQL, {
        label: "OpenCode", maxBuffer: 8 * 1024 * 1024, timeout: 30000,
      });
      for (const s of srows) {
        const title = typeof s?.title === "string" ? s.title : "";
        const id = typeof s?.id === "string" ? s.id : "";
        if (id && /\(fork[ #\d]*\)/i.test(title)) forkSessionIds.add(id);
      }
    } catch {
      // best effort
    }
  }
  console.log(`[forkdedup] detected ${forkSessionIds.size} fork session(s) by title`);
  const PART_SQL = `SELECT message_id, session_id, data FROM part ORDER BY message_id ASC`;

  const allMsgs = []; // { id, sessionID, timeUpdated, data, dbIndex }
  const partsByMsg = new Map(); // `dbIndex:msgId` -> [partText,...]

  for (let di = 0; di < dbPaths.length; di++) {
    const dbPath = dbPaths[di];
    if (!existsSync(dbPath)) {
      console.warn(`[forkdedup] db missing, skipping: ${dbPath}`);
      continue;
    }
    const rows = readSqliteJsonRows(dbPath, MESSAGE_SQL, {
      label: "OpenCode",
      maxBuffer: 50 * 1024 * 1024,
      timeout: 30000,
    });
    for (const row of rows) {
      if (!row || typeof row.data !== "string") continue;
      let data;
      try {
        data = JSON.parse(row.data);
      } catch {
        continue;
      }
      const tokens = data?.tokens;
      if (!tokens || typeof tokens !== "object") continue;
      const hasTokens =
        num(tokens.input) > 0 || num(tokens.output) > 0 || num(tokens.reasoning) > 0;
      if (!hasTokens) continue;
      allMsgs.push({
        id: row.id || data.id,
        sessionID: row.session_id || data.sessionID,
        timeUpdated: row.time_updated || 0,
        data,
        dbIndex: di,
      });
    }
    const partRows = readSqliteJsonRows(dbPath, PART_SQL, {
      label: "OpenCode",
      maxBuffer: 50 * 1024 * 1024,
      timeout: 30000,
    });
    for (const pr of partRows) {
      if (!pr || typeof pr.data !== "string") continue;
      let pd;
      try {
        pd = JSON.parse(pr.data);
      } catch {
        continue;
      }
      const text = pd?.text;
      let t = null;
      if (typeof text === "string") t = text;
      else if (Array.isArray(text)) t = JSON.stringify(text);
      if (t == null) continue;
      const key = `${pr.dbIndex ?? di}:${pr.message_id ?? ""}`;
      if (!partsByMsg.has(key)) partsByMsg.set(key, []);
      partsByMsg.get(key).push(t);
    }
  }

  console.log(`[forkdedup] total assistant msgs with tokens: ${allMsgs.length}`);

  // ---------------------------------------------------------------------------
  // 2. Session creation order (parent created before fork).
  // ---------------------------------------------------------------------------
  // We don't have session creation time per message inside data reliably for
  // ordering; use the message's own time as an approximation and rely on the
  // fact that a fork's CONTINUATION messages postdate the copied prefix. For
  // the copied prefix, parent and fork share time_created, so we keep the
  // first one we see in DB order (parent rows appear first in the table).
  // ---------------------------------------------------------------------------

  // ---------------------------------------------------------------------------
  // 3. Compute signature per message; keep first occurrence.
  // ---------------------------------------------------------------------------
  function sigFor(msg) {
    const timeMs =
      num(msg.data?.time?.completed) || num(msg.data?.time?.created) || 0;
    const parts = partsByMsg.get(`${msg.dbIndex}:${msg.id}`) || [];
    const sorted = [...parts].sort();
    const content = sorted.join("\u0000");
    const hash = crypto.createHash("sha256").update(content).digest("hex").slice(0, 32);
    return `${timeMs}|${hash}`;
  }

  const seen = new Map(); // sig -> { msg, order }
  let kept = 0;
  let dropped = 0;
  const keptMsgs = [];
  let order = 0;
  for (const msg of allMsgs) {
    const sig = sigFor(msg);
    const isFork = forkSessionIds.has(msg.sessionID);
    const prior = seen.get(sig);
    if (prior) {
      // Keep the non-fork (parent) copy; if both are forks, keep the first.
      if (isFork && !prior.isFork) {
        // this fork copy is a duplicate; drop it
        dropped += 1;
        continue;
      }
      if (!isFork && prior.isFork) {
        // we stored a fork copy earlier; replace with authoritative parent
        seen.set(sig, { msg, isFork, order: prior.order });
        keptMsgs[prior.order] = msg;
        dropped += 1;
        continue;
      }
      dropped += 1;
      continue;
    }
    seen.set(sig, { msg, isFork, order });
    keptMsgs.push(msg);
    order += 1;
    kept += 1;
  }
  keptMsgs.length = order;
  console.log(`[forkdedup] kept ${kept}, dropped ${dropped} fork-copied messages`);

  // ---------------------------------------------------------------------------
  // 4. Feed deduped messages to the app's own parser -> append correct buckets.
  // ---------------------------------------------------------------------------
  const cursors = {
    opencode: { messages: {} },
    hourly: { buckets: {}, groupQueued: {}, updatedAt: null },
  };

  const res = await r.parseOpencodeDbIncremental({
    dbMessages: keptMsgs,
    dbPath: dbPaths[0],
    cursors,
    queuePath,
    source: "opencode",
    cursorKey: "opencode",
  });

  console.log(
    `[forkdedup] DONE: +${res.eventsAggregated} events, +${res.bucketsQueued} buckets appended to ${queuePath}`
  );
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

main().catch((e) => {
  console.error("ERR:", (e && e.stack) || e);
  process.exit(1);
});