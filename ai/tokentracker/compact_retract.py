#!/usr/bin/env python3
"""Compact a TokenTracker queue.jsonl and retract ghost opencode buckets.

Usage: compact_retract.py <queue-path> <hourlyBuckets-dump.json> [--apply]

Behavior:
- Last-wins dedup per (source, model, hour_start).
- For every `opencode` bucket present in the deduped dump: the compacted row's
  totals are replaced with the dump's authoritative values.
- For every `opencode` bucket in the queue but ABSENT from the dump (ghost
  bucket — messages moved/deleted since earlier syncs): a zeroed row is kept so
  the cloud upsert retracts it to zero.
- Non-opencode sources (codex, hermes, openclaw, ...) keep their last-wins rows.
- --apply writes the file; default prints a summary only.
"""
import json, sys, copy

ZERO = {
    "input_tokens": 0, "cached_input_tokens": 0, "cache_creation_input_tokens": 0,
    "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0,
    "billable_total_tokens": 0, "conversation_count": 0,
}

def main():
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    queue_path, dump_path = args[0], args[1]

    dump = json.load(open(dump_path))
    buckets = dump["buckets"]

    rows = []
    for line in open(queue_path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass

    best = {}
    order = []
    for r in rows:
        k = (r["source"], r["model"], r.get("hour_start"))
        if k not in best:
            order.append(k)
        best[k] = r  # last wins

    fixed = 0
    retracted = 0
    kept = 0
    out_rows = []
    for k in order:
        r = best[k]
        src, model, hour = k
        if src == "opencode":
            key = f"opencode|{model}|{hour}"
            if key in buckets:
                want = buckets[key]["totals"]
                cur = {kk: r.get(kk, 0) for kk in want}
                if any(abs(cur.get(kk, 0) - want[kk]) > 0 for kk in want):
                    fixed += 1
                nr = copy.deepcopy(r)
                for kk, vv in want.items():
                    nr[kk] = vv
                if "billable_total_tokens" in nr:
                    nr["billable_total_tokens"] = want.get("total_tokens", 0)
                out_rows.append(nr)
                kept += 1
                continue
            else:
                # ghost bucket -> retract to zero
                nr = copy.deepcopy(r)
                for kk, vv in ZERO.items():
                    nr[kk] = vv
                out_rows.append(nr)
                retracted += 1
                continue
        out_rows.append(r)
        kept += 1

    print(f"rows in: {len(rows)}  ->  out: {len(out_rows)}")
    print(f"opencode buckets corrected: {fixed}  kept-as-is: {kept}  ghost-retracted: {retracted}")

    oc_total = sum(r.get("total_tokens", 0) for r in out_rows if r["source"] == "opencode")
    print(f"opencode total after compact: {oc_total}")

    if apply:
        with open(queue_path, "w") as f:
            for r in out_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("WROTE", queue_path)

if __name__ == "__main__":
    main()
