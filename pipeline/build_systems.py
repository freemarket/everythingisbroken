"""Build the analysis table from hospital_data.csv (append-only source of truth).
- One row per filer (EIN), latest fiscal year.
- CEO identified by rule (documented), with a confidence flag.
- Multi-EIN systems rolled up by shared CEO name (same person reported on several filings).
Writes: filers_latest.csv, systems_rollup.csv, ceo_unresolved.csv
"""
import csv, re
from collections import defaultdict

SRC = '../hospital_data.csv'
rows = [r for r in csv.DictReader(open(SRC)) if r['status'] == 'active' and r['retrieval_method'].startswith('IRS bulk')]

# group by (ein, fye)
filings = defaultdict(dict); people = defaultdict(list); meta = {}
for r in rows:
    k = (r['ein'], r['fiscal_year_end'])
    if r['metric'].startswith('compensation_'):
        people[k].append(r); continue
    filings[k][r['metric']] = r['value']
    meta[k] = (r['entity_name'], r['source_doc'])

def num(x):
    try: return float(x)
    except: return None

# latest filing per EIN
latest = {}
for (ein, fye) in filings:
    if ein not in latest or fye > latest[ein]: latest[ein] = fye

CEO_RE = re.compile(r'\bCEO\b|CHIEF EXEC|CHIEF EXECUTIVE', re.I)
PRES_RE = re.compile(r'\bPRESIDENT\b', re.I)
ADMIN_RE = re.compile(r'ADMINISTRATOR|EXECUTIVE DIRECTOR', re.I)
EXCL_RE = re.compile(r'VICE PRES|\bVP\b|ASSISTANT|ASSOC|REGIONAL|DIVISION|FOUNDATION|AUXILIARY|MEDICAL STAFF|COACH|SEE SCHEDULE', re.I)

import parse_xml as _P, os as _os
_so_cache = {}
def _so_titles(object_id):
    if object_id in _so_cache: return _so_cache[object_id]
    path = f'xml/{object_id}_public.xml'; res = {}
    if _os.path.exists(path):
        try:
            d = _P.parse_file(path)
            for p in d.get('people', []):
                if p.get('sched_o_titles'): res[p['person']] = p['sched_o_titles']
        except Exception: pass
    _so_cache[object_id] = res; return res

def pick_ceo(plist, object_id=None):
    so = _so_titles(object_id) if object_id else {}
    # aggregate per person: org + related + other
    agg = defaultdict(lambda: {'title': '', 'org': 0, 'rel': 0, 'oth': 0, 'flags': ''})
    for r in plist:
        p = agg[r['person']]
        p['title'] = r['person_title'] or p['title']; p['flags'] = r['notes'] or p['flags']
        v = num(r['value']) or 0
        # A person listed more than once in Part VII (one line per role) usually repeats the same
        # totals; summing would double-count. Take the maximum single entry per column.
        if r['metric'] == 'compensation_reportable': p['org'] = max(p['org'], v)
        elif r['metric'] == 'compensation_related_org': p['rel'] = max(p['rel'], v)
        elif r['metric'] == 'compensation_other': p['oth'] = max(p['oth'], v)
    cands = []
    for name, p in agg.items():
        t = p['title'] or ''
        if re.search(r'SCHEDULE O', t, re.I) and name in so:
            t = so[name]; p['title'] = t + ' [from Sch O]'
        if 'former' in p['flags'] or re.search(r'\bFORMER\b|EMERIT', t, re.I): continue
        if EXCL_RE.search(t): continue
        p['departed'] = bool(re.search(r'TERMED|TERM\.|THRU \d|THROUGH \d|\(TO \d|UNTIL \d', t, re.I))
        tot = p['org'] + p['rel'] + p['oth']
        if CEO_RE.search(t): cands.append((0, -tot, name, p))
        elif PRES_RE.search(t): cands.append((1, -tot, name, p))
        elif ADMIN_RE.search(t): cands.append((2, -tot, name, p))
    top = max(agg.items(), key=lambda kv: kv[1]['org'] + kv[1]['rel'] + kv[1]['oth'], default=(None, None))
    if not cands:
        return None, 'unresolved', top
    cands.sort()
    # A CEO whose title carries an end date (termed, through <date>) is kept only if no current
    # (undated) CEO-tier candidate exists; the departing CEO stands for a year with no successor listed.
    top_tier = cands[0][0]
    current = [c for c in cands if c[0] == top_tier and not c[3].get('departed')]
    if current: cands = current + [c for c in cands if c not in current]
    tier, _, name, p = cands[0]
    conf = {0: 'ceo_title', 1: 'president_title', 2: 'administrator_title'}[tier]
    # if several CEO-titled people, note it
    if sum(1 for c in cands if c[0] == tier) > 1: conf += '_multiple'
    return (name, p), conf, top

