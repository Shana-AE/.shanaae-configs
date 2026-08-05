#!/usr/bin/env python3
"""screenpipe — AI that knows everything you've seen, said, or heard
https://screenpipe.com
Sync opencode's model providers (qiniu + BYOK providers from opencode auth)
into screenpipe's pi-config/models.json, store.bin AI presets, and pipe.md
frontmatter, so screenpipe keeps working after the screenpipe-cloud gift
subscription expires.

Sources of truth:
  - qiniu models        : ~/.config/opencode/opencode.jsonc  (provider.qiniu.models)
  - BYOK provider keys  : ~/.local/share/opencode/auth.json
  - qiniu API key       : ~/.shanaae/configs/.secrets.d/qiniu_ai_api_key
  - model catalogs      : live probe of each provider's /v1/models, cached in
                          ~/.cache/screenpipe-sync/provider-models.json; embedded
                          fallback lists for offline use

Targets (screenpipe data dir):
  - pi-config/models.json   -> add/merge a provider entry per opencode provider
  - store.bin               -> one AI preset per provider (qiniu = default),
                               demote `screenpipe-cloud` to non-default fallback,
                               and (unless --keep-cloud-transcription) switch
                               audio transcription + live meeting transcription
                               to local engines
  - pipes/*/pipe.md         -> `preset: screenpipe-cloud` -> `preset: qiniu`,
                               add `preset: qiniu` where missing, and swap
                               legacy `provider: screenpipe`

Usage:
  sync_opencode_models.py [--apply] [--target DIR] [--wsl-copy] [--no-probe]
                          [--keep-cloud-transcription] [--quiet]
Default is dry-run (prints the diff plan, writes nothing).

Never prints API keys (only masked prefixes).
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime

HOME = os.path.expanduser("~")
OPENCODE_JSONC = os.path.join(HOME, ".config/opencode/opencode.jsonc")
AUTH_JSON = os.path.join(HOME, ".local/share/opencode/auth.json")
QINIU_SECRET = os.path.join(HOME, ".shanaae/configs/.secrets.d/qiniu_ai_api_key")
CACHE_DIR = os.path.join(HOME, ".cache/screenpipe-sync")
PROVIDER_MODELS_CACHE = os.path.join(CACHE_DIR, "provider-models.json")

DEFAULT_TARGET = "/mnt/c/Users/shana/.screenpipe"
WSL_COPY_TARGET = os.path.join(HOME, ".screenpipe")

PRESET_ID = "qiniu"
DEFAULT_PRESET_MODEL = "deepseek/deepseek-v4-flash-20260731"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_CONTEXT_CHARS = 128000

# legacy screenpipe-cloud preset ids (any of these is demoted to fallback)
CLOUD_PRESET_IDS = {"screenpipe-cloud", "screenpipe", "pi"}

# baseURL per opencode auth provider id (models.dev / provider docs)
PROVIDER_BASEURLS = {
    "qiniu": "https://api.qnaigc.com/v1",
    "deepseek": "https://api.deepseek.com",
    "zhipuai-coding-plan": "https://open.bigmodel.cn/api/paas/v4",
    "minimax-cn-coding-plan": "https://api.minimaxi.com/v1",
    "kimi-for-coding": "https://api.kimi.com/coding/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "alibaba-cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

# providers to sync; "openai" is OAuth-only (ChatGPT login), skip it.
SYNC_PROVIDERS = [
    "qiniu",
    "deepseek",
    "zhipuai-coding-plan",
    "minimax-cn-coding-plan",
    "kimi-for-coding",
    "nvidia",
    "alibaba-cn",
]

# default model for each provider's AI preset (used by chat + pipes)
PRESET_DEFAULT_MODELS = {
    "qiniu": DEFAULT_PRESET_MODEL,
    "deepseek": "deepseek-v4-flash",
    "zhipuai-coding-plan": "glm-5.2",
    "minimax-cn-coding-plan": "MiniMax-M3",
    "kimi-for-coding": "k3-256k",
    "nvidia": "nvidia/nemotron-3-super-120b-a12b",
    "alibaba-cn": "qwen3.8-max",
}

# curated cap + keep-list for the huge catalogs (nvidia ~102, alibaba ~234)
BIG_CATALOG_CAP = 20
NVIDIA_KEEP = re.compile(r"nemotron|deepseek|qwen|llama|minitron|phi|grok|cosmos|smol", re.I)
ALIBABA_KEEP = re.compile(r"^(qwen3\.|qwen-max|qwen-plus|qwen3-|qwen2\.5-vl|qwen-vl|kimi/kimi-k2|kimi/kimi-k3|glm-5)", re.I)
# vision-ish heuristics for native providers (models.dev has no modality data here)
VISION_HINT = re.compile(r"vl|vision|multimodal|image|ocr|audio", re.I)

# embedded fallback model lists (last known good, used offline / when probe fails)
FALLBACK_MODELS = {
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "zhipuai-coding-plan": ["glm-4.5", "glm-4.5-air", "glm-4.6", "glm-4.7", "glm-5", "glm-5-turbo", "glm-5.1", "glm-5.2"],
    "minimax-cn-coding-plan": ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.5", "MiniMax-M2.5-highspeed", "MiniMax-M2.1", "MiniMax-M2.1-highspeed", "MiniMax-M2"],
    "kimi-for-coding": ["kimi-for-coding", "kimi-for-coding-highspeed", "k3", "k3-256k"],
}

# local (non-cloud) transcription settings, applied unless --keep-cloud-transcription
LOCAL_TRANSCRIPTION_ENGINE = "whisper-large-v3-turbo-quantized"
LOCAL_MEETING_PROVIDER = "local"

# system prompt for generated presets (mirrors the stock screenpipe-cloud preset)
PRESET_PROMPT = (
    "IMPORTANT: At the start of every conversation, read the files in .pi/skills/ directory (e.g. .pi/skills/screenpipe-api/SKILL.md and .pi/skills/screenpipe-cli/SKILL.md) before responding.\n"
    "Rules:\n"
    "- Media: use standard markdown with angle-bracket local paths, like ![description](</path/to/file.mp4>) for videos and ![description](</path/to/image.jpg>) for images\n"
    "- Always wrap local file paths in angle brackets because screenpipe paths often contain spaces or parentheses\n"
    "- Always answer my question/intent, do not make up things\n"
)


def log(msg, quiet=False):
    if not quiet:
        print(msg)


def mask(key):
    if not key:
        return "None"
    if len(key) <= 12:
        return key[0] + "…"
    return key[:8] + "…"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def strip_jsonc_comments(src):
    """Strip // and /* */ comments from JSONC, leaving string contents intact."""
    out = []
    i, n = 0, len(src)
    in_str = False
    while i < n:
        c = src[i]
        if in_str:
            out.append(c)
            if c == "\\":
                i += 1
                if i < n:
                    out.append(src[i])
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = src[i + 1]
            if nxt == "/":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                    i += 1
                i = min(i + 2, n)
                continue
        out.append(c)
        i += 1
    return "".join(out)


