#!/usr/bin/env node
// Shana-AE fix for TokenTracker opencode token accounting.
//
// OpenCode stores PER-MESSAGE (per-call) token counts in message.data.tokens:
//   tokens = { input, output, reasoning, cache: { read, write } }
// where `input` is the non-cached input of that single call and `cache.read`
// is that call's cached-prompt prefix (grows inside a session, resets on
// context clears). The bundled parser treats these as CUMULATIVE running
// totals (like Gemini transcripts) and subtracts the previous message
// (diffGeminiTotals) — corrupting the numbers (multi-billion overcount, and
// cache-read undercount) vs provider billing.
//
// This patch makes the opencode paths use diffOpencodeTotals(), which emits
// each message's own totals exactly once (the messageIndex cursor already
// dedupes re-parses). Idempotent: safe to re-run after every
// `tokentracker init` / upgrade, since those recreate the app dir.
//
// Usage:
//   node patch-rollout.mjs [path-to-tokentracker-app]
//   (default: ~/.tokentracker/tracker/app — also works from WSL with the
//    /mnt/c/... path passed explicitly)

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function resolveTarget(argv) {
  if (argv[0]) {
    const explicit = resolve(argv[0]);
    if (explicit.endsWith("rollout.js")) return explicit;
    return join(explicit, "src", "lib", "rollout.js");
  }
  return join(homedir(), ".tokentracker", "tracker", "app", "src", "lib", "rollout.js");
}

const FN = `// OpenCode stores per-message (per-call) token counts in message.data.tokens,
// NOT cumulative running totals like Gemini's session transcripts do. Each
// message's \`input\` is the non-cached input for that single API call and
// \`cache.read\` is that call's cached-prompt prefix (it grows inside a session
// then resets on context clears). diffGeminiTotals() subtracts the previous
// message's totals, which corrupts these numbers (undercounting input and
// cache, and occasionally emitting full bursts on resets). For OpenCode the
// correct accounting is: emit the message's own totals exactly once. The
// messageIndex cursor already dedupes re-parses via sameGeminiTotals().
// Shana-AE patch: fixes multi-billion-token overcount vs provider billing.
function diffOpencodeTotals(current, previous) {
  if (!current || typeof current !== "object") return null;
  if (!previous || typeof previous !== "object") return current;
  if (sameGeminiTotals(current, previous)) return null;
  return current;
}

`;

function main() {
  const target = resolveTarget(process.argv.slice(2));
  if (!existsSync(target)) {
    console.error(`[rollout] not found: ${target}`);
    process.exit(1);
  }
  let src = readFileSync(target, "utf8");

  if (src.includes("function diffOpencodeTotals")) {
    console.log(`[rollout] already patched: ${target}`);
    return;
  }

  // 1. Insert diffOpencodeTotals right after diffGeminiTotals.
  const anchor = "return isAllZeroUsage(delta) ? null : delta;\n}\n";
  const idx = src.indexOf(anchor);
  if (idx === -1) {
    console.error("[rollout] could not locate diffGeminiTotals() end; aborting");
    process.exit(1);
  }
  src = src.slice(0, idx + anchor.length) + FN + src.slice(idx + anchor.length);

  // 2. Swap the two opencode call sites (this exact arg-shape only occurs in
  //    the opencode file + db parsers; gemini uses totals/projectTotals).
  const before = String(src.split("diffGeminiTotals(currentTotals, lastTotals)").length - 1);
  src = src.split("diffGeminiTotals(currentTotals, lastTotals)").join("diffOpencodeTotals(currentTotals, lastTotals)");

  writeFileSync(target, src, "utf8");
  console.log(`[rollout] patched ${target} (swapped ${before} call site(s) + inserted diffOpencodeTotals)`);
}

main();