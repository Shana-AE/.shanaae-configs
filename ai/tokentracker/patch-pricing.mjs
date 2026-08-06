#!/usr/bin/env node
// Shana-AE pricing patcher for TokenTracker (tokentracker-cli).
//
// Merges the curated additions in pricing.json (same schema as the tokentracker
// curated-overrides.json) into the installed app's curated-overrides.json, so
// custom Qiniu/Sufy models get USD/M cost estimates. Curated entries always win
// over LiteLLM live data inside the app.
//
// Idempotent: re-running replaces the previously-added keys/rules (tracked under
// _meta.shanaae_exact / _meta.shanaae_fuzzy) instead of duplicating them.
//
// Usage:
//   node patch-pricing.mjs [path-to-tokentracker-app]
//   (default: ~/.tokentracker/tracker/app/src/lib/pricing/curated-overrides.json)
//
// Re-run after every `tokentracker init` / upgrade, since the app dir is
// recreated from the npm package. Prefer the installed-app path so both the
// Windows dashboard and the WSL-triggered sync read the same file.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PRICING_SRC = join(__dirname, "pricing.json");

function resolveTarget(argv) {
  if (argv[0]) {
    const explicit = resolve(argv[0]);
    // Allow passing either the app root or the curated-overrides.json directly.
    if (explicit.endsWith("curated-overrides.json")) return explicit;
    return join(explicit, "src", "lib", "pricing", "curated-overrides.json");
  }
  return join(homedir(), ".tokentracker", "tracker", "app", "src", "lib", "pricing", "curated-overrides.json");
}

function main() {
  const target = resolveTarget(process.argv.slice(2));
  if (!existsSync(target)) {
    console.error(`[pricing] curated-overrides.json not found: ${target}`);
    console.error("[pricing] pass the tokentracker app dir explicitly, e.g.:");
    console.error("  node patch-pricing.mjs /mnt/c/Users/<user>/.tokentracker/tracker/app");
    process.exit(1);
  }
  if (!existsSync(PRICING_SRC)) {
    console.error(`[pricing] pricing.json not found next to this script: ${PRICING_SRC}`);
    process.exit(1);
  }

  const src = JSON.parse(readFileSync(PRICING_SRC, "utf8"));
  const file = JSON.parse(readFileSync(target, "utf8"));

  const meta = file._meta && typeof file._meta === "object" ? file._meta : {};
  const prevExact = Array.isArray(meta.shanaae_exact) ? meta.shanaae_exact : [];
  const prevFuzzy = Array.isArray(meta.shanaae_fuzzy) ? meta.shanaae_fuzzy : [];

  file.exact = file.exact && typeof file.exact === "object" ? file.exact : {};
  file.fuzzy = Array.isArray(file.fuzzy) ? file.fuzzy : [];

  // 1. Remove previously-added exact keys (only if we added them).
  for (const key of prevExact) {
    delete file.exact[key];
  }
  // Remove previously-added fuzzy rules by match.
  const prevFuzzySet = new Set(prevFuzzy);
  file.fuzzy = file.fuzzy.filter((r) => r && r.match && !prevFuzzySet.has(r.match));

  // 2. Merge new exact entries (ours win over whatever replaced them).
  const newExactKeys = Object.keys(src.exact || {});
  for (const key of newExactKeys) {
    file.exact[key] = src.exact[key];
  }

  // 3. Merge new fuzzy rules (dedupe by match).
  const existingMatches = new Set(file.fuzzy.map((r) => r && r.match).filter(Boolean));
  const newFuzzy = (src.fuzzy || []).filter(
    (r) => r && r.match && r.ref && !existingMatches.has(r.match),
  );
  file.fuzzy.push(...newFuzzy);

  // 4. Track ownership for the next run.
  meta.shanaae_exact = newExactKeys;
  meta.shanaae_fuzzy = newFuzzy.map((r) => r.match);
  meta.shanaae_applied_at = new Date().toISOString();
  file._meta = meta;

  writeFileSync(target, `${JSON.stringify(file, null, 2)}\n`, "utf8");

  console.log(`[pricing] patched ${target}`);
  console.log(`[pricing] exact entries: ${newExactKeys.length} (total ${Object.keys(file.exact).length})`);
  console.log(`[pricing] fuzzy rules:   ${newFuzzy.length} new (total ${file.fuzzy.length})`);
}

main();