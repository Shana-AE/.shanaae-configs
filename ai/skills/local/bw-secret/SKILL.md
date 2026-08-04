---
name: bw-secret
description: Fetch secrets from the Vaultwarden vault (Dev Secrets, login passwords, TOTP, SSH keys) without leaking values. Use when you need a credential stored in Bitwarden/Vaultwarden — 从保险库取密钥, bw get, bitwarden, vaultwarden, ssh key from vault, TOTP from vault.
---

# bw-secret — vault credentials without leaking

Context: Vaultwarden at `vault.shanaae.com`. The vault's **Dev Secrets** folder (secure notes named `secret: KEY`) is synced hourly into `${AI_CONFIGS_ROOT:-$HOME/.shanaae/configs}/.secrets.d/` (one 600-perm file per key, lowercase) by `shell/vault-sync.py` (cron on WSL + Mac mini). The master password file lives at `.secrets.d/bw-master-password` so `bw` can unlock non-interactively. The core rule: **capture values into variables or files — never print them**.

## 1. Discovery — what exists? (names only, safe)

```bash
python3 ~/.shanaae/configs/shell/vault-sync.py --list          # Dev Secret keys
bw list items | jq -r '.[].name'                               # all vault item names
```

Never print raw `bw list items` output — it contains decrypted passwords.

## 2. Synced Dev Secrets (preferred — no bw session needed)

```bash
python3 ~/.shanaae/configs/shell/vault-sync.py --pull KEY      # materializes .secrets.d/key (chmod 600)
export KEY="$(cat ~/.shanaae/configs/.secrets.d/key)"           # value never printed
# or load everything at once:
set -a; source ${AI_CONFIGS_ROOT:-$HOME/.shanaae/configs}/.secrets; set +a
```

## 3. On-demand vault items (login passwords, usernames, TOTP)

Unlock once, silently (the command text shows only the password-file path):

```bash
export BW_SESSION="$(NODE_OPTIONS=--dns-result-order=ipv4first command bw unlock --raw --passwordfile ~/.shanaae/configs/.secrets.d/bw-master-password)"
```

Then capture, never print:

```bash
PASS="$(bw get password 'Item Name')"          # capture into a variable
USER="$(bw get username 'Item Name')"
OTP="$(bw get totp 'Item Name')"
curl -sS -u "$USER:$PASS" https://...          # use in-place; only $VAR is recorded
bw lock                                        # always lock after
```

## 4. SSH keys (vault item `ssh: NAME`, native SSH-key type; `.sshKey.privateKey` / `.sshKey.publicKey` / `.sshKey.keyFingerprint`)

Fetch to a file, never to stdout:

```bash
bw get item 'ssh: wsl' | jq -r .sshKey.privateKey > /tmp/bwkey && chmod 600 /tmp/bwkey
ssh -i /tmp/bwkey user@host ...
rm -f /tmp/bwkey
# public key:  bw get item 'ssh: wsl' | jq -r .sshKey.publicKey
# fingerprint: bw get item 'ssh: wsl' | jq -r .sshKey.keyFingerprint
```

Store a new key pair: `python3 ~/.shanaae/configs/shell/vault-sync.py --add-ssh NAME --ssh-keyfile ~/.ssh/id_ed25519` (defaults to `~/.ssh/id_ed25519`; creates or updates item `ssh: NAME`).

## 5. MCP servers

Reference materialized files in opencode.jsonc: `"Authorization": "Bearer {file:~/.shanaae/configs/.secrets.d/<key>}"` — fresh hourly via cron; run `--pull <key>` for instant refresh.

## Hard rules (never violate)

- **Never run `bw get ...` / `bw get item ...` standalone** — the value goes to stdout → tool output → transcript.
- **Never run `bw unlock --raw` standalone** — it prints the session key.
- **Never echo a captured value or pass it as a literal argument** — use `$VAR` references; shell expansion happens after the command text is recorded.
- **Never print `bw list items` output** (includes decrypted passwords) — pipe to `jq` for names only.
- **Never `bw export`** (dumps the whole vault).
- `bw status`/`bw sync`/`bw lock` are allow-listed in permission config; any other `bw` command triggers a prompt — approve **"once"**, never **"always"** (always stores `bw * → allow`, which would let standalone `bw get` run silently).
- **Lock after use**: `bw lock`.
- The interactive zsh auto-unlock wrapper may not exist in tool shells — always set `BW_SESSION` explicitly as in section 3.
