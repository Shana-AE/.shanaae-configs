#!/usr/bin/env node
/**
 * Extract Gmail session auth from a Chrome DevTools Protocol target.
 * Outputs:
 *   - Netscape cookie jar  -> <out-cookies> (default ./cookies.txt)
 *   - Gmail "ik" session key -> printed to stdout (and saved to <out-ik> if given)
 *
 * Usage:
 *   node gmail_cdp_auth.js <page-webSocketDebuggerUrl> [out-cookies] [out-ik]
 *
 * Resolve the page WS URL first:
 *   curl -s http://127.0.0.1:9222/json | jq -r '.[]|select(.type=="page" and (.url|test("mail.google")))|.webSocketDebuggerUrl'
 *
 * The "ik" key is captured by enabling Network, reloading, and scanning request
 * URLs for "ik=...". It is stable for the session and required for Gmail
 * attachment download URLs.
 */
const WS_URL = process.argv[2];
const OUT_COOKIES = process.argv[3] || './cookies.txt';
const OUT_IK = process.argv[4] || '';
if (!WS_URL) { console.error('Usage: node gmail_cdp_auth.js <pageWSUrl> [out-cookies] [out-ik]'); process.exit(1); }

const fs = require('fs');
const ws = new WebSocket(WS_URL);
let id = 0; const pending = new Map(); let IK = '';
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const i = ++id; pending.set(i, { resolve, reject });
  ws.send(JSON.stringify({ id: i, method, params }));
});
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id).resolve(d.result || {}); pending.delete(d.id); }
  if (d.method === 'Network.requestWillBeSent') {
    const ik = d.params.request.url.match(/[?&]ik=([a-zA-Z0-9_]+)/);
    if (ik && !IK) { IK = ik[1]; console.error('FOUND ik=' + IK); }
  }
};
ws.onerror = (e) => { console.error('WS error:', e.message); process.exit(1); };

ws.onopen = async () => {
  await send('Network.enable');
  await send('Page.enable');
  await send('Page.reload', {});
  await new Promise(r => setTimeout(r, 6000));
  // cookies
  const c = await send('Network.getAllCookies');
  const jar = (c.cookies || [])
    .filter(x => /(^|\.)google\.com$/.test(x.domain.replace(/^\./, '')))
    .map(x => `${x.domain}\tTRUE\t${x.path}\t${x.secure ? 'TRUE' : 'FALSE'}\t${x.expires}\t${x.name}\t${x.value}`)
    .join('\n');
  fs.writeFileSync(OUT_COOKIES, '# Netscape HTTP Cookie File\n' + jar + '\n');
  if (OUT_IK && IK) fs.writeFileSync(OUT_IK, IK);
  console.log(JSON.stringify({ ik: IK, cookies: OUT_COOKIES, cookieCount: (c.cookies || []).length, hasSAPISID: /SAPISID/.test(jar) }));
  ws.close(); process.exit(0);
};
setTimeout(() => { if (!IK) console.error('WARN: ik not captured (page may need an interaction first)'); console.log(JSON.stringify({ ik: IK, cookies: OUT_COOKIES })); ws.close(); process.exit(IK ? 0 : 2); }, 14000);
