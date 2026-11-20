"""How a chief executive's name as filed in Form 990 Part VII is shown on the site. Shared by build_site.py and
check_ceo_names.py so both use the same rule. display_names.csv overrides it for names filed surname-first or run
together; each override carries its evidence."""
import csv, os, re

def cap(w):
    # str.title() capitalizes after an apostrophe ("Children'S", "St Luke'S"). Capitalize each letter run; after an
    # apostrophe only when more than one letter follows (O'Halla, O'Connor), never for a possessive s.
    # A Mc name capitalizes the letter after Mc (McLaren, McCoy, McCook) when a vowel follows; acronyms such as MCHS keep
    # their single capital (Nov 20, 2026).
    w = re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", lambda m: m.group(0)[0].upper() + re.sub(r"'([a-z]{2,})", lambda n: "'" + n.group(1).title(), m.group(0)[1:].lower()), w)
    return re.sub(r"\bMc([a-z])(?=[a-z]*[aeiouy])", lambda m: 'Mc' + m.group(1).upper(), w)
CREDS_DISP = {'PHD':'PhD','MD':'MD','DO':'DO','JD':'JD','RN':'RN','MBA':'MBA','MHA':'MHA','MPH':'MPH','FACHE':'FACHE','III':'III','II':'II','IV':'IV','DHA':'DHA','MSN':'MSN','MS':'MS'}
def person(s):
    s = s or ''
    # Title text the filing ran into the name field: 'MARGARET TROYTHROUGH AUG 2024', 'BRIAN T CANFIELD TERMED 42025',
    # 'MICHAEL B LAIGN UNTIL 1024', 'Travis Olsen CFO thru'. Cut at the date word, then drop a trailing title.
    s = re.split(r'(?i)THROUGH\b|\bTHRU\b|\bUNTIL\b|\bTERMED\b|\bSTART\b', s)[0]
    s = re.sub(r'(\s+\d+)+\s*$', '', s)                                  # 'BRENDAN CARR 1'
    s = re.sub(r'\s+(PRESIDENTCEO|UPM|CFO|CEO)$', '', s.strip(), flags=re.I)
    s = re.sub(r'^(MR|MRS|MS|DR)\.?\s+', '', s, flags=re.I)              # 'MR KEVIN BROWN', 'DR PATRICK BATTEY'
    out=[]
    for w in s.split():
        u=w.upper().strip('.,')
        if u in CREDS_DISP: out.append(CREDS_DISP[u])
        elif len(w)==1 or (len(w)==2 and w.endswith('.')): out.append(w.upper())
        elif w != w.upper() and w != w.lower(): out.append(w)                 # filed in mixed case: VanderSteeg, McLarney
        else: out.append(cap(w))
    return ' '.join(out)

def display_names(data_dir):
    return {r['name_as_filed']: r['display_name'] for r in csv.DictReader(open(os.path.join(data_dir, 'display_names.csv')))}
