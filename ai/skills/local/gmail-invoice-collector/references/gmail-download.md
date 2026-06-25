# Downloading Invoices from Gmail

Invoices arrive in **two forms**. Detect which, then use the matching method.
**The single most important lesson: clicking Gmail's "Download attachment"
button under automation produces NO file** — it needs a real user gesture.
Do not waste time on click-to-download; use the network-level methods below.

## Form 1 — Gmail attachments (e.g. 盒马/Hema, 支付宝/Alipay)

Found by searching `has:attachment filename:pdf`. Threads (e.g. "(10)") hold
**one invoice per message** — download every message, not just the first.

### Reliable method: in-page CDP fetch (preferred)
A bare `curl` with the cookie jar often gets redirected (Gmail now wants
`SAPISIDHASH`). Fetching **from inside the live Gmail tab** carries the full
session automatically:

```js
// Runtime.evaluate on the mail.google.com page:
const url = "https://mail.google.com/mail/u/0/?ui=2&ik=" + IK + "&view=att&th=" + TH + "&attid=0.1&disp=safe&zw";
const r = await fetch(url, { credentials: "include" });
const b = await r.arrayBuffer();
btoa(String.fromCharCode(...new Uint8Array(b)));  // -> base64 PDF
```
Decode the base64 in Python/Node and write the `.pdf`. `attid=0.1` = the PDF
(skip `0.2` which is the `.xml`).

### Getting the message id `th`
`th` is a 16-hex message id (NOT the thread id `FMfcgzQ…`). Get it by:
- Expanding a thread's "show more" (`.adx`) controls, then reading each
  message's `download_url` data attribute from the DOM; or
- enabling CDP `Network`, opening the email, and reading `th=` from any
  `ik=…&th=…` request URL.

### Getting the `ik` session key
Run `scripts/gmail_cdp_auth.js` (enables Network, reloads, captures `ik=…` from
request URLs). `ik` is stable for the whole session.

## Form 2 — Download links in the email body (e.g. 京东/JD)

NOT attachments. Search without the attachment filter:
`after:YYYY/M/D before:YYYY/M/D 京东`. Open the email and read the 发票 download
link from the body — it is usually a **public presigned CDN URL**
(`storage.jd.com/...`, `jdcloud-oss.com/...`) reachable directly with `curl`,
**no login needed**. A single "批量选择的电子发票…共计N张" email often bundles
many invoices into one zip — start there; individual per-order emails are
usually duplicates of the batch.

```bash
# extract the link, then:
curl -sL -x http://127.0.0.1:7897 "<presigned-url>" -o batch.zip
unzip -o batch.zip -d /staging        # may contain PDFs + XMLs; keep only .pdf
```

Capture the exact URL via CDP `Network` when the link is clicked, or read it
from the email HTML via `Runtime.evaluate` (find `<a>` relating to 发票下载).

## Proxy
If a proxy is needed to reach Google/JD (e.g. behind the GFW), pass
`-x http://127.0.0.1:7897` to curl, and launch the browser with
`--proxy-server`.

## Verification
After every download, confirm it is a real invoice:
```bash
file <pdf>                        # -> "PDF document"
pdftotext -layout <pdf> - | head  # contains Chinese invoice text
```
Then use `scripts/invoice_extract.py` to read invoice number / buyer / amount.
