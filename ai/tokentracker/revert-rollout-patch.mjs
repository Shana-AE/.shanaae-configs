#!/usr/bin/env node
// Shana-AE reverse-patch: remove the (now-known-wrong) diffOpencodeTotals
// patch from a TokenTracker rollout.js, restoring the pristine upstream
// behavior. The patch was based on a wrong reproducer (raw queue.jsonl
// summation); the upstream parser is correct (verified bucket-level).
// The REAL inflation is opencode fork-copy duplication, fixed by
// rebuild-opencode-forkdedup.mjs, not by replacing diffGeminiTotals.
//
// Usage:
//   node revert-rollout-patch.mjs <path-to-rollout.js>

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function resolveTarget(argv) {
  if (argv[0]) {
    const explicit = resolve(argv[0]);
    if (explicit.endsWith("rollout.js")) return explicit;
    if (existsSync(explicit) && !existsSync(join(explicit, "package.json"))) {
      // A file path (e.g. a copied rollout.js) — use as-is.
      return explicit;
    }
    return join(explicit, "src", "lib", "rollout.js");
  }
  return join(process.env.HOME || process.env.USERPROFILE || "", ".tokentracker", "tracker", "app", "src", "lib", "rollout.js");
}

function main() {
  const target = resolveTarget(process.argv.slice(2));
  if (!existsSync(target)) {
    console.error(`[revert] not found: ${target}`);
    process.exit(1);
  }
  const raw = readFileSync(target, "utf8");

  if (!raw.includes("function diffOpencodeTotals")) {
    console.log(`[revert] already pristine (no diffOpencodeTotals): ${target}`);
    return;
  }

  // 1. Remove the inserted diffOpencodeTotals function block (comment + fn).
  const fnStart = raw.indexOf("// OpenCode stores per-message (per-call) token counts in message.data.tokens,");
  if (fnStart === -1) {
    console.error("[revert] could not locate patch comment block; aborting (edit manually)");
    process.exit(1);
  }
  const fnEndMarker = "function diffOpencodeTotals(current, previous) {";
  const fnEnd = raw.indexOf("}", raw.indexOf(fnEndMarker)) + 1;
  if (fnEnd <= fnStart) {
    console.error("[revert] could not locate end of diffOpencodeTotals; aborting");
    process.exit(1);
  }
  let src = raw.slice(0, fnStart) + raw.slice(fnEnd + 1);

  // 2. Swap the two opencode call sites back to diffGeminiTotals.
  const needle = "diffOpencodeTotals(currentTotals, lastTotals)";
  const before = String(src.split(needle).length - 1);
  if (before !== 2) {
    console.warn(`[revert] expected 2 call sites, found ${before}`);
  }
  src = src.split(needle).join("diffGeminiTotals(currentTotals, lastTotals)");

  writeFileSync(target, src, "utf8");
  console.log(`[revert] reverted ${target} (removed patch block, swapped ${before} call site(s) back)`);
}

main();