"""Rebuild one IRS bulk batch with this repo's parser and compare every figure with the published master.

Download the year's index and one batch from https://apps.irs.gov/pub/epostcard/990/xml/<year>/ into an empty folder,
unzip the batch into <folder>/x with the system unzip (the IRS zips use Deflate64, which Python cannot read), then run
    python3 -I pipeline/check_irs_batch.py <repo> <folder> <batch name, e.g. 2025_TEOS_XML_01A>
It reports how many returns mention Schedule H, how many contain one, whether each is in the master, and whether
the figures load_all.py would write today equal the master's, filing by filing. Standard library only."""
import csv, gzip, os, re, sys
from collections import Counter, defaultdict
repo, dl, batch = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, 'pipeline'))
import parse_xml as P
import load_all as L

# 1. The IRS index: total rows, and this batch's returns
idx_rows = 0; in_batch = {}
with open(os.path.join(dl, f'index_{batch[:4]}.csv'), newline='', encoding='utf-8', errors='replace') as fh:
    for r in csv.DictReader(fh):
        idx_rows += 1
        if r.get('XML_BATCH_ID') == batch: in_batch[r['OBJECT_ID']] = r['RETURN_TYPE']
print(f'index_{batch[:4]}.csv: {idx_rows:,} rows; {len(in_batch):,} in {batch} ({Counter(in_batch.values()).most_common(4)})')

# 2. The batch files: which mention Schedule H, and which the parser reads as Schedule H
files = {}
for root, _, fs in os.walk(os.path.join(dl, 'x')):
    for f in fs:
        if f.endswith('_public.xml'): files[f.replace('_public.xml', '')] = os.path.join(root, f)
grep_h = {o for o, p in files.items() if b'IRS990ScheduleH' in open(p, 'rb').read()}
parsed = {}
for o in sorted(grep_h):
    d = P.parse_file(files[o])
    if 'sch_h' in d: parsed[o] = d
print(f'batch files: {len(files):,}; mention IRS990ScheduleH: {len(grep_h)}; parsed with a Schedule H: {len(parsed)}')
nonh = grep_h - set(parsed)
if nonh:
    sample = sorted(nonh)[:3]
    print('mention but no Schedule H parsed, e.g.:', [(o, in_batch.get(o)) for o in sample])
    print('  where the string appears:', [re.findall(rb'.{0,60}IRS990ScheduleH.{0,40}', open(files[o], 'rb').read())[:1] for o in sample[:2]])

# 3. The master's rows for these filings
master = defaultdict(list); master_oids_this_release = set()
with gzip.open(os.path.join(repo, 'data/hospital-ceo-pay/hospital_data.csv.gz'), 'rt') as fh:
    for r in csv.DictReader(fh):
        if not r['retrieval_method'].startswith('IRS bulk'): continue
        m = re.search(r'ObjectId (\d+)', r['source_doc'])
        if not m: continue
        master_oids_this_release.add(m.group(1))
        if m.group(1) in parsed: master[m.group(1)].append(r)
in_master = set(parsed) & set(master)
print(f'parsed Schedule H filings in the master: {len(in_master)} of {len(parsed)}; missing from master: {sorted(set(parsed) - set(master))[:10]}')

# 4. Figure by figure: what load_all would write now versus what the master holds
def key(r):
    v = r['value'] if isinstance(r, dict) and 'row_id' in r else r['value']
    try: v = round(float(v), 4)
    except (TypeError, ValueError): v = str(v)
    return (r['metric'], v, r.get('person') or '', r.get('source_location') or '')
same = diff = 0; examples = []
for o in sorted(in_master):
    new = Counter(key(r) for r in L.rows_for(parsed[o]))
    old = Counter(key(r) for r in master[o])
    if new == old: same += 1
    else:
        diff += 1
        if len(examples) < 4: examples.append((o, sorted((new - old).items())[:3], sorted((old - new).items())[:3]))
print(f'filings whose rebuilt figures equal the master exactly: {same}; differ: {diff}')
for e in examples: print('  ', e)
