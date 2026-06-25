#!/usr/bin/env python3
"""
Extract, deduplicate, filter, and sum Chinese e-invoices (电子发票/数电票) PDFs.

Reads invoice number, buyer (购买方/购方/买 名称), 价税合计 amount, and 开票日期
from each PDF via pdftotext. Deduplicates by invoice number (NOT amount — two
distinct invoices can share an amount by coincidence). Keeps only invoices whose
buyer contains a keyword, optionally within a date window. Sums amounts and can
copy the keep-set into a destination folder, printing a manifest.

Usage examples:
  # Just report
  python3 invoice_extract.py --buyer 北京绮心科技有限公司 /path/to/pdfs
  # Report + copy keeps to dest + date window
  python3 invoice_extract.py --buyer 北京绮心科技有限公司 --from 2026-05-01 --to 2026-06-30 \
      --copy-to /dest/dir /dir1 /dir2
Requires: pdftotext (poppler-utils). Pure-Python stdlib only.
"""
import argparse, subprocess, re, sys, glob, os, shutil, json
from decimal import Decimal

def extract(pdf):
    try:
        txt = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return {'error': str(e)}
    r = {'inv_no': '', 'buyer': '', 'amount': '', 'date': ''}
    m = re.search(r'发票号码[：:]\s*(\d{15,25})', txt)
    if m: r['inv_no'] = m.group(1)
    # buyer line: "购/买 名称: <co>" — stop at 2+ spaces or 售/销
    m = (re.search(r'(?:购|买)\s*名\s*称[：:]\s*(\S.*?)\s{2,}', txt)
         or re.search(r'(?:购|买)\s*名\s*称[：:]\s*(\S.*?)\s*(?:售|销)', txt)
         or re.search(r'(?:购|买)\s*名\s*称[：:]\s*(.+)', txt))
    if m: r['buyer'] = m.group(1).strip()[:50]
    # 价税合计 numeric after 小写 (handles ¥ ￥ ´ ` prefixes)
    m = re.search(r'[（(]小写[）)]\s*[¥￥´`′]*\s*([\d,]+\.\d{2})', txt)
    if m: r['amount'] = m.group(1).replace(',', '')
    m = re.search(r'开票日期[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日', txt)
    if m: r['date'] = '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
    return r

def main():
    ap = argparse.ArgumentParser(description='Extract/filter/sum Chinese e-invoice PDFs')
    ap.add_argument('dirs', nargs='+', help='PDF directories (or files)')
    ap.add_argument('--buyer', default='', help='buyer keyword to KEEP (e.g. 北京绮心科技有限公司)')
    ap.add_argument('--from', dest='frm', default='', help='start date YYYY-MM-DD (inclusive)')
    ap.add_argument('--to', default='', help='end date YYYY-MM-DD (inclusive)')
    ap.add_argument('--copy-to', default='', help='copy KEEP files into this dir')
    ap.add_argument('--json', action='store_true', help='emit JSON manifest')
    args = ap.parse_args()

    files = []
    for d in args.dirs:
        if os.path.isdir(d): files += glob.glob(os.path.join(d, '*.pdf'))
        elif d.lower().endswith('.pdf'): files.append(d)
    files = sorted(set(files))

    rows, keep, seen = [], [], set()
    for f in files:
        r = extract(f); r['file'] = os.path.basename(f); r['path'] = f; rows.append(r)
        if r.get('error') or not r['inv_no'] or not r['amount']:
            r['status'] = 'SKIP'; continue
        is_buyer = (args.buyer in r['buyer']) if args.buyer else True
        in_window = True
        if args.frm and r['date'] and r['date'] < args.frm: in_window = False
        if args.to and r['date'] and r['date'] > args.to: in_window = False
        if not is_buyer: r['status'] = 'EXCLUDE_BUYER'
        elif r['inv_no'] in seen: r['status'] = 'DUP'
        elif not in_window: r['status'] = 'OUT_OF_WINDOW'
        else:
            seen.add(r['inv_no']); r['status'] = 'KEEP'; keep.append(r)

    total = sum((Decimal(r['amount']) for r in keep), Decimal('0'))

    if args.copy_to:
        os.makedirs(args.copy_to, exist_ok=True)
        for r in keep:
            shutil.copy2(r['path'], os.path.join(args.copy_to, r['file']))

    if args.json:
        print(json.dumps({'keep': keep, 'total': str(total), 'all': rows}, ensure_ascii=False, indent=2))
        return
    print('FILE|STATUS|INV_NO|DATE|AMOUNT|BUYER')
    for r in rows:
        print(f"{r['file']}|{r.get('status','-')}|{r['inv_no']}|{r['date']}|{r['amount']}|{r['buyer']}")
    print(f'\nKEEP: {len(keep)}  TOTAL: {total}')

if __name__ == '__main__':
    main()
