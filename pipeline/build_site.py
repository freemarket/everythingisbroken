"""Static site generator for Report No. 1, Nonprofit Hospital Executive Pay vs Charity Care.

Reads   data/hospital-ceo-pay/{systems_rollup,filers_latest}.csv and hospital_data.csv.gz
Writes  reports/hospital-ceo-pay/  (index, all, states, state/XX, system/<slug>, methodology, manual, data)
        reports/hospital-ceo-pay/summary.json
        index.html  (rewrites the blocks between <!-- gen:NAME --> and <!-- /gen:NAME --> markers
                     so the main page and the report are built from the same table)

Run from anywhere:  python3 pipeline/build_site.py
No dependencies beyond Python 3 and the `markdown` package (pip install markdown), used only for manual.html.
"""
import csv, os, re, json, html, gzip, hashlib, datetime, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'data', 'hospital-ceo-pay')
BASE = '/reports/hospital-ceo-pay'          # URL path of the report
OUT = os.path.join(REPO, BASE.strip('/'))
DATA_URL = '/data/hospital-ceo-pay'

REPORT_NO = 1
REPORT_TITLE = 'Nonprofit Hospital Executive Pay vs Charity Care'   # one variable; matches the main page
SERIES = 'Annual Report'
HEADLINE_MIN_REV = 1e8   # the headline count covers general hospital systems with revenue at or above this
PUBLISHER = 'Everything Is Broken'
SUBLINE = ''
SITE = 'https://everythingisbroken.org'
EDITION = '2026'
DATA_ASOF = '2026-10-21'        # date the IRS releases were pulled and the tables built
BUILD = datetime.date.today().isoformat()

STATES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'District of Columbia','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','PR':'Puerto Rico'}

def f(x):
    try: return float(x) if x not in ('', 'None', None) else None
    except: return None
def money(v, short=True):
    if v is None: return ''
    if v < 0: return '−' + money(-v, short)
    if short:
        if abs(v) >= 1e9: return f'${v/1e9:.1f}B'
        if abs(v) >= 1e6: return f'${v/1e6:.1f}M'
        return f'${v:,.0f}'
    return f'${v:,.0f}'
def pct(v, d=2): return '' if v is None else f'{v:.{d}f}%'
def slug(s): return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')[:80]
def titlecase(s):
    small = {'of','and','the','for','at','in','on','dba','inc','llc'}
    w = s.lower().split(); out=[]
    for i,x in enumerate(w):
        if x in ('inc','llc','md','phd','do','jd','rn','upmc','uc','ucsf','ut','uf','lsu','nyu','bjc','osf','ssm','chi','rwj','hca','ucla'): out.append(x.upper() if len(x)<=4 else x.title())
        elif x in small and i>0: out.append(x)
        else: out.append(x.title())
    return ' '.join(out)
def person(s):
    s = re.sub(r'\s+(PRESIDENTCEO|UPM)$', '', s or '', flags=re.I)
    out=[]
    for w in s.split():
        u=w.upper().strip('.,')
        if u in ('MD','PHD','DO','JD','RN','MBA','MHA','MPH','FACHE','III','II','IV','DHA','MSN','MS'): out.append({'PHD':'PhD','MD':'MD','DO':'DO','JD':'JD','RN':'RN','MBA':'MBA','MHA':'MHA','MPH':'MPH','FACHE':'FACHE','III':'III','II':'II','IV':'IV','DHA':'DHA','MSN':'MSN','MS':'MS'}[u])
        elif len(w)==1 or (len(w)==2 and w.endswith('.')): out.append(w.upper())
        else: out.append(w.title())
    return ' '.join(out)
E = html.escape
# Display names where the lead filer's legal name is not how the public knows the system. Keyed by lead EIN.
DISPLAY = {'36-2169147':'Advocate Health (Midwest)','13-3971298':'NYU Langone Health','13-3957095':'NewYork-Presbyterian','13-1740114':'Montefiore Health System','35-2528741':'Vanderbilt University Medical Center','39-0816848':'Mercyhealth','39-0910727':'ProHealth Care (Waukesha Memorial)','36-2256036':'Shirley Ryan AbilityLab','36-4113692':'RML Specialty Hospital','94-1105628':'Kaiser Permanente (Hospitals)','36-4724966':'Northwestern Medicine','11-2965586':'Northwell Health','38-1357020':'Henry Ford Health','20-8295721':'UPMC','94-1196203':'CommonSpirit Health (Dignity)','45-0233470':'Banner Health','52-1301088':'Bon Secours Mercy Health','36-2167060':'Endeavor Health','36-2174823':'Rush University System for Health','36-3488183':'UChicago Medicine','36-4015560':'Loyola Medicine','36-1509000':'Sinai Chicago (Mount Sinai)','36-2170133':'Holy Cross Hospital (Sinai Chicago)','36-2264414':'St. Bernard Hospital','35-0868085':'Parkview Health','01-0211501':'Northern Light Eastern Maine Medical Center','51-0216586':'Providence','11-2241326':'Northwell Health (Long Island Jewish)','38-3952644':'Mayo Clinic','23-1352685':'Penn Medicine (University of Pennsylvania)','61-1740292':'Corewell Health','91-2153073':'Cleveland Clinic'}
# Names the filing lists surname-first or run together. Keyed by the name exactly as filed.
CEO_DISPLAY = {'MIHALJEVIC MD TOMISLAV':'Tomislav Mihaljevic MD','BJC LIEKWEG RICHARD':'Richard Liekweg','FARRUGIA MD GIANRICO':'Gianrico Farrugia MD','MAHONEY KEVIN':'Kevin Mahoney','BerdanBarclay E':'Barclay E Berdan'}

# ---------- load ----------
S = list(csv.DictReader(open(os.path.join(DATA, 'systems_rollup.csv'))))
F = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'filers_latest.csv')))}
for s in S:
    s['rev'] = f(s['total_revenue']); s['exp'] = f(s['total_expenses']); s['cc'] = f(s['charity_care_net'])
    s['ccp'] = f(s['charity_care_pct_computed']); s['pay'] = f(s['ceo_comp_total']); s['ratio'] = f(s['ceo_pay_pct_of_charity_care'])
    s['cb'] = f(s['total_cb_net']); s['bad'] = f(s['bad_debt']); s['na'] = f(s['net_assets']); s['emp'] = f(s['employees'])
    _nm = re.sub(r'\s+(Inc|Corp|Corporation|Group Return|Group|Incorporated|Llc|Co)\.?$', '', titlecase(s['lead_filer']), flags=re.I)
    _nm = re.sub(r'\s*(-\s*)?(of the )?Hospital Sisters( of)?( the)? Third Order.*$', ' (HSHS)', _nm, flags=re.I)
    s['name'] = DISPLAY.get(s['lead_ein'], _nm); s['slug'] = slug(s['lead_filer'] + '-' + s['lead_ein'])
    s['ceo'] = CEO_DISPLAY.get(s['ceo_name']) or person(s['ceo_name']); s['pub'] = s['publishable'] == 'yes'; s['kids'] = s['childrens_hospital'] == 'yes'
    lead = F.get(s['lead_ein'], {}); s['oid'] = lead.get('object_id', ''); s['fye'] = lead.get('fye', '')
    s['members'] = [(e, F[e]) for e in s['member_eins'].split(';') if e in F]
ranked = sorted([s for s in S if s['pub'] and s['pay']], key=lambda s: -s['pay'])
for i, s in enumerate(ranked, 1): s['rank'] = i
big = [s for s in ranked if (s['rev'] or 0) >= 1e9 and not s['kids']]
MED_CC = st.median([s['ccp'] for s in big if s['ccp'] is not None]); MED_RATIO = st.median([s['ratio'] for s in big if s['ratio']])
UNDER1 = sum(1 for s in big if s['ccp'] is not None and s['ccp'] < 1) / len(big) * 100
OVER100 = [s for s in big if s['ratio'] and s['ratio'] >= 100]
N_FILINGS = 19245  # Schedule H XML filings read from the 2025 and 2026 IRS releases (Reproduction manual, section 5)
# headline group: general hospital systems with revenue over HEADLINE_MIN_REV, children's and specialty filers excluded
XCL = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'headline_exclusions.csv')))}
for s in S: s['xcl'] = XCL.get(s['lead_ein'])
hl_all = [s for s in ranked if (s['rev'] or 0) >= HEADLINE_MIN_REV and not s['kids'] and not s['xcl'] and s['cc']]
hl_over = sorted([s for s in hl_all if s['ratio'] and s['ratio'] > 100], key=lambda s: -s['pay'])
HL_PAY = sum(s['pay'] for s in hl_over); HL_CC = sum(s['cc'] for s in hl_over)
HEADLINE = f"{len(hl_over)} nonprofit hospital chief executives were paid more than their hospitals gave in charity care."
HEADLINE_SUB = f"Among {len(hl_all):,} general hospital systems with revenue over ${HEADLINE_MIN_REV/1e6:.0f} million, by the hospitals' own IRS filings. Together the {len(hl_over)} were paid {money(HL_PAY)}; their hospitals gave {money(HL_CC)} to patients who could not pay."

# other chief executives (co-CEO, former CEO, executive chair) listed in the same filings
_pp = defaultdict(lambda: defaultdict(lambda: {'org':0,'rel':0,'oth':0,'title':''}))
with gzip.open(os.path.join(DATA, 'hospital_data.csv.gz'), 'rt') as fh:
    for r in csv.DictReader(fh):
        if r['status'] != 'active' or not r['metric'].startswith('compensation_') or not r['retrieval_method'].startswith('IRS bulk'): continue
        if r['metric'] not in ('compensation_reportable','compensation_related_org','compensation_other'): continue
        fr = F.get(r['ein'])
        if not fr or fr['fye'] != r['fiscal_year_end']: continue
        k = {'compensation_reportable':'org','compensation_related_org':'rel','compensation_other':'oth'}[r['metric']]
        p = _pp[r['ein']][r['person']]; p[k] = max(p[k], f(r['value']) or 0); p['title'] = r['person_title'] or p['title']
CEO_TITLE = re.compile(r'\bCEO\b|CHIEF EXEC|EXECUTIVE CHAIR', re.I)
for s_ in S:
    seen = {}
    for e, _ in s_['members']:
        for name, p in _pp.get(e, {}).items():
            if name == s_['ceo_name']: continue
            if CEO_TITLE.search(p['title'] or '') and (p['org']+p['rel']+p['oth']) >= 1e6:
                tot = p['org']+p['rel']+p['oth']
                if name not in seen or tot > seen[name][0]: seen[name] = (tot, p['title'])
    s_['other_execs'] = sorted(((t, n, ti) for n, (t, ti) in seen.items()), reverse=True)[:4]