def read_opencode_qiniu_models():
    """Parse qiniu provider models out of opencode.jsonc (strip comments)."""
    src = strip_jsonc_comments(open(OPENCODE_JSONC, encoding="utf-8").read())
    cfg = json.loads(src)
    models = cfg.get("provider", {}).get("qiniu", {}).get("models", {})
    out = []
    for mid, spec in models.items():
        if isinstance(spec, dict):
            out.append({
                "id": mid,
                "name": spec.get("name", mid),
                "context": spec.get("limit", {}).get("context", 128000),
                "output": spec.get("limit", {}).get("output", 64000),
                "reasoning": bool(spec.get("reasoning")),
                "attachment": bool(spec.get("attachment")),
                "modalities": spec.get("modalities", {}).get("input", []),
            })
    return out


def probe_models(base_url, api_key, timeout=25):
    """GET {base}/models with the provider key; returns list of model ids or None."""
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        ids = [m["id"] for m in data.get("data", [])]
        return ids if ids else None
    except Exception:
        return None


def load_provider_models_cache():
    try:
        return load_json(PROVIDER_MODELS_CACHE)
    except Exception:
        return {}


def native_model_entry(mid, keep_re=None):
    """Build a screenpipe models[] entry for a native provider model id."""
    if keep_re and not keep_re.search(mid):
        return None
    return {
        "id": mid,
        "name": mid,
        "contextWindow": 128000,
        "maxTokens": 128000,
        "reasoning": False,
        "input": ["text", "image"] if VISION_HINT.search(mid) else ["text"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
    }


def build_qiniu_provider(api_key, qiniu_models):
    models = []
    for m in qiniu_models:
        # pi's models.json schema only allows "text" and "image" input literals
        # (pi-coding-agent model-config.js); anything else invalidates the file.
        inp = ["text"]
        if m["attachment"]:
            inp.append("image")
        models.append({
            "id": m["id"],
            "name": m["name"],
            "contextWindow": m["context"],
            "maxTokens": m["output"],
            "reasoning": m["reasoning"],
            "input": inp,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        })
    return {
        "baseUrl": PROVIDER_BASEURLS["qiniu"],
        "api": "openai-completions",
        "apiKey": api_key,
        "models": models,
    }


def build_custom_provider(api_key, qiniu_models):
    """The app passes provider='custom' for every BYOK preset (chat + pipes),
    and the pi agent resolves it from a models.json provider keyed 'custom'.
    Chat overwrites this entry at piStart with the active preset's url; pipes
    rely on this static one (qiniu endpoint = the default preset)."""
    q = build_qiniu_provider(api_key, qiniu_models)
    return {
        "baseUrl": q["baseUrl"],
        "api": "openai-completions",
        "apiKey": api_key,
        "models": q["models"],
    }


def build_native_provider(provider, api_key, model_ids):
    keep = NVIDIA_KEEP if provider == "nvidia" else (ALIBABA_KEEP if provider == "alibaba-cn" else None)
    models = [native_model_entry(mid, keep) for mid in model_ids]
    models = [m for m in models if m]
    if provider in ("nvidia", "alibaba-cn"):
        models = models[:BIG_CATALOG_CAP]
    return {
        "baseUrl": PROVIDER_BASEURLS[provider],
        "api": "openai-completions",
        "apiKey": api_key,
        "models": models,
    }


def collect_providers(no_probe=False, quiet=False):
    """Returns {provider_id: provider_entry} for every SYNC_PROVIDERS."""
    auth = load_json(AUTH_JSON)
    qiniu_key = open(QINIU_SECRET, encoding="utf-8").read().strip()
    qiniu_models = read_opencode_qiniu_models()
    log(f"[providers] qiniu: {len(qiniu_models)} models from opencode.jsonc", quiet)

    cached = load_provider_models_cache()
    result = {
        "qiniu": build_qiniu_provider(qiniu_key, qiniu_models),
        # pi resolves every BYOK preset as provider "custom" — pre-write the
        # entry (qiniu endpoint = default preset) so pipes work without a
        # chat start having rewritten it first.
        "custom": build_custom_provider(qiniu_key, qiniu_models),
    }

    for prov in SYNC_PROVIDERS:
        if prov == "qiniu":
            continue
        entry = auth.get(prov)
        api_key = (entry or {}).get("key") or (entry or {}).get("api")
        if not api_key:
            log(f"[providers] SKIP {prov}: no key in auth.json", quiet)
            continue
        base_url = PROVIDER_BASEURLS[prov]

        model_ids = None
        if not no_probe:
            if prov in cached:
                model_ids = cached[prov]
            else:
                model_ids = probe_models(base_url, api_key)
                if model_ids:
                    cached[prov] = model_ids
        if not model_ids:
            model_ids = FALLBACK_MODELS.get(prov, [])
            log(f"[providers] {prov}: using embedded fallback list ({len(model_ids)})", quiet)
        else:
            log(f"[providers] {prov}: {len(model_ids)} models from live probe", quiet)

        result[prov] = build_native_provider(prov, api_key, model_ids)

    if not no_probe:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = CACHE_DIR + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cached, f, indent=1)
        os.replace(tmp, PROVIDER_MODELS_CACHE)
    return result


