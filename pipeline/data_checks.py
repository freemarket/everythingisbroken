"""Checks that guard the published figures, rerun from the data at any time.

Three checks, each written to a CSV in data/hospital-ceo-pay/:

1. check_shared_officers.csv. One system split across rows. Two system rows are linked when filings in them name
   at least two of the same current officers in Form 990 Part VII (officer box ticked, not marked former, title not
   a clinical one). Linked rows form clusters. A cluster is not necessarily an error (a management company or a
   shared board officer can link separate systems); it is the list to read before joining anything.

2. check_name_splits.csv. One chief executive counted as two rows. Rows are grouped when their chief executives'
   names agree on first and last name once credentials, middle initials and order are ignored, or when two rows
   report the identical CEO pay figure. Each group needs a resolution: joined, kept separate by an override (the
   reason is copied from rollup_overrides.csv), or a reviewer's note.

3. check_charity_elsewhere.csv. Charity care reported on another line. Line 7a (charity care at cost) can be small
   because a hospital booked free care under line 7c (other means-tested programs) or 7g (subsidized health
   services). Listed: every member filing of a headline row, and every member filing of a system over $100 million
   whose line 7a is under 0.5 percent of expenses while lines 7c and 7g together exceed it. With --fetch, the
   script reads each filing's Schedule H narratives on ProPublica and copies every passage about charity care or
   financial assistance into the file; a reviewer reads them and records a finding for each filing.

Usage:  python3 pipeline/data_checks.py           # offline: recompute the lists, keep earlier resolutions and findings
        python3 pipeline/data_checks.py --fetch   # also fetch narratives for filings that have none yet
The build (build_site.py) recomputes the lists and stops if a saved file is out of date or a row lacks a resolution.
Standard library only.
"""
import csv, gzip, html, os, re, sys, tempfile, time, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'hospital-ceo-pay')
CACHE = os.path.join(tempfile.gettempdir(), 'eib_filing_cache')
FILES = {'officers': 'check_shared_officers.csv', 'names': 'check_name_splits.csv', 'charity': 'check_charity_elsewhere.csv'}
LINES = {'sch_h_7a_financial_assistance_at_cost_net': 'a', 'sch_h_7c_other_means_tested_net': 'c',
         'sch_h_7g_subsidized_health_services_net': 'g', 'total_expenses': 'exp'}
CREDENTIALS = set('MD DO PHD RN BSN MSN DNP FACHE LFACHE MBA MHA MPH MPA JD CPA FACP FACS FAAP FHFMA CHFP DHA DBA MS MA BS '
                  'EDD PE PA NP CRNA FACC FAAFP SPHR CHC CPHQ FABC PHARMD RPH DMD DDS ESQ MSHA FAHA LCSW MSW DR MR MRS '
                  'JR SR II III IV FACMPE CPHIMS CHCIO CEO CFO COO'.split())
CLINICAL = re.compile(r'PHYSICIAN|SURGEON|\bNURSE\b|\bRN\b|CRNA|\bNP\b|HOSPITALIST|ANESTHES|RADIOLOG|PATHOLOG|PSYCHIATR|'
                      r'CARDIOLOG|ONCOLOG|NEUROLOG|ORTHOPED|PEDIATRICIAN|INTENSIVIST|THERAPIST|PHARMACIST', re.I)

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def name_tokens(name):
    toks = [t for t in re.sub(r'[^A-Z ]', ' ', (name or '').upper()).split() if t not in CREDENTIALS and len(t) > 1]
    return toks