# ---------- css: the main page's look, without Tailwind ----------
CSS = """
:root{--bg:#f0ece1;--paper:#faf8f2;--surface:#f3efe4;--border:#d6cfc2;--ink:#111;--muted:#555;--red:#8b2626;--blue:#3b5d7a;
--serif:"Libre Baskerville",Georgia,"Times New Roman",serif;--mono:"Space Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:var(--ink)}
.sheet{max-width:1100px;margin:0 auto;background:var(--paper);padding:40px 32px;min-height:100vh}
@media(min-width:640px){.sheet{margin:32px auto;border:1px solid var(--border);box-shadow:0 1px 2px rgba(0,0,0,.05)}}
@media(max-width:640px){.sheet{padding:28px 16px}}
.mast{text-align:center;margin-bottom:28px}
.mast .seal{display:inline-block;margin-bottom:18px}
.mast .seal img{width:128px;height:128px;display:block;margin:0 auto}
.mast h1{font-size:2.6rem;letter-spacing:.1em;text-transform:uppercase;margin:0 0 14px;font-weight:700;line-height:1.1}
@media(max-width:640px){.mast h1{font-size:1.7rem}}
.rule-double{border-top:4px double var(--ink);margin-bottom:18px}
.rule-double-bottom{border-bottom:4px double var(--ink)}
.rule-single{border-bottom:1px solid var(--ink)}
.mast .sub{font-style:italic;font-size:1.25rem;margin:12px 0 22px;letter-spacing:.02em}
.mast nav.site{display:flex;flex-wrap:wrap;justify-content:center;gap:12px 36px;text-transform:uppercase;letter-spacing:.1em;font-size:.95rem;padding-bottom:16px;border-bottom:1px solid var(--ink)}
.mast nav.site a{text-decoration:none}
.mast nav.site a:hover{color:var(--muted)}
.mast nav.site a.on{font-weight:700;text-decoration:underline}
.band{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 24px;padding:12px 0;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.band .rep{color:var(--ink)}
.band nav{display:flex;flex-wrap:wrap;gap:6px 18px}
.band nav a{color:var(--muted);text-decoration:none}
.band nav a:hover,.band nav a.on{color:var(--ink);text-decoration:underline}
h1.title{font-size:2rem;line-height:1.2;margin:34px 0 8px;font-weight:700}
h2{font-size:1.25rem;text-transform:uppercase;letter-spacing:.12em;margin:48px 0 14px;font-weight:700;display:inline-block;padding-bottom:4px;border-bottom:1px solid var(--ink)}
h2 .n{font-family:var(--mono);font-weight:400;color:var(--muted);margin-right:10px;letter-spacing:.05em}
h3{font-size:1.05rem;margin:26px 0 8px}
p{margin:0 0 1rem}
.doc-no{font-family:var(--mono);font-size:.75rem;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin:34px 0 0}
.doc-no a{color:var(--muted)}
.lede{font-size:1.2rem;line-height:1.55;max-width:66ch}
.prose{max-width:70ch}
.fig{font-family:var(--mono);font-size:.95em;letter-spacing:-.02em}
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));border:1px solid var(--ink);margin:26px 0}
.stat{padding:16px 18px 14px;border-right:1px solid var(--border);min-width:0}
.stat:last-child{border-right:0}
.stat .v{font-family:var(--mono);font-size:2.1rem;line-height:1.05;font-weight:700;letter-spacing:-.03em}
.stat .v.red{color:var(--red)}
.stat .l{font-size:.82rem;color:var(--muted);margin-top:8px;line-height:1.4}
.big3 .stat .v{font-size:2.6rem}
@media(max-width:640px){.stat .v,.big3 .stat .v{font-size:1.7rem}.stat-row{grid-template-columns:1fr 1fr}.stat:nth-child(2n){border-right:0}}
.tablewrap{overflow-x:auto;border:1px solid var(--ink);margin:14px 0 10px}
table{border-collapse:collapse;width:100%;font-size:.9rem;white-space:nowrap}
thead th{background:var(--ink);color:#fff;font-family:var(--mono);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;font-weight:400;padding:10px 12px;text-align:left;cursor:pointer;user-select:none;white-space:normal;line-height:1.3;vertical-align:bottom}
thead th.num{text-align:right}
thead th[data-asc="1"]::after{content:" ▲"}thead th[data-asc="0"]::after{content:" ▼"}
td{padding:10px 12px;border-bottom:1px solid #d9d4c7;vertical-align:top}
tbody tr:last-child td{border-bottom:0}
td.num{text-align:right;font-family:var(--mono);font-size:.86rem}
td.name{min-width:200px;white-space:normal}
td.name a{font-weight:700;text-decoration:none}
td.name a:hover{text-decoration:underline}
td .sub{display:block;font-size:.84rem;color:var(--muted);font-weight:400;margin-top:2px}
td.ratio{color:var(--red);font-weight:700}
tr.kids td{color:var(--muted)}tr.kids td.name a{color:var(--muted);font-weight:400}
.toolbar{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:center;margin:18px 0 4px;font-size:.92rem}
.toolbar input[type=search]{font:inherit;font-size:.95rem;padding:8px 12px;border:1px solid var(--ink);background:var(--paper);color:var(--ink);min-width:min(340px,100%);border-radius:0}
.toolbar label{display:flex;gap:8px;align-items:center;color:var(--muted)}
.note{font-size:.88rem;color:var(--muted);max-width:70ch;line-height:1.55}
.src{font-size:.85rem;color:var(--muted);margin-top:8px}
dl.kv{display:grid;grid-template-columns:max-content 1fr;gap:6px 24px;font-size:.95rem;max-width:70ch;border-top:1px solid var(--border);padding-top:12px;margin:0}
dl.kv dt{color:var(--muted)}dl.kv dd{margin:0;font-family:var(--mono);font-size:.9rem;min-width:0}
.callout{background:var(--surface);border:1px solid var(--ink);border-left:6px solid var(--red);padding:14px 18px;max-width:70ch;margin:22px 0;font-size:1.02rem;line-height:1.55}
.cb{display:grid;grid-template-columns:1fr auto;gap:4px 16px;font-size:.92rem;max-width:600px}
.cb span:nth-child(2n){font-family:var(--mono);font-size:.88rem}
.cb .bar{grid-column:1/-1;height:12px;background:#d9d4c7;position:relative;margin-bottom:10px;border:1px solid var(--border)}
.cb .bar i{position:absolute;left:0;top:0;bottom:0;background:var(--red)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:10px}
.sharebox{display:grid;grid-template-columns:minmax(0,600px) 1fr;gap:22px;align-items:start;border:1px solid var(--ink);padding:18px;margin:22px 0;background:var(--surface)}
.sharebox img{width:100%;height:auto;border:1px solid var(--border);display:block}
.sharelinks p{margin:0 0 10px;font-size:.92rem}
.sharelinks .btn{margin:4px 6px 4px 0;cursor:pointer;font-family:var(--mono)}
button.btn{border:2px solid var(--ink);background:var(--ink);color:#fff}button.btn.ghost{background:transparent;color:var(--ink)}button.btn.ghost:hover{background:var(--ink);color:#fff}
@media(max-width:800px){.sharebox{grid-template-columns:1fr}}
.statelist{columns:3;column-gap:28px;font-size:.95rem}.statelist a{display:block;padding:3px 0;text-decoration:none}.statelist a:hover{text-decoration:underline}@media(max-width:640px){.statelist{columns:2}}
.card{border:1px solid var(--ink);padding:22px}
.card h3{margin:0 0 10px;font-size:1rem;text-transform:uppercase;letter-spacing:.1em}
.card p,.card li{font-size:.92rem}
.btn{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;font-family:var(--mono);font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;padding:10px 16px;margin:4px 6px 4px 0}
.btn:hover{background:#333}
.btn.ghost{background:transparent;color:var(--ink);border:2px solid var(--ink);padding:8px 14px}
.btn.ghost:hover{background:var(--ink);color:#fff}
ul.files{list-style:none;padding:0;margin:0}
ul.files li{padding:12px 0;border-bottom:1px solid var(--border)}
ul.files li:last-child{border-bottom:0}
ul.files .fn{font-family:var(--mono);font-weight:700}
ul.files .meta{font-family:var(--mono);font-size:.74rem;color:var(--muted);display:block;margin-top:4px;white-space:normal;word-break:break-all}
code{font-family:var(--mono);font-size:.88em}
pre{background:var(--surface);border:1px solid var(--border);padding:14px;overflow-x:auto;font-size:.82rem;line-height:1.45}
.manual table{white-space:normal;font-size:.86rem}
.manual thead th{cursor:default}
footer{margin-top:64px;padding-top:28px;text-align:center;font-family:var(--mono);font-size:.8rem;letter-spacing:.12em;color:var(--muted)}
footer .rule-single{width:100%;max-width:440px;margin:0 auto 22px}
footer .links a{color:var(--muted);text-decoration:none;margin:0 10px}
footer .links a:hover{color:var(--ink)}
footer p{margin:14px 0 0}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
"""

SITE_NAV = [('main','Main'),('reports','Reports'),('data','Data'),('contact','Contact'),('about','About'),('standards','Standards'),(f'{BASE}/for-local-groups.html','For local groups')]
REPORT_NAV = [(f'{BASE}/','Ranking'),(f'{BASE}/all.html','Complete list'),(f'{BASE}/states.html','By state'),(f'{BASE}/methodology.html','Methodology'),(f'{BASE}/manual.html','Reproduction manual'),(f'{BASE}/data.html','Data files')]

def HEAD(title, desc='', here=None, wide=True, card=None, url=None):
    local = (here or '').endswith('for-local-groups.html')
    def _nav(k, v):
        href = k if k.startswith('/') else '/#' + k
        on = (k == 'reports' and not local) or (k.startswith('/') and local)
        return f'<a href="{href}"{" class=on" if on else ""}>{v}</a>'
    site_nav = ''.join(_nav(k, v) for k, v in SITE_NAV)
    card = card or f'{BASE}/cards/summary.png'
    og = f"""<meta property="og:type" content="article"><meta property="og:site_name" content="{E(PUBLISHER)}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="{SITE}{card}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
{f'<meta property="og:url" content="{SITE}{url}">' if url else ''}
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{SITE}{card}">"""
    rep_nav = ''.join(f'<a href="{u}"{" class=on" if u==here else ""}>{v}</a>' for u, v in REPORT_NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} - {E(PUBLISHER)}</title>
