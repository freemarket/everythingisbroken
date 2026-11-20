"""Check every chief executive's name shown on the site against the other places the same filing names that person.

Form 990 Part VII is the source of each name (and of the pay). A name typed surname-first ("GREGORY PHD AUDREY") or run
together ("ClarkTimothy") is shown wrong unless display_names.csv corrects it. This reads each CEO filing's IRS XML and
collects the person's name as it appears in the fields of the same return that are typed separately from Part VII: the
principal officer (Form 990 item F) and the officer who signed the return (ReturnHeader BusinessOfficerGrp). Schedule J
Part II is listed too, but most software copies it from Part VII, so it is not counted as a second source. Each row:
  confirmed          item F or the signer gives the same name tokens in the same order as the site shows
  order differs      item F or the signer gives the same tokens in another order, or the return lists every Part VII
                     name surname-first (part_vii_order) and the site shows this one as filed
  spelling differs   item F or the signer gives a name with the same tokens but one spelled differently
  consistent         no separately typed field names this person; the name passed the pattern tests below
  unconfirmed: review  no separately typed field names this person, and a pattern test failed: across every Part VII
                     name in the master, the shown order is less likely than the reverse (first token mostly a surname,
                     last token mostly a given name), a token is run together, or title words are left in the name
A reviewer records a resolution for every flagged row; build_site.py stops if a shown name is missing from the file,
has changed since, or is flagged without a resolution.

Usage: python3 -I pipeline/check_ceo_names.py <repo> <irs folder from fetch_all.sh>
Writes data/hospital-ceo-pay/check_ceo_names.csv, keeping earlier resolutions. Standard library only.
"""
import csv, gzip, math, os, re, sys
import xml.etree.ElementTree as ET
from collections import Counter

repo, irs = sys.argv[1:3]
sys.path.insert(0, os.path.join(repo, 'pipeline'))
from names import person, display_names
DATA = os.path.join(repo, 'data', 'hospital-ceo-pay')
OUT = os.path.join(DATA, 'check_ceo_names.csv')
NS = '{http://www.irs.gov/efile}'
FLAGGED = ('order differs', 'spelling differs', 'unconfirmed: review', 'filing not found')
TITLE_WORDS = set('PRESIDENT CEO CHIEF EXECUTIVE OFFICER BOARD SECRETARY MEMBER TRUSTEE DIRECTOR INTERIM CHAIR CHAIRMAN '
                  'TREASURER VICE EVP SVP VP CFO COO FORMER ADMINISTRATOR'.split())
CREDS = set('MD DO PHD RN BSN MSN DNP FACHE LFACHE MBA MHA MPH MPA JD CPA FACP FACS FAAP FHFMA CHFP DHA DBA MS MA BS EDD '
            'PE PA NP CRNA FACC FAAFP DR MR MRS JR SR II III IV ESQ MSHA'.split())

def toks(name):
    """Name tokens in order: letters only, upper case, without credentials, titles or single-letter initials."""
    return [t for t in re.sub(r"[^A-Za-z' ]", ' ', name or '').upper().replace("'", '').split()
            if len(t) > 1 and t not in CREDS and t not in TITLE_WORDS]

