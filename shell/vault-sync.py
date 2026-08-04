#!/usr/bin/env python3
"""Bidirectional sync: Vaultwarden 'Dev Secrets' <-> .secrets + .secrets.d.
3-way merge (vault, .secrets, baseline). Conflicts flagged; deletions NOT propagated.
Run via hourly cron. Uses persisted BW_SESSION (auto-refreshed via
.secrets.d/bw-master-password when stale). Relies on clash DNS (vault.shanaae.com -> .63).

Subcommands (agent-facing):
  (no args)      full 3-way sync (cron)
  --list         print Dev Secrets key names only (safe)
  --pull KEY     materialize one Dev Secret into .secrets.d/<key> (chmod 600)
  --add-ssh NAME store an SSH key pair as vault item 'ssh: NAME' (secure note)
"""
import argparse, json, os, re, subprocess, sys
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
    candidates = []
    for p in os.environ.get("PATH", "").split(os.pathsep):
        f = Path(p) / "bw"
        if f.exists() and os.access(f, os.X_OK):
            candidates.append(f)
    for c in [Path("/opt/homebrew/bin/bw"), Path.home() / ".local/share/pnpm/bin/bw", Path.home() / "Library/pnpm/bin/bw"]:
        if c.exists():
            candidates.append(c)
    for c in candidates:
        try:
            r = subprocess.run([str(c), "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return str(c)
        except Exception:
            continue
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


def ensure_session(bwpath):
    session = SESSION_FILE.read_text().strip() if SESSION_FILE.exists() else ""
    st = bw(bwpath, ["status"], session)
    try:
        status = json.loads(st.stdout)["status"]
    except Exception:
        status = ""
    if status != "unlocked":
        if not MASTER_PW.exists():
            print(f"vault '{status}'; no session and no {MASTER_PW}; skip")
            return None
        u = bw(bwpath, ["unlock", "--raw", "--passwordfile", str(MASTER_PW)])
        if not u or u.returncode != 0 or not u.stdout.strip():
            print(f"vault '{status}'; unlock failed; skip")
            return None
        session = u.stdout.strip()
        SESSION_FILE.write_text(session)
        os.chmod(SESSION_FILE, 0o600)
        print("  session refreshed (auto-unlock)")
    return session


def load_dev_secrets(bwpath, session):
    bw(bwpath, ["sync"], session)
    fr = bw(bwpath, ["get", "folder", FOLDER], session)
    try:
        fid = json.loads(fr.stdout)["id"]
    except Exception:
        print("folder not found")
        return {}, None
    lr = bw(bwpath, ["list", "items", "--folderid", fid], session)
    vault = {}
    for it in json.loads(lr.stdout or "[]"):
        n = it.get("name", "")
        if n.startswith("secret: "):
            vault[n[8:]] = it
    return vault, fid


def cmd_pull(vault, key):
    it = vault.get(key)
    if not it:
        print(f"no Dev Secret named '{key}'")
        return 1
    SECD.mkdir(parents=True, exist_ok=True)
    os.chmod(SECD, 0o700)
    f = SECD / key.lower()
    f.write_text(it.get("notes") or "")
    os.chmod(f, 0o600)
    print(f"pulled -> {f}")
    return 0


def ssh_key_type(name):
    n = name.lower()
    if "rsa" in n:
        return "rsa"
    if "ecdsa" in n:
        return "ecdsa"
    return "ed25519"


def ssh_key_type_from_pub(pub_content):
    parts = pub_content.split()
    if len(parts) >= 2:
        t = parts[0]
        if t == "ssh-rsa":
            return "rsa"
        if t.startswith("ecdsa"):
            return "ecdsa"
        if t == "ssh-ed25519":
            return "ed25519"
    return ""


def ssh_fingerprint(pub):
    try:
        r = subprocess.run(["ssh-keygen", "-lf", str(pub), "-E", "sha256"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[1]
    except Exception:
        pass
    return ""


def cmd_add_ssh(bwpath, session, name, keyfile):
    keyfile = Path(keyfile).expanduser()
    pubfile = Path(str(keyfile) + ".pub")
    if not keyfile.exists() or not pubfile.exists():
        print(f"key files not found: {keyfile} / {pubfile}")
        return 1
    pub = pubfile.read_text().strip()
    fields = [
        {"name": "publicKey", "value": pub},
        {"name": "fingerprint", "value": ssh_fingerprint(pubfile)},
        {"name": "keyType", "value": ssh_key_type_from_pub(pub) or ssh_key_type(name + " " + keyfile.name)},
    ]
    item = {
        "type": 2,
        "secureNote": {"type": 0},
        "name": f"ssh: {name}",
        "notes": keyfile.read_text().strip(),
        "fields": fields,
    }
    enc = bw_encode(bwpath, item)
    if not enc:
        print("encode failed")
        return 1
    existing = None
    lr = bw(bwpath, ["list", "items", "--search", f"ssh: {name}"], session)
    try:
        for it in json.loads(lr.stdout or "[]"):
            if it.get("name") == f"ssh: {name}" and it.get("type") == 2:
                existing = it
                break
    except Exception:
        pass
    if existing:
        it = json.loads(bw(bwpath, ["get", "item", existing["id"]], session).stdout)
        it["notes"] = item["notes"]
        it["fields"] = fields
        enc = bw_encode(bwpath, it)
        r = bw(bwpath, ["edit", "item", existing["id"], enc], session)
        verb = "updated"
    else:
        r = bw(bwpath, ["create", "item", enc], session)
        verb = "created"
    if r and r.returncode == 0:
        print(f"ssh key '{name}' {verb} (fingerprint: {fields[1]['value']})")
        return 0
    print("failed to store ssh key")
    return 1


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print Dev Secrets key names only")
    ap.add_argument("--pull", metavar="KEY", help="materialize one Dev Secret into .secrets.d")
    ap.add_argument("--add-ssh", metavar="NAME", help="store SSH key pair as vault item 'ssh: NAME'")
    ap.add_argument("--ssh-keyfile", default="~/.ssh/id_ed25519", help="private key path for --add-ssh")
    args = ap.parse_args()

    bwpath = find_bw()
    if not bwpath:
        print("bw not found")
        return 1
    session = ensure_session(bwpath)
    if session is None:
        return 0

    if args.add_ssh:
        return cmd_add_ssh(bwpath, session, args.add_ssh, args.ssh_keyfile)

    vault, fid = load_dev_secrets(bwpath, session)
    if vault is None:
        return 1

    if args.list:
        for k in sorted(vault):
            print(k)
        return 0

    if args.pull:
        return cmd_pull(vault, args.pull)

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
        vit = vault.get(k)
        v = vit["notes"] if vit else None
        s, b = secrets.get(k), baseline.get(k)
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
                item = json.dumps(json.loads(bw(bwpath, ["get", "item", vit["id"]], session).stdout))
                it = json.loads(item); it["notes"] = s
                enc = bw_encode(bwpath, it)
                if enc and bw(bwpath, ["edit", "item", vit["id"], enc], session):
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
