#!/usr/bin/env node
// Update Qiniu models in live Cordis profiles without evaluating !!js tags.
const fs = require('node:fs');
const path = require('node:path');
const { isDeepStrictEqual } = require('node:util');
const { pathToFileURL } = require('node:url');

function loadYaml(profile) {
  return require(process.env.DSH_YAML_MODULE || require.resolve('yaml', { paths: [path.dirname(profile), __dirname] }));
}
function qiniuEntry(doc, yaml) {
  if (!yaml.isSeq(doc.contents)) throw new Error('Cordis profile must be a YAML sequence');
  return doc.contents.items.find(entry => yaml.isMap(entry) && entry.get('id') === 'llm-pi-ai');
}
function patchProfileText(text, models, yaml) {
  const doc = yaml.parseDocument(text);
  if (doc.errors.length) throw new Error('Invalid YAML in Cordis profile');
  const entry = qiniuEntry(doc, yaml);
  const node = entry?.getIn(['config', 'providers', 'qiniu', 'models'], true);
  if (!node) return text; // This profile does not manage Qiniu.
  if (!yaml.isSeq(node) || !node.range) throw new Error('Qiniu models must be a YAML sequence');
  if (isDeepStrictEqual(node.toJSON(), models)) return text;
  const start = node.range[0], end = node.range[2];
  const column = start - (text.lastIndexOf('\n', start) + 1);
  const rendered = node.flow ? JSON.stringify(models) + (text[end - 1] === '\n' ? '\n' : '')
    : yaml.stringify(models, { indent: 2, lineWidth: 0 }).trimEnd()
      .split('\n').map((line, index) => index ? ' '.repeat(column) + line : line).join('\n') + '\n';
  const result = text.slice(0, start) + rendered + text.slice(end);
  const after = yaml.parseDocument(result);
  if (after.errors.length) throw new Error('Profile update produced invalid YAML');
  const actual = qiniuEntry(after, yaml)?.getIn(['config', 'providers', 'qiniu', 'models'], true)?.toJSON();
  if (!isDeepStrictEqual(actual, models)) throw new Error('Profile model verification failed');
  // Compare everything else, including credentials, custom tags, and plugins.
  entry.deleteIn(['config', 'providers', 'qiniu', 'models']);
  qiniuEntry(after, yaml).deleteIn(['config', 'providers', 'qiniu', 'models']);
  if (!isDeepStrictEqual(doc.toJS(), after.toJS())) throw new Error('Profile update changed unrelated settings');
  return result;
}
function ensureDiscoveryPlugin(text, pluginPath, yaml) {
  const doc = yaml.parseDocument(text);
  if (doc.errors.length) throw new Error('Invalid YAML in Cordis profile');
  if (!qiniuEntry(doc, yaml)?.getIn(['config', 'providers', 'qiniu', 'models'], true)) return text;
  const id = 'qiniu-model-discovery';
  const url = pathToFileURL(pluginPath).href;
  const apiKeyEnv = qiniuEntry(doc, yaml).getIn(['config', 'providers', 'qiniu', 'apiKeyEnv']);
  if (apiKeyEnv !== undefined && typeof apiKeyEnv !== 'string') throw new Error('Qiniu apiKeyEnv must be a credential reference');
  const config = {apiKeyEnv: apiKeyEnv || 'QINIU_AI_API_KEY'};
  for (const patch of doc.contents.items) {
    const insert = yaml.isMap(patch) ? patch.get('insert', true) : undefined;
    const entry = yaml.isSeq(insert) ? insert.items.find(row => yaml.isMap(row) && row.get('id') === id) : undefined;
    if (!entry) continue;
    if (entry.get('name') === url && entry.getIn(['config', 'apiKeyEnv']) === config.apiKeyEnv) return text;
    entry.set('name', url);
    entry.setIn(['config', 'apiKeyEnv'], config.apiKeyEnv);
    const replacement = yaml.stringify([patch.toJSON()], {lineWidth:0}).trimEnd();
    return text.slice(0, patch.range[0] - 2) + replacement + '\n' + text.slice(patch.range[2]);
  }
  // A profile is a PATCH list: a bare id only overrides a pre-existing row.
  // Migrate the earlier bare row to an insert so the module actually mounts.
  const legacy = doc.contents.items.find(row => yaml.isMap(row) && row.get('id') === id);
  const entry = {...(legacy?.toJSON() || {}), id, name:url, config:{...(legacy?.get('config', true)?.toJSON() || {}), ...config}};
  const replacement = '- ' + JSON.stringify({insert:[entry]}) + '\n';
  if (legacy) return text.slice(0, legacy.range[0] - 2) + replacement + text.slice(legacy.range[2]);
  return text.trimEnd() + '\n' + replacement;
}
function main(argv) {
  const [source, mode, ...profiles] = argv;
  const check = mode === '--check';
  let stale = false;
  for (const profile of profiles) {
    const yaml = loadYaml(profile);
    const sourceDoc = yaml.parseDocument(fs.readFileSync(source, 'utf8'));
    if (sourceDoc.errors.length) throw new Error('Invalid generated dsh settings');
    const models = sourceDoc.getIn(['llm-pi-ai', 'providers', 'qiniu', 'models'], true)?.toJSON();
    if (!Array.isArray(models) || !models.length) throw new Error('Empty Qiniu source catalog; refusing profile update');
    const current = fs.readFileSync(profile, 'utf8');
    let desired = patchProfileText(current, models, yaml);
    const plugin = path.join(path.dirname(source), 'plugins/qiniu-model-discovery/index.mjs');
    if (fs.existsSync(plugin)) desired = ensureDiscoveryPlugin(desired, plugin, yaml);
    if (current === desired) {
      console.log(`ok: ${profile} Qiniu models in sync`);
    } else if (check) {
      console.log(`STALE: ${profile} Qiniu models`);
      stale = true;
    } else {
      const backup = profile + '.qiniu-sync.bak';
      if (!fs.existsSync(backup)) {
        fs.copyFileSync(profile, backup, fs.constants.COPYFILE_EXCL);
        fs.chmodSync(backup, 0o600);
      }
      fs.writeFileSync(profile, desired);
      console.log(`wrote ${profile}: ${models.length} Qiniu models`);
    }
  }
  return stale ? 1 : 0;
}
module.exports = { patchProfileText, ensureDiscoveryPlugin, main };
if (require.main === module) {
  try { process.exitCode = main(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