# ---------------------------------------------------------------------------
# models.json
# ---------------------------------------------------------------------------

def models_json_path(data_dir):
    return os.path.join(data_dir, "pi-config", "models.json")


def merge_models_json(data_dir, providers):
    path = models_json_path(data_dir)
    try:
        doc = load_json(path)
    except Exception:
        doc = {"providers": {}}
    doc.setdefault("providers", {})
    if not isinstance(doc["providers"], dict):
        doc["providers"] = {}
    changed = []
    for pid, entry in providers.items():
        existing = doc["providers"].get(pid)
        if existing != entry:
            doc["providers"][pid] = entry
            changed.append(pid)
    return doc, changed


# ---------------------------------------------------------------------------
# store.bin (settings.aiPresets + transcription settings)
# ---------------------------------------------------------------------------

def store_bin_path(data_dir):
    return os.path.join(data_dir, "store.bin")


def build_presets(store, providers):
    """One AI preset per provider; qiniu = default; legacy cloud presets demoted."""
    presets = store.get("settings", {}).get("aiPresets", [])
    if not isinstance(presets, list):
        presets = []

    cloud = next((p for p in presets
                  if p.get("id") in CLOUD_PRESET_IDS or p.get("provider") in ("screenpipe-cloud", "pi")),
                 None)
    prompt = (cloud or {}).get("prompt", PRESET_PROMPT)

    new_presets = []
    seen = set()
    for p in presets:
        p = dict(p)
        if p.get("id") in CLOUD_PRESET_IDS or p.get("provider") in ("screenpipe-cloud", "pi"):
            p["defaultPreset"] = False
        new_presets.append(p)
        seen.add(p["id"])

    for prov in SYNC_PROVIDERS:
        entry = providers.get(prov)
        if not entry:
            continue
        new_preset = {
            "id": prov,
            "prompt": prompt,
            "provider": "custom",
            "url": entry["baseUrl"],
            "model": PRESET_DEFAULT_MODELS.get(prov, DEFAULT_PRESET_MODEL),
            "defaultPreset": prov == PRESET_ID,
            "apiKey": entry["apiKey"],
            "maxContextChars": DEFAULT_CONTEXT_CHARS,
            "maxTokens": DEFAULT_MAX_TOKENS,
            "acpAgent": None,
        }
        if prov not in seen:
            new_presets.append(new_preset)
            seen.add(prov)
        else:
            # replace a stale entry under the same id (e.g. old anonymous "screenpipe")
            new_presets = [new_preset if p["id"] == prov else p for p in new_presets]
    return new_presets


