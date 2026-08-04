#!/usr/bin/env python3
"""Bidirectional sync: Vaultwarden 'Dev Secrets' <-> .secrets + .secrets.d.
3-way merge (vault, .secrets, baseline). Conflicts flagged; deletions NOT propagated.
Run via hourly cron. Uses persisted BW_SESSION (auto-refreshed via
.secrets.d/bw-master-password when stale). Relies on clash DNS (vault.shanaae.com -> .63)."""
import json, os, re, subprocess, sys
from pathlib import Path

CONFIGS = Path.home() / ".shanaae" / "configs"
SECRETS = CONFIGS / ".secrets"
SECD = CONFIGS / ".secrets.d"
SYNCSTATE = CONFIGS / ".secrets.syncstate"
CONFLICTS = CONFIGS / ".secrets.conflicts"
SESSION_FILE = CONFIGS / ".bw-session"
MASTER_PW = CONFIGS / ".secrets.d" / "bw-master-password"
FOLDER = "Dev Secrets"
KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

def find_bw():
    for p in os.environ.get("PATH", "").split(os.pathsep):
        f = Path(p) / "bw"
        if f.exists() and os.access(f, os.X_OK):
            return str(f)
    for c in [Path.home() / ".local/share/pnpm/bin/bw", Path.home() / "Library/pnpm/bin/bw", Path("/opt/homebrew/bin/bw")]:
        if c.exists():
            return str(c)
    return None

def bw(bwpath, args, session=None):
    env = os.environ.copy()
    if session:
        env["BW_SESSION"] = session
    env["NODE_OPTIONS"] = "--dns-result-order=ipv4first"
    try:
        return subprocess.run([bwpath] + args, capture_output=True, text=True, env=env, timeout=120)
    except Exception as e:
        print(f"  bw error: {e}")
        return None

def bw_encode(bwpath, data):
    env = {**os.environ, "NODE_OPTIONS": "--dns-result-order=ipv4first"}
    r = subprocess.run([bwpath, "encode"], input=json.dumps(data), capture_output=True, text=True, env=env)
    return r.stdout.strip() if r.returncode == 0 else None

def update_line(lines, key, value):
    pat = re.compile(rf"^{re.escape(key)}=.*$")
    for i, l in enumerate(lines):
        if pat.match(l):
            lines[i] = f"{key}={value}"
            return
    lines.append(f"{key}={value}")

def parse_kv(lines):
    d = {}
    for l in lines:
        m = KV.match(l)
        if m:
            d[m.group(1)] = m.group(2)
    return d

def main():
    bwpath = find_bw()
    if not bwpath:
        print("bw not found")
        return 1
    session = SESSION_FILE.read_text().strip() if SESSION_FILE.exists() else ""

    st = bw(bwpath, ["status"], session)
    try:
        status = json.loads(st.stdout)["status"]
    except Exception:
        status = ""
    if status != "unlocked":
        if not MASTER_PW.exists():
            print(f"vault '{status}'; no session and no {MASTER_PW}; skip")
            return 0
        u = bw(bwpath, ["unlock", "--raw", "--passwordfile", str(MASTER_PW)])
        if not u or u.returncode != 0 or not u.stdout.strip():
            print(f"vault '{status}'; unlock failed; skip")
            return 0
        session = u.stdout.strip()
        SESSION_FILE.write_text(session)
        os.chmod(SESSION_FILE, 0o600)
        print("  session refreshed (auto-unlock)")

    bw(bwpath, ["sync"], session)
    fr = bw(bwpath, ["get", "folder", FOLDER], session)
    try:
        fid = json.loads(fr.stdout)["id"]
    except Exception:
        print("folder not found")
        return 1

    lr = bw(bwpath, ["list", "items", "--folderid", fid], session)
    vault, ids = {}, {}
    for it in json.loads(lr.stdout or "[]"):
        n = it.get("name", "")
        if n.startswith("secret: "):
            k = n[8:]
            vault[k] = it.get("notes") or ""
            ids[k] = it["id"]

    slines = SECRETS.read_text().splitlines() if SECRETS.exists() else []
    secrets = parse_kv(slines)
    baseline = {}
    if SYNCSTATE.exists():
        try:
            baseline = json.loads(SYNCSTATE.read_text())
        except Exception:
            pass

    keys = set(vault) | set(secrets) | set(baseline)
    new_lines = list(slines)
    conflicts = []
    new_baseline = {}
    changed = False

    for k in sorted(keys):
        v, s, b = vault.get(k), secrets.get(k), baseline.get(k)
        vp, sp, bp = v is not None, s is not None, b is not None

        if v == s:
            if vp:
                new_baseline[k] = v
            continue

        if vp and sp:
            vc, sc = (v != b), (s != b)
            if vc and not sc:
                update_line(new_lines, k, v); new_baseline[k] = v; changed = True; print(f"  vault->secrets: {k}")
            elif sc and not vc:
                item = json.dumps(json.loads(bw(bwpath, ["get", "item", ids[k]], session).stdout))
                it = json.loads(item); it["notes"] = s
                enc = bw_encode(bwpath, it)
                if enc and bw(bwpath, ["edit", "item", ids[k], enc], session):
                    new_baseline[k] = s; print(f"  secrets->vault: {k}")
                else:
                    conflicts.append((k, v, s)); print(f"  ! edit failed: {k}")
            else:
                conflicts.append((k, v, s)); new_baseline[k] = b if bp else v; print(f"  CONFLICT: {k}")
        elif vp and not sp:
            if not bp:
                update_line(new_lines, k, v); new_baseline[k] = v; changed = True; print(f"  vault->secrets (new): {k}")
            else:
                new_baseline[k] = v; print(f"  (deleted in .secrets, kept in vault): {k}")
        elif not vp and sp:
            if not bp:
                tmpl = json.loads(bw(bwpath, ["get", "template", "item"], session).stdout or "{}")
                tmpl.update({"type": 2, "secureNote": {"type": 0}, "name": f"secret: {k}", "notes": s, "folderId": fid})
                enc = bw_encode(bwpath, tmpl)
                if enc and bw(bwpath, ["create", "item", enc], session):
                    new_baseline[k] = s; print(f"  secrets->vault (new): {k}")
                else:
                    conflicts.append((k, v, s)); print(f"  ! create failed: {k}")
            else:
                new_baseline[k] = s; print(f"  (deleted in vault, kept in .secrets): {k}")

    if changed:
        tmp = SECRETS.with_suffix(".tmp")
        tmp.write_text("\n".join(new_lines) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(SECRETS)
        print("  .secrets updated (comments preserved)")

    final = parse_kv(new_lines)
    SECD.mkdir(parents=True, exist_ok=True)
    os.chmod(SECD, 0o700)
    for k, val in final.items():
        f = SECD / k.lower()
        f.write_text(val)
        os.chmod(f, 0o600)

    SYNCSTATE.write_text(json.dumps(new_baseline, indent=2, sort_keys=True))
    os.chmod(SYNCSTATE, 0o600)
    if conflicts:
        CONFLICTS.write_text("\n".join(f"{k}: vault={v!r} secrets={s!r}" for k, v, s in conflicts) + "\n")
        os.chmod(CONFLICTS, 0o600)
        print(f"  {len(conflicts)} conflict(s) -> .secrets.conflicts")
    else:
        CONFLICTS.unlink(missing_ok=True)

    bw(bwpath, ["sync"], session)
    print(f"sync done ({len(final)} keys)")

if __name__ == "__main__":
    sys.exit(main() or 0)
