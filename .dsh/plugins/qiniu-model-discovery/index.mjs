import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'qiniu-model-discovery';
export const inject = ['llm'];
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const FILTER_SCRIPT = resolve(ROOT, 'ai/skills/local/qiniu-model-sync/scripts/qiniu_model_sync.py');
const GATEWAYS = new Set(['api.qnaigc.com', 'openai.qiniu.com', 'api.modelink.ai', 'openai.sufy.com']);
export const CATALOG_BASE = 'https://api.modelink.ai/v1';
const LEGACY_BASE = 'https://openai.sufy.com/v1';

export function isQiniuDiscovery(namespace, request) {
  if (namespace !== 'llm-pi-ai' || request?.provider !== 'qiniu') return false;
  if (!request.baseURL) return true;
  try { return new URL(request.baseURL).protocol === 'https:' && GATEWAYS.has(new URL(request.baseURL).hostname); }
  catch { return false; }
}
export function filterWithPolicy(entries, signal, options = {}) {
  if (signal?.aborted) return Promise.reject(new Error('Qiniu discovery aborted'));
  return new Promise((resolveResult, reject) => {
    const child = spawn(options.python || process.env.DSH_PYTHON_BIN || 'python3',
      [options.script || FILTER_SCRIPT, 'filter'], { stdio: ['pipe', 'pipe', 'pipe'], signal });
    let output = '', size = 0;
    child.on('error', () => reject(new Error(signal?.aborted ? 'Qiniu discovery aborted' : 'Could not run the Qiniu model policy; check DSH_PYTHON_BIN')));
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      size += Buffer.byteLength(chunk);
      if (size > 2 * 1024 * 1024) { child.kill(); reject(new Error('Qiniu model metadata exceeded the size limit')); }
      else output += chunk;
    });
    // Never include subprocess stderr in UI errors; it may contain local config details.
    child.stderr.resume();
    child.stdin.on('error', () => {});
    child.on('close', code => {
      if (code !== 0) { reject(new Error(signal?.aborted ? 'Qiniu discovery aborted' : 'Qiniu model policy failed; check model-policy.json')); return; }
      try {
        const rows = JSON.parse(output);
        if (!Array.isArray(rows)) throw new Error();
        resolveResult(rows);
      } catch { reject(new Error('Qiniu model policy returned invalid metadata')); }
    });
    child.stdin.end(JSON.stringify(entries));
  });
}
export function wrapDiscovery(original, filter = filterWithPolicy, resolveKey = async () => undefined) {
  return async function(namespace, request, signal) {
    if (!isQiniuDiscovery(namespace, request)) return original.call(this, namespace, request, signal);
    const deadline = AbortSignal.timeout(20000);
    const effectiveSignal = signal ? AbortSignal.any([signal, deadline]) : deadline;
    // Omitting provider bypasses pi-ai's bundled Qiniu catalog. Resolve the
    // stored credential first, because an anonymous draft has no profile lookup.
    const apiKey = request.apiKey ?? await resolveKey();
    const draft = { ...request, provider: undefined, apiKey, baseURL: CATALOG_BASE, api: 'openai-completions' };
    let entries;
    try { entries = await original.call(this, namespace, draft, effectiveSignal); }
    catch (error) {
      if (effectiveSignal.aborted || !String(error?.message).startsWith('could not reach ')) throw error;
      entries = await original.call(this, namespace, { ...draft, baseURL: LEGACY_BASE }, effectiveSignal);
    }
    if (!entries.length) throw new Error('Qiniu model catalog was empty; the configured models were not changed');
    return filter(entries, effectiveSignal);
  };
}
export function apply(ctx, config = {}) {
  // Cordis may expose context-bound service facades. Patch the holder of the
  // public method so the host's Remote discoverModels call uses this adapter too.
  let target = ctx.llm;
  while (target && !Object.hasOwn(target, 'discoverModels')) target = Object.getPrototypeOf(target);
  if (!target || typeof target.discoverModels !== 'function') throw new Error('This dsh build has no compatible model discovery method');
  ctx.effect(() => {
    const original = target.discoverModels;
    const wrapped = wrapDiscovery(original, filterWithPolicy, async () => {
      const ref = config.apiKeyEnv || 'QINIU_AI_API_KEY';
      const credentials = ctx.get?.('credentials');
      const key = credentials ? (await credentials.resolve(ref))?.value : process.env[ref];
      if (!key) throw new Error('Qiniu discovery credential is unavailable; check the provider API key');
      return key;
    });
    target.discoverModels = wrapped;
    ctx.logger.info('Qiniu model discovery: Modelink catalog with shared retention policy');
    return () => { if (target.discoverModels === wrapped) target.discoverModels = original; };
  });
}