def patch_store(store, providers, keep_cloud_transcription=False):
    settings = store.setdefault("settings", {})
    changes = []

    old_presets = settings.get("aiPresets")
    new_presets = build_presets(store, providers)
    settings["aiPresets"] = new_presets
    if json.dumps(old_presets, sort_keys=True) != json.dumps(new_presets, sort_keys=True):
        changes.append("aiPresets")

    if not keep_cloud_transcription:
        if settings.get("audioTranscriptionEngine") == "screenpipe-cloud":
            settings["audioTranscriptionEngine"] = LOCAL_TRANSCRIPTION_ENGINE
            changes.append("audioTranscriptionEngine -> local whisper")
        if settings.get("meetingLiveTranscriptionProvider") == "screenpipe-cloud":
            settings["meetingLiveTranscriptionProvider"] = LOCAL_MEETING_PROVIDER
            changes.append("meetingLiveTranscriptionProvider -> local")
    return store, changes


# ---------------------------------------------------------------------------
# pipes/*/pipe.md
# ---------------------------------------------------------------------------

def patch_pipe_frontmatter(md):
    """Swap presets in pipe.md frontmatter. Returns (new_md, changed, note)."""
    lines = md.split("\n")
    idx = 0
    end = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
    if end is None:
        return md, False, "no frontmatter"
    fm = lines[1:end]
    changed = False
    note = ""
    preset_line_idx = None
    provider_line_idx = None
    enabled_idx = None
    for i, ln in enumerate(fm):
        if ln.startswith("preset:"):
            preset_line_idx = i
        elif ln.startswith("provider:"):
            provider_line_idx = i
        elif ln.startswith("enabled:"):
            enabled_idx = i

    if preset_line_idx is not None:
        val = fm[preset_line_idx][len("preset:"):].strip()
        # consume YAML list items belonging to this key ("- screenpipe-cloud")
        j = preset_line_idx + 1
        while j < len(fm) and re.match(r"^\s*-\s+", fm[j]):
            j += 1
        if val in ("screenpipe-cloud", "screenpipe", "pi", '["screenpipe-cloud"]', "[screenpipe-cloud]"):
            fm[preset_line_idx] = "preset: qiniu"
            del fm[preset_line_idx + 1:j]
            changed = True
        elif not val:
            fm[preset_line_idx] = "preset: qiniu"
            del fm[preset_line_idx + 1:j]
            changed = True
        elif "screenpipe-cloud" in val:
            fm[preset_line_idx] = fm[preset_line_idx].replace("screenpipe-cloud", "qiniu")
            changed = True
        else:
            note = f"preset already '{val}'"
    else:
        insert_at = (enabled_idx + 1) if enabled_idx is not None else 0
        fm.insert(insert_at, "preset: qiniu")
        if provider_line_idx is not None and provider_line_idx >= insert_at:
            provider_line_idx += 1
        changed = True

    if provider_line_idx is not None and "screenpipe" in fm[provider_line_idx]:
        fm[provider_line_idx] = "provider: qiniu"
        changed = True
        note = "provider: screenpipe -> qiniu (kept legacy key)"
        # legacy pipes also pin `model:`; point it at the qiniu preset default
        m = provider_line_idx + 1
        while m < len(fm) and not fm[m].startswith("model:"):
            m += 1
        if m < len(fm) and "auto" in fm[m]:
            fm[m] = f"model: {DEFAULT_PRESET_MODEL}"
            changed = True

    return "\n".join(lines[:1] + fm + lines[end:]), changed, note