<meta name="description" content="{E(desc)}">
{og}
<link rel="icon" type="image/png" href="/logo.png">
<link rel="stylesheet" href="/fonts/fonts.css">
<style>{CSS}</style></head><body>
<div class="sheet">
<header class="mast">
<a class="seal" href="/" aria-label="{E(PUBLISHER)} home"><img src="/logo.png" alt="Official Seal, {E(PUBLISHER)} ({EDITION})"></a>
<h1>{E(PUBLISHER)}</h1>
<div class="rule-double"></div>
<nav class="site">{site_nav}</nav>
<div class="band"><span class="rep">Report No. {REPORT_NO} &middot; {E(REPORT_TITLE)} &middot; {E(SERIES)}, {EDITION} edition</span><nav>{rep_nav}</nav></div>
</header>
<main>
"""
FOOT = f"""</main>
<footer><div class="rule-single"></div>
<div class="links"><a href="/#reports">Reports</a>|<a href="/#data">Data</a>|<a href="/#contact">Contact</a>|<a href="/#about">About</a>|<a href="/#standards">Standards</a></div>
<p>Report No. {REPORT_NO}, {E(SERIES)}, {EDITION} edition &middot; Data as of {DATA_ASOF} &middot; Built {BUILD}</p>
<p>Every figure is taken from the hospital's own IRS Form 990 as published by the IRS and is linked on the page where it appears. Corrections: send the filing that contradicts a figure to contact@everythingisbroken.org.</p>
<p>Everything Is Broken does not support violence, threats, or harassment of any kind. Change should come through transparency and open public debate. Donations are not tax-deductible.</p>
<p>&copy; {EDITION} EVERYTHINGISBROKEN.ORG</p></footer>
</div></body></html>"""

def pp_url(s): return f"https://projects.propublica.org/nonprofits/organizations/{s['lead_ein'].replace('-','')}/{s['oid']}/full" if s['oid'] else f"https://projects.propublica.org/nonprofits/organizations/{s['lead_ein'].replace('-','')}"

def row(s, show_state=True):
    cls = ' class="kids"' if s['kids'] else ''
    return f"""<tr{cls} data-name="{E(s['name'].lower())}" data-ceo="{E(s['ceo'].lower())}" data-state="{s['state']}" data-kids="{int(s['kids'])}">
<td class="num">{s.get('rank','')}</td>
<td class="name"><a href="{BASE}/system/{s['slug']}.html">{E(s['name'])}</a><span class="sub">{E(s['ceo'])}{' · children’s' if s['kids'] else ''}</span></td>
{'<td>'+s['state']+'</td>' if show_state else ''}
<td class="num" data-v="{s['pay']}">{money(s['pay'])}</td>
<td class="num" data-v="{s['rev'] or 0}">{money(s['rev'])}</td>
<td class="num" data-v="{s['ccp'] if s['ccp'] is not None else -1}">{pct(s['ccp'])}</td>
<td class="num" data-v="{s['cc'] or 0}">{money(s['cc'])}</td>
<td class="num ratio" data-v="{s['ratio'] or 0}">{pct(s['ratio'],0)}</td></tr>"""

TABLE_HEAD = lambda show_state=True: f"""<thead><tr><th class="num" data-k="num">#</th><th data-k="text">System and CEO</th>{'<th data-k="text">State</th>' if show_state else ''}<th class="num" data-k="num">CEO pay</th><th class="num" data-k="num">Revenue</th><th class="num" data-k="num">Charity care,<br>% of expenses</th><th class="num" data-k="num">Charity care</th><th class="num" data-k="num">CEO pay as %<br>of charity care</th></tr></thead>"""

SORT_JS = """<script>
(function(){
  var tables=document.querySelectorAll('table.sortable');
  tables.forEach(function(t){
    var ths=t.querySelectorAll('th');
    ths.forEach(function(th,i){th.addEventListener('click',function(){
      var tb=t.tBodies[0], rows=Array.prototype.slice.call(tb.rows), k=th.dataset.k, asc=th.dataset.asc!=='1';
      ths.forEach(function(h){delete h.dataset.asc}); th.dataset.asc=asc?'1':'0';
      rows.sort(function(a,b){var x=a.cells[i],y=b.cells[i]; if(k==='num'){x=parseFloat(x.dataset.v!==undefined?x.dataset.v:x.textContent)||0;y=parseFloat(y.dataset.v!==undefined?y.dataset.v:y.textContent)||0;return asc?x-y:y-x}
        x=x.textContent.trim().toLowerCase();y=y.textContent.trim().toLowerCase();return asc?(x<y?-1:x>y?1:0):(x>y?-1:x<y?1:0)});
      rows.forEach(function(r){tb.appendChild(r)});
    })});
  });
  var q=document.getElementById('q'), kids=document.getElementById('kids');
  function filter(){var v=(q?q.value:'').trim().toLowerCase(), showKids=kids?kids.checked:true;
    document.querySelectorAll('table.sortable tbody tr').forEach(function(r){
      var ok=(!v||r.dataset.name.indexOf(v)>=0||r.dataset.ceo.indexOf(v)>=0||r.dataset.state.toLowerCase()===v)&&(showKids||r.dataset.kids!=='1');
      r.hidden=!ok;});}
  if(q){q.addEventListener('input',filter)} if(kids){kids.addEventListener('change',filter)}
})();
</script>"""

import shutil
for _d in ('system', 'state'):
    shutil.rmtree(os.path.join(OUT, _d), ignore_errors=True)

def write(path, body):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(body)

STATS = f"""<div class="stat-row">
<div class="stat"><div class="v">{len(ranked):,}</div><div class="l">systems ranked, of {len(S):,} identified in {N_FILINGS:,} IRS Schedule H filings</div></div>
<div class="stat"><div class="v">{MED_CC:.2f}%</div><div class="l">median share of expenses spent on charity care, systems over $1B</div></div>
<div class="stat"><div class="v">{UNDER1:.0f}%</div><div class="l">of systems over $1B spend under one percent</div></div>
<div class="stat"><div class="v red">{len(hl_over)}</div><div class="l">chief executives paid more than their hospital gave in charity care, hospitals over ${HEADLINE_MIN_REV/1e6:.0f}M</div></div>
</div>"""


# ---------- findings ----------
giants = sorted([s for s in big if (s['rev'] or 0) >= 1e10], key=lambda s: -(s['ccp'] or 0))
OPERATING = lambda s: s['rev'] and s['exp'] and 0.65 <= s['exp']/s['rev'] <= 1.5   # foundations and joint-venture partners report investment income, not hospital operations
best = sorted([s for s in big if s['ccp'] is not None and OPERATING(s)], key=lambda s: -s['ccp'])[:10]
over = sorted(OVER100, key=lambda s: -s['ratio'])
kaiser = next((s for s in giants if s['lead_ein'] == '94-1105628'), giants[0])
advocate = next((s for s in giants if s['lead_ein'] == '36-2169147'), None)
def frow(s, cols):
    cells = {'sys': f'<td class="name"><a href="{BASE}/system/{s["slug"]}.html">{E(s["name"])}</a><span class="sub">{E(s["ceo"])}</span></td>',
             'st': f'<td>{s["state"]}</td>', 'rev': f'<td class="num">{money(s["rev"])}</td>', 'cc': f'<td class="num">{money(s["cc"])}</td>',
             'ccp': f'<td class="num">{pct(s["ccp"])}</td>', 'pay': f'<td class="num">{money(s["pay"])}</td>', 'ratio': f'<td class="num ratio">{pct(s["ratio"],0)}</td>'}
    return '<tr>' + ''.join(cells[c] for c in cols) + '</tr>'
FH = {'sys':'<th>System and chief executive</th>','st':'<th>State</th>','rev':'<th class="num">Revenue</th>','cc':'<th class="num">Charity care</th>','ccp':'<th class="num">Charity care,<br>% of expenses</th>','pay':'<th class="num">CEO pay</th>','ratio':'<th class="num">CEO pay as %<br>of charity care</th>'}
def ftable(rows, cols): return f'<div class="tablewrap"><table><thead><tr>{"".join(FH[c] for c in cols)}</tr></thead><tbody>{"".join(frow(s, cols) for s in rows)}</tbody></table></div>'
adv_txt = ''
if advocate:
    adv_txt = f" {E(advocate['name'])}, the system this report's first target runs, is {E(STATES.get(advocate['state'], advocate['state']))}'s largest and sits near the bottom at {pct(advocate['ccp'])}: Kaiser is {kaiser['rev']/advocate['rev']:.1f} times its size and gave {kaiser['cc']/advocate['cc']:.1f} times the charity care."
FINDINGS = f"""
<h2><span class="n">&sect;2</span>What the filings show</h2>
<div class="prose">
<p><strong>{HEADLINE}</strong> {HEADLINE_SUB} The list is every general hospital system with revenue over ${HEADLINE_MIN_REV/1e6:.0f} million where one person's pay exceeded the cost of all the free and discounted care the system gave in the same year, by CEO pay. Rehabilitation, long-term acute care, cancer, behavioral and other specialty hospitals are left out of this count and listed with the reason in <a href="{DATA_URL}/headline_exclusions.csv">headline_exclusions.csv</a>; they remain in the full ranking. Every row was checked against the filing, including the Part VI narrative, before it was listed.</p>
</div>
{ftable(hl_over, ['sys','st','rev','cc','ccp','pay','ratio'])}
<div class="prose">
<p><strong>The biggest systems can do it. Most don't.</strong> Among the {len(giants)} systems with revenue over $10 billion, {E(kaiser['name'])} gave the most charity care in dollars ({money(kaiser['cc'])}) and the most as a share of expenses ({pct(kaiser['ccp'])}), and paid its chief executive, {E(kaiser['ceo'])}, {money(kaiser['pay'])}, which is {pct(kaiser['ratio'],1)} of that charity care, the lowest ratio of any system its size.{adv_txt} Same tax exemption, same filing, same line of the form.</p>
</div>
{ftable(giants, ['sys','st','rev','cc','ccp','pay','ratio'])}
<div class="prose">
<p><strong>The highest rates in the country are at large regional systems, not the giants.</strong> Of the {len(big)} systems over $1 billion, these ten gave the largest share of their expenses as charity care. Several are two to three times {E(kaiser['name'])}'s rate. They are the standard the rest of the list should be measured against, because they prove the money is there.</p>
</div>
{ftable(best, ['sys','st','rev','cc','ccp','pay','ratio'])}
"""

# ---------- press kit ----------
import zipfile, io
hl_csv = io.StringIO(); w = csv.writer(hl_csv)
w.writerow(['rank_by_ceo_pay','system','state','chief_executive','ceo_pay_usd','charity_care_usd','charity_care_pct_of_expenses','ceo_pay_pct_of_charity_care','total_revenue_usd','fiscal_year_end','lead_ein','filing_url','page_url'])
for i, s in enumerate(hl_over, 1):
    w.writerow([i, s['name'], s['state'], s['ceo'], int(s['pay']), int(s['cc']), round(s['ccp'], 2), round(s['ratio'], 1), int(s['rev'] or 0), s['fye'], s['lead_ein'], pp_url(s), f"{SITE}{BASE}/system/{s['slug']}.html"])
open(os.path.join(DATA, 'ceo_pay_exceeds_charity_care.csv'), 'w').write(hl_csv.getvalue())

