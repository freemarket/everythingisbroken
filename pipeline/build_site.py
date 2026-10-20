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
PUBLISHER = 'Everything Is Broken'
SUBLINE = 'Office of Institutional Accounts'
SITE = 'https://everythingisbroken.org'
EDITION = '2026'
DATA_ASOF = '2026-10-18'        # date the IRS releases were pulled and the tables built
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
DISPLAY = {'36-2169147':'Advocate Health (Midwest)','13-3971298':'NYU Langone Health','13-3957095':'NewYork-Presbyterian','13-1740114':'Montefiore Health System','35-2528741':'Vanderbilt University Medical Center','39-0816848':'Mercyhealth','94-1105628':'Kaiser Permanente (Hospitals)','36-4724966':'Northwestern Medicine','11-2965586':'Northwell Health','38-1357020':'Henry Ford Health','20-8295721':'UPMC','94-1196203':'CommonSpirit Health (Dignity)','45-0233470':'Banner Health','52-1301088':'Bon Secours Mercy Health','36-2167060':'Endeavor Health','36-2174823':'Rush University System for Health','36-3488183':'UChicago Medicine','36-4015560':'Loyola Medicine','36-1509000':'Sinai Chicago (Mount Sinai)','36-2170133':'Holy Cross Hospital (Sinai Chicago)','36-2264414':'St. Bernard Hospital'}

# ---------- load ----------
S = list(csv.DictReader(open(os.path.join(DATA, 'systems_rollup.csv'))))
F = {r['ein']: r for r in csv.DictReader(open(os.path.join(DATA, 'filers_latest.csv')))}
for s in S:
    s['rev'] = f(s['total_revenue']); s['exp'] = f(s['total_expenses']); s['cc'] = f(s['charity_care_net'])
    s['ccp'] = f(s['charity_care_pct_computed']); s['pay'] = f(s['ceo_comp_total']); s['ratio'] = f(s['ceo_pay_pct_of_charity_care'])
    s['cb'] = f(s['total_cb_net']); s['bad'] = f(s['bad_debt']); s['na'] = f(s['net_assets']); s['emp'] = f(s['employees'])
    s['name'] = DISPLAY.get(s['lead_ein'], re.sub(r'\s+(Inc|Corp|Corporation|Group Return|Group|Incorporated|Llc|Co)\.?$', '', titlecase(s['lead_filer']), flags=re.I)); s['slug'] = slug(s['lead_filer'] + '-' + s['lead_ein'])
    s['ceo'] = person(s['ceo_name']); s['pub'] = s['publishable'] == 'yes'; s['kids'] = s['childrens_hospital'] == 'yes'
    lead = F.get(s['lead_ein'], {}); s['oid'] = lead.get('object_id', ''); s['fye'] = lead.get('fye', '')
    s['members'] = [(e, F[e]) for e in s['member_eins'].split(';') if e in F]
ranked = sorted([s for s in S if s['pub'] and s['pay']], key=lambda s: -s['pay'])
for i, s in enumerate(ranked, 1): s['rank'] = i
big = [s for s in ranked if (s['rev'] or 0) >= 1e9 and not s['kids']]
MED_CC = st.median([s['ccp'] for s in big if s['ccp'] is not None]); MED_RATIO = st.median([s['ratio'] for s in big if s['ratio']])
UNDER1 = sum(1 for s in big if s['ccp'] is not None and s['ccp'] < 1) / len(big) * 100
OVER100 = [s for s in big if s['ratio'] and s['ratio'] >= 100]
N_FILINGS = 19245  # Schedule H XML filings read from the 2025 and 2026 IRS releases (Reproduction manual, section 5)

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
.rule-double{border-top:4px double var(--ink)}
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

SITE_NAV = [('main','Main'),('reports','Reports'),('data','Data'),('contact','Contact'),('about','About'),('standards','Standards')]
REPORT_NAV = [(f'{BASE}/','Ranking'),(f'{BASE}/all.html','Complete list'),(f'{BASE}/states.html','By state'),(f'{BASE}/methodology.html','Methodology'),(f'{BASE}/manual.html','Reproduction manual'),(f'{BASE}/data.html','Data files')]

def HEAD(title, desc='', here=None, wide=True):
    site_nav = ''.join(f'<a href="/#{k}"{" class=on" if k=="reports" else ""}>{v}</a>' for k, v in SITE_NAV)
    rep_nav = ''.join(f'<a href="{u}"{" class=on" if u==here else ""}>{v}</a>' for u, v in REPORT_NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} - {E(PUBLISHER)}</title>
