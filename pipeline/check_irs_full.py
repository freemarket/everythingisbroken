"""Rebuild the whole master from the IRS files and compare it with the published one, filing by filing.

Run fetch_all.sh first (about 7 GB of downloads; it keeps only the hospital returns, about 1 GB). Then
    python3 -I pipeline/check_irs_full.py <repo> <irs folder written by fetch_all.sh>
For every return the IRS files hold with a Schedule H, and for the parent returns kept in xml_nonH/, this runs
parse_xml.py and load_all.py's row builder, exactly as the original load did, and compares the rows with the
master's rows for the same object ID (metric, value, person, form line). It reports:
  - returns with a Schedule H that are not in the master, and master filings that are not in the IRS files
  - filings whose rebuilt figures differ from the master, with examples
and writes data/hospital-ceo-pay/irs_rebuild_check_<date>.csv, one line per filing. Exit status 1 if any filing
is missing or differs. Standard library only.
"""
import csv, datetime, gzip, os, re, sys
from collections import Counter, defaultdict

repo, irs = sys.argv[1:3]
sys.path.insert(0, os.path.join(repo, 'pipeline'))
import parse_xml as P
import load_all as L
DATA = os.path.join(repo, 'data', 'hospital-ceo-pay')

def key(r):
    v = r['value']
    try: v = round(float(v), 4)
    except (TypeError, ValueError): v = str(v)
    return (r['metric'], v, r.get('person') or '', r.get('source_location') or '')

master = defaultdict(list)
with gzip.open(os.path.join(DATA, 'hospital_data.csv.gz'), 'rt') as fh:
    for r in csv.DictReader(fh):
        if not r['retrieval_method'].startswith('IRS bulk'): continue
        m = re.search(r'ObjectId (\d+)', r['source_doc'])
        if m: master[m.group(1)].append(r)

files = {}
for sub in ('xml', 'xml_nonH'):
    d = os.path.join(irs, sub)
    for f in os.listdir(d):
        if f.endswith('_public.xml'): files[f[:-len('_public.xml')]] = (sub, os.path.join(d, f))
print(f'IRS files kept by fetch_all.sh: {sum(1 for s, _ in files.values() if s == "xml"):,} with Schedule H, '
      f'{sum(1 for s, _ in files.values() if s == "xml_nonH"):,} parent returns; master filings: {len(master):,}')

out, bad = [], 0
not_in_master = []
for i, (oid, (sub, path)) in enumerate(sorted(files.items())):
    d = P.parse_file(path)
    if sub == 'xml' and 'sch_h' not in d:
        out.append({'object_id': oid, 'folder': sub, 'in_master': '', 'result': 'no Schedule H parsed', 'rows_rebuilt': '', 'rows_master': '', 'example': ''}); bad += 1; continue
    if oid not in master:
        not_in_master.append(oid)
        out.append({'object_id': oid, 'folder': sub, 'in_master': 'no', 'result': 'not in master', 'rows_rebuilt': '', 'rows_master': '', 'example': d.get('name', '')}); bad += 1; continue
    new = Counter(key(r) for r in L.rows_for(d)); old = Counter(key(r) for r in master[oid])
    same = new == old
    ex = '' if same else f'rebuilt only: {sorted(new - old)[:2]}; master only: {sorted(old - new)[:2]}'
    out.append({'object_id': oid, 'folder': sub, 'in_master': 'yes', 'result': 'identical' if same else 'DIFFERS',
                'rows_rebuilt': sum(new.values()), 'rows_master': sum(old.values()), 'example': ex})
    bad += not same
    if i % 500 == 0: print(i, flush=True)
missing = sorted(set(master) - set(files))
for oid in missing:
    out.append({'object_id': oid, 'folder': '', 'in_master': 'yes', 'result': 'not in the IRS files', 'rows_rebuilt': '', 'rows_master': len(master[oid]), 'example': ''})
bad += len(missing)

path = os.path.join(DATA, f'irs_rebuild_check_{datetime.date.today().isoformat()}.csv')
with open(path, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
c = Counter(r['result'] for r in out)
print('results: ' + ', '.join(f'{k} {v:,}' for k, v in c.most_common()))
for r in out:
    if r['result'] not in ('identical',): print('  ', r['object_id'], r['result'], r['example'][:300])
print(f'wrote {os.path.relpath(path, repo)}')
sys.exit(1 if bad else 0)
