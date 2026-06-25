---
name: gmail-invoice-collector
description: Download, filter, deduplicate, total, and package electronic invoices (电子发票/数电票) from Gmail into a monthly zip. Use when the user asks to collect/export/reimburse company invoices from email — e.g. "download May-June invoices from Gmail", "package this month's 发票 into a zip", "sum invoice amounts for 北京绮心科技有限公司", or any task combining Gmail invoice download + company filtering + amount totaling + zip packaging. Covers Gmail attachments AND link-based invoices (e.g. 京东/JD), Chinese e-invoice PDF parsing, and dedup by invoice number.
---

# Gmail Invoice Collector

Download invoices from Gmail, keep only a target company's, total the amounts,
and package into a `桃子-<total>元.zip` (matches the existing `YYYYMM` folder +
`桃子-<amount>元.zip` convention).

## Prerequisites
- A visible browser exposing Chrome DevTools Protocol (CDP) the user can log
  into Gmail in. See [references/browser-setup.md](references/browser-setup.md).
- `pdftotext` (poppler-utils) for parsing invoices. `zip` for packaging.
- Node.js (global `WebSocket`) for the auth script.

## Workflow

### 1. Launch a visible browser + log in
Launch a real browser with `--remote-debugging-port=9222` (see
[references/browser-setup.md](references/browser-setup.md) for per-system
commands and the **agent-browser headless caveat**). The user logs into Gmail
and completes 2FA themselves — **never handle passwords/2FA**. Watch for the
"Show password" checkbox being ticked (warn the user; recommend password
rotation). Confirm login: `agent-browser --cdp 9222 get url` shows
`mail.google.com/mail/.../#inbox`.

### 2. Extract Gmail session auth (once)
```bash
WS=$(curl -s http://127.0.0.1:9222/json | jq -r '.[]|select(.type=="page" and (.url|test("mail.google")))|.webSocketDebuggerUrl')
node scripts/gmail_cdp_auth.js "$WS" /tmp/cookies.txt /tmp/ik.txt
```
Captures the `ik` session key + cookie jar. Both are needed to fetch
attachments.

### 3. Enumerate invoice emails
Search the Gmail search box (`aria-label "Search mail"`). Run both an
attachment search and a link search — invoices may be attachments OR body links:
- `after:YYYY/M/D before:YYYY/M/D has:attachment filename:pdf 发票`
- `after:YYYY/M/D before:YYYY/M/D <seller>` (e.g. `京东` — links, not attachments)

Note THREADS (e.g. "(10)") = one invoice per message inside. Scroll the result
list to load all rows.

### 4. Download
See [references/gmail-download.md](references/gmail-download.md) for details.
- **Attachments** (盒马, 支付宝): UI click-downloads FAIL under automation.
  Fetch from inside the live Gmail tab via CDP `Runtime.evaluate`+`fetch()`
  (base64 → decode), using `?ui=2&ik=<IK>&view=att&th=<TH>&attid=0.1&disp=safe&zw`.
- **Links** (京东): read the 发票 download URL from the email body and `curl` it
  directly (usually a public presigned CDN URL, no login). A single "批量…
  共计N张" email often bundles everything — start there; per-order emails are
  usually duplicates of the batch.
Save all PDFs to a staging dir (e.g. `/tmp/invoice-raw`).

### 5. Extract, dedup, filter, total
```bash
python3 scripts/invoice_extract.py \
  --buyer "北京绮心科技有限公司" --from 2026-05-01 --to 2026-06-30 \
  --copy-to "/path/to/invoice/YYYYMM" /tmp/invoice-raw "/path/to/invoice/YYYYMM"
```
Deduplicates by **invoice number** (发票号码), not amount. Emits a manifest and
the total. (Personal invoices under another buyer, e.g. 陶佳旺, are auto-excluded.)

### 6. Package
Match the existing convention `桃子-<total>元.zip` inside the `YYYYMM` folder:
```bash
cd "/path/to/invoice/YYYYMM" && zip -j "桃子-<TOTAL>元.zip" *.pdf
```
(Use the total printed by the script. Two-decimal, no thousands separator.)

## Key gotchas
- **UI clicks don't download** Gmail attachments (no user gesture). Use CDP
  in-page `fetch()` instead — bare curl+cookies often redirects (needs
  SAPISIDHASH).
- **Dedup by invoice number**, never by amount.
- Ask the user about **borderline dates** (e.g. one day outside the window) and
  any **manually-placed invoices** (e.g. 中油) before finalizing the total.
- After finishing, close the automation browser: `pkill -f remote-debugging-port=9222`.
