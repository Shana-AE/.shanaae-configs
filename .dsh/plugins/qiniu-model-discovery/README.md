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

Install the local package through dsh's official CLI, then migrate the old
file-module mount and synchronize the existing credential reference:

```sh
dsh plugin --profile desktop add "$AI_CONFIGS_ROOT/.dsh/plugins/qiniu-model-discovery"
python3 "$AI_CONFIGS_ROOT/ai/skills/local/config-sync/scripts/render_dsh.py"
```

Restart dsh after installation. **Plugins → Installed → Qiniu Model Discovery**
now shows the package, its version, description, and enable/disable controls.
The package declares `dsh.bundle.patch`; dsh manages its dependency and selected
bundle in the live profile. The shared renderer only synchronizes its credential
reference and migrates the former direct file-module entry. It does not install,
reinstall, or re-enable the package, so disabling or removing it stays effective.
The plugin is private/local and is not published to the community marketplace.

The runtime endpoint, credentials, and other providers are preserved. The
plugin wraps dsh's public `discoverModels` method because this installed build
has no separate catalog URL setting. Disposal restores the method. Check it
after dsh upgrades; an incompatible discovery API fails explicitly.

Node.js 20+ (dsh supplies the runtime) and Python 3.9+ are required. The local
package is linked to this configs checkout because it uses the shared retention
policy and Python script there. Set `DSH_PYTHON_BIN` if dsh cannot find Python.
No additional service is required.

## Validation

- `node --test .dsh/plugins/qiniu-model-discovery/index.test.mjs`
- `python3 ai/skills/local/qiniu-model-sync/scripts/test_qiniu_model_sync.py`
- `node --test ai/skills/local/config-sync/scripts/test_sync_dsh_profiles.cjs`
- Check **Fetch available** in the running desktop's Qiniu editor.