<meta name="description" content="{E(desc)}">
<link rel="icon" type="image/png" href="/logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="sheet">
<header class="mast">
<a class="seal" href="/" aria-label="{E(PUBLISHER)} home"><img src="/logo.png" alt="Official Seal, {E(PUBLISHER)} ({EDITION})"></a>
<h1>{E(PUBLISHER)}</h1>
<div class="rule-double"></div>
<p class="sub">{E(SUBLINE)}</p>
<nav class="site">{site_nav}</nav>
<div class="band"><span class="rep">Report No. {REPORT_NO} &middot; {E(REPORT_TITLE)} &middot; {EDITION} edition</span><nav>{rep_nav}</nav></div>
</header>
<main>
"""
FOOT = f"""</main>
<footer><div class="rule-single"></div>
<div class="links"><a href="/#reports">Reports</a>|<a href="/#data">Data</a>|<a href="/#contact">Contact</a>|<a href="/#about">About</a>|<a href="/#standards">Standards</a></div>
<p>Report No. {REPORT_NO}, {EDITION} edition &middot; Data as of {DATA_ASOF} &middot; Built {BUILD}</p>
<p>Every figure is taken from the hospital's own IRS Form 990 as published by the IRS and is linked on the page where it appears. Corrections: send the filing that contradicts a figure to corrections@everythingisbroken.org.</p>
<p>Everything Is Broken never supports violence, threats, or harassment of any kind. We believe institutional reform must happen through transparency, the open exchange of ideas, and vigorous public discourse.</p>
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

def write(path, body):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(body)

STATS = f"""<div class="stat-row">
<div class="stat"><div class="v">{len(ranked):,}</div><div class="l">systems ranked, of {len(S):,} identified in {N_FILINGS:,} IRS Schedule H filings</div></div>
<div class="stat"><div class="v">{MED_CC:.2f}%</div><div class="l">median share of expenses spent on charity care, systems over $1B</div></div>
<div class="stat"><div class="v">{UNDER1:.0f}%</div><div class="l">of systems over $1B spend under one percent</div></div>
<div class="stat"><div class="v red">{len(OVER100)}</div><div class="l">large systems whose chief executive was paid more than all charity care</div></div>
</div>"""