# ---------- index ----------
top = ranked[:100]
index = HEAD(REPORT_TITLE, HEADLINE + ' ' + f'{len(ranked)} nonprofit hospital systems ranked by CEO pay, beside what each spent on charity care, from their own IRS filings.', here=f'{BASE}/', url=f'{BASE}/') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; Data as of {DATA_ASOF}</p>
<h1 class="title">{E(REPORT_TITLE)}</h1>
<p class="lede">{HEADLINE} The median large system spends about one cent of every dollar on charity care and pays its chief executive {MED_RATIO:.0f} percent of that. Every figure on this page is from the hospital's own IRS Form 990, linked on every row.</p>
{STATS}
<div class="sharebox"><img src="{BASE}/cards/summary.png" alt="Summary card" width="600" height="315"><div class="sharelinks"><strong>Share this report.</strong> The card to the left is what appears when this page's link is posted. <a href="{BASE}/cards/summary.png" download>Download the card</a> &middot; <a href="{BASE}/press-kit.zip" download>Press kit</a> &middot; <a href="{BASE}/for-local-groups.html">For local groups</a></div></div>
<h2><span class="n">&sect;1</span>Top 100 by CEO pay</h2>
<div class="toolbar"><input type="search" id="q" placeholder="Search a hospital, CEO, or state code"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<p class="note">Click a column to sort. Children’s hospitals are shown in grey: Medicaid covers most low-income children, so their charity care is structurally low.</p>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD()}<tbody>
{''.join(row(s) for s in top)}
</tbody></table></div>
<p class="note">Full list of {len(ranked)} systems on the <a href="{BASE}/all.html">complete ranking</a>. Systems where the chief executive could not be identified from the filing with confidence, or where charity care is reported on a line other than 7a, are excluded from the ranking and explained in the <a href="{BASE}/methodology.html">methodology</a>.</p>
{FINDINGS}
<h2><span class="n">&sect;3</span>How to read it</h2>
<div class="prose">
<p><strong>CEO pay</strong> is total compensation reported on Form 990 Part VII: salary and bonus from the organization and its related organizations, plus deferred compensation and benefits (columns D, E and F). It is the figure the hospital's board approved and the hospital reported.</p>
<p><strong>Charity care</strong> is Schedule H Part I line 7a: free or discounted care given under the hospital's own financial assistance policy, at the hospital's cost. It is not bad debt and not the Medicaid shortfall, which hospitals often add when they describe their community benefit publicly. The IRS form keeps them separate; so does this report.</p>
<p>Hospitals usually describe their charity care at charges, the list prices on their chargemaster, which run several times what the care costs to deliver. The IRS does not accept that figure. Line 7a must be reported at cost, using either the hospital’s cost accounting system or its own ratio of total expenses to total charges, and net of any payment received for the care. When a hospital’s press release gives a larger charity-care number than this report, that is almost always the difference.</p>
<p><strong>The ratio</strong> is CEO pay divided by charity care. At 100 percent, one person was paid as much as the system gave to every patient who could not pay.</p>
<p>A nonprofit hospital pays no federal income tax and, in nearly every state, no property or sales tax. The exemption is granted on the premise that the hospital serves the community in ways a business would not. This report puts two of the hospital's own numbers beside each other and lets the reader decide whether the premise holds.</p>
</div>
<h2><span class="n">&sect;4</span>Rebuttals</h2>
<div class="prose"><p>Institutions named in this report may reply to contact@everythingisbroken.org. Replies are published here in full. None has been received.</p></div>
{SORT_JS}{FOOT}"""
write('index.html', index)

# full list
allp = HEAD('Complete ranking', 'All ranked nonprofit hospital systems by CEO pay.', here=f'{BASE}/all.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition</p><h1 class="title">Complete ranking</h1>
<p class="lede">{len(ranked)} nonprofit hospital systems with an identifiable chief executive and positive charity care, ranked by CEO pay.</p>
<div class="toolbar"><input type="search" id="q" placeholder="Search a hospital, CEO, or state code"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD()}<tbody>{''.join(row(s) for s in ranked)}</tbody></table></div>
{SORT_JS}{FOOT}"""
write('all.html', allp)

# ---------- system pages ----------
def cb_bar(s):
    if not s['cb'] or not s['cc']: return ''
    share = min(100, s['cc'] / s['cb'] * 100)
    return f"""<div class="cb"><span>What the system reported as total community benefit (Schedule H line 7k)</span><span>{money(s['cb'])}</span>
<span>Of which charity care to patients who could not pay (line 7a)</span><span>{money(s['cc'])} ({share:.0f}%)</span>
<div class="bar"><i style="width:{share:.1f}%"></i></div></div>
<p class="note">The rest of line 7k is Medicaid shortfall, medical education, research, subsidized services and contributions. Bad debt ({money(s['bad'])}) and Medicare shortfall are reported separately by the IRS and are not community benefit on the form.</p>"""


# ---------- cards (1200 x 630 PNG, rendered from HTML with headless Chromium) ----------
CARD_DIR = os.path.join(OUT, 'cards'); shutil.rmtree(CARD_DIR, ignore_errors=True); os.makedirs(os.path.join(CARD_DIR, 'system')); os.makedirs(os.path.join(CARD_DIR, 'state'))
LOGO_URI = 'data:image/png;base64,' + __import__('base64').b64encode(open(os.path.join(REPO, 'logo.png'), 'rb').read()).decode()
FONT_CSS = open(os.path.join(REPO, 'fonts', 'fonts.css')).read().replace('url(/fonts/', f'url(file://{REPO}/fonts/')
CARD_CSS = FONT_CSS + """
*{box-sizing:border-box}html,body{margin:0;width:1200px;height:630px;overflow:hidden}
body{background:#f0ece1;font-family:"Libre Baskerville",Georgia,serif;color:#111}
.card{position:absolute;inset:18px;background:#faf8f2;border:1px solid #d6cfc2;padding:34px 44px 30px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:18px;border-bottom:4px double #111;padding-bottom:14px}
.top img{width:74px;height:74px}
.top .name{font-size:30px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;line-height:1}
.top .rep{font-family:"Space Mono",monospace;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:#555;margin-top:8px}
.title{font-size:34px;font-weight:700;line-height:1.15;margin:22px 0 4px}
.title.small{font-size:28px}
.sub{font-size:17px;color:#333;margin:0 0 14px}
.nums{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #111;margin-top:auto}
.nums.two{grid-template-columns:repeat(2,1fr)}
.n{padding:16px 20px 14px;border-right:1px solid #d6cfc2}.n:last-child{border-right:0}
.n .v{font-family:"Space Mono",monospace;font-size:46px;font-weight:700;letter-spacing:-.03em;line-height:1}
.n .v.red{color:#8b2626}
.n .l{font-size:14px;color:#444;margin-top:9px;line-height:1.3}
.foot{display:flex;justify-content:space-between;gap:20px;font-family:"Space Mono",monospace;font-size:12px;letter-spacing:.06em;color:#555;margin-top:16px;text-transform:uppercase;white-space:nowrap}
.say{font-size:24px;line-height:1.4;margin:26px 0 0;max-width:1000px}
.foot b{color:#111;font-weight:700}
table{border-collapse:collapse;width:100%;font-size:17px;margin-top:10px}
td{padding:7px 10px;border-bottom:1px solid #d6cfc2;vertical-align:top}td.num{text-align:right;font-family:"Space Mono",monospace;font-size:16px;white-space:nowrap}
td:first-child{max-width:560px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td.red{color:#8b2626;font-weight:700}
tr:last-child td{border-bottom:0}
.ceo{color:#555;font-size:15px}
"""
def card_html(body, title_rep=f'Report No. {REPORT_NO} · {EDITION} edition'):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CARD_CSS}</style></head><body><div class="card">
<div class="top"><img src="{LOGO_URI}" alt=""><div><div class="name">{E(PUBLISHER)}</div><div class="rep">{E(REPORT_TITLE)} · {title_rep}</div></div></div>
{body}
</div></body></html>"""
def foot(left):
    return f'<div class="foot"><span>{left}</span><span><b>everythingisbroken.org</b> · data as of {DATA_ASOF}</span></div>'

CARD_JOBS = []   # (path, html)
# summary card
top4 = hl_over[:5]
CARD_JOBS.append(('summary.png', card_html(f"""
<div class="title">{E(HEADLINE)}</div>
<p class="sub">Among {len(hl_all):,} general hospital systems with revenue over ${HEADLINE_MIN_REV/1e6:.0f} million. Together the {len(hl_over)} were paid {money(HL_PAY)}; their hospitals gave {money(HL_CC)} to patients who could not pay.</p>
<table>{''.join(f'<tr><td>{E(s["ceo"])} <span class="ceo">· {E(s["name"])}, {s["state"]}</span></td><td class="num">{money(s["pay"], False)} paid</td><td class="num">{money(s["cc"], False)} charity care</td><td class="num red">{s["ratio"]:.0f}%</td></tr>' for s in top4)}</table>
{foot(f'Source: each hospital’s IRS Form 990 Schedule H · {len(ranked):,} systems ranked')}""")))
# system cards
def sys_card(s):
    fy = s['fye'] or ''
    ratio_txt = f"{s['ratio']:.0f}%" if s['ratio'] else 'n/a'
    rank_txt = f"Ranked {s['rank']} of {len(ranked):,} by CEO pay" if s.get('rank') else 'Not ranked'
    if s['ratio'] and s['ratio'] > 100: say = f"{E(s['ceo'])} was paid {s['ratio']/100:.1f} times what the system gave in charity care to every patient who could not pay."
    elif s['ratio'] and s['ratio'] >= 15: say = f"{E(s['ceo'])}’s pay equals {s['ratio']:.0f} percent of all the charity care the system gave in the same year."
    elif s['ratio']: say = f"For every dollar the system gave in charity care, it paid its chief executive {s['ratio']:.0f} cents."
    else: say = "The figures below are as filed; see the page for why this system is not ranked."
    return card_html(f"""
<div class="title{' small' if len(s['name'])>34 else ''}">{E(s['name'])}</div>
<p class="sub">{E(STATES.get(s['state'], s['state']))} · {rank_txt} · fiscal year ending {fy}</p>
<p class="say">{say}</p>
<div class="nums">
<div class="n"><div class="v">{money(s['pay'])}</div><div class="l">paid to {E(s['ceo'])}, chief executive<br>Form 990 Part VII</div></div>
<div class="n"><div class="v">{money(s['cc'])}</div><div class="l">charity care, {pct(s['ccp'])} of expenses<br>Schedule H Part I line 7a</div></div>
<div class="n"><div class="v red">{ratio_txt}</div><div class="l">CEO pay as a share of all charity care</div></div>
</div>
{foot(f'Source: IRS Form 990, EIN {s["lead_ein"]}, as filed by the hospital')}""")
for s in S:
    if s['pay'] or s['cc']: CARD_JOBS.append((f"system/{s['slug']}.png", sys_card(s)))
# state cards
bystate0 = defaultdict(list)
for s in S:
    if s['state'] and (s['pay'] or s['cc']): bystate0[s['state']].append(s)
def state_card(st_, lst):
    cc = [s['ccp'] for s in lst if s['ccp'] is not None and s['zero_charity_care_flag'] != 'yes']
    med = st.median(cc) if cc else None
    over_here = [s for s in hl_over if s['state'] == st_]
    general = sorted([s for s in lst if s in hl_all], key=lambda s: s['ccp'])
    if over_here:
        rows_ = over_here[:5]; label = f"{len(over_here)} chief executive{'s' if len(over_here)!=1 else ''} paid more than the hospital gave in charity care" + (", the largest five:" if len(over_here) > 5 else ":")
    else:
        rows_ = general[:5]; label = "No chief executive was paid more than the hospital gave in charity care. The lowest charity care rates among general hospitals over $100 million:"
    return card_html(f"""
