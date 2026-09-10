#!/usr/bin/env python3
"""Extract opencode hourly buckets from a TokenTracker cursor state into the
compact_retract.py dump format."""
import json, sys

state_path, out_path = sys.argv[1], sys.argv[2]
d = json.load(open(state_path))
ho = (d.get("hourly") or {}).get("buckets", {})
out = {}
for k, v in ho.items():
    if not k.startswith("opencode|"):
        continue
    out[k] = {"totals": v.get("totals", {}), "queuedKey": v.get("queuedKey")}
json.dump({"buckets": out, "updatedAt": d.get("updatedAt")}, open(out_path, "w"))
print(f"extracted {len(out)} opencode buckets -> {out_path}")