def load():
    F = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'filers_latest.csv')))}
    S = list(csv.DictReader(open(os.path.join(DATA, 'systems_rollup.csv'))))
    by_oid = {r['object_id']: e for e, r in F.items()}
    people = defaultdict(dict); lines = defaultdict(dict)
    with gzip.open(os.path.join(DATA, 'hospital_data.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r['status'] != 'active' or not r['retrieval_method'].startswith('IRS bulk'): continue
            m = re.search(r'ObjectId (\d+)', r['source_doc'])
            if not m or m.group(1) not in by_oid: continue
            e = by_oid[m.group(1)]
            if r['metric'].startswith('compensation') and r['person']:
                flags = {x.strip() for x in r['notes'].split('|')[0].split(',')}
                p = people[e].setdefault(r['person'], {'title': r['person_title'], 'flags': flags, 'pay': 0.0})
                p['pay'] += f(r['value']) or 0
            elif r['metric'] in LINES:
                lines[e][LINES[r['metric']]] = f(r['value']) or 0.0
    return F, S, people, lines

def ranked(s): return s['publishable'] == 'yes' and (f(s['ceo_comp_total']) or 0) > 0

def shared_officers(F, S, people):
    row_of = {e: s['lead_ein'] for s in S for e in s['member_eins'].split(';')}
    holders = defaultdict(set)   # officer name -> rows
    for e, ps in people.items():
        if e not in row_of: continue
        for name, p in ps.items():
            if 'officer' in p['flags'] and 'former' not in p['flags'] and not CLINICAL.search(p['title'] or ''):
                toks = name_tokens(name)
                if len(toks) >= 2: holders[toks[0] + ' ' + toks[-1]].add(row_of[e])
    pair = defaultdict(set)
    for name, rows in holders.items():
        rows = sorted(rows)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)): pair[(rows[i], rows[j])].add(name)
    links = {k: v for k, v in pair.items() if len(v) >= 2}
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in links: parent[find(a)] = find(b)
    clusters = defaultdict(set)
    for a, b in links: clusters[find(a)].update((a, b))
    sysd = {s['lead_ein']: s for s in S}
    out = []
    for n, rows in enumerate(sorted(clusters.values(), key=lambda c: (-len(c), sorted(c))), 1):
        for r in sorted(rows):
            names = sorted({nm for (a, b), v in links.items() if r in (a, b) for nm in v})
            out.append({'cluster': n, 'lead_ein': r, 'system': sysd[r]['lead_filer'], 'ranked': 'yes' if ranked(sysd[r]) else 'no',
                        'rows_in_cluster': len(rows), 'shared_officers': '; '.join(names[:8])})
    return out

def name_splits(S, previous):
    rows = [s for s in S if s['ceo_name'] and (f(s['ceo_comp_total']) or 0) > 0]
    groups = defaultdict(set)
    for s in rows:
        toks = name_tokens(s['ceo_name'])
        if len(toks) >= 2: groups[('same name', ' '.join(sorted((toks[0], toks[-1]))))].add(s['lead_ein'])
        groups[('same pay', f"{round(f(s['ceo_comp_total']))}")].add(s['lead_ein'])
    splits = defaultdict(list)
    for o in csv.DictReader(open(os.path.join(DATA, 'rollup_overrides.csv'))):
        if o['action'] == 'split': splits[o['ein']].append(o['reason'])
    sysd = {s['lead_ein']: s for s in S}
    out = []
    for (signal, k), leads in sorted(groups.items()):
        if len(leads) < 2: continue
        gid = f"{signal}: " + ' + '.join(sorted(leads))
        auto = '; '.join(r for l in sorted(leads) for e in sysd[l]['member_eins'].split(';') for r in splits.get(e, []))
        for l in sorted(leads):
            s = sysd[l]
            out.append({'group': gid, 'signal': signal, 'lead_ein': l, 'system': s['lead_filer'], 'ranked': 'yes' if ranked(s) else 'no',
                        'ceo_name': s['ceo_name'], 'ceo_title': s['ceo_title'], 'ceo_pay': s['ceo_comp_total'],
                        'resolution': previous.get(gid) or (f'Kept separate by rollup_overrides.csv: {auto}' if auto else '')})
    return out

def charity_candidates(F, S, lines):
    hl_all = [s for s in S if ranked(s) and (f(s['total_revenue']) or 0) >= 1e8 and f(s['charity_care_net'])]
    headline = {s['lead_ein'] for s in hl_all if (f(s['ceo_pay_pct_of_charity_care']) or 0) > 100}
    out = []
    for s in hl_all:
        for e in s['member_eins'].split(';'):
            if e not in F: continue
            v = lines.get(e, {}); a, c, g, x = v.get('a', 0), v.get('c', 0), v.get('g', 0), v.get('exp', 0)
            low = x > 0 and a / x * 100 < 0.5 and c + g > a
            if s['lead_ein'] in headline or low:
                out.append({'lead_ein': s['lead_ein'], 'system': s['lead_filer'], 'headline_row': 'yes' if s['lead_ein'] in headline else 'no',
                            'ein': e, 'filer': F[e]['name'], 'object_id': F[e]['object_id'], 'line_7a': round(a), 'line_7c': round(c),
                            'line_7g': round(g), 'expenses': round(x), 'line_7a_pct_of_expenses': round(a / x * 100, 3) if x else '',
                            'why_listed': ' and '.join(w for w, t in [('headline row', s['lead_ein'] in headline), ('7a small next to 7c and 7g', low)] if t)})
    return out