<div class="title">{E(STATES.get(st_, st_))}: {len(lst)} nonprofit hospital systems</div>
<p class="sub">Median charity care {pct(med)} of expenses. {label}</p>
<table>{''.join(f'<tr><td>{E(s["name"])} <span class="ceo">· {E(s["ceo"])}</span></td><td class="num">{money(s["pay"], False)} CEO pay</td><td class="num">{money(s["cc"], False)} charity care ({pct(s["ccp"])})</td><td class="num red">{s["ratio"]:.0f}%</td></tr>' for s in rows_)}</table>
{foot('Source: each hospital’s IRS Form 990 Schedule H')}""")
for st_, lst in sorted(bystate0.items()): CARD_JOBS.append((f"state/{st_}.png", state_card(st_, lst)))

def render_cards(jobs):
    from playwright.sync_api import sync_playwright
    tmp = os.path.join(CARD_DIR, '_tmp'); os.makedirs(tmp, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1200, 'height': 630})
        for path, html_ in jobs:
            hp = os.path.join(tmp, 'c.html'); open(hp, 'w').write(html_)
            pg.goto('file://' + hp); pg.wait_for_timeout(30)
            pg.screenshot(path=os.path.join(CARD_DIR, path), type='png')
        b.close()
    shutil.rmtree(tmp, ignore_errors=True)
if os.environ.get('EIB_SKIP_CARDS') != '1':
    render_cards(CARD_JOBS)
    print(f'rendered {len(CARD_JOBS)} cards')

def sharebox(s=None, st_=None):
    if s is not None:
        url = f"{SITE}{BASE}/system/{s['slug']}.html"; img = f"{BASE}/cards/system/{s['slug']}.png"
        sent = f"{s['name']} paid chief executive {s['ceo']} {money(s['pay'], False)} in the fiscal year ending {s['fye']}. It spent {pct(s['ccp'])} of expenses on charity care, {money(s['cc'], False)}. Source: its own IRS Form 990. {url}"
        alt = f"{s['name']}: CEO pay {money(s['pay'])}, charity care {pct(s['ccp'])} of expenses"
    else:
        url = f"{SITE}{BASE}/state/{st_}.html"; img = f"{BASE}/cards/state/{st_}.png"
        sent = f"Nonprofit hospital CEO pay vs charity care in {STATES.get(st_, st_)}, from the hospitals' own IRS filings. {url}"
        alt = f"{STATES.get(st_, st_)} nonprofit hospitals: CEO pay vs charity care"
    embed = f'<a href="{url}"><img src="{SITE}{img}" alt="{E(alt)}" width="600" height="315" style="max-width:100%;height:auto"></a>'
    return f"""<h2><span class="n">&sect;</span>Share</h2>
<div class="sharebox"><img src="{img}" alt="{E(alt)}" width="600" height="315">
<div class="sharelinks">
<p>This card is what appears when the link to this page is posted. Use it, the sentence, or the embed code. No permission needed; attribution is on the card.</p>
<p><a class="btn" href="{img}" download>Download card</a> <button class="btn ghost" data-copy="{E(url)}">Copy link</button> <button class="btn ghost" data-copy="{E(sent)}">Copy sentence</button> <button class="btn ghost" data-copy="{E(embed)}">Copy embed code</button></p>
<p class="note" style="margin:0">{E(sent)}</p>
</div></div>"""
COPY_JS = """<script>document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',function(){navigator.clipboard.writeText(b.dataset.copy).then(function(){var t=b.textContent;b.textContent='Copied';setTimeout(function(){b.textContent=t},1400)})})});</script>"""

n_sys = 0
for s in S:
    if not s['pay'] and not s['cc']: continue
    n_sys += 1
    rank_line = f"Ranked {s['rank']} of {len(ranked)} by CEO pay." if s.get('rank') else "Not ranked: see note below."
    ratio_txt = f"{s['ratio']:.0f}%" if s['ratio'] else 'n/a'
    callout = ''
    if s['ratio'] and s['ratio'] >= 100:
        callout = f'<div class="callout">In the most recent filing year, {E(s["ceo"])} was paid {money(s["pay"], False)}. The system’s charity care for the same year was {money(s["cc"], False)}. One person was paid {s["ratio"]/100:.1f} times what the system gave to every patient who could not pay.</div>'
    elif s['ratio'] and s['ratio'] >= 15:
        callout = f'<div class="callout">{E(s["ceo"])}’s pay of {money(s["pay"], False)} equals {s["ratio"]:.0f} percent of the {money(s["cc"], False)} the system spent on charity care in the same year.</div>'
    note = ''
    if re.search(r'\bEFF\b|EFFECTIVE|\bBEG\b|BEGIN|\bSTART|AS OF|\bINTERIM\b|\bINTERM\b|PART.?YEAR|\bPT YR\b|PARTIAL', s['ceo_title'] or '', re.I) and s['pub']:
        note = f'<p class="note">The chief executive\'s title on the filing indicates a change during the year ({E((s["ceo_title"] or "").split("[")[0].strip())}); the pay shown is what the filing reports for that person, which may cover part of the year.</p>'
    if not s['pub']:
        why = []
        if s['ceo_confidence'] not in ('ceo_title','ceo_title_multiple','manual_override'): why.append('the chief executive could not be identified from the filing with confidence')
        if s['zero_charity_care_flag'] == 'yes': why.append('the filing reports zero on line 7a while reporting other community benefit, which usually means charity care was booked on another line; the filing is being read by hand')
        if not s['cc']: why.append('no charity care figure is present')
        note = f'<p class="callout">Not in the ranking because {"; and ".join(why)}. The figures below are shown as filed.</p>'
    members = ''
    if len(s['members']) > 1:
        members = '<h2><span class="n">&sect;3</span>Filings in this system</h2><div class="tablewrap"><table><thead><tr><th>Filing entity</th><th>EIN</th><th>FY end</th><th class="num">Revenue</th><th class="num">Charity care</th><th class="num">% of expenses</th><th>Filing</th></tr></thead><tbody>' + ''.join(
            f"<tr><td style=\"white-space:normal\">{E(titlecase(r['name']))}</td><td><code>{e}</code></td><td>{r['fye']}</td><td class=\"num\">{money(f(r['total_revenue']))}</td><td class=\"num\">{money(f(r['charity_care_net']))}</td><td class=\"num\">{pct(f(r['charity_care_pct']))}</td><td><a href=\"https://projects.propublica.org/nonprofits/organizations/{e.replace('-','')}/{r['object_id']}/full\">990</a></td></tr>" for e, r in s['members']) + '</tbody></table></div>'
    page = HEAD(s['name'], f"{s['name']}: CEO pay {money(s['pay'])}, charity care {pct(s['ccp'])} of expenses, from its IRS Form 990.", card=f"{BASE}/cards/system/{s['slug']}.png", url=f"{BASE}/system/{s['slug']}.html") + f"""
<p class="doc-no"><a href="{BASE}/state/{s['state']}.html">{E(STATES.get(s['state'], s['state']))}</a> &middot; {rank_line}</p>
<h1 class="title">{E(s['name'])}</h1>
<p class="lede">{E(s['ceo'])}, {E((s['ceo_title'] or 'chief executive').split('[')[0].strip().title())}. Fiscal year ending {s['fye']}.</p>
<div class="stat-row big3">
<div class="stat"><div class="v">{money(s['pay'])}</div><div class="l">CEO total compensation<br>Form 990 Part VII, columns D+E+F</div></div>
<div class="stat"><div class="v">{pct(s['ccp'])}</div><div class="l">of expenses spent on charity care<br>Schedule H Part I line 7a</div></div>
<div class="stat"><div class="v red">{ratio_txt}</div><div class="l">CEO pay as a share of all charity care</div></div>
</div>
{callout}{note}
{('<p class="note">Also listed with a chief executive title in the same filings: ' + '; '.join(f'{E(person(n))}, {E(ti.split("(")[0].strip().title())}, {money(t, False)}' for t, n, ti in s['other_execs']) + '. Where a chief executive retired during the year, the filing reports the final-year payout.</p>') if s['other_execs'] else ''}
<h2><span class="n">&sect;1</span>The filing</h2>
<dl class="kv">
<dt>Total revenue</dt><dd>{money(s['rev'], False)}</dd>
<dt>Total expenses</dt><dd>{money(s['exp'], False)}</dd>
<dt>Net assets</dt><dd>{money(s['na'], False)}</dd>
<dt>Employees</dt><dd>{int(s['emp'] or 0):,}</dd>
<dt>Hospitals covered</dt><dd>{int(f(s['facility_count']) or 0)} facilities across {len(s['members'])} filing{'s' if len(s['members'])!=1 else ''}</dd>
<dt>Charity care, net</dt><dd>{money(s['cc'], False)}</dd>
<dt>Bad debt</dt><dd>{money(s['bad'], False)}</dd>
<dt>Medicare shortfall</dt><dd>{money(f(s['medicare_shortfall']), False)}</dd>
<dt>CEO pay</dt><dd>{money(s['pay'], False)} to {E(s['ceo'])}</dd>
</dl>
<p class="src">Source: <a href="{pp_url(s)}">Form 990, {E(s['name'])}, EIN {s['lead_ein']}, fiscal year ending {s['fye']}</a>, as published by the IRS. CEO identification: {E(s['ceo_confidence'].replace('_',' '))}.</p>
<h2><span class="n">&sect;2</span>Community benefit versus charity care</h2>
{cb_bar(s)}
{members}
<p class="note" style="margin-top:28px">Every number on this page was copied from the filing linked above. If a figure is wrong, send the filing that contradicts it and the correction runs at the top of this page.</p>
{sharebox(s=s)}
{COPY_JS}{FOOT}"""
    write(f"system/{s['slug']}.html", page)

# ---------- state pages ----------
bystate = defaultdict(list)
for s in S:
    if s['state'] and (s['pay'] or s['cc']): bystate[s['state']].append(s)
state_index_rows = []
for st_, lst in sorted(bystate.items()):
    pubs = [s for s in lst if s['pub']]; pubs.sort(key=lambda s: -s['pay'])
    cc = [s['ccp'] for s in lst if s['ccp'] is not None and s['zero_charity_care_flag'] != 'yes']
    med = st.median(cc) if cc else None
    state_index_rows.append((st_, STATES.get(st_, st_), len(lst), med))
    body = HEAD(f"{STATES.get(st_, st_)} hospitals", f"Nonprofit hospital systems in {STATES.get(st_, st_)} ranked by CEO pay.", here=f'{BASE}/states.html', card=f"{BASE}/cards/state/{st_}.png", url=f"{BASE}/state/{st_}.html") + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; <a href="{BASE}/states.html">all states</a></p>
