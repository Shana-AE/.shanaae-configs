#!/usr/bin/env node
// Seed a TokenTracker cursor state with the fork-deduped rebuild output.
//
// Merges into the LIVE cursor state (preserving codex/hermes/etc.):
//   - hourly.buckets: every "opencode|..." bucket replaced with the deduped
//     totals from hourlyBuckets.json; ghost buckets zeroed
//   - opencode.messages: replaced with the complete per-message index from
//     messageIndex.json (so future scans compute delta=0 for existing messages)
//
// Targets:
//   PC  (0.96.x): cursor-store-v2/generations/<current>/core.json
//   mac (0.87.x): ~/.tokentracker/tracker/cursors.json
//
// Usage: node seed-cursor-state.mjs <core-or-cursors.json> <dump-dir> [--apply]

import { readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { resolve } from "node:path";

const args = process.argv.slice(2);
const apply = args.includes("--apply");
const pos = args.filter((a) => !a.startsWith("--"));
const statePath = resolve(pos[0]);
const dumpDir = resolve(pos[1]);

const msgDump = JSON.parse(readFileSync(resolve(dumpDir, "messageIndex.json"), "utf8"));
const bucketDump = JSON.parse(readFileSync(resolve(dumpDir, "hourlyBuckets.json"), "utf8"));

const state = JSON.parse(readFileSync(statePath, "utf8"));
const now = new Date().toISOString();

// --- hourly buckets ---------------------------------------------------------
const hourly = state.hourly || (state.hourly = { buckets: {}, updatedAt: null });
const buckets = hourly.buckets || (hourly.buckets = {});
let replaced = 0, zeroed = 0, added = 0;
const ZERO = {
  input_tokens: 0, cached_input_tokens: 0, cache_creation_input_tokens: 0,
  output_tokens: 0, reasoning_output_tokens: 0, total_tokens: 0,
  conversation_count: 0,
};
// 1. replace/insert all deduped buckets
for (const [key, b] of Object.entries(bucketDump.buckets)) {
  if (buckets[key]) replaced++;
  else added++;
  buckets[key] = { totals: { ...b.totals }, queuedKey: b.queuedKey ?? null };
}
// 2. zero the ghost buckets: opencode buckets in state but absent from dump
for (const [key, bucket] of Object.entries(buckets)) {
  if (!key.startsWith("opencode|")) continue;
  if (!bucketDump.buckets[key]) {
    const t = bucket.totals || {};
    const nonZero = Object.values(t).some((v) => Number(v) > 0);
    if (nonZero) {
      bucket.totals = { ...ZERO };
      zeroed++;
    }
  }
}
hourly.updatedAt = now;

// --- opencode messageIndex --------------------------------------------------
const oc = state.opencode || (state.opencode = {});
const prevCount = Object.keys(oc.messages || {}).length;
oc.messages = { ...msgDump.messages };
oc.updatedAt = now;
// PC 0.96.x has a dbCursor — advance past all current rows so the app does not
// re-read old rows (the complete messageIndex already covers them).
if (oc.dbCursor && typeof oc.dbCursor === "object" && msgDump.dbCursor) {
  oc.dbCursor = msgDump.dbCursor;
}

console.log(`hourly: ${replaced} replaced, ${added} added, ${zeroed} ghosts zeroed`);
console.log(`opencode.messages: ${prevCount} -> ${Object.keys(oc.messages).length}`);

if (apply) {
  copyFileSync(statePath, statePath + ".pre-seed.bak");
  writeFileSync(statePath, JSON.stringify(state));
  console.log("WROTE", statePath, "(backup at .pre-seed.bak)");
} else {
  console.log("(dry run — pass --apply to write)");
}
