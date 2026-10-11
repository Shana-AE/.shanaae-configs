# Qiniu discovery in dsh Desktop / 七牛模型发现

The Qiniu runtime gateway and authoritative model catalog have different URLs.
This local Cordis profile plugin routes the existing **Fetch available** action
for `llm-pi-ai` / `qiniu` to `https://api.modelink.ai/v1/models` using the host's
existing discovery handler. An anonymous draft bypasses pi-ai's bundled catalog;
the profile's `apiKeyEnv` is resolved through the host credentials service before
that draft is sent. Draft API keys take precedence. Request execution stays
on the provider's configured runtime base URL. Network failures fall back to
`https://openai.sufy.com/v1/models`; authentication errors and aborts do not.

Discovery results pass through the shared Python `filter` command, so the same
`model-policy.json` cutoffs apply and old generations do not reappear in the UI.
Known metadata from the canonical config fills absent context/output/input
fields; upstream discovery metadata takes precedence. The filter never adds
model IDs absent from the live reply. API keys never enter the policy subprocess
input, log messages, or command arguments.

## Installation

Run `python3 ai/skills/local/config-sync/scripts/render_dsh.py`. It adds a local
file-module entry to existing live profiles that configure Qiniu. The profile's
runtime endpoint, credentials, and other providers are preserved. A private
backup exists beside its `cordis.patch.yml`. The plugin wraps dsh's public
`discoverModels` method because this installed build does not expose a separate
catalog URL setting. Disposal restores the method. An incompatible dsh API
fails explicitly; the adapter should be checked after dsh upgrades.

Node.js and Python 3.9+ are required. Set `DSH_PYTHON_BIN` if the app cannot find
`python3`. The installed profile already supplies the `yaml` module used by the
installer. Restart dsh after the first installation if HMR has not loaded it. No npm installation or additional service is required.

## Validation

- `node --test .dsh/plugins/qiniu-model-discovery/index.test.mjs`
- `python3 ai/skills/local/qiniu-model-sync/scripts/test_qiniu_model_sync.py`
- `node --test ai/skills/local/config-sync/scripts/test_sync_dsh_profiles.cjs`
- Check **Fetch available** in the running desktop's Qiniu editor.