<h1 class="title">{E(STATES.get(st_, st_))}</h1>
<p class="lede">{len(lst)} nonprofit hospital systems file from {E(STATES.get(st_, st_))}. Median charity care: {pct(med)} of expenses.</p>
<div class="toolbar"><input type="search" id="q" placeholder="Search"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD(False)}<tbody>{''.join(row(s, False) for s in pubs)}</tbody></table></div>
<p class="note">Systems not shown: {len(lst)-len(pubs)} with an unidentifiable chief executive or charity care reported off line 7a. Each has its own page: {', '.join(f'<a href="{BASE}/system/{s["slug"]}.html">{E(s["name"])}</a>' for s in lst if not s['pub']) or 'none'}.</p>
{sharebox(st_=st_)}
{SORT_JS}{COPY_JS}{FOOT}"""
    write(f'state/{st_}.html', body)
states = HEAD('By state', 'Nonprofit hospital charity care and CEO pay, state by state.', here=f'{BASE}/states.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition</p><h1 class="title">By state</h1>
<p class="lede">Median charity care as a share of expenses, by the state each system files from. Click a state for its ranking.</p>
<div class="tablewrap"><table class="sortable"><thead><tr><th data-k="text">State</th><th class="num" data-k="num">Systems</th><th class="num" data-k="num">Median charity care, % of expenses</th></tr></thead><tbody>
{''.join(f'<tr><td class="name"><a href="{BASE}/state/{a}.html">{E(n)}</a></td><td class="num">{c}</td><td class="num" data-v="{m if m is not None else -1}">{pct(m)}</td></tr>' for a,n,c,m in sorted(state_index_rows, key=lambda x: (x[3] if x[3] is not None else 99)))}
</tbody></table></div>{SORT_JS}{FOOT}"""
write('states.html', states)