def lev(a, b):
    """Edit distance between two tokens."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]

def text(el):
    return ' '.join((el.text or '').split()) if el is not None else ''

def names_on_return(path):
    """(field, name, title) for every name on the return other than Part VII, then the Part VII names."""
    root = ET.parse(path).getroot()
    part7 = [text(g.find(NS + 'PersonNm')) for g in root.iter(NS + 'Form990PartVIISectionAGrp') if g.find(NS + 'PersonNm') is not None]
    out = []
    for g in root.iter(NS + 'BusinessOfficerGrp'):
        out.append(('signed the return', text(g.find(NS + 'PersonNm')), text(g.find(NS + 'PersonTitleTxt'))))
    for e in root.iter(NS + 'PrincipalOfficerNm'):
        out.append(('principal officer (item F)', text(e), ''))
    for sj in root.iter(NS + 'IRS990ScheduleJ'):
        for g in sj.iter(NS + 'RltdOrgOfficerTrstKeyEmplGrp'):
            out.append(('Schedule J Part II', text(g.find(NS + 'PersonNm')), text(g.find(NS + 'TitleTxt'))))
    return [x for x in out if x[1]], part7

def main():
    S = list(csv.DictReader(open(os.path.join(DATA, 'systems_rollup.csv'))))
    F = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'filers_latest.csv')))}
    shown = display_names(DATA)
    prev = {r['ceo_name_as_filed'] + '|' + r['object_id']: r['resolution'] for r in csv.DictReader(open(OUT))} if os.path.exists(OUT) else {}

    # How often each token opens or closes a Part VII name in the master, as evidence of which is the given name
    first, last = Counter(), Counter()
    with gzip.open(os.path.join(DATA, 'hospital_data.csv.gz'), 'rt') as fh:
        seen = set()
        for r in csv.DictReader(fh):
            p = r['person']
            if p and p not in seen:
                seen.add(p); t = toks(p)
                if len(t) >= 2: first[t[0]] += 1; last[t[-1]] += 1

    def score(tk):
        return math.log((last[tk[0]] + 1) / (first[tk[0]] + 1)) + math.log((first[tk[-1]] + 1) / (last[tk[-1]] + 1))

    rows = []
    for s in S:
        if not s['ceo_name'] or not (float(s['ceo_comp_total'] or 0) > 0): continue
        cf = next((F[e] for e in s['member_eins'].split(';') if e in F and F[e]['name'] == s['ceo_filer'] and F[e]['ceo_name'] == s['ceo_name']), None)
        if cf is None: continue
        filed = s['ceo_name']; disp = shown.get(filed) or person(filed)
        path = os.path.join(irs, 'xml', f"{cf['object_id']}_public.xml")
        if not os.path.exists(path): path = os.path.join(irs, 'xml_nonH', f"{cf['object_id']}_public.xml")
        others, part7 = names_on_return(path) if os.path.exists(path) else (None, [])
        # Does this return list its people surname-first? Score each Part VII name: positive when its first token is
        # more often a surname and its last token more often a given name, across every Part VII name in the master.
        sc = [score(toks(n)) for n in part7 if len(toks(n)) >= 2]
        decisive = [x for x in sc if abs(x) > math.log(4)]
        order = ('surname first' if len(decisive) >= 5 and sum(x > 0 for x in decisive) >= 0.6 * len(decisive) else
                 'given name first' if len(decisive) >= 5 and sum(x < 0 for x in decisive) >= 0.6 * len(decisive) else 'unclear')
        d = toks(disp)
        status, evidence = '', ''
        if others is None:
            status = 'filing not found'
        else:
            indep = [o for o in others if o[0] != 'Schedule J Part II']
            def pairs(o):
                """Compare tokens in order: equal, nickname (one a prefix of the other), or spelled differently."""
                b = toks(o[1])
                if len(b) != len(d) or len(d) < 2: return None
                kinds = ['eq' if x == y else 'nick' if min(len(x), len(y)) >= 3 and (x.startswith(y) or y.startswith(x))
                         else 'spell' if lev(x, y) <= 2 and min(len(x), len(y)) >= 4 else 'other' for x, y in zip(d, b)]
                return kinds
            same = [o for o in indep if toks(o[1]) == d or (pairs(o) and set(pairs(o)) <= {'eq', 'nick'} and 'eq' in pairs(o))]
            moved = [o for o in indep if sorted(toks(o[1])) == sorted(d) and toks(o[1]) != d and len(d) >= 2]
            near = [o for o in indep if pairs(o) and 'spell' in pairs(o) and 'other' not in pairs(o) and ('eq' in pairs(o) or 'nick' in pairs(o))]
            if order == 'surname first' and toks(filed) == d:
                # item F and the signer are often typed the same way on such a return, so they cannot confirm the order
                status = 'order differs'; evidence = f'the return lists its Part VII names surname-first ({sum(x > 0 for x in decisive)} of {len(decisive)} decisive names), e.g. ' + '; '.join(part7[:3])
            elif same:
                status = 'confirmed'; evidence = f'{same[0][0]}: {same[0][1]}'
            elif moved:
                status = 'order differs'; evidence = '; '.join(f'{o[0]}: {o[1]}' for o in moved[:2])
            elif near:
                status = 'spelling differs'; evidence = '; '.join(f'{o[0]}: {o[1]}' for o in near[:2])
            else:
                why = []
                if len(d) >= 2 and order != 'given name first' and score(d) > math.log(2):
                    why.append(f'{d[0]} opens {first[d[0]]} Part VII names and closes {last[d[0]]}; {d[-1]} opens {first[d[-1]]} and closes {last[d[-1]]}')
                if re.search(r'[a-z][A-Z]', re.sub(r'\b(PhD|DrPH|PharmD|EdD|DNP)\b', '', filed)) and not re.search(r"\b(Mc|Mac|De|Di|Da|La|Le|Van|Vander|Von|O')[A-Z]", filed):
                    why.append('capital letter inside a word (run together?)')
                if any(t in TITLE_WORDS for t in re.sub(r'[^A-Za-z ]', ' ', disp).upper().split()):
                    why.append('title words in the shown name')
                if len(d) < 2: why.append('fewer than two name tokens')
                status = 'unconfirmed: review' if why else 'consistent'
                evidence = '; '.join(why) if why else '; '.join(f'{o[0]}: {o[1]}' for o in others[:3])
        rows.append({'lead_ein': s['lead_ein'], 'system': s['lead_filer'], 'ranked': 'yes' if s['publishable'] == 'yes' else 'no',
                     'object_id': cf['object_id'], 'part_vii_order': order, 'ceo_name_as_filed': filed, 'name_shown': disp,
                     'from_display_names_csv': 'yes' if filed in shown else 'no', 'status': status, 'evidence': evidence,
                     'resolution': prev.get(filed + '|' + cf['object_id'], '')})
    with open(OUT, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    c = Counter(r['status'] for r in rows)
    print(f'{len(rows)} names checked: ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    need = [r for r in rows if r['status'] in FLAGGED and not r['resolution']]
    print(f'{len(need)} need a resolution')

if __name__ == '__main__':
    main()