def narratives(oid):
    """Every Schedule H narrative passage that mentions charity care or financial assistance, from ProPublica's rendering."""
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, f'{oid}_IRS990ScheduleH.html')
    if not os.path.exists(fn):
        for attempt in range(4):
            try:
                with urllib.request.urlopen(f'https://projects.propublica.org/nonprofits/full_text/{oid}/IRS990ScheduleH', timeout=60) as r: body = r.read()
                if len(body) > 1000: open(fn, 'wb').write(body); break
            except Exception: pass
            time.sleep(2 * (attempt + 1))
        else: return None
        time.sleep(0.5)
    raw = open(fn, 'rb').read()
    h = (__import__('gzip').decompress(raw) if raw[:2] == b'\x1f\x8b' else raw).decode('utf-8', 'replace')
    refs = dict(re.findall(r'SupplementalInformationDetail\[(\d+)\]/FormAndLineReferenceDesc\[1\]">(.*?)</span>', h, re.S))
    texts = re.findall(r'SupplementalInformationDetail\[(\d+)\]/ExplanationTxt\[1\]">(.*?)</span>', h, re.S)
    keep = []
    for n, t in texts:
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t))).strip()
        ref = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', refs.get(n, '')))).strip()
        if re.search(r'charity|financial assistance|free care|uncompensated', t, re.I):
            keep.append(f'[{ref}] {t}')
    return ' || '.join(keep)

def read_previous(name, key, col):
    p = os.path.join(DATA, FILES[name])
    if not os.path.exists(p): return {}
    return {k: r[col] for r in csv.DictReader(open(p)) for k in [key(r)] if r.get(col)}

def write(name, rows, fields):
    with open(os.path.join(DATA, FILES[name]), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)

def compute(prev_names=None, prev_findings=None, prev_text=None):
    F, S, people, lines = load()
    officers = shared_officers(F, S, people)
    names = name_splits(S, prev_names or {})
    charity = charity_candidates(F, S, lines)
    for r in charity:
        r['narrative_excerpts'] = (prev_text or {}).get(r['object_id'], '')
        r['finding'] = (prev_findings or {}).get(r['object_id'], '')
    return officers, names, charity

def main():
    prev_names = read_previous('names', lambda r: r['group'], 'resolution')
    prev_findings = read_previous('charity', lambda r: r['object_id'], 'finding')
    prev_text = read_previous('charity', lambda r: r['object_id'], 'narrative_excerpts')
    officers, names, charity = compute(prev_names, prev_findings, prev_text)
    if '--fetch' in sys.argv:
        for i, r in enumerate(charity):
            if not r['narrative_excerpts']:
                t = narratives(r['object_id'])
                r['narrative_excerpts'] = t if t else ('(no narrative mentions charity care)' if t == '' else '(could not fetch)')
            if i % 25 == 0: print('narratives', i, len(charity), flush=True)
    write('officers', officers, ['cluster', 'lead_ein', 'system', 'ranked', 'rows_in_cluster', 'shared_officers'])
    write('names', names, ['group', 'signal', 'lead_ein', 'system', 'ranked', 'ceo_name', 'ceo_title', 'ceo_pay', 'resolution'])
    write('charity', charity, ['lead_ein', 'system', 'headline_row', 'ein', 'filer', 'object_id', 'line_7a', 'line_7c', 'line_7g', 'expenses',
                               'line_7a_pct_of_expenses', 'why_listed', 'narrative_excerpts', 'finding'])
    n_clusters = len({r['cluster'] for r in officers})
    groups = {r['group'] for r in names}; open_groups = {r['group'] for r in names if not r['resolution']}
    print(f'shared officers: {n_clusters} clusters, {len(officers)} rows')
    print(f'name splits: {len(groups)} groups, {len(open_groups)} without a resolution')
    print(f"charity elsewhere: {len(charity)} filings, {sum(1 for r in charity if not r['finding'])} without a finding")

if __name__ == '__main__':
    main()