# ---------- methodology ----------
meth = HEAD('Methodology', 'How the figures were taken from IRS filings, and the rules used.', here=f'{BASE}/methodology.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition</p><h1 class="title">Methodology</h1>
<div class="prose">
<p class="lede">No figure here is an estimate. Each is copied from a form the hospital filed, or computed from such figures with the formula stated.</p>
<h2>Source</h2><p>Every nonprofit hospital files IRS Form 990 with Schedule H. The IRS publishes every e-filed return as XML. This report reads the 2025 and 2026 releases (about 1.2 million filings), keeps the {N_FILINGS:,} that include Schedule H, and takes the latest fiscal year for each of the {len(F):,} filers. Each page links the filing it was built from.</p>
<h2>CEO pay</h2><p>Form 990 Part VII, Section A lists officers, directors, key employees and the five highest-paid employees with three compensation columns: from the organization, from related organizations, and other compensation (deferred pay and benefits). CEO pay is the sum of the three. The chief executive is the person whose title contains CEO or chief executive and who is not marked former; where titles are ambiguous, the filing was read by hand and the decision recorded with its reason. Systems whose chief executive could not be identified from the filing are shown on their own pages but not ranked.</p>
<h2>Charity care</h2><p>Schedule H Part I line 7a, "financial assistance at cost": free or discounted care given under the hospital's written financial assistance policy, valued at cost. Column (e), net of any grants received for it. The percentage of expenses shown on this site is that figure divided by total expenses from Form 990 line 18, computed the same way for every system; the percentage the hospital itself entered in column (f) is published in the data files for comparison. It excludes bad debt (Part III) and Medicaid shortfall (line 7b), which the IRS reports separately.</p>
<h2>Systems, and what one row is</h2><p>Many systems file one return per hospital. Filings that report the same chief executive are combined into one row: revenue, expenses and charity care are summed and the chief executive is counted once. Where a system's hospitals file under their own presidents, each hospital appears as its own row under its own president, and the parent's executives are attributed to no hospital. So a row is a filing, or a set of filings, with the chief executive that filing reports; it is not always the whole corporate system, and a hospital president's pay is compared only with that hospital's charity care. Where a filing reports a parent organization's executive rather than the hospital's own, the hospital is shown but excluded from CEO figures, with the reason in the data files. Every combination above $1 billion in revenue was checked by hand, as was every row on the headline list.</p>
<h2>Children's hospitals</h2><p>Medicaid and CHIP cover most low-income children, so children's hospitals report little uncompensated care and appear at the bottom of any charity care ranking. They are shown in grey and can be hidden from any table.</p>
<h2>What this report does not do</h2><p>It does not estimate the value of the tax exemption. It does not count public hospitals (county, state, veterans), which file no Form 990. It does not judge whether a chief executive is overpaid. It puts two of the hospital's own numbers beside each other.</p>
<h2>Independent check</h2><p>CEO pay figures were compared against CEO Paycheck, which reads the same filings with its own method: of 129 systems present in both, 121 agree on the person and the dollar amount. The eight differences are explained in section 7 of the <a href="{BASE}/manual.html">reproduction manual</a>.</p>
<h2>Corrections</h2><p>If a figure is wrong, send the filing that contradicts it to contact@everythingisbroken.org. The correction runs at the top of the affected page with the date, and in the corrections log on the <a href="/#standards">Standards</a> page.</p>
<p>The full <a href="{BASE}/manual.html">reproduction manual</a>, with every rule and every manual decision, and the <a href="{BASE}/data.html">data files and scripts</a> that build this report from the IRS release, are published alongside it.</p>
</div>{FOOT}"""
write('methodology.html', meth)

# ---------- reproduction manual (rendered from pipeline/REPRODUCTION_MANUAL.md) ----------
try:
    import markdown
    md = open(os.path.join(HERE, 'REPRODUCTION_MANUAL.md')).read()
    md = md.split('\n', 1)[1]  # drop the H1; the page supplies it
    manual_html = markdown.markdown(md, extensions=['tables', 'fenced_code'])
except ImportError:
    manual_html = f'<p>The manual is published as <a href="/pipeline/REPRODUCTION_MANUAL.md">REPRODUCTION_MANUAL.md</a>. Install the Python <code>markdown</code> package to render it here.</p>'
manual = HEAD('Reproduction manual', 'A complete procedure for rebuilding the dataset from the IRS bulk files.', here=f'{BASE}/manual.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; <a href="/pipeline/REPRODUCTION_MANUAL.md">plain-text original</a></p>
<h1 class="title">Reproduction manual</h1>
<div class="prose manual">{manual_html}</div>{FOOT}"""
write('manual.html', manual)

# ---------- data files ----------
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()
def nrows(p):
    if p.endswith('.gz'):
        with gzip.open(p, 'rt') as fh: return sum(1 for _ in fh) - 1
    return sum(1 for _ in open(p)) - 1
def size(p):
    b = os.path.getsize(p)
    return f'{b/1e6:.1f} MB' if b >= 1e6 else f'{b/1e3:.0f} KB'
FILES = [
    ('systems_rollup.csv', 'One row per hospital system after roll-up: members, revenue, expenses, charity care, chief executive, CEO pay, ratios and flags. This is the table every page on this site is built from.'),
    ('filers_latest.csv', 'One row per filing entity (EIN), latest fiscal year, before roll-up, with the identified chief executive and confidence.'),
    ('hospital_data.csv.gz', 'The master table, append-only: one row per figure with its form, schedule, part, line, source URL and retrieval method. Superseded rows are marked ignore, never deleted. Gzipped; about 170 MB uncompressed.'),
    ('ceo_overrides.csv', 'Every manual decision about who the chief executive is, with the reason and date.'),
    ('headline_exclusions.csv', 'Specialty filers left out of the headline count, with the reason. They remain in the full ranking.'),
    ('ceo_pay_exceeds_charity_care.csv', 'The headline list: every general hospital system over $100M where CEO pay exceeded charity care, with a link to each filing.'),
    ('rollup_overrides.csv', 'Every manual decision about which filings form one system, with the reason and date.'),
    ('ceopaycheck_crosscheck.csv', 'Result of the independent check of CEO pay figures against CEO Paycheck.'),
    ('ceopaycheck_snapshot_2026-10-18.csv', 'The CEO Paycheck rows used for that check, as captured on the date in the name.'),
]
WORKING = [('working/ceo_unresolved.csv', 'Filers where the CEO rule found no chief executive.'), ('working/ceo_review_large.csv', 'Material used for the manual review of filers above $1B.'), ('working/hospitals_wide.csv', 'An early wide-format export, kept for the record.')]
SCRIPTS = ['fetch_all.sh', 'parse_xml.py', 'load_all.py', 'add_rows.py', 'build_systems.py', 'build_site.py', 'analyze.py', 'parse_schh.py', 'save_and_parse.py', 'seed_01.py']
file_rows = []; sums = []
for fn, desc in FILES + WORKING:
    p = os.path.join(DATA, fn); h = sha(p); sums.append(f'{h}  {fn}')
    file_rows.append(f'<li><a class="fn" href="{DATA_URL}/{fn}" download>{fn}</a> <span class="note" style="display:inline">({size(p)}, {nrows(p):,} rows)</span><br>{desc}<span class="meta">sha256 {h}</span></li>')
open(os.path.join(DATA, 'SHA256SUMS'), 'w').write('\n'.join(sums) + '\n')
data = HEAD('Data files', 'Download the full dataset, the manual decisions, and the scripts that build the report.', here=f'{BASE}/data.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; Data as of {DATA_ASOF}</p><h1 class="title">Data files</h1>
<div class="prose">
<p class="lede">Everything on this site is generated from one table, and that table is generated from the IRS release by scripts anyone can run. The files below are the complete record.</p>
<p><a class="btn" href="{DATA_URL}/systems_rollup.csv" download>Download systems_rollup.csv</a> <a class="btn ghost" href="{DATA_URL}/SHA256SUMS" download>SHA256SUMS</a> <a class="btn ghost" href="{BASE}/manual.html">Reproduction manual</a></p>
<h2>Dataset</h2>
<ul class="files">{''.join(file_rows[:len(FILES)])}</ul>
<h2>Working files</h2>
<p class="note">Intermediate files from the review process. Not needed to reproduce the report; kept because nothing is deleted.</p>
<ul class="files">{''.join(file_rows[len(FILES):])}</ul>
<h2>Scripts</h2>
<p>The pipeline, in the order it runs. Python 3 standard library only; no accounts or API keys. Section 5 of the <a href="{BASE}/manual.html">reproduction manual</a> walks through each step.</p>
<ul class="files">{''.join(f'<li><a class="fn" href="/pipeline/{x}">{x}</a></li>' for x in SCRIPTS)}</ul>
<h2>Primary sources</h2>
<ul>
<li><a href="https://www.irs.gov/charities-non-profits/form-990-series-downloads">IRS Form 990 series downloads</a>: the bulk XML releases every figure was read from.</li>
<li><a href="https://www.irs.gov/forms-pubs/about-schedule-h-form-990">IRS Schedule H (Form 990)</a>: the hospital schedule, Part I line 7a, where charity care is reported.</li>
<li><a href="https://projects.propublica.org/nonprofits/">ProPublica Nonprofit Explorer</a>: a readable copy of each filing, linked from every system page by EIN and object ID.</li>
</ul>
<h2>Version log</h2>
<ul class="files">
<li><span class="fn">{EDITION}.3</span> &middot; 2026-10-21<br>Audit of the full table, started from the list of systems where CEO pay exceeded charity care (98 before review) and extended to all ranked systems. Findings and fixes: (1) parent or regional executives reported on a subsidiary's return were being compared with that subsidiary's charity care; where the filings allow it the system is assembled (Mount Sinai, Adventist Health, WVU Health System, Northern Light, Monument Health, Banner Wyoming, CHI Health Nebraska Heart, Rady/CHOC) and where they do not the filer is excluded from CEO figures with the reason (SSM Regional, Touro, Calvary, Covenant Specialty, St Anthony's, Baptist Southeast Texas, Holy Cross Fort Lauderdale, Maple Grove, Cedars-Sinai Marina, Porter, Otero). (2) The same person was split into several rows by spelling: nine joins. (3) The chief-executive rule now excludes titles marked retired, FRMR or FMR, and a chief executive whose title carries an end date yields to a successor whose title carries a start date or is interim; 40 rows changed executive. (4) Two closed hospitals' wind-down years excluded. (5) Ten specialty filers listed in headline_exclusions.csv. (6) Narratives read for 64 filings with small line 7a; none reports charity care elsewhere. (7) Fifty filings re-parsed from XML: no mismatches. Open limitation: systems whose hospitals file under local presidents appear as separate rows; a shared-officer test found 129 such clusters, listed for the next edition. {len(S):,} systems, {len(ranked):,} ranked; headline {len(hl_over)} of {len(hl_all):,}.</li>
<li><span class="fn">{EDITION}.2</span> &middot; 2026-10-20<br>Parkview Health (IN) assembled from its ten filings: the parent filer alone had shown $84,340 of charity care and a 4,360% ratio. 1,642 systems, 1,074 ranked. Ten rows added to rollup_overrides.csv with the filing evidence. No figures changed otherwise.</li>
<li><span class="fn">{EDITION}.1</span> &middot; 2026-10-18<br>Initial release. 2025 and 2026 IRS releases; {N_FILINGS:,} Schedule H filings; {len(F):,} filers; 1,649 systems; 1,074 ranked.</li>
</ul>
<h2>How to cite</h2>
<p>{E(PUBLISHER)}, <em>{E(REPORT_TITLE)}</em>, Report No. {REPORT_NO}, {EDITION} edition, data as of {DATA_ASOF}. {SITE}{BASE}/</p>
<h2>Licence</h2><p>The figures are public records. The tables and scripts may be reused with attribution to {E(PUBLISHER)}.</p>
</div>{FOOT}"""
write('data.html', data)


# ---------- for local groups ----------
state_links = ''.join(f'<a href="{BASE}/state/{a}.html">{E(n)} <span class="note" style="display:inline">({c})</span></a>' for a, n, c, m in sorted(state_index_rows, key=lambda x: x[1]))
local = HEAD('For local groups and officeholders', 'How to use this report for your hospital, your state, or your district: pages, cards, sentences and data, free to take.', here=f'{BASE}/for-local-groups.html', url=f'{BASE}/for-local-groups.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition</p>
<h1 class="title">For local groups and officeholders</h1>
<p class="lede">This report was built so that anyone, anywhere in the country, can put their own hospital's numbers in front of their own town. Everything here is free to take. You do not need permission and you do not need to agree with us about anything; the numbers are the hospitals' own.</p>
<h2><span class="n">&sect;1</span>Find your hospital</h2>
<div class="toolbar"><input type="search" id="q" placeholder="Type a hospital system, a chief executive, or a state code"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD()}<tbody>{''.join(row(s) for s in ranked)}</tbody></table></div>
<p class="note">Every row links to the system's page, which has its card, its filing, and the sentence below.</p>
<h2><span class="n">&sect;2</span>Find your state</h2>
<div class="statelist">{state_links}</div>
<h2><span class="n">&sect;3</span>What you can take</h2>
<div class="prose">
<p><strong>The card.</strong> Every system and every state has a 1200 by 630 image with its numbers, the fiscal year, the EIN and the source on it, so it survives being screenshotted and forwarded. Download it from the system's page, or just post the page's link: the card appears on its own.</p>
<p><strong>The sentence.</strong> Each system page has a one-sentence version with the numbers and the link, ready to paste into a post, a newsletter, or a floor speech. It reads like this: <em>{E(hl_over[0]['name'])} paid chief executive {E(hl_over[0]['ceo'])} {money(hl_over[0]['pay'], False)} in the fiscal year ending {hl_over[0]['fye']}. It spent {pct(hl_over[0]['ccp'])} of expenses on charity care, {money(hl_over[0]['cc'], False)}. Source: its own IRS Form 990.</em></p>
<p><strong>The embed.</strong> One line of HTML that puts the card on your site, linked to the page.</p>
<p><strong>The data.</strong> The whole dataset is on the <a href="{BASE}/data.html">data page</a>, with a <a href="{BASE}/manual.html">manual</a> for rebuilding it, and a <a href="{BASE}/press-kit.zip" download>press kit</a> with the summary card and the list of {len(hl_over)} as a spreadsheet.</p>
<h2><span class="n">&sect;4</span>If the hospital answers</h2>
<p>Send us the reply. Replies from institutions named in this report are published in full on the report page, and the hospital's own filing is the answer to most of them. The usual one is a larger charity-care number than ours; that number is almost always at list price, and the IRS requires the figure on the form to be at cost. The <a href="{BASE}/methodology.html">methodology</a> explains it in a paragraph you can quote.</p>
<p>Contact: contact@everythingisbroken.org.</p>
</div>
{SORT_JS}{FOOT}"""
write('for-local-groups.html', local)

# ---------- press kit (csv written earlier, after findings) ----------
readme = f"""{PUBLISHER}
{REPORT_TITLE}, {SERIES}, {EDITION} edition. Data as of {DATA_ASOF}.
{SITE}{BASE}/

HEADLINE
{HEADLINE} {HEADLINE_SUB}

WHAT IS IN THIS KIT
summary.png                         The headline card (1200 x 630), free to publish.
ceo_pay_exceeds_charity_care.csv    The {len(hl_over)} systems, with CEO pay, charity care, the ratio, fiscal year, EIN, a link to the filing and a link to the page.
method.txt                          The method in one page.

DEFINITIONS
CEO pay: total compensation on Form 990 Part VII (columns D, E and F): salary and bonus from the organization and related organizations, plus deferred compensation and benefits.
Charity care: Schedule H Part I line 7a, financial assistance at cost, net of any payment received for it. Not bad debt, not Medicaid shortfall. The IRS requires it at cost, not at list price.
Systems: filings reporting the same chief executive are combined; every combination over $1 billion was checked by hand. Children's hospitals and specialty hospitals (rehabilitation, long-term acute care, cancer, behavioral) are excluded from the headline count and listed with the reason in headline_exclusions.csv on the data page.

EVERY FIGURE links to the filing it came from. Full dataset, scripts and a reproduction manual: {SITE}{BASE}/data.html
Contact: contact@everythingisbroken.org. Corrections: send the filing that contradicts a figure.
"""
method = f"""METHOD, IN ONE PAGE

Source. Every nonprofit hospital files IRS Form 990 with Schedule H. The IRS publishes every e-filed return as XML. This report reads the 2025 and 2026 releases, keeps the {N_FILINGS:,} filings that include Schedule H, and takes the latest fiscal year for each of {len(F):,} filers.

CEO pay. Form 990 Part VII lists officers and the highest-paid employees with three compensation columns: from the organization, from related organizations, and other (deferred pay and benefits). CEO pay is the sum. The chief executive is the person whose title says CEO or chief executive and is not marked former; where the filing is ambiguous it was read by hand and the decision recorded with its reason.

Charity care. Schedule H Part I line 7a: free or discounted care under the hospital's own financial assistance policy, at cost, net of payments received for it. The IRS does not accept charges (list price). Bad debt and Medicaid shortfall are separate lines and are not counted.

Systems. Filings reporting the same chief executive are one system; revenue, expenses and charity care are summed and the executive counted once. Where a system's hospitals file under local presidents, a shared system officer in Part VII is the test for membership. Every combination over $1 billion was checked by hand.

The headline count. General hospital systems with revenue over ${HEADLINE_MIN_REV/1e6:.0f} million where CEO pay exceeded charity care. Children's hospitals (Medicaid covers most low-income children) and specialty hospitals are excluded and listed with reasons. Each of the {len(hl_over)} was checked against its filing, including the Part VI narrative, for charity care reported on another line; none was found.

Independent check. CEO pay was compared against CEO Paycheck, which reads the same filings with its own method: 121 of 129 shared systems agree to the dollar; the eight differences are explained in the reproduction manual.

What the report does not do. It does not estimate the value of the tax exemption, does not count public hospitals (they file no Form 990), and does not say whether anyone is overpaid. It puts two of the hospital's own numbers beside each other.

Full manual, every rule and every manual decision: {SITE}{BASE}/manual.html
"""
open(os.path.join(DATA, 'README.txt'), 'w').write(readme)
with zipfile.ZipFile(os.path.join(OUT, 'press-kit.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('README.txt', readme); z.writestr('method.txt', method); z.writestr('ceo_pay_exceeds_charity_care.csv', hl_csv.getvalue())
    if os.path.exists(os.path.join(CARD_DIR, 'summary.png')): z.write(os.path.join(CARD_DIR, 'summary.png'), 'summary.png')

# ---------- summary for the main page and for anyone who wants the headline numbers as JSON ----------
summary = {'report_no': REPORT_NO, 'title': REPORT_TITLE, 'series': SERIES, 'edition': EDITION, 'data_as_of': DATA_ASOF, 'built': BUILD,
    'headline': HEADLINE, 'headline_sub': HEADLINE_SUB, 'headline_min_revenue': HEADLINE_MIN_REV, 'headline_universe': len(hl_all), 'headline_count': len(hl_over), 'headline_ceo_pay_total': HL_PAY, 'headline_charity_care_total': HL_CC,
    'summary_card': f'{SITE}{BASE}/cards/summary.png',
    'filings': N_FILINGS, 'filers': len(F), 'systems': len(S), 'ranked': len(ranked), 'systems_over_1b': len(big),
    'median_charity_care_pct_over_1b': round(MED_CC, 2), 'median_ceo_pay_pct_of_charity_care_over_1b': round(MED_RATIO, 1),
    'share_over_1b_under_1pct': round(UNDER1), 'over_1b_ceo_paid_more_than_charity_care': len(OVER100),
    'ceo_paid_more_than_charity_care': [{'system': s['name'], 'state': s['state'], 'ceo': s['ceo'], 'ceo_pay': s['pay'], 'charity_care': s['cc'], 'ratio_pct': s['ratio'], 'card': f"{SITE}{BASE}/cards/system/{s['slug']}.png", 'url': f"{SITE}{BASE}/system/{s['slug']}.html"} for s in hl_over],
    'giants_by_charity_care_pct': [{'system': s['name'], 'state': s['state'], 'revenue': s['rev'], 'charity_care': s['cc'], 'charity_care_pct': s['ccp'], 'ceo': s['ceo'], 'ceo_pay': s['pay']} for s in giants],
    'top10': [{'rank': s['rank'], 'system': s['name'], 'ceo': s['ceo'], 'state': s['state'], 'ceo_pay': s['pay'], 'charity_care': s['cc'], 'charity_care_pct': s['ccp'], 'ceo_pay_pct_of_charity_care': s['ratio'], 'url': f"{SITE}{BASE}/system/{s['slug']}.html"} for s in ranked[:10]]}
write('summary.json', json.dumps(summary, indent=1))

# ---------- main page blocks ----------
top10 = '\n'.join(row(s) for s in ranked[:10])

BLOCKS = {
'latest': f"""<div class="absolute top-0 right-0 bg-black text-white px-3 py-1 text-xs uppercase tracking-widest">Latest Report</div>
<div class="text-xs uppercase tracking-widest text-gray-500 mb-2 font-mono">Report <span class="fig">No. {REPORT_NO}</span> | <span class="fig">{EDITION}</span> edition | Data as of <span class="fig">{DATA_ASOF}</span></div>
<h3 class="text-2xl font-bold mb-3">{E(REPORT_TITLE)}</h3>
<p class="text-xl sm:text-2xl font-bold leading-snug mb-2">{E(HEADLINE)}</p>
<p class="text-sm text-gray-700 mb-4">{E(HEADLINE_SUB)}</p>
{STATS}
<ul class="list-disc list-outside ml-5 mb-5 text-sm space-y-1">
<li>The largest of the {len(hl_over)}: {E(hl_over[0]['name'])} ({E(hl_over[0]['state'])}) paid {E(hl_over[0]['ceo'])} {money(hl_over[0]['pay'])} and gave {money(hl_over[0]['cc'])} to patients who could not pay.</li>
<li>{E(kaiser['name'])} shows the biggest systems can do it: {pct(kaiser['ccp'])} of expenses, {money(kaiser['cc'])}, the most of any system over $10 billion.{(' ' + E(advocate['name']) + ', at ' + pct(advocate['ccp']) + ', is near the bottom.') if advocate else ''}</li>
<li>The highest rates are at large regional systems: {E(best[0]['name'])} ({best[0]['state']}) {pct(best[0]['ccp'])}, {E(best[1]['name'])} ({best[1]['state']}) {pct(best[1]['ccp'])}, {E(best[2]['name'])} ({best[2]['state']}) {pct(best[2]['ccp'])}.</li>
</ul>
<p class="mb-5 text-gray-700">Every figure is the hospital's own, from its IRS Form 990, and every row links to the filing.</p>
<a href="{BASE}/" class="inline-block border-2 border-black px-6 py-2 uppercase tracking-wide text-sm font-bold hover:bg-black hover:text-white transition-colors mr-3 mb-2">Read the Full Report &rarr;</a>
<a href="{BASE}/for-local-groups.html" class="inline-block px-2 py-2 uppercase tracking-wide text-sm underline hover:text-gray-600 mb-2 mr-3">For local groups</a>
<a href="{BASE}/press-kit.zip" class="inline-block px-2 py-2 uppercase tracking-wide text-sm underline hover:text-gray-600 mb-2" download>Press kit</a>""",

'report1': f"""<div class="text-sm uppercase tracking-widest text-gray-500 mb-2">Report <span class="fig">No. {REPORT_NO}</span> | <span class="fig">{EDITION}</span> edition | Data as of <span class="fig">{DATA_ASOF}</span></div>
<h2 class="text-3xl font-bold mb-3"><a href="{BASE}/" class="hover:underline">{E(REPORT_TITLE)}</a></h2>
<p class="text-xl font-bold leading-snug mb-2">{E(HEADLINE)}</p>
<p class="text-sm text-gray-700 mb-4">{E(HEADLINE_SUB)}</p>
<p class="mb-4">Annual. Built from <span class="fig">{N_FILINGS:,}</span> IRS Schedule H filings covering <span class="fig">{len(F):,}</span> filers, combined into <span class="fig">{len(S):,}</span> hospital systems, of which <span class="fig">{len(ranked):,}</span> have an identifiable chief executive and positive charity care and are ranked. The median large system spends <span class="fig">{MED_CC:.2f}</span> percent of expenses on charity care and pays its chief executive <span class="fig">{MED_RATIO:.0f}</span> percent of that amount.</p>
{STATS}
<p class="mb-2 font-bold uppercase text-sm tracking-widest">Highest-paid CEOs (Top 10 of {len(ranked):,})</p>
<p class="text-xs text-gray-600 mb-2">Click any column header to sort, or click a system to inspect its full IRS Form 990 filing breakdown.</p>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD()}<tbody>
{top10}
</tbody></table></div>
<p class="text-sm text-gray-600 mb-8">CEO pay is Form 990 Part VII total compensation. Charity care is Schedule H Part I line 7a, the hospital's own figure. Full definitions in the <a class="underline" href="{BASE}/methodology.html">methodology</a>.</p>
<div class="space-y-3">
<a href="{BASE}/" class="block hover:underline font-bold">&#8627; Top 100 systems by CEO pay</a>
<a href="{BASE}/all.html" class="block hover:underline font-bold">&#8627; Complete ranking, all {len(ranked):,} systems, searchable and sortable</a>
<a href="{BASE}/states.html" class="block hover:underline font-bold">&#8627; By state, {len(bystate)} states and territories</a>
<a href="{BASE}/methodology.html" class="block hover:underline font-bold">&#8627; Methodology, in plain language</a>
<a href="{BASE}/manual.html" class="block hover:underline font-bold">&#8627; Reproduction manual, every rule and every manual decision</a>
<a href="{BASE}/data.html" class="block hover:underline font-bold">&#8627; Data files and scripts</a>
<a href="{BASE}/for-local-groups.html" class="block hover:underline font-bold">&#8627; For local groups and officeholders: cards, sentences and data for your hospital and your state</a>
<a href="{BASE}/press-kit.zip" class="block hover:underline font-bold" download>&#8627; Press kit: the summary card, the list of {len(hl_over)}, the method in one page</a>
</div>
<p class="mt-8 text-sm"><strong>Rebuttals received:</strong> none. Institutions named in this report may write to contact@everythingisbroken.org; replies are published in full on the report page.</p>""",

'data': f"""<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
<div class="border border-black p-6">
<h3 class="text-xl font-bold mb-3 uppercase tracking-wider">Dataset Download</h3>
<p class="text-sm mb-1">Report No. {REPORT_NO}, {EDITION} edition, data as of <span class="fig">{DATA_ASOF}</span>. Append-only: superseded rows are flagged, never removed. Every row carries its source filing and retrieval method.</p>
<ul class="text-sm font-mono my-4 space-y-2">
<li><a class="underline" href="{DATA_URL}/systems_rollup.csv" download>systems_rollup.csv</a> <span class="text-gray-500">{size(os.path.join(DATA,'systems_rollup.csv'))}, one row per system</span></li>
<li><a class="underline" href="{DATA_URL}/filers_latest.csv" download>filers_latest.csv</a> <span class="text-gray-500">{size(os.path.join(DATA,'filers_latest.csv'))}, one row per filer</span></li>
<li><a class="underline" href="{DATA_URL}/hospital_data.csv.gz" download>hospital_data.csv.gz</a> <span class="text-gray-500">{size(os.path.join(DATA,'hospital_data.csv.gz'))}, master table, {nrows(os.path.join(DATA,'hospital_data.csv.gz')):,} rows</span></li>
<li><a class="underline" href="{DATA_URL}/ceo_pay_exceeds_charity_care.csv" download>ceo_pay_exceeds_charity_care.csv</a> <span class="text-gray-500">the headline list, {len(hl_over)} rows</span></li>
<li><a class="underline" href="{DATA_URL}/SHA256SUMS" download>SHA256SUMS</a></li>
</ul>
<a href="{BASE}/data.html" class="underline hover:text-gray-600 block text-sm font-bold">All files, overrides, checksums and scripts &rarr;</a>
</div>
<div class="border border-black p-6">
<h3 class="text-xl font-bold mb-3 uppercase tracking-wider">Reproduction Manual</h3>
<p class="text-sm mb-4">A complete, self-contained procedure for rebuilding the dataset from the IRS bulk files: definitions with form lines and XML element names, the scripts in order, every decision rule, the override files, nine validation checks, known limits, and the annual re-run. Written so another person or another LLM can do it with no prior knowledge of this project.</p>
<a href="{BASE}/manual.html" class="underline hover:text-gray-600 block text-sm font-bold mt-2">Read the Manual &rarr;</a>
<a href="/pipeline/REPRODUCTION_MANUAL.md" class="underline hover:text-gray-600 block text-sm mt-2">Plain-text version</a>
</div>
<div class="border border-black p-6">
<h3 class="text-xl font-bold mb-3 uppercase tracking-wider">Primary Sources</h3>
<ul class="list-disc list-outside ml-4 text-sm space-y-2">
<li><a class="underline" href="https://www.irs.gov/charities-non-profits/form-990-series-downloads">IRS Form 990 bulk XML</a>, 2025 and 2026 releases</li>
<li><a class="underline" href="https://www.irs.gov/forms-pubs/about-schedule-h-form-990">IRS Schedule H</a>, Part I line 7a</li>
<li><a class="underline" href="https://projects.propublica.org/nonprofits/">ProPublica Nonprofit Explorer</a>, linked from every system page</li>
</ul>
</div>
<div class="border border-black p-6">
<h3 class="text-xl font-bold mb-3 uppercase tracking-wider">Version Log</h3>
<p class="text-sm mb-4">What changed in each release of the data, dated.</p>
<div class="font-mono text-xs text-gray-600 space-y-1">
<p>[<span class="fig">2026-10-21</span>] v{EDITION}.3 - Review of the CEO-pay-exceeds-charity-care list; five systems assembled from their filings; specialty exclusions published.</p>
<p>[<span class="fig">2026-10-20</span>] v{EDITION}.2 - Parkview Health assembled from ten filings.</p>
<p>[<span class="fig">2026-10-18</span>] v{EDITION}.1 - Initial release: {N_FILINGS:,} Schedule H filings, {len(F):,} filers, 1,649 systems, 1,074 ranked.</p>
</div>
</div>
</div>
<div class="mt-8 pt-6 rule-single text-sm">
<p><strong>How to cite this data:</strong> {E(PUBLISHER)}, <em>"{E(REPORT_TITLE)},"</em> Report No. {REPORT_NO}, <span class="fig">{EDITION}</span> edition, data as of <span class="fig">{DATA_ASOF}</span>. everythingisbroken.org{BASE}/</p>
</div>""",
}
ip = os.path.join(REPO, 'index.html'); page = open(ip).read(); missing = []
for name, body in BLOCKS.items():
    pat = re.compile(rf'(<!-- gen:{name} -->).*?(<!-- /gen:{name} -->)', re.S)
    if not pat.search(page): missing.append(name); continue
    page = pat.sub(lambda m: m.group(1) + '\n' + body + '\n' + m.group(2), page)
open(ip, 'w').write(page)

print(f'wrote index, all, {n_sys} system pages, {len(bystate)} state pages, methodology, manual, data, summary.json -> {OUT}')
print(f'ranked {len(ranked)}; big non-children {len(big)}; median CC {MED_CC:.2f}; median ratio {MED_RATIO:.1f}; under1 {UNDER1:.0f}%; over100 {len(OVER100)}')
print('main page blocks updated:', [k for k in BLOCKS if k not in missing], 'missing markers:', missing)