def patch_pipes(data_dir):
    pipes_dir = os.path.join(data_dir, "pipes")
    results = []
    if not os.path.isdir(pipes_dir):
        return results
    for name in sorted(os.listdir(pipes_dir)):
        pmd = os.path.join(pipes_dir, name, "pipe.md")
        if not os.path.isfile(pmd):
            continue
        with open(pmd, encoding="utf-8") as f:
            md = f.read()
        new_md, changed, note = patch_pipe_frontmatter(md)
        results.append({"path": pmd, "changed": changed, "note": note, "content": new_md if changed else None})
    return results


# ---------------------------------------------------------------------------
# apply / atomic writes / backups
# ---------------------------------------------------------------------------

def atomic_write(path, content):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".sp-sync-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def backup(path, stamp):
    if os.path.exists(path):
        bak = f"{path}.bak-pre-qiniu-sync-{stamp}"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
            return bak
    return None


def resolve_target(explicit):
    """Pick the live screenpipe data dir.

    The app pins SCREENPIPE_DATA_DIR to the store's `dataDir` setting at
    startup (main.rs), so the real store/pipes may live on another volume
    (e.g. H:\\.screenpipe) while a stale copy sits at ~/.screenpipe. If no
    --target is given, read dataDir from the default store and use it when
    it exists; otherwise fall back to the default path.
    """
    if explicit:
        return explicit
    try:
        store = load_json(os.path.join(DEFAULT_TARGET, "store.bin"))
        dd = (store.get("settings", {}) or {}).get("dataDir") or ""
        if dd and dd not in ("default", ""):
            p = dd.replace("\\", "/")
            m = re.match(r"^([A-Za-z]):(/.*)$", p)
            if m:
                p = f"/mnt/{m.group(1).lower()}{m.group(2)}"
            if os.path.isdir(p):
                return p
            log(f"[target] dataDir '{dd}' not accessible, falling back to {DEFAULT_TARGET}")
    except Exception:
        pass
    return DEFAULT_TARGET


