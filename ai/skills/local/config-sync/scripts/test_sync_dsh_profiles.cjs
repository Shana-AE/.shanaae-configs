const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const yaml = require(process.env.DSH_YAML_MODULE || path.join(os.homedir(), '.dsh/profiles/desktop/node_modules/yaml'));
const { patchProfileText, main } = require('./sync_dsh_profiles.cjs');
const models = [{ id: 'openai/gpt-6.1-sol', name: 'Sol', input: ['text', 'image'] }];
const profile = '# preserve comment\n- id: llm-pi-ai\n  config:\n    providers:\n      qiniu:\n        apiKeyEnv: QINIU_AI_API_KEY\n        models:\n          - id: deepseek-v3\n        baseURL: https://api.qnaigc.com/v1\n      other:\n        apiKey: !!js process.env.OTHER_KEY\n        models: [{id: other-model}]\n- id: plugin-extra\n  config: {keep: true}\n';

test('replaces only models and preserves comments, providers, plugins, and JS tags', () => {
  const result = patchProfileText(profile, models, yaml);
  assert.ok(result.startsWith('# preserve comment\n'));
  assert.ok(result.endsWith(profile.slice(profile.indexOf('        baseURL:'))));
  assert.ok(result.includes('apiKey: !!js process.env.OTHER_KEY'));
  assert.ok(!result.includes('deepseek-v3'));
  assert.equal(patchProfileText(result, models, yaml), result);
});
test('supports flow-style model sequences', () => {
  const original = '- id: llm-pi-ai\n  config:\n    providers:\n      qiniu:\n        models: [{id: old}]\n        apiKeyEnv: QINIU_AI_API_KEY\n';
  const result = patchProfileText(original, models, yaml);
  assert.ok(result.includes('apiKeyEnv: QINIU_AI_API_KEY'));
  assert.equal(patchProfileText(result, models, yaml), result);
});
test('profiles without Qiniu are untouched', () => {
  const text = '- id: llm-pi-ai\n  config: {providers: {other: {models: []}}}\n';
  assert.equal(patchProfileText(text, models, yaml), text);
});
test('check mode detects desktop drift without writing', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dsh-profile-check-'));
  const target = path.join(root, 'cordis.patch.yml'), source = path.join(root, 'settings.yaml');
  fs.writeFileSync(target, profile);
  fs.writeFileSync(source, yaml.stringify({'llm-pi-ai': {providers: {qiniu: {models}}}}));
  const old = process.env.DSH_YAML_MODULE;
  process.env.DSH_YAML_MODULE = require.resolve(process.env.DSH_YAML_MODULE || path.join(os.homedir(), '.dsh/profiles/desktop/node_modules/yaml'));
  try {
    assert.equal(main([source, '--check', target]), 1);
    assert.equal(fs.readFileSync(target, 'utf8'), profile);
    assert.equal(main([source, '--apply', target]), 0);
    assert.equal(main([source, '--check', target]), 0);
    assert.equal(fs.readFileSync(target + '.qiniu-sync.bak', 'utf8'), profile);
  } finally {
    if (old === undefined) delete process.env.DSH_YAML_MODULE; else process.env.DSH_YAML_MODULE = old;
    fs.rmSync(root, {recursive: true, force: true});
  }
});