# ---------- index ----------
top = ranked[:100]
index = HEAD(REPORT_TITLE, f'{len(ranked)} nonprofit hospital systems ranked by CEO pay, beside what each spent on charity care. From their own IRS filings.', here=f'{BASE}/') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; Data as of {DATA_ASOF}</p>
<h1 class="title">{E(REPORT_TITLE)}</h1>
<p class="lede">The median large nonprofit hospital system spends about one cent of every dollar on charity care, and pays its chief executive {MED_RATIO:.0f} percent of that. Every figure on this page is from the hospital's own IRS Form 990, linked on every row.</p>
{STATS}
<h2><span class="n">&sect;1</span>Top 100 by CEO pay</h2>
<div class="toolbar"><input type="search" id="q" placeholder="Search a hospital, CEO, or state code"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<p class="note">Click a column to sort. Children’s hospitals are shown in grey: Medicaid covers most low-income children, so their charity care is structurally low.</p>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD()}<tbody>
{''.join(row(s) for s in top)}
</tbody></table></div>
<p class="note">Full list of {len(ranked)} systems on the <a href="{BASE}/all.html">complete ranking</a>. Systems where the chief executive could not be identified from the filing with confidence, or where charity care is reported on a line other than 7a, are excluded from the ranking and explained in the <a href="{BASE}/methodology.html">methodology</a>.</p>
<h2><span class="n">&sect;2</span>How to read it</h2>
<div class="prose">
<p><strong>CEO pay</strong> is total compensation reported on Form 990 Part VII: salary and bonus from the organization and its related organizations, plus deferred compensation and benefits (columns D, E and F). It is the figure the hospital's board approved and the hospital reported.</p>
<p><strong>Charity care</strong> is Schedule H Part I line 7a: free or discounted care given under the hospital's own financial assistance policy, at the hospital's cost. It is not bad debt and not the Medicaid shortfall, which hospitals often add when they describe their community benefit publicly. The IRS form keeps them separate; so does this report.</p>
<p>Hospitals usually describe their charity care at charges, the list prices on their chargemaster, which run several times what the care costs to deliver. The IRS does not accept that figure. Line 7a must be reported at cost, using either the hospital’s cost accounting system or its own ratio of total expenses to total charges, and net of any payment received for the care. When a hospital’s press release gives a larger charity-care number than this report, that is almost always the difference.</p>
<p><strong>The ratio</strong> is CEO pay divided by charity care. At 100 percent, one person was paid as much as the system gave to every patient who could not pay.</p>
<p>A nonprofit hospital pays no federal income tax and, in nearly every state, no property or sales tax. The exemption is granted on the premise that the hospital serves the community in ways a business would not. This report puts two of the hospital's own numbers beside each other and lets the reader decide whether the premise holds.</p>
</div>
<h2><span class="n">&sect;3</span>Rebuttals</h2>
<div class="prose"><p>Institutions named in this report may reply to rebuttals@everythingisbroken.org. Replies are published here in full. None has been received.</p></div>
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
    page = HEAD(s['name'], f"{s['name']}: CEO pay {money(s['pay'])}, charity care {pct(s['ccp'])} of expenses, from its IRS Form 990.") + f"""
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
{FOOT}"""
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
    body = HEAD(f"{STATES.get(st_, st_)} hospitals", f"Nonprofit hospital systems in {STATES.get(st_, st_)} ranked by CEO pay.", here=f'{BASE}/states.html') + f"""
<p class="doc-no">Report No. {REPORT_NO} &middot; {EDITION} edition &middot; <a href="{BASE}/states.html">all states</a></p>
<h1 class="title">{E(STATES.get(st_, st_))}</h1>
<p class="lede">{len(lst)} nonprofit hospital systems file from {E(STATES.get(st_, st_))}. Median charity care: {pct(med)} of expenses.</p>
<div class="toolbar"><input type="search" id="q" placeholder="Search"><label><input type="checkbox" id="kids" checked> Include children’s hospitals</label></div>
<div class="tablewrap"><table class="sortable">{TABLE_HEAD(False)}<tbody>{''.join(row(s, False) for s in pubs)}</tbody></table></div>
<p class="note">Systems not shown: {len(lst)-len(pubs)} with an unidentifiable chief executive or charity care reported off line 7a. Each has its own page: {', '.join(f'<a href="{BASE}/system/{s["slug"]}.html">{E(s["name"])}</a>' for s in lst if not s['pub']) or 'none'}.</p>
{SORT_JS}{FOOT}"""
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
<h2>Charity care</h2><p>Schedule H Part I line 7a, "financial assistance at cost": free or discounted care given under the hospital's written financial assistance policy, valued at cost. Column (e), net of any grants received for it. The percentage of expenses is the figure the hospital itself filed in column (f). It excludes bad debt (Part III) and Medicaid shortfall (line 7b), which the IRS reports separately.</p>
<h2>Systems</h2><p>Many systems file one return per hospital. Filings that report the same chief executive are combined into one system: revenue, expenses and charity care are summed and the chief executive is counted once. Every combination above $1 billion in revenue was checked by hand. A parent entity that files no Schedule H but pays the chief executive (Advocate Health, for example) is joined to its hospitals' filings.</p>
<h2>Children's hospitals</h2><p>Medicaid and CHIP cover most low-income children, so children's hospitals report little uncompensated care and appear at the bottom of any charity care ranking. They are shown in grey and can be hidden from any table.</p>
<h2>What this report does not do</h2><p>It does not estimate the value of the tax exemption. It does not count public hospitals (county, state, veterans), which file no Form 990. It does not judge whether a chief executive is overpaid. It puts two of the hospital's own numbers beside each other.</p>
<h2>Independent check</h2><p>CEO pay figures were compared against CEO Paycheck, which reads the same filings with its own method: of 129 systems present in both, 121 agree on the person and the dollar amount. The eight differences are explained in section 7 of the <a href="{BASE}/manual.html">reproduction manual</a>.</p>
<h2>Corrections</h2><p>If a figure is wrong, send the filing that contradicts it to corrections@everythingisbroken.org. The correction runs at the top of the affected page with the date, and in the corrections log on the <a href="/#standards">Standards</a> page.</p>
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
<li><span class="fn">{EDITION}.1</span> &middot; {DATA_ASOF}<br>Initial release. 2025 and 2026 IRS releases; {N_FILINGS:,} Schedule H filings; {len(F):,} filers; {len(S):,} systems; {len(ranked):,} ranked.</li>
</ul>
<h2>How to cite</h2>
<p>{E(PUBLISHER)}, <em>{E(REPORT_TITLE)}</em>, Report No. {REPORT_NO}, {EDITION} edition, data as of {DATA_ASOF}. {SITE}{BASE}/</p>
<h2>Licence</h2><p>The figures are public records. The tables and scripts may be reused with attribution to {E(PUBLISHER)}.</p>
</div>{FOOT}"""
write('data.html', data)

# ---------- summary for the main page and for anyone who wants the headline numbers as JSON ----------
summary = {'report_no': REPORT_NO, 'title': REPORT_TITLE, 'edition': EDITION, 'data_as_of': DATA_ASOF, 'built': BUILD,
    'filings': N_FILINGS, 'filers': len(F), 'systems': len(S), 'ranked': len(ranked), 'systems_over_1b': len(big),
    'median_charity_care_pct_over_1b': round(MED_CC, 2), 'median_ceo_pay_pct_of_charity_care_over_1b': round(MED_RATIO, 1),
    'share_over_1b_under_1pct': round(UNDER1), 'over_1b_ceo_paid_more_than_charity_care': len(OVER100),
    'top10': [{'rank': s['rank'], 'system': s['name'], 'ceo': s['ceo'], 'state': s['state'], 'ceo_pay': s['pay'], 'charity_care': s['cc'], 'charity_care_pct': s['ccp'], 'ceo_pay_pct_of_charity_care': s['ratio'], 'url': f"{SITE}{BASE}/system/{s['slug']}.html"} for s in ranked[:10]]}
write('summary.json', json.dumps(summary, indent=1))

# ---------- main page blocks ----------
top10 = '\n'.join(row(s) for s in ranked[:10])

BLOCKS = {
'latest': f"""<div class="absolute top-0 right-0 bg-black text-white px-3 py-1 text-xs uppercase tracking-widest">Latest Report</div>
<div class="text-xs uppercase tracking-widest text-gray-500 mb-2 font-mono">Report <span class="fig">No. {REPORT_NO}</span> | <span class="fig">{EDITION}</span> edition | Data as of <span class="fig">{DATA_ASOF}</span></div>
<h3 class="text-2xl font-bold mb-4">{E(REPORT_TITLE)}</h3>
{STATS}
<p class="mb-5 text-gray-700">Every figure is the hospital's own, from its IRS Form 990, and every row links to the filing.</p>
<a href="{BASE}/" class="inline-block border-2 border-black px-6 py-2 uppercase tracking-wide text-sm font-bold hover:bg-black hover:text-white transition-colors mr-3 mb-2">Read the Full Report &rarr;</a>
<a href="#reports" onclick="showSection('reports')" class="inline-block px-2 py-2 uppercase tracking-wide text-sm underline hover:text-gray-600 mb-2">Report index</a>""",

'report1': f"""<div class="text-sm uppercase tracking-widest text-gray-500 mb-2">Report <span class="fig">No. {REPORT_NO}</span> | <span class="fig">{EDITION}</span> edition | Data as of <span class="fig">{DATA_ASOF}</span></div>
<h2 class="text-3xl font-bold mb-4"><a href="{BASE}/" class="hover:underline">{E(REPORT_TITLE)}</a></h2>
<p class="mb-4">National and annual. Built from <span class="fig">{N_FILINGS:,}</span> IRS Schedule H filings covering <span class="fig">{len(F):,}</span> filers, combined into <span class="fig">{len(S):,}</span> hospital systems, of which <span class="fig">{len(ranked):,}</span> have an identifiable chief executive and positive charity care and are ranked. The median large system spends <span class="fig">{MED_CC:.2f}</span> percent of expenses on charity care and pays its chief executive <span class="fig">{MED_RATIO:.0f}</span> percent of that amount.</p>
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
</div>
<p class="mt-8 text-sm"><strong>Rebuttals received:</strong> none. Institutions named in this report may write to rebuttals@everythingisbroken.org; replies are published in full on the report page.</p>""",

'data': f"""<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
<div class="border border-black p-6">
<h3 class="text-xl font-bold mb-3 uppercase tracking-wider">Dataset Download</h3>
<p class="text-sm mb-1">Report No. {REPORT_NO}, {EDITION} edition, data as of <span class="fig">{DATA_ASOF}</span>. Append-only: superseded rows are flagged, never removed. Every row carries its source filing and retrieval method.</p>
<ul class="text-sm font-mono my-4 space-y-2">
<li><a class="underline" href="{DATA_URL}/systems_rollup.csv" download>systems_rollup.csv</a> <span class="text-gray-500">{size(os.path.join(DATA,'systems_rollup.csv'))}, one row per system</span></li>
<li><a class="underline" href="{DATA_URL}/filers_latest.csv" download>filers_latest.csv</a> <span class="text-gray-500">{size(os.path.join(DATA,'filers_latest.csv'))}, one row per filer</span></li>
<li><a class="underline" href="{DATA_URL}/hospital_data.csv.gz" download>hospital_data.csv.gz</a> <span class="text-gray-500">{size(os.path.join(DATA,'hospital_data.csv.gz'))}, master table, {nrows(os.path.join(DATA,'hospital_data.csv.gz')):,} rows</span></li>
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
<p>[<span class="fig">{DATA_ASOF}</span>] v{EDITION}.1 - Initial release: {N_FILINGS:,} Schedule H filings, {len(F):,} filers, {len(S):,} systems, {len(ranked):,} ranked.</p>
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