def main():
    ap = argparse.ArgumentParser(description="sync opencode model providers into screenpipe config")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--target", default=None, help="screenpipe data dir (default: auto-detect from dataDir setting)")
    ap.add_argument("--wsl-copy", action="store_true", help="target the WSL copy (~/.screenpipe) instead")
    ap.add_argument("--no-probe", action="store_true", help="skip live /v1/models probes (use fallbacks)")
    ap.add_argument("--keep-cloud-transcription", action="store_true",
                    help="leave audio/meeting transcription on screenpipe-cloud")
    ap.add_argument("--quiet", action="store_true", help="less output")
    args = ap.parse_args()

    target = args.target or (WSL_COPY_TARGET if args.wsl_copy else resolve_target(None))
    if not os.path.isdir(target):
        sys.exit(f"target dir not found: {target}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    log(f"=== screenpipe sync ({mode}) -> {target}")

    providers = collect_providers(no_probe=args.no_probe, quiet=args.quiet)
    for pid, entry in providers.items():
        log(f"  provider {pid}: baseUrl={entry['baseUrl']} key={mask(entry['apiKey'])} models={len(entry['models'])}")

    mj_path = models_json_path(target)
    mj_doc, mj_changed = merge_models_json(target, providers)
    mj_pretty = json.dumps(mj_doc, indent=2)
    log(f"[models.json] providers to add/update: {mj_changed or 'none'}")

    sb_path = store_bin_path(target)
    store = load_json(sb_path)
    store, sb_changes = patch_store(store, providers, keep_cloud_transcription=args.keep_cloud_transcription)
    sb_pretty = json.dumps(store, indent=2)
    presets = store["settings"]["aiPresets"]
    log(f"[store.bin] presets now: {[(p['id'], p['defaultPreset']) for p in presets]}")
    log(f"[store.bin] changes: {sb_changes or 'none'}")
    if not args.keep_cloud_transcription:
        log(f"[store.bin] transcription: engine={store['settings'].get('audioTranscriptionEngine')} "
            f"meeting={store['settings'].get('meetingLiveTranscriptionProvider')}")

    pipe_results = patch_pipes(target)
    for r in pipe_results:
        log(f"[pipe] {os.path.basename(os.path.dirname(r['path']))}: {'CHANGED' if r['changed'] else 'ok'} {r['note']}")

    if not args.apply:
        log("\nDRY-RUN complete — no files written. Re-run with --apply to commit.")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    b1 = backup(mj_path, stamp)
    b2 = backup(sb_path, stamp)
    if mj_changed:
        atomic_write(mj_path, mj_pretty)
    if sb_changes:
        atomic_write(sb_path, sb_pretty)
    for r in pipe_results:
        if r["changed"] and r["content"]:
            b3 = backup(r["path"], stamp)
            atomic_write(r["path"], r["content"])
    log(f"\nAPPLIED. backups: {[b for b in (b1, b2) if b]}")
    log("Remember: restart the screenpipe app so it picks up store.bin.")


if __name__ == "__main__":
    main()