# Manual overrides (ein,fye) -> row
OVR = {}
import os as _os2
if _os2.path.exists('ceo_overrides.csv'):
    for o in csv.DictReader(open('ceo_overrides.csv')):
        OVR[(o['ein'], o['fye'])] = o
out = []; unresolved = []
for ein, fye in latest.items():
    k = (ein, fye); f = filings[k]; name, doc = meta[k]
    ceo, conf, top = pick_ceo(people[k], doc.split('ObjectId ')[-1].strip())
    ovr = OVR.get((ein, fye))
    if ovr:
        if ovr['ceo_name_override']:
            # find that person in the filing's people
            agg = {}
            for r_ in people[k]:
                agg.setdefault(r_['person'], {'title': r_['person_title'], 'org': 0, 'rel': 0, 'oth': 0})
                v = num(r_['value']) or 0
                if r_['metric'] == 'compensation_reportable': agg[r_['person']]['org'] = max(agg[r_['person']]['org'], v)
                elif r_['metric'] == 'compensation_related_org': agg[r_['person']]['rel'] = max(agg[r_['person']]['rel'], v)
                elif r_['metric'] == 'compensation_other': agg[r_['person']]['oth'] = max(agg[r_['person']]['oth'], v)
            nm = ovr['ceo_name_override']
            match = next((p for p in agg if re.sub(r'[^A-Z]','',p.upper()) == re.sub(r'[^A-Z]','',nm.upper())), None)
            if match: ceo = (match, agg[match]); conf = 'manual_override'
            else: ceo = None; conf = 'override_name_not_found'
        else:
            ceo = None; conf = 'manual_excluded'
    rec = {
        'ein': ein, 'name': name, 'fye': fye, 'object_id': doc.split('ObjectId ')[-1], 'group_return': f.get('group_return'),
        'city_state': f.get('filer_city_state'), 'total_revenue': num(f.get('total_revenue')), 'total_expenses': num(f.get('total_expenses')),
        'net_income': num(f.get('net_income_990')), 'net_assets': num(f.get('net_assets')), 'employees': num(f.get('employee_count')), 'over_100k': num(f.get('indiv_over_100k_cnt')),
        'charity_care_net': num(f.get('sch_h_7a_financial_assistance_at_cost_net')), 'charity_care_pct': num(f.get('sch_h_7a_financial_assistance_at_cost_pct_total_expense')),
        'medicaid_shortfall_net': num(f.get('sch_h_7b_medicaid_net')), 'total_cb_net': num(f.get('sch_h_7k_total_community_benefits_net')), 'total_cb_pct': num(f.get('sch_h_7k_total_community_benefits_pct_total_expense')),
        'bad_debt': num(f.get('sch_h_bad_debt')), 'medicare_shortfall': num(f.get('sch_h_medicare_shortfall')), 'fpg_free': num(f.get('sch_h_fpg_free_pct')), 'fpg_discount': num(f.get('sch_h_fpg_discount_pct')),
        'facility_count': num(f.get('sch_h_facility_count')), 'facilities': f.get('sch_h_facilities_list'),
        'ceo_name': ceo[0] if ceo else None, 'ceo_title': ceo[1]['title'] if ceo else None,
        'ceo_comp_org': ceo[1]['org'] if ceo else None, 'ceo_comp_related': ceo[1]['rel'] if ceo else None, 'ceo_comp_other': ceo[1]['oth'] if ceo else None,
        'ceo_comp_total': (ceo[1]['org'] + ceo[1]['rel'] + ceo[1]['oth']) if ceo else None, 'ceo_confidence': conf,
        'override_reason': ovr['reason'] if ovr else '',
        'top_paid_name': top[0], 'top_paid_title': top[1]['title'] if top[1] else None, 'top_paid_total': (top[1]['org'] + top[1]['rel'] + top[1]['oth']) if top[1] else None,
        'childrens_hospital': 'yes' if re.search(r"CHILDREN|PEDIATRIC|SHRINERS|ST JUDE", (name or '').upper()) else '',
        'zero_charity_care_flag': 'yes' if (num(f.get('sch_h_7a_financial_assistance_at_cost_net')) or 0) == 0 and (num(f.get('sch_h_7k_total_community_benefits_net')) or 0) > 0 else '',
    }
    out.append(rec)
    if conf == 'unresolved': unresolved.append(rec)

