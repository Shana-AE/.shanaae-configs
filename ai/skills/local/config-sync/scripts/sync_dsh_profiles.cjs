#!/usr/bin/env node
// Update Qiniu models in live Cordis profiles without evaluating !!js tags.
const fs = require('node:fs');
const path = require('node:path');
const { isDeepStrictEqual } = require('node:util');

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
    const desired = patchProfileText(current, models, yaml);
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
module.exports = { patchProfileText, main };
if (require.main === module) {
  try { process.exitCode = main(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
