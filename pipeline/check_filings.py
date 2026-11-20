"""Check headline rows against the hospitals' own filings, from public sources only.

For each row of ceo_pay_exceeds_charity_care.csv (or the ranks given), this reads the filings on ProPublica
Nonprofit Explorer, which renders the IRS e-file XML with each value tagged by its XML path:
  - CEO pay: Form 990 Part VII columns D, E and F for the chief executive, from the filing in filing_url
  - charity care: Schedule H Part I line 7a column (e) from every member filing of the system
    (the object IDs are in filers_latest.csv), summed
and writes one line per row to data/hospital-ceo-pay/filing_check_<date>.csv with the filed values next to the
published ones. Exit status 1 if any figure differs.

Usage: python3 pipeline/check_filings.py [first_rank last_rank]
Standard library only. Pages are cached in the system temp folder so a rerun does not refetch them.
"""
import csv, datetime, gzip, html, os, re, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'hospital-ceo-pay')
CACHE = os.path.join(tempfile.gettempdir(), 'eib_filing_cache'); os.makedirs(CACHE, exist_ok=True)

def page(oid, form):
    """ProPublica's rendering of one form of one filing. /full_text redirects to a signed S3 URL; the body may be gzip."""
    fn = os.path.join(CACHE, f'{oid}_{form}.html')
    if not os.path.exists(fn):
        for attempt in range(4):
            try:
                with urllib.request.urlopen(f'https://projects.propublica.org/nonprofits/full_text/{oid}/{form}', timeout=60) as r:
                    body = r.read()
                if len(body) > 1000:
                    open(fn, 'wb').write(body); break
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        else:
            raise SystemExit(f'could not fetch {form} for filing {oid}')
        time.sleep(0.5)
    raw = open(fn, 'rb').read()
    return (gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw).decode('utf-8', 'replace')

def amount(s):
    s = s.strip().replace(',', '').replace('$', '')
    try: return int(float(s))
    except ValueError: return None

def part_vii(h):
    rows = {}
    for n, field, v in re.findall(r'Form990PartVIISectionAGrp\[(\d+)\]/(\w+)\[1\]">([^<]*)', h):
        rows.setdefault(int(n), {})[field] = html.unescape(v.strip())
    return [dict(name=r.get('PersonNm', ''), title=r.get('TitleTxt', ''),
                 d=amount(r.get('ReportableCompFromOrgAmt', '0')) or 0, e=amount(r.get('ReportableCompFromRltdOrgAmt', '0')) or 0,
                 f=amount(r.get('OtherCompensationAmt', '0')) or 0) for _, r in sorted(rows.items())]

def line_7a(h):
    m = re.search(r'FinancialAssistanceAtCostTyp\[1\]/NetCommunityBenefitExpnsAmt\[1\]">([^<]*)', h)
    return amount(m.group(1)) if m else 0   # a blank line 7a is zero

def year_end(h):
    m = re.search(r'TaxPeriodEndDt(?:\[1\])?">([^<]*)', h)
    return m.group(1).strip() if m else ''

def main():
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (1, 10 ** 6)
    headline = [r for r in csv.DictReader(open(os.path.join(DATA, 'ceo_pay_exceeds_charity_care.csv'))) if lo <= int(r['rank_by_ceo_pay']) <= hi]
    systems = {r['lead_ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'systems_rollup.csv')))}
    filers = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'filers_latest.csv')))}
    out, bad = [], 0
    for r in headline:
        s = systems[r['lead_ein']]
        oid = re.search(r'/(\d{15,})/full', r['filing_url']).group(1)
        form = page(oid, 'IRS990')
        people = part_vii(form)
        want = s['ceo_name'].upper()
        ceo = next((p for p in people if p['name'].upper() == want), None) or \
              next((p for p in people if want.split()[-1] in p['name'].upper() and want.split()[0] in p['name'].upper()), None)
        filed_pay = ceo['d'] + ceo['e'] + ceo['f'] if ceo else None
        members, cc = [], 0
        for ein in s['member_eins'].split(';'):
            if ein not in filers: continue
            v = line_7a(page(filers[ein]['object_id'], 'IRS990ScheduleH'))
            members.append(f"{ein}:{filers[ein]['object_id']}:{v}"); cc += v
        pay_ok = filed_pay == int(r['ceo_pay_usd']); cc_ok = cc == int(r['charity_care_usd'])
        bad += (not pay_ok) + (not cc_ok)
        out.append({'rank': r['rank_by_ceo_pay'], 'system': r['system'], 'lead_ein': r['lead_ein'], 'filing_object_id': oid,
                    'fiscal_year_end_published': r['fiscal_year_end'], 'fiscal_year_end_filed': year_end(form),
                    'ceo_published': r['chief_executive'], 'ceo_filed_name': ceo['name'] if ceo else 'NOT FOUND', 'ceo_filed_title': ceo['title'] if ceo else '',
                    'pay_published': r['ceo_pay_usd'], 'pay_col_d': ceo['d'] if ceo else '', 'pay_col_e': ceo['e'] if ceo else '', 'pay_col_f': ceo['f'] if ceo else '',
                    'pay_filed': filed_pay if filed_pay is not None else '', 'pay_match': 'yes' if pay_ok else 'NO',
                    'charity_care_published': r['charity_care_usd'], 'charity_care_filed': cc, 'charity_care_members': ';'.join(members),
                    'charity_care_match': 'yes' if cc_ok else 'NO'})
        print(r['rank_by_ceo_pay'], r['system'], 'ok' if pay_ok and cc_ok else 'MISMATCH', flush=True)
    path = os.path.join(DATA, f'filing_check_{datetime.date.today().isoformat()}.csv')
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f'{len(out)} rows checked, {bad} figures differ; wrote {os.path.relpath(path, os.path.join(HERE, ".."))}')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