out.sort(key=lambda r: -(r['total_revenue'] or 0))
with open('filers_latest.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
with open('ceo_unresolved.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(unresolved)

# Roll-up: filers sharing the same CEO name (normalized) are one system
def norm(n): return re.sub(r'[^A-Z ]', '', (n or '').upper()).strip()
RO = {}
if _os2.path.exists('rollup_overrides.csv'):
    for o in csv.DictReader(open('rollup_overrides.csv')): RO[(o['ein'], o['fye'])] = o
groups = defaultdict(list)
for r in out:
    o = RO.get((r['ein'], r['fye']))
    if o and o['action'] == 'drop_duplicate': continue
    key = norm(r['ceo_name']) if r['ceo_name'] else 'EIN:' + r['ein']
    if o and o['action'] in ('split', 'merge', 'join', 'parent') and o['system_key_override']: key = o['system_key_override']
    groups[key].append(r)
# Generic rule: if a group contains a filer named '... GROUP RETURN' and another filer whose name is a prefix of it, drop the latter (contained in the group return)
for key, members in list(groups.items()):
    grp = [m for m in members if 'GROUP RETURN' in m['name'].upper() or ' GROUP' in m['name'].upper()[-7:]]
    if grp and len(members) > 1:
        keep = []
        for m in members:
            base = re.sub(r'\s*GROUP( RETURN)?\s*$', '', m['name'].upper()).strip()
            contained = any(g is not m and re.sub(r'\s*GROUP( RETURN)?\s*$', '', g['name'].upper()).strip() == base for g in grp)
            if contained and 'GROUP' not in m['name'].upper(): m['rollup_note'] = 'dropped: contained in group return'; continue
            keep.append(m)
        groups[key] = keep
systems = []
for key, members in groups.items():
    parents = [r for r in members if RO.get((r['ein'], r['fye']), {}).get('action') == 'parent']
    m0 = parents[0] if parents else max(members, key=lambda r: r['total_revenue'] or 0)
    m_rev = max(members, key=lambda r: r['total_revenue'] or 0)
    def s(field):
        v = [r[field] for r in members if r[field] is not None]; return sum(v) if v else None
    cc = s('charity_care_net'); ex = s('total_expenses')
    systems.append({
        'system_key': key, 'lead_filer': m_rev['name'], 'lead_ein': m_rev['ein'], 'state': (m_rev['city_state'] or '').split(',')[-1].strip()[:2], 'ceo_filer': m0['name'],
        'n_filers': len(members), 'member_eins': ';'.join(r['ein'] for r in members), 'member_names': ' | '.join(r['name'] for r in members),
        'total_revenue': s('total_revenue'), 'total_expenses': ex, 'net_assets': s('net_assets'), 'employees': s('employees'),
        'charity_care_net': cc, 'charity_care_pct_computed': (cc / ex * 100) if cc is not None and ex else None,
        'total_cb_net': s('total_cb_net'), 'bad_debt': s('bad_debt'), 'medicare_shortfall': s('medicare_shortfall'), 'facility_count': s('facility_count'),
        'ceo_name': m0['ceo_name'], 'ceo_title': m0['ceo_title'], 'ceo_comp_total': m0['ceo_comp_total'], 'ceo_confidence': m0['ceo_confidence'],
        'ceo_pay_pct_of_charity_care': (m0['ceo_comp_total'] / cc * 100) if m0['ceo_comp_total'] and cc else None,
        'childrens_hospital': 'yes' if all(r['childrens_hospital'] == 'yes' for r in members) else ('mixed' if any(r['childrens_hospital'] == 'yes' for r in members) else ''),
        'zero_charity_care_flag': 'yes' if any(r['zero_charity_care_flag'] == 'yes' for r in members) else '',
        'publishable': 'yes' if (m0['ceo_confidence'] in ('ceo_title','ceo_title_multiple','manual_override') and cc and cc > 0 and not any(r['zero_charity_care_flag']=='yes' for r in members)) else 'no',
    })
systems.sort(key=lambda r: -(r['total_revenue'] or 0))
with open('systems_rollup.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(systems[0].keys())); w.writeheader(); w.writerows(systems)

from collections import Counter
print(len(out), 'filers;', Counter(r['ceo_confidence'] for r in out))
print(len(systems), 'systems after CEO-name rollup;', sum(1 for s in systems if s['n_filers'] > 1), 'multi-filer systems')
