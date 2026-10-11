import test from 'node:test';
import assert from 'node:assert/strict';
import { wrapDiscovery, apply, CATALOG_BASE, isQiniuDiscovery } from './index.mjs';
const qiniu = { provider: 'qiniu', baseURL: 'https://api.qnaigc.com/v1', api: 'openai-completions', apiKey: 'test-placeholder' };

test('Qiniu uses Modelink and keeps the original draft, credential, and receiver', async () => {
  let call;
  const receiver = {};
  const original = async function(ns, req, signal) { call = {ns, req, signal, receiver:this}; return [{id:'old'}, {id:'new'}]; };
  const wrapped = wrapDiscovery(original, async rows => rows.filter(row => row.id === 'new'));
  assert.deepEqual(await wrapped.call(receiver, 'llm-pi-ai', qiniu), [{id:'new'}]);
  assert.equal(call.req.baseURL, CATALOG_BASE);
  assert.equal(call.req.apiKey, qiniu.apiKey);
  assert.equal(call.req.provider, undefined);
  assert.equal(call.receiver, receiver);
  assert.equal(qiniu.baseURL, 'https://api.qnaigc.com/v1');
});
test('other providers and unrecognized Qiniu endpoints are unchanged', async () => {
  for (const req of [{...qiniu,provider:'openai'}, {...qiniu,baseURL:'https://example.com/v1'}]) {
    let received;
    const wrapped=wrapDiscovery(async (ns,draft) => { received=draft; return ['unchanged']; }, () => assert.fail('must not filter'));
    assert.deepEqual(await wrapped('llm-pi-ai',req), ['unchanged']);
    assert.equal(received,req);
  }
  assert.equal(isQiniuDiscovery('other',qiniu),false);
});
test('network failures use the legacy Qiniu catalog; authentication errors do not', async () => {
  let calls=[];
  const wrapped=wrapDiscovery(async (ns,req) => { calls.push(req.baseURL); if(calls.length===1) throw new Error('could not reach '+req.baseURL); return [{id:'new'}]; },async rows=>rows);
  await wrapped('llm-pi-ai',qiniu);
  assert.deepEqual(calls,[CATALOG_BASE,'https://openai.sufy.com/v1']);
  calls=[];
  await assert.rejects(wrapDiscovery(async () => { calls.push(1); throw new Error('answered 401; check the API key'); })('llm-pi-ai',qiniu), /401/);
  assert.equal(calls.length,1);
});
test('abort does not fall back or filter; empty catalogs are refused', async () => {
  const controller=new AbortController();controller.abort();let count=0;
  await assert.rejects(wrapDiscovery(async (ns,req,signal)=>{count++; signal.throwIfAborted();},()=>assert.fail())('llm-pi-ai',qiniu,controller.signal));
  assert.equal(count,1);
  await assert.rejects(wrapDiscovery(async()=>[],()=>assert.fail())('llm-pi-ai',qiniu), /empty/);
});
test('installation reaches context-bound service facades and disposal restores the method', () => {
  const original=async()=>[];const holder={discoverModels:original};const facade=Object.create(holder);let dispose;
  apply({llm:facade,effect:fn=>{dispose=fn();},logger:{info(){}}});
  assert.notEqual(holder.discoverModels,original);
  dispose();assert.equal(holder.discoverModels,original);
});

test('anonymous discovery draft bypasses bundled catalog with stored credential', async () => {
  let received;
  const wrapped = wrapDiscovery(async (ns, req) => { received = req; return req.provider ? [{id:'deepseek-v3'}] : [{id:'gpt-6.1-sol'}]; }, async rows => rows, async () => 'stored-test-key');
  assert.deepEqual(await wrapped('llm-pi-ai', {...qiniu, apiKey:undefined}), [{id:'gpt-6.1-sol'}]);
  assert.equal(received.apiKey, 'stored-test-key');
  assert.equal(received.provider, undefined);
});
